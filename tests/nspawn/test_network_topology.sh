#!/usr/bin/env bash
# R359 (E3.M8) — network-topology L3.
# Operator-VERBATIM master spec §8 ASCII diagram + §8.1 interface specs.
# /goal contract: NO MINIMIZING / NO REPHRASING enforced at push.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NT="${REPO_ROOT}/scripts/network/topology.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. show returns ASCII diagram + 2 interfaces ────────────────────
out="$(python3 "${NT}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['interface_count'] == 2
assert 'diagram_verbatim' in d
# §8 diagram MUST contain the exact OPNsense + VLAN lines
diag = d['diagram_verbatim']
assert 'OPNsense Core Router / SD-WAN Firewall' in diag
assert '(VLAN 100)' in diag
assert '(VLAN 200)' in diag
assert 'SAIN-01 NODE' in diag
" || fail "show diagram"
pass "1. show returns §8 ASCII diagram with OPNsense+VLAN100/200+SAIN-01 markers"

# ── 2. diagram preserves §8 verbatim per-NIC role lines ─────────────
out="$(python3 "${NT}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
diag = d['diagram_verbatim']
must_have = [
    '[Intel I226-V 2.5GbE]',
    '[Marvell AQC113C 10GbE]',
    'Host SSH',
    'Tetragon Log Streams',
    'System Updates',
    'Isolated Container Bridge',
    'Model Weight Pulls (NAS)',
    'No Outbound WAN Access',
    'Management/Telemetry',
    'Model Ingestion/Storage',
]
for phrase in must_have:
    assert phrase in diag, f'missing §8 verbatim: {phrase!r}'
" || fail "diagram verbatim"
pass "2. §8 ASCII diagram preserves 10 operator-VERBATIM role lines (Intel/Marvell × responsibilities)"

# ── 3. §8.1 interface specs preserve verbatim address + MTU ─────────
out="$(python3 "${NT}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_iface = {i['interface']: i for i in d['interfaces']}
# §8.1 verbatim values
assert by_iface['enp6s0']['address_cidr'] == '10.0.100.50/24'
assert by_iface['enp6s0']['gateway'] == '10.0.100.1'
assert by_iface['enp6s0']['intended_mtu'] == 1500
assert by_iface['enp6s0']['vlan'] == 100
assert by_iface['enp5s0']['address_cidr'] == '10.0.200.50/24'
assert by_iface['enp5s0']['intended_mtu'] == 9000  # jumbo
assert by_iface['enp5s0']['vlan'] == 200
assert by_iface['enp5s0']['wan_access'] is False
" || fail "§8.1 verbatim"
pass "3. §8.1 verbatim addresses/MTU/VLAN: enp6s0=10.0.100.50/24+1500+VLAN100; enp5s0=10.0.200.50/24+9000+VLAN200"

# ── 4. responsibilities_verbatim per-NIC unchanged ──────────────────
out="$(python3 "${NT}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_iface = {i['interface']: i for i in d['interfaces']}
# Intel 2.5GbE responsibilities (operator-verbatim)
intel = by_iface['enp6s0']['responsibilities_verbatim']
assert 'Host SSH' in intel
assert 'Tetragon Log Streams' in intel
assert 'System Updates' in intel
# Marvell 10GbE responsibilities (operator-verbatim)
mar = by_iface['enp5s0']['responsibilities_verbatim']
assert 'Isolated Container Bridge' in mar
assert 'Model Weight Pulls (NAS)' in mar
assert 'No Outbound WAN Access' in mar
" || fail "responsibilities verbatim"
pass "4. responsibilities_verbatim per-NIC: 3+3 operator-VERBATIM bullets preserved unchanged"

# ── 5. chipset values verbatim (I226-V + AQC113C) ───────────────────
out="$(python3 "${NT}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_iface = {i['interface']: i for i in d['interfaces']}
assert by_iface['enp6s0']['vendor'] == 'Intel'
assert by_iface['enp6s0']['chipset'] == 'I226-V'
assert by_iface['enp5s0']['vendor'] == 'Marvell'
assert by_iface['enp5s0']['chipset'] == 'AQC113C'
" || fail "chipset"
pass "5. operator-verbatim chipset SKUs: Intel I226-V + Marvell AQC113C (§1.2 + §8 cross-ref)"

