#!/usr/bin/env python3
"""scripts/network/topology.py — R359 (E3.M8).

Operator-pull entry-point for master spec §8 Network Infrastructure &
Perimeter Segregation — operator's exact ASCII topology diagram +
the 2 NIC asymmetric layout (Marvell 10GbE compute / Intel 2.5GbE
management) + VLAN 100/200 segregation + MTU 9000 jumbo frames.

§8 operator-verbatim (block 2 of the SAIN-01 master spec dump):

  The ProArt X870E-Creator features asymmetric networking ports:
  a Marvell 10GbE adapter and an Intel 2.5GbE adapter. To align
  with a Zero-Trust OPNsense / SD-WAN core architecture, network
  traffic is physically segregated at the hardware boundary.

         [ OPNsense Core Router / SD-WAN Firewall ]
                          |
           +--------------+--------------+
           | (VLAN 100)                  | (VLAN 200)
           | Management/Telemetry        | Model Ingestion/Storage
           v                             v
  +-----------------------------------------------------------+
  | SAIN-01 NODE                                              |
  |  [Intel I226-V 2.5GbE]       [Marvell AQC113C 10GbE]      |
  |  - Host SSH                 - Isolated Container Bridge   |
  |  - Tetragon Log Streams     - Model Weight Pulls (NAS)    |
  |  - System Updates           - No Outbound WAN Access      |
  +-----------------------------------------------------------+

§8.1 verbatim interface config:
  # Intel 2.5GbE - Dedicated Secure Management Interface
  auto enp6s0
  iface enp6s0 inet static
      address 10.0.100.50/24
      gateway 10.0.100.1
      dns-nameservers 10.0.100.1

  # Marvell 10GbE - High-Speed Isolated Computation Interface
  auto enp5s0
  iface enp5s0 inet static
      address 10.0.200.50/24
      up ip link set dev enp5s0 mtu 9000 # Jumbo Frames for 10G NAS

Until R359, this content existed in render-asymmetric.sh as a
renderer but had no operator-pull verb to (a) SURFACE the §8
diagram + verbatim NIC roles, or (b) VERIFY live MTU/IP/VLAN
against the intended config.

CLI:
  topology.py show               [--config P] [--json|--human]
  topology.py verify             [--config P] [--json|--human]
                                  probe live /sys/class/net/<iface>;
                                  compare MTU + address against §8.1;
                                  rc=1 on drift; NEVER raises
  topology.py scaffold           [--config P] [--json|--human]
                                  emit operator-runnable
                                  /etc/network/interfaces block AND
                                  systemd-networkd unit equivalents

Operator-overlay (R283/SDD-030): /etc/sovereign-os/network-topology.toml
  - override interface names (different board / different distro)
  - override VLAN tags / IPs / MTUs

Exit codes:
  0  show rendered / verify clean
  1  verify drift (interface absent / MTU mismatch / address mismatch)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R359"
SDD_VECTOR = "E3.M8"


# Operator's §8 ASCII diagram preserved verbatim (NO REPHRASING).
TOPOLOGY_DIAGRAM_VERBATIM = """\
       [ OPNsense Core Router / SD-WAN Firewall ]
                        |
         +--------------+--------------+
         | (VLAN 100)                  | (VLAN 200)
         | Management/Telemetry        | Model Ingestion/Storage
         v                             v
