#!/usr/bin/env bash
# R313 (E1.M33) — PSU OC-mode orchestrator L3.
#
# Operator-named (§1b mandate row): "be Quiet! Dark Power Pro 13
# 1600W Power Supply ... My PSU even have an overclock mode which
# might be important".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/psu-oc-mode-orchestrator.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

mk_cfg() {
    local body="$1"
    local cfg
    cfg=$(mktemp --suffix=.toml)
    printf '%s\n' "${body}" > "${cfg}"
    echo "${cfg}"
}

# ── 1. status --json envelope ───────────────────────────────
out="$(python3 "${SCRIPT}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R313'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M33'
for k in ('config', 'psu', 'recommendation'):
    assert k in d, k
" || fail "envelope"
pass "1. status --json envelope"

# ── 2. Default PSU is Dark Power Pro 13 1600W ──────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['config']['psu_model'] == 'dark-power-pro-13-1600w'
psu = d['psu']
assert psu['display_name'] == 'be Quiet! Dark Power Pro 13 1600W'
assert psu['form_factor'] == 'ATX 3.1'
assert psu['efficiency_rating'] == '80 Plus Titanium'
assert psu['wattage_rated_w'] == 1600
assert psu['oc_switch_present'] is True
" || fail "default psu"
pass "2. default PSU = be Quiet! Dark Power Pro 13 1600W (ATX 3.1 Titanium)"

# ── 3. oc_mode=unknown → rc=1 + operator action message ────
RC=0
out="$(python3 "${SCRIPT}" status --json)" || RC=$?
[[ "${RC}" == "1" ]] || fail "expected rc=1 on oc_mode=unknown; got ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['recommendation']['verdict'] == 'oc-mode-undeclared'
assert 'operator_action' in d['recommendation']
" || fail "undeclared verdict"
pass "3. oc_mode=unknown → rc=1 + verdict='oc-mode-undeclared' + operator_action"

# ── 4. oc_mode=on unlocks higher multiplier ceiling ────────
cfg=$(mk_cfg 'oc_mode = "on"')
out_on="$(python3 "${SCRIPT}" status --config "${cfg}" --json)"
echo "${out_on}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r = d['recommendation']
assert r['verdict'] == 'oc-mode-on-headroom-unlocked'
assert r['rc'] == 0
# OC ON ceiling > OFF ceiling.
assert r['max_safe_oc_multiplier'] == 1.25, r
" || fail "oc on multiplier"
rm -f "${cfg}"
pass "4. oc_mode=on → verdict='oc-mode-on-headroom-unlocked' + 1.25x ceiling"

# ── 5. oc_mode=off → per-rail-active verdict + 1.10x ceiling ──
cfg=$(mk_cfg 'oc_mode = "off"')
out_off="$(python3 "${SCRIPT}" status --config "${cfg}" --json)"
echo "${out_off}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r = d['recommendation']
assert r['verdict'] == 'oc-mode-off-per-rail-active'
assert r['rc'] == 0
assert r['max_safe_oc_multiplier'] == 1.10, r
" || fail "oc off multiplier"
rm -f "${cfg}"
pass "5. oc_mode=off → verdict='oc-mode-off-per-rail-active' + 1.10x ceiling"

# ── 6. Dual-GPU + OC off triggers rail-assignment note ────
cfg=$(mk_cfg 'oc_mode = "off"
dual_gpu = true')
out_dg="$(python3 "${SCRIPT}" status --config "${cfg}" --json)"
echo "${out_dg}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
notes = d['recommendation'].get('additional_notes', [])
assert any('Cable' in n for n in notes), notes
" || fail "dual gpu notes"
rm -f "${cfg}"
pass "6. dual_gpu=true + oc_mode=off → rail-assignment note included"

# ── 7. recipe verb returns recipe steps + caveats ──────────
out_r="$(python3 "${SCRIPT}" recipe --json)"
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R313'
assert d['oc_switch_present'] is True
assert d['oc_switch_location'] and 'rear' in d['oc_switch_location'].lower()
assert isinstance(d['recipe_steps'], list) and len(d['recipe_steps']) >= 5
assert isinstance(d['operator_caveats'], list) and d['operator_caveats']
" || fail "recipe shape"
pass "7. recipe verb returns switch location + ≥5 steps + operator caveats"

# ── 8. Generic PSU fallback when unknown model declared ────
cfg=$(mk_cfg 'psu_model = "generic-multi-rail"
oc_mode = "off"')
out_g="$(python3 "${SCRIPT}" status --config "${cfg}" --json)"
echo "${out_g}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
psu = d['psu']
assert psu['display_name'].startswith('Generic')
assert psu['oc_switch_present'] is False
# Generic ceiling is 1.05 — most conservative.
assert d['recommendation']['max_safe_oc_multiplier'] == 1.05
" || fail "generic fallback"
rm -f "${cfg}"
pass "8. generic-multi-rail PSU fallback → no OC switch + 1.05x ceiling"

# ── 9. Malformed overlay → defaults + _parse_error ─────────
cfg=$(mk_cfg "this is not toml [[[[ }}}}")
out_bad="$(python3 "${SCRIPT}" status --config "${cfg}" --json || true)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['config']['oc_mode'] == 'unknown'
assert '_parse_error' in d['overlay']
" || fail "malformed overlay"
rm -f "${cfg}"
pass "9. malformed overlay → defaults + _parse_error"

# ── 10. sovereign-osctl psu-oc-mode dispatch ────────────────
out_disp="$(bash "${OSCTL}" psu-oc-mode status --json 2>/dev/null || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R313'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl psu-oc-mode dispatches"

echo "ALL OK"
