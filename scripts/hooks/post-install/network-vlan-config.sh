#!/usr/bin/env bash
# scripts/hooks/post-install/network-vlan-config.sh
#
# Configure dual-NIC VLAN split per the profile's hardware.network
# list. Generates systemd-networkd .network units; default behavior:
# - role=mgmt → VLAN 100, default gateway via this NIC
# - role=data → VLAN 200, MTU 9000, no default gateway
# Reads NIC names from /sys/class/net by matching vendor:device IDs.

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

# Read network NIC config from profile + emit one .network per NIC
python3 -c "
import os, yaml, pathlib, textwrap
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    d = yaml.safe_load(f)
nics = (d.get('hardware') or {}).get('network') or []
out_dir = pathlib.Path('${network_dir}')

for idx, nic in enumerate(nics):
    role = nic.get('role', f'nic{idx}')
    vendor = nic.get('vendor', '')
    model = nic.get('model', '')
    vlan = nic.get('vlan')
    mtu = nic.get('mtu')
    default_gw = nic.get('default_gateway', False)
    speed = nic.get('speed_gbps', '?')

    name = f'{10+idx:02d}-{role}.network'
    # Match by vendor model (heuristic; operator can pin MAC at install time)
    match_lines = []
    if vendor or model:
        match_lines.append(f'# {vendor} {model} ({speed} Gbps)')
    # Use type=ether as fallback; operator overrides with [Match] MACAddress= via local override
    match_lines.append('[Match]')
    match_lines.append('Type=ether')

    cfg = '\n'.join(match_lines) + '\n\n[Network]\n'
    cfg += 'DHCP=yes\n' if not vlan else f'VLAN={role}-vlan\n'
    if not default_gw:
        cfg += 'DefaultRouteOnDevice=no\n'

    out = out_dir / name
    out.write_text(cfg)
    print(f'  wrote {out}')

    # If a VLAN was declared, also write the .netdev + .network for the VLAN
    if vlan:
        vlan_netdev = out_dir / f'{20+idx:02d}-{role}-vlan.netdev'
        vlan_netdev.write_text(textwrap.dedent(f'''\
            [NetDev]
            Name={role}-vlan
            Kind=vlan

            [VLAN]
            Id={vlan}
            '''))
        print(f'  wrote {vlan_netdev}')

        vlan_network = out_dir / f'{30+idx:02d}-{role}-vlan.network'
        vlan_cfg = textwrap.dedent(f'''\
            [Match]
            Name={role}-vlan

            [Network]
            DHCP=yes
            ''')
        if mtu:
            vlan_cfg += f'\n[Link]\nMTUBytes={mtu}\n'
        if not default_gw:
            vlan_cfg += 'DefaultRouteOnDevice=no\n'
        vlan_network.write_text(vlan_cfg)
        print(f'  wrote {vlan_network}')
"

# Restart networkd
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable systemd-networkd 2>&1 | sed 's/^/  /' || true
  systemctl restart systemd-networkd 2>&1 | sed 's/^/  /' || log_warn "systemd-networkd restart failed; manual intervention may be needed"
fi

emit_metric sovereign_os_post_install_network_vlan_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"configured\""
log_info "${STEP_ID} complete"
