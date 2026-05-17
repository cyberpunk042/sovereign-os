#!/usr/bin/env bash
# R337 (E1.M39) — fan/cooling awareness advisor L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/fan-advisor.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. modes --json envelope + 4 operator-named modes ─────
out="$(python3 "${SCRIPT}" modes --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R337'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M39'
assert d['mode_count'] == 4
names = {m['mode'] for m in d['modes']}
assert names == {'idle', 'inference-ready', 'training', 'oc-burst'}, names
" || fail "modes"
pass "1. modes --json + 4 operator-named modes (idle/inference-ready/training/oc-burst)"

# ── 2. Each mode has full schema ───────────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for m in d['modes']:
    for k in ('mode', 'axis', 'description', 'cpu_target_c_max',
              'gpu_target_c_max', 'fan_duty_pct_chassis',
              'fan_duty_pct_cpu', 'fan_duty_pct_gpu', 'operator_caveat'):
        assert k in m, (k, m['mode'])
    # Reasonable bounds.
    assert 30 <= m['cpu_target_c_max'] <= 95
    assert 0 <= m['fan_duty_pct_cpu'] <= 100
" || fail "mode schema"
pass "2. each mode has full schema (description + temps + duty% + caveat)"

# ── 3. recommend default mode = inference-ready ────────────
out="$(python3 "${SCRIPT}" recommend --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode']['mode'] == 'inference-ready'
" || fail "default mode"
pass "3. recommend default → inference-ready (operator's stated SAIN-01 default)"

# ── 4. recommend --mode training overrides ────────────────
out="$(python3 "${SCRIPT}" recommend --mode training --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['mode']
assert m['mode'] == 'training'
# Training mode should be hotter + higher duty than idle.
assert m['cpu_target_c_max'] > 65
assert m['fan_duty_pct_chassis'] >= 70
" || fail "training mode"
pass "4. recommend --mode training overrides + hotter than inference-ready"

# ── 5. recommend --mode unknown → rc=1 ────────────────────
RC=0
python3 "${SCRIPT}" recommend --mode no-such-mode --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "unknown mode rc expected 1; got ${RC}"
pass "5. recommend --mode unknown → rc=1 + structured error"

# ── 6. bios-gate covers operator's board ──────────────────
out="$(python3 "${SCRIPT}" bios-gate --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['board'] == 'asus-proart-x870e-creator-wifi'
assert 'X870E-Creator' in d['board_name']
knobs = d['bios_knobs_for_software_fan_override']
assert len(knobs) >= 2
knob_names = {k['knob'] for k in knobs}
assert 'Q-Fan Tuning' in knob_names
" || fail "bios-gate"
pass "6. bios-gate covers ASUS X870E-Creator WiFi with Q-Fan Tuning knob"

# ── 7. bios-gate carries post-BIOS setup steps ─────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
steps = d.get('post_bios_setup_steps', [])
assert len(steps) >= 4
joined = ' '.join(steps)
# Operator-runnable commands present.
assert 'sensors-detect' in joined
assert 'pwmconfig' in joined
assert 'fancontrol' in joined
" || fail "setup steps"
pass "7. bios-gate post-BIOS steps include sensors-detect + pwmconfig + fancontrol"

# ── 8. status verb returns probe + verdict + mode ─────────
RC=0
out="$(python3 "${SCRIPT}" status --json)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" || "${RC}" == "2" ]] || fail "status rc unexpected: ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R337'
for k in ('active_mode', 'mode', 'fan_probe', 'verdict', 'rc'):
    assert k in d, k
" || fail "status shape"
pass "8. status returns active_mode + mode + fan_probe + verdict + rc"

# ── 9. Operator overlay overrides active_mode ─────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<'TOML'
active_mode = "training"
TOML
RC=0
out="$(python3 "${SCRIPT}" recommend --config "${cfg}" --json)" || RC=$?
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode']['mode'] == 'training'
" || fail "overlay active_mode"
rm -f "${cfg}"
pass "9. operator overlay (R283/SDD-030) sets active_mode → training"

# ── 10. sovereign-osctl fan-advisor dispatch ─────────────
out_disp="$(bash "${OSCTL}" fan-advisor modes --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R337'
" || fail "osctl dispatch"
pass "10. sovereign-osctl fan-advisor dispatches"

echo "ALL OK"
