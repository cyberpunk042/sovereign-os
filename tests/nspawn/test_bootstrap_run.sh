#!/usr/bin/env bash
# tests/nspawn/test_bootstrap_run.sh
#
# Layer 3 test for R201 — `sovereign-osctl bootstrap run` master spec
# § 12 phase executor (DRY-RUN-ONLY first cut).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
RUN="${__REPO_ROOT}/scripts/bootstrap/run.sh"
PHASES="${__REPO_ROOT}/scripts/bootstrap/phases.sh"

echo "tests/nspawn/test_bootstrap_run.sh"
echo

[ -x "${RUN}" ] && ok "bootstrap/run.sh executable" \
  || { ko "missing bootstrap/run.sh"; exit 1; }

grep -q "run)" "${OSCTL}" \
  && ok "osctl carries R201 'run' subverb dispatch" \
  || ko "run dispatch missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---- usage ----
set +e
"${RUN}" --phase 7 >"${WORK}/usage.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "invalid --phase rejected with rc=2" \
  || ko "expected rc=2 on bad phase, got ${rc}"

# ---- all-phase plan ----
set +e
"${RUN}" >"${WORK}/all.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "all-phase dry-run rc=0 on clean tree" \
  || ko "expected rc=0, got ${rc}"

for phase in I II III IV V; do
  grep -q "Phase ${phase} — execution plan" "${WORK}/all.out" \
    && ok "Phase ${phase} plan section emitted" \
    || ko "Phase ${phase} section missing"
done

grep -q "DRY-RUN ONLY" "${WORK}/all.out" \
  && ok "safety banner emitted" || ko "no safety banner"
grep -q "SOVEREIGN_OS_CONFIRM_DESTROY=YES" "${WORK}/all.out" \
  && ok "safety banner cites destructive-gate env var" \
  || ko "no destructive-gate citation"

# Each artifact kind should appear somewhere in the all-phase output.
for kind in build-step installer-hook post-install-hook recurrent-hook \
            systemd-unit systemd-timer tooling config; do
  grep -q "\[${kind} " "${WORK}/all.out" \
    && ok "kind '${kind}' surfaces in plan" \
    || ko "kind '${kind}' never classified"
done

# ---- --phase filter ----
set +e
"${RUN}" --phase 3 >"${WORK}/p3.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--phase 3 rc=0" || ko "expected rc=0 on phase 3"
grep -q "Phase III" "${WORK}/p3.out" \
  && ok "--phase 3 emits Phase III" || ko "missing Phase III header"
! grep -q "Phase I — execution plan" "${WORK}/p3.out" \
  && ok "--phase 3 filters out Phase I" || ko "phase filter leaked"

# Roman-numeral filter accepted.
set +e
"${RUN}" --phase IV >"${WORK}/p4.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--phase IV accepted" || ko "roman numeral rejected"
grep -q "Phase IV" "${WORK}/p4.out" \
  && ok "roman numeral resolves correctly" || ko "wrong phase emitted"

# ---- JSON output ----
set +e
"${RUN}" --phase 1 --json >"${WORK}/p1.json" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--json --phase 1 rc=0" || ko "json mode failed"
python3 -c "
import json,sys
d = json.load(open('${WORK}/p1.json'))
assert d['mode'] == 'dry-run', d['mode']
assert 'safety_note' in d
assert len(d['phases']) == 1, len(d['phases'])
p = d['phases'][0]
assert p['phase'] == 'I'
assert p['would_invoke'] == len(p['plan'])
assert p['artifacts_missing'] == 0
for art in p['plan']:
    assert art['status'] == 'present'
    assert art['kind'] in {'build-step','installer-hook','post-install-hook',
                           'recurrent-hook','systemd-unit','systemd-timer',
                           'tooling','config','other'}
print('JSON-OK')
" >"${WORK}/json.check" 2>&1 \
  && grep -q "JSON-OK" "${WORK}/json.check" \
  && ok "JSON shape conforms" \
  || ko "JSON shape failed: $(cat ${WORK}/json.check)"

# ---- R202: phases.sh + run.sh share canonical YAML loader ----
loader_count=$(python3 "${__REPO_ROOT}/scripts/bootstrap/lib/load-phases.py" | wc -l)
[ "${loader_count}" -eq 5 ] \
  && ok "YAML loader emits 5/5 phases (R202 canonical source)" \
  || ko "YAML loader phase count mismatch: ${loader_count}"
grep -q "load-phases.py" "${PHASES}" \
  && ok "phases.sh consumes the canonical loader" \
  || ko "phases.sh has stale inline phase table"
grep -q "load-phases.py" "${RUN}" \
  && ok "run.sh consumes the canonical loader" \
  || ko "run.sh has stale inline phase table"

# ---- osctl bridge invokes run.sh ----
set +e
"${OSCTL}" bootstrap run --phase 2 >"${WORK}/osctl-p2.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl bootstrap run --phase 2 rc=0" \
  || ko "osctl bridge failed: $(tail -5 ${WORK}/osctl-p2.out)"
grep -q "Phase II — execution plan" "${WORK}/osctl-p2.out" \
  && ok "osctl bridge surfaces Phase II output" \
  || ko "osctl bridge output unexpected"

# ---- missing artifact propagates rc=1 ----
# Stash a Phase-I artifact, rerun, expect rc=1.
mv "${__REPO_ROOT}/config/preseed/sain-01.preseed.example.cfg" \
   "${WORK}/sain-01.preseed.example.cfg"
set +e
"${RUN}" --phase 1 >"${WORK}/miss.out" 2>&1
rc=$?
set -e
mv "${WORK}/sain-01.preseed.example.cfg" \
   "${__REPO_ROOT}/config/preseed/sain-01.preseed.example.cfg"
[ "${rc}" -eq 1 ] && ok "missing artifact → rc=1" \
  || ko "expected rc=1 on missing artifact, got ${rc}"
grep -q "MISSING" "${WORK}/miss.out" \
  && ok "MISSING marker surfaces in plan" \
  || ko "MISSING marker absent"

echo
total=$((pass + fail))
echo "test_bootstrap_run: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
