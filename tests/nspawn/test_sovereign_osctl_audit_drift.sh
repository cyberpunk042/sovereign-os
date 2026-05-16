#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_audit_drift.sh
#
# Layer 3 test for `sovereign-osctl audit drift` (Round 111).
# Verifies drift detection across deployed hardening drop-ins, JSON mode,
# and DEST_PREFIX-aware redirection for chroot/image-build flows.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_sovereign_osctl_audit_drift.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

# Empty target: no drop-ins deployed
target="${tmp}/target-empty"
mkdir -p "${target}"

# ---------- empty target → all not-deployed, exit 0 ----------
set +e
out="$(SOVEREIGN_OS_HARDENING_DEST_PREFIX="${target}" "${OSCTL}" audit drift 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "drifted=0 unchanged=0 not-deployed=6" <<< "${out}"; then
  ok "empty target → exit 0 + 6 not-deployed"
else
  ko "empty-target gate broken (rc=${rc})"
fi

# ---------- deploy all server drop-ins; expect 5 unchanged + 1 not-deployed (ws sshd) ----------
mkdir -p "${target}/etc/audit/rules.d" \
         "${target}/etc/fail2ban/jail.d" \
         "${target}/etc/apt/apt.conf.d" \
         "${target}/etc/ssh/sshd_config.d" \
         "${target}/etc/security/pwquality.conf.d"
cp "${__REPO_ROOT}/config/server/auditd.rules" "${target}/etc/audit/rules.d/sovereign-os.rules"
cp "${__REPO_ROOT}/config/server/fail2ban-jail.local" "${target}/etc/fail2ban/jail.d/sovereign-os.local"
cp "${__REPO_ROOT}/config/server/unattended-upgrades.conf" "${target}/etc/apt/apt.conf.d/52sovereign-os-unattended.conf"
cp "${__REPO_ROOT}/config/server/sshd.conf" "${target}/etc/ssh/sshd_config.d/50sovereign-os.conf"
cp "${__REPO_ROOT}/config/server/pwquality.conf" "${target}/etc/security/pwquality.conf.d/50sovereign-os.conf"

set +e
out="$(SOVEREIGN_OS_HARDENING_DEST_PREFIX="${target}" "${OSCTL}" audit drift 2>&1)"
rc=$?
set -e
# Workstation sshd shares the same destination as server sshd, so when
# server sshd is deployed, the deployed file matches the server source
# but DIFFERS from workstation source → reports as drifted.
if [ "${rc}" -eq 1 ] && grep -q "drifted=1 unchanged=5 not-deployed=0" <<< "${out}"; then
  ok "server-deployed → 5 unchanged + 1 drifted (workstation sshd conflict)"
else
  ko "server-deployed summary wrong (rc=${rc}): ${out:0:200}"
fi

# ---------- introduce drift in auditd.rules; verify it flags ----------
echo "# operator-modified" >> "${target}/etc/audit/rules.d/sovereign-os.rules"
set +e
out="$(SOVEREIGN_OS_HARDENING_DEST_PREFIX="${target}" "${OSCTL}" audit drift 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "DRIFTED:.*\[server\] auditd.rules" <<< "${out}"; then
  ok "modified file → flagged as DRIFTED with file name"
else
  ko "drift detection broken (rc=${rc})"
fi

# Summary shows new drift count
if grep -q "drifted=2 unchanged=4 not-deployed=0" <<< "${out}"; then
  ok "drift summary correctly tallies (drifted=2, unchanged=4)"
else
  ko "drift summary wrong: ${out:0:200}"
fi

# Re-apply hint surfaced
if grep -q "re-apply with" <<< "${out}"; then
  ok "drift output includes operator re-apply remediation hint"
else
  ko "re-apply hint missing"
fi

# ---------- --json mode ----------
set +e
json_out="$(SOVEREIGN_OS_HARDENING_DEST_PREFIX="${target}" "${OSCTL}" audit drift --json 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ]; then
  ok "--json mode exits 1 on drift presence"
else
  ko "--json exit code wrong (rc=${rc})"
fi
# Valid JSON
if python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
assert 'summary' in data and 'entries' in data
assert data['summary']['drifted'] == 2
assert data['summary']['unchanged'] == 4
assert len(data['entries']) == 6
" <<< "${json_out}"; then
  ok "--json output is valid JSON + correct summary"
else
  ko "--json output malformed or summary mismatch"
fi

# JSON entries have required fields
if python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
for e in data['entries']:
    assert all(k in e for k in ('kind', 'file', 'destination', 'state')), f'missing field in {e}'
    assert e['kind'] in ('server', 'workstation')
    assert e['state'] in ('unchanged', 'drifted', 'not-deployed', 'source-missing')
" <<< "${json_out}"; then
  ok "--json entries have all required fields + valid enum values"
else
  ko "--json entry shape invalid"
fi

# ---------- clean state (only workstation deployed) → 1 unchanged + 5 not-deployed ----------
ws_target="${tmp}/target-ws"
mkdir -p "${ws_target}/etc/ssh/sshd_config.d"
cp "${__REPO_ROOT}/config/workstation/sshd.conf" "${ws_target}/etc/ssh/sshd_config.d/50sovereign-os.conf"

set +e
out="$(SOVEREIGN_OS_HARDENING_DEST_PREFIX="${ws_target}" "${OSCTL}" audit drift 2>&1)"
rc=$?
set -e
# Server sshd source ≠ deployed workstation sshd → server sshd is "drifted",
# workstation sshd is "unchanged", everything else not-deployed
if grep -q "drifted=1 unchanged=1 not-deployed=4" <<< "${out}"; then
  ok "workstation-only deployed → 1 unchanged (ws) + 1 drifted (server vs ws) + 4 not-deployed"
else
  ko "workstation-only summary wrong: ${out:0:200}"
fi

# ---------- help ----------
help_out="$("${OSCTL}" help 2>&1)"
if grep -q "audit drift" <<< "${help_out}"; then
  ok "help documents 'audit drift'"
else
  ko "help missing 'audit drift'"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_sovereign_osctl_audit_drift: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
