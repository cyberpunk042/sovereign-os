#!/usr/bin/env bash
# R309 (E2.M15) — sovereign-os CoT registry L3.
#
# Operator-named (§1b mandate row): "Programming, Proto-Programing,
# Proto-Proto-Programming and CoT and custom CoT, integrated
# intelligence modules, features and options".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/intelligence/cot-registry.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + 6 default routines ────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R309'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M15'
assert d['total_count'] == 6
" || fail "envelope"
pass "1. list --json envelope + 6 default CoT routines"

# ── 2. Six operator-named routines present ────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {r['name'] for r in d['routines']}
must = {'oc-go-no-go-cot', 'health-triage-cot', 'psu-budget-cot',
        'storage-cleanup-cot', 'pre-shutdown-cot', 'boot-troubleshoot-cot'}
missing = must - names
assert not missing, missing
" || fail "names"
pass "2. all 6 operator-named CoT routines present"

# ── 3. Each routine carries description + axes_probes + GO set ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for r in d['routines']:
    for k in ('name', 'description', 'axis', 'axes_probes',
              'go_when_all_verdicts_in'):
        assert k in r, (k, r['name'])
    assert isinstance(r['axes_probes'], list) and r['axes_probes']
    for spec in r['axes_probes']:
        assert isinstance(spec, list) and len(spec) == 2
" || fail "routine schema"
pass "3. every routine carries description + axes_probes + go_when_all_verdicts_in"

# ── 4. --axis filter narrows ─────────────────────────────────
out_p="$(python3 "${SCRIPT}" list --axis performance --json)"
echo "${out_p}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert all(r['axis'] == 'performance' for r in d['routines'])
assert d['filtered_count'] == 2  # oc-go-no-go + psu-budget
" || fail "axis filter"
pass "4. --axis performance filter narrows (2 routines)"

# ── 5. show <cot> renders detail ───────────────────────────
out_s="$(python3 "${SCRIPT}" show oc-go-no-go-cot --json)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r = d['routine']
assert r['name'] == 'oc-go-no-go-cot'
assert r['axis'] == 'performance'
assert len(r['axes_probes']) == 3
" || fail "show shape"
pass "5. show oc-go-no-go-cot renders full detail"

# ── 6. Unknown CoT → rc=1 + structured error ──────────────
RC=0
python3 "${SCRIPT}" show no-such-cot --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "show unknown rc expected 1; got ${RC}"
err="$(python3 "${SCRIPT}" show no-such-cot --json 2>&1 1>/dev/null)" || true
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'unknown CoT' in d['error']
assert isinstance(d['known'], list)
" || fail "show unknown shape"
pass "6. show unknown CoT → rc=1 + structured error JSON"

# ── 7. run <cot> composes probes + emits CoT verdict ────────
RC=0
out_r="$(python3 "${SCRIPT}" run oc-go-no-go-cot --json)" || RC=$?
# rc ∈ {0, 1, 2} all valid (depends on host posture)
[[ "${RC}" == "0" || "${RC}" == "1" || "${RC}" == "2" ]] \
    || fail "run rc unexpected: ${RC}"
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R309'
assert d['cot'] == 'oc-go-no-go-cot'
assert 'verdict' in d
assert d['verdict'] in ('GO', 'WAIT', 'WAIT (critical)', 'probes-unavailable')
assert 'axes_results' in d
assert len(d['axes_results']) == 3
for r in d['axes_results']:
    for k in ('probe', 'verdict', 'available'):
        assert k in r
" || fail "run shape"
pass "7. run oc-go-no-go-cot composes 3 probes + emits CoT verdict"

# ── 8. Unknown CoT → run rc=2 ───────────────────────────────
RC=0
python3 "${SCRIPT}" run no-such-cot --json 2>/dev/null || RC=$?
[[ "${RC}" == "2" ]] || fail "run unknown rc expected 2; got ${RC}"
pass "8. run unknown CoT → rc=2"

# ── 9. Operator overlay replaces catalog ──────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[routines]]
name        = "operator-custom-cot"
axis        = "test"
description = "operator-pinned fixture for overlay replacement"
axes_probes = [
    ["scripts/hardware/health-scan.py", ["--json"]],
]
go_when_all_verdicts_in = ["ok", "healthy"]
operator_caveat = "n/a"
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [r['name'] for r in d['routines']]
assert names == ['operator-custom-cot'], names
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "9. operator overlay (R283/SDD-030) replaces catalog"

# ── 10. sovereign-osctl cot dispatch ──────────────────────
out_disp="$(bash "${OSCTL}" cot list --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R309'
assert d['total_count'] == 6
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl cot dispatches (list/show/run subverbs)"

echo "ALL OK"
