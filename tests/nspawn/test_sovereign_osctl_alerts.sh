#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_alerts.sh
#
# Layer 3 test for `sovereign-osctl alerts` (Round 89).
# Verifies the rule engine against synthetic .prom files covering each rule.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_sovereign_osctl_alerts.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

# ---------- clean dir → 0 alerts, exit 0 ----------
clean="${tmp}/clean"; mkdir -p "${clean}"
cat > "${clean}/sovereign-os-clean.prom" <<'EOF'
sovereign_os_build_step_render_total{profile="sain-01",result="success"} 1
sovereign_os_perimeter_status 1
sovereign_os_zfs_pool_health{pool="tank"} 1
sovereign_os_security_updates_available 0
EOF

set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${clean}" "${OSCTL}" alerts 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "no alerts derived" <<< "${out}"; then
  ok "clean dir → exit 0 + 'no alerts derived'"
else
  ko "clean-dir gate broken (rc=${rc})"
fi

# ---------- failing build step → ALERT ----------
dirty="${tmp}/dirty"; mkdir -p "${dirty}"
cat > "${dirty}/sovereign-os-build.prom" <<'EOF'
sovereign_os_build_step_sign_total{profile="sain-01",posture="signed",result="fail"} 1
EOF

set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${dirty}" "${OSCTL}" alerts 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q '\[ALERT\] sovereign_os_build_step_sign_total' <<< "${out}"; then
  ok "Rule 1 — failing build-step counter → ALERT + exit 1"
else
  ko "Rule 1 broken (rc=${rc})"
fi

# ---------- friction audit failures → ALERT ----------
fric="${tmp}/fric"; mkdir -p "${fric}"
cat > "${fric}/sovereign-os-friction.prom" <<'EOF'
sovereign_os_friction_audit_failures{profile="sain-01"} 3
EOF

set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${fric}" "${OSCTL}" alerts 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "Rule 2\|friction_audit_failures" <<< "${out}" && grep -q "ALERT.*friction_audit_failures" <<< "${out}"; then
  ok "Rule 2 — friction_audit_failures > 0 → ALERT"
else
  ko "Rule 2 broken (rc=${rc})"
fi

# ---------- perimeter inactive → ALERT ----------
peri="${tmp}/peri"; mkdir -p "${peri}"
cat > "${peri}/sovereign-os-perimeter.prom" <<'EOF'
sovereign_os_perimeter_status 0
EOF

set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${peri}" "${OSCTL}" alerts 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "ALERT.*sovereign_os_perimeter_status" <<< "${out}" && grep -q "Tetragon not active" <<< "${out}"; then
  ok "Rule 3 — perimeter_status != 1 → ALERT + remediation"
else
  ko "Rule 3 broken (rc=${rc})"
fi

# ---------- zfs pool degraded → ALERT ----------
zfs="${tmp}/zfs"; mkdir -p "${zfs}"
cat > "${zfs}/sovereign-os-zfs.prom" <<'EOF'
sovereign_os_zfs_pool_health{pool="tank"} 0
EOF

set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${zfs}" "${OSCTL}" alerts 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "ALERT.*zfs_pool_health" <<< "${out}" && grep -q "pool 'tank' not ONLINE" <<< "${out}"; then
  ok "Rule 4 — zfs_pool_health < 1 → ALERT"
else
  ko "Rule 4 broken (rc=${rc})"
fi

# ---------- security updates pending → WARN (not ALERT, so exit 0) ----------
sec="${tmp}/sec"; mkdir -p "${sec}"
cat > "${sec}/sovereign-os-sec.prom" <<'EOF'
sovereign_os_security_updates_available 7
EOF

set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${sec}" "${OSCTL}" alerts 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "WARN.*security_updates_available" <<< "${out}" && grep -q "7 security update" <<< "${out}"; then
  ok "Rule 5 — security_updates_available > 0 → WARN + exit 0"
else
  ko "Rule 5 broken (rc=${rc})"
fi

# ---------- stale last-run timestamp → WARN ----------
stale="${tmp}/stale"; mkdir -p "${stale}"
# 30 days ago in unix epoch
old_ts=$(( $(date +%s) - 30 * 86400 ))
cat > "${stale}/sovereign-os-stale.prom" <<EOF
sovereign_os_log_rotation_last_run_timestamp ${old_ts}
EOF

set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${stale}" "${OSCTL}" alerts 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "WARN.*last_run_timestamp" <<< "${out}"; then
  ok "Rule 6 — stale _last_run_timestamp → WARN"
else
  ko "Rule 6 broken (rc=${rc})"
fi

# ---------- --json mode emits valid JSON array ----------
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${dirty}" "${OSCTL}" alerts --json 2>&1)"
rc=$?
set -e
if python3 -c "import json,sys; arr=json.loads(sys.stdin.read()); assert isinstance(arr, list) and len(arr)>=1 and arr[0]['level']=='ALERT'" <<< "${out}"; then
  ok "--json mode emits a valid JSON array with ALERT entries"
else
  ko "--json mode broken (rc=${rc})"
fi

# ---------- --json mode on clean dir emits [] ----------
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${clean}" "${OSCTL}" alerts --json 2>&1)"
set -e
if [ "${out}" = "[]" ]; then
  ok "--json mode on clean dir → []"
else
  ko "--json clean-dir broken: got '${out:0:80}…'"
fi

# ---------- absent dir → exit 0 + clear message ----------
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${tmp}/no-such-dir-$$" "${OSCTL}" alerts 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "metrics dir absent" <<< "${out}"; then
  ok "absent dir → exit 0 + 'metrics dir absent'"
else
  ko "absent-dir gate broken (rc=${rc})"
fi

# ---------- absent dir --json → [] ----------
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${tmp}/no-such-dir-$$" "${OSCTL}" alerts --json 2>&1)"
set -e
if [ "${out}" = "[]" ]; then
  ok "absent dir + --json → []"
else
  ko "absent-dir+json broken"
fi

# ---------- combined: ALERT outranks WARN in summary ----------
combo="${tmp}/combo"; mkdir -p "${combo}"
cat > "${combo}/sovereign-os-mix.prom" <<EOF
sovereign_os_perimeter_status 0
sovereign_os_security_updates_available 3
EOF

set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${combo}" "${OSCTL}" alerts 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "ALERT count: 1" <<< "${out}" && grep -q "WARN  count: 1" <<< "${out}"; then
  ok "combined ALERT+WARN — both counted, exit 1 on ALERT presence"
else
  ko "combined-rule gate broken (rc=${rc})"
fi

# ---------- help documents alerts ----------
help_out="$("${OSCTL}" help 2>&1)"
if grep -q "alerts \[--json\]" <<< "${help_out}"; then
  ok "help documents 'alerts [--json]'"
else
  ko "help missing alerts row"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_sovereign_osctl_alerts: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
