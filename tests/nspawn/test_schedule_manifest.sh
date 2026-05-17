#!/usr/bin/env bash
# tests/nspawn/test_schedule_manifest.sh — R262 (SDD-029 R262).
# Graceful-shutdown manifest: list, plan (dry-run), apply (gated).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/power/schedule-manifest.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
EXAMPLE="${__REPO_ROOT}/config/shutdown-manifest.toml.example"

echo "tests/nspawn/test_schedule_manifest.sh"
echo

[ -x "${SCRIPT}" ] && ok "schedule-manifest.py executable" \
  || { ko "missing"; exit 1; }
[ -f "${EXAMPLE}" ] && ok "example manifest shipped" || ko "example missing"
grep -q "R262" "${SCRIPT}" && ok "script cites R262" || ko "R262 missing"
grep -q "^  power-shutdown)" "${OSCTL}" \
  && ok "osctl bridges 'power-shutdown'" || ko "osctl dispatch missing"
grep -q "power-shutdown apply" "${OSCTL}" \
  && ok "osctl help documents 'power-shutdown'" || ko "osctl help missing"

TMP="$(mktemp -d -t r262.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

# ---- list --json: example manifest shape ----
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R262', d
assert d['valid'] is True, d
assert d['step_count'] == 6, d
names = [s['name'] for s in d['steps']]
assert 'drain-inference-router' in names, names
assert 'poweroff' in names, names
" \
  && ok "list --json: example has 6 steps incl. drain-inference-router + poweroff" \
  || ko "list shape wrong"

# ---- plan --json: dry-run plan ----
out="$(python3 "${SCRIPT}" plan --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['valid'] is True, d
assert len(d['plan']) == 6, d
for r in d['plan']:
    assert 'order' in r and 'name' in r and 'would_do' in r
" \
  && ok "plan --json: per-step 'would_do' description" \
  || ko "plan shape wrong"

# ---- apply without --confirm rc=2 ----
set +e
python3 "${SCRIPT}" apply > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "apply without --confirm → rc=2" \
  || ko "expected rc=2, got ${rc}"

# ---- apply --dry-run (no confirm needed) ----
set +e
out="$(python3 "${SCRIPT}" apply --dry-run --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "apply --dry-run rc=0" || ko "dry-run rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['dry_run'] is True, d
assert d['failure_count'] == 0, d
assert d['executed_count'] == 6, d
for r in d['results']:
    assert r['outcome'] == 'dry-run', r
" \
  && ok "apply --dry-run: every step outcome=dry-run, no real exec" \
  || ko "dry-run shape wrong"

# ---- apply --confirm with synthetic manifest (sleep + shell true only) ----
cat > "${TMP}/safe.toml" <<'TOML'
[meta]
description = "test-safe manifest"

[[steps]]
name = "test-shell-true"
kind = "shell"
cmd = "true"
timeout_s = 5
fail_action = "continue"

[[steps]]
name = "test-sleep"
kind = "sleep"
seconds = 0
timeout_s = 5
fail_action = "continue"
TOML

set +e
out="$(python3 "${SCRIPT}" apply --manifest "${TMP}/safe.toml" --confirm --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "apply --confirm rc=0 on safe manifest" || ko "rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['dry_run'] is False, d
assert d['confirmed'] is True, d
assert d['failure_count'] == 0, d
assert all(r['outcome'] == 'ok' for r in d['results']), d
" \
  && ok "apply --confirm safe manifest: 2 ok results, 0 failures" \
  || ko "apply-real shape wrong"

# ---- apply with FAILING shell step + fail_action=continue ----
cat > "${TMP}/fail-continue.toml" <<'TOML'
[[steps]]
name = "deliberate-fail"
kind = "shell"
cmd = "false"
timeout_s = 5
fail_action = "continue"

[[steps]]
name = "recover"
kind = "shell"
cmd = "true"
timeout_s = 5
fail_action = "continue"
TOML

set +e
out="$(python3 "${SCRIPT}" apply --manifest "${TMP}/fail-continue.toml" --confirm --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "fail+continue: rc=1 (≥1 failure)" || ko "expected rc=1, got ${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['failure_count'] == 1, d
assert d['executed_count'] == 2, d
assert d['aborted'] is False, d
assert d['results'][0]['outcome'] == 'failed', d
assert d['results'][1]['outcome'] == 'ok', d
" \
  && ok "fail+continue: continues past failure, both steps execute" \
  || ko "fail+continue shape wrong"

# ---- apply with FAILING shell step + fail_action=abort ----
cat > "${TMP}/fail-abort.toml" <<'TOML'
[[steps]]
name = "deliberate-fail"
kind = "shell"
cmd = "false"
timeout_s = 5
fail_action = "abort"

[[steps]]
name = "should-not-run"
kind = "shell"
cmd = "true"
timeout_s = 5
fail_action = "continue"
TOML

set +e
out="$(python3 "${SCRIPT}" apply --manifest "${TMP}/fail-abort.toml" --confirm --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "fail+abort: rc=1 (failure)" || ko "expected rc=1, got ${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['aborted'] is True, d
# results includes the failed step + the (abort) marker.
names = [r['name'] for r in d['results']]
assert 'deliberate-fail' in names, names
assert 'should-not-run' not in names, names
" \
  && ok "fail+abort: aborts sequence, downstream step skipped" \
  || ko "fail+abort shape wrong"

# ---- invalid manifest → validation errors → apply rc=2 ----
cat > "${TMP}/invalid.toml" <<'TOML'
[[steps]]
name = "bogus"
kind = "not-a-real-kind"
TOML

set +e
python3 "${SCRIPT}" apply --manifest "${TMP}/invalid.toml" --confirm --json > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "invalid manifest → apply rc=2" || ko "expected rc=2, got ${rc}"

# ---- list surfaces validation errors ----
out="$(python3 "${SCRIPT}" list --manifest "${TMP}/invalid.toml" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['valid'] is False, d
assert len(d['validation_errors']) > 0, d
" \
  && ok "list surfaces validation errors when manifest invalid" \
  || ko "validation-error surface wrong"

# ---- SOVEREIGN_OS_CONFIRM_DESTROY=YES alternative gate ----
set +e
out="$(SOVEREIGN_OS_CONFIRM_DESTROY=YES python3 "${SCRIPT}" apply --manifest "${TMP}/safe.toml" --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "SOVEREIGN_OS_CONFIRM_DESTROY=YES alt-gate works" \
  || ko "alt-gate rc=${rc}"

# ---- osctl bridge ----
set +e
"${OSCTL}" power-shutdown list --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl power-shutdown list rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R262', d
" \
  && ok "osctl bridge surfaces R262 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" power-shutdown nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown power-shutdown subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_schedule_manifest: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
