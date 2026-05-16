#!/usr/bin/env bash
# tests/nspawn/test_bootstrap_hardware_match.sh
#
# Layer 3 test for R166 — scripts/hardware/sain01-match.py +
# sovereign-osctl bootstrap hardware-match (selfdef SDD-017 mirror).
#
# Validates the cross-repo mirror: same dimensions, same verdict
# semantics, same exit codes as selfdef's `selfdefctl hardware`.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/sain01-match.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_bootstrap_hardware_match.sh"
echo

[ -x "${SCRIPT}" ] && ok "sain01-match.py executable" || { ko "missing"; exit 1; }
[ -x "${OSCTL}" ]  && ok "sovereign-osctl executable" || ko "osctl missing"

grep -q "SDD-017" "${SCRIPT}" && ok "script cites selfdef SDD-017 (cross-repo mirror)" \
  || ko "SDD-017 citation missing"

# ---------- default invocation prints all sections ----------
set +e
out="$(python3 "${SCRIPT}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] || [ "${rc}" -eq 2 ] && ok "default run exits 0 or 2" \
  || ko "default rc=${rc}"
for section in "## CPU" "## Memory" "## GPUs" "## Motherboard" "## PCIe" "## Sain01Match verdict"; do
  grep -q "${section}" <<< "${out}" && ok "section: ${section}" \
    || ko "section missing: ${section}"
done

# ---------- --verdict-only ----------
set +e
out="$(python3 "${SCRIPT}" --verdict-only 2>&1)"
rc=$?
set -e
case "${out}" in
  FullMatch|PartialMatch|NoMatch)
    ok "--verdict-only returns valid label: ${out}"
    ;;
  *)
    ko "--verdict-only returned bad label: ${out}"
    ;;
esac

# ---------- --json ----------
set +e
out="$(python3 "${SCRIPT}" --json 2>&1)"
set -e
if python3 -c "import json,sys; d=json.loads('''${out}'''); assert 'snapshot' in d; assert 'sain01_match' in d; assert d['sain01_match']['overall'] in ('FullMatch','PartialMatch','NoMatch')" 2>/dev/null; then
  ok "--json output is valid + carries expected keys"
else
  ko "--json output broken"
fi

# ---------- exit-code mapping ----------
# We can't FORCE the verdict on the test host but we can verify the
# rule (0 for Full/Partial, 2 for NoMatch).
set +e
verdict="$(python3 "${SCRIPT}" --verdict-only 2>/dev/null)"
rc=$?
set -e
case "${verdict}" in
  FullMatch|PartialMatch)
    [ "${rc}" -eq 0 ] && ok "Full/Partial verdict → rc=0" || ko "Full/Partial gave rc=${rc}"
    ;;
  NoMatch)
    [ "${rc}" -eq 2 ] && ok "NoMatch verdict → rc=2" || ko "NoMatch gave rc=${rc}"
    ;;
esac

# ---------- sovereign-osctl bootstrap hardware-match dispatches ----------
set +e
out="$("${OSCTL}" bootstrap hardware-match --verdict-only 2>&1)"
set -e
case "${out}" in
  FullMatch|PartialMatch|NoMatch)
    ok "sovereign-osctl bootstrap hardware-match dispatches correctly"
    ;;
  *)
    ko "osctl dispatch broken: ${out}"
    ;;
esac

# ---------- help text mentions hardware-match ----------
set +e
help_out="$("${OSCTL}" bootstrap help 2>&1)"
set -e
grep -q "hardware-match" <<< "${help_out}" && ok "bootstrap help documents hardware-match" \
  || ko "help missing hardware-match"

echo
total=$((pass + fail))
echo "test_bootstrap_hardware_match: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
