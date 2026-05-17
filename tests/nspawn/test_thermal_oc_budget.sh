#!/usr/bin/env bash
# R296 (E2.M10) — heat budget tied to OC profile L3.
#
# Operator-named (§1b mandate row, on R292/R294): "considering XMP
# profile and OC profile and room for each and estimated at 100%
# usage and then real time tracking and intelligence around it.
# (Possibly heat too I guess)".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/thermal-oc-budget.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope ────────────────────────────────
out="$(python3 "${SCRIPT}" status --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R296'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M10'
for k in ('thermal', 'psu_headroom_verdict', 'verdict', 'rc', 'sources', 'config'):
    assert k in d, k
" || fail "status envelope"
pass "1. status --json envelope"

# ── 2. Combined verdict is one of the matrix outcomes ──────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
allowed = {'safe', 'thermal-watch', 'psu-watch', 'both-tight',
           'pull-oc-now', 'probes-unavailable'}
assert d['verdict'] in allowed, d['verdict']
# rc reflects severity.
assert d['rc'] in (0, 1, 2), d['rc']
" || fail "combined verdict outside matrix"
pass "2. combined verdict ∈ {safe, thermal-watch, psu-watch, both-tight, pull-oc-now, probes-unavailable}"

# ── 3. Per-source provenance surfaced ────────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
sources = d['sources']
for k in ('thermal', 'oc_headroom', 'psu_oc'):
    assert k in sources, k
    v = sources[k]
    assert v.startswith('scripts/') or v == '(unavailable)'
" || fail "sources provenance missing"
pass "3. per-source provenance surfaced (thermal / oc_headroom / psu_oc)"

# ── 4. Operator overlay controls thermal margins ─────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
cpu_tjmax_c                   = 100
cpu_tjmax_watch_margin_c      = 15
cpu_tjmax_critical_margin_c   = 5
gpu_temp_watch_c              = 70
gpu_temp_critical_c           = 85
TOML

out_ov="$(python3 "${SCRIPT}" status --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cfg = d['config']
assert cfg['cpu_tjmax_c'] == 100
assert cfg['cpu_tjmax_watch_margin_c'] == 15
assert cfg['gpu_temp_critical_c'] == 85
" || fail "overlay knob takeover"
rm -f "${overlay}"
pass "4. operator overlay (R283/SDD-030) controls thermal margins"

# ── 5. Malformed overlay → defaults + _parse_error ──────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" status --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['config']['cpu_tjmax_c'] == 95
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "5. malformed overlay → defaults + _parse_error"

# ── 6. advisory verb returns minimal envelope + verdict ──────
out_adv="$(python3 "${SCRIPT}" advisory --json)"
echo "${out_adv}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R296'
assert d['verdict'] in {'safe', 'thermal-watch', 'psu-watch', 'both-tight',
                       'pull-oc-now', 'probes-unavailable'}
assert 'message' in d
" || fail "advisory shape"
pass "6. advisory --json carries verdict + message"

# ── 7. inputs verb shows provenance ──────────────────────────
out_in="$(python3 "${SCRIPT}" inputs --json)"
echo "${out_in}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'sources' in d
assert 'thermal' in d
assert 'psu_headroom_verdict' in d
" || fail "inputs shape"
pass "7. inputs verb surfaces provenance + per-probe values"

# ── 8. sovereign-osctl thermal-oc-budget dispatch ────────────
out_disp="$(bash "${OSCTL}" thermal-oc-budget status --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R296'
" || fail "sovereign-osctl thermal-oc-budget dispatch"
pass "8. sovereign-osctl thermal-oc-budget dispatches"

# ── 9. Read-only invariant (two status calls identical modulo
#       real-time fields) ────────────────────────────────────
out2="$(python3 "${SCRIPT}" status --json)"
python3 -c "
import json, sys
a = json.loads('''$(echo "${out}" | sed "s/'/'\"'\"'/g")''')
b = json.loads('''$(echo "${out2}" | sed "s/'/'\"'\"'/g")''')
# Strip volatile fields.
for d in (a, b):
    d['thermal'].pop('hottest_cpu_c', None)
    d['thermal'].pop('hottest_gpu_c', None)
assert a == b, 'two status calls diverge modulo real-time'
" || fail "read-only invariant"
pass "9. read-only invariant (two status calls match modulo real-time °C)"

echo "ALL OK"
