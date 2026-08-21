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
: "${SOVEREIGN_OS_PROFILE:=sain-01}"

# Resolve the INTENDED arming posture (mirrors tetragon-policy-load.sh's knob).
# The fence is deliberately DISARMED on non-appliance hosts (the operator
# desktop: host-wide Sigkill would brick it, and container scope is opt-in) —
# there the policy file is present but intentionally NOT loaded, so "not loaded"
# is HEALTHY, not drift. Resolving the intent lets us tell an intentional disarm
# apart from an accidental blind perimeter.
#
# Read the profile field directly (NOT via load_profile — its require_file exits
# the script if the profile is absent, which must never take down the verifier).
# Fail SAFE toward armed: if the intent can't be read, assume the fence SHOULD be
# loaded and alert when it isn't. Env override wins for tests/appliances.
if [ -z "${SOVEREIGN_OS_TETRAGON_ARMED:-}" ]; then
  _prof="${SOVEREIGN_OS_PROFILES_DIR:-${__REPO_ROOT}/profiles}/${SOVEREIGN_OS_PROFILE}.yaml"
  [ -f "${_prof}" ] && SOVEREIGN_OS_TETRAGON_ARMED="$(
    SOVEREIGN_OS_PROFILE_FILE="${_prof}" profile_field provisioning.tetragon.armed 2>/dev/null || true)"
fi
case "${SOVEREIGN_OS_TETRAGON_ARMED:-}" in
  0|false|no|off|disarmed) SOVEREIGN_OS_TETRAGON_ARMED=0 ;;
  *)                       SOVEREIGN_OS_TETRAGON_ARMED=1 ;;
esac

log_step_header "tetragon-policy-verify" "verify perimeter policy (armed=${SOVEREIGN_OS_TETRAGON_ARMED})"

# Layer B perimeter status, gauged: 1=healthy, 0=drift/down/missing.
# "Healthy" means the running state MATCHES the intended arming posture:
# armed → fence loaded, or disarmed → fence intentionally not loaded. An
# intentional disarm is therefore status=1 (no alert), while an armed-but-
# unloaded fence (accidental blind) stays status=0. Emitted on every code-path
# exit so a single missed verification is visible. Includes last_run timestamp
# so 'verifier overdue' is detectable.
emit_perimeter_status() {
  local healthy="$1"
  emit_metric_set perimeter \
    '# HELP sovereign_os_perimeter_status Tetragon perimeter health (1=matches armed intent, 0=drift/down/missing)' \
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
# listing; we just verify the daemon's journal records the policy load).
# Scan THIS BOOT's journal (-b), not the last 100 lines (-n 100): the
# policy-load message is logged once at tetragon startup, so on any
# long-running host it has long scrolled past the last 100 lines and the
# old check emitted perimeter_status=0 (false "drift/down") on a perfectly
# healthy system. `-b` finds the one-time load message regardless of how
# much tetragon has logged since; `grep -q` short-circuits on first match.
if journalctl -u tetragon -b 2>/dev/null | grep -q "sovereign-kernel-fence"; then
  # Fence IS loaded. Healthy only if that matches the intent — a fence loaded on
  # a host that declared armed=0 is real drift (the load hook should have removed
  # it), and a silent live Sigkill fence on a desktop is exactly what disarm
  # exists to prevent.
  if [ "${SOVEREIGN_OS_TETRAGON_ARMED}" = 1 ]; then
    log_info "policy 'sovereign-kernel-fence' loaded (journal evidence this boot) — armed, perimeter healthy"
    emit_perimeter_status 1
  else
    log_error "sovereign-kernel-fence is LOADED but posture is DISARMED (armed=0) — drift"
    echo "$(date -u --iso-8601=seconds) PERIMETER_DRIFT disarmed posture but fence loaded" >> "${SOVEREIGN_OS_AUDIT_LOG}" 2>/dev/null || true
    emit_perimeter_status 0
  fi
elif [ "${SOVEREIGN_OS_TETRAGON_ARMED}" = 0 ]; then
  # Not loaded AND disarm is the declared intent → this is the healthy observe
  # posture (e.g. the operator desktop), NOT a blind perimeter. No alert, no
  # drift line — but log it so an operator can see the fence is intentionally
  # off rather than silently absent.
  log_info "sovereign-kernel-fence DISARMED by policy (armed=0) — fence intentionally not loaded (observe posture); healthy"
  emit_perimeter_status 1
else
  # Armed intent but no load record this boot → accidental blind perimeter.
  # Record the drift in the forensic audit log like the sibling drift cases
  # above (they all write PERIMETER_*). Kept non-fatal (no exit 1) because this
  # remains a journal heuristic: if tetragon ever changes its load-message
  # wording the grep could miss a genuinely-loaded policy, and a hard-fail there
  # would false-alarm. The status=0 gauge + audit-log line are the signals; a
  # hard listing check (tetra tracingpolicy list) would be the upgrade if/when
  # that CLI is guaranteed present.
  log_warn "no journal evidence of policy load this boot (armed) — perimeter BLIND"
  echo "$(date -u --iso-8601=seconds) PERIMETER_DRIFT no policy-load record this boot" >> "${SOVEREIGN_OS_AUDIT_LOG}" 2>/dev/null || true
  emit_perimeter_status 0
fi

log_info "tetragon-policy-verify complete"
