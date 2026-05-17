#!/usr/bin/env bash
# R306 (E2.M13) — Debian 13 base-system hardening catalog L3.
#
# Operator-named (§1b mandate row): "Debian 13 Base , Sovereign OS
# and vision, why non-GUI by default. server, dashboard or API and
# modules and tools vision".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardening/base-catalog.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + ≥10 items ────────────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R306'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M13'
assert d['total_count'] >= 10
" || fail "envelope"
pass "1. list --json envelope + ≥10 hardening items"

# ── 2. Operator-named anchor items present (all 6 axes covered) ──
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {x['name'] for x in d['items']}
must = {
    'kernel.dmesg_restrict', 'kernel.kptr_restrict',
    'net.ipv4.conf.all.rp_filter', 'net.ipv4.tcp_syncookies',
    'kernel.unprivileged_bpf_disabled', 'kernel.yama.ptrace_scope',
    'apparmor', 'unattended-upgrades', 'auditd', 'fail2ban',
    'sshd.PermitRootLogin', 'sshd.PasswordAuthentication',
}
missing = must - names
assert not missing, missing
" || fail "anchors"
pass "2. all 12 anchor items present (sysctl + lsm + updates + audit + network + ssh)"

# ── 3. Every item has full schema ───────────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for x in d['items']:
    for k in ('name', 'axis', 'scope', 'recommended',
              'rationale', 'can_probe'):
        assert k in x, (k, x)
" || fail "item shape"
pass "3. every item has name/axis/scope/recommended/rationale/can_probe"

# ── 4. --axis filter narrows ──────────────────────────────────
out_sy="$(python3 "${SCRIPT}" list --axis sysctl --json)"
echo "${out_sy}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert all(x['axis'] == 'sysctl' for x in d['items'])
assert d['filtered_count'] >= 6
" || fail "axis filter"
pass "4. --axis sysctl filter narrows correctly (≥6 sysctl items)"

# ── 5. show <item> renders detail ──────────────────────────
out_show="$(python3 "${SCRIPT}" show 'sshd.PermitRootLogin' --json)"
echo "${out_show}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
x = d['item']
assert x['name'] == 'sshd.PermitRootLogin'
assert x['axis'] == 'ssh'
assert x['recommended'] == 'no'
assert 'sshd -T' in x['probe_command']
" || fail "show shape"
pass "5. show <sshd.PermitRootLogin> renders detail + probe command"

# ── 6. Unknown item → rc=1 + structured error ──────────────
RC=0
python3 "${SCRIPT}" show no-such-item --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "expected rc=1; got ${RC}"
err="$(python3 "${SCRIPT}" show no-such-item --json 2>&1 1>/dev/null)" || true
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'unknown item' in d['error']
assert isinstance(d['known'], list)
" || fail "unknown error shape"
pass "6. unknown item → rc=1 + structured error JSON"

# ── 7. check verb runs probes ────────────────────────────
RC=0
out_chk="$(python3 "${SCRIPT}" check --json)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "check rc unexpected: ${RC}"
echo "${out_chk}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R306'
assert isinstance(d['results'], list) and d['results']
for r in d['results']:
    assert 'name' in r
    assert 'probe_result' in r
    assert 'probable' in r['probe_result']
" || fail "check shape"
pass "7. check verb runs probes + emits per-result shape"

# ── 8. Operator overlay replaces catalog ────────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[items]]
name              = "operator-custom-knob"
axis              = "test"
scope             = "sysctl"
recommended       = "42"
rationale         = "test fixture for overlay replacement"
can_probe         = false
operator_caveat   = "n/a"
TOML

out_ov="$(python3 "${SCRIPT}" list --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [x['name'] for x in d['items']]
assert names == ['operator-custom-knob'], names
" || fail "overlay list-replace"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) replaces catalog"

# ── 9. Malformed overlay → defaults + _parse_error ─────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" list --config "${bad}" --json)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {x['name'] for x in d['items']}
assert 'kernel.dmesg_restrict' in names
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "9. malformed overlay → defaults + _parse_error"

# ── 10. sovereign-osctl hardening-base dispatch + read-only ──
out_disp="$(bash "${OSCTL}" hardening-base list --json)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R306'
" || fail "sovereign-osctl dispatch"
out2="$(python3 "${SCRIPT}" list --json)"
[[ "${out}" == "${out2}" ]] || fail "list output changed between calls"
pass "10. sovereign-osctl hardening-base dispatch + read-only invariant"

echo "ALL OK"
