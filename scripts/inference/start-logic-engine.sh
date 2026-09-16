#!/usr/bin/env bash
# scripts/inference/start-logic-engine.sh — start the Logic Engine
# tier on the RTX 5090 (32 GB Blackwell GB202, internal secondary,
# PCIEX16_2 x8). Per operator directive 2026-07-14 (D-022) the Logic
# tier runs on the internal 5090 — more bandwidth than the RTX 4090 on
# the PCIe 4.0 x4 OcuLink eGPU. The RTX 4090 (operator §17.1's original
# Logic card) is now the OcuLink eGPU / opt-in VFIO sandbox and the
# DSpark speculative-decode draft target. Backend pluggable:
#   - vllm (default; podman-launched)
#   - vllm_host (host-resident vLLM, no podman — mirrors the Oracle Core path)
#   - llama_cpp (fallback for hardware constraints / debugging)
#
# Per SDD-011 routing rule 4 + default, the router sends json_object /
# tools / general requests here.
#
# Env vars (all overridable; sain-01 defaults shown):
#   SOVEREIGN_OS_LOGIC_BACKEND  vllm | vllm_host | llama_cpp (default: vllm)
#   LOGIC_GPU_MEMORY_UTILIZATION  vllm_host only (default: 0.90)
#   LOGIC_MAX_MODEL_LEN           vllm_host only (default: 32768)
#   LOGIC_SERVED_MODEL_NAME       vllm_host only; else the served id is the weights path
#   LOGIC_TRUST_REMOTE_CODE       vllm_host only; set for models shipping custom code
#   LOGIC_REASONING_PARSER        vllm_host only; --reasoning-parser value
#                                 (nemotron_v3 / deepseek_r1 / qwen3 / …) for
#                                 models that emit chain-of-thought
#   LOGIC_ATTENTION_BACKEND       vllm_host only; --attention-backend value
#                                 (TRITON_ATTN / FLASH_ATTN / TORCH_SDPA / …).
#                                 The env var VLLM_ATTENTION_BACKEND no longer
#                                 exists in vLLM; this flag is the only way.
#   LOGIC_EXTRA_ARGS              Additional vLLM argv (shlex-split). Used for
#                                 served model id, reasoning/tool parsers, and
#                                 agentic tool-choice support.
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

# A selected profile owns its declared Logic settings.  In particular this
# prevents stale Nemotron-specific values from /etc's EnvironmentFile winning
# over a newly activated Qwen profile.
runtime_profile_override LOGIC_MODEL logic model
# Keep the catalog id for profile validation while allowing a quantized local
# artifact to be the actual llama.cpp input.  Without this, a GGUF catalog id
# resolves only to its containing directory and the launcher cannot select the
# intended quantization.
runtime_profile_override LOGIC_MODEL logic model_path
runtime_profile_override LOGIC_GPU_MEMORY_UTILIZATION logic gpu_memory_utilization
runtime_profile_override LOGIC_MAX_MODEL_LEN logic max_model_len
runtime_profile_override LOGIC_REASONING_PARSER logic reasoning_parser
runtime_profile_override LOGIC_EXTRA_ARGS logic extra_args

# Orchestration profiles use the catalog's portable engine names; the launcher
# uses backend identifiers.  Keep this translation here so selecting a
# llama.cpp profile actually changes the live logic service rather than leaving
# its old vLLM backend in place.
_logic_profile_engine="$(runtime_profile_get_tier_field logic engine)"
case "${_logic_profile_engine}" in
  vllm)
    SOVEREIGN_OS_LOGIC_BACKEND=vllm_host
    # A selected orchestration profile owns request formatting as well as its
    # model.  Do not let a previous resident's reasoning parser or tool parser
    # leak through /etc's long-lived EnvironmentFile (for example Nemotron's
    # parser being passed to Qwen).  An explicit profile value was already
    # applied above; an absent one means intentionally no parser/extra flags.
    [ -n "$(runtime_profile_get_tier_field logic reasoning_parser)" ] || LOGIC_REASONING_PARSER=""
    [ -n "$(runtime_profile_get_tier_field logic extra_args)" ] || LOGIC_EXTRA_ARGS=""
    ;;
  llama.cpp)
    SOVEREIGN_OS_LOGIC_BACKEND=llama_cpp
    # Do not inherit vLLM-only arguments from the service EnvironmentFile.
    # An omitted llama.cpp `extra_args` is deliberately empty, not stale.
    LOGIC_EXTRA_ARGS="$(runtime_profile_get_tier_field logic extra_args)"
    ;;
esac

