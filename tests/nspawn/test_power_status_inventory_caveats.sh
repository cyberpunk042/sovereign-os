#!/usr/bin/env bash
# R348 (E9.M17) — R252 power-status adopts scripts/lib/inventory_consult.
# Second consumer of the SDD-032 §4 helper after R315 refactor.
# Surfaces UPS SMT2200C operator-actionable caveat to advisories verdict.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PS="${REPO_ROOT}/scripts/hardware/power-status.py"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. advisories JSON exposes inventory_caveats field ────────────────
out="$(python3 "${PS}" advisories --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'inventory_caveats' in d, 'inventory_caveats key missing'
assert isinstance(d['inventory_caveats'], list)
" || fail "field present"
pass "1. advisories JSON exposes inventory_caveats field"

# ── 2. UPS SMT2200C caveat surfaces ───────────────────────────────────
out="$(python3 "${PS}" advisories --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ic = d.get('inventory_caveats', [])
ups_cv = next((c for c in ic if c.get('slot') == 'ups-0'), None)
assert ups_cv is not None, f'ups-0 caveat missing; got slots: {[c.get(\"slot\") for c in ic]}'
assert ups_cv.get('sku') == 'SMT2200C'
assert ups_cv.get('caveat')
assert ups_cv.get('severity') in ('warn', 'info')
" || fail "ups caveat"
pass "2. ups-0 (SMT2200C) caveat surfaces in advisories JSON"

# ── 3. NEVER-raise — psu/ups/budget verbs still return valid JSON ─────
for verb in psu ups budget advisories; do
    out="$(python3 "${PS}" "${verb}" --json 2>&1 || true)"
    echo "${out}" | python3 -c "import json, sys; json.loads(sys.stdin.read())" \
        || fail "verb ${verb} broken"
done
pass "3. NEVER-raise — psu/ups/budget/advisories all return valid JSON"

# ── 4. helper module is importable + exports public API ───────────────
PYTHONPATH="${REPO_ROOT}/scripts/lib" python3 -c "
from inventory_consult import find_advisor_caveats, caveats_matching
assert callable(find_advisor_caveats)
assert callable(caveats_matching)
# R252 returns at least one entry (UPS caveat)
out = find_advisor_caveats('R252')
assert isinstance(out, list)
assert len(out) >= 1, f'expected R252-tagged caveats; got {out}'
# R315 returns at least one (4-DIMM XMP)
out = find_advisor_caveats('R315')
assert len(out) >= 1
# unknown round → []
assert find_advisor_caveats('R99999') == []
# empty round → []
assert find_advisor_caveats('') == []
" || fail "helper API"
pass "4. helper module exports find_advisor_caveats + caveats_matching (SDD-032 contract)"

# ── 5. caveats_matching filter — contains_any narrows result set ──────
PYTHONPATH="${REPO_ROOT}/scripts/lib" python3 -c "
from inventory_consult import caveats_matching
# 'refurbished' is in the ups caveat text
hits = caveats_matching('R252', contains_any=['refurbished'])
assert len(hits) >= 1, f'expected refurbished hit; got {hits}'
# nonsense substring → []
hits = caveats_matching('R252', contains_any=['nonexistent-xyz-zzz'])
assert hits == []
" || fail "contains_any"
pass "5. caveats_matching contains_any filter narrows result set"

# ── 6. NEVER-raise contract — broken catalog path → [] not crash ──────
PYTHONPATH="${REPO_ROOT}/scripts/lib" python3 -c "
import inventory_consult
# Monkeypatch path to a non-existent file
import pathlib
inventory_consult._CATALOG_PATH = pathlib.Path('/no/such/catalog.py')
out = inventory_consult.find_advisor_caveats('R252')
assert out == [], f'expected [] on missing catalog; got {out}'
out = inventory_consult.caveats_matching('R252', contains_any=['x'])
assert out == []
" || fail "never raise"
pass "6. NEVER-raise — missing catalog file → [] (no exception)"

# ── 7. R315 + R252 both visible in helper output (multi-consumer) ────
PYTHONPATH="${REPO_ROOT}/scripts/lib" python3 -c "
from inventory_consult import find_advisor_caveats
r315 = find_advisor_caveats('R315')
r252 = find_advisor_caveats('R252')
# Same catalog, different round tags → different slot sets surface
slots_315 = {c['slot'] for c in r315}
slots_252 = {c['slot'] for c in r252}
assert 'ups-0' in slots_252, slots_252
assert 'ram-dimm-2' in slots_315, slots_315
# UPS slot not tagged R315 → not in R315 result
assert 'ups-0' not in slots_315
" || fail "multi consumer"
pass "7. multi-consumer — R315 and R252 see different (correct) slot sets"

echo "ALL OK"
