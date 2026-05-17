#!/usr/bin/env bash
# tests/nspawn/test_known_boards_toml.sh — R260 (SDD-029 R260).
# KNOWN_BOARDS table refactored from hardcoded dict → TOML registry.
# Operator-pull workflow: drop /etc/sovereign-os/known-boards.toml
# to add new board advisories without editing Python.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/bios-info.py"
EXAMPLE="${__REPO_ROOT}/config/known-boards.toml.example"

echo "tests/nspawn/test_known_boards_toml.sh"
echo

[ -f "${EXAMPLE}" ] && ok "config/known-boards.toml.example shipped" \
  || ko "missing example config"
grep -q "R260" "${SCRIPT}" && ok "bios-info.py cites R260" || ko "R260 missing"
grep -q "load_known_boards_from_toml" "${SCRIPT}" \
  && ok "bios-info.py has TOML loader" || ko "loader missing"
grep -q "merged_known_boards" "${SCRIPT}" \
  && ok "bios-info.py merges hardcoded + TOML" || ko "merge fn missing"

TMP="$(mktemp -d -t r260.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

# ---- TOML registry can add a brand-new board ----
cat > "${TMP}/boards.toml" <<'TOML'
[boards."TEST-OPERATOR-BOARD"]
match_id = "TEST-OPERATOR-BOARD"
vendor = "TestCorp"
chipset = "Test Z999"
socket = "test-socket"
memory_channels = 4
memory_max_speed_jedec_mts = 4800
memory_max_speed_exp_oc_mts = 8400
pcie_layout = [
    "SLOT_1: x16 PCIe 6.0",
    "SLOT_2: x8 PCIe 6.0",
]
advisories = [
    "Enable test-mode in BIOS.",
    "Test board needs firmware 0.1 minimum.",
    "Test optimization knob #3.",
]
TOML

python3 -c "
import importlib.util, os
os.environ['SOVEREIGN_OS_KNOWN_BOARDS'] = '${TMP}/boards.toml'
spec = importlib.util.spec_from_file_location('bi','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
merged = m.merged_known_boards()
assert 'TEST-OPERATOR-BOARD' in merged, list(merged.keys())
b = merged['TEST-OPERATOR-BOARD']
assert b['vendor'] == 'TestCorp', b
assert b['chipset'] == 'Test Z999', b
assert b['memory_channels'] == 4, b
assert b['memory_max_speed_jedec'] == 4800, b
assert b['memory_max_speed_exp_oc'] == 8400, b
assert len(b['advisories']) == 3, b
# pcie_layout is parsed from string list → dict
assert b['pcie_layout']['SLOT_1'] == 'x16 PCIe 6.0', b
" \
  && ok "TOML can add a new board (parsed: name + meta + pcie_layout dict + advisories)" \
  || ko "TOML load shape wrong"

# ---- Hardcoded baseline still present when TOML adds new entries ----
python3 -c "
import importlib.util, os
os.environ['SOVEREIGN_OS_KNOWN_BOARDS'] = '${TMP}/boards.toml'
spec = importlib.util.spec_from_file_location('bi','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
merged = m.merged_known_boards()
# Original ASUS entry STILL in merged result.
assert 'ProArt X870E-CREATOR WIFI' in merged, list(merged.keys())
" \
  && ok "merge preserves hardcoded ASUS X870E baseline" \
  || ko "hardcoded baseline lost"

# ---- TOML can OVERRIDE the hardcoded entry ----
cat > "${TMP}/override.toml" <<'TOML'
[boards."ProArt X870E-CREATOR WIFI"]
match_id = "ProArt X870E-CREATOR WIFI"
vendor = "ASUSTeK COMPUTER INC."
chipset = "AMD X870E"
socket = "AM5"
memory_channels = 2
memory_max_speed_jedec_mts = 5600
memory_max_speed_exp_oc_mts = 8000
pcie_layout = []
advisories = ["OVERRIDE: only this advisory should land"]
TOML
python3 -c "
import importlib.util, os
os.environ['SOVEREIGN_OS_KNOWN_BOARDS'] = '${TMP}/override.toml'
spec = importlib.util.spec_from_file_location('bi','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
merged = m.merged_known_boards()
adv = merged['ProArt X870E-CREATOR WIFI']['advisories']
assert len(adv) == 1, adv
assert 'OVERRIDE' in adv[0], adv
" \
  && ok "TOML entry OVERRIDES hardcoded entry (operator-pull wins)" \
  || ko "TOML override didn't apply"

# ---- Missing TOML file = hardcoded baseline still works ----
python3 -c "
import importlib.util, os
os.environ['SOVEREIGN_OS_KNOWN_BOARDS'] = '/no-such-file'
spec = importlib.util.spec_from_file_location('bi','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Missing env-pointed file falls through to dev example
merged = m.merged_known_boards()
assert 'ProArt X870E-CREATOR WIFI' in merged
" \
  && ok "missing TOML path → hardcoded baseline (graceful)" \
  || ko "missing TOML broke baseline"

# ---- Malformed TOML = silent fallback to hardcoded ----
cat > "${TMP}/broken.toml" <<'TOML'
this is not valid toml [[[ ]] }} {{
TOML
python3 -c "
import importlib.util, os
os.environ['SOVEREIGN_OS_KNOWN_BOARDS'] = '${TMP}/broken.toml'
spec = importlib.util.spec_from_file_location('bi','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
merged = m.merged_known_boards()
# Hardcoded baseline still present.
assert 'ProArt X870E-CREATOR WIFI' in merged
" \
  && ok "malformed TOML → silent fallback to hardcoded" \
  || ko "malformed TOML broke baseline"

# ---- derive_advisories picks up TOML entry ----
python3 -c "
import importlib.util, os
os.environ['SOVEREIGN_OS_KNOWN_BOARDS'] = '${TMP}/boards.toml'
spec = importlib.util.spec_from_file_location('bi','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
adv = m.derive_advisories({'product': 'TEST-OPERATOR-BOARD'})
assert adv['matched_board'] == 'TEST-OPERATOR-BOARD', adv
assert len(adv['advisories']) == 3, adv
assert adv['board_meta']['vendor'] == 'TestCorp', adv
" \
  && ok "derive_advisories surfaces TOML-added board" \
  || ko "derive_advisories missed TOML entry"

# ---- Example config is parseable ----
python3 -c "
import tomllib
with open('${EXAMPLE}', 'rb') as f:
    doc = tomllib.load(f)
assert 'boards' in doc, doc
assert 'ProArt X870E-CREATOR WIFI' in doc['boards'], list(doc['boards'].keys())
b = doc['boards']['ProArt X870E-CREATOR WIFI']
assert len(b['advisories']) >= 5, b['advisories']
" \
  && ok "example config parses + carries ASUS X870E with ≥5 advisories" \
  || ko "example config malformed"

# ---- end-to-end via subprocess: bios-info advisories --json runs without crash
#      regardless of TOML presence (live CI has no real baseboard match) ----
set +e
SOVEREIGN_OS_KNOWN_BOARDS="${TMP}/boards.toml" \
  python3 "${SCRIPT}" advisories --json > "${TMP}/adv.json" 2>/dev/null
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "end-to-end: advisories --json rc=0 with TOML override env" \
  || ko "end-to-end advisories rc=${rc}"

echo
total=$((pass + fail))
echo "test_known_boards_toml: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
