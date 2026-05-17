#!/usr/bin/env bash
# R300 (E1.M25) — holistic operator-posture rollup L3.
#
# Operator-named (§1b mandate row): "Everything via dashboard/
# UInterface or terminal tools OR AI".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/operator-posture.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"
SERVE="${REPO_ROOT}/scripts/dashboard/serve.py"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope ────────────────────────────────
out="$(python3 "${SCRIPT}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R300'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M25'
for k in ('axes', 'verdict', 'rc', 'message'):
    assert k in d, k
" || fail "envelope"
pass "1. status --json envelope"

# ── 2. All 5 expected axes present ───────────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
want = {'oc_headroom', 'psu_oc', 'thermal_oc', 'storage_health', 'bios_directives'}
got = set(d['axes'].keys())
assert want == got, (want - got, got - want)
" || fail "axes mismatch"
pass "2. axes = {oc_headroom, psu_oc, thermal_oc, storage_health, bios_directives}"

# ── 3. Each axis has posture ∈ {ok, watch, degraded, unknown} ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
allowed = {'ok', 'watch', 'degraded', 'unknown'}
for name, axis in d['axes'].items():
    assert axis['posture'] in allowed, (name, axis['posture'])
    assert 'probe' in axis
" || fail "axis posture shape"
pass "3. every axis has posture ∈ {ok, watch, degraded, unknown}"

# ── 4. Combined verdict matches worst-axis severity ──────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
weight = {'ok': 0, 'unknown': 1, 'watch': 1, 'degraded': 2}
sev = max(weight.get(a['posture'], 1) for a in d['axes'].values())
expected = {2: 'degraded', 1: 'watch', 0: 'ok'}[sev]
assert d['verdict'] == expected, (sev, d['verdict'], expected)
assert d['rc'] == sev, (sev, d['rc'])
" || fail "combined-verdict math"
pass "4. combined verdict matches worst-axis severity"

# ── 5. advisory verb returns axes_summary ────────────────────
out_adv="$(python3 "${SCRIPT}" advisory --json || true)"
echo "${out_adv}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R300'
assert isinstance(d['axes_summary'], dict)
assert set(d['axes_summary'].keys()) == {'oc_headroom', 'psu_oc',
    'thermal_oc', 'storage_health', 'bios_directives'}
" || fail "advisory shape"
pass "5. advisory verb returns axes_summary"

# ── 6. sovereign-osctl operator-posture dispatch ─────────────
out_disp="$(bash "${OSCTL}" operator-posture status --json || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R300'
" || fail "sovereign-osctl dispatch"
pass "6. sovereign-osctl operator-posture dispatches"

# ── 7. Dashboard card renders rollup data ───────────────────
html="$(python3 "${SERVE}" --render-only)" || fail "render-only"
grep -q 'Operator posture rollup' <<<"${html}" \
    || fail "dashboard missing operator-posture card title"
grep -q 'id="card-operator-posture"' <<<"${html}" \
    || fail "dashboard missing operator-posture section id"
pass "7. dashboard renders the new operator-posture card"

# ── 8. Existing dashboard cards still present (no regression) ──
for cid in card-gpu card-network card-cpu card-fs card-bios card-power; do
    grep -q "id=\"${cid}\"" <<<"${html}" \
        || fail "missing existing dashboard card id=${cid}"
done
pass "8. existing dashboard cards still present (no regression)"

# ── 9. Read-only invariant (two status calls match) ────────
out2="$(python3 "${SCRIPT}" status --json || true)"
python3 -c "
import json, sys
a = json.loads('''$(echo "${out}" | sed "s/'/'\"'\"'/g")''')
b = json.loads('''$(echo "${out2}" | sed "s/'/'\"'\"'/g")''')
# Strip per-call volatile fields (oc-headroom carries current_draw_watts
# and current_deviance_pct which may differ between calls).
for d in (a, b):
    if 'thermal_oc' in d['axes']:
        d['axes']['thermal_oc'].pop('message', None)
assert a == b, 'two status calls diverge modulo volatile fields'
" || fail "read-only invariant"
pass "9. read-only invariant (two status calls match modulo volatile fields)"

echo "ALL OK"
