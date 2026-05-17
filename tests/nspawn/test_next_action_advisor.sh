#!/usr/bin/env bash
# R329 (E2.M22) — next-action advisor L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/intelligence/next-action-advisor.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope ────────────────────────────────
RC=0
out="$(python3 "${SCRIPT}" list --json)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "unexpected rc: ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R329'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M22'
for k in ('snapshot_at', 'recommendation_count', 'recommendations'):
    assert k in d, k
" || fail "envelope"
pass "1. list --json envelope (round/snapshot_at/recommendation_count/recommendations)"

# ── 2. Each recommendation has full schema ─────────────────
RC=0
out="$(python3 "${SCRIPT}" list --json)" || RC=$?
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for r in d['recommendations']:
    for k in ('probe', 'axis', 'severity', 'rc', 'verdict',
              'suggested_verb', 'rationale', 'priority'):
        assert k in r, (k, r)
    assert r['severity'] in ('critical', 'attention', 'unknown')
    assert isinstance(r['suggested_verb'], str)
    assert r['suggested_verb'].startswith('sovereign-osctl') or \
           r['suggested_verb'].startswith('#')
" || fail "schema"
pass "2. each recommendation has full schema (probe/axis/severity/rc/verdict/suggested_verb/rationale/priority)"

# ── 3. Recommendations sorted by priority (critical first) ──
RC=0
out="$(python3 "${SCRIPT}" list --json)" || RC=$?
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
priorities = [r['priority'] for r in d['recommendations']]
# Priorities should be in non-increasing order (highest first).
assert priorities == sorted(priorities, reverse=True), priorities
" || fail "sort"
pass "3. recommendations sorted by priority (critical-first)"

# ── 4. Informational probes excluded from recommendations ──
RC=0
out="$(python3 "${SCRIPT}" list --json)" || RC=$?
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for r in d['recommendations']:
    # rc=0 (informational) → would be sev='informational' which is filtered
    assert r['severity'] != 'informational', r
" || fail "filter"
pass "4. informational (rc=0) probes excluded from recommendations"

# ── 5. severity_from_rc unit ──────────────────────────────
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/intelligence')
import importlib.util
spec = importlib.util.spec_from_file_location('n', '${REPO_ROOT}/scripts/intelligence/next-action-advisor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.severity_from_rc(0) == 'informational'
assert m.severity_from_rc(1) == 'attention'
assert m.severity_from_rc(2) == 'critical'
assert m.severity_from_rc(None) == 'unknown'
assert m.severity_from_rc(99) == 'unknown'
print('PASS')
" || fail "severity"
pass "5. severity_from_rc maps 0/1/2/None correctly"

# ── 6. derive_recommendations handles None snapshot ────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('n', '${REPO_ROOT}/scripts/intelligence/next-action-advisor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
recs = m.derive_recommendations(None, 10)
assert recs == []
print('PASS')
" || fail "none snapshot"
pass "6. derive_recommendations returns [] on None snapshot"

# ── 7. PROBE_TO_VERB covers operator-named probes ─────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('n', '${REPO_ROOT}/scripts/intelligence/next-action-advisor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
must = {'heat-oc-throttle', 'memory-pressure-damper', 'thermal-oc',
        'operator-posture', 'storage-health', 'autohealth',
        'kernel-cmdline', 'hardening-base', 'network-stack',
        'battery-ladder', 'cpu-hotswap', 'psu-oc-mode', 'board-advisor'}
missing = must - set(m.PROBE_TO_VERB.keys())
assert not missing, missing
for name, spec_ in m.PROBE_TO_VERB.items():
    assert 'verb' in spec_
    assert 'axis' in spec_
    assert 'rationale' in spec_
print('PASS')
" || fail "probe to verb"
pass "7. PROBE_TO_VERB covers all ≥13 operator-named probes with verb+axis+rationale"

# ── 8. top verb returns single recommendation or None ──────
RC=0
out="$(python3 "${SCRIPT}" top --json)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "top rc unexpected: ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R329'
assert 'top_recommendation' in d
top = d['top_recommendation']
# top is either a dict OR None (no recommendations).
assert top is None or isinstance(top, dict)
if top is not None:
    assert 'probe' in top
    assert 'severity' in top
" || fail "top shape"
pass "8. top verb returns single recommendation (or None when all-clear)"

# ── 9. --limit caps recommendations ───────────────────────
RC=0
out="$(python3 "${SCRIPT}" list --limit 2 --json)" || RC=$?
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['recommendation_count'] <= 2
" || fail "limit"
pass "9. --limit 2 caps recommendations at 2"

# ── 10. sovereign-osctl next-action dispatch ──────────────
RC=0
out_disp="$(bash "${OSCTL}" next-action list --json 2>/dev/null)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "osctl rc unexpected: ${RC}"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R329'
" || fail "osctl dispatch"
pass "10. sovereign-osctl next-action dispatches"

echo "ALL OK"
