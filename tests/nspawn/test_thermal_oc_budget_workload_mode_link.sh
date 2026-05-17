#!/usr/bin/env bash
# R341 (E2.M30) — thermal-oc-budget adopts R338 workload-mode as canonical L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
THERMAL="${REPO_ROOT}/scripts/hardware/thermal-oc-budget.py"
MODE="${REPO_ROOT}/scripts/intelligence/workload-mode.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. canonical=training → margins modulated tighter ──────
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${THERMAL}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'training'
assert d['workload_mode_source'] == 'R338-canonical'
c = d['config']; cm = d['config_modulated']
# Training: cpu_tjmax_watch_margin reduced by 5 (10 → 5)
assert cm['cpu_tjmax_watch_margin_c'] == c['cpu_tjmax_watch_margin_c'] - 5
# Training: gpu_temp_watch_c raised by 3 (80 → 83)
assert cm['gpu_temp_watch_c'] == c['gpu_temp_watch_c'] + 3
" || fail "training modulation"
rm -f "${wm}" "${cfg}"
pass "1. canonical=training → cpu_watch_margin -5°C; gpu_watch +3°C"

# ── 2. canonical=idle → margins modulated more conservative ──
wm=$(mktemp); echo 'active_mode = "idle"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${THERMAL}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['config']; cm = d['config_modulated']
# Idle: cpu_tjmax_watch_margin raised by 5 (10 → 15)
assert cm['cpu_tjmax_watch_margin_c'] == c['cpu_tjmax_watch_margin_c'] + 5
# Idle: gpu_temp_watch_c lowered by 5 (80 → 75)
assert cm['gpu_temp_watch_c'] == c['gpu_temp_watch_c'] - 5
" || fail "idle modulation"
rm -f "${wm}" "${cfg}"
pass "2. canonical=idle → cpu_watch_margin +5°C (warn sooner); gpu_watch -5°C"

# ── 3. canonical=inference-ready → no modulation (default) ────
wm=$(mktemp); echo 'active_mode = "inference-ready"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${THERMAL}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['config']; cm = d['config_modulated']
# inference-ready: all deltas = 0
assert cm['cpu_tjmax_watch_margin_c'] == c['cpu_tjmax_watch_margin_c']
assert cm['gpu_temp_watch_c'] == c['gpu_temp_watch_c']
" || fail "inference-ready"
rm -f "${wm}" "${cfg}"
pass "3. canonical=inference-ready → no modulation (zero-delta default)"

# ── 4. canonical=oc-burst → maximum modulation ─────────────
wm=$(mktemp); echo 'active_mode = "oc-burst"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${THERMAL}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['config']; cm = d['config_modulated']
# oc-burst: cpu_watch_margin -7 (10 → 3); gpu_watch +5 (80 → 85)
assert cm['cpu_tjmax_watch_margin_c'] == c['cpu_tjmax_watch_margin_c'] - 7
assert cm['gpu_temp_watch_c'] == c['gpu_temp_watch_c'] + 5
" || fail "oc-burst"
rm -f "${wm}" "${cfg}"
pass "4. canonical=oc-burst → max modulation (cpu -7°C, gpu +5°C)"

# ── 5. Critical thresholds preserved across modes ─────────
# Verify modulation respects critical (less aggressive than watch).
for mode in idle inference-ready training oc-burst; do
    wm=$(mktemp); echo "active_mode = \"${mode}\"" > "${wm}"
    cfg=$(mktemp --suffix=.toml)
    cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
    out="$(python3 "${THERMAL}" status --config "${cfg}" --json || true)"
    echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cm = d['config_modulated']
# Critical CPU margin should always be ≤ watch margin (closer to tjmax).
assert cm['cpu_tjmax_critical_margin_c'] <= cm['cpu_tjmax_watch_margin_c'], cm
# Critical GPU threshold should always be ≥ watch threshold (hotter).
assert cm['gpu_temp_critical_c'] >= cm['gpu_temp_watch_c'], cm
" || fail "critical preserved for ${mode}"
    rm -f "${wm}" "${cfg}"
done
pass "5. critical thresholds preserved as ordering invariant across all 4 modes"

# ── 6. R338 file absent → no modulation, defaults preserved ──
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "/no/such/file/anywhere"
TOML
out="$(python3 "${THERMAL}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] is None
assert d['workload_mode_source'] == 'thermal-oc-budget-overlay'
c = d['config']; cm = d['config_modulated']
# No modulation → modulated equals original.
assert cm['cpu_tjmax_watch_margin_c'] == c['cpu_tjmax_watch_margin_c']
assert cm['gpu_temp_watch_c'] == c['gpu_temp_watch_c']
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
out="$(python3 "${THERMAL}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_source'] == 'thermal-oc-budget-overlay'
c = d['config']; cm = d['config_modulated']
assert cm['cpu_tjmax_watch_margin_c'] == c['cpu_tjmax_watch_margin_c']
" || fail "opt-out"
rm -f "${wm}" "${cfg}"
pass "7. follow_workload_mode_coordinator=false disables modulation"

# ── 8. workload_mode_to_margin_delta map exposed in JSON ──
out="$(python3 "${THERMAL}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['workload_mode_to_margin_delta']
for must in ('idle', 'inference-ready', 'training', 'oc-burst'):
    assert must in m, must
    assert 'rationale' in m[must]
    for k in ('cpu_tjmax_watch_margin_c_delta',
              'cpu_tjmax_critical_margin_c_delta',
              'gpu_temp_watch_c_delta',
              'gpu_temp_critical_c_delta'):
        assert k in m[must], (must, k)
" || fail "map exposed"
pass "8. workload_mode_to_margin_delta map exposed in JSON (all 4 modes, 4 delta keys each)"

# ── 9. R338 affected-advisors registry shows R296 adopted_in_round=R341 ──
out="$(python3 "${MODE}" affected-advisors --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r296 = next(a for a in d['advisors'] if a['advisor'] == 'R296 thermal-oc-budget')
assert r296['future_adoption'] is False
assert r296.get('adopted_in_round') == 'R341', r296
" || fail "registry update"
pass "9. R338 affected-advisors registry shows R296 adopted_in_round=R341"

# ── 10. End-to-end: workload-mode set training → thermal modulates ──
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
out="$(python3 "${THERMAL}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'training'
cm = d['config_modulated']
# Training tightens cpu watch margin.
assert cm['cpu_tjmax_watch_margin_c'] == 5, cm['cpu_tjmax_watch_margin_c']
" || fail "end-to-end"
rm -f "${wm}" "${state}" "${cfg}"
pass "10. end-to-end: workload-mode set training → thermal-oc-budget modulates"

echo "ALL OK"
