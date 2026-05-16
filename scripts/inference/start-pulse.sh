#!/usr/bin/env bash
# scripts/inference/start-pulse.sh — start the Pulse module.
#
# Pulse = bitnet.cpp ternary inference on CCD 0 (cores 0-5 by default).
# The SRP Trinity's fast-path. Per SDD-011 routing rule 1, the
# inference router sends ternary/bitnet model requests here.
#
# Env vars (all overridable; documented values are sain-01 defaults):
#   PULSE_MODEL          Path to model weights
#                        (default: /mnt/vault/models/microsoft__bitnet-b1.58-2B-4T)
#   PULSE_HOST           Listen host (default: 127.0.0.1)
#   PULSE_PORT           Listen port (default: 8081 — sovereign-router routes here)
#   PULSE_AFFINITY       taskset --cpu-list mask (default: 0-5 — CCD 0 cores)
#   PULSE_THREADS        bitnet.cpp -t threads (default: 6 — matches affinity)
#   PULSE_CTX            bitnet.cpp -c context size (default: 4096)
#   BITNET_BIN           bitnet.cpp binary (default: bitnet-cli)
#   SOVEREIGN_OS_DRY_RUN When set, print argv + exit 0 without exec
#   SOVEREIGN_OS_METRICS_DISABLE  Skip Layer B metric emission
#
# Idempotency: if PULSE_PORT is already bound, exits 0 with a log line
# ("already listening — no-op"). Operator restart via 'sovereign-osctl
# inference restart pulse'.
#
# Layer B metrics emitted (SDD-016):
#   sovereign_os_inference_backend_start_total{tier="pulse",result="success|skip|fail"}
#   sovereign_os_inference_backend_pid{tier="pulse"} (when started)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__SCRIPT_DIR}/../build/lib/common.sh"
# shellcheck source=../build/lib/observability.sh
. "${__SCRIPT_DIR}/../build/lib/observability.sh"

STEP_ID="inference-pulse"
TIER="pulse"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
: "${PULSE_MODEL:=/mnt/vault/models/microsoft__bitnet-b1.58-2B-4T}"
: "${PULSE_HOST:=127.0.0.1}"
: "${PULSE_PORT:=8081}"
: "${PULSE_AFFINITY:=0-5}"
: "${PULSE_THREADS:=6}"
: "${PULSE_CTX:=4096}"
: "${BITNET_BIN:=bitnet-cli}"

# Export so the inline python3 (subshell) sees them via os.environ.
export PULSE_MODEL PULSE_HOST PULSE_PORT PULSE_AFFINITY PULSE_THREADS PULSE_CTX BITNET_BIN

log_step_header "${STEP_ID}" "start Pulse (bitnet.cpp, CCD 0 cores ${PULSE_AFFINITY})"

emit_start_metric() {
  emit_metric sovereign_os_inference_backend_start_total 1 \
    "tier=\"${TIER}\",result=\"$1\""
}

# ---- idempotency: port already bound? ----
if command -v ss >/dev/null 2>&1 && ss -lnt "sport = :${PULSE_PORT}" 2>/dev/null | grep -q LISTEN; then
  log_info "port ${PULSE_PORT} already listening — pulse appears up; no-op exit"
  emit_start_metric skip
  exit 0
fi

require_command "${BITNET_BIN}" "install bitnet.cpp from github.com/microsoft/BitNet"

# Resolve argv via the Python adapter for consistency with router defaults
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
log_info "affinity: ${PULSE_AFFINITY} (CCD 0)"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN — not starting"
  emit_start_metric skip
  exit 0
fi

# Enforce CPU affinity via taskset (defense-in-depth — bitnet.cpp's
# own pinning may not survive systemd-managed restarts cleanly).
if command -v taskset >/dev/null 2>&1; then
  emit_start_metric success
  emit_metric sovereign_os_inference_backend_pid $$ "tier=\"${TIER}\""
  exec taskset --cpu-list "${PULSE_AFFINITY}" ${argv}
else
  log_warn "taskset not available; running without affinity pinning"
  emit_start_metric success
  emit_metric sovereign_os_inference_backend_pid $$ "tier=\"${TIER}\""
  exec ${argv}
fi
