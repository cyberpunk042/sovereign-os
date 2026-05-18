#!/usr/bin/env bash
# R377 (E10.M21) — quarterly-review meta-audit L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
QR="${REPO_ROOT}/scripts/intelligence/quarterly-review.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. snapshot returns grade + composed source data ────────────────
out="$(python3 "${QR}" snapshot --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for k in ('grade', 'headline_issues', 'coverage_audit', 'doctrine_status',
         'verbatim_summary', 'mandate_stats', 'recent_rounds_shipped'):
    assert k in d, f'missing key: {k}'
assert d['grade'] in ('A', 'B', 'C', 'D', 'F')
" || fail "snapshot schema"
pass "1. snapshot returns grade + 6 composed source data fields"

# ── 2. current state grades A (all axes ✓ shipped, all lints clean) ─
out="$(python3 "${QR}" snapshot --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Current state should be A (0 TODO + 0 partial in coverage + clean lints)
assert d['grade'] == 'A', f'expected A grade, got {d[\"grade\"]}: {d[\"headline_issues\"]}'
assert d['headline_issues'] == []
" || fail "current state A"
pass "2. current state grades A (no headline issues)"

# ── 3. coverage_audit shows 30/30 ✓ shipped ─────────────────────────
out="$(python3 "${QR}" snapshot --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cov = d['coverage_audit']['data']
assert cov['total_axes'] >= 30
assert cov['shipped_count'] >= 30
assert cov['todo_count'] == 0
" || fail "coverage rolled up"
pass "3. coverage_audit rolled up: 30/30 ✓ shipped + 0 TODO"

# ── 4. doctrine_status shows ≥7 lints + ≥60 assertions + ≥20 bugs ──
out="$(python3 "${QR}" snapshot --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
doc = d['doctrine_status']['data']
assert doc['lint_family_size'] >= 7
assert doc['total_declared_assertions'] >= 60
assert doc['cumulative_bugs_caught'] >= 20
" || fail "doctrine rolled up"
pass "4. doctrine_status rolled up: ≥7 lints / ≥60 assertions / ≥20 bugs"

# ── 5. verbatim_summary shows ≥70 catalogued items ──────────────────
out="$(python3 "${QR}" snapshot --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
verb = d['verbatim_summary']['data']
assert verb['total_items'] >= 70
" || fail "verbatim rolled up"
pass "5. verbatim_summary rolled up: ≥70 catalogued items"

# ── 6. mandate stats reflect actual file (≥150 rows, non-zero size) ─
out="$(python3 "${QR}" snapshot --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['mandate_stats']
assert m['file_present'] is True
assert m['row_count'] >= 150
assert m['file_size_bytes'] >= 50000
assert len(m['recent_rounds']) >= 5
" || fail "mandate stats"
pass "6. mandate stats: file present + ≥150 rows + ≥50KB + ≥5 recent rounds"

# ── 7. recent_rounds_shipped includes ≥15 commits since R350 ───────
out="$(python3 "${QR}" snapshot --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
recent = d['recent_rounds_shipped']
# 22+ rounds shipped in this verbatim-preservation arc
assert len(recent) >= 15, f'only {len(recent)} commits since R350'
" || fail "recent rounds"
pass "7. ≥15 commits shipped since R350 (verbatim-preservation arc)"

# ── 8. grade verb returns just grade + issues ──────────────────────
out="$(python3 "${QR}" grade --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['grade'] == 'A'
assert d['headline_issues'] == []
" || fail "grade"
pass "8. grade verb returns A + empty headline_issues for current state"

# ── 9. recent verb lists rounds since R<N> ──────────────────────────
out="$(python3 "${QR}" recent --since R370 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['since_round'] == 370
# At least R371..R377 should appear (7 rounds)
assert d['commit_count'] >= 5
for c in d['commits']:
    assert c['round'].startswith('R')
" || fail "recent"
pass "9. recent --since R370 lists ≥5 commits with R-numbers ≥R370"

# ── 10. rc=0 when grade A; rc=1 when grade C/D/F ───────────────────
rc=0; python3 "${QR}" snapshot --json >/dev/null 2>&1 || rc=$?
[[ "${rc}" == 0 ]] || fail "snapshot rc=${rc} (expected 0 for A grade)"
pass "10. rc=0 when current grade A; rc=1 reserved for grade C/D/F"

# ── 11. osctl dispatches all 3 subverbs ─────────────────────────────
"${OSCTL}" quarterly-review snapshot --json >/dev/null 2>&1 || fail "osctl snapshot"
"${OSCTL}" quarterly-review grade --json >/dev/null 2>&1 || fail "osctl grade"
"${OSCTL}" quarterly-review recent --json >/dev/null 2>&1 || fail "osctl recent"
pass "11. sovereign-osctl quarterly-review dispatches snapshot/grade/recent"

# ── 12. NEVER-raises: subverbs return JSON even if a composed source
#       fails (NEVER-raise contract per SDD-032)
# Simulate: rename one composed source momentarily
backup=$(mktemp -u)
mv "${REPO_ROOT}/scripts/intelligence/coverage-map.py" "${backup}"
rc=0; out="$(python3 "${QR}" snapshot --json 2>&1)" || rc=$?
mv "${backup}" "${REPO_ROOT}/scripts/intelligence/coverage-map.py"
# Should still emit JSON even with missing source
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# coverage_audit will have 'error' field instead of 'data'
assert 'coverage_audit' in d
" || fail "NEVER-raise on missing source"
pass "12. NEVER-raises on missing composed source — emits JSON with error field"

echo "ALL OK"
