#!/usr/bin/env bash
# R344 (E2.M32) — xmp-oc-room-advisor adopts R338 workload-mode L3.
# First post-SDD-035 adopter — validates the formal contract works
# for advisors beyond the original 4-adopter set.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
XMP="${REPO_ROOT}/scripts/hardware/xmp-oc-room-advisor.py"
MODE="${REPO_ROOT}/scripts/intelligence/workload-mode.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. canonical=idle → single-GPU + zero OC ──────────────
wm=$(mktemp); echo 'active_mode = "idle"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${XMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'idle'
assert d['workload_mode_source'] == 'R338-canonical'
cm = d['config_modulated']
assert cm['dual_gpu_active'] is False
assert cm['cpu_oc_multiplier'] == 1.0
assert cm['gpu_oc_notch'] == 0
" || fail "idle"
rm -f "${wm}" "${cfg}"
pass "1. canonical=idle → single-GPU (PRO 6000 only), zero CPU/GPU OC"

# ── 2. canonical=training → dual-GPU + 10% OC ─────────────
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${XMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cm = d['config_modulated']
assert cm['dual_gpu_active'] is True
assert cm['cpu_oc_multiplier'] == 1.1
assert cm['gpu_oc_notch'] == 1
" || fail "training"
rm -f "${wm}" "${cfg}"
pass "2. canonical=training → dual-GPU + 10% CPU/GPU OC"

# ── 3. canonical=oc-burst → max-everything ────────────────
wm=$(mktemp); echo 'active_mode = "oc-burst"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${XMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cm = d['config_modulated']
assert cm['cpu_oc_multiplier'] == 1.2
assert cm['gpu_oc_notch'] == 2
assert cm['dual_gpu_active'] is True
" || fail "oc-burst"
rm -f "${wm}" "${cfg}"
pass "3. canonical=oc-burst → max-everything (1.2x CPU, +20% GPU, dual-GPU)"

# ── 4. canonical=inference-ready → dual-GPU stock ─────────
wm=$(mktemp); echo 'active_mode = "inference-ready"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${XMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cm = d['config_modulated']
assert cm['dual_gpu_active'] is True
assert cm['cpu_oc_multiplier'] == 1.0
assert cm['gpu_oc_notch'] == 0
" || fail "inference-ready"
rm -f "${wm}" "${cfg}"
pass "4. canonical=inference-ready → dual-GPU + stock OC"

# ── 5. Idle mode reduces estimated_total_w (single-GPU only) ──
wm_idle=$(mktemp); echo 'active_mode = "idle"' > "${wm_idle}"
wm_train=$(mktemp); echo 'active_mode = "training"' > "${wm_train}"
cfg_idle=$(mktemp --suffix=.toml); cat > "${cfg_idle}" <<TOML
workload_mode_overlay_path = "${wm_idle}"
TOML
cfg_train=$(mktemp --suffix=.toml); cat > "${cfg_train}" <<TOML
workload_mode_overlay_path = "${wm_train}"
TOML
idle_out=$(python3 "${XMP}" status --config "${cfg_idle}" --json 2>&1 || true)
train_out=$(python3 "${XMP}" status --config "${cfg_train}" --json 2>&1 || true)
idle_w=$(echo "${idle_out}" | python3 -c "import json,sys; print(int(json.loads(sys.stdin.read())['estimated_total_w']))")
train_w=$(echo "${train_out}" | python3 -c "import json,sys; print(int(json.loads(sys.stdin.read())['estimated_total_w']))")
[[ "${idle_w}" -lt "${train_w}" ]] || fail "idle (${idle_w}W) should be < training (${train_w}W)"
# Idle should be substantially less (PRO 6000 only ≈ 880W vs training dual+OC ≈ 1400W).
[[ $((train_w - idle_w)) -gt 400 ]] || fail "expected ≥400W gap; got $((train_w - idle_w))W"
rm -f "${wm_idle}" "${wm_train}" "${cfg_idle}" "${cfg_train}"
pass "5. idle estimated_total_w << training (≥400W gap from dual-GPU + OC)"

# ── 6. R338 file absent → no modulation ────────────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "/no/such/file"
TOML
out="$(python3 "${XMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] is None
assert d['workload_mode_source'] == 'xmp-oc-room-overlay'
c = d['config']; cm = d['config_modulated']
# No modulation → modulated equals original
assert cm == c
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
out="$(python3 "${XMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_source'] == 'xmp-oc-room-overlay'
c = d['config']; cm = d['config_modulated']
assert cm == c
" || fail "opt-out"
rm -f "${wm}" "${cfg}"
pass "7. follow_workload_mode_coordinator=false disables modulation"

# ── 8. workload_mode_to_runtime_knobs map exposed ──────────
out="$(python3 "${XMP}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['workload_mode_to_runtime_knobs']
for must in ('idle', 'inference-ready', 'training', 'oc-burst'):
    assert must in m, must
    for k in ('xmp_enabled', 'cpu_oc_multiplier', 'gpu_oc_notch',
              'dual_gpu_active', 'rationale'):
        assert k in m[must], (must, k)
" || fail "map exposed"
pass "8. workload_mode_to_runtime_knobs map exposed (4 modes × 5 fields)"

# ── 9. R338 affected-advisors registry shows R315 adopted_in_round=R344 ──
out="$(python3 "${MODE}" affected-advisors --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r315 = next((a for a in d['advisors'] if a['advisor'] == 'R315 xmp-oc-room-advisor'), None)
assert r315 is not None, 'R315 missing from registry'
assert r315['future_adoption'] is False
assert r315.get('adopted_in_round') == 'R344', r315
" || fail "registry update"
pass "9. R338 affected-advisors registry shows R315 adopted_in_round=R344"

# ── 10. End-to-end: workload-mode set training → xmp-oc-room sees it ──
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
out="$(python3 "${XMP}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'training'
cm = d['config_modulated']
assert cm['cpu_oc_multiplier'] == 1.1
assert cm['gpu_oc_notch'] == 1
" || fail "end-to-end"
rm -f "${wm}" "${state}" "${cfg}"
pass "10. end-to-end: workload-mode set training → xmp-oc-room (cpu_oc=1.1, gpu_notch=1)"

echo "ALL OK"
