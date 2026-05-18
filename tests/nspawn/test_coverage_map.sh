#!/usr/bin/env bash
# R365 (E10.M10) — coverage-map L3.
# Operator-pull catalog of every named axis from hook drops + mandate
# + raw dumps mapped to implementing verbs / SDDs / mandate rows.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CM="${REPO_ROOT}/scripts/intelligence/coverage-map.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. axes verb returns ≥30 A-NN catalog ───────────────────────────
out="$(python3 "${CM}" axes --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['axis_count'] >= 30
for a in d['axes']:
    for k in ('id','axis_verbatim','source','implementing_verbs',
             'mandate_rows','status','notes'):
        assert k in a, (k, a)
    assert a['id'].startswith('A-')
    assert a['status'] in ('✓ shipped', 'partial', 'TODO')
" || fail "axes schema"
pass "1. axes catalog ≥30 A-NN with id+axis_verbatim+source+verbs+rows+status+notes"

# ── 2. each axis has ≥1 implementing verb (no orphan operator demand)
out="$(python3 "${CM}" axes --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for a in d['axes']:
    verbs = a.get('implementing_verbs') or []
    assert len(verbs) >= 1, f'axis {a[\"id\"]} has no implementing verb'
" || fail "verb coverage"
pass "2. every axis has ≥1 implementing verb (no orphan operator demand)"

# ── 3. status counts: ≥25 shipped, ≤5 partial, 0 TODO ──────────────
out="$(python3 "${CM}" axes --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['shipped_count'] >= 25
assert d['partial_count'] <= 5
assert d['todo_count'] == 0
" || fail "status counts"
pass "3. status: ≥25 ✓ shipped + ≤5 partial + 0 TODO (operator demand fully addressed)"

# ── 4. operator-VERBATIM hook-drop phrases preserved in axes ────────
out="$(python3 "${CM}" axes --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
all_verbatim = ' '.join(a.get('axis_verbatim','') for a in d['axes'])
# Operator-verbatim phrases from the 2026-05-17 hook drop
must = [
    'AI and the tools but also download, fine-tune',
    'non docker vs docker install',
    'container level vs system level',
    'autohealth and doctor',
    'Cloudflared',
    'tailscale',
    'Traefik',
    'logs, log rotate',
    'CMK128GX5M2B6400C42',
    'SMT2200C',
    '990 EVO Plus',
    'be Quiet! Dark Power Pro 13 1600W',
    'Proto-Programing',
    'Proto-Proto-Programming',
    'custom CoT',
    'continue till you meet ALL MY REQUIREMENTS',
    'RETURN REREAD ALL THE RAW DUMP AND REPROCESS',
    'DO not stop',
    'continue endlessly',
    'We do not minimize anything',
]
for phrase in must:
    assert phrase in all_verbatim, f'missing operator-verbatim: {phrase!r}'
" || fail "verbatim hook-drop phrases"
pass "4. axes preserve 20 operator-VERBATIM hook-drop phrases unchanged (no paraphrasing)"

# ── 5. audit verb rc=0 when no TODO (current state) ─────────────────
rc=0; out="$(python3 "${CM}" audit --json 2>&1)" || rc=$?
[[ "${rc}" == 0 ]] || fail "audit rc=${rc} (expected 0)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['todo_count'] == 0
assert d['shipped_count'] >= 25
" || fail "audit shape"
pass "5. audit rc=0 (no TODO); ≥25 shipped axes"

# ── 6. show A-04 (GPU details) cites RTX 3090 + RTX Pro 6000 + AVX512
out="$(python3 "${CM}" show A-04 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
a = d['axis']
av = a['axis_verbatim']
assert 'RTX 3090' in av
assert 'RTX Pro 6000' in av
assert 'AVX512' in av
assert 'gpu-card-advisor' in ' '.join(a['implementing_verbs'])
assert 'avx512-advisor' in ' '.join(a['implementing_verbs'])
" || fail "A-04 GPU axis"
pass "6. show A-04 — RTX 3090 + RTX Pro 6000 + AVX512 verbatim + binds gpu-card-advisor + avx512-advisor"

# ── 7. show A-22 (PSU/APC integration) cites operator's exact "schedule/planifest/graceful"
out="$(python3 "${CM}" show A-22 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
a = d['axis']
av = a['axis_verbatim']
# Operator's verbatim 'schedule/planifest/graceful' (note 'planifest' typo preserved)
assert 'schedule/planifest/graceful' in av
assert 'power-shutdown' in ' '.join(a['implementing_verbs'])
" || fail "A-22 PSU/APC"
pass "7. show A-22 — operator's verbatim 'schedule/planifest/graceful' (typo preserved per /goal NO PARAPHRASING)"

# ── 8. show unknown axis → rc=1 + known_axes list ──────────────────
rc=0; err="$(python3 "${CM}" show A-NOPE --json 2>&1 1>/dev/null)" || rc=$?
[[ "${rc}" == 1 ]] || fail "rc=${rc}"
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'error' in d
assert len(d['known_axes']) >= 30
" || fail "show unknown shape"
pass "8. show unknown axis → rc=1 + structured {error, known_axes ≥30}"

# ── 9. search 'pcie' finds A-19 ────────────────────────────────────
out="$(python3 "${CM}" search 'pcie' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [a['id'] for a in d['matched_axes']]
assert 'A-19' in ids, ids
" || fail "search pcie"
pass "9. search 'pcie' → A-19 (pcie lane splits axis)"

# ── 10. search 'verbatim' / 'no minimizing' finds /goal-contract axis
out="$(python3 "${CM}" search 'MINIMIZING' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [a['id'] for a in d['matched_axes']]
assert 'A-27' in ids, ids
" || fail "search MINIMIZING"
pass "10. search 'MINIMIZING' → A-27 (/goal NO MINIMIZING contract axis)"

# ── 11. --status filter narrows to ✓ shipped ────────────────────────
out="$(python3 "${CM}" axes --status '✓ shipped' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for a in d['axes']:
    assert a['status'] == '✓ shipped'
assert d['axis_count'] >= 25
" || fail "status filter"
pass "11. --status '✓ shipped' filter narrows to shipped axes only"

# ── 12. sovereign-osctl coverage dispatches all 4 subverbs ──────────
"${OSCTL}" coverage axes --json >/dev/null 2>&1 || fail "osctl axes"
"${OSCTL}" coverage show A-01 --json >/dev/null 2>&1 || fail "osctl show"
"${OSCTL}" coverage audit --json >/dev/null 2>&1 || fail "osctl audit"
"${OSCTL}" coverage search ups --json >/dev/null 2>&1 || fail "osctl search"
pass "12. sovereign-osctl coverage dispatches axes/show/audit/search"

# ── 13. operator-overlay extends axes (R283/SDD-030) ───────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
[[axes]]
id = "A-99"
axis_verbatim = "operator overlay test axis"
source = "test"
implementing_verbs = ["sovereign-osctl test"]
sdd_refs = []
mandate_rows = []
status = "TODO"
notes = "test"
TOML
out="$(python3 "${CM}" axes --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [a['id'] for a in d['axes']]
assert 'A-99' in ids
" || fail "overlay"
# audit with overlay should rc=1 (A-99 is TODO)
rc=0; python3 "${CM}" audit --config "${cfg}" --json >/dev/null 2>&1 || rc=$?
[[ "${rc}" == 1 ]] || fail "overlay audit rc=${rc} (expected 1 because A-99 is TODO)"
rm -f "${cfg}"
pass "13. operator-overlay extends axes (lists-replace) AND audit rc=1 on TODO axis (proves status enforcement)"

echo "ALL OK"
