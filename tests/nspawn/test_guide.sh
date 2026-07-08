#!/usr/bin/env bash
# R349 (E10.M1) — guide topic catalog L3.
# Operator-pull "guide me INTO <topic>" — kernel / hardware / gpu /
# psu / ups / memory / workload-mode / inference / network.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GUIDE="${REPO_ROOT}/scripts/intelligence/guide.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. topics verb lists all expected topics ─────────────────────────
out="$(python3 "${GUIDE}" topics --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = set(d['topic_names'])
for must in ('kernel','hardware','gpu','psu','ups','memory',
             'workload-mode','inference','network'):
    assert must in names, f'missing topic: {must}'
" || fail "topics list"
pass "1. topics verb lists all 9 expected topics"

# ── 2. axes enumeration covers system/hardware/intelligence/ai/network
out="$(python3 "${GUIDE}" topics --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
axes = set(d['axes'])
for must in ('system','hardware','intelligence','ai','network'):
    assert must in axes, f'missing axis: {must}'
" || fail "axes"
pass "2. axes enumeration covers system/hardware/intelligence/ai/network"

# ── 3. show <topic> returns full topic block ─────────────────────────
out="$(python3 "${GUIDE}" show gpu --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
t = d['topic']
for k in ('mission','layers','operator_verbs','thresholds','cross_refs','bios_or_hw_caveats'):
    assert k in t, k
assert len(t['layers']) >= 3
assert len(t['operator_verbs']) >= 3
" || fail "show schema"
pass "3. show gpu --json returns full topic schema (mission+layers+verbs+thresholds+xrefs+caveats)"

# ── 4. unknown topic → rc=1 + structured error ───────────────────────
rc=0
err="$(python3 "${GUIDE}" show no-such-topic --json 2>&1 1>/dev/null)" || rc=$?
[[ "${rc}" == 1 ]] || fail "unknown rc=${rc}"
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'error' in d and 'known' in d
assert len(d['known']) >= 5
" || fail "unknown shape"
pass "4. unknown topic → rc=1 + structured {error, known: [...]}"

# ── 5. walkthrough <topic> emits narrative block ─────────────────────
out="$(python3 "${GUIDE}" walkthrough kernel --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['walkthrough_mode'] is True
assert d['topic_name'] == 'kernel'
assert d['layer_count'] >= 3
assert d['verb_count'] >= 3
assert isinstance(d['layers'], list)
assert isinstance(d['operator_verbs'], list)
" || fail "walkthrough schema"
pass "5. walkthrough kernel --json emits narrative block (layers+verbs+caveats)"

# ── 6. EVERY topic — layer count MATCHES verb count (zip correctness)
out="$(python3 "${GUIDE}" list --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
mismatches = []
for t in d['topics']:
    L = len(t.get('layers') or [])
    V = len(t.get('operator_verbs') or [])
    if L != V:
        mismatches.append(f'{t[\"topic\"]}: layers={L} verbs={V}')
assert not mismatches, 'layer/verb count mismatch (walkthrough zip drift): ' + '; '.join(mismatches)
" || fail "zip mismatch"
pass "6. EVERY topic — layer count == verb count (walkthrough zip integrity)"

# ── 7. operator-verbatim phrases preserved in mission text ──────────
out="$(python3 "${GUIDE}" list --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Operator §1b drop named these by SKU — they MUST surface in topic content
text = json.dumps(d)
for must in ('CMK128GX5M2B6400C42', 'SMT2200C', 'RTX 4090',
             'RTX PRO 6000', 'Ryzen 9 9900X', 'be Quiet! Dark Power Pro',
             'ASUS', 'X870E-CREATOR'):
    assert must in text, f'topic catalog missing operator-verbatim: {must}'
" || fail "verbatim"
pass "7. operator-verbatim §1b hardware SKUs preserved in topic catalog"

# ── 8. --axis filter narrows result set ──────────────────────────────
out="$(python3 "${GUIDE}" list --axis hardware --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['axis_filter'] == 'hardware'
for t in d['topics']:
    assert t['axis'] == 'hardware'
assert len(d['topics']) >= 4
" || fail "axis filter"
pass "8. --axis filter narrows list to matching topics (≥4 in 'hardware' axis)"

# ── 9. sovereign-osctl guide dispatches all 4 verbs ──────────────────
"${OSCTL}" guide topics --json >/dev/null 2>&1 || fail "osctl topics"
"${OSCTL}" guide list --json >/dev/null 2>&1 || fail "osctl list"
"${OSCTL}" guide show ups --json >/dev/null 2>&1 || fail "osctl show"
"${OSCTL}" guide walkthrough memory --json >/dev/null 2>&1 || fail "osctl walkthrough"
pass "9. sovereign-osctl guide dispatches topics/list/show/walkthrough"

# ── 10. cross_refs cite real SDDs that exist on disk ─────────────────
out="$(python3 "${GUIDE}" list --json || true)"
echo "${out}" | python3 -c "
import json, sys, os, re, pathlib
d = json.loads(sys.stdin.read())
REPO = pathlib.Path('${REPO_ROOT}')
sdd_dir = REPO / 'docs' / 'sdd'
on_disk = {p.name for p in sdd_dir.glob('*.md')}
# Build set of SDD-NNN slugs by matching first 3 digits of each file.
sdd_numbers = set()
for f in on_disk:
    m = re.match(r'(\d{3})-', f)
    if m: sdd_numbers.add(m.group(1))
missing = []
for t in d['topics']:
    for ref in t.get('cross_refs') or []:
        m = re.search(r'SDD[-\s](\d{3})', ref, re.I)
        if m and m.group(1) not in sdd_numbers:
            missing.append(f'{t[\"topic\"]}: {ref}')
assert not missing, f'topic cross_refs cite missing SDDs: {missing}'
" || fail "cross refs"
pass "10. topic cross_refs cite SDDs that actually exist on disk"

echo "ALL OK"
