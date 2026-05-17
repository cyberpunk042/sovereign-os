#!/usr/bin/env bash
# R340 (E2.M29) — cpu-hotswap adopts R338 workload-mode as canonical L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CPU="${REPO_ROOT}/scripts/hardware/cpu-hotswap.py"
MODE="${REPO_ROOT}/scripts/intelligence/workload-mode.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. R338 canonical=training → cpu-hotswap derives performance/performance ──
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${CPU}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'training'
assert d['workload_mode_source'] == 'R338-canonical'
assert d['derived_pinned_mode'] == 'performance'
assert d['derived_pinned_epp'] == 'performance'
" || fail "training derivation"
rm -f "${wm}" "${cfg}"
pass "1. R338 canonical=training → derived (performance, performance)"

# ── 2. R338 canonical=idle → cpu-hotswap derives powersave/power ──
wm=$(mktemp); echo 'active_mode = "idle"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${CPU}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'idle'
assert d['derived_pinned_mode'] == 'powersave'
assert d['derived_pinned_epp'] == 'power'
" || fail "idle derivation"
rm -f "${wm}" "${cfg}"
pass "2. R338 canonical=idle → derived (powersave, power)"

# ── 3. R338 canonical=inference-ready → schedutil/balance_performance ──
wm=$(mktemp); echo 'active_mode = "inference-ready"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${CPU}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['derived_pinned_mode'] == 'schedutil'
assert d['derived_pinned_epp'] == 'balance_performance'
" || fail "inference-ready derivation"
rm -f "${wm}" "${cfg}"
pass "3. R338 canonical=inference-ready → derived (schedutil, balance_performance)"

# ── 4. Explicit overlay pinned_mode wins over R338 canonical ──
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
pinned_mode = "schedutil"
pinned_epp = "balance_power"
TOML
out="$(python3 "${CPU}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Explicit overlay pinned_* should override the R338 canonical mapping.
assert d['workload_mode_source'] == 'cpu-hotswap-overlay-explicit'
assert d['config']['pinned_mode'] == 'schedutil'
assert d['config']['pinned_epp'] == 'balance_power'
" || fail "overlay overrides canonical"
rm -f "${wm}" "${cfg}"
pass "4. explicit overlay pinned_mode/pinned_epp wins over R338 canonical"

# ── 5. R338 file absent → no derivation, defaults preserved ──
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "/no/such/file"
TOML
out="$(python3 "${CPU}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] is None
assert d['workload_mode_source'] == 'cpu-hotswap-overlay'
assert d['derived_pinned_mode'] == ''
assert d['derived_pinned_epp'] == ''
" || fail "absent fallback"
rm -f "${cfg}"
pass "5. R338 file absent → no derivation, defaults preserved"

# ── 6. follow_workload_mode_coordinator=false opts out ──
wm=$(mktemp); echo 'active_mode = "training"' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
follow_workload_mode_coordinator = false
TOML
out="$(python3 "${CPU}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Opt-out → no derivation even though R338 file exists.
assert d['workload_mode_source'] == 'cpu-hotswap-overlay'
assert d['derived_pinned_mode'] == ''
" || fail "opt-out"
rm -f "${wm}" "${cfg}"
pass "6. follow_workload_mode_coordinator=false disables canonical read"

# ── 7. Malformed R338 file → graceful fallback ────────────
wm=$(mktemp); echo 'malformed [[[[ }}}}' > "${wm}"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${CPU}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Malformed → no canonical extracted, falls back gracefully.
assert d['workload_mode_canonical'] is None
assert d['workload_mode_source'] == 'cpu-hotswap-overlay'
" || fail "malformed"
rm -f "${wm}" "${cfg}"
pass "7. malformed R338 file → graceful fallback (no crash)"

# ── 8. workload_mode_to_gov_epp map exposed in JSON ──────
out="$(python3 "${CPU}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
m = d['workload_mode_to_gov_epp']
for must in ('idle', 'inference-ready', 'training', 'oc-burst'):
    assert must in m, must
    assert 'governor' in m[must]
    assert 'epp' in m[must]
    assert 'rationale' in m[must]
" || fail "map exposed"
pass "8. workload_mode_to_gov_epp map exposed in JSON (idle/inference-ready/training/oc-burst)"

# ── 9. R338 affected-advisors registry shows R307 adopted_in_round=R340 ──
out="$(python3 "${MODE}" affected-advisors --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r307 = next(a for a in d['advisors'] if a['advisor'] == 'R307 cpu-hotswap')
assert r307['future_adoption'] is False
assert r307.get('adopted_in_round') == 'R340', r307
" || fail "registry update"
pass "9. R338 affected-advisors registry shows R307 adopted_in_round=R340"

# ── 10. End-to-end: workload-mode set training → cpu-hotswap sees it ──
wm=$(mktemp -u)
state=$(mktemp -u)
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" \
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
python3 "${MODE}" set training --apply --confirm-mode-set \
    --target "${wm}" --json >/dev/null 2>&1
[[ -f "${wm}" ]] || fail "workload-mode set must write target"
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
workload_mode_overlay_path = "${wm}"
TOML
out="$(python3 "${CPU}" status --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['workload_mode_canonical'] == 'training'
assert d['derived_pinned_mode'] == 'performance'
" || fail "end-to-end"
rm -f "${wm}" "${state}" "${cfg}"
pass "10. end-to-end: workload-mode set training → cpu-hotswap derives performance"

echo "ALL OK"
