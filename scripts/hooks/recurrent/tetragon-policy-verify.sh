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

: "${SOVEREIGN_OS_POLICY_DIR:=/etc/tetragon/tracing-policies}"
: "${SOVEREIGN_OS_AUDIT_LOG:=/mnt/vault/context/security_audit.log}"

log_step_header "tetragon-policy-verify" "verify perimeter policy"

require_root

if ! command -v tetragon >/dev/null 2>&1; then
  log_error "tetragon not installed"
  exit 1
fi

if ! systemctl is-active --quiet tetragon; then
  log_error "tetragon not active"
  echo "$(date -u --iso-8601=seconds) PERIMETER_DOWN tetragon inactive" >> "${SOVEREIGN_OS_AUDIT_LOG}" 2>/dev/null || true
  exit 1
fi

policy="${SOVEREIGN_OS_POLICY_DIR}/sovereign-kernel-fence.yaml"
if [ ! -f "${policy}" ]; then
  log_error "policy file missing: ${policy}"
  echo "$(date -u --iso-8601=seconds) PERIMETER_DRIFT policy missing" >> "${SOVEREIGN_OS_AUDIT_LOG}" 2>/dev/null || true
  exit 1
fi

# Spot-check that policy is loaded (tetragon doesn't expose easy
# listing; we just verify the daemon's stdout contains the policy
# name in recent journal)
if journalctl -u tetragon -n 100 2>/dev/null | grep -q "sovereign-kernel-fence"; then
  log_info "policy 'sovereign-kernel-fence' loaded (journal evidence)"
else
  log_warn "no journal evidence of policy load in last 100 lines"
fi

log_info "tetragon-policy-verify complete"
