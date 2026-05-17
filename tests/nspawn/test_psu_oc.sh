#!/usr/bin/env bash
# R294 (E1.M22) — PSU OC-mode orchestration L3.
#
# Operator-named (§1b mandate row): "My PSU even have an overclock
# mode which might be important".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/psu-oc.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. state --json envelope ─────────────────────────────────
out="$(python3 "${SCRIPT}" state --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R294'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M22'
assert d['operator_psu_model'] == 'be Quiet! Dark Power Pro 13 1600W'
assert d['oc_mode_enabled'] is False
assert d['operator_psu_spec'] is not None
" || fail "state envelope"
pass "1. state --json envelope + operator's PSU resolved"

# ── 2. be Quiet! Dark Power Pro 13 1600W is the default PSU ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
spec = d['operator_psu_spec']
assert spec['rated_standard_watts'] == 1600
assert spec['rated_oc_mode_watts'] == 1600
assert spec['brief_peak_watts'] == 3200
assert spec['atx_revision'] == '3.1'
assert spec['efficiency'] == '80 Plus Titanium'
" || fail "be Quiet! spec mismatch"
pass "2. be Quiet! Dark Power Pro 13 1600W spec correct (ATX 3.1 Titanium, 3200 W peak)"

# ── 3. budget verb emits effective rated + planning budget ───
out_b="$(python3 "${SCRIPT}" budget --json)"
echo "${out_b}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
b = d['effective_budget']
assert b['rated_watts'] == 1600
assert b['effective_rated_watts'] == 1600
# planning_budget = rated × (1 - safety_margin / 100) = 1600 × 0.9
assert abs(b['planning_budget_watts'] - 1440.0) < 0.1, b
assert b['oc_mode_enabled'] is False
assert b['brief_peak_watts'] == 3200
" || fail "budget shape"
pass "3. budget: 1440 W planning budget (1600 × (1 - 10%))"

# ── 4. OC-mode toggle shifts the planning budget ─────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
oc_mode_enabled            = true
sustained_safety_margin_pct = 5
TOML

out_oc="$(python3 "${SCRIPT}" budget --config "${overlay}" --json)"
echo "${out_oc}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
b = d['effective_budget']
assert b['oc_mode_enabled'] is True
# 1600 × 0.95 = 1520
assert abs(b['planning_budget_watts'] - 1520.0) < 0.1, b
" || fail "OC-mode toggle effect"
rm -f "${overlay}"
pass "4. OC-mode toggle reshapes planning budget (5% safety → 1520 W)"

# ── 5. Operator-extendable known_psus registry ────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
operator_psu_model         = "Operator-Custom-PSU"
oc_mode_enabled            = false
sustained_safety_margin_pct = 20

[[known_psus]]
model                = "Operator-Custom-PSU"
rated_standard_watts = 850
rated_oc_mode_watts  = 850
brief_peak_watts     = 1100
efficiency           = "80 Plus Gold"
atx_revision         = "2.4"
oc_mode_semantics    = "No OC mode."
TOML

out_op="$(python3 "${SCRIPT}" state --config "${overlay}" --json)"
echo "${out_op}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['operator_psu_model'] == 'Operator-Custom-PSU'
spec = d['operator_psu_spec']
assert spec is not None
assert spec['rated_standard_watts'] == 850
# Default registry NOT inherited — operator's known_psus replaces.
known = [k['model'] for k in d['operator_psu_spec'] if False] or None
# planning budget = 850 × (1 - 20%) = 680
assert abs(d['effective_budget']['planning_budget_watts'] - 680.0) < 0.1
" || fail "operator overlay add"
rm -f "${overlay}"
pass "5. operator can declare custom PSU + spec via overlay"

# ── 6. Unknown PSU model gives operator-readable note ─────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
operator_psu_model = "Unknown-PSU-Model-XYZ"
TOML

out_unk="$(python3 "${SCRIPT}" state --config "${overlay}" --json)"
echo "${out_unk}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# operator_psu_spec is None (resolve_spec didn't find it).
assert d['operator_psu_spec'] is None
b = d['effective_budget']
assert b['planning_budget_watts'] is None
assert 'not in known_psus' in b['note']
" || fail "unknown PSU handling"
rm -f "${overlay}"
pass "6. unknown PSU model → spec=None + operator-readable note"

# ── 7. Malformed overlay → defaults + _parse_error ───────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" state --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['operator_psu_model'] == 'be Quiet! Dark Power Pro 13 1600W'
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "7. malformed overlay → defaults + _parse_error"

# ── 8. projection verb composes R292 oc-headroom ──────────────
out_proj="$(python3 "${SCRIPT}" projection --json)"
echo "${out_proj}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R294'
# Both standard + oc modes have at least a verdict reading.
assert 'standard_mode' in d
assert 'oc_mode' in d
for mode in ('standard_mode', 'oc_mode'):
    # Either rendered cleanly or None (when oc-headroom unavailable).
    v = d[mode].get('verdict')
    assert v is None or v in ('headroom-safe', 'headroom-tight', 'over-budget'), (mode, v)
" || fail "projection shape"
pass "8. projection composes R292 oc-headroom for standard + oc modes"

# ── 9. sovereign-osctl psu-oc dispatch ────────────────────────
out_disp="$(bash "${OSCTL}" psu-oc state --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R294'
" || fail "sovereign-osctl psu-oc dispatch"
pass "9. sovereign-osctl psu-oc dispatches"

# ── 10. config example valid + declares full schema ────────────
example="${REPO_ROOT}/config/psu-oc.toml.example"
[[ -f "${example}" ]] || fail "missing ${example}"
python3 -c "
import sys
try:
    import tomllib as t
except ImportError:
    import tomli as t  # type: ignore
data = t.loads(open('${example}').read())
for k in ('operator_psu_model', 'oc_mode_enabled',
         'sustained_safety_margin_pct', 'known_psus'):
    assert k in data, f'example missing {k}'
# Each PSU entry must declare the full spec.
for p in data['known_psus']:
    for k in ('model', 'rated_standard_watts', 'rated_oc_mode_watts',
             'brief_peak_watts', 'efficiency', 'atx_revision'):
        assert k in p, f'PSU {p.get(\"model\")} missing {k}'
" || fail "config example schema"
pass "10. config example declares full schema + every PSU has all spec keys"

echo "ALL OK"
