#!/usr/bin/env bash
# scripts/inference/start-oracle-core.sh — Oracle Core on RTX PRO 6000
# Blackwell (vLLM native, host-resident; DFlash drafts when configured).
#
# Per E110: target model is Ling-2.6-flash (MoE-active-only) or
# Nemotron-3-Nano-Omni (BF16 native fit). Operator picks at deployment.
#
# R455 (E11.M4 Nemotron 3 finish): Blackwell-aware quantization
# default. When NVFP4-capable GPU detected (RTX PRO 6000 / B100 / B200),
# default ORACLE_QUANTIZATION=nvfp4 selecting the NVFP4 catalog variant
# (22.4 GiB checkpoint) for native Blackwell tensor-core path. Falls
# back to bf16 on Ada/Hopper. Operator-overridable.
# Per operator §1g verbatim: "all the best selection of models adapted
# for various size and at various quantization or for various specific
# purpose".

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

# R455: Blackwell-detection helper. Returns 0 (true) when NVFP4-capable
# GPU detected via nvidia-smi compute-capability ≥ 10.0 (Blackwell SM_100).
# Never raises; absence of nvidia-smi → not-Blackwell.
oracle_is_blackwell() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    return 1
  fi
  local cap
  cap="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null \
         | head -n1 | tr -d ' ')"
  if [ -z "${cap}" ]; then
    return 1
  fi
  # Compute capability "10.0" or higher = Blackwell (SM_100, SM_120, etc.)
  local major="${cap%%.*}"
  if [ "${major}" -ge 10 ] 2>/dev/null; then
    return 0
  fi
  return 1
}

# R455: VRAM probe. Returns max VRAM in GiB across detected GPUs.
# Echoes "0" when nvidia-smi unavailable.
oracle_max_vram_gib() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo 0
    return 0
  fi
  nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null \
    | sort -n | tail -n1 | awk '{printf "%d\n", $1/1024}'
}

# Sensible defaults; operator overrides via env
# Env vars (all overridable; sain-01 defaults shown):
#   ORACLE_MODEL              Path to weights (default: Blackwell-aware:
#                             nvfp4 path on Blackwell, BF16 elsewhere)
#   ORACLE_QUANTIZATION       nvfp4 | fp8 | bf16 (R455 default: nvfp4 on
#                             Blackwell, bf16 elsewhere)
#   ORACLE_HOST               Listen host (default: 127.0.0.1)
#   ORACLE_PORT               Listen port (default: 8083 — router routes here)
#   ORACLE_KV_CACHE_DTYPE     fp8 | auto (default: fp8 — deep-context-friendly)
#   ORACLE_DFLASH_DRAFT       Optional DFlash draft model id for speculative decode
#   ORACLE_VRAM_REQUIRED_GIB  Min VRAM required (R455 default: 22 for nvfp4, 64 for bf16)
#   SOVEREIGN_OS_DRY_RUN      Print argv + exit without exec
#   SOVEREIGN_OS_METRICS_DISABLE  Skip Layer B metrics
# R151: honor active runtime profile § 18 oracle-tier allocation
runtime_profile_override ORACLE_MODEL          oracle model
runtime_profile_override ORACLE_KV_CACHE_DTYPE oracle kv_cache_dtype
runtime_profile_override ORACLE_QUANTIZATION   oracle quantization

# R455: Blackwell-aware default quantization. Operator-overridable.
if [ -z "${ORACLE_QUANTIZATION:-}" ]; then
  if oracle_is_blackwell; then
    ORACLE_QUANTIZATION="nvfp4"
    log_info "R455: Blackwell GPU detected — defaulting ORACLE_QUANTIZATION=nvfp4 (native Blackwell tensor-core path)"
  else
    ORACLE_QUANTIZATION="bf16"
    log_info "R455: no Blackwell detected — defaulting ORACLE_QUANTIZATION=bf16 (Ada/Hopper-compatible path)"
  fi
fi

# R455: Default model path follows the selected quantization.
if [ -z "${ORACLE_MODEL:-}" ]; then
  case "${ORACLE_QUANTIZATION}" in
    nvfp4)
      ORACLE_MODEL="/mnt/vault/models/nvidia__Nemotron-3-Nano-Omni-30B-A3B-Reasoning-NVFP4"
      : "${ORACLE_VRAM_REQUIRED_GIB:=22}"   # 22.4 GiB checkpoint
      ;;
    fp8)
      ORACLE_MODEL="/mnt/vault/models/nvidia__Nemotron-3-Nano-Omni-30B-A3B-Reasoning-FP8"
      : "${ORACLE_VRAM_REQUIRED_GIB:=32}"
      ;;
    bf16|*)
      ORACLE_MODEL="/mnt/vault/models/nvidia__Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16"
      : "${ORACLE_VRAM_REQUIRED_GIB:=64}"
      ;;
  esac
fi

: "${ORACLE_HOST:=127.0.0.1}"
: "${ORACLE_PORT:=8083}"
: "${ORACLE_KV_CACHE_DTYPE:=fp8}"     # 'auto' on first run; fp8 for deep context (per L0 Profile 3)
: "${ORACLE_DFLASH_DRAFT:=}"          # e.g. z-lab/Nemotron-3-Nano-Omni-DFlash when published
: "${ORACLE_VRAM_REQUIRED_GIB:=22}"

# R455: VRAM verification — warn (don't refuse) when detected VRAM is
# below the chosen-variant minimum. Operator-discoverable.
__oracle_max_vram="$(oracle_max_vram_gib)"
if [ "${__oracle_max_vram}" -gt 0 ] 2>/dev/null \
   && [ "${__oracle_max_vram}" -lt "${ORACLE_VRAM_REQUIRED_GIB}" ]; then
  log_warn "R455: detected max GPU VRAM=${__oracle_max_vram}GiB < required=${ORACLE_VRAM_REQUIRED_GIB}GiB for quantization=${ORACLE_QUANTIZATION}; OOM risk. Consider ORACLE_QUANTIZATION=nvfp4 (22 GiB) or ORACLE_QUANTIZATION=fp8 (32 GiB)."
fi

# Export so the inline python3 (subshell) sees them via os.environ.
export ORACLE_MODEL ORACLE_HOST ORACLE_PORT ORACLE_KV_CACHE_DTYPE ORACLE_DFLASH_DRAFT \
       ORACLE_QUANTIZATION ORACLE_VRAM_REQUIRED_GIB

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
log_info "quantization: ${ORACLE_QUANTIZATION}  (R455 Blackwell-aware default)"
log_info "vram required: ${ORACLE_VRAM_REQUIRED_GIB} GiB (detected max: ${__oracle_max_vram} GiB)"
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
