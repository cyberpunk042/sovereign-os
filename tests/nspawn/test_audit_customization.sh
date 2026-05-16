#!/usr/bin/env bash
# tests/nspawn/test_audit_customization.sh
#
# Layer 3 test for sovereign-osctl audit customization (R142; F-07 MED).
# Verifies the cross-cutting check shape + JSON schema.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_audit_customization.sh"
echo

# Text mode
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 "${OSCTL}" audit customization 2>&1)"
rc=$?
set -e

# rc is 0 (clean) or 1 (some fail) depending on the test host; both acceptable
if [ "${rc}" -le 1 ]; then
  ok "audit customization → exit ≤ 1 (per fail-presence)"
else
  ko "unexpected rc=${rc}"
fi

# Header
if grep -q "customization audit" <<< "${out}"; then
  ok "header line surfaced"
else
  ko "header missing"
fi

# Required check names
for name in "active-profile" "os-release-id" "package-count" "hostname"; do
  if grep -q "${name}" <<< "${out}"; then
    ok "check surfaced: ${name}"
  else
    ko "check missing: ${name}"
  fi
done

# Summary line
if grep -qE "summary: [0-9]+ pass" <<< "${out}"; then
  ok "summary line with pass count"
else
  ko "summary line missing"
fi

# ---------- --json ----------
set +e
json_out="$(SOVEREIGN_OS_PROFILE=sain-01 "${OSCTL}" audit customization --json 2>&1)"
rc=$?
set -e
if [ "${rc}" -le 1 ]; then
  ok "audit customization --json → exit ≤ 1"
else
  ko "json mode rc=${rc}"
fi

# Valid JSON with schema
if python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
assert 'summary' in data and 'checks' in data
assert 'profile' in data
s = data['summary']
for k in ('pass','warn','fail'):
    assert k in s, f'summary missing {k}'
    assert isinstance(s[k], int)
for c in data['checks']:
    for f in ('status','name','expected','actual'):
        assert f in c, f'check missing {f}: {c}'
    assert c['status'] in ('pass','warn','fail')
" <<< "${json_out}"; then
  ok "--json output is valid + schema-conformant"
else
  ko "--json schema broken"
fi

# Schema asserts checks exist for known names
if python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
names = {c['name'] for c in data['checks']}
for n in ('active-profile','os-release-id','package-count','hostname'):
    assert n in names, f'missing check: {n}'
" <<< "${json_out}"; then
  ok "--json contains every required check"
else
  ko "--json missing required checks"
fi

# ---------- missing profile ----------
set +e
out="$(SOVEREIGN_OS_PROFILE=does-not-exist "${OSCTL}" audit customization 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "missing" <<< "${out}"; then
  ok "missing profile → exit 1 + 'missing'"
else
  ko "missing-profile gate broken (rc=${rc})"
fi

# ---------- --json missing profile ----------
set +e
json_out="$(SOVEREIGN_OS_PROFILE=does-not-exist "${OSCTL}" audit customization --json 2>&1)"
set -e
if python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
assert data['summary']['fail'] >= 1
" <<< "${json_out}"; then
  ok "--json on missing profile still emits parseable JSON"
else
  ko "--json missing-profile shape broken"
fi

# ---------- help mentions ----------
help_out="$("${OSCTL}" help 2>&1)"
if grep -q "audit customization" <<< "${help_out}"; then
  ok "help documents 'audit customization'"
else
  ko "help missing"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_audit_customization: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
