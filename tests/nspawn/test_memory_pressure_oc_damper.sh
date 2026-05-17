#!/usr/bin/env bash
# R304 (E1.M29) — memory-pressure → OC dampening advisor L3.
#
# Operator-named (§1b mandate row — continuous compose of "memory"
# axis with "OC profile and room for each").

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/memory-pressure-oc-damper.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope ───────────────────────────────
out="$(python3 "${SCRIPT}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R304'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M29'
for k in ('verdict', 'rc', 'message', 'sources'):
    assert k in d, k
" || fail "envelope"
pass "1. status --json envelope"

# ── 2. Verdict is one of expected outcomes ──────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
allowed = {'no-dampening', 'dampen-by-1', 'dampen-fully',
           'memory-probe-unavailable', 'memory-pressure-unparsed'}
assert d['verdict'] in allowed, d['verdict']
assert d['rc'] in (0, 1, 2)
" || fail "verdict outside matrix"
pass "2. verdict ∈ {no-dampening, dampen-by-1, dampen-fully, memory-probe-unavailable, memory-pressure-unparsed}"

# ── 3. Sources surfaced ─────────────────────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
sources = d['sources']
for k in ('memory_pressure', 'oc_headroom'):
    assert k in sources, k
" || fail "sources missing"
pass "3. sources surface (memory_pressure + oc_headroom provenance)"

# ── 4. Recommendation derivation: synthetic CRITICAL → dampen-fully ──
python3 -c "
import sys, importlib.util
spec = importlib.util.spec_from_file_location('damp', 'scripts/hardware/memory-pressure-oc-damper.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Synthetic R269 output with verdict='critical'.
memp = {'verdict': 'critical', 'metrics': {'psi_full_avg10_pct': 70.0}}
oc = {'verdict': 'headroom-safe',
      'config': {'gpu_oc_multiplier': 1.15},
      'headroom': {'gpu_oc_multiplier': 1.15}}
cfg = m.DEFAULTS
rec = m.derive_recommendation(memp, oc, cfg)
assert rec['verdict'] == 'dampen-fully', rec
assert rec['rc'] == 2
assert rec['recommended_oc_multiplier'] == 1.0
print('PASS')
" || fail "synthetic critical"
pass "4. R269 verdict=critical → dampen-fully (recommended_oc_multiplier=1.0, rc=2)"

# ── 5. Synthetic WARN → dampen-by-1 ─────────────────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('damp', 'scripts/hardware/memory-pressure-oc-damper.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
memp = {'verdict': 'warn', 'metrics': {'psi_full_avg10_pct': 40.0}}
oc = {'verdict': 'headroom-safe',
      'config': {'gpu_oc_multiplier': 1.15},
      'headroom': {'gpu_oc_multiplier': 1.15}}
rec = m.derive_recommendation(memp, oc, m.DEFAULTS)
assert rec['verdict'] == 'dampen-by-1', rec
assert rec['rc'] == 1
# 1.15 - 0.05 = 1.10
assert abs(rec['recommended_oc_multiplier'] - 1.10) < 0.01
print('PASS')
" || fail "synthetic warn"
pass "5. R269 verdict=warn → dampen-by-1 (1.15 - 0.05 = 1.10, rc=1)"

# ── 6. Synthetic OK → no-dampening ───────────────────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('damp', 'scripts/hardware/memory-pressure-oc-damper.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
memp = {'verdict': 'ok', 'metrics': {'psi_full_avg10_pct': 5.0}}
oc = {'verdict': 'headroom-safe',
      'config': {'gpu_oc_multiplier': 1.0},
      'headroom': {'gpu_oc_multiplier': 1.0}}
rec = m.derive_recommendation(memp, oc, m.DEFAULTS)
assert rec['verdict'] == 'no-dampening', rec
assert rec['rc'] == 0
print('PASS')
" || fail "synthetic ok"
pass "6. R269 verdict=ok → no-dampening (rc=0)"

# ── 7. Probe-unavailable fallback ───────────────────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('damp', 'scripts/hardware/memory-pressure-oc-damper.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
rec = m.derive_recommendation(None, None, m.DEFAULTS)
assert rec['verdict'] == 'memory-probe-unavailable'
assert rec['rc'] == 1
print('PASS')
" || fail "probe-unavailable"
pass "7. memory probe unavailable → verdict=memory-probe-unavailable (rc=1)"

# ── 8. Operator overlay controls thresholds ────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
memory_pressure_warn_avg10 = 50.0
memory_pressure_crit_avg10 = 80.0
dampen_step_mild           = 0.10
TOML

out_ov="$(python3 "${SCRIPT}" status --config "${overlay}" --json || true)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cfg = d['config']
assert cfg['memory_pressure_warn_avg10'] == 50.0
assert cfg['dampen_step_mild'] == 0.10
" || fail "overlay knob takeover"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) controls thresholds"

# ── 9. Malformed overlay → defaults + _parse_error ─────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" status --config "${bad}" --json || true)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['config']['memory_pressure_warn_avg10'] == 30.0
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "9. malformed overlay → defaults + _parse_error"

# ── 10. sovereign-osctl memory-pressure-damper dispatch ────
out_disp="$(bash "${OSCTL}" memory-pressure-damper status --json || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R304'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl memory-pressure-damper dispatches"

echo "ALL OK"
