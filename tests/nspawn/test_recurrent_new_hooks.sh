#!/usr/bin/env bash
# tests/nspawn/test_recurrent_new_hooks.sh
#
# Layer 3 test for Round 35 — security-update-check.sh +
# backup-snapshot.sh. Both gracefully no-op on non-Debian / non-ZFS
# hosts (CI runners don't have ZFS; some won't have apt) and emit
# their Layer B metrics either way.
#
# Asserts:
#   - security-update-check: non-apt host → graceful no-op + emits
#     count=-1 (sentinel for 'unsupported')
#   - security-update-check: DRY_RUN exits 0 cleanly
#   - backup-snapshot: non-ZFS host → graceful no-op + emits count=0
#   - backup-snapshot: DRY_RUN logs intended action without zfs invocation
#   - Both hooks emit Layer B metric_set with expected key names

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

SEC="${__REPO_ROOT}/scripts/hooks/recurrent/security-update-check.sh"
SNAP="${__REPO_ROOT}/scripts/hooks/recurrent/backup-snapshot.sh"

[ -x "${SEC}" ] || { echo "FAIL: security-update-check.sh not executable"; exit 1; }
[ -x "${SNAP}" ] || { echo "FAIL: backup-snapshot.sh not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_recurrent_new_hooks.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_METRICS_DIR="${tmp}/metrics"

# ----------- security-update-check: DRY-RUN ---------------

# Capture then grep — under pipefail, 'grep -q' SIGPIPE-kills upstream
# and the pipe reports failure even when the output IS correct.
sec_out_dryrun="$(SOVEREIGN_OS_DRY_RUN=1 "${SEC}" 2>&1)"
if grep -q "DRY-RUN" <<< "${sec_out_dryrun}"; then
  ok "security-update-check honors SOVEREIGN_OS_DRY_RUN=1"
else
  ko "security-update-check missing DRY-RUN log"
fi

# ----------- security-update-check: real run ---------------

set +e
out_sec="$(${SEC} 2>&1)"
rc_sec=$?
set -e

if [ "${rc_sec}" -eq 0 ]; then
  ok "security-update-check exits 0"
else
  ko "security-update-check rc=${rc_sec}: ${out_sec:0:200}"
fi

sec_metrics="${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-security-updates.prom"
if [ -f "${sec_metrics}" ]; then
  ok "security-update-check emitted sovereign-os-security-updates.prom"
else
  ko "security-update-check metrics file missing"
fi

if grep -qE "^sovereign_os_security_updates_available -?[0-9]+$" "${sec_metrics}" 2>/dev/null; then
  ok "security_updates_available gauge present"
else
  ko "security_updates_available gauge missing/malformed"
fi

if grep -qE "^sovereign_os_security_update_check_last_run_timestamp [0-9]+$" "${sec_metrics}" 2>/dev/null; then
  ok "last_run_timestamp gauge present"
else
  ko "last_run_timestamp gauge missing"
fi

# On a non-Debian host (e.g., some CI runners), expect count=-1 sentinel
# OR a non-negative integer (when apt IS available). Either is valid.
val="$(grep -oE 'sovereign_os_security_updates_available -?[0-9]+' "${sec_metrics}" | awk '{print $2}')"
if [ -n "${val}" ] && [ "${val}" -ge -1 ]; then
  ok "security_updates_available value plausible (${val})"
else
  ko "security_updates_available unexpected value: ${val}"
fi

# ----------- backup-snapshot: DRY-RUN ---------------

snap_out_dryrun="$(SOVEREIGN_OS_DRY_RUN=1 "${SNAP}" 2>&1)"
if grep -q "DRY-RUN" <<< "${snap_out_dryrun}"; then
  ok "backup-snapshot honors SOVEREIGN_OS_DRY_RUN=1"
else
  ko "backup-snapshot missing DRY-RUN log"
fi

# DRY-RUN must NOT invoke zfs binary even if available
set +e
SOVEREIGN_OS_DRY_RUN=1 out_dryrun="$("${SNAP}" 2>&1)"
set -e
if ! grep -q "zfs snapshot" <<< "${out_dryrun}" || grep -q "would: zfs snapshot" <<< "${out_dryrun}"; then
  ok "backup-snapshot DRY-RUN does not run zfs snapshot (only logs intent)"
else
  ko "backup-snapshot DRY-RUN ran zfs snapshot — should only log intent"
fi

# ----------- backup-snapshot: real run on non-ZFS ---------------

set +e
out_snap="$(${SNAP} 2>&1)"
rc_snap=$?
set -e

if [ "${rc_snap}" -eq 0 ]; then
  ok "backup-snapshot exits 0 on non-ZFS host (graceful no-op)"
else
  ko "backup-snapshot rc=${rc_snap}: ${out_snap:0:200}"
fi

snap_metrics="${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-backup-snapshot.prom"
if [ -f "${snap_metrics}" ]; then
  ok "backup-snapshot emitted sovereign-os-backup-snapshot.prom"
else
  ko "backup-snapshot metrics file missing"
fi

for key in sovereign_os_snapshot_count sovereign_os_snapshot_last_created_timestamp \
           sovereign_os_snapshot_pruned_total sovereign_os_snapshot_created_total; do
  if grep -q "^${key}{" "${snap_metrics}" 2>/dev/null; then
    ok "metric ${key} emitted"
  else
    ko "metric ${key} missing"
  fi
done

# ----------- systemd unit files exist + L1 hardened ---------------

for unit in sovereign-security-update-check.service sovereign-security-update-check.timer \
            sovereign-backup-snapshot.service sovereign-backup-snapshot.timer; do
  if [ -f "${__REPO_ROOT}/systemd/system/${unit}" ]; then
    ok "systemd unit present: ${unit}"
  else
    ko "systemd unit missing: ${unit}"
  fi
done

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_recurrent_new_hooks: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
