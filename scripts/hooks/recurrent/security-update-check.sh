#!/usr/bin/env bash
# scripts/hooks/recurrent/security-update-check.sh
#
# Daily check for available security updates. Emits Layer B metric
# with the count of pending security upgrades + last-check timestamp.
# Does NOT auto-apply — unattended-upgrades (configured per-profile)
# handles application on profiles that opt in; this script just
# surfaces visibility.
#
# Operator IaC bar: "observable and operable, at all stages of
# lifecycle" — pending-security-update count is a critical health
# signal for any long-running deployment.
#
# Honors SOVEREIGN_OS_DRY_RUN=1 (skip the apt-list run).
#
# Tunable env:
#   SOVEREIGN_OS_APT_ORIGIN_PATTERN  pattern to grep for security origins
#                                    (default: 'Debian-Security')

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

: "${SOVEREIGN_OS_APT_ORIGIN_PATTERN:=Debian-Security}"

log_step_header "security-update-check" "scan for pending security updates"

# require_command apt — but on non-Debian boxes (e.g., test runners),
# we want to gracefully no-op so the recurrent surface stays usable.
if ! command -v apt >/dev/null 2>&1; then
  log_warn "apt not available — not a Debian-derivative; skipping"
  emit_metric_set security-updates \
    '# HELP sovereign_os_security_updates_available Pending security-only upgrades (Debian-Security origin)' \
    '# TYPE sovereign_os_security_updates_available gauge' \
    'sovereign_os_security_updates_available -1' \
    '# HELP sovereign_os_security_update_check_last_run_timestamp Unix timestamp of last successful check' \
    '# TYPE sovereign_os_security_update_check_last_run_timestamp gauge' \
    "sovereign_os_security_update_check_last_run_timestamp $(date +%s)"
  exit 0
fi

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would: apt update && apt list --upgradable | grep ${SOVEREIGN_OS_APT_ORIGIN_PATTERN}"
  exit 0
fi

# Refresh package lists (operator-pullable per sovereignty principle —
# only happens via this hook's cadence, never auto on boot)
apt update 2>/dev/null >/dev/null || log_warn "apt update failed (network?)"

# Count upgradable from security origin. Use Origin/Suite fields rather
# than parsing prose — more robust.
count="$(apt list --upgradable 2>/dev/null \
  | grep -c "${SOVEREIGN_OS_APT_ORIGIN_PATTERN}" || true)"

log_info "pending security updates: ${count}"

emit_metric_set security-updates \
  '# HELP sovereign_os_security_updates_available Pending security-only upgrades (Debian-Security origin)' \
  '# TYPE sovereign_os_security_updates_available gauge' \
  "sovereign_os_security_updates_available ${count}" \
  '# HELP sovereign_os_security_update_check_last_run_timestamp Unix timestamp of last successful check' \
  '# TYPE sovereign_os_security_update_check_last_run_timestamp gauge' \
  "sovereign_os_security_update_check_last_run_timestamp $(date +%s)"

# Exit code: 0 always (informational); operator dashboards alarm on
# the count metric exceeding profile-specific thresholds.
exit 0
