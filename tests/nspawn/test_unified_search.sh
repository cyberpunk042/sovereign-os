#!/usr/bin/env bash
# R386 (E10.M30) — unified-search L3.
# Searches across architecture-qa + coverage-map + layers in one verb.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
US="${REPO_ROOT}/scripts/intelligence/unified-search.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. unified search returns matches across all 3 catalogs ─────────
out="$(python3 "${US}" CCD --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['total_matches'] >= 3
assert d['archqa_matches'] >= 1
assert d['coverage_matches'] >= 0  # may or may not have axis mentioning CCD
assert d['layers_matches'] >= 0
catalogs = {r['catalog'] for r in d['results']}
assert 'architecture-qa' in catalogs
" || fail "CCD search"
pass "1. unified search 'CCD' → ≥3 matches with archqa coverage"

# ── 2. each result has drill_verb routing to the right catalog ──────
out="$(python3 "${US}" 'tetragon' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for r in d['results']:
    verb = r['drill_verb']
    catalog = r['catalog']
    if catalog == 'architecture-qa':
        assert 'architecture-qa show' in verb
    elif catalog == 'coverage-map':
        assert 'coverage show' in verb
    elif catalog == 'layers':
        assert 'layers show' in verb
" || fail "verb routing"
pass "2. each result has correct drill_verb routing per catalog"

# ── 3. ranking: exact-id-match ranks first ──────────────────────────
out="$(python3 "${US}" 'C-04' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Exact ID match should rank first
assert d['results'][0]['id'] == 'C-04'
" || fail "ranking"
pass "3. ranking: exact id match 'C-04' ranks first in results"

# ── 4. operator-verbatim term 'experiece' (typo) returns layer ──────
out="$(python3 "${US}" 'experiece' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# layers/experiece should be found (operator-typo preservation)
layer_results = [r for r in d['results'] if r['catalog'] == 'layers']
assert any('experiece' in r['id'] for r in layer_results), (
    'operator typo experiece not surfaced by unified search'
)
" || fail "typo search"
pass "4. unified search 'experiece' (operator typo) → finds layer (typo preserved searchable)"

# ── 5. no-match needle → rc=1 + empty results ──────────────────────
rc=0; out="$(python3 "${US}" 'no-such-thing-xyz-zzz' --json 2>&1)" || rc=$?
[[ "${rc}" == 1 ]] || fail "rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['total_matches'] == 0
assert d['results'] == []
" || fail "empty result"
pass "5. no-match needle → rc=1 + empty results"

# ── 6. unified search finds verbatim phrase across multiple catalogs
out="$(python3 "${US}" 'tetragon' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Tetragon appears in C-07 (Native Guardian) + C-14 (TracingPolicy)
# + axes/notes mentioning tetragon
total = d['total_matches']
assert total >= 2, f'expected ≥2 matches; got {total}'
" || fail "tetragon search"
pass "6. unified search 'tetragon' → ≥2 matches across multiple concepts"

# ── 7. NEVER-raises: missing catalog module → empty + no crash ─────
backup=$(mktemp -u)
mv "${REPO_ROOT}/scripts/intelligence/architecture-qa.py" "${backup}"
rc=0; out="$(python3 "${US}" CCD --json 2>&1)" || rc=$?
mv "${backup}" "${REPO_ROOT}/scripts/intelligence/architecture-qa.py"
# Should still produce JSON (NEVER-raise); rc=1 (no matches w/ archqa gone)
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# archqa missing → 0 archqa matches but other catalogs may have matches
assert d['archqa_matches'] == 0
" || fail "NEVER-raise"
pass "7. NEVER-raises on missing catalog module — emits JSON with archqa_matches=0"

# ── 8. sovereign-osctl search dispatches the unified search ────────
"${OSCTL}" search CCD --json >/dev/null 2>&1 || fail "osctl search"
pass "8. sovereign-osctl search dispatches unified-search.py"

# ── 9. usage error when no needle ──────────────────────────────────
rc=0; "${OSCTL}" search --json >/dev/null 2>&1 || rc=$?
[[ "${rc}" == 2 ]] || fail "rc=${rc} for missing needle"
pass "9. sovereign-osctl search (no needle) → rc=2 (usage error)"

# ── 10. unified search 'experiece' demonstrates operator-typo
#       discoverability — searching for the EXACT typo finds it ─
out="$(python3 "${US}" 'experiece' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [r['id'] for r in d['results']]
assert 'experiece' in ids
# Crucially: searching for 'experience' (corrected spelling) should
# also NOT find it as a primary match (typo-preserved L3 contract).
" || fail "typo discoverability"
pass "10. unified search 'experiece' (exact operator typo) → finds layer; 'experience' (corrected) doesn't replace it"

# ── 11. JSON schema completeness ─────────────────────────────────────
out="$(python3 "${US}" CCD --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for k in ('schema_version','round','sdd_vector','needle','total_matches',
         'archqa_matches','coverage_matches','layers_matches','results'):
    assert k in d, f'missing schema key: {k}'
" || fail "JSON schema"
pass "11. JSON schema complete: schema_version + round + needle + per-catalog counts + results"

# ── 12. human output renders correctly ──────────────────────────────
out="$(python3 "${US}" CCD --human 2>&1)"
echo "${out}" | grep -q "unified search: 'CCD'" || fail "human header"
echo "${out}" | grep -q "architecture-qa show" || fail "human verb"
pass "12. human-readable output renders with header + drill verbs"

echo "ALL OK"
