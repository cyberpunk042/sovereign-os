#!/usr/bin/env bash
# R293 (E1.M21) — operator-pull power-management profile registry L3.
#
# Operator-named (§1b mandate row): "the PSU/APC integration with the
# power mangement and the scheduled shutdown when battery reach a
# certain point as one default profile. (schedule/planifest/graceful
# on all levels, orderly)".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/power/profiles.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + 5 default profiles ──────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R293'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M21'
assert d['profile_count'] >= 4
names = {p['name'] for p in d['profiles']}
for must in ('battery-threshold-graceful-shutdown', 'scheduled-graceful-poweroff',
             'thermal-budget-throttle', 'psu-headroom-warn'):
    assert must in names, f'missing {must}: {names}'
# ac-loss-graceful-suspend REMOVED — always-on box never suspends (would break it).
assert 'ac-loss-graceful-suspend' not in names, f'suspend profile must be gone: {names}'
assert not any('systemctl suspend' in ' '.join(p.get('steps', [])) for p in d['profiles']), \
    'no profile may call systemctl suspend'
" || fail "list envelope / default 4 profiles + no suspend"
pass "1. list --json envelope + 4 default profiles + no suspend anywhere"

# ── 2. battery-threshold profile is the default ────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['active_profile'] == 'battery-threshold-graceful-shutdown', d['active_profile']
" || fail "battery profile not default"
pass "2. battery-threshold-graceful-shutdown is the default profile"

# ── 3. show <profile> renders trigger + steps ──────────────────
out_show="$(python3 "${SCRIPT}" show battery-threshold-graceful-shutdown --json)"
echo "${out_show}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
p = d['profile']
assert p['name'] == 'battery-threshold-graceful-shutdown'
assert p['default'] is True
assert isinstance(p['steps'], list) and len(p['steps']) >= 3
# Steps must reference real sovereign-osctl verbs.
joined = ' '.join(p['steps'])
for v in ('power-status ups', 'service-deps drain', 'power-shutdown'):
    assert v in joined, (v, joined)
" || fail "show profile shape"
pass "3. show <profile> renders trigger + steps + composed verbs"

# ── 4. simulate <profile> emits ordered steps without applying ──
out_sim="$(python3 "${SCRIPT}" simulate scheduled-graceful-poweroff --json)"
echo "${out_sim}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['profile_name'] == 'scheduled-graceful-poweroff'
assert d['simulate_mode'] is True
assert 'SIMULATE is print-only' in d['note']
assert isinstance(d['steps'], list) and len(d['steps']) >= 2
" || fail "simulate shape"
pass "4. simulate <profile> emits ordered steps + simulate_mode marker"

# ── 5. active verb returns the default profile ────────────────
out_act="$(python3 "${SCRIPT}" active --json)"
echo "${out_act}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['active_profile'] is not None
assert d['active_profile']['name'] == 'battery-threshold-graceful-shutdown'
" || fail "active verb"
pass "5. active verb returns the operator-default profile"

# ── 6. Unknown profile → rc=1 + structured error ──────────────
RC=0
python3 "${SCRIPT}" show no-such-profile --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "expected rc=1 on unknown; got ${RC}"
err="$(python3 "${SCRIPT}" show no-such-profile --json 2>&1 1>/dev/null)" || true
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'unknown profile' in d['error']
assert isinstance(d['known'], list)
" || fail "unknown-profile error shape"
pass "6. unknown profile → rc=1 + structured error JSON"

# ── 7. Operator overlay replaces profile list entirely ────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[profiles]]
name    = "operator-custom-only"
default = true
trigger = "operator-pulled by hand for test"
steps   = ["echo only-this"]
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [p['name'] for p in d['profiles']]
assert names == ['operator-custom-only'], names
assert d['active_profile'] == 'operator-custom-only'
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "7. operator overlay (R283/SDD-030) replaces profile list"

# ── 8. Malformed overlay → defaults + _parse_error ────────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" list --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {p['name'] for p in d['profiles']}
assert 'battery-threshold-graceful-shutdown' in names
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "8. malformed overlay → defaults + _parse_error"

# ── 9. sovereign-osctl power-profiles dispatch ────────────────
out_disp="$(bash "${OSCTL}" power-profiles list --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R293'
" || fail "sovereign-osctl power-profiles dispatch"
pass "9. sovereign-osctl power-profiles dispatches"

# ── 10. config example declares the full schema ─────────────────
example="${REPO_ROOT}/config/power-profiles.toml.example"
[[ -f "${example}" ]] || fail "missing ${example}"
python3 -c "
import sys
try:
    import tomllib as t
except ImportError:
    import tomli as t  # type: ignore
data = t.loads(open('${example}').read())
assert 'profiles' in data
defaults = [p for p in data['profiles'] if p.get('default')]
assert len(defaults) == 1, f'expected exactly one default, got {len(defaults)}'
for p in data['profiles']:
    for k in ('name', 'default', 'trigger', 'steps'):
        assert k in p, f'profile {p.get(\"name\")} missing {k}'
" || fail "config example schema"
pass "10. config example declares full schema + exactly one default"

# ── 11. Read-only invariant (two list calls byte-identical) ────
out2="$(python3 "${SCRIPT}" list --json)"
[[ "${out}" == "${out2}" ]] || fail "list output changed between calls"
pass "11. read-only invariant (two list --json calls identical)"

echo "ALL OK"
