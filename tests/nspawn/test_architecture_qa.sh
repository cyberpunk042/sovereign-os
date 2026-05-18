#!/usr/bin/env bash
# R355 (E10.M3) — architecture-qa L3.
# Operator-pull master spec §13 (Q&A Matrix) + §14 (Gotchas) verbatim.
# /goal compliance: NO MINIMIZING / NO REPHRASING — verbatim preservation
# of operator-stated content is the load-bearing assertion.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AQ="${REPO_ROOT}/scripts/intelligence/architecture-qa.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. questions verb returns ≥4 Q-NN items with full schema ────────
out="$(python3 "${AQ}" questions --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['question_count'] >= 4
for q in d['questions']:
    for k in ('id','question','answer','tags','spec_ref'):
        assert k in q, (k, q)
    assert q['id'].startswith('Q-')
    assert q['spec_ref'].startswith('master spec §13')
" || fail "questions schema"
pass "1. questions returns ≥4 Q-NN with id+question+answer+tags+spec_ref (all §13)"

# ── 2. gotchas verb returns ≥3 G-NN items with full schema ──────────
out="$(python3 "${AQ}" gotchas --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['gotcha_count'] >= 3
for g in d['gotchas']:
    for k in ('id','name','context','gotcha','prevention','tags','spec_ref'):
        assert k in g, (k, g)
    assert g['id'].startswith('G-')
    assert g['spec_ref'].startswith('master spec §14')
" || fail "gotchas schema"
pass "2. gotchas returns ≥3 G-NN with id+name+context+gotcha+prevention+spec_ref (all §14)"

# ── 3. operator-VERBATIM preservation — Q-02 zfs sync=always answer ─
out="$(python3 "${AQ}" show Q-02 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
q = d['item']
# These EXACT phrases are from master spec §13 Q2 — they MUST appear verbatim
must_have = [
    'sync=always',
    'lazy write page-caching',
    'context race conditions',
    'physically flushes the dirty cache pages to NVMe silicon',
    'synchronous write paths across the transactional pipeline',
]
for phrase in must_have:
    assert phrase in q['answer'], f'missing verbatim phrase: {phrase!r}'
" || fail "Q-02 verbatim"
pass "3. Q-02 answer preserves master spec §13 verbatim phrasing (5 key phrases present)"

# ── 4. operator-VERBATIM preservation — G-01 dual-GPU lane verbatim ─
out="$(python3 "${AQ}" show G-01 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
g = d['item']
# §14 gotcha 1 verbatim phrases
must_have = [
    'ASUS ProArt X870E-Creator',
    'x8 / x8 execution topology',
    'increased latency',
    'high-frequency context loops',
]
for phrase in must_have:
    assert any(phrase in g.get(f, '') for f in ('context','gotcha','prevention')), \
        f'missing verbatim phrase: {phrase!r}'
" || fail "G-01 verbatim"
pass "4. G-01 dual-GPU gotcha preserves master spec §14 verbatim phrasing (4 key phrases)"

# ── 5. operator-VERBATIM preservation — G-02 MOK verbatim ───────────
out="$(python3 "${AQ}" show G-02 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
g = d['item']
must_have = [
    '6.12-znver5 kernel',
    'Machine Owner Key (MOK)',
    'catastrophic kernel panic or silent boot failure',
    'mokutil',
]
for phrase in must_have:
    assert any(phrase in g.get(f, '') for f in ('context','gotcha','prevention')), \
        f'missing verbatim phrase: {phrase!r}'
" || fail "G-02 verbatim"
pass "5. G-02 MOK gotcha preserves verbatim phrasing (4-phrase check including 6.12-znver5)"

# ── 6. unknown id → rc=1 + structured error with both known catalogs
rc=0
err="$(python3 "${AQ}" show no-such-id --json 2>&1 1>/dev/null)" || rc=$?
[[ "${rc}" == 1 ]] || fail "rc=${rc}"
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'error' in d
assert 'known_questions' in d and 'known_gotchas' in d
assert len(d['known_questions']) >= 4
assert len(d['known_gotchas']) >= 3
" || fail "unknown shape"
pass "6. show unknown → rc=1 + structured {error, known_questions, known_gotchas}"

# ── 7. --tag filter narrows to matching items ────────────────────────
out="$(python3 "${AQ}" questions --tag znver5 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['tag_filter'] == 'znver5'
for q in d['questions']:
    assert 'znver5' in q['tags']
assert d['question_count'] >= 1
" || fail "tag filter"
pass "7. questions --tag znver5 → narrows to Q-NN items with that tag"

# ── 8. search verb finds across questions + gotchas ─────────────────
out="$(python3 "${AQ}" search tetragon --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# 'tetragon' should hit G-03 (OPNsense + Tetragon)
total = d['question_match_count'] + d['gotcha_match_count']
assert total >= 1
assert d['gotcha_match_count'] >= 1
" || fail "search"
pass "8. search 'tetragon' → ≥1 gotcha match (G-03 OPNsense+Tetragon)"

# ── 9. operator-overlay can extend (R283/SDD-030) ───────────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
[[questions]]
id = "Q-99"
question = "operator-overlay test question?"
answer = "operator-overlay test answer."
tags = ["test","overlay"]
spec_ref = "operator overlay 2026-05-18"
TOML
out="$(python3 "${AQ}" questions --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Overlay REPLACES list per SDD-030 lists-replace
ids = [q['id'] for q in d['questions']]
assert 'Q-99' in ids
" || fail "overlay"
rm -f "${cfg}"
pass "9. operator-overlay extends questions list (R283/SDD-030 lists-replace)"

# ── 10. sovereign-osctl architecture-qa dispatches all 4 subverbs ───
"${OSCTL}" architecture-qa questions --json >/dev/null 2>&1 || fail "osctl questions"
"${OSCTL}" architecture-qa gotchas --json >/dev/null 2>&1 || fail "osctl gotchas"
"${OSCTL}" architecture-qa show Q-01 --json >/dev/null 2>&1 || fail "osctl show"
"${OSCTL}" architecture-qa search zfs --json >/dev/null 2>&1 || fail "osctl search"
pass "10. sovereign-osctl architecture-qa dispatches questions/gotchas/show/search"

# ── 11. related_verbs on gotchas reference REAL osctl verbs ─────────
out="$(python3 "${AQ}" gotchas --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Each gotcha lists related_verbs that mostly mention 'sovereign-osctl'
osctl_count = 0
for g in d['gotchas']:
    verbs = g.get('related_verbs') or []
    osctl_count += sum(1 for v in verbs if 'sovereign-osctl' in v)
assert osctl_count >= 3, f'expected ≥3 osctl verbs across gotchas; got {osctl_count}'
" || fail "related verbs"
pass "11. gotchas reference real sovereign-osctl verbs (≥3 across catalog)"

# ── 12. Q-03 cross-references the kernel-build axis correctly ───────
out="$(python3 "${AQ}" search march --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# 'march' or '-march=' should hit Q-03 (znver5 vs x86-64-v3)
ids = [q['id'] for q in d['matched_questions']]
assert 'Q-03' in ids, ids
" || fail "search march"
pass "12. search 'march' → matches Q-03 (znver5 vs x86-64-v3 verbatim)"

echo "ALL OK"
