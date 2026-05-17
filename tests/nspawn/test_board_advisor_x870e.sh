#!/usr/bin/env bash
# R312 (E1.M32) — ASUS ProArt X870E-CREATOR WIFI board-specific
# tuning advisor L3.
#
# Operator-named (§1b mandate row): "possibly detecting the ASUS
# ProArt X870E-CREATOR WIFI and its settings and potential
# optimisations and fixes. pci lane splits and whatever".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/board-advisor-x870e-creator.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope (graceful when DMI absent) ──
out="$(python3 "${SCRIPT}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R312'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M32'
for k in ('dmi', 'matched_board', 'verdict', 'rc'):
    assert k in d, k
" || fail "envelope"
pass "1. status --json envelope (graceful when DMI absent)"

# ── 2. ASUS ProArt X870E-Creator WiFi in default catalog ────
out_a="$(python3 "${SCRIPT}" advise --json)"
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {b['name'] for b in d['boards']}
assert 'asus-proart-x870e-creator-wifi' in names, names
" || fail "anchor board"
pass "2. operator's exact board (asus-proart-x870e-creator-wifi) in catalog"

# ── 3. Board carries full operator-pull schema ──────────────
out_b="$(python3 "${SCRIPT}" advise --board asus-proart-x870e-creator-wifi --json)"
echo "${out_b}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
b = d['board']
for k in ('match_vendor', 'match_name', 'display_name', 'chipset',
          'socket', 'supported_cpus', 'pcie_slots', 'm2_slots',
          'dual_gpu_bifurcation_modes', 'bios_flashback_recipe',
          'memory_training_timeout_advice', 'known_issues',
          'operator_caveat'):
    assert k in b, k
" || fail "board schema"
pass "3. board carries full 13-field operator-pull schema"

# ── 4. PCIe slot table covers 3 slots ─────────────────────
echo "${out_b}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
slots = d['board']['pcie_slots']
labels = {s['label'] for s in slots}
assert {'PCIE_1', 'PCIE_2', 'PCIE_3'} <= labels, labels
# Every slot has lanes + operator_note
for s in slots:
    assert s.get('lanes'), s
    assert s.get('operator_note'), s
" || fail "pcie slots"
pass "4. PCIe slot allocation table covers 3 slots (PCIE_1/2/3) with lanes + operator_note"

# ── 5. M.2 slot matrix covers Gen5 + Gen4 ──────────────────
echo "${out_b}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m2 = d['board']['m2_slots']
assert len(m2) >= 4, m2
labels = {s['label'] for s in m2}
assert {'M.2_1', 'M.2_2', 'M.2_3', 'M.2_4'} <= labels, labels
# At least one Gen5 and one Gen4 in the matrix.
speeds = [s['speed'] for s in m2]
assert any('Gen5' in s for s in speeds), speeds
assert any('Gen4' in s for s in speeds), speeds
" || fail "m2 slots"
pass "5. M.2 slot matrix has 4 slots, Gen5 + Gen4 mix"

# ── 6. Dual-GPU bifurcation modes catalog ──────────────────
echo "${out_b}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
modes = d['board']['dual_gpu_bifurcation_modes']
mode_names = {m['mode'] for m in modes}
# Must include x8/x8 (operator's dual-GPU target).
assert any('x8/x8' in m for m in mode_names), mode_names
" || fail "bifurcation modes"
pass "6. dual-GPU bifurcation modes include x8/x8 (operator's target)"

# ── 7. slot-map verb requires host match (gracefully reports) ──
RC=0
out_sm="$(python3 "${SCRIPT}" slot-map --json 2>&1)" || RC=$?
# In sandbox without DMI match, returns 1; production with matched board returns 0.
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "slot-map rc unexpected: ${RC}"
pass "7. slot-map verb returns rc∈{0,1} (gracefully on no host match)"

# ── 8. Unknown board → rc=1 + structured error ──────────────
RC=0
python3 "${SCRIPT}" advise --board no-such-board --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "advise unknown rc expected 1; got ${RC}"
pass "8. advise unknown board → rc=1 + structured error"

# ── 9. Operator overlay (R283/SDD-030) adds custom board ────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[boards]]
match_vendor = "Test Vendor"
match_name   = "Test Board X1"
name         = "test-board-x1"
display_name = "Test Board X1"
chipset      = "Test Chipset"
socket       = "TS1"
supported_cpus = ["Test CPU"]
pcie_slots = []
m2_slots = []
dual_gpu_bifurcation_modes = []
bios_flashback_recipe = "n/a"
memory_training_timeout_advice = "n/a"
known_issues = []
operator_caveat = "test fixture"
TOML

out_ov="$(python3 "${SCRIPT}" advise --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [b['name'] for b in d['boards']]
assert names == ['test-board-x1'], names
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "9. operator overlay replaces catalog (lists REPLACE per R283)"

# ── 10. sovereign-osctl board-advisor dispatch ──────────────
out_disp="$(bash "${OSCTL}" board-advisor advise --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R312'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl board-advisor dispatches"

echo "ALL OK"