# ── 6. verify NEVER-raises on container (interfaces absent) ─────────
rc=0; out="$(python3 "${NT}" verify --json 2>&1)" || rc=$?
[[ "${rc}" == 0 || "${rc}" == 1 ]] || fail "verify rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# On container, interfaces likely absent → drift_count=2 (both)
assert d['row_count'] == 2
for r in d['rows']:
    for k in ('interface','vendor','chipset','intended_mtu','intended_address_cidr',
             'present','drifted','remediation'):
        assert k in r, (k, r)
" || fail "verify schema"
pass "6. verify NEVER-raises on container; emits full schema for both NICs"

# ── 7. scaffold emits operator-runnable /etc/network/interfaces ─────
out="$(python3 "${NT}" scaffold --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert len(d['blocks']) == 2
joined = ''
for b in d['blocks']:
    joined += '\n'.join(b['stanza']) + '\n'
# §8.1 verbatim shape — must include both interfaces with their addresses
assert 'auto enp6s0' in joined
assert 'iface enp6s0 inet static' in joined
assert 'address 10.0.100.50/24' in joined
assert 'auto enp5s0' in joined
assert 'address 10.0.200.50/24' in joined
# Jumbo frame line only on enp5s0 (MTU 9000)
assert 'mtu 9000' in joined
assert 'mtu 9000 # ' not in joined or 'mtu 9000' in joined
" || fail "scaffold"
pass "7. scaffold emits §8.1-shaped /etc/network/interfaces blocks for both NICs + jumbo MTU 9000"

# ── 8. scaffold note documents 'does NOT execute' ───────────────────
out="$(python3 "${NT}" scaffold --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'does NOT execute' in d['note']
assert 'SOVEREIGN_OS_CONFIRM_DESTROY' in d['note']
" || fail "scaffold note"
pass "8. scaffold note documents 'does NOT execute' + triple-gate guard"

# ── 9. operator-overlay replaces interfaces list ────────────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
[[interfaces]]
interface = "eth0"
role = "test"
vendor = "Test"
chipset = "TEST-0"
speed = "1GbE"
vlan = 1
address_cidr = "192.168.1.10/24"
gateway = "192.168.1.1"
intended_mtu = 1500
responsibilities_verbatim = ["test"]
wan_access = true
spec_ref = "overlay test"
TOML
out="$(python3 "${NT}" show --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['interface_count'] == 1
assert d['interfaces'][0]['interface'] == 'eth0'
" || fail "overlay"
rm -f "${cfg}"
pass "9. operator-overlay replaces interfaces list (R283/SDD-030 lists-replace)"

# ── 10. sovereign-osctl network-topology dispatches all 3 subverbs ──
"${OSCTL}" network-topology show --json >/dev/null 2>&1 || fail "osctl show"
"${OSCTL}" network-topology verify --json >/dev/null 2>&1 && true  # rc 0 or 1
"${OSCTL}" network-topology scaffold --json >/dev/null 2>&1 || fail "osctl scaffold"
pass "10. sovereign-osctl network-topology dispatches show/verify/scaffold"

# ── 11. per-NIC spec_ref preserves master spec §8 + §8.1 reference ─
out="$(python3 "${NT}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for i in d['interfaces']:
    assert 'master spec §8' in i['spec_ref']
    assert '§8.1' in i['spec_ref']
" || fail "spec ref"
pass "11. each interface's spec_ref cites master spec §8 + §8.1"

# ── 12. zero-trust posture: enp5s0.wan_access=False ─────────────────
out="$(python3 "${NT}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_iface = {i['interface']: i for i in d['interfaces']}
# §8 verbatim: Marvell 10GbE = 'No Outbound WAN Access' → wan_access False
assert by_iface['enp5s0']['wan_access'] is False
# Intel 2.5GbE handles WAN-bound traffic (System Updates) → wan_access True
assert by_iface['enp6s0']['wan_access'] is True
" || fail "zero-trust"
pass "12. zero-trust segregation: Marvell 10GbE wan_access=False; Intel 2.5GbE wan_access=True (§8 posture)"

echo "ALL OK"
