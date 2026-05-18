#!/usr/bin/env bash
# R382 (E10.M26) — layers L3.
# Operator-verbatim 11-layer 'guide into' enumeration from 2026-05-17.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LY="${REPO_ROOT}/scripts/intelligence/layers.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list returns exactly 11 operator-named layers ────────────────
out="$(python3 "${LY}" list --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['layer_count'] == 11
" || fail "11 layers"
pass "1. list returns exactly 11 operator-named layers from hook drop"

# ── 2. operator typo 'experiece' preserved verbatim (NO correction) ─
out="$(python3 "${LY}" list --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {l['layer'] for l in d['layers']}
# Operator typo MUST be preserved
assert 'experiece' in names, 'operator typo experiece NOT preserved'
# AND must NOT be silently corrected to 'experience'
assert 'experience' not in names, 'silent typo correction detected'
" || fail "typo preservation"
pass "2. operator typo 'experiece' preserved verbatim (NO silent correction)"

# ── 3. all 11 operator-named layers present + ordered as in hook drop
out="$(python3 "${LY}" list --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
expected = ['experiece', 'field', 'kernel', 'hardware', 'OS', 'modules',
            'features', 'services', 'configurations', 'personalisations',
            'customizations']
actual = [l['layer'] for l in d['layers']]
assert actual == expected, f'expected {expected}, got {actual}'
" || fail "order"
pass "3. layers ordered exactly as operator hook drop verbatim (11 layers)"

# ── 4. each layer has ≥1 implementing verb ──────────────────────────
out="$(python3 "${LY}" list --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for layer in d['layers']:
    verbs = layer.get('implementing_verbs') or []
    assert len(verbs) >= 1, f'layer {layer[\"layer\"]} has no verbs'
" || fail "verbs"
pass "4. every layer has ≥1 implementing verb (no orphan layer)"

# ── 5. layer_verbatim strings preserve operator's exact phrasing ────
out="$(python3 "${LY}" list --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_name = {l['layer']: l for l in d['layers']}
# Operator's verbatim 'into the X' / 'the X' phrasing preserved
assert by_name['experiece']['layer_verbatim'] == 'into the experiece'
assert by_name['kernel']['layer_verbatim'] == 'into the kernel'
assert by_name['services']['layer_verbatim'] == 'the services'
assert by_name['personalisations']['layer_verbatim'] == 'the personalisations'
" || fail "verbatim phrasing"
pass "5. layer_verbatim strings preserve 'into the X' / 'the X' operator phrasing"

# ── 6. show preserves operator's verbatim sentence in human output ──
out="$(python3 "${LY}" list --human 2>&1)"
# The full operator-verbatim sentence must appear
echo "${out}" | grep -q "Its not only going to be an AI" \
    || fail "missing operator verbatim opening"
echo "${out}" | grep -q "experiece" || fail "list human missing typo"
echo "${out}" | grep -q "personalisations" || fail "list human missing personalisations"
pass "6. list --human prints operator-verbatim sentence + 'experiece' typo + all 11 layers"

# ── 7. show <layer> drill-in returns full schema ────────────────────
out="$(python3 "${LY}" show kernel --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
layer = d['layer_detail']
for k in ('layer', 'layer_verbatim', 'operator_note',
         'implementing_verbs', 'guide_topic_match', 'spec_ref'):
    assert k in layer, k
assert layer['layer'] == 'kernel'
assert layer['guide_topic_match'] == 'kernel'  # cross-link to R349 guide
" || fail "show schema"
pass "7. show kernel returns full schema + cross-links to R349 guide topic"

# ── 8. show unknown layer → rc=1 + known_layers list ────────────────
rc=0; err="$(python3 "${LY}" show no-such --json 2>&1 1>/dev/null)" || rc=$?
[[ "${rc}" == 1 ]] || fail "rc=${rc}"
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'error' in d
assert len(d['known_layers']) == 11
" || fail "known_layers"
pass "8. show unknown → rc=1 + known_layers list has 11 entries"

# ── 9. search 'whitelabel' finds personalisations layer ────────────
out="$(python3 "${LY}" search whitelabel --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {l['layer'] for l in d['matched_layers']}
assert 'personalisations' in names
" || fail "search"
pass "9. search 'whitelabel' → personalisations layer matched"

# ── 10. search 'configurations' finds configurations layer ─────────
out="$(python3 "${LY}" search configurations --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {l['layer'] for l in d['matched_layers']}
assert 'configurations' in names
" || fail "search configs"
pass "10. search 'configurations' → configurations layer matched"

# ── 11. osctl dispatches all 3 subverbs ─────────────────────────────
"${OSCTL}" layers list --json >/dev/null 2>&1 || fail "osctl list"
"${OSCTL}" layers show kernel --json >/dev/null 2>&1 || fail "osctl show"
"${OSCTL}" layers search hardware --json >/dev/null 2>&1 || fail "osctl search"
pass "11. sovereign-osctl layers dispatches list/show/search"

# ── 12. operator-overlay extends layers list ───────────────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
[[layers]]
layer = "overlay-test"
layer_verbatim = "into the test"
operator_note = "test"
implementing_verbs = ["sovereign-osctl test"]
spec_ref = "overlay test 2026-05-18"
TOML
out="$(python3 "${LY}" list --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {l['layer'] for l in d['layers']}
assert 'overlay-test' in names
" || fail "overlay"
rm -f "${cfg}"
pass "12. operator-overlay extends layers list (R283/SDD-030)"

# ── 13. cross-link to architecture-qa concepts (C-NN refs in verbs) ─
out="$(python3 "${LY}" list --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Multiple layers should cross-link to architecture-qa C-NN concepts
total_concept_refs = sum(
    1 for layer in d['layers']
    for v in (layer.get('implementing_verbs') or [])
    if 'architecture-qa show C-' in v
)
assert total_concept_refs >= 5, f'only {total_concept_refs} layers cross-link to C-NN concepts'
" || fail "concept cross-links"
pass "13. ≥5 layers cross-link to architecture-qa C-NN concepts (catalog connectivity)"

echo "ALL OK"
