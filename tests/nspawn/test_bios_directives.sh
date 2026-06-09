#!/usr/bin/env bash
# R299 (E1.M24) — ASUS X870E-CREATOR WIFI BIOS directives catalog L3.
#
# Operator-named (§1b mandate row): "bios settings directives and
# admonition of things that might also not be possible on some
# board, possibly detecting the ASUS ProArt X870E-CREATOR WIFI and
# its settings and potential optimisations and fixes".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/bios-directives.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope ──────────────────────────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R299'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M24'
assert d['board'] == 'ASUS ProArt X870E-CREATOR WIFI'
assert d['total_count'] >= 10
" || fail "envelope"
pass "1. list --json envelope + board pinned + ≥10 directives"

# ── 2. Operator-named anchor settings all present ────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {x['name'] for x in d['directives']}
for must in ('AMD EXPO', 'SVM Mode', 'IOMMU',
             'Above 4G Decoding', 'Re-Size BAR Support',
             'AVX-512 Support', 'PCIe Gen Speed (PCIEX16_1)',
             'Q-Fan Control (fan curves)'):
    assert must in names, (must, names)
" || fail "anchor names"
pass "2. all 8 operator-named BIOS settings anchored (EXPO/SVM/IOMMU/Above4G/ReBAR/AVX-512/PCIe/fan-curves)"

# ── 3. Each directive carries the operator-required shape ────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for x in d['directives']:
    for k in ('name', 'menu_path', 'recommended', 'default',
              'rationale', 'workload_axis', 'can_probe'):
        assert k in x, (k, x)
    assert isinstance(x['workload_axis'], list)
" || fail "directive shape"
pass "3. every directive has name/menu_path/recommended/default/rationale/workload_axis/can_probe"

# ── 4. --axis filter narrows to one workload axis ────────────
out_ai="$(python3 "${SCRIPT}" list --axis ai-inference --json)"
echo "${out_ai}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for x in d['directives']:
    assert 'ai-inference' in x['workload_axis'], x
assert d['filtered_count'] >= 5
" || fail "axis filter"
pass "4. --axis ai-inference narrows to AI-relevant settings"

# ── 5. show <setting> renders full detail ─────────────────────
out_show="$(python3 "${SCRIPT}" show 'AMD EXPO' --json)"
echo "${out_show}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
x = d['directive']
assert x['name'] == 'AMD EXPO'
assert 'Ai Tweaker' in x['menu_path']
assert x['can_probe'] is True
assert 'JEDEC' in x['rationale']
" || fail "show shape"
pass "5. show <AMD EXPO> renders menu path + rationale + probe info"

# ── 6. check verb runs probes and returns rc reflecting mismatch ──
RC=0
out_check="$(python3 "${SCRIPT}" check --json)" || RC=$?
# rc is 0 (all match) or 1 (≥1 mismatch). Either is acceptable in test env.
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "check rc unexpected: ${RC}"
echo "${out_check}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R299'
assert isinstance(d['results'], list) and d['results']
for r in d['results']:
    assert 'name' in r
    assert 'probe_result' in r
    pr = r['probe_result']
    assert 'probable' in pr
" || fail "check shape"
pass "6. check verb runs probes + emits per-result probe shape"

# ── 7. Unknown setting → rc=1 + structured error ─────────────
RC=0
python3 "${SCRIPT}" show no-such-setting --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "expected rc=1; got ${RC}"
err="$(python3 "${SCRIPT}" show no-such-setting --json 2>&1 1>/dev/null)" || true
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'unknown setting' in d['error']
assert isinstance(d['known'], list)
" || fail "unknown error shape"
pass "7. unknown setting → rc=1 + structured error JSON"

# ── 8. Operator overlay replaces catalog ────────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[directives]]
name              = "operator-custom-bios-setting"
menu_path         = "Custom > Test > Path"
recommended       = "Custom-value"
default           = "Auto"
rationale         = "operator test entry"
workload_axis     = ["test"]
can_probe         = false
operator_caveat   = "test fixture only"
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [x['name'] for x in d['directives']]
assert names == ['operator-custom-bios-setting'], names
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) replaces catalog"

# ── 9. Malformed overlay → defaults + _parse_error ──────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" list --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {x['name'] for x in d['directives']}
assert 'AMD EXPO' in names
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "9. malformed overlay → defaults + _parse_error"

# ── 10. sovereign-osctl bios-directives dispatch + read-only ──
out_disp="$(bash "${OSCTL}" bios-directives list --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R299'
" || fail "sovereign-osctl dispatch"
out2="$(python3 "${SCRIPT}" list --json)"
[[ "${out}" == "${out2}" ]] || fail "list output changed between calls"
pass "10. sovereign-osctl bios-directives dispatch + read-only invariant"

echo "ALL OK"
