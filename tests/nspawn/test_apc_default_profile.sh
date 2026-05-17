#!/usr/bin/env bash
# R314 (E1.M34) — APC default-profile orchestration L3.
#
# Operator-named (§1b mandate row): "PSU/APC integration with the
# power management and the scheduled shutdown when battery reach a
# certain point as one default profile. (schedule/planifest/graceful
# on all levels, orderly)".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/apc-default-profile.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

mk_cfg() {
    local body="$1"
    local cfg
    cfg=$(mktemp --suffix=.toml)
    printf '%s\n' "${body}" > "${cfg}"
    echo "${cfg}"
}

# ── 1. list --json envelope + 3 default profiles ──────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R314'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M34'
assert d['total_count'] == 3
" || fail "envelope"
pass "1. list --json envelope + 3 default profiles"

# ── 2. Default active = balanced + 3 named profiles present ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['active_profile'] == 'balanced'
names = {p['name'] for p in d['profiles']}
assert names == {'conservative', 'balanced', 'aggressive'}, names
" || fail "anchors"
pass "2. default active = balanced + 3 named (conservative/balanced/aggressive)"

# ── 3. Every profile has 4 thresholds with full schema ────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for p in d['profiles']:
    assert len(p['thresholds']) == 4, p['name']
    for t in p['thresholds']:
        for k in ('battery_pct', 'severity', 'action', 'rationale'):
            assert k in t, (k, p['name'])
        assert t['severity'] in ('informational', 'attention', 'critical')
" || fail "threshold schema"
pass "3. every profile has 4 thresholds with full schema (battery_pct/severity/action/rationale)"

# ── 4. Thresholds in descending battery_pct order per profile ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for p in d['profiles']:
    pcts = [t['battery_pct'] for t in p['thresholds']]
    assert pcts == sorted(pcts, reverse=True), (p['name'], pcts)
" || fail "threshold order"
pass "4. thresholds in descending battery_pct order per profile (operator-readable)"

# ── 5. Final threshold per profile is shutdown action ─────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for p in d['profiles']:
    final = p['thresholds'][-1]
    assert final['severity'] == 'critical'
    assert final['action'].startswith('shutdown'), (p['name'], final)
" || fail "final shutdown"
pass "5. final threshold of every profile = critical shutdown action"

# ── 6. show <profile> renders detail ───────────────────────
out_s="$(python3 "${SCRIPT}" show conservative --json)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
p = d['profile']
assert p['name'] == 'conservative'
# Conservative shuts down at 25% (earlier than balanced's 10%).
final = p['thresholds'][-1]
assert final['battery_pct'] == 25
" || fail "show conservative"
pass "6. show conservative → final shutdown threshold = 25% (earlier than balanced's 10%)"

# ── 7. apply-hint emits operator-runnable battery-ladder commands ──
out_a="$(python3 "${SCRIPT}" apply-hint balanced --json)"
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R314'
assert d['profile'] == 'balanced'
assert len(d['commands']) == 4
for c in d['commands']:
    assert 'sovereign-osctl battery-ladder add-threshold' in c['command']
    assert '--pct' in c['command']
    assert '--severity' in c['command']
    assert '--action' in c['command']
" || fail "apply-hint shape"
pass "7. apply-hint emits 4 operator-runnable battery-ladder add-threshold commands"

# ── 8. Unknown profile → rc=1 + structured error ──────────
RC=0
python3 "${SCRIPT}" show no-such-profile --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "show unknown rc expected 1; got ${RC}"
RC=0
python3 "${SCRIPT}" apply-hint no-such-profile --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "apply-hint unknown rc expected 1; got ${RC}"
pass "8. unknown profile (show + apply-hint) → rc=1 + structured error"

# ── 9. Operator overlay sets active_profile ────────────────
cfg=$(mk_cfg 'active_profile = "aggressive"')
out_ov="$(python3 "${SCRIPT}" list --config "${cfg}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['active_profile'] == 'aggressive'
" || fail "overlay active"
rm -f "${cfg}"
pass "9. operator overlay (R283/SDD-030) sets active_profile"

# ── 10. sovereign-osctl apc-profile dispatch ────────────────
out_disp="$(bash "${OSCTL}" apc-profile list --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R314'
assert d['total_count'] == 3
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl apc-profile dispatches"

echo "ALL OK"
