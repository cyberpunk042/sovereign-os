#!/usr/bin/env bash
# R338 (E2.M27) — workload-mode coordinator L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/intelligence/workload-mode.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope + default mode = idle ─────
out="$(python3 "${SCRIPT}" status --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R338'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M27'
assert d['active_mode'] == 'idle'
assert d['valid_mode'] is True
" || fail "envelope"
pass "1. status --json + default active_mode = idle"

# ── 2. modes verb returns 4 named modes ────────────────────
out="$(python3 "${SCRIPT}" modes --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['mode_count'] == 4
names = {m['mode'] for m in d['modes']}
assert names == {'idle', 'inference-ready', 'training', 'oc-burst'}, names
" || fail "modes"
pass "2. modes verb returns 4 named modes (idle/inference-ready/training/oc-burst)"

# ── 3. Each mode has description + use case ───────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for m in d['modes']:
    assert m['description']
    assert m['operator_use_case']
" || fail "mode schema"
pass "3. each mode has description + operator_use_case"

# ── 4. affected-advisors lists ≥5 surfaces ─────────────────
out="$(python3 "${SCRIPT}" affected-advisors --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['advisor_count'] >= 5
for a in d['advisors']:
    for k in ('advisor', 'script', 'verb', 'consumes_mode_via',
              'future_adoption', 'operator_caveat'):
        assert k in a, (k, a)
" || fail "affected-advisors"
pass "4. affected-advisors lists ≥5 surfaces with full schema"

# ── 5. affected-advisors includes R337 fan-advisor + future R296/R304 ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
advs = {a['advisor'] for a in d['advisors']}
for must in ('R337 fan-advisor', 'R296 thermal-oc-budget',
             'R304 memory-pressure-damper', 'R293 power-profiles',
             'R307 cpu-hotswap'):
    assert must in advs, advs
" || fail "registry coverage"
pass "5. affected-advisors registry covers R337 + future R296/R304/R293/R307"

# ── 6. Operator overlay sets active_mode → training ───────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<'TOML'
active_mode = "training"
TOML
out="$(python3 "${SCRIPT}" status --config "${cfg}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['active_mode'] == 'training'
" || fail "overlay knob"
rm -f "${cfg}"
pass "6. operator overlay sets active_mode = training"

# ── 7. set unknown mode → rc=1 + structured error ─────────
RC=0
python3 "${SCRIPT}" set no-such-mode --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "set unknown rc expected 1; got ${RC}"
pass "7. set unknown mode → rc=1 + structured error"

# ── 8. set without gates → dry-run + no write ──────────────
target=$(mktemp -u)
state=$(mktemp -u)
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" \
python3 "${SCRIPT}" set training --target "${target}" --json >/dev/null 2>&1 || true
[[ ! -f "${target}" ]] || fail "dry-run must not write target"
rm -f "${state}"
pass "8. set without gates → dry-run + no write"

# ── 9. set with all 3 gates writes target ────────────────
target=$(mktemp -u)
state=$(mktemp -u)
RC=0
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" \
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
python3 "${SCRIPT}" set training --apply --confirm-mode-set \
    --target "${target}" --json >/dev/null 2>&1 || RC=$?
[[ "${RC}" == "0" ]] || fail "expected rc=0; got ${RC}"
[[ -f "${target}" ]] || fail "target file should exist"
grep -q '^active_mode = "training"$' "${target}" \
    || fail "target should declare active_mode = training"
# Audit log should have a row.
grep -q '"verb": "workload-mode set"' "${state}" \
    || fail "audit log missing workload-mode set verb"
grep -q '"round_origin": "R338"' "${state}" \
    || fail "audit log missing round_origin=R338"
rm -f "${target}" "${state}"
pass "9. set with all 3 gates writes target + audits via R327"

# ── 10. sovereign-osctl workload-mode dispatch ─────────────
out_disp="$(bash "${OSCTL}" workload-mode modes --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R338'
" || fail "osctl dispatch"
pass "10. sovereign-osctl workload-mode dispatches"

echo "ALL OK"
