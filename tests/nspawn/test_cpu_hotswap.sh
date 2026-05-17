#!/usr/bin/env bash
# R307 (E1.M31) — CPU hotswap mode detection L3.
#
# Operator-named (§1b mandate row): "Hotswap, CPU mode and option(s)".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/cpu-hotswap.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope (graceful no-cpus fallback) ──
out="$(python3 "${SCRIPT}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R307'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M31'
for k in ('cpus', 'cpu_count', 'transitions', 'verdict', 'rc',
          'modes_catalog'):
    assert k in d, k
" || fail "envelope"
pass "1. status --json envelope (graceful /sys-absent fallback)"

# ── 2. modes_catalog covers operator-named 4 governors + 4 EPP ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
gov_modes = {m['mode'] for m in d['modes_catalog'] if m['axis'] == 'governor'}
epp_modes = {m['mode'] for m in d['modes_catalog'] if m['axis'] == 'epp'}
assert {'performance', 'schedutil', 'powersave', 'ondemand'} <= gov_modes, gov_modes
assert {'performance', 'balance_performance', 'balance_power', 'power'} <= epp_modes, epp_modes
# Each has rationale.
for m in d['modes_catalog']:
    assert m['rationale']
" || fail "modes catalog"
pass "2. modes catalog: 4 governors + 4 EPP modes with per-mode rationale"

# ── 3. swap-hint emits operator-runnable commands ──────────
out_p="$(python3 "${SCRIPT}" swap-hint performance --json)"
echo "${out_p}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode'] == 'performance'
assert d['scope'] == 'governor'
assert 'scaling_governor' in d['command']
assert 'cpupower' in d['alt_persistent']
" || fail "swap-hint governor"
out_e="$(python3 "${SCRIPT}" swap-hint balance_performance --scope epp --json)"
echo "${out_e}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode'] == 'balance_performance'
assert d['scope'] == 'epp'
assert 'energy_performance_preference' in d['command']
" || fail "swap-hint epp"
pass "3. swap-hint emits scaling_governor + energy_performance_preference commands"

# ── 4. transitions verb reports drivers + common modes ─────
out_t="$(python3 "${SCRIPT}" transitions --json || true)"
echo "${out_t}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R307'
trans = d['transitions']
for k in ('governors_common', 'epp_common', 'drivers'):
    assert k in trans
" || fail "transitions shape"
pass "4. transitions verb returns governors_common / epp_common / drivers"

# ── 5. per-cpu --cpu N narrows to one CPU when present ──────
out_pc="$(python3 "${SCRIPT}" per-cpu --json || true)"
echo "${out_pc}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R307'
# When no CPUs are probable, cpus = [] (graceful).
assert isinstance(d['cpus'], list)
" || fail "per-cpu shape"
pass "5. per-cpu verb returns list (graceful when /sys absent)"

# ── 6. probe_cpus unit on a synthetic /sys/devices/system/cpu tree ──
python3 -c "
import sys, importlib.util, tempfile, pathlib, os
spec = importlib.util.spec_from_file_location('cm', 'scripts/hardware/cpu-hotswap.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# We can't easily fake /sys without mock, so test the derive_* path.
fake_cpus = [
    {'cpu': 0, 'governor': 'performance', 'epp': 'performance',
     'driver': 'amd-pstate-epp', 'freq_cur_khz': 4500000,
     'freq_max_khz': 5500000, 'freq_min_khz': 400000,
     'governors_available': ['performance', 'powersave'],
     'epp_available': ['performance', 'balance_performance']},
    {'cpu': 1, 'governor': 'performance', 'epp': 'balance_performance',
     'driver': 'amd-pstate-epp', 'freq_cur_khz': 4500000,
     'freq_max_khz': 5500000, 'freq_min_khz': 400000,
     'governors_available': ['performance', 'schedutil'],
     'epp_available': ['performance', 'balance_performance']},
]
trans = m.derive_transitions(fake_cpus)
# common = intersection of available lists
assert trans['governors_common'] == ['performance'], trans
assert sorted(trans['epp_common']) == ['balance_performance', 'performance'], trans
assert trans['drivers'] == ['amd-pstate-epp']
print('PASS')
" || fail "derive_transitions"
pass "6. derive_transitions intersects per-CPU governor / EPP availability"

# ── 7. derive_verdict drift detection ─────────────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('cm', 'scripts/hardware/cpu-hotswap.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

fake_cpus = [
    {'cpu': 0, 'governor': 'performance', 'epp': 'performance',
     'driver': 'amd-pstate-epp', 'freq_cur_khz': 4500000,
     'freq_max_khz': 5500000, 'freq_min_khz': 400000,
     'governors_available': [], 'epp_available': []},
    {'cpu': 1, 'governor': 'powersave', 'epp': 'balance_performance',
     'driver': 'amd-pstate-epp', 'freq_cur_khz': 400000,
     'freq_max_khz': 5500000, 'freq_min_khz': 400000,
     'governors_available': [], 'epp_available': []},
]
# pin governor=performance — cpu1 drifts.
cfg = {'pinned_mode': 'performance', 'pinned_epp': ''}
v = m.derive_verdict(fake_cpus, cfg)
assert v['verdict'] == 'drift', v
assert v['rc'] == 1
assert len(v['drift']) == 1
assert v['drift'][0]['cpu'] == 1
# no pin → no-pin.
v2 = m.derive_verdict(fake_cpus, {'pinned_mode': '', 'pinned_epp': ''})
assert v2['verdict'] == 'no-pin'
assert v2['rc'] == 0
print('PASS')
" || fail "derive_verdict"
pass "7. derive_verdict: pin→drift detection + no-pin→accept-all"

# ── 8. Operator overlay controls pinned mode ──────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
pinned_mode = "performance"
pinned_epp  = "balance_performance"
TOML

out_ov="$(python3 "${SCRIPT}" status --config "${overlay}" --json || true)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['config']['pinned_mode'] == 'performance'
assert d['config']['pinned_epp'] == 'balance_performance'
" || fail "overlay knob"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) sets pinned_mode + pinned_epp"

# ── 9. Malformed overlay → defaults + _parse_error ─────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" status --config "${bad}" --json || true)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['config']['pinned_mode'] == ''
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "9. malformed overlay → defaults + _parse_error"

# ── 10. sovereign-osctl cpu-hotswap dispatch ──────────────
out_disp="$(bash "${OSCTL}" cpu-hotswap status --json 2>/dev/null || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R307'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl cpu-hotswap dispatches"

echo "ALL OK"
