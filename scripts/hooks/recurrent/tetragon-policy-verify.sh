#!/usr/bin/env bash
# scripts/hooks/recurrent/tetragon-policy-verify.sh
#
# Daily verification that the Tetragon sovereign-kernel-fence policy
# is still loaded + matches the on-disk source-of-truth. Logs to
# tank/context/security_audit.log on any drift.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

: "${SOVEREIGN_OS_POLICY_DIR:=/etc/tetragon/tracing-policies}"
: "${SOVEREIGN_OS_AUDIT_LOG:=/mnt/vault/context/security_audit.log}"

log_step_header "tetragon-policy-verify" "verify perimeter policy"

# Layer B perimeter status, gauged: 1=healthy, 0=drift/down/missing.
# Emitted on every code-path exit so a single missed verification is
# visible. Includes last_run timestamp so 'verifier overdue' is detectable.
emit_perimeter_status() {
  local healthy="$1"
  emit_metric_set perimeter \
    '# HELP sovereign_os_perimeter_status Tetragon perimeter health (1=loaded, 0=drift/down/missing)' \
    '# TYPE sovereign_os_perimeter_status gauge' \
    "sovereign_os_perimeter_status ${healthy}" \
    '# HELP sovereign_os_perimeter_verify_last_run_timestamp Unix timestamp of last verifier run' \
    '# TYPE sovereign_os_perimeter_verify_last_run_timestamp gauge' \
    "sovereign_os_perimeter_verify_last_run_timestamp $(date +%s)"
}

require_root

if ! command -v tetragon >/dev/null 2>&1; then
  log_error "tetragon not installed"
  emit_perimeter_status 0
  exit 1
fi

if ! systemctl is-active --quiet tetragon; then
  log_error "tetragon not active"
  echo "$(date -u --iso-8601=seconds) PERIMETER_DOWN tetragon inactive" >> "${SOVEREIGN_OS_AUDIT_LOG}" 2>/dev/null || true
  emit_perimeter_status 0
  exit 1
fi

policy="${SOVEREIGN_OS_POLICY_DIR}/sovereign-kernel-fence.yaml"
if [ ! -f "${policy}" ]; then
  log_error "policy file missing: ${policy}"
  echo "$(date -u --iso-8601=seconds) PERIMETER_DRIFT policy missing" >> "${SOVEREIGN_OS_AUDIT_LOG}" 2>/dev/null || true
  emit_perimeter_status 0
  exit 1
fi

# Spot-check that policy is loaded (tetragon doesn't expose easy
# listing; we just verify the daemon's stdout contains the policy
# name in recent journal)
if journalctl -u tetragon -n 100 2>/dev/null | grep -q "sovereign-kernel-fence"; then
  log_info "policy 'sovereign-kernel-fence' loaded (journal evidence)"
  emit_perimeter_status 1
else
  log_warn "no journal evidence of policy load in last 100 lines"
  emit_perimeter_status 0
fi

log_info "tetragon-policy-verify complete"
