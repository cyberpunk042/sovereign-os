#!/usr/bin/env bash
# scripts/inference/start-oracle-core.sh — Oracle Core on RTX PRO 6000
# Blackwell (vLLM native, host-resident; DFlash drafts when configured).
#
# Per E110: target model is Ling-2.6-flash (MoE-active-only) or
# Nemotron-3-Nano-Omni (BF16 native fit). Operator picks at deployment.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__SCRIPT_DIR}/../build/lib/common.sh"
# shellcheck source=../build/lib/observability.sh
. "${__SCRIPT_DIR}/../build/lib/observability.sh"
# shellcheck source=../build/lib/runtime-profile.sh
. "${__SCRIPT_DIR}/../build/lib/runtime-profile.sh"

STEP_ID="inference-oracle-core"
TIER="oracle_core"

# Sensible defaults; operator overrides via env
# Env vars (all overridable; sain-01 defaults shown):
#   ORACLE_MODEL              Path to weights (default: nemotron BF16 path)
#   ORACLE_HOST               Listen host (default: 127.0.0.1)
#   ORACLE_PORT               Listen port (default: 8083 — router routes here)
#   ORACLE_KV_CACHE_DTYPE     fp8 | auto (default: fp8 — deep-context-friendly)
#   ORACLE_DFLASH_DRAFT       Optional DFlash draft model id for speculative decode
#   SOVEREIGN_OS_DRY_RUN      Print argv + exit without exec
#   SOVEREIGN_OS_METRICS_DISABLE  Skip Layer B metrics
# R151: honor active runtime profile § 18 oracle-tier allocation
runtime_profile_override ORACLE_MODEL          oracle model
runtime_profile_override ORACLE_KV_CACHE_DTYPE oracle kv_cache_dtype

: "${ORACLE_MODEL:=/mnt/vault/models/nvidia__Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16}"
: "${ORACLE_HOST:=127.0.0.1}"
: "${ORACLE_PORT:=8083}"
: "${ORACLE_KV_CACHE_DTYPE:=fp8}"     # 'auto' on first run; fp8 for deep context (per L0 Profile 3)
: "${ORACLE_DFLASH_DRAFT:=}"          # e.g. z-lab/Nemotron-3-Nano-Omni-DFlash when published

# Export so the inline python3 (subshell) sees them via os.environ.
export ORACLE_MODEL ORACLE_HOST ORACLE_PORT ORACLE_KV_CACHE_DTYPE ORACLE_DFLASH_DRAFT

log_step_header "${STEP_ID}" "start Oracle Core (vLLM, Blackwell native)"
runtime_profile_log_active

emit_start_metric() {
  emit_metric sovereign_os_inference_backend_start_total 1 \
    "tier=\"${TIER}\",result=\"$1\""
}

# Idempotency: already listening?
if command -v ss >/dev/null 2>&1 && ss -lnt "sport = :${ORACLE_PORT}" 2>/dev/null | grep -q LISTEN; then
  log_info "port ${ORACLE_PORT} already listening — oracle core appears up; no-op exit"
  emit_start_metric skip
  exit 0
fi

require_command python3
# vLLM is python-side; assume operator installed via pip per profile.packages

argv=$(python3 - <<PY
import os, sys
sys.path.insert(0, "${__SCRIPT_DIR}")
from backends.vllm import VllmBackend
b = VllmBackend.for_oracle_core(
    os.environ["ORACLE_MODEL"],
    dflash_draft_model=os.environ.get("ORACLE_DFLASH_DRAFT") or None,
    kv_cache_dtype=os.environ.get("ORACLE_KV_CACHE_DTYPE", "fp8"),
)
b.config.host = os.environ["ORACLE_HOST"]
b.config.port = int(os.environ["ORACLE_PORT"])
print(" ".join(b.start_command()))
PY
)

log_info "argv: ${argv}"
log_info "model: ${ORACLE_MODEL}"
log_info "DFlash draft: ${ORACLE_DFLASH_DRAFT:-<none>}"
log_info "kv cache dtype: ${ORACLE_KV_CACHE_DTYPE}"
log_info "listening: http://${ORACLE_HOST}:${ORACLE_PORT}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN — not starting"
  emit_start_metric skip
  exit 0
fi

emit_start_metric success
emit_metric sovereign_os_inference_backend_pid $$ "tier=\"${TIER}\""
exec ${argv}
