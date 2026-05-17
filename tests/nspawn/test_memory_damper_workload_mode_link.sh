#!/usr/bin/env bash
# R342 (E2.M31) — memory-pressure-damper adopts R338 workload-mode L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DAMP="${REPO_ROOT}/scripts/hardware/memory-pressure-oc-damper.py"
MODE="${REPO_ROOT}/scripts/intelligence/workload-mode.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. canonical=training → thresholds raised, step gentler ──
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${DAMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'training'
assert d['workload_mode_source'] == 'R338-canonical'
cm = d['config_modulated']
# Training: warn 30 + 20 = 50; crit 60 + 10 = 70; mild 0.05 - 0.03 = 0.02
assert cm['memory_pressure_warn_avg10'] == 50.0, cm
assert cm['memory_pressure_crit_avg10'] == 70.0, cm
assert abs(cm['dampen_step_mild'] - 0.02) < 0.001, cm
" || fail "training mod"
rm -f "${wm}" "${cfg}"
pass "1. canonical=training → warn 50%/crit 70% (raised), mild 2% (gentler)"

# ── 2. canonical=idle → thresholds lowered, step bigger ────
wm=$(mktemp); echo 'active_mode = "idle"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${DAMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cm = d['config_modulated']
# Idle: warn 30 - 10 = 20; crit 60 - 10 = 50; mild 0.05 + 0.02 = 0.07
assert cm['memory_pressure_warn_avg10'] == 20.0, cm
assert cm['memory_pressure_crit_avg10'] == 50.0, cm
assert abs(cm['dampen_step_mild'] - 0.07) < 0.001, cm
" || fail "idle mod"
rm -f "${wm}" "${cfg}"
pass "2. canonical=idle → warn 20%/crit 50% (lowered), mild 7% (bigger)"

# ── 3. canonical=inference-ready → no modulation (zero-delta) ──
wm=$(mktemp); echo 'active_mode = "inference-ready"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${DAMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['config']; cm = d['config_modulated']
assert cm['memory_pressure_warn_avg10'] == c['memory_pressure_warn_avg10']
assert cm['memory_pressure_crit_avg10'] == c['memory_pressure_crit_avg10']
assert cm['dampen_step_mild'] == c['dampen_step_mild']
" || fail "inference-ready"
rm -f "${wm}" "${cfg}"
pass "3. canonical=inference-ready → no modulation (zero-delta default)"

# ── 4. canonical=oc-burst → tightest thresholds + aggressive step ──
wm=$(mktemp); echo 'active_mode = "oc-burst"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${DAMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cm = d['config_modulated']
# OC-burst: warn 30 - 15 = 15; crit 60 - 20 = 40; mild 0.05 + 0.05 = 0.10
assert cm['memory_pressure_warn_avg10'] == 15.0, cm
assert cm['memory_pressure_crit_avg10'] == 40.0, cm
assert abs(cm['dampen_step_mild'] - 0.10) < 0.001, cm
" || fail "oc-burst"
rm -f "${wm}" "${cfg}"
pass "4. canonical=oc-burst → warn 15%/crit 40% (tightest), mild 10% (aggressive)"

# ── 5. Floor invariants preserved across modes ────────────
# warn ≥ 5%, crit ≥ warn, mild ≥ 0.01 for all 4 modes.
for mode in idle inference-ready training oc-burst; do
    wm=$(mktemp); echo "active_mode = \"${mode}\"" > "${wm}"
    cfg=$(mktemp --suffix=.toml)
    cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
    out="$(python3 "${DAMP}" status --config "${cfg}" --json || true)"
    echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cm = d['config_modulated']
assert cm['memory_pressure_warn_avg10'] >= 5.0, cm
assert cm['memory_pressure_crit_avg10'] >= cm['memory_pressure_warn_avg10'], cm
assert cm['dampen_step_mild'] >= 0.01, cm
" || fail "floors for ${mode}"
    rm -f "${wm}" "${cfg}"
done
pass "5. floor invariants preserved (warn≥5%, crit≥warn, mild≥0.01) across all 4 modes"

# ── 6. R338 file absent → no modulation ────────────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "/no/such/file"
TOML
out="$(python3 "${DAMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] is None
assert d['workload_mode_source'] == 'memory-damper-overlay'
c = d['config']; cm = d['config_modulated']
assert cm['memory_pressure_warn_avg10'] == c['memory_pressure_warn_avg10']
" || fail "absent fallback"
rm -f "${cfg}"
pass "6. R338 file absent → no modulation, defaults preserved"

# ── 7. follow_workload_mode_coordinator=false opts out ────
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
follow_workload_mode_coordinator = false
TOML
out="$(python3 "${DAMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_source'] == 'memory-damper-overlay'
c = d['config']; cm = d['config_modulated']
assert cm['memory_pressure_warn_avg10'] == c['memory_pressure_warn_avg10']
" || fail "opt-out"
rm -f "${wm}" "${cfg}"
pass "7. follow_workload_mode_coordinator=false disables modulation"

# ── 8. workload_mode_to_damper_delta map exposed in JSON ──
out="$(python3 "${DAMP}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['workload_mode_to_damper_delta']
for must in ('idle', 'inference-ready', 'training', 'oc-burst'):
    assert must in m, must
    for k in ('memory_pressure_warn_avg10_delta',
              'memory_pressure_crit_avg10_delta',
              'dampen_step_mild_delta', 'rationale'):
        assert k in m[must], (must, k)
" || fail "map exposed"
pass "8. workload_mode_to_damper_delta map exposed (4 modes × 4 fields each)"

# ── 9. R338 affected-advisors registry shows R304 adopted_in_round=R342 ──
out="$(python3 "${MODE}" affected-advisors --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r304 = next(a for a in d['advisors'] if a['advisor'] == 'R304 memory-pressure-damper')
assert r304['future_adoption'] is False
assert r304.get('adopted_in_round') == 'R342', r304
" || fail "registry"
pass "9. R338 affected-advisors registry shows R304 adopted_in_round=R342"

# ── 10. End-to-end: workload-mode set training → damper modulates ──
wm=$(mktemp -u)
state=$(mktemp -u)
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" \
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
python3 "${MODE}" set training --apply --confirm-mode-set \
    --target "${wm}" --json >/dev/null 2>&1
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${DAMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'training'
assert d['config_modulated']['memory_pressure_warn_avg10'] == 50.0
" || fail "end-to-end"
rm -f "${wm}" "${state}" "${cfg}"
pass "10. end-to-end: workload-mode set training → memory-damper warn=50%"

echo "ALL OK"
