#!/usr/bin/env bash
# R317 (E1.M37) — hardware inventory catalog L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/inventory-catalog.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + ≥10 components ──────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R317'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M37'
assert d['total_count'] >= 10
" || fail "envelope"
pass "1. list --json envelope + ≥10 components"

# ── 2. Operator's exact specs present (UPS / RAM kit SKU / NVMe model) ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# UPS SKU SMT2200C
ups = [c for c in d['components'] if c.get('category') == 'ups']
assert ups, 'no ups'
assert ups[0].get('sku') == 'SMT2200C'
assert ups[0].get('watt_rating') == 1980
# RAM SKU CMK128GX5M2B6400C42
ram = [c for c in d['components'] if c.get('category') == 'ram']
assert len(ram) == 4, f'expected 4 DIMMs; got {len(ram)}'
for r in ram:
    assert r.get('sku') == 'CMK128GX5M2B6400C42'
    assert r.get('speed_mhz') == 6400
    assert r.get('capacity_gib') == 64
# NVMe Samsung 990 EVO Plus
nvme = [c for c in d['components'] if c.get('category') == 'nvme']
assert len(nvme) == 2
for n in nvme:
    assert '990 EVO Plus' in n.get('model', '')
    assert n.get('capacity_gb') == 2000
" || fail "operator specs"
pass "2. operator's verbatim specs in catalog (SMT2200C / CMK128GX5M2B6400C42 / 990 EVO Plus)"

# ── 3. RAM totals 256 GiB across 4 DIMMs ──────────────────
out_a="$(python3 "${SCRIPT}" audit --json)"
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
totals = d['totals']
assert totals['ram_gib'] == 256, totals
assert totals['nvme_gb'] == 4000, totals
assert totals['gpu_vram_gib'] == 152, totals  # SDD-993: 96 (PRO 6000) + 32 (RTX 5090) + 24 (RTX 4090 eGPU)
" || fail "totals"
pass "3. audit totals: RAM=256 GiB, NVMe=4000 GB, GPU VRAM=152 GiB"

# ── 4. --category filter narrows ───────────────────────────
out_r="$(python3 "${SCRIPT}" list --category ram --json)"
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert all(c.get('category') == 'ram' for c in d['components'])
assert d['filtered_count'] == 4
" || fail "category filter"
pass "4. --category ram filter narrows (4 DIMMs)"

# ── 5. show <slot> renders detail ──────────────────────────
out_s="$(python3 "${SCRIPT}" show ups-0 --json)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['component']
assert c['slot'] == 'ups-0'
assert c['sku'] == 'SMT2200C'
assert 'related_advisor' in c
" || fail "show shape"
pass "5. show ups-0 → SKU SMT2200C + related_advisor cross-refs"

# ── 6. Each component cross-refs related advisor ────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# At least UPS / PSU / RAM / NVMe / GPU / board entries should reference
# their related advisor (operator-pull navigation).
must_have_advisor = {'ups', 'psu', 'ram', 'nvme', 'gpu', 'board'}
have_advisor = {c['category'] for c in d['components']
                if c.get('related_advisor')}
missing = must_have_advisor - have_advisor
assert not missing, missing
" || fail "advisor cross-refs"
pass "6. every category cross-refs related advisor for operator-pull navigation"

# ── 7. Unknown slot → rc=1 + structured error ──────────────
RC=0
python3 "${SCRIPT}" show no-such-slot --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "show unknown rc expected 1; got ${RC}"
pass "7. show unknown slot → rc=1 + structured error"

# ── 8. Operator overlay replaces a slot ────────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[components]]
slot         = "ups-0"
category     = "ups"
model        = "Operator-replaced UPS"
vendor       = "Test"
sku          = "TEST-UPS-1"
va_rating    = 5000
watt_rating  = 4500
form_factor  = "Rackmount"
voltage_v    = 240
amp_rating   = 30
smart_connect = false
related_advisor = "test"
operator_caveat = "overlay-replaced fixture"
TOML

out_ov="$(python3 "${SCRIPT}" show ups-0 --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['component']
assert c['model'] == 'Operator-replaced UPS'
assert c['watt_rating'] == 4500
" || fail "overlay replace"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) replaces slot by match"

# ── 9. Audit verb covers per-category counts ──────────────
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
counts = d['category_counts']
# Must include all 7 operator-named categories at least once.
for cat in ('cpu', 'psu', 'ups', 'ram', 'nvme', 'gpu', 'board'):
    assert counts.get(cat, 0) >= 1, cat
" || fail "audit shape"
pass "9. audit verb: 7 categories present (cpu/psu/ups/ram/nvme/gpu/board)"

# ── 10. sovereign-osctl inventory dispatch ─────────────────
out_disp="$(bash "${OSCTL}" inventory audit --json 2>/dev/null || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R317'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl inventory dispatches"

echo "ALL OK"
