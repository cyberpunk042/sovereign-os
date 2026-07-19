#!/usr/bin/env bash
# scripts/inference/start-oracle-hybrid.sh — serve a big-MoE catalog
# candidate via the llama.cpp RAM+VRAM hybrid (2026-07-19
# oracle-alternatives evaluation; see
# docs/evaluations/oracle-alternatives-glm47-m3-gptoss-2026-07-19.md).
#
# The hybrid envelope: GGUF <= ~350 GB serves with dense layers + KV on
# the internal Blackwell pair (RTX PRO 6000 96 GB + RTX 5090 32 GB,
# tensor-split 3,1) while routed experts stay in 256 GB DDR5 via
# llama.cpp --n-cpu-moe. No disk streaming. Targets: GLM-4.7 (358B-A32B,
# Q4 ~180-200 GB), MiniMax-M3 (427B-A23B, IQ3 ~159 GB). The RTX 4090
# OcuLink eGPU (PCIe 4.0 x4) is deliberately excluded from the split.
#
# Port 8086 is a BENCH/TRIAL endpoint, not a router tier — the
# throughput promotion gate drives it directly:
#   sovereign-osctl models eval run GLM-4.7 --benchmark throughput \
#       --endpoint http://127.0.0.1:8086/v1 --min-tok-s 10
# Routing the hybrid as a real tier is an operator decision AFTER the
# bench (catalog promotion path).
#
# Env vars (all overridable; sain-01 defaults shown):
#   HYBRID_MODEL           GGUF file OR a directory containing one
#                          (default: /mnt/vault/models/GLM-4.7 — the
#                          pull.sh --allow-candidate destination)
#   HYBRID_HOST            Listen host (default: 127.0.0.1)
#   HYBRID_PORT            Listen port (default: 8086 — bench endpoint)
#   HYBRID_N_CPU_MOE       Expert layers kept on CPU (default: 999 = all;
#                          tune DOWN to promote hot experts onto VRAM)
#   HYBRID_CTX             Context size (default: 16384)
#   HYBRID_TENSOR_SPLIT    Per-GPU dense split (default: "3,1" — 96:32
#                          VRAM ratio across PRO 6000 + 5090)
#   HYBRID_CPU_AFFINITY    Optional taskset range for the CPU expert
#                          matmuls (unset = no pinning; the CCD partition
#                          reserves CCD0 for Pulse — pin only if Pulse
#                          is idle during the trial)
#   SOVEREIGN_OS_DRY_RUN   Print argv + exit without exec
#   SOVEREIGN_OS_METRICS_DISABLE  Skip Layer B metrics

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__SCRIPT_DIR}/../build/lib/common.sh"
# shellcheck source=../build/lib/observability.sh
. "${__SCRIPT_DIR}/../build/lib/observability.sh"
# shellcheck source=../build/lib/runtime-profile.sh
. "${__SCRIPT_DIR}/../build/lib/runtime-profile.sh"

STEP_ID="inference-oracle-hybrid"
TIER="oracle_hybrid"

: "${HYBRID_MODEL:=/mnt/vault/models/GLM-4.7}"
: "${HYBRID_HOST:=127.0.0.1}"
: "${HYBRID_PORT:=8086}"
: "${HYBRID_N_CPU_MOE:=999}"
: "${HYBRID_CTX:=16384}"
: "${HYBRID_TENSOR_SPLIT:=3,1}"

# Resolve a directory (pull.sh destination) to its first GGUF shard —
# llama-server takes the -00001-of- file and loads the rest itself.
if [ -d "${HYBRID_MODEL}" ]; then
  first_gguf="$(find "${HYBRID_MODEL}" -maxdepth 1 -name '*.gguf' 2>/dev/null | sort | head -n1)"
  if [ -n "${first_gguf}" ]; then
    log_info "resolved GGUF inside ${HYBRID_MODEL}: ${first_gguf}"
    HYBRID_MODEL="${first_gguf}"
  else
    log_warn "HYBRID_MODEL is a directory with no .gguf inside: ${HYBRID_MODEL}"
    log_warn "  pull weights first: scripts/models/pull.sh <model-id> --allow-candidate"
  fi
fi

export HYBRID_MODEL HYBRID_HOST HYBRID_PORT HYBRID_N_CPU_MOE HYBRID_CTX \
  HYBRID_TENSOR_SPLIT HYBRID_CPU_AFFINITY="${HYBRID_CPU_AFFINITY:-}"

log_step_header "${STEP_ID}" "start oracle HYBRID (llama.cpp --n-cpu-moe=${HYBRID_N_CPU_MOE}; dense on Blackwell pair split ${HYBRID_TENSOR_SPLIT}; experts in DDR5; bench endpoint :${HYBRID_PORT} — NOT a router tier)"
runtime_profile_log_active

emit_start_metric() {
  emit_metric sovereign_os_inference_backend_start_total 1 \
    "tier=\"${TIER}\",backend=\"llama_cpp\",result=\"$1\""
}

# Idempotency: already listening?
if command -v ss >/dev/null 2>&1 && ss -lnt "sport = :${HYBRID_PORT}" 2>/dev/null | grep -q LISTEN; then
  log_info "port ${HYBRID_PORT} already listening — oracle hybrid appears up; no-op exit"
  emit_start_metric skip
  exit 0
fi

argv=$(python3 - <<PY
import os, sys
sys.path.insert(0, "${__SCRIPT_DIR}")
from backends.llama_cpp import LlamaCppBackend
b = LlamaCppBackend.for_sain01_hybrid(
    os.environ["HYBRID_MODEL"],
    port=int(os.environ["HYBRID_PORT"]),
    n_cpu_moe=int(os.environ["HYBRID_N_CPU_MOE"]),
    ctx_size=int(os.environ["HYBRID_CTX"]),
    tensor_split=os.environ["HYBRID_TENSOR_SPLIT"] or None,
)
b.config.host = os.environ["HYBRID_HOST"]
if os.environ.get("HYBRID_CPU_AFFINITY"):
    b.config.cpu_affinity = os.environ["HYBRID_CPU_AFFINITY"]
print(" ".join(b.start_command()))
PY
)

log_info "argv: ${argv}"
log_info "model: ${HYBRID_MODEL}"
log_info "listening: http://${HYBRID_HOST}:${HYBRID_PORT}"
log_info "bench next: sovereign-osctl models eval run <model-id> --benchmark throughput --endpoint http://${HYBRID_HOST}:${HYBRID_PORT}/v1 --min-tok-s <bar>"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN — not starting"
  emit_start_metric skip
  exit 0
fi

emit_start_metric success
emit_metric sovereign_os_inference_backend_pid $$ "tier=\"${TIER}\""
exec ${argv}
