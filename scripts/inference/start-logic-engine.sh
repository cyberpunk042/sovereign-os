#!/usr/bin/env bash
# scripts/inference/start-logic-engine.sh — start the Logic Engine
# tier on the RTX 5090 (32 GB Blackwell GB202, internal secondary,
# PCIEX16_2 x8). Per operator directive 2026-07-14 (D-022) the Logic
# tier runs on the internal 5090 — more bandwidth than the RTX 4090 on
# the PCIe 4.0 x4 OcuLink eGPU. The RTX 4090 (operator §17.1's original
# Logic card) is now the OcuLink eGPU / opt-in VFIO sandbox and the
# DSpark speculative-decode draft target. Backend pluggable:
#   - vllm (default; podman-launched)
#   - llama_cpp (fallback for hardware constraints / debugging)
#
# Per SDD-011 routing rule 4 + default, the router sends json_object /
# tools / general requests here.
#
# Env vars (all overridable; sain-01 defaults shown):
#   SOVEREIGN_OS_LOGIC_BACKEND  vllm | llama_cpp (default: vllm)
#   LOGIC_MODEL                 Path to weights (default: /mnt/vault/models/qwen3-coder)
#   LOGIC_HOST                  Listen host (default: 127.0.0.1)
#   LOGIC_PORT                  Listen port (default: 8082 — router routes here)
#   SOVEREIGN_OS_DRY_RUN        Print argv + exit without exec
#   SOVEREIGN_OS_METRICS_DISABLE  Skip Layer B metrics

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__SCRIPT_DIR}/../build/lib/common.sh"
# shellcheck source=../build/lib/observability.sh
. "${__SCRIPT_DIR}/../build/lib/observability.sh"
# shellcheck source=../build/lib/runtime-profile.sh
. "${__SCRIPT_DIR}/../build/lib/runtime-profile.sh"

STEP_ID="inference-logic-engine"
TIER="logic_engine"

# R151: honor active runtime profile § 18 logic-tier allocation
runtime_profile_override LOGIC_MODEL logic model

: "${SOVEREIGN_OS_LOGIC_BACKEND:=vllm}"
: "${LOGIC_MODEL:=/mnt/vault/models/qwen3-coder}"
: "${LOGIC_HOST:=127.0.0.1}"
: "${LOGIC_PORT:=8082}"

# Export so the inline python3 (subshell) sees them via os.environ.
export SOVEREIGN_OS_LOGIC_BACKEND LOGIC_MODEL LOGIC_HOST LOGIC_PORT

log_step_header "${STEP_ID}" "start Logic Engine (backend=${SOVEREIGN_OS_LOGIC_BACKEND}, RTX 5090 internal secondary — operator D-022; the RTX 4090 is now the OcuLink eGPU / opt-in VFIO DSpark draft)"
runtime_profile_log_active

emit_start_metric() {
  emit_metric sovereign_os_inference_backend_start_total 1 \
    "tier=\"${TIER}\",backend=\"${SOVEREIGN_OS_LOGIC_BACKEND}\",result=\"$1\""
}

# Idempotency: already listening?
if command -v ss >/dev/null 2>&1 && ss -lnt "sport = :${LOGIC_PORT}" 2>/dev/null | grep -q LISTEN; then
  log_info "port ${LOGIC_PORT} already listening — logic engine appears up; no-op exit"
  emit_start_metric skip
  exit 0
fi

case "${SOVEREIGN_OS_LOGIC_BACKEND}" in
  vllm)
    require_command podman "apt install podman"
    argv=$(python3 - <<PY
import os, sys
sys.path.insert(0, "${__SCRIPT_DIR}")
from backends.vllm import VllmBackend
b = VllmBackend.for_logic_engine(os.environ["LOGIC_MODEL"])
b.config.host = os.environ["LOGIC_HOST"]
b.config.port = int(os.environ["LOGIC_PORT"])
print(" ".join(b.start_command()))
PY
)
    ;;
  llama_cpp)
    argv=$(python3 - <<PY
import os, sys
sys.path.insert(0, "${__SCRIPT_DIR}")
from backends.llama_cpp import LlamaCppBackend
b = LlamaCppBackend.for_sain01_fallback(os.environ["LOGIC_MODEL"])
b.config.host = os.environ["LOGIC_HOST"]
b.config.port = int(os.environ["LOGIC_PORT"])
print(" ".join(b.start_command()))
PY
)
    ;;
  *)
    log_error "unknown SOVEREIGN_OS_LOGIC_BACKEND: ${SOVEREIGN_OS_LOGIC_BACKEND}"
    emit_start_metric fail
    exit 1
    ;;
esac

log_info "argv: ${argv}"
log_info "model: ${LOGIC_MODEL}"
log_info "listening: http://${LOGIC_HOST}:${LOGIC_PORT}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN — not starting"
  emit_start_metric skip
  exit 0
fi

emit_start_metric success
emit_metric sovereign_os_inference_backend_pid $$ "tier=\"${TIER}\""
exec ${argv}
