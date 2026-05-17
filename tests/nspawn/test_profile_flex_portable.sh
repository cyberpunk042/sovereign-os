#!/usr/bin/env bash
# tests/nspawn/test_profile_flex_portable.sh — R245 (SDD-026 Z-3 expansion).
# Operator-portable flex-profile bundle: export → import (replace/merge).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/profile-flex.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_profile_flex_portable.sh"
echo

[ -x "${SCRIPT}" ] && ok "profile-flex.py executable" \
  || { ko "missing profile-flex.py"; exit 1; }
grep -q "R245" "${SCRIPT}" && ok "profile-flex.py cites R245" || ko "R245 missing"
grep -q "profiles flex export" "${OSCTL}" \
  && ok "osctl help documents 'export'" || ko "osctl help missing"

TMP="$(mktemp -d -t r245.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
HOST_A="${TMP}/host-a.json"
HOST_B="${TMP}/host-b.json"
BUNDLE="${TMP}/bundle.json"

# ---- seed host-a with 3 deltas ----
python3 "${SCRIPT}" --state "${HOST_A}" set inference.streaming true > /dev/null
python3 "${SCRIPT}" --state "${HOST_A}" set gpu.power_limit_watts 300 > /dev/null
python3 "${SCRIPT}" --state "${HOST_A}" set cpu.affinity "0-5" > /dev/null

# ---- export from host-a to bundle ----
python3 "${SCRIPT}" --state "${HOST_A}" export --output "${BUNDLE}" --json > "${TMP}/exp.out"
python3 -c "
import json
d=json.load(open('${TMP}/exp.out'))
assert d['exported'] is True, d
assert d['delta_count']==3, d
assert d['path']=='${BUNDLE}', d
" \
  && ok "export --output writes bundle + JSON status" \
  || ko "export shape wrong"

# Bundle file shape
python3 -c "
import json
d=json.load(open('${BUNDLE}'))
assert d['round']=='R245', d
assert d['delta_count']==3, d
keys=sorted(x['key'] for x in d['deltas'])
assert keys==['cpu.affinity','gpu.power_limit_watts','inference.streaming'], keys
" \
  && ok "bundle JSON has round + delta_count + sorted deltas" \
  || ko "bundle shape wrong"

# ---- import bundle into host-b (replace mode default) ----
python3 "${SCRIPT}" --state "${HOST_B}" import "${BUNDLE}" --json > "${TMP}/imp.out"
python3 -c "
import json
d=json.load(open('${TMP}/imp.out'))
assert d['imported'] is True, d
assert d['mode']=='replace', d
assert d['prior_count']==0, d
assert d['incoming_count']==3, d
assert d['final_count']==3, d
" \
  && ok "import replace into empty host: prior=0 final=3" \
  || ko "import shape wrong"

# Verify host-b state matches host-a logically.
python3 -c "
import json
a=json.load(open('${HOST_A}'))['deltas']
b=json.load(open('${HOST_B}'))['deltas']
a_keys=sorted(x['key'] for x in a)
b_keys=sorted(x['key'] for x in b)
assert a_keys==b_keys, f'host-b keys differ: {a_keys} vs {b_keys}'
" \
  && ok "host-b deltas match host-a after replace-import" \
  || ko "host-b state differs"

# ---- replace mode drops existing deltas ----
python3 "${SCRIPT}" --state "${HOST_B}" set extra.knob 42 > /dev/null
# host-b now has 4 deltas (3 imported + 1 extra)
python3 "${SCRIPT}" --state "${HOST_B}" import "${BUNDLE}" --mode replace --json > "${TMP}/imp2.out"
python3 -c "
import json
d=json.load(open('${TMP}/imp2.out'))
assert d['prior_count']==4, d
assert d['final_count']==3, d  # back to bundle's 3
" \
  && ok "import --mode replace drops prior deltas" \
  || ko "replace mode wrong"

# ---- merge mode appends ----
python3 "${SCRIPT}" --state "${HOST_B}" set merge.test 99 > /dev/null
# host-b has 4 deltas (3 + 1 merge.test)
python3 "${SCRIPT}" --state "${HOST_B}" import "${BUNDLE}" --mode merge --json > "${TMP}/imp3.out"
python3 -c "
import json
d=json.load(open('${TMP}/imp3.out'))
assert d['mode']=='merge', d
assert d['prior_count']==4, d
assert d['incoming_count']==3, d
assert d['final_count']==7, d  # 4 + 3
" \
  && ok "import --mode merge appends (4+3=7)" \
  || ko "merge mode wrong"

# ---- import non-existent bundle → rc=2 ----
set +e
python3 "${SCRIPT}" --state "${HOST_B}" import /tmp/never-existed.json > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "import missing bundle → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- import malformed JSON → rc=2 ----
echo "not json" > "${TMP}/bad.json"
set +e
python3 "${SCRIPT}" --state "${HOST_B}" import "${TMP}/bad.json" > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "import bad JSON → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- import bundle missing `deltas` key → rc=2 ----
echo '{"hi": "world"}' > "${TMP}/incomplete.json"
set +e
python3 "${SCRIPT}" --state "${HOST_B}" import "${TMP}/incomplete.json" > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "import schema-mismatch bundle → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- export with no --output goes to stdout ----
out="$(python3 "${SCRIPT}" --state "${HOST_A}" export)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R245', d
assert d['delta_count']==3, d
" \
  && ok "export without --output emits to stdout" \
  || ko "stdout export wrong"

# ---- import --mode bogus → rc=2 (argparse) ----
set +e
python3 "${SCRIPT}" --state "${HOST_B}" import "${BUNDLE}" --mode nope > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "import --mode bogus → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- osctl bridge ----
set +e
"${OSCTL}" profiles flex export --state "${HOST_A}" --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl profiles flex export rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R245', d
assert d['delta_count']==3, d
" \
  && ok "osctl bridge surfaces R245 JSON" \
  || ko "osctl JSON wrong"

echo
total=$((pass + fail))
echo "test_profile_flex_portable: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
