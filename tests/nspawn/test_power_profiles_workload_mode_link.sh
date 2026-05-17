#!/usr/bin/env bash
# R345 (E2.M33) — R293 power-profiles adopts R338 workload-mode L3.
# Sixth post-SDD-035 adopter; closes the deferred candidate.
# Demonstrates the contract generalizes to a profile-name-string shape.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PROFILES="${REPO_ROOT}/scripts/power/profiles.py"
MODE="${REPO_ROOT}/scripts/intelligence/workload-mode.py"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. canonical=idle → recommends ac-loss-graceful-suspend ──────────
wm=$(mktemp); echo 'active_mode = "idle"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${PROFILES}" list --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'idle', d.get('workload_mode_canonical')
assert d['workload_mode_source'] == 'R338-canonical', d.get('workload_mode_source')
assert d['workload_mode_recommended_profile'] == 'ac-loss-graceful-suspend', d
" || fail "idle"
rm -f "${wm}" "${cfg}"
pass "1. canonical=idle → recommended_profile=ac-loss-graceful-suspend"

# ── 2. canonical=training → recommends thermal-budget-throttle ───────
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${PROFILES}" active --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'training'
assert d['workload_mode_recommended_profile'] == 'thermal-budget-throttle', d
" || fail "training"
rm -f "${wm}" "${cfg}"
pass "2. canonical=training → recommended_profile=thermal-budget-throttle"

# ── 3. canonical=oc-burst → recommends psu-headroom-warn ─────────────
wm=$(mktemp); echo 'active_mode = "oc-burst"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${PROFILES}" list --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_recommended_profile'] == 'psu-headroom-warn', d
" || fail "oc-burst"
rm -f "${wm}" "${cfg}"
pass "3. canonical=oc-burst → recommended_profile=psu-headroom-warn"

# ── 4. canonical=inference-ready → battery-threshold-graceful-shutdown
wm=$(mktemp); echo 'active_mode = "inference-ready"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${PROFILES}" list --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_recommended_profile'] == 'battery-threshold-graceful-shutdown', d
" || fail "inference-ready"
rm -f "${wm}" "${cfg}"
pass "4. canonical=inference-ready → recommended_profile=battery-threshold-graceful-shutdown"

# ── 5. recommended_profile != active_profile (additive surface) ──────
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${PROFILES}" active --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Operator's default: true on battery-threshold-graceful-shutdown remains active.
# R338 recommendation is separate, additive surface.
assert d['active_profile']['name'] == 'battery-threshold-graceful-shutdown', d['active_profile']
assert d['workload_mode_recommended_profile'] == 'thermal-budget-throttle'
" || fail "additive surface"
rm -f "${wm}" "${cfg}"
pass "5. recommended_profile is ADDITIVE — active_profile (operator-pinned) preserved"

# ── 6. R338 file absent → no recommendation, defaults preserved ──────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "/no/such/file"
TOML
out="$(python3 "${PROFILES}" list --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] is None
assert d['workload_mode_source'] == 'power-profiles-overlay'
assert d['workload_mode_recommended_profile'] is None
# Profiles still load.
assert d['profile_count'] >= 5
" || fail "absent fallback"
rm -f "${cfg}"
pass "6. R338 file absent → no recommendation, defaults preserved"

# ── 7. follow_workload_mode_coordinator=false opts out ──────────────
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
follow_workload_mode_coordinator = false
TOML
out="$(python3 "${PROFILES}" list --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_source'] == 'power-profiles-overlay'
assert d['workload_mode_canonical'] is None
assert d['workload_mode_recommended_profile'] is None
" || fail "opt-out"
rm -f "${wm}" "${cfg}"
pass "7. follow_workload_mode_coordinator=false disables recommendation"

# ── 8. workload_mode_to_profile_name map exposed on every verb ───────
for verb in list active; do
    out="$(python3 "${PROFILES}" "${verb}" --json || true)"
    echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['workload_mode_to_profile_name']
for must in ('idle', 'inference-ready', 'training', 'oc-burst'):
    assert must in m, must
    assert 'profile_name' in m[must]
    assert 'rationale' in m[must]
" || fail "map on ${verb}"
done
out="$(python3 "${PROFILES}" show battery-threshold-graceful-shutdown --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'workload_mode_to_profile_name' in d
" || fail "map on show"
out="$(python3 "${PROFILES}" simulate battery-threshold-graceful-shutdown --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'workload_mode_to_profile_name' in d
" || fail "map on simulate"
pass "8. workload_mode_to_profile_name map exposed on list/active/show/simulate"

# ── 9. R338 affected-advisors registry shows R293 adopted_in_round=R345
out="$(python3 "${MODE}" affected-advisors --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r293 = next((a for a in d['advisors'] if a['advisor'] == 'R293 power-profiles'), None)
assert r293 is not None, 'R293 missing from registry'
assert r293['future_adoption'] is False, r293
assert r293.get('adopted_in_round') == 'R345', r293
" || fail "registry update"
pass "9. R338 affected-advisors registry shows R293 adopted_in_round=R345"

# ── 10. end-to-end: workload-mode set training → profiles sees it ───
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
out="$(python3 "${PROFILES}" active --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'training'
assert d['workload_mode_source'] == 'R338-canonical'
assert d['workload_mode_recommended_profile'] == 'thermal-budget-throttle'
" || fail "end-to-end"
rm -f "${wm}" "${state}" "${cfg}"
pass "10. end-to-end: workload-mode set training → profiles recommends thermal-budget-throttle"

echo "ALL OK"
