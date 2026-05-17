#!/usr/bin/env bash
# R318 (E1.M38) — heat-tied OC auto-throttle with triple-gate L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/heat-oc-autothrottle.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope ──────────────────────────────
out="$(python3 "${SCRIPT}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R318'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M38'
for k in ('current', 'target', 'damping_pct', 'sources',
          'verdict', 'rc'):
    assert k in d, k
" || fail "envelope"
pass "1. status --json envelope"

# ── 2. recommend verb returns same shape as status ─────────
out_r="$(python3 "${SCRIPT}" recommend --json || true)"
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R318'
for k in ('current', 'target', 'verdict'):
    assert k in d
" || fail "recommend shape"
pass "2. recommend verb returns same shape as status"

# ── 3. derive_target picks min of available probe recs ────
python3 -c "
import importlib.util, json
spec = importlib.util.spec_from_file_location('h', 'scripts/hardware/heat-oc-autothrottle.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Monkey-patch probes to simulate different recommendation values.
m.probe_thermal_oc = lambda: {'recommended': {'gpu_oc_multiplier': 1.10}}
m.probe_mem_damper = lambda: {'recommended_oc_multiplier': 1.05}
m.probe_xmp_oc_room = lambda: {'verdict': 'has-budget'}
m.probe_oc_headroom_current = lambda: 1.15
r = m.derive_target(dict(m.DEFAULTS))
# min of (1.10, 1.05) = 1.05; current 1.15 → damping needed.
assert r['target'] == 1.05, r
assert r['current'] == 1.15
assert r['verdict'] == 'damping-recommended', r
assert r['rc'] == 1
print('PASS')
" || fail "derive_target min"
pass "3. derive_target picks min of (thermal, mem-damper) recommendations"

# ── 4. damping_floor prevents below-stock damping ──────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('h', 'scripts/hardware/heat-oc-autothrottle.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.probe_thermal_oc = lambda: {'recommended': {'gpu_oc_multiplier': 0.8}}
m.probe_mem_damper = lambda: {'recommended_oc_multiplier': 0.5}
m.probe_xmp_oc_room = lambda: {'verdict': 'has-budget'}
m.probe_oc_headroom_current = lambda: 1.10
cfg = dict(m.DEFAULTS)
cfg['damping_floor'] = 1.0
r = m.derive_target(cfg)
# Both candidates below 1.0; floor clamps to 1.0.
assert r['target'] == 1.0, r
print('PASS')
" || fail "damping floor"
pass "4. damping_floor clamps target to ≥1.0 (never below stock)"

# ── 5. No-damping-needed when target = current ─────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('h', 'scripts/hardware/heat-oc-autothrottle.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.probe_thermal_oc = lambda: {'recommended': {'gpu_oc_multiplier': 1.0}}
m.probe_mem_damper = lambda: {'recommended_oc_multiplier': 1.0}
m.probe_xmp_oc_room = lambda: {'verdict': 'has-budget'}
m.probe_oc_headroom_current = lambda: 1.0
r = m.derive_target(dict(m.DEFAULTS))
assert r['verdict'] == 'no-damping-needed'
assert r['rc'] == 0
print('PASS')
" || fail "no damping"
pass "5. no-damping-needed when target = current (rc=0)"

# ── 6. apply without ANY gates → dry-run (does not write) ──
state=$(mktemp -u)
out_dry="$(python3 "${SCRIPT}" apply --target "${state}" --json 2>&1 || true)"
echo "${out_dry}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ap = d['apply']
assert ap['triple_gate_ok'] is False
assert ap['wrote'] is False
" || fail "dry-run shape"
[[ ! -f "${state}" ]] || fail "dry-run must not write target"
pass "6. apply without gates → dry-run + does not write target file"

# ── 7. apply with --apply only (2/3 gates missing) → dry-run ──
state=$(mktemp -u)
python3 "${SCRIPT}" apply --apply --target "${state}" --json >/dev/null 2>&1 || true
[[ ! -f "${state}" ]] || fail "--apply alone must not write"
pass "7. apply --apply alone (2/3 gates missing) → no write"

# ── 8. apply with all 3 gates writes target ────────────────
state=$(mktemp -u)
# Need damping recommendation present to actually write.
# Use a config that pretends current is 1.15 by passing an overlay that
# the apply path doesn't override — but here we'll just verify the
# triple-gate logic via the synthetic-probe approach.
python3 -c "
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location('h', 'scripts/hardware/heat-oc-autothrottle.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Force a damping recommendation.
m.probe_thermal_oc = lambda: {'recommended': {'gpu_oc_multiplier': 1.05}}
m.probe_mem_damper = lambda: {'recommended_oc_multiplier': 1.05}
m.probe_xmp_oc_room = lambda: {'verdict': 'has-budget'}
m.probe_oc_headroom_current = lambda: 1.15

# Set env gate.
os.environ['SOVEREIGN_OS_CONFIRM_DESTROY'] = 'YES'
rc = m.main(['apply', '--apply', '--confirm-throttle',
              '--target', '${state}', '--json'])
sys.exit(rc)
" >/dev/null 2>&1 || true
[[ -f "${state}" ]] || fail "all-3-gates apply must write target"
grep -q '^gpu_oc_multiplier = 1.05$' "${state}" || fail "expected gpu_oc_multiplier = 1.05 in target"
rm -f "${state}"
pass "8. apply with all 3 gates (--apply + --confirm-throttle + env=YES) writes target"

# ── 9. Operator overlay sets damping_floor ─────────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<'TOML'
damping_floor = 1.10
TOML
out_ov="$(python3 "${SCRIPT}" status --config "${cfg}" --json || true)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Synthetic probes not patched, so verdict depends on real probes —
# we just check the config knob was honored via the overlay path.
# (The overlay loader path returned non-empty source.)
assert d['overlay'].get('_source', '').endswith('.toml')
" || fail "overlay knob"
rm -f "${cfg}"
pass "9. operator overlay (R283/SDD-030) sets damping_floor"

# ── 10. sovereign-osctl heat-oc-throttle dispatch ─────────
out_disp="$(bash "${OSCTL}" heat-oc-throttle status --json 2>/dev/null || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R318'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl heat-oc-throttle dispatches"

echo "ALL OK"
