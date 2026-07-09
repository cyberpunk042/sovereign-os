#!/usr/bin/env bash
# R369 (E10.M13) — verbatim-render L3.
# Consolidated render of the entire SDD-037 verbatim catalog surface.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VR="${REPO_ROOT}/scripts/intelligence/verbatim-render.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. summary returns counts across all 10 catalogs ────────────────
out="$(python3 "${VR}" summary --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
tally = d['catalog_tally']
must_keys = ['questions', 'gotchas', 'concepts', 'coverage_axes',
              'ccd_layers', 'state_files', 'state_zfs_props',
              'network_ifaces', 'repl_modes']
for k in must_keys:
    assert k in tally, f'missing catalog: {k}'
assert d['total_items'] >= 70
" || fail "summary tally"
pass "1. summary tallies 9 catalogs with total ≥70 verbatim items"

# ── 2. summary catalog tally matches expected SDD-037 floors ────────
out="$(python3 "${VR}" summary --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
t = d['catalog_tally']
assert t['questions'] >= 4
assert t['gotchas'] >= 3
assert t['concepts'] >= 10
assert t['coverage_axes'] >= 30
assert t['ccd_layers'] == 3
assert t['state_files'] == 4
assert t['state_zfs_props'] == 3
assert t['network_ifaces'] == 2
assert t['repl_modes'] == 4
" || fail "tally floors"
pass "2. tally meets SDD-037 floors: ≥4 Q + ≥3 G + ≥10 C + ≥30 A + 3 CCD + 4 files + 3 ZFS + 2 NIC + 4 REPL"

# ── 3. manifest returns one entry per verbatim item ─────────────────
out="$(python3 "${VR}" manifest --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# manifest covers Q+G+C+A categories
cats = {e['category'] for e in d['entries']}
assert cats >= {'question', 'gotcha', 'concept', 'axis'}
# every entry has verb + spec_ref
for e in d['entries']:
    assert e.get('verb', '').startswith('sovereign-osctl ')
    assert e.get('spec_ref')
assert d['entry_count'] >= 60
" || fail "manifest"
pass "3. manifest enumerates ≥60 entries each with valid sovereign-osctl verb + spec_ref"

# ── 4. render emits markdown with required section headers ──────────
out="$(python3 "${VR}" render 2>&1)"
required=(
    '## §13 Architectural'
    '## §14 Critical'
    '## Architecture-qa concepts'
    '## Coverage-map axes'
    '## §19.2 CCD'
    '## §7.1 State fabric'
    '## §7.2 State fabric'
    '## §8 Network'
    '## Multi-level REPL'
)
for hdr in "${required[@]}"; do
    if ! grep -qF "${hdr}" <<< "${out}"; then
        fail "missing section header: ${hdr}"
    fi
done
pass "4. render emits all 9 catalog sections (§13/§14/concepts/axes/§19.2/§7.1/§7.2/§8/REPL)"

# ── 5. render preserves operator-verbatim phrases (cross-catalog) ──
out="$(python3 "${VR}" render 2>&1)"
# Each catalog must contribute at least one operator-EXACT phrase
must_phrases=(
    'sync=always'                                  # §7.2 ZFS
    '0xfff'                                        # §19.2 Pulse mask
    'tank/context'                                 # §7.1
    'No Outbound WAN Access'                       # §8
    'AVX-512'                                      # multiple sections
    'bitnet.cpp'                                   # multiple
    "'Magician'"                                   # §1.2 (apostrophes)
    'M.2_2 slot must remain empty'                 # §1.2
    'CMK128GX5M2B6400C42'                          # §1b hardware drop
    'SMT2200C'                                     # §1b hardware drop
)
for phrase in "${must_phrases[@]}"; do
    if ! grep -qF "${phrase}" <<< "${out}"; then
        fail "render missing operator-verbatim phrase: ${phrase}"
    fi
done
pass "5. render preserves 10 operator-VERBATIM phrases (sync=always, 0xfff, Magician, M.2_2, CMK..., SMT..., etc)"

