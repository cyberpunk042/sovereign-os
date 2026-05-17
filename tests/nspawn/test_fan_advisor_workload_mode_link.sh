#!/usr/bin/env bash
# R339 (E2.M28) — fan-advisor adopts R338 workload-mode as canonical L3.
#
# Verifies the cross-advisor mode-linking pattern: fan-advisor first
# reads R338 workload-mode; falls back to its own overlay when R338
# unset / unavailable.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FAN="${REPO_ROOT}/scripts/hardware/fan-advisor.py"
MODE="${REPO_ROOT}/scripts/intelligence/workload-mode.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. R338 file declares training → fan-advisor picks it up ──
wm_file=$(mktemp); echo 'active_mode = "training"' > "${wm_file}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm_file}"
active_mode = "idle"
TOML
out="$(python3 "${FAN}" recommend --config "${cfg}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode']['mode'] == 'training', d['mode']['mode']
assert d['mode_source'] == 'R338-canonical', d['mode_source']
" || fail "canonical pickup"
rm -f "${wm_file}" "${cfg}"
pass "1. R338 file declares training → fan-advisor adopts (source=R338-canonical)"

# ── 2. R338 file absent → falls back to fan-advisor's own overlay ──
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "/no/such/file/anywhere"
active_mode = "oc-burst"
TOML
out="$(python3 "${FAN}" recommend --config "${cfg}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode']['mode'] == 'oc-burst', d['mode']['mode']
assert d['mode_source'] == 'fan-advisor-overlay', d['mode_source']
" || fail "fallback"
rm -f "${cfg}"
pass "2. R338 file absent → falls back to fan-advisor active_mode (source=fan-advisor-overlay)"

# ── 3. Explicit --mode flag wins over both canonical AND overlay ──
wm_file=$(mktemp); echo 'active_mode = "training"' > "${wm_file}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm_file}"
active_mode = "idle"
TOML
out="$(python3 "${FAN}" recommend --mode oc-burst --config "${cfg}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode']['mode'] == 'oc-burst', d['mode']['mode']
assert d['mode_source'] == 'explicit-flag', d['mode_source']
" || fail "explicit override"
rm -f "${wm_file}" "${cfg}"
pass "3. --mode flag wins over both R338 canonical AND fan-advisor overlay"

# ── 4. follow_workload_mode_coordinator=false disables canonical read ──
wm_file=$(mktemp); echo 'active_mode = "training"' > "${wm_file}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm_file}"
follow_workload_mode_coordinator = false
active_mode = "idle"
TOML
out="$(python3 "${FAN}" recommend --config "${cfg}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# follow=false → never reads R338, always falls back to overlay.
assert d['mode']['mode'] == 'idle', d['mode']['mode']
assert d['mode_source'] == 'fan-advisor-overlay', d['mode_source']
" || fail "opt-out knob"
rm -f "${wm_file}" "${cfg}"
pass "4. follow_workload_mode_coordinator=false disables canonical read"

# ── 5. Malformed workload-mode.toml → graceful fallback ──
wm_file=$(mktemp); echo 'malformed [[[[ }}}}' > "${wm_file}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm_file}"
active_mode = "inference-ready"
TOML
RC=0
out="$(python3 "${FAN}" recommend --config "${cfg}" --json)" || RC=$?
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Malformed → fall back gracefully to fan-advisor's overlay.
assert d['mode']['mode'] == 'inference-ready', d['mode']['mode']
assert d['mode_source'] == 'fan-advisor-overlay', d['mode_source']
" || fail "malformed graceful"
rm -f "${wm_file}" "${cfg}"
pass "5. malformed workload-mode.toml → graceful fallback (no crash)"

# ── 6. status verb also picks up canonical mode ────────────
wm_file=$(mktemp); echo 'active_mode = "training"' > "${wm_file}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm_file}"
active_mode = "idle"
TOML
RC=0
out="$(python3 "${FAN}" status --config "${cfg}" --json)" || RC=$?
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['active_mode'] == 'training', d['active_mode']
assert d['mode_source'] == 'R338-canonical', d['mode_source']
" || fail "status canonical"
rm -f "${wm_file}" "${cfg}"
pass "6. status verb picks up R338 canonical (not just recommend)"

# ── 7. R338 affected-advisors registry shows R337 as adopted ──
out="$(python3 "${MODE}" affected-advisors --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r337 = next(a for a in d['advisors'] if a['advisor'] == 'R337 fan-advisor')
# After R339 wiring: future_adoption=False AND adopted_in_round=R339
assert r337['future_adoption'] is False
assert r337.get('adopted_in_round') == 'R339', r337
" || fail "registry update"
pass "7. R338 affected-advisors registry shows R337 adopted_in_round=R339"

# ── 8. End-to-end: workload-mode set training → fan-advisor sees it ──
wm_file=$(mktemp -u)
state=$(mktemp -u)
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" \
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
python3 "${MODE}" set training --apply --confirm-mode-set \
    --target "${wm_file}" --json >/dev/null 2>&1
[[ -f "${wm_file}" ]] || fail "workload-mode set must write target"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm_file}"
active_mode = "idle"
TOML
out="$(python3 "${FAN}" recommend --config "${cfg}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode']['mode'] == 'training', d
assert d['mode_source'] == 'R338-canonical', d
" || fail "end-to-end"
rm -f "${wm_file}" "${state}" "${cfg}"
pass "8. end-to-end: workload-mode set training → fan-advisor sees it via canonical"

# ── 9. R337 backwards-compat — no R338 file → still works as before ──
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "/never/exists/file"
active_mode = "training"
TOML
out="$(python3 "${FAN}" recommend --config "${cfg}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode']['mode'] == 'training', d
" || fail "backwards-compat"
rm -f "${cfg}"
pass "9. R337 backwards-compat — fan-advisor overlay still authoritative without R338"

# ── 10. sovereign-osctl fan-advisor dispatch with canonical link ──
wm_file=$(mktemp); echo 'active_mode = "oc-burst"' > "${wm_file}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm_file}"
active_mode = "idle"
TOML
out_disp="$(SOVEREIGN_OS_OVERLAY_FAN_ADVISOR=${cfg} bash "${OSCTL}" fan-advisor recommend --config "${cfg}" --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R337'
assert d['mode']['mode'] == 'oc-burst'
assert d['mode_source'] == 'R338-canonical'
" || fail "osctl dispatch"
rm -f "${wm_file}" "${cfg}"
pass "10. sovereign-osctl fan-advisor dispatch + canonical link works"

echo "ALL OK"
