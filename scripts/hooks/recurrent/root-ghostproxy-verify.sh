#!/usr/bin/env bash
# scripts/hooks/recurrent/root-ghostproxy-verify.sh
#
# Weekly read-only drift verify of the root-ghostproxy endpoint
# AI-agent safety envelope (SDD-046).
#
# Runs the upstream installer's --check (read-only op_verify) in the
# pinned posture: --profile base --mode endpoint (proxy half OFF per
# operator directive 2026-07-03). The contract is OBSERVATION, not
# REMEDIATION (same as `sovereign-osctl audit drift`, D-018): this hook
# never re-applies or overwrites — remediation is the install hook
# (scripts/hooks/post-install/root-ghostproxy-endpoint-install.sh)
# under its explicit confirm gate.
#
#   - Absent checkout is a REPORT, not a hook failure (exit 0;
#     result="absent" in metrics).
#   - Drift is a REPORT (exit 0; result="drift" — the alert layer
#     consumes the metric; the hook run itself succeeded).
#
# Emits Layer B metrics:
#   sovereign_os_ghostproxy_endpoint_verify_result{result=current|drift|absent}
#   sovereign_os_ghostproxy_endpoint_verify_last_run_timestamp

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

: "${SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR:=${HOME}/root-ghostproxy}"
: "${SOVEREIGN_OS_GHOSTPROXY_PROFILE:=base}"
# Pinned per SDD-046 A2 — see the install hook's header for why.
GHOSTPROXY_MODE="endpoint"

log_step_header "root-ghostproxy-verify" \
  "read-only drift check of AI-agent safety envelope (mode=${GHOSTPROXY_MODE})"

emit_summary() {
  local result="$1"
  emit_metric_set ghostproxy-endpoint-verify \
    '# HELP sovereign_os_ghostproxy_endpoint_verify_result Last verify outcome (1 = this result)' \
    '# TYPE sovereign_os_ghostproxy_endpoint_verify_result gauge' \
    "sovereign_os_ghostproxy_endpoint_verify_result{result=\"${result}\"} 1" \
    '# HELP sovereign_os_ghostproxy_endpoint_verify_last_run_timestamp Unix timestamp of last run' \
    '# TYPE sovereign_os_ghostproxy_endpoint_verify_last_run_timestamp gauge' \
    "sovereign_os_ghostproxy_endpoint_verify_last_run_timestamp $(date +%s)"
}

INSTALLER="${SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR}/install.sh"

if [ ! -x "${INSTALLER}" ]; then
  log_warn "no root-ghostproxy checkout at ${SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR} (set SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR)"
  emit_summary absent
  exit 0   # absent is a report, not a hook failure
fi

cd "${SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR}"
require_command bash

if bash "${INSTALLER}" --check --profile "${SOVEREIGN_OS_GHOSTPROXY_PROFILE}" --mode "${GHOSTPROXY_MODE}"; then
  log_info "  endpoint envelope matches spec (no drift)."
  emit_summary current
else
  log_warn "  upstream --check reported drift. Remediation: re-run the install hook with SOVEREIGN_OS_CONFIRM_GHOSTPROXY_INSTALL=YES."
  emit_summary drift
fi
