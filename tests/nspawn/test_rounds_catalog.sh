#!/usr/bin/env bash
# R321 (E9.M9) — rounds catalog L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/intelligence/rounds-catalog.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + ≥100 rounds ─────────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R321'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E9.M9'
# After this round, ≥100 rounds in mandate.
assert d['round_count'] >= 100, d['round_count']
" || fail "envelope"
pass "1. list --json envelope + ≥100 rounds discovered"

# ── 2. Every round entry has full shape ────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for r in d['rounds']:
    for k in ('round', 'module', 'epic', 'title', 'status'):
        assert k in r, (k, r)
    # Round IDs match expected patterns.
    assert r['round'].startswith('R') or r['round'].startswith('SD-R'), r['round']
    # Epic matches E<digit>.
    assert r['epic'].startswith('E')
" || fail "shape"
pass "2. every round entry has full shape (round/module/epic/title/status)"

# ── 3. show <round> finds existing rounds ──────────────────
out_s="$(python3 "${SCRIPT}" show R317 --json)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R321'
assert d['queried'] == 'R317'
assert len(d['matches']) >= 1
m = d['matches'][0]
assert m['module'] == 'E1.M37'
assert 'inventory' in m['title'].lower()
" || fail "show R317"
pass "3. show R317 → matches E1.M37 (hardware inventory)"

# ── 4. show normalizes lowercase / bare number ────────────
out_low="$(python3 "${SCRIPT}" show r317 --json)"
echo "${out_low}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['queried'] == 'R317'
" || fail "lowercase"
out_bare="$(python3 "${SCRIPT}" show 317 --json)"
echo "${out_bare}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['queried'] == 'R317'
" || fail "bare number"
pass "4. show normalizes 'r317' and bare '317' → 'R317'"

# ── 5. show SD-R97 finds selfdef round ─────────────────────
out_sd="$(python3 "${SCRIPT}" show SD-R97 --json)"
echo "${out_sd}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['matches'][0]
assert m['module'] == 'E8.M6'
" || fail "SD-R97"
pass "5. show SD-R97 → matches E8.M6 (selfdef token-saving aliases)"

# ── 6. Unknown round → rc=1 + structured error ─────────────
RC=0
python3 "${SCRIPT}" show R99999 --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "unknown round rc expected 1; got ${RC}"
pass "6. show unknown round → rc=1 + structured error"

# ── 7. by-epic <epic> filters correctly ────────────────────
out_e1="$(python3 "${SCRIPT}" by-epic E1 --json)"
echo "${out_e1}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['epic'] == 'E1'
# E1 has ≥30 rounds across hardware advisors.
assert d['match_count'] >= 30, d['match_count']
for r in d['rounds']:
    assert r['epic'] == 'E1'
" || fail "by-epic E1"
pass "7. by-epic E1 returns ≥30 rounds, all in E1"

# ── 8. by-epic normalizes 'e1' + '1' inputs ─────────────────
out_low_e="$(python3 "${SCRIPT}" by-epic e1 --json)"
echo "${out_low_e}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['epic'] == 'E1'
" || fail "lowercase epic"
pass "8. by-epic normalizes 'e1' → 'E1'"

# ── 9. recent --n N returns last N rounds ──────────────────
out_r="$(python3 "${SCRIPT}" recent --n 3 --json)"
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['n'] == 3
assert len(d['rounds']) == 3
" || fail "recent shape"
pass "9. recent --n 3 returns last 3 rounds by sort order"

# ── 10. sovereign-osctl rounds dispatch ────────────────────
out_disp="$(bash "${OSCTL}" rounds list --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R321'
" || fail "osctl dispatch"
pass "10. sovereign-osctl rounds dispatches"

echo "ALL OK"