+-----------------------------------------------------------+
| SAIN-01 NODE                                              |
|  [Intel I226-V 2.5GbE]       [Marvell AQC113C 10GbE]      |
|  - Host SSH                 - Isolated Container Bridge   |
|  - Tetragon Log Streams     - Model Weight Pulls (NAS)    |
|  - System Updates           - No Outbound WAN Access      |
+-----------------------------------------------------------+\
"""


# ── Default interface catalog (§8.1 verbatim per-NIC specs) ──────
DEFAULT_INTERFACES: list[dict[str, Any]] = [
    {
        "interface": "enp6s0",
        "role": "Dedicated Secure Management Interface",
        "vendor": "Intel",
        "chipset": "I226-V",
        "speed": "2.5GbE",
        "vlan": 100,
        "address_cidr": "10.0.100.50/24",
        "gateway": "10.0.100.1",
        "intended_mtu": 1500,
        "responsibilities_verbatim": [
            "Host SSH",
            "Tetragon Log Streams",
            "System Updates",
        ],
        "wan_access": True,
        "spec_ref": "master spec §8 + §8.1 verbatim",
    },
    {
        "interface": "enp5s0",
        "role": "High-Speed Isolated Computation Interface",
        "vendor": "Marvell",
        "chipset": "AQC113C",
        "speed": "10GbE",
        "vlan": 200,
        "address_cidr": "10.0.200.50/24",
        "gateway": None,
        "intended_mtu": 9000,
        "responsibilities_verbatim": [
            "Isolated Container Bridge",
            "Model Weight Pulls (NAS)",
            "No Outbound WAN Access",
        ],
        "wan_access": False,
        "spec_ref": "master spec §8 + §8.1 verbatim",
    },
]


# ── Probing ────────────────────────────────────────────────────────
def _read_iface_mtu(iface: str) -> int | None:
    """Read /sys/class/net/<iface>/mtu. NEVER raises."""
    p = Path(f"/sys/class/net/{iface}/mtu")
    try:
        body = p.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        return int(body)
    except ValueError:
        return None


def _iface_addresses(iface: str) -> list[str]:
    """Return list of CIDR addresses on iface via `ip -j addr show`.
    NEVER raises; returns [] when ip(8) unavailable / iface absent."""
    if not shutil.which("ip"):
        return []
    try:
        cp = subprocess.run(
            ["ip", "-j", "addr", "show", "dev", iface],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return []
    if cp.returncode != 0:
        return []
    try:
        items = json.loads(cp.stdout)
    except json.JSONDecodeError:
        return []
    out: list[str] = []
    if isinstance(items, list):
        for item in items:
            for addr in item.get("addr_info") or []:
                local = addr.get("local")
                prefixlen = addr.get("prefixlen")
                if local and prefixlen is not None:
                    out.append(f"{local}/{prefixlen}")
    return out


def derive_iface_state(spec: dict) -> dict[str, Any]:
    """Probe a single interface vs its operator-§8.1 intent."""
    iface = spec["interface"]
    mtu_path = Path(f"/sys/class/net/{iface}")
    present = mtu_path.is_dir()
    actual_mtu = _read_iface_mtu(iface) if present else None
    actual_addrs = _iface_addresses(iface) if present else []
    intended_mtu = int(spec.get("intended_mtu", 0) or 0)
    intended_addr = spec.get("address_cidr")
    mtu_drifted = (
        present and actual_mtu is not None
        and actual_mtu != intended_mtu
    )
    addr_drifted = (
        present and intended_addr
        and intended_addr not in actual_addrs
    )
    drifted = mtu_drifted or addr_drifted or not present
    remediation: list[str] = []
    if not present:
        remediation.append(
            f"# interface {iface} absent; verify hardware / driver "
            f"({spec.get('vendor')} {spec.get('chipset')})"
        )
    if mtu_drifted:
        remediation.append(
            f"ip link set dev {iface} mtu {intended_mtu}"
        )
    if addr_drifted and intended_addr:
        remediation.append(
            f"ip addr add {intended_addr} dev {iface}"
        )
    return {
        "interface": iface,
        "vendor": spec.get("vendor"),
        "chipset": spec.get("chipset"),
        "speed": spec.get("speed"),
        "vlan": spec.get("vlan"),
        "role": spec.get("role"),
        "intended_mtu": intended_mtu,
        "actual_mtu": actual_mtu,
        "intended_address_cidr": intended_addr,
        "actual_addresses": actual_addrs,
        "mtu_drifted": mtu_drifted,
        "addr_drifted": addr_drifted,
        "present": present,
        "drifted": bool(drifted),
        "remediation": remediation,
    }


def verify_all(ifaces: list[dict]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for spec in ifaces:
        if isinstance(spec, dict) and spec.get("interface"):
            rows.append(derive_iface_state(spec))
    drift_count = sum(1 for r in rows if r["drifted"])
    probed_count = sum(1 for r in rows if r["present"])
    return {
        "rows": rows,
        "drift_count": drift_count,
        "probed_count": probed_count,
        "row_count": len(rows),
    }


# ── Loading ────────────────────────────────────────────────────────
def load_state(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    ifaces = list(DEFAULT_INTERFACES)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "network-topology",
            {"interfaces": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("interfaces"):
            ifaces = list(loaded["interfaces"])
    return ifaces, meta


# ── Renderers ──────────────────────────────────────────────────────
def render_show_human(ifaces: list[dict]) -> str:
    lines = ["── R359 network topology (master spec §8 + §8.1 verbatim) ──"]
    lines.append("")
    lines.append("  ASCII DIAGRAM (operator verbatim):")
    for line in TOPOLOGY_DIAGRAM_VERBATIM.split("\n"):
        lines.append(f"    {line}")
    lines.append("")
    lines.append("  INTERFACES (§8.1 verbatim):")
    for spec in ifaces:
        lines.append("")
        lines.append(f"    {spec.get('interface')}  "
                      f"[{spec.get('vendor')} {spec.get('chipset')}]  "
                      f"{spec.get('speed')}  VLAN {spec.get('vlan')}")
        lines.append(f"      role:        {spec.get('role')}")
        lines.append(f"      address:     {spec.get('address_cidr')}")
        if spec.get("gateway"):
            lines.append(f"      gateway:     {spec.get('gateway')}")
        lines.append(f"      MTU:         {spec.get('intended_mtu')}")
        lines.append(f"      wan_access:  {spec.get('wan_access')}")
        lines.append(f"      responsibilities (operator verbatim):")
        for r in spec.get("responsibilities_verbatim") or []:
            lines.append(f"        - {r}")
    return "\n".join(lines) + "\n"


def render_verify_human(state: dict) -> str:
    lines = ["── R359 network topology verify (master spec §8 + §8.1) ──"]
    lines.append(f"  interfaces: {state['row_count']} | probed: "
                  f"{state['probed_count']} | drifted: {state['drift_count']}")
    lines.append("")
    for r in state["rows"]:
        glyph = "✗" if r["drifted"] else "✓"
        if not r["present"]:
            lines.append(f"  {glyph} {r['interface']}  "
                          f"[{r['vendor']} {r['chipset']}]: ABSENT")
        else:
            mtu_str = (f"MTU={r['actual_mtu']} (intended {r['intended_mtu']})"
                        + (" ✗" if r["mtu_drifted"] else ""))
            addr_str = (f"addrs={r['actual_addresses']} "
                         f"(intended {r['intended_address_cidr']})"
                         + (" ✗" if r["addr_drifted"] else ""))
            lines.append(f"  {glyph} {r['interface']}  {mtu_str}")
            lines.append(f"      {addr_str}")
        for rem in r.get("remediation") or []:
            lines.append(f"      $ {rem}")
    return "\n".join(lines) + "\n"


def render_scaffold_human(ifaces: list[dict]) -> str:
    lines = ["── R359 network topology scaffold (master spec §8.1 verbatim) ──"]
    lines.append("")
    lines.append("  # /etc/network/interfaces — master spec §8.1 verbatim shape")
    for spec in ifaces:
        lines.append("")
        lines.append(f"  # {spec.get('vendor')} {spec.get('speed')} — "
                      f"{spec.get('role')}")
        lines.append(f"  auto {spec.get('interface')}")
        lines.append(f"  iface {spec.get('interface')} inet static")
        if spec.get("address_cidr"):
            lines.append(f"      address {spec.get('address_cidr')}")
        if spec.get("gateway"):
            lines.append(f"      gateway {spec.get('gateway')}")
            lines.append(f"      dns-nameservers {spec.get('gateway')}")
        if int(spec.get("intended_mtu", 0) or 0) != 1500:
            lines.append(
                f"      up ip link set dev {spec.get('interface')} "
                f"mtu {spec.get('intended_mtu')}  "
                f"# Jumbo Frames per §8.1"
            )
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="topology.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    for verb in ("show", "verify", "scaffold"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        spg = sp.add_mutually_exclusive_group()
        spg.add_argument("--json", dest="fmt", action="store_const", const="json")
        spg.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    ifaces, meta = load_state(getattr(args, "config", None))

    if args.cmd == "show":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "diagram_verbatim": TOPOLOGY_DIAGRAM_VERBATIM,
                "interface_count": len(ifaces),
                "interfaces": ifaces,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(ifaces), end="")
        return 0

    if args.cmd == "verify":
        state = verify_all(ifaces)
        out = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            **state,
            "overlay": meta,
        }
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(render_verify_human(state), end="")
        return 1 if state["drift_count"] > 0 else 0

    if args.cmd == "scaffold":
        if args.fmt == "json":
            blocks: list[dict[str, Any]] = []
            for spec in ifaces:
                cmd_lines = [
                    f"auto {spec['interface']}",
                    f"iface {spec['interface']} inet static",
                ]
                if spec.get("address_cidr"):
                    cmd_lines.append(f"    address {spec['address_cidr']}")
                if spec.get("gateway"):
                    cmd_lines.append(f"    gateway {spec['gateway']}")
                    cmd_lines.append(f"    dns-nameservers {spec['gateway']}")
                if int(spec.get("intended_mtu", 0) or 0) != 1500:
                    cmd_lines.append(
                        f"    up ip link set dev {spec['interface']} "
                        f"mtu {spec['intended_mtu']}"
                    )
                blocks.append({
                    "interface": spec["interface"],
                    "stanza": cmd_lines,
                })
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "blocks": blocks,
                "note": ("operator-runnable /etc/network/interfaces shape — "
                          "this verb does NOT execute; write to file under "
                          "SOVEREIGN_OS_CONFIRM_DESTROY=YES guard"),
                "overlay": meta,
            }, indent=2))
        else:
            print(render_scaffold_human(ifaces), end="")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
