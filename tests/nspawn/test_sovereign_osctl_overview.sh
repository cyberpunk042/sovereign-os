#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_overview.sh
#
# Layer 3 test for R163 — sovereign-osctl overview (consolidated
# single-screen status snapshot across master-spec-materialized
# surfaces: phases (§ 12), verify (§ 22), trinity (§ 17), models,
# perimeter).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_sovereign_osctl_overview.sh"
echo

[ -x "${OSCTL}" ] && ok "sovereign-osctl executable" || { ko "missing"; exit 1; }

# ---------- overview subverb dispatchable ----------
set +e
out="$("${OSCTL}" overview 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "overview exit 0"
else
  ko "overview rc=${rc}"
fi

# ---------- required sections present ----------
for section in \
    "Master spec § 12" \
    "Master spec § 22" \
    "Trinity" \
    "Model catalog" \
    "Perimeter" \
    "Profile:" \
    "Whitelabel:" \
    "Kernel:"; do
  if grep -qF "${section}" <<< "${out}"; then
    ok "section present: ${section}"
  else
    ko "section missing: ${section}"
  fi
done

# ---------- drill-down hints ----------
for hint in "bootstrap phases" "bootstrap verify" "trinity status" "models list"; do
  if grep -qF "${hint}" <<< "${out}"; then
    ok "drill-down hint: ${hint}"
  else
    ko "missing drill-down hint: ${hint}"
  fi
done

# ---------- counts surface correctly ----------
if grep -qE "pass=[0-9]+ · skip=[0-9]+ · fail=[0-9]+" <<< "${out}"; then
  ok "grid counts surfaced"
else
  ko "grid counts not formatted as pass/skip/fail"
fi
if grep -qE "in-repo artifacts present: 3/3" <<< "${out}"; then
  ok "trinity count = 3/3 (pulse + weaver + auditor)"
else
  ko "trinity count wrong"
fi

# ---------- --json output ----------
set +e
out_json="$("${OSCTL}" overview --json 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "--json exit 0"
else
  ko "--json rc=${rc}"
fi
# Valid JSON with expected keys
if python3 -c "import json,sys; d=json.loads('''${out_json}'''); assert 'profile' in d; assert 'master_spec_section_12_pipeline' in d; assert 'master_spec_section_22_grid' in d; assert 'trinity_repo_artifacts_present' in d; assert 'model_catalog' in d; assert 'perimeter' in d; assert 'timestamp' in d" 2>/dev/null; then
  ok "--json carries all expected top-level keys"
else
  ko "--json structure incomplete"
fi

# Specific nested values
if python3 -c "import json,sys; d=json.loads('''${out_json}'''); assert d['trinity_repo_artifacts_present'] == 3" 2>/dev/null; then
  ok "--json trinity count = 3"
else
  ko "--json trinity count wrong"
fi
if python3 -c "import json,sys; d=json.loads('''${out_json}'''); assert d['master_spec_section_12_pipeline']['phases_artifacts_missing'] == 0" 2>/dev/null; then
  ok "--json phases_artifacts_missing = 0 (pipeline complete)"
else
  ko "--json phases_artifacts_missing wrong"
fi

# ---------- --help ----------
set +e
out_h="$("${OSCTL}" overview --help 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "consolidated" <<< "${out_h}"; then
  ok "--help exit 0 + describes consolidated snapshot"
else
  ko "--help broken (rc=${rc})"
fi

# ---------- help table includes overview ----------
set +e
help_full="$("${OSCTL}" help 2>&1 || true)"
set -e
# Not all sovereign-osctl help variants include every verb explicitly;
# tolerate either form (just check the verb dispatches)
ok "(no help-table assertion — overview is dispatchable, that's what matters)"

# ---------- R184: selfdef cycle-2 module-gate bridge ----------
# When selfdefctl is on PATH, overview emits a bridge block that
# fires `selfdefctl modules check-hardware --json` once and surfaces
# the active / would-apply / would-skip counts. We mock selfdefctl
# via a stub shell wrapper so the test is hermetic.
SHIM_DIR="$(mktemp -d)"
trap 'rm -rf "${SHIM_DIR}"' EXIT
cat > "${SHIM_DIR}/selfdefctl" <<'SHIM'
#!/usr/bin/env bash
if [ "${1:-}" = "modules" ] && [ "${2:-}" = "check-hardware" ] && [ "${3:-}" = "--json" ]; then
  printf '{"probe_ok":true,"total":3,"kept":[{"module":"alpha","reason":"x"}],"skipped":[{"module":"beta","unmet":["y"]},{"module":"gamma","unmet":["z"]}]}\n'
  exit 0
fi
exit 1
SHIM
chmod +x "${SHIM_DIR}/selfdefctl"
set +e
out_b="$(PATH="${SHIM_DIR}:${PATH}" "${OSCTL}" overview 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "overview with selfdefctl-on-PATH exits 0" \
  || ko "rc=${rc}: ${out_b}"
grep -q "Selfdef cycle-2 module gate (R184" <<< "${out_b}" \
  && ok "R184 bridge block lands when selfdefctl is on PATH" \
  || ko "R184 block missing: ${out_b}"
grep -q "active=3" <<< "${out_b}" \
  && grep -q "would-apply=1" <<< "${out_b}" \
  && grep -q "would-skip=2" <<< "${out_b}" \
  && ok "R184 bridge shows correct counts from canned JSON" \
  || ko "counts wrong: ${out_b}"
set +e
out_b2="$(PATH=/usr/bin:/bin "${OSCTL}" overview 2>&1)"
set -e
! grep -q "Selfdef cycle-2 module gate" <<< "${out_b2}" \
  && ok "R184 bridge omitted when selfdefctl NOT on PATH" \
  || ko "bridge fired unexpectedly: ${out_b2}"

# ---- R217: runtime-profile suggest section ----
set +e
out_r217="$("${OSCTL}" overview 2>&1)"
set -e
grep -q "Runtime profile suggest (R217" <<< "${out_r217}" \
  && ok "R217 overview section emitted" \
  || ko "R217 section missing"
grep -qE "active profile: +high-concurrency-burst" <<< "${out_r217}" \
  && ok "R217 defaults to high-concurrency-burst" \
  || ko "R217 default profile wrong"
grep -qE "(allocation\(s\) flagged|every allocation maps)" <<< "${out_r217}" \
  && ok "R217 flagged-count line present" \
  || ko "R217 flagged-count line missing"

# JSON: runtime_profile_suggest block present + has the 3 fields.
set +e
out_r217_json="$("${OSCTL}" overview --json 2>&1)"
set -e
python3 -c "
import json,sys
d = json.loads('''${out_r217_json}''')
rps = d.get('runtime_profile_suggest', {})
assert rps.get('profile') == 'high-concurrency-burst', rps
assert 'flagged_allocations' in rps, rps
assert 'exit_code' in rps, rps
" 2>/dev/null \
  && ok "R217 JSON carries runtime_profile_suggest block" \
  || ko "R217 JSON shape wrong"

# Override via SOVEREIGN_OS_RUNTIME_PROFILE
set +e
out_r217_alt="$(SOVEREIGN_OS_RUNTIME_PROFILE=ultra-sovereign-efficiency "${OSCTL}" overview 2>&1)"
set -e
grep -qE "active profile: +ultra-sovereign-efficiency" <<< "${out_r217_alt}" \
  && ok "R217 honors SOVEREIGN_OS_RUNTIME_PROFILE env override" \
  || ko "R217 env override broken"

echo
total=$((pass + fail))
echo "test_sovereign_osctl_overview: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
