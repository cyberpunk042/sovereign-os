#!/usr/bin/env bash
# tests/nspawn/test_power_status.sh — R252 (SDD-026 Z-18).
# PSU + UPS + wattage budget + graceful-shutdown advisories.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/power-status.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
EXAMPLE="${__REPO_ROOT}/config/power.toml.example"

echo "tests/nspawn/test_power_status.sh"
echo

[ -x "${SCRIPT}" ] && ok "power-status.py executable" \
  || { ko "missing power-status.py"; exit 1; }
[ -f "${EXAMPLE}" ] && ok "config/power.toml.example shipped" \
  || ko "example config missing"
grep -q "R252" "${SCRIPT}" && ok "power-status.py cites R252" || ko "R252 missing"
grep -q "be Quiet" "${EXAMPLE}" \
  && ok "example config seeds operator-named be Quiet! PSU" \
  || ko "PSU model missing"
grep -q "1600" "${EXAMPLE}" \
  && ok "example config seeds operator-named 1600W rating" \
  || ko "wattage missing"
grep -q "^  power-status)" "${OSCTL}" \
  && ok "osctl bridges 'power-status'" || ko "osctl dispatch missing"
grep -q "power-status psu" "${OSCTL}" \
  && ok "osctl help documents 'power-status'" || ko "osctl help missing"

TMP="$(mktemp -d -t r252.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

# ---- psu --json: returns operator-declared PSU + computed budget ----
out="$(python3 "${SCRIPT}" psu --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R252', d
assert d['vector'].startswith('SDD-026 Z-18'), d
assert d['psu']['rated_watts']==1600, d
assert d['psu']['atx_revision']=='3.1', d
assert d['derating_factor']==0.85, d
assert d['sustained_budget_watts']==1360.0, d
" \
  && ok "psu --json: 1600W rated × 0.85 = 1360W budget" \
  || ko "psu shape wrong"

# ---- budget --json: aggregates GPU + CPU + overhead ----
out="$(python3 "${SCRIPT}" budget --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R252', d
for k in ('psu_rated_watts','psu_sustained_budget_watts','components',
         'estimated_load_watts','headroom_watts','utilization_pct','warnings'):
    assert k in d, f'missing {k}'
# CPU TDP from operator-declared example = 170W
assert d['components']['cpu_tdp_watts_declared']==170, d
" \
  && ok "budget --json: components + headroom + utilization shape" \
  || ko "budget shape wrong"

# ---- isolated config: high utilization triggers warning ----
cat > "${TMP}/high.toml" <<'TOML'
derating = 0.85
estimated_overhead_watts = 200
[psu]
model = "test-low-budget"
rated_watts = 500
rating = "test"
[cpu]
tdp_watts = 250
[graceful_shutdown]
battery_critical_pct = 15
runtime_warn_minutes = 5
shutdown_minutes = 2
TOML
out="$(SOVEREIGN_OS_POWER_CONFIG=${TMP}/high.toml python3 "${SCRIPT}" budget --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
# 250 (CPU) + 200 (overhead) + 0 GPU = 450W out of 425W budget (500×0.85) → over
assert d['utilization_pct']>=100, d
assert any('EXCEEDS' in w for w in d['warnings']), d
" \
  && ok "budget: ≥100% utilization → warning emitted" \
  || ko "high-load warning missing"

# ---- ups --json: no UPS path is graceful ----
out="$(python3 "${SCRIPT}" ups --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R252', d
assert 'detected' in d
# CI runners don't have UPS so detected=false expected.
assert d['detected'] in (True, False)
" \
  && ok "ups --json: stable shape (detected boolean)" \
  || ko "ups shape wrong"

# ---- advisories --json: no-ups verdict ----
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R252', d
assert 'thresholds' in d
assert d['thresholds']['battery_critical_pct']==15.0, d
assert d['thresholds']['runtime_warn_minutes']==5.0, d
assert d['thresholds']['shutdown_minutes']==2.0, d
# When no UPS: verdict is no-ups.
if not d['ups_present']:
    assert d['verdict']=='no-ups', d
" \
  && ok "advisories --json: thresholds + no-ups verdict" \
  || ko "advisories shape wrong"

# ---- human render: psu banner + budget banner ----
out_h="$(python3 "${SCRIPT}" psu)"
echo "${out_h}" | grep -q "R252 sovereign-os power-status psu" \
  && ok "psu human banner present" || ko "psu banner missing"
echo "${out_h}" | grep -q "be Quiet" \
  && ok "psu human shows operator-declared model" || ko "model missing"

out_h="$(python3 "${SCRIPT}" budget)"
echo "${out_h}" | grep -q "R252 sovereign-os power-status budget" \
  && ok "budget human banner present" || ko "budget banner missing"

# ---- osctl bridge ----
set +e
"${OSCTL}" power-status psu --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl power-status psu rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R252', d
" \
  && ok "osctl bridge surfaces R252 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" power-status nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown power-status subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_power_status: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
