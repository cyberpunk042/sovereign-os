#!/usr/bin/env bash
# R292 (E1.M20) — OC + XMP headroom model L3 test.
#
# Operator-named (§1b mandate row, verbatim): "considering XMP profile
# and OC profile and room for each and estimated at 100% usage and
# then real time tracking and intelligence around it. (Possibly heat
# too I guess)".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/oc-headroom.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope (round / schema / verdict / inputs / headroom) ──
out="$(python3 "${SCRIPT}" status --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R292'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M20'
for k in ('config', 'inputs', 'headroom', 'verdict', 'message', 'rc'):
    assert k in d, k
" || fail "status envelope"
pass "1. status --json envelope"

# ── 2. Headroom calc tracks the projected 100% formula ──────────
# With defaults (no GPU detected in CI, no memory probe in
# unprivileged CI), the model should still produce a number.
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
h = d['headroom']
# Identities the model promises.
assert h['cpu_tdp_watts'] == d['config']['cpu_tdp_watts']
assert h['chassis_baseline_watts'] == d['config']['chassis_baseline_watts']
# Projected = cpu + gpu_total + memory + chassis (within float tol).
expected = (h['cpu_tdp_watts'] + h['gpu_total_projected_watts']
            + h['memory_watts'] + h['chassis_baseline_watts'])
assert abs(h['projected_100pct_watts'] - expected) < 1.0, (h, expected)
# headroom = psu_rated × oc_mode_mult - projected.
assert abs(h['psu_headroom_watts']
           - (h['psu_rated_watts'] - h['projected_100pct_watts'])) < 1.0
" || fail "headroom math"
pass "2. headroom math is internally consistent"

# ── 3. operator-overlay (R283/SDD-030) controls every knob ──────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
cpu_tdp_watts          = 230
chassis_baseline_watts = 100
gpu_oc_multiplier      = 1.20
psu_oc_mode_multiplier = 1.05
safety_margin_pct      = 25
psu_rated_watts        = 1300
TOML

out_ov="$(python3 "${SCRIPT}" status --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cfg = d['config']
assert cfg['cpu_tdp_watts'] == 230, cfg
assert cfg['chassis_baseline_watts'] == 100, cfg
assert cfg['gpu_oc_multiplier'] == 1.20, cfg
assert cfg['psu_oc_mode_multiplier'] == 1.05, cfg
assert cfg['safety_margin_pct'] == 25, cfg
# psu_rated_watts is reloaded from overlay; the probe-discovered
# value takes precedence ONLY when power-status.py was reachable,
# which it isn't in this CI test env — so overlay wins here.
assert d['headroom']['psu_rated_watts'] == 1300 * 1.05, d['headroom']
" || fail "overlay didn't take effect"
rm -f "${overlay}"
pass "3. operator overlay (R283/SDD-030) controls every knob"

# ── 4. over-budget verdict + rc=2 when projected > psu_rated ────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
psu_rated_watts        = 50   # absurdly low → over-budget
psu_oc_mode_multiplier = 1.0
TOML
RC=0
python3 "${SCRIPT}" status --config "${overlay}" --json >/dev/null || RC=$?
[[ "${RC}" == "2" ]] || fail "expected rc=2 (over-budget); got ${RC}"
# advisory also exits 2 for over-budget — `|| true` defangs set -e.
out_ob="$(python3 "${SCRIPT}" advisory --config "${overlay}" --json || true)"
echo "${out_ob}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['verdict'] == 'over-budget', d
assert 'EXCEEDS PSU' in d['message'], d
" || fail "over-budget verdict shape"
rm -f "${overlay}"
pass "4. over-budget verdict + rc=2 + actionable message"

# ── 5. headroom-tight verdict + rc=1 when margin < safety_margin_pct ──
# Bump safety to a huge value so the default config trips tight.
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
safety_margin_pct = 99
TOML
RC=0
python3 "${SCRIPT}" status --config "${overlay}" --json >/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "expected rc=1 (headroom-tight); got ${RC}"
echo "${out_ob}" >/dev/null  # silence unused
rm -f "${overlay}"
pass "5. headroom-tight verdict + rc=1 when margin < safety_margin_pct"

# ── 6. Malformed overlay falls back + parse_error ───────────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" status --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Defaults still apply.
assert d['config']['cpu_tdp_watts'] == 170
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "6. malformed overlay → defaults + _parse_error (no crash)"

# ── 7. inputs verb shows per-source provenance ──────────────────
out_in="$(python3 "${SCRIPT}" inputs --json)"
echo "${out_in}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
inp = d['inputs']
assert 'sources' in inp
# Every source key must be either a real script path or '(unavailable)'
# / '(operator-overlay default)' / '(no real-time sampler data)'.
for k, v in inp['sources'].items():
    assert v.startswith('scripts/') or v.startswith('(')
# The probe-sources expected.
for k in ('memory', 'gpu', 'psu_rated', 'current_draw'):
    assert k in inp['sources'], k
" || fail "inputs provenance"
pass "7. inputs verb surfaces per-source provenance"

# ── 8. sovereign-osctl oc-headroom dispatch ─────────────────────
out_disp="$(bash "${OSCTL}" oc-headroom advisory --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R292'
assert d['verdict'] in ('headroom-safe', 'headroom-tight', 'over-budget')
" || fail "sovereign-osctl oc-headroom dispatch"
pass "8. sovereign-osctl oc-headroom dispatches"

# ── 9. config example valid + declares every knob ───────────────
example="${REPO_ROOT}/config/oc-headroom.toml.example"
[[ -f "${example}" ]] || fail "missing ${example}"
python3 -c "
import sys
try:
    import tomllib as t
except ImportError:
    import tomli as t  # type: ignore
data = t.loads(open('${example}').read())
for k in ('cpu_tdp_watts', 'chassis_baseline_watts', 'gpu_oc_multiplier',
         'psu_oc_mode_multiplier', 'safety_margin_pct',
         'memory_dimm_base_watts', 'memory_mts_premium_per_1000',
         'psu_rated_watts'):
    assert k in data, f'example missing {k}'
" || fail "config example schema"
pass "9. config example declares every knob the script reads"

# ── 10. Probes are read-only (two status calls identical apart from ──
# the volatile current_draw_watts field — drop that for the compare).
out2="$(python3 "${SCRIPT}" status --json)"
python3 -c "
import json
a = json.loads('''$(echo "${out}" | sed "s/'/'\"'\"'/g")''')
b = json.loads('''$(echo "${out2}" | sed "s/'/'\"'\"'/g")''')
# Strip volatile real-time sampler fields (CPU current draw + per-GPU
# power draw fluctuates between calls; we only care that probes don't
# mutate persistent state).
for d in (a, b):
    d['inputs'].pop('current_draw_watts', None)
    d['headroom'].pop('current_draw_watts', None)
    d['headroom'].pop('current_deviance_pct', None)
    for g in d['inputs'].get('gpus') or []:
        g.pop('power_draw_watts', None)
assert a == b, 'two status calls diverge beyond the real-time sampler field'
" || fail "two status calls diverge (probes mutated state?)"
pass "10. probes are read-only (two status calls match modulo real-time sampler)"

echo "ALL OK"
