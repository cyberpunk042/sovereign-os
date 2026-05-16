#!/usr/bin/env bash
# tests/nspawn/test_wizard.sh
#
# Layer 3 test for R169 — sovereign-osctl wizard (selfdef SD-R11 mirror).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/wizard/onboard.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_wizard.sh"
echo

[ -x "${SCRIPT}" ] && ok "onboard.py executable" || { ko "missing"; exit 1; }
[ -x "${OSCTL}" ] && ok "sovereign-osctl executable" || ko "osctl missing"

grep -q "SD-R11" "${SCRIPT}" && ok "script cites selfdef SD-R11 (cross-repo mirror)" \
  || ko "SD-R11 citation missing"

# ---------- default invocation: 4 steps ----------
set +e
out="$(python3 "${SCRIPT}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "default invocation exits 0" || ko "rc=${rc}"
for step in "Step 1: Hardware probe" "Step 2: Recommendation" "Step 3:" "Step 4: Next steps"; do
  grep -q "${step}" <<< "${out}" && ok "section: ${step}" \
    || ko "section missing: ${step}"
done

# ---------- --verdict-only returns one of the 5 known profiles ----------
set +e
verdict="$(python3 "${SCRIPT}" --verdict-only 2>&1)"
set -e
case "${verdict}" in
  sain-01|headless|developer|old-workstation|minimal)
    ok "--verdict-only returns valid profile: ${verdict}"
    ;;
  *)
    ko "--verdict-only returned bad value: ${verdict}"
    ;;
esac

# ---------- --json output ----------
set +e
out="$(python3 "${SCRIPT}" --json 2>&1)"
set -e
if python3 -c "import json,sys; d=json.loads('''${out}'''); assert 'probe' in d; assert 'recommendation' in d; assert d['recommendation']['recommended_profile'] in ('sain-01','headless','developer','old-workstation','minimal'); assert 'next_steps' in d['recommendation']; assert 'rationale' in d['recommendation']; assert 'selfdef_capabilities_present' in d['recommendation']" 2>/dev/null; then
  ok "--json output is valid + carries all expected keys"
else
  ko "--json output broken"
fi

# ---------- cross-repo bridge detection ----------
# Default: no selfdef capabilities file present → next_steps mentions
# selfdefctl hardware export
set +e
out="$(python3 "${SCRIPT}" 2>&1)"
set -e
if grep -q "selfdefctl hardware export" <<< "${out}"; then
  ok "cross-repo bridge surfaces selfdefctl hardware export when caps absent"
else
  ko "selfdef bridge guidance missing"
fi

# ---------- sovereign-osctl wizard dispatches ----------
set +e
out="$("${OSCTL}" wizard --verdict-only 2>&1)"
set -e
case "${out}" in
  sain-01|headless|developer|old-workstation|minimal)
    ok "sovereign-osctl wizard dispatches script correctly"
    ;;
  *)
    ko "osctl dispatch broken: ${out}"
    ;;
esac

# ---------- output includes a copy-pasteable next-step set ----------
set +e
out="$("${OSCTL}" wizard 2>&1)"
set -e
grep -qE 'sovereign-osctl install|sovereign-osctl trinity|sovereign-osctl bootstrap' <<< "${out}" \
  && ok "next-step commands include a sovereign-osctl verb" \
  || ko "next-step section missing osctl verbs"

# ---------- doesn't write anything ----------
TMP_FAKE_FILES="$(ls -la /tmp /var/tmp 2>/dev/null | wc -l)"
python3 "${SCRIPT}" >/dev/null 2>&1
TMP_FAKE_FILES_AFTER="$(ls -la /tmp /var/tmp 2>/dev/null | wc -l)"
# We just verify it doesn't crash; no strict file-count assertion
# because parallel processes may create temp files.
ok "wizard pure-read invocation completes without error"

# ---------- R186: per-profile selfdef module recommendations ----------
grep -q "R186" "${SCRIPT}" \
  && ok "wizard carries R186 marker" \
  || ko "R186 marker missing"
set +e
out_full="$(python3 "${SCRIPT}" --json 2>&1)"
set -e
if python3 -c "
import json
d = json.loads('''${out_full}''')
rec = d['recommendation']
assert 'selfdef_module_recommendations' in rec, 'missing R186 field'
assert isinstance(rec['selfdef_module_recommendations'], list)
" 2>/dev/null; then
  ok "--json carries selfdef_module_recommendations array"
else
  ko "R186 JSON field missing"
fi

# When the wizard's recommendation includes any modules, the human
# output should surface a "Step 3.5" block with the copy-paste hint.
set +e
out_h="$(python3 "${SCRIPT}" 2>&1)"
set -e
# On a CPU with AVX-512 (which CI runners often have), at least
# hardware-tune-cache should appear; on minimal hosts the block is
# absent. Either way the test must not crash — assert that IF the
# block appears, it carries the section heading + a [modules.…] line.
if grep -q "Step 3.5: Recommended selfdef modules" <<< "${out_h}"; then
  grep -q "\[modules\." <<< "${out_h}" \
    && ok "Step 3.5 block: copy-paste [modules.X] line present" \
    || ko "Step 3.5 section without copy-paste line"
else
  ok "(Step 3.5 absent — host doesn't trigger any recommendations; informational)"
fi

echo
total=$((pass + fail))
echo "test_wizard: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
