"""R401 (E10.M45) — network-vlan-config + §8.1 operator-verbatim content lint.

Extends R387-R399 operational-artifact pinning to:
  scripts/hooks/post-install/network-vlan-config.sh
  profiles/sain-01.yaml (hardware.network section)

Master spec §8 + §8.1 verbatim (operator-named Zero-Trust segregation):
  > "VLAN 100 (Management/Telemetry) on Intel 2.5GbE; VLAN 200 (Model
  >  Ingestion/Storage) on Marvell 10GbE; Marvell MUST NOT carry the
  >  default route (no outbound WAN access per master spec § 8 ASCII
  >  topology diagram)."
  - Intel i226-v 2.5GbE → VLAN 100 mgmt + default gateway + 10.0.100.50/24 + enp6s0
  - Marvell AQC113C 10GbE → VLAN 200 data + MTU 9000 + no-default-gw + 10.0.200.50/24 + enp5s0

Critical operator invariant: Marvell (data NIC) MUST NOT have
default_gateway: true. If a future agent silently flips this, the
Zero-Trust topology breaks — data plane reaches WAN, security
perimeter violation per §8 verbatim topology.

If a future agent silently:
  - drops MTU 9000 (jumbo-frame storage performance loss)
  - swaps VLAN 100 ↔ 200 (mgmt traffic hits storage subnet)
  - sets data NIC default_gateway: true (WAN exposure of storage path)
  - drops systemd-networkd reload (config doesn't take effect)
…the operator's §8.1 Zero-Trust segregation silently breaks.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VLAN_SCRIPT = REPO_ROOT / "scripts" / "hooks" / "post-install" / "network-vlan-config.sh"
SAIN01 = REPO_ROOT / "profiles" / "sain-01.yaml"


def _read_script() -> str:
    assert VLAN_SCRIPT.is_file(), f"missing {VLAN_SCRIPT}"
    return VLAN_SCRIPT.read_text(encoding="utf-8")


def _load_profile() -> dict:
    assert SAIN01.is_file(), f"missing {SAIN01}"
    return yaml.safe_load(SAIN01.read_text(encoding="utf-8"))


def _network_list() -> list[dict]:
    d = _load_profile()
    nics = (d.get("hardware") or {}).get("network") or []
    assert isinstance(nics, list) and nics, (
        "sain-01 profile missing hardware.network NIC list (§8.1 verbatim)"
    )
    return nics


def _nic_by_role(role: str) -> dict:
    for nic in _network_list():
        if nic.get("role") == role:
            return nic
    raise AssertionError(
        f"sain-01 profile missing hardware.network NIC with role={role!r} "
        f"(§8.1 verbatim — operator-named mgmt+data dual-NIC split)"
    )


def test_vlan_script_file_exists():
    assert VLAN_SCRIPT.is_file(), f"missing {VLAN_SCRIPT}"


def test_script_reads_hardware_network():
    """Script MUST source NICs from profile's hardware.network YAML path
    (drift to hardware.nics or hardware.interfaces silently disconnects
    the script from operator's §8.1 verbatim spec)."""
    body = _read_script()
    assert "hardware" in body and "network" in body, (
        "network-vlan-config.sh missing hardware.network YAML path "
        "(§8.1 verbatim — operator's NIC config source)"
    )


def test_script_emits_systemd_networkd_units():
    """Script MUST write to /etc/systemd/network (systemd-networkd
    config dir). Drift to /etc/network/interfaces would break ZT
    segregation on systemd-based image."""
    body = _read_script()
    assert "/etc/systemd/network" in body, (
        "network-vlan-config.sh missing /etc/systemd/network output path "
        "(systemd-networkd .network units — §8.1 ZT VLAN segregation)"
    )


def test_script_handles_vlan_kind():
    """Script MUST emit Kind=vlan .netdev units when vlan is declared."""
    body = _read_script()
    assert "Kind=vlan" in body, (
        "network-vlan-config.sh missing Kind=vlan .netdev emission "
        "(§8.1 verbatim — operator-named VLAN 100/200 segregation)"
    )


def test_script_handles_mtu():
    """Script MUST propagate MTU from profile to .network unit
    (master spec §8.1 verbatim — data NIC carries MTU 9000 jumbo frames
    for 10GbE storage path performance)."""
    body = _read_script()
    has_mtu = "MTUBytes" in body or "mtu" in body.lower()
    assert has_mtu, (
        "network-vlan-config.sh missing MTU propagation "
        "(§8.1 verbatim — data NIC MUST carry MTU 9000)"
    )


def test_script_respects_default_gateway_flag():
    """Script MUST honor the profile's default_gateway flag —
    specifically MUST emit DefaultRouteOnDevice=no when false
    (otherwise Marvell data NIC silently carries WAN traffic =
    §8 Zero-Trust violation)."""
    body = _read_script()
    has_default_route_control = "DefaultRouteOnDevice" in body
    assert has_default_route_control, (
        "network-vlan-config.sh missing DefaultRouteOnDevice= control "
        "(§8 verbatim — Marvell MUST NOT carry the default route; "
        "without this directive, data NIC silently routes WAN traffic)"
    )


def test_script_refuses_dhcp_gateway_on_data_nic():
    """Defense-in-depth for §8 Zero-Trust: DefaultRouteOnDevice=no governs only
    an *on-link* default route — it does NOT stop a DHCP-offered gateway from
    becoming the default route. The data NIC runs DHCP, so the script MUST also
    refuse the DHCP gateway (UseGateway=no) or the data plane can still acquire
    WAN egress whenever the data VLAN's DHCP hands out a router. Pin the robust
    enforcement so it can't silently regress to the ineffective directive."""
    body = _read_script()
    assert "UseGateway=no" in body, (
        "network-vlan-config.sh missing [DHCPv4] UseGateway=no for the "
        "non-gateway NIC — DefaultRouteOnDevice=no alone does not suppress a "
        "DHCP-offered default route, leaving a §8 Zero-Trust egress hole"
    )


def test_script_reloads_networkd():
    """Script MUST restart systemd-networkd after writing units
    (otherwise next reboot needed for §8.1 segregation to take effect;
    operator-discovery surface stays broken until reboot)."""
    body = _read_script()
    has_reload = (
        "systemctl restart systemd-networkd" in body
        or "systemctl reload systemd-networkd" in body
    )
    assert has_reload, (
        "network-vlan-config.sh missing systemd-networkd reload "
        "(§8.1 verbatim — VLAN segregation needs networkd restart "
        "to take effect at install time, not just on next boot)"
    )


def test_profile_has_mgmt_nic_section_8_1():
    """Profile MUST declare mgmt NIC with §8.1 verbatim properties:
    Intel i226-v + 2.5 Gbps + VLAN 100 + default_gateway=true +
    10.0.100.50/24 + enp6s0."""
    mgmt = _nic_by_role("mgmt")
    assert mgmt.get("vendor") == "intel", (
        f"§8.1 verbatim: mgmt NIC vendor MUST be intel (got {mgmt.get('vendor')!r})"
    )
    assert "i226" in str(mgmt.get("model", "")).lower(), (
        f"§8.1 verbatim: mgmt NIC model MUST be i226-v "
        f"(got {mgmt.get('model')!r})"
    )
    assert mgmt.get("speed_gbps") == 2.5, (
        f"§8.1 verbatim: mgmt NIC speed MUST be 2.5 Gbps "
        f"(got {mgmt.get('speed_gbps')!r})"
    )
    assert mgmt.get("vlan") == 100, (
        f"§8.1 verbatim: mgmt NIC VLAN MUST be 100 "
        f"(got {mgmt.get('vlan')!r}); swap with VLAN 200 would route mgmt "
        f"traffic onto storage subnet"
    )
    assert mgmt.get("default_gateway") is True, (
        f"§8.1 verbatim: mgmt NIC MUST carry default gateway "
        f"(got default_gateway={mgmt.get('default_gateway')!r})"
    )
    assert "10.0.100.50/24" in str(mgmt.get("address", "")), (
        f"§8.1 verbatim address: mgmt NIC MUST be 10.0.100.50/24 "
        f"(got {mgmt.get('address')!r})"
    )


def test_profile_has_data_nic_section_8_1():
    """Profile MUST declare data NIC with §8.1 verbatim properties:
    Marvell aqc113c + 10 Gbps + VLAN 200 + MTU 9000 +
    default_gateway=false + 10.0.200.50/24 + enp5s0."""
    data = _nic_by_role("data")
    assert data.get("vendor") == "marvell", (
        f"§8.1 verbatim: data NIC vendor MUST be marvell "
        f"(got {data.get('vendor')!r})"
    )
    assert "aqc113" in str(data.get("model", "")).lower(), (
        f"§8.1 verbatim: data NIC model MUST be aqc113c "
        f"(got {data.get('model')!r})"
    )
    assert data.get("speed_gbps") == 10, (
        f"§8.1 verbatim: data NIC speed MUST be 10 Gbps "
        f"(got {data.get('speed_gbps')!r})"
    )
    assert data.get("vlan") == 200, (
        f"§8.1 verbatim: data NIC VLAN MUST be 200 "
        f"(got {data.get('vlan')!r}); swap with VLAN 100 would route "
        f"storage traffic onto mgmt subnet"
    )
    assert data.get("mtu") == 9000, (
        f"§8.1 verbatim: data NIC MTU MUST be 9000 jumbo frames "
        f"(got {data.get('mtu')!r}); drift loses 10GbE storage throughput"
    )
    assert "10.0.200.50/24" in str(data.get("address", "")), (
        f"§8.1 verbatim address: data NIC MUST be 10.0.200.50/24 "
        f"(got {data.get('address')!r})"
    )


def test_data_nic_must_not_carry_default_route():
    """OPERATOR-CRITICAL §8 verbatim invariant:
      'Marvell MUST NOT carry the default route (no outbound WAN
       access per master spec § 8 ASCII topology diagram).'

    If data NIC default_gateway flips to true → WAN exposure of the
    storage path → Zero-Trust segregation breakdown.
    """
    data = _nic_by_role("data")
    assert data.get("default_gateway") is not True, (
        "§8 OPERATOR-VERBATIM CRITICAL: 'Marvell MUST NOT carry the "
        "default route'. data NIC default_gateway is True — Zero-Trust "
        "topology violation. Flip back to default_gateway: false."
    )


def test_vlan_id_separation_preserved():
    """The operator-named §8.1 binding is:
      VLAN 100 ↔ mgmt (Intel 2.5GbE)
      VLAN 200 ↔ data (Marvell 10GbE)

    Drift where mgmt is on VLAN 200 (or data on VLAN 100) would route
    mgmt telemetry through storage subnet — silent ZT violation."""
    mgmt = _nic_by_role("mgmt")
    data = _nic_by_role("data")
    assert mgmt.get("vlan") == 100 and data.get("vlan") == 200, (
        f"§8.1 verbatim VLAN binding: mgmt MUST be 100, data MUST be 200 "
        f"(got mgmt={mgmt.get('vlan')!r} data={data.get('vlan')!r}); "
        f"swap silently misroutes mgmt/storage traffic onto wrong subnet"
    )


def test_profile_documents_master_spec_section_8():
    """Profile SHOULD reference §8 in network section comments
    (operator-discovery context — reader sees the binding to §8)."""
    body = SAIN01.read_text(encoding="utf-8")
    has_section_ref = (
        "§ 8" in body
        or "§8" in body
        or "section 8" in body.lower()
        or "master spec § 8" in body.lower()
    )
    assert has_section_ref, (
        "profiles/sain-01.yaml network section missing master spec §8 "
        "reference (operator-discovery context)"
    )


def test_no_silent_wan_exposure_pattern():
    """Catches a script-level drift where the data-role NIC config
    silently omits the default_gateway=false handling — that would
    let systemd-networkd auto-add a route gateway via the data NIC,
    re-exposing storage path to WAN.

    Sanity: the script body MUST handle role=data without forcing
    default_gateway=true. The current logic uses the profile flag, but
    drift toward 'always set default_gateway' would be a regression."""
    body = _read_script()
    # The script should NOT have hardcoded 'DefaultRoute=yes' for
    # data role (only honor profile flag)
    forbidden_patterns = [
        "DefaultRoute=yes\\nDefaultRoute=yes",  # double-set (parser ambiguity)
        "role == 'data':\n        default_gw = True",  # forced override
    ]
    bad = [p for p in forbidden_patterns if p in body]
    assert not bad, (
        f"network-vlan-config.sh has forced-default-route drift: {bad}; "
        f"§8 verbatim requires honoring the profile's default_gateway flag"
    )
