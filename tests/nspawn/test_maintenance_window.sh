#!/usr/bin/env bash
# R323 (E2.M19) — maintenance-window scheduler L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/lifecycle/maintenance-window.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + 3 default windows ──────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R323'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M19'
assert d['total_count'] == 3
" || fail "envelope"
pass "1. list --json envelope + 3 default windows"

# ── 2. 3 operator-named windows present ────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {w['name'] for w in d['windows']}
must = {'daily-light-touch', 'weekly-deep-maintenance', 'operator-on-call-only'}
assert names == must, names
" || fail "names"
pass "2. 3 named windows (daily-light-touch / weekly-deep / operator-on-call)"

# ── 3. Every window has full schema ────────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for w in d['windows']:
    for k in ('name', 'axis', 'schedule', 'days', 'start', 'end',
              'timezone', 'description'):
        assert k in w, (k, w)
    assert isinstance(w['days'], list)
    # start/end are HH:MM
    for k in ('start', 'end'):
        h, m = w[k].split(':')
        assert 0 <= int(h) <= 23
        assert 0 <= int(m) <= 59
" || fail "schema"
pass "3. every window has full schema (name/axis/schedule/days/start/end/tz)"

# ── 4. is_active() unit tests ──────────────────────────────
python3 -c "
import datetime as dt, importlib.util
spec = importlib.util.spec_from_file_location('m', 'scripts/lifecycle/maintenance-window.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

w = {'days': ['daily'], 'start': '02:00', 'end': '04:00', 'timezone': 'UTC'}
# Inside window
now = dt.datetime(2026, 5, 18, 3, 0, tzinfo=dt.timezone.utc)
assert m.is_active(w, now), 'expected active at 03:00 UTC'
# Outside window
now2 = dt.datetime(2026, 5, 18, 10, 0, tzinfo=dt.timezone.utc)
assert not m.is_active(w, now2), 'expected inactive at 10:00 UTC'

# Day-specific window
w_tue = {'days': ['Tue'], 'start': '02:00', 'end': '04:00', 'timezone': 'UTC'}
tue = dt.datetime(2026, 5, 19, 3, 0, tzinfo=dt.timezone.utc)  # Tue
wed = dt.datetime(2026, 5, 20, 3, 0, tzinfo=dt.timezone.utc)  # Wed
assert m.is_active(w_tue, tue), 'Tue 03:00 should match Tue-only window'
assert not m.is_active(w_tue, wed), 'Wed 03:00 should NOT match Tue-only window'
print('PASS')
" || fail "is_active unit"
pass "4. is_active() handles daily / day-specific / inside / outside window"

# ── 5. Cross-midnight window support ────────────────────────
python3 -c "
import datetime as dt, importlib.util
spec = importlib.util.spec_from_file_location('m', 'scripts/lifecycle/maintenance-window.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Window crossing midnight: 23:00 → 02:00
w = {'days': ['daily'], 'start': '23:00', 'end': '02:00', 'timezone': 'UTC'}
# 23:30 → inside
n1 = dt.datetime(2026, 5, 18, 23, 30, tzinfo=dt.timezone.utc)
assert m.is_active(w, n1), '23:30 should be inside 23:00-02:00 wrap'
# 01:00 → inside (next day morning)
n2 = dt.datetime(2026, 5, 18, 1, 0, tzinfo=dt.timezone.utc)
assert m.is_active(w, n2), '01:00 should be inside 23:00-02:00 wrap'
# 12:00 → outside
n3 = dt.datetime(2026, 5, 18, 12, 0, tzinfo=dt.timezone.utc)
assert not m.is_active(w, n3), '12:00 should be outside 23:00-02:00 wrap'
print('PASS')
" || fail "cross midnight"
pass "5. is_active() supports cross-midnight windows (23:00-02:00 wraps)"

# ── 6. show <window> renders detail ────────────────────────
out_s="$(python3 "${SCRIPT}" show weekly-deep-maintenance --json)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
w = d['window']
assert w['name'] == 'weekly-deep-maintenance'
assert 'Tue' in w['days']
assert w['start'] == '02:00'
assert 'active_now' in d
" || fail "show shape"
pass "6. show weekly-deep-maintenance renders detail + active_now bool"

# ── 7. can-run-now returns rc=0/1 based on current time ────
RC=0
python3 "${SCRIPT}" can-run-now daily-light-touch --json >/dev/null || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "can-run-now rc invalid: ${RC}"
pass "7. can-run-now returns rc=0 (active) OR rc=1 (outside-window)"

# ── 8. Unknown window → rc=2 + structured error ────────────
RC=0
python3 "${SCRIPT}" can-run-now no-such-window --json 2>/dev/null || RC=$?
[[ "${RC}" == "2" ]] || fail "expected rc=2 unknown; got ${RC}"
pass "8. can-run-now unknown window → rc=2 + structured error"

# ── 9. Operator overlay replaces window catalog ──────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[windows]]
name        = "operator-custom-window"
axis        = "test"
schedule    = "daily 00:00-23:59 UTC"
days        = ["daily"]
start       = "00:00"
end         = "23:59"
timezone    = "UTC"
description = "always-active operator fixture"
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [w['name'] for w in d['windows']]
assert names == ['operator-custom-window'], names
" || fail "overlay replace"
# can-run-now with always-active window → rc=0
RC=0
python3 "${SCRIPT}" can-run-now operator-custom-window --config "${overlay}" --json >/dev/null || RC=$?
[[ "${RC}" == "0" ]] || fail "always-active window should give rc=0; got ${RC}"
rm -f "${overlay}"
pass "9. operator overlay (R283/SDD-030) replaces catalog + always-active window → rc=0"

# ── 10. sovereign-osctl maintenance-window dispatch ────────
out_disp="$(bash "${OSCTL}" maintenance-window list --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R323'
" || fail "osctl dispatch"
pass "10. sovereign-osctl maintenance-window dispatches"

echo "ALL OK"
