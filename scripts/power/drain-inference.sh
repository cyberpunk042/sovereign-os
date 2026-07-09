#!/usr/bin/env bash
# scripts/power/drain-inference.sh — SDD-026 Z-18: quiesce the inference router so
# IN-FLIGHT LLM requests FINISH before backends are stopped during a graceful
# shutdown ("LLM chat message finishing" — operator, 2026-07-08). It signals the
# router's drain flag (→ the router 503s NEW completions) then polls
# /drain-status until in-flight reaches 0 or the deadline. No-op if the router
# isn't running (nothing to drain). Idempotent; safe to re-run.
#
# Usage: drain-inference.sh [max_wait_seconds]
#   default 60, or SOVEREIGN_OS_DRAIN_MAX_SECONDS. Honors SOVEREIGN_OS_DRY_RUN.
set -uo pipefail
__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh" 2>/dev/null || {
  log_info() { echo "INFO  [drain-inference] $*"; }
  log_warn() { echo "WARN  [drain-inference] $*" >&2; }
}
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh" 2>/dev/null || emit_metric() { :; }

MAX="${1:-${SOVEREIGN_OS_DRAIN_MAX_SECONDS:-60}}"
FLAG="${SOVEREIGN_OS_ROUTER_DRAIN_FLAG:-/run/sovereign-os/router-drain}"
ROUTER="${SOVEREIGN_OS_ROUTER_URL:-http://127.0.0.1:8080}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would touch ${FLAG} + poll ${ROUTER}/drain-status up to ${MAX}s"
  emit_metric sovereign_os_power_drain_inference_total 1 'result="dry-run"'
  exit 0
fi

mkdir -p "$(dirname "${FLAG}")" 2>/dev/null || true
: > "${FLAG}" 2>/dev/null || touch "${FLAG}" 2>/dev/null || true
log_info "router drain signalled (${FLAG}); waiting up to ${MAX}s for in-flight to finish"

_inflight() {  # echo the router's in-flight count, or empty when unreachable
  python3 - "${ROUTER}" <<'PY' 2>/dev/null
import json, sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1].rstrip("/") + "/drain-status", timeout=3) as r:
        print(json.load(r).get("inflight", 0))
except Exception:
    pass
PY
}

waited=0
final="unknown"
while [ "${waited}" -lt "${MAX}" ]; do
  n="$(_inflight)"
  if [ -z "${n}" ]; then log_info "router not reachable — nothing to drain"; final="no-router"; break; fi
  if [ "${n}" -eq 0 ] 2>/dev/null; then log_info "in-flight drained to 0 after ${waited}s"; final="drained"; break; fi
  log_info "  ${n} request(s) still in flight (${waited}/${MAX}s)"
  sleep 3; waited=$((waited + 3))
done
if [ "${waited}" -ge "${MAX}" ]; then
  log_warn "drain deadline ${MAX}s reached — proceeding (remaining in-flight may be cut)"
  final="timeout"
fi
emit_metric sovereign_os_power_drain_inference_total 1 "result=\"${final}\""
exit 0
