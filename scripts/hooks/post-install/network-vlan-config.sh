#!/usr/bin/env bash
# scripts/hooks/post-install/network-vlan-config.sh
#
# Configure dual-NIC VLAN split per the profile's hardware.network
# list. Generates systemd-networkd .network / .netdev units honoring
# each NIC's profile fields:
#   - iface_hint → [Match] Name=  (so a dual-NIC host actually splits
#     roles; without it the units fall back to Type=ether, which is
#     ambiguous — systemd applies the lowest-numbered .network to EVERY
#     ethernet NIC — and the operator must pin [Match] manually)
#   - address    → static Address= (else DHCP=yes)
#   - gateway    → Gateway= (only on the default-gateway NIC)
#   - dns_nameservers → DNS=
#   - vlan / mtu / default_gateway → VLAN netdev, MTU, Zero-Trust routing
# Zero-Trust (§8): a non-gateway NIC carries NO default route —
# DefaultRouteOnDevice=no, and on DHCP it also refuses the offered
# gateway/routes so the invariant holds on the host, not the network.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="network-vlan-config"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "configure dual-NIC VLAN split"

require_root

network_dir="/etc/systemd/network"
mkdir -p "${network_dir}"

# Render one .network (+ optional .netdev/.network for the VLAN) per NIC.
# Quoted heredoc → no bash interpolation inside the Python; paths via env.
# Capture the generator's rc: a failure (unwritable /etc/systemd/network,
# malformed profile YAML) would otherwise abort via set -e before the
# result="configured" emit, leaving a host with NO network config and no
# fail signal — every other terminal here reports a metric.
network_rc=0
NETWORK_DIR="${network_dir}" python3 <<'PYEOF' || network_rc=$?
import os, yaml, pathlib, textwrap

with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    d = yaml.safe_load(f)
nics = (d.get('hardware') or {}).get('network') or []
out_dir = pathlib.Path(os.environ['NETWORK_DIR'])


def match_block(vendor, model, speed, name_hint):
    lines = []
    if vendor or model:
        lines.append('# %s %s (%s Gbps)' % (vendor, model, speed))
    lines.append('[Match]')
    if name_hint:
        # Pin the physical NIC by its profile name hint (e.g. enp6s0) so the
        # role split is deterministic on a multi-NIC host.
        lines.append('Name=%s' % name_hint)
    else:
        lines.append('Type=ether')
        lines.append('# WARNING: no iface_hint in profile — Type=ether matches EVERY')
        lines.append('# ethernet NIC, so systemd applies the lowest-numbered .network to')
        lines.append('# all of them. Pin [Match] Name=/MACAddress= for the role split.')
    return '\n'.join(lines)


def network_body(static_addr, gateway, dns, want_gw):
    # Static when the profile declares an address; else DHCP. Honor the declared
    # gateway + DNS. Enforce Zero-Trust "no default route" on non-gateway NICs.
    b = '[Network]\n'
    if static_addr:
        b += 'Address=%s\n' % static_addr
        if want_gw and gateway:
            b += 'Gateway=%s\n' % gateway
        for ns in dns:
            b += 'DNS=%s\n' % ns
        if not want_gw:
            b += 'DefaultRouteOnDevice=no\n'
    else:
        b += 'DHCP=yes\n'
        for ns in dns:
            b += 'DNS=%s\n' % ns
        if not want_gw:
            # DefaultRouteOnDevice=no alone won't stop a DHCP-offered gateway
            # from becoming the default route; refuse the gateway + routes DHCP
            # hands out so the Zero-Trust invariant holds on the host.
            b += 'DefaultRouteOnDevice=no\n[DHCPv4]\nUseGateway=no\nUseRoutes=no\n'
    return b


for idx, nic in enumerate(nics):
    role = nic.get('role', 'nic%d' % idx)
    vendor = nic.get('vendor', '')
    model = nic.get('model', '')
    speed = nic.get('speed_gbps', '?')
    vlan = nic.get('vlan')
    mtu = nic.get('mtu')
    default_gw = nic.get('default_gateway', False)
    address = nic.get('address')
    gateway = nic.get('gateway')
    dns = nic.get('dns_nameservers') or []
    iface_hint = nic.get('iface_hint')
    addr_label = address or 'dhcp'

    base_name = out_dir / ('%02d-%s.network' % (10 + idx, role))
    if vlan:
        # Base NIC: match the physical NIC + attach the VLAN. No IP on the base
        # — the VLAN interface below carries the address.
        base_name.write_text(
            match_block(vendor, model, speed, iface_hint)
            + '\n\n[Network]\nVLAN=%s-vlan\n' % role
        )
        print('  wrote %s (base, VLAN trunk)' % base_name)

        vlan_netdev = out_dir / ('%02d-%s-vlan.netdev' % (20 + idx, role))
        vlan_netdev.write_text(textwrap.dedent('''\
            [NetDev]
            Name=%s-vlan
            Kind=vlan

            [VLAN]
            Id=%s
            ''' % (role, vlan)))
        print('  wrote %s' % vlan_netdev)

        vlan_network = out_dir / ('%02d-%s-vlan.network' % (30 + idx, role))
        vcfg = '[Match]\nName=%s-vlan\n\n' % role
        vcfg += network_body(address, gateway, dns, default_gw)
        if mtu:
            vcfg += '[Link]\nMTUBytes=%s\n' % mtu
        vlan_network.write_text(vcfg)
        print('  wrote %s (addr=%s)' % (vlan_network, addr_label))
    else:
        # Non-VLAN NIC: the IP sits directly on the physical interface.
        cfg = match_block(vendor, model, speed, iface_hint) + '\n\n'
        cfg += network_body(address, gateway, dns, default_gw)
        if mtu:
            cfg += '[Link]\nMTUBytes=%s\n' % mtu
        base_name.write_text(cfg)
        print('  wrote %s (addr=%s)' % (base_name, addr_label))
PYEOF
if [ "${network_rc}" -ne 0 ]; then
  log_error "networkd unit generation failed (rc=${network_rc}); host may have NO network config — check ${network_dir} writability + profile hardware.network"
  emit_metric sovereign_os_post_install_network_vlan_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  exit 1
fi

# Restart networkd
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable systemd-networkd 2>&1 | sed 's/^/  /' || true
  systemctl restart systemd-networkd 2>&1 | sed 's/^/  /' || log_warn "systemd-networkd restart failed; manual intervention may be needed"
fi

emit_metric sovereign_os_post_install_network_vlan_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"configured\""
log_info "${STEP_ID} complete"
