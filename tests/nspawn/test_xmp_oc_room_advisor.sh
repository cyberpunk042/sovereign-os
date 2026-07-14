#!/usr/bin/env bash
# R315 (E1.M35) — XMP/OC profile room estimator L3.
#
# Operator-named (§1b mandate row): "considering XMP profile and OC
# profile and room for each and estimated at 100% usage and then
# real time tracking and intelligence around it".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/xmp-oc-room-advisor.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

mk_cfg() {
    local body="$1"
    local cfg
    cfg=$(mktemp --suffix=.toml)
    printf '%s\n' "${body}" > "${cfg}"
    echo "${cfg}"
}

# ── 1. status --json envelope ──────────────────────────────
out="$(python3 "${SCRIPT}" status --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R315'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M35'
for k in ('config', 'load_estimate', 'verdict', 'rc',
          'psu_rated_w', 'safety_ceiling_w',
          'estimated_total_w', 'budget_remaining_w',
          'safe_remaining_w'):
    assert k in d, k
" || fail "envelope"
pass "1. status --json envelope"

# ── 2. Default PSU = 1600W (operator's Dark Power Pro 13) ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['psu_rated_w'] == 1600
" || fail "default psu"
pass "2. default PSU rating = 1600W (operator's Dark Power Pro 13)"

# ── 3. Load breakdown covers CPU+XMP+GPU1+GPU2+misc ────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
load = d['load_estimate']
for k in ('cpu_total_w', 'xmp_extra_w', 'gpu1_w', 'gpu2_w',
          'misc_w', 'estimated_total_w'):
    assert k in load, k
# Total ≈ sum of parts.
calc = (load['cpu_total_w'] + load['xmp_extra_w']
        + load['gpu1_w'] + load['gpu2_w'] + load['misc_w'])
assert abs(load['estimated_total_w'] - calc) < 0.1, (load['estimated_total_w'], calc)
" || fail "breakdown sum"
pass "3. load breakdown covers CPU + XMP + GPU1 + GPU2 + misc; total = sum"

# ── 4. Default config → has-budget verdict ─────────────────
RC=0
python3 "${SCRIPT}" status --json >/dev/null || RC=$?
[[ "${RC}" == "0" ]] || fail "expected has-budget rc=0; got ${RC}"
pass "4. default config (XMP on + stock CPU/GPU OC) → has-budget (rc=0)"

# ── 5. Aggressive OC rises above default but STAYS within budget ───
# SDD-993: with the RTX PRO 6000 Max-Q (300 W) primary + RTX 5090 (350 W)
# secondary, even 1.2x CPU + +20% GPU OC under dual GPU stays comfortably
# under the 1600 W PSU — the Max-Q part is why the rig has wide headroom.
# (The over-budget verdict path is exercised by the 850 W-PSU test below.)
cfg=$(mk_cfg 'xmp_enabled = true
cpu_oc_multiplier = 1.2
gpu_oc_notch = 2
dual_gpu_active = true')
RC=0
out_a="$(python3 "${SCRIPT}" status --config "${cfg}" --json)" || RC=$?
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Aggressive OC lifts the total above the ~907 W default but stays in budget.
assert d['verdict'] in ('has-budget', 'tight'), d
assert 1000 < d['estimated_total_w'] < 1600, d['estimated_total_w']
" || fail "aggressive"
rm -f "${cfg}"
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "expected rc 0 or 1 (within budget); got ${RC}"
pass "5. aggressive (1.2x CPU + +20% GPU + XMP + dual GPU) → above default, still within 1600W (Max-Q headroom)"

# ── 6. Single-GPU config drops total significantly ─────────
cfg=$(mk_cfg 'dual_gpu_active = false')
out_s="$(python3 "${SCRIPT}" status --config "${cfg}" --json)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
load = d['load_estimate']
# GPU2 contribution should be 0 when dual_gpu_active=false.
assert load['gpu2_w'] == 0, load
# Total should drop by ~600W relative to default.
assert load['estimated_total_w'] < 800, load['estimated_total_w']
" || fail "single gpu"
rm -f "${cfg}"
pass "6. single-GPU config → GPU2=0W, total drops below 800W"

# ── 7. budget verb returns budget shape ─────────────────────
out_b="$(python3 "${SCRIPT}" budget --json)"
echo "${out_b}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R315'
for k in ('psu_rated_w', 'estimated_total_w', 'budget_remaining_w',
          'safe_remaining_w', 'verdict', 'rc'):
    assert k in d, k
" || fail "budget shape"
pass "7. budget verb returns budget shape (PSU rated / load / remaining)"

# ── 8. recommend verb evaluates combo matrix + picks aggressive-safe ──
out_r="$(python3 "${SCRIPT}" recommend --json)"
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R315'
assert d['total_combos_evaluated'] == 2 * 3 * 3  # xmp × cpu_oc × gpu_oc
assert d['safe_combos_count'] >= 1
# Aggressive-safe pick exists.
rec = d['recommended_aggressive_safe']
assert rec is not None
assert rec['safe'] is True
for c in d['all_combos']:
    for k in ('xmp', 'cpu_oc_multiplier', 'gpu_oc_notch',
              'estimated_total_w', 'verdict', 'safe'):
        assert k in c, (k, c)
" || fail "recommend shape"
pass "8. recommend evaluates 18-combo matrix + picks aggressive-safe combo"

# ── 9. Operator overlay overrides PSU rating ──────────────
cfg=$(mk_cfg 'psu_rated_w = 850
xmp_enabled = true
dual_gpu_active = true')
RC=0
out_psu="$(python3 "${SCRIPT}" status --config "${cfg}" --json)" || RC=$?
echo "${out_psu}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['psu_rated_w'] == 850, d
# 850W can't handle dual GPU at sustained load → over-budget.
assert d['verdict'] == 'over-budget', d['verdict']
" || fail "overlay psu"
rm -f "${cfg}"
[[ "${RC}" == "2" ]] || fail "expected rc=2 over-budget; got ${RC}"
pass "9. operator overlay sets psu_rated_w=850 → over-budget (rc=2) for dual GPU"

# ── 10. sovereign-osctl xmp-oc-room dispatch ────────────────
out_disp="$(bash "${OSCTL}" xmp-oc-room status --json 2>/dev/null || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R315'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl xmp-oc-room dispatches"

echo "ALL OK"
