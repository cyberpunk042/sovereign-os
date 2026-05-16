#!/usr/bin/env bash
# scripts/inference/start-pulse.sh — start the Pulse module
# (bitnet.cpp pinned to CCD 0 cores 0-5 per the SRP Trinity).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__SCRIPT_DIR}/../build/lib/common.sh"

STEP_ID="inference-pulse"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
: "${PULSE_MODEL:=/mnt/vault/models/microsoft__bitnet-b1.58-2B-4T}"
: "${PULSE_HOST:=127.0.0.1}"
: "${PULSE_PORT:=8081}"
: "${PULSE_AFFINITY:=0-5}"
: "${BITNET_BIN:=bitnet-cli}"

log_step_header "${STEP_ID}" "start Pulse (bitnet.cpp, CCD 0)"

require_command "${BITNET_BIN}" "install bitnet.cpp from github.com/microsoft/BitNet"

# Resolve via the Python adapter for argv consistency
argv=$(python3 - <<PY
import sys, os
sys.path.insert(0, "${__SCRIPT_DIR}")
from backends.bitnet import BitnetBackend
from lib.backend import BackendConfig

cfg = BackendConfig(
    model_path=os.environ["PULSE_MODEL"],
    host=os.environ["PULSE_HOST"],
    port=int(os.environ["PULSE_PORT"]),
    cpu_affinity=os.environ["PULSE_AFFINITY"],
    env={"BITNET_BIN": os.environ.get("BITNET_BIN", "bitnet-cli")},
)
b = BitnetBackend(cfg)
print(" ".join(b.start_command()))
PY
)

log_info "argv: ${argv}"
log_info "model: ${PULSE_MODEL}"
log_info "listening: http://${PULSE_HOST}:${PULSE_PORT}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN — not starting"
  exit 0
fi

exec ${argv}
