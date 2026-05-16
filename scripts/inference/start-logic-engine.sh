#!/usr/bin/env bash
# scripts/inference/start-logic-engine.sh — Logic Engine on RTX 3090
# (VFIO-bound; vLLM via podman by default; llama.cpp fallback when
# SOVEREIGN_OS_LOGIC_BACKEND=llama_cpp).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__SCRIPT_DIR}/../build/lib/common.sh"

STEP_ID="inference-logic-engine"

: "${SOVEREIGN_OS_LOGIC_BACKEND:=vllm}"
: "${LOGIC_MODEL:=/mnt/vault/models/qwen3-coder}"
: "${LOGIC_HOST:=127.0.0.1}"
: "${LOGIC_PORT:=8082}"

log_step_header "${STEP_ID}" "start Logic Engine (backend=${SOVEREIGN_OS_LOGIC_BACKEND}, RTX 3090 VFIO)"

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
    exit 1
    ;;
esac

log_info "argv: ${argv}"
log_info "listening: http://${LOGIC_HOST}:${LOGIC_PORT}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN — not starting"
  exit 0
fi

exec ${argv}
