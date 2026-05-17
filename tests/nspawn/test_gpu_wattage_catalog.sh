#!/usr/bin/env bash
# R303 (E1.M28) — GPU per-card per-mode wattage catalog L3.
#
# Operator-named (§1b mandate row): "GPU too, watts, RTX 3090 details
# and possibilities established and non-established, same for the
# RTX Pro 6000".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/gpu-wattage-catalog.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope ────────────────────────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R303'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M28'
assert d['total_count'] == 8  # 4 modes × 2 cards
" || fail "envelope"
pass "1. list --json envelope (8 default entries = 4 modes × 2 cards)"

# ── 2. Both operator cards × 4 modes covered ───────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cards = set(d['cards'])
assert cards == {'RTX 3090', 'RTX PRO 6000'}, cards
# Per card: idle / typical-inference / peak-training / oc-peak.
by_card_modes = {}
for e in d['entries']:
    by_card_modes.setdefault(e['card'], set()).add(e['mode'])
for c in ('RTX 3090', 'RTX PRO 6000'):
    assert by_card_modes[c] == {'idle', 'typical-inference',
                                 'peak-training', 'oc-peak'}, (c, by_card_modes[c])
" || fail "cards × modes coverage"
pass "2. RTX 3090 + RTX PRO 6000 each have idle/typical-inference/peak-training/oc-peak"

# ── 3. Wattage monotonic per card (idle < typical < peak < oc) ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
order = ['idle', 'typical-inference', 'peak-training', 'oc-peak']
for c in ('RTX 3090', 'RTX PRO 6000'):
    by_mode = {e['mode']: e['watts'] for e in d['entries'] if e['card'] == c}
    watts = [by_mode[m] for m in order]
    assert watts == sorted(watts), (c, watts)
" || fail "monotonic wattage"
pass "3. wattage strictly increases idle → typical → peak → oc-peak per card"

# ── 4. Each entry has full shape (card/mode/watts/source/note) ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for e in d['entries']:
    for k in ('card', 'mode', 'watts', 'source', 'operator_note'):
        assert k in e, (k, e)
    assert isinstance(e['watts'], int)
" || fail "entry shape"
pass "4. every entry has card / mode / watts / source / operator_note"

# ── 5. show <card> <mode> renders specific entry ────────────
out_show="$(python3 "${SCRIPT}" show 'RTX PRO 6000' oc-peak --json)"
echo "${out_show}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
e = d['entry']
assert e['card'] == 'RTX PRO 6000'
assert e['mode'] == 'oc-peak'
assert e['watts'] == 720
" || fail "show"
pass "5. show 'RTX PRO 6000' oc-peak → 720 W"

# ── 6. --card filter narrows ──────────────────────────────────
out_3090="$(python3 "${SCRIPT}" list --card 'RTX 3090' --json)"
echo "${out_3090}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for e in d['entries']:
    assert e['card'] == 'RTX 3090', e
assert d['filtered_count'] == 4
" || fail "card filter"
pass "6. --card 'RTX 3090' filter narrows to 4 entries"

# ── 7. budget verb sums + emits verdict ────────────────────
out_b="$(python3 "${SCRIPT}" budget --json)"
echo "${out_b}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Default modes = typical-inference for both.
# RTX 3090 typical = 220 W; PRO 6000 typical = 380 W
assert d['rtx_3090']['watts'] == 220
assert d['rtx_pro_6000']['watts'] == 380
assert d['gpu_total_watts'] == 600
assert d['projected_total_watts'] == 600 + 170 + 80  # + cpu + chassis
assert d['psu_rated_watts'] == 1600
assert d['verdict'] == 'headroom-safe'
" || fail "budget"
pass "7. budget verb sums GPU+CPU+chassis vs PSU + emits verdict"

# ── 8. budget verdict shifts to tight when OC peak ──────────
out_oc="$(python3 "${SCRIPT}" budget --mode-3090 oc-peak --mode-pro6000 oc-peak --json)"
echo "${out_oc}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# 420 + 720 + 170 + 80 = 1390; psu = 1600; headroom = 210; pct = 13.1%
assert d['psu_headroom_watts'] == 210, d
assert d['verdict'] == 'headroom-tight', d
" || fail "oc-peak budget"
pass "8. budget oc-peak/oc-peak → headroom-tight (210 W headroom, 13.1%)"

# ── 9. Operator overlay replaces catalog ────────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[entries]]
card    = "Operator-Custom-GPU"
mode    = "idle"
watts   = 10
source  = "operator test entry"
operator_note = "test fixture"
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['cards'] == ['Operator-Custom-GPU'], d['cards']
assert d['total_count'] == 1
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "9. operator overlay (R283/SDD-030) replaces catalog"

# ── 10. Unknown card / mode → rc=1 + structured error ──────
RC=0
python3 "${SCRIPT}" show 'no-such-card' idle --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "expected rc=1; got ${RC}"
err="$(python3 "${SCRIPT}" show 'RTX 3090' no-such-mode --json 2>&1 1>/dev/null)" || true
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'no entry' in d['error']
assert 'known_modes_for_card' in d
" || fail "unknown error shape"
pass "10. unknown card / mode → rc=1 + structured error"

# ── 11. sovereign-osctl gpu-wattage dispatch ──────────────
out_disp="$(bash "${OSCTL}" gpu-wattage list --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R303'
" || fail "sovereign-osctl dispatch"
pass "11. sovereign-osctl gpu-wattage dispatches"

echo "ALL OK"
