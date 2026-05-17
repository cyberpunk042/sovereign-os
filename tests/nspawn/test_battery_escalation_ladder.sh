#!/usr/bin/env bash
# R302 (E1.M27) — UPS battery escalation ladder L3.
#
# Operator-named (§1b mandate row): "the PSU/APC integration with the
# power mangement and the scheduled shutdown when battery reach a
# certain point as one default profile. (schedule/planifest/graceful
# on all levels, orderly)".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/power/battery-escalation-ladder.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope ────────────────────────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R302'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M27'
assert d['step_count'] == 5
" || fail "envelope"
pass "1. list --json envelope (5 default steps)"

# ── 2. Operator-named 5 steps all present in order ──────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [s['step'] for s in d['steps']]
assert names == ['pre-alert', 'warn-watch', 'drain-infer',
                  'drain-all', 'hard-shutdown'], names
" || fail "step order/names"
pass "2. ladder order: pre-alert → warn-watch → drain-infer → drain-all → hard-shutdown"

# ── 3. Each step has full schema ────────────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for s in d['steps']:
    for k in ('step', 'remaining_minutes_min', 'remaining_minutes_max',
              'severity', 'summary', 'commands'):
        assert k in s, (k, s)
    assert isinstance(s['commands'], list) and s['commands']
    assert s['severity'] in ('info', 'warn', 'action', 'urgent', 'critical')
" || fail "step shape"
pass "3. every step has full schema + severity in {info, warn, action, urgent, critical}"

# ── 4. Ranges are contiguous + ordered ─────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
steps = d['steps']
# pre-alert covers [30, 999999)
# warn-watch covers [20, 30)
# drain-infer covers [10, 20)
# drain-all covers [5, 10)
# hard-shutdown covers [0, 5)
expected = [(30, 999999), (20, 30), (10, 20), (5, 10), (0, 5)]
got = [(s['remaining_minutes_min'], s['remaining_minutes_max']) for s in steps]
assert got == expected, got
" || fail "ranges"
pass "4. ranges form a contiguous descending ladder (30+ → 20-30 → 10-20 → 5-10 → 0-5)"

# ── 5. simulate resolves correct step per remaining-minutes ──
for case in "60:pre-alert" "25:warn-watch" "15:drain-infer" "7:drain-all" "3:hard-shutdown"; do
    rem="${case%%:*}"
    want="${case##*:}"
    out_s="$(python3 "${SCRIPT}" simulate --remaining-minutes "${rem}" --json)"
    got="$(echo "${out_s}" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['resolved_step']['step'])")"
    [[ "${got}" == "${want}" ]] || fail "remaining=${rem} → expected ${want}, got ${got}"
done
pass "5. simulate resolves correct step for each band (60/25/15/7/3 min)"

# ── 6. show <step> renders detail ───────────────────────────
out_show="$(python3 "${SCRIPT}" show drain-infer --json)"
echo "${out_show}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
s = d['step']
assert s['step'] == 'drain-infer'
assert s['severity'] == 'action'
assert any('slm-' in c for c in s['commands'])
assert any('oracle-' in c for c in s['commands'])
" || fail "show shape"
pass "6. show drain-infer → severity=action + drain slm-/oracle- prefixes"

# ── 7. Unknown step → rc=1 + structured error ───────────────
RC=0
python3 "${SCRIPT}" show no-such-step --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "expected rc=1; got ${RC}"
err="$(python3 "${SCRIPT}" show no-such-step --json 2>&1 1>/dev/null)" || true
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'unknown step' in d['error']
" || fail "unknown error shape"
pass "7. unknown step → rc=1 + structured error JSON"

# ── 8. Operator overlay replaces ladder ────────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[steps]]
step                   = "operator-custom"
remaining_minutes_min  = 0
remaining_minutes_max  = 999999
severity               = "info"
summary                = "operator-defined single-step ladder"
commands               = ["echo do-something"]
operator_note          = "test fixture"
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [s['step'] for s in d['steps']]
assert names == ['operator-custom'], names
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) replaces ladder entirely"

# ── 9. Malformed overlay → defaults + _parse_error ─────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" list --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['step_count'] == 5
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "9. malformed overlay → defaults + _parse_error"

# ── 10. simulate without --remaining-minutes degrades gracefully ──
out_probe="$(python3 "${SCRIPT}" simulate --json)"
echo "${out_probe}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R302'
assert d['simulate_mode'] is True
# Either probed a real value OR reported unavailable.
assert 'remaining_minutes' in d
assert 'source' in d
" || fail "probe-fallback"
pass "10. simulate without --remaining-minutes degrades gracefully"

# ── 11. sovereign-osctl battery-ladder dispatch + read-only ──
out_disp="$(bash "${OSCTL}" battery-ladder list --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R302'
" || fail "sovereign-osctl dispatch"
out2="$(python3 "${SCRIPT}" list --json)"
[[ "${out}" == "${out2}" ]] || fail "list output changed between calls"
pass "11. sovereign-osctl battery-ladder dispatch + read-only invariant"

echo "ALL OK"