# ── 6. render includes ASCII diagram verbatim ───────────────────────
out="$(python3 "${VR}" render 2>&1)"
grep -qF '[ OPNsense Core Router / SD-WAN Firewall ]' <<< "${out}" || fail "diagram top"
grep -qF '[Intel I226-V 2.5GbE]' <<< "${out}" || fail "diagram intel"
grep -qF '[Marvell AQC113C 10GbE]' <<< "${out}" || fail "diagram marvell"
pass "6. render preserves §8 ASCII diagram verbatim (3 key lines)"

# ── 7. render includes all 4 §7.1 file states (verbatim role text) ─
out="$(python3 "${VR}" render 2>&1)"
for f in IDENTITY.md SOUL.md AGENTS.md CLAUDE.md; do
    grep -qF "${f}" <<< "${out}" || fail "missing §7.1 file: ${f}"
done
# Verbatim role texts
grep -qF 'Immutable System Persona' <<< "${out}" || fail "IDENTITY role"
grep -qF 'Atomic Append-Only' <<< "${out}" || fail "CLAUDE role"
pass "7. render includes 4 §7.1 files with verbatim role text (Immutable Persona, Atomic Append-Only)"

# ── 8. NEVER-raises: missing catalog module → renders what's available
# Simulate: temporarily rename architecture-qa.py to force load failure
backup=$(mktemp -u)
mv "${REPO_ROOT}/scripts/intelligence/architecture-qa.py" "${backup}"
rc=0
out="$(python3 "${VR}" summary --json 2>&1)" || rc=$?
mv "${backup}" "${REPO_ROOT}/scripts/intelligence/architecture-qa.py"
[[ "${rc}" == 0 ]] || fail "summary should NEVER-raise; got rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# With architecture-qa missing, those catalogs are 0 but other catalogs
# still render
assert d['catalog_tally']['questions'] == 0
assert d['catalog_tally']['concepts'] == 0
# coverage_axes / ccd_layers / state_files still loaded
assert d['catalog_tally']['coverage_axes'] >= 30
" || fail "NEVER-raise schema"
pass "8. NEVER-raises on missing catalog module — other catalogs still render (graceful degradation)"

# ── 9. sovereign-osctl verbatim-render dispatches all 3 subverbs ───
"${OSCTL}" verbatim-render summary --json >/dev/null 2>&1 || fail "osctl summary"
"${OSCTL}" verbatim-render manifest --json >/dev/null 2>&1 || fail "osctl manifest"
"${OSCTL}" verbatim-render render >/dev/null 2>&1 || fail "osctl render"
pass "9. sovereign-osctl verbatim-render dispatches summary/manifest/render"

# ── 10. estimated phrase count is reasonable (≥200) ─────────────────
out="$(python3 "${VR}" summary --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# 76+ items × ~5 phrases each = 380+; conservative floor 200
assert d['estimated_phrase_count'] >= 200
" || fail "phrase count"
pass "10. estimated phrase count ≥200 (reflects ~378 mechanized phrases per SDD-037 cumulative)"

# ── 11. manifest entries have valid verb-shape ──────────────────────
out="$(python3 "${VR}" manifest --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Verify per-category verb shape
for e in d['entries']:
    if e['category'] in ('question', 'gotcha', 'concept'):
        assert 'architecture-qa show' in e['verb']
    elif e['category'] == 'axis':
        assert 'coverage show' in e['verb']
" || fail "manifest verb shape"
pass "11. manifest verb-shape correct per category (architecture-qa show / coverage show)"

# ── 12. render output is non-empty + has top-level title ───────────
out="$(python3 "${VR}" render 2>&1)"
grep -q "# Sovereign-OS verbatim-preservation" <<< "${out%%$'\n'*}" || fail "top title"
# Output should be ≥500 lines for the full catalog
line_count=$(echo "${out}" | wc -l)
[[ "${line_count}" -ge 500 ]] || fail "output too short: ${line_count} lines"
pass "12. render output ≥500 lines with operator-readable top-level title"

# ── 13. R367/R368 SDD-037 lint still green (cross-regression) ──────
python3 -m pytest "${REPO_ROOT}/tests/lint/test_verbatim_preservation_doctrine.py" \
                    "${REPO_ROOT}/tests/lint/test_verbatim_spec_ref_format.py" \
                    -q >/dev/null 2>&1 || fail "SDD-037 lint regressed"
pass "13. R367 + R368 SDD-037 L1 lint still green (no regression)"

echo "ALL OK"
