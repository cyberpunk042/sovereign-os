#!/usr/bin/env bash
# tests/nspawn/test_psu_overclock.sh — R259 (SDD-026 Z-18 / SDD-029 R259).
# PSU overclock mode lifts the sustained budget when operator-enabled.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/power-status.py"

echo "tests/nspawn/test_psu_overclock.sh"
echo

grep -q "R259" "${SCRIPT}" && ok "power-status.py cites R259" || ko "R259 ref missing"

TMP=$(mktemp -d -t r259.XXXXXX)
trap 'rm -rf "${TMP}"' EXIT

# Test fixture: OC supported but DISABLED.
cat > "${TMP}/oc-off.toml" <<'TOML'
derating = 0.85
estimated_overhead_watts = 75
[psu]
model = "test"
rated_watts = 1600
overclock_mode_supported = true
overclock_mode_enabled = false
overclock_multiplier = 1.10
[cpu]
tdp_watts = 170
[graceful_shutdown]
battery_critical_pct = 15
runtime_warn_minutes = 5
shutdown_minutes = 2
TOML

set +e
out="$(SOVEREIGN_OS_POWER_CONFIG=${TMP}/oc-off.toml python3 "${SCRIPT}" budget --json)"
set -e
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
oc = d['psu_overclock']
assert oc['supported'] is True, oc
assert oc['enabled'] is False, oc
assert oc['active'] is False, oc
assert oc['multiplier'] == 1.10, oc
assert oc['effective_rated_watts'] is None, oc
# 1600 W × 0.85 = 1360 W (no OC lift)
assert d['psu_sustained_budget_watts'] == 1360.0, d
"  \
  && ok "OC off: budget = rated × derating = 1360 W (no OC lift)" \
  || ko "OC off path wrong"

# Test fixture: OC enabled.
cat > "${TMP}/oc-on.toml" <<'TOML'
derating = 0.85
estimated_overhead_watts = 75
[psu]
model = "test"
rated_watts = 1600
overclock_mode_supported = true
overclock_mode_enabled = true
overclock_multiplier = 1.10
[cpu]
tdp_watts = 170
[graceful_shutdown]
battery_critical_pct = 15
runtime_warn_minutes = 5
shutdown_minutes = 2
TOML

set +e
out="$(SOVEREIGN_OS_POWER_CONFIG=${TMP}/oc-on.toml python3 "${SCRIPT}" budget --json)"
set -e
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
oc = d['psu_overclock']
assert oc['supported'] is True, oc
assert oc['enabled'] is True, oc
assert oc['active'] is True, oc
# 1600 × 1.10 = 1760 effective; 1760 × 0.85 = 1496 W budget.
assert abs(oc['effective_rated_watts'] - 1760.0) < 0.1, oc
assert abs(d['psu_sustained_budget_watts'] - 1496.0) < 0.1, d
"  \
  && ok "OC on: budget = rated × 1.10 × derating = 1496 W" \
  || ko "OC on path wrong"

# Test fixture: OC supported, disabled, BUT host is utilizing ≥70%.
# Expect a warning telling operator to flip the OC switch.
cat > "${TMP}/oc-suggest.toml" <<'TOML'
derating = 0.85
estimated_overhead_watts = 50
[psu]
model = "test"
rated_watts = 500
overclock_mode_supported = true
overclock_mode_enabled = false
overclock_multiplier = 1.20
[cpu]
tdp_watts = 250
[graceful_shutdown]
battery_critical_pct = 15
runtime_warn_minutes = 5
shutdown_minutes = 2
TOML
set +e
out="$(SOVEREIGN_OS_POWER_CONFIG=${TMP}/oc-suggest.toml python3 "${SCRIPT}" budget --json)"
set -e
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
# 250 + 50 = 300 W load / (500 * 0.85 = 425) = 70.6% utilization.
assert d['utilization_pct'] >= 70, d
assert any('overclock mode but it is DISABLED' in w for w in d['warnings']), d
assert any('20%' in w for w in d['warnings']), d  # multiplier 1.20 → 20% lift
"  \
  && ok "OC disabled + ≥70% util → suggest-enable warning with %-lift" \
  || ko "OC-suggest warning missing"

# Test fixture: OC NOT supported. No warning even at high utilization.
cat > "${TMP}/no-oc.toml" <<'TOML'
derating = 0.85
estimated_overhead_watts = 50
[psu]
model = "test"
rated_watts = 500
overclock_mode_supported = false
[cpu]
tdp_watts = 250
[graceful_shutdown]
battery_critical_pct = 15
runtime_warn_minutes = 5
shutdown_minutes = 2
TOML
set +e
out="$(SOVEREIGN_OS_POWER_CONFIG=${TMP}/no-oc.toml python3 "${SCRIPT}" budget --json)"
set -e
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
oc = d['psu_overclock']
assert oc['supported'] is False, oc
assert oc['multiplier'] is None, oc
# No OC-suggest warning when OC not supported.
assert not any('overclock mode but it is DISABLED' in w for w in d.get('warnings', [])), d
"  \
  && ok "OC not supported: no 'enable OC' warning emitted" \
  || ko "incorrectly emitted OC warning when not supported"

# Example config seeds overclock_multiplier
grep -q "overclock_multiplier" "${__REPO_ROOT}/config/power.toml.example" \
  && ok "config/power.toml.example documents overclock_multiplier" \
  || ko "example config missing multiplier knob"

# psu --json still surfaces overclock_mode_supported + enabled
set +e
out="$(SOVEREIGN_OS_POWER_CONFIG=${TMP}/oc-on.toml python3 "${SCRIPT}" psu --json)"
set -e
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
psu = d['psu']
assert psu['overclock_mode_supported'] is True, psu
assert psu['overclock_mode_enabled'] is True, psu
"  \
  && ok "psu --json surfaces overclock_mode_supported + enabled" \
  || ko "psu --json missing OC flags"

echo
total=$((pass + fail))
echo "test_psu_overclock: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