# Profile allocations name catalog ids while vLLM needs a local checkpoint
# directory.  Prefer an installed local artifact; preserve an explicit path or
# HF repo id when no matching local directory exists.
if [[ "${LOGIC_MODEL}" != /* ]]; then
  _logic_models_dir="${SOVEREIGN_OS_MODELS_DIR:-/mnt/vault/models}"
  if [ -d "${_logic_models_dir}/${LOGIC_MODEL}" ]; then
    LOGIC_MODEL="${_logic_models_dir}/${LOGIC_MODEL}"
  fi
fi

: "${SOVEREIGN_OS_LOGIC_BACKEND:=vllm}"
: "${LOGIC_GPU_MEMORY_UTILIZATION:=0.90}"
: "${LOGIC_MAX_MODEL_LEN:=32768}"
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
  vllm_host)
    # Host-resident vLLM: same engine as `vllm` but launched directly instead of
    # through podman, mirroring how the Oracle Core runs. For boxes without podman,
    # or where the container image is not built. Measured 2026-07-28 on the RTX 5090
    # with Nemotron-3-Nano-Omni-30B NVFP4: 314.41 tok/s decode, TTFT 0.173s.
    # CUDA_VISIBLE_DEVICES pins the tier to its card; set it in the env file.
    require_command python3
    argv=(python3 -m vllm.entrypoints.openai.api_server)
    argv+=(--model "${LOGIC_MODEL}")
    argv+=(--host "${LOGIC_HOST}" --port "${LOGIC_PORT}")
    argv+=(--gpu-memory-utilization "${LOGIC_GPU_MEMORY_UTILIZATION}")
    argv+=(--max-model-len "${LOGIC_MAX_MODEL_LEN}")
    [ -n "${LOGIC_SERVED_MODEL_NAME:-}" ] && argv+=(--served-model-name "${LOGIC_SERVED_MODEL_NAME}")
    [ -n "${LOGIC_TRUST_REMOTE_CODE:-}" ] && argv+=(--trust-remote-code)
    # Attention backend selection. There is NO env var for this — vLLM removed
    # VLLM_ATTENTION_BACKEND, and setting it is silently inert (0.26 does not
    # reference the name anywhere). The only mechanism is this CLI flag, so a
    # deployment that must avoid FlashInfer — e.g. a host with no nvcc, where
    # flashinfer's JIT-only build cannot compile — has no way to say so without
    # it. Accepts any AttentionBackendEnum name (TRITON_ATTN, FLASH_ATTN,
    # TORCH_SDPA, FLASHINFER, …).
    [ -n "${LOGIC_ATTENTION_BACKEND:-}" ] && argv+=(--attention-backend "${LOGIC_ATTENTION_BACKEND}")
    # Reasoning models emit chain-of-thought and then the answer. Without a
    # parser the whole trace is returned as message content, so a caller sees the
    # model thinking out loud plus a stray closing marker. vLLM splits it into
    # reasoning_content when told which format to expect.
    [ -n "${LOGIC_REASONING_PARSER:-}" ] && argv+=(--reasoning-parser "${LOGIC_REASONING_PARSER}")
    # The backend adapter does not model every vLLM option. In particular,
    # OpenClaw sends tools with tool_choice=auto, which vLLM rejects unless
    # these explicitly managed extra arguments enable a compatible parser.
    if [ -n "${LOGIC_EXTRA_ARGS:-}" ]; then
      read -r -a logic_extra_argv <<< "${LOGIC_EXTRA_ARGS}"
      argv+=("${logic_extra_argv[@]}")
    fi
    ;;
  llama_cpp)
    # The system llama-server may be a CPU-only package.  Prefer the isolated
    # CUDA build when present; it is intentionally outside /usr/local so a
    # profile cannot alter system-managed binaries.
    _llama_cuda_dir="${SOVEREIGN_OS_LLAMA_CUDA_DIR:-/home/jfortin/sovereign-os/.runtime/llama-cuda}"
    if [ -x "${_llama_cuda_dir}/llama-server" ]; then
      export LLAMA_BIN="${_llama_cuda_dir}/llama-server"
      export LD_LIBRARY_PATH="${_llama_cuda_dir}:/opt/sovereign-os/venv/vllm/lib/python3.14/site-packages/nvidia/cu13/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
    fi
    argv_text=$(python3 - <<PY
import os, sys
sys.path.insert(0, "${__SCRIPT_DIR}")
from backends.llama_cpp import LlamaCppBackend
b = LlamaCppBackend.for_sain01_fallback(os.environ["LOGIC_MODEL"])
b.config.host = os.environ["LOGIC_HOST"]
b.config.port = int(os.environ["LOGIC_PORT"])
b.ctx_size = int(os.environ.get("LOGIC_MAX_MODEL_LEN", b.ctx_size))
print(" ".join(b.start_command()))
PY
)
    read -r -a argv <<< "${argv_text}"
    # Profile-managed llama.cpp options (for example --model-draft for
    # speculative decoding) must reach the server just as vLLM options do.
    # Without this, selecting a llama.cpp profile silently starts only its
    # base model with the backend defaults.
    if [ -n "${LOGIC_EXTRA_ARGS:-}" ]; then
      read -r -a logic_extra_argv <<< "${LOGIC_EXTRA_ARGS}"
      argv+=("${logic_extra_argv[@]}")
    fi
    ;;
  *)
    log_error "unknown SOVEREIGN_OS_LOGIC_BACKEND: ${SOVEREIGN_OS_LOGIC_BACKEND}"
    emit_start_metric fail
    exit 1
    ;;
esac

printf -v argv_log '%q ' "${argv[@]}"
log_info "argv: ${argv_log}"
log_info "model: ${LOGIC_MODEL}"
log_info "listening: http://${LOGIC_HOST}:${LOGIC_PORT}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN — not starting"
  emit_start_metric skip
  exit 0
fi

emit_start_metric success
emit_metric sovereign_os_inference_backend_pid $$ "tier=\"${TIER}\""
exec "${argv[@]}"
