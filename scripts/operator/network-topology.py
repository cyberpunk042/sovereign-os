#!/usr/bin/env python3
"""scripts/operator/network-topology.py — R449 (E11.M8).

Operator §1g verbatim:
  "Like normal my AI will also be behind a firewall which will do a VPN
   bridge to my other network since my two LANs are over two different
   WAN and that each have an ISP router with NAT and then my Opnsense
   Firewall with another NAT. This can be detected too I guess and
   maybe it might require some configuration on it and we would say it
   to the user. Maybe we can even integrate features, I can even create
   a user and an API key and then it unlock other capabilities when
   its detected and we want to connect to it. Be aware of its state."

The §1g surface for operator-discoverable network topology:
  - Detect upstream NAT layers (ISP router → OPNsense → workstation)
  - Detect VPN bridge presence + state
  - Detect OPNsense reachability + API connectivity tier
  - Surface integration-unlock state (does the workstation have an
    OPNsense API key configured + can it reach the API)
  - Operator-discoverable: "what does my network look like + what
    needs configuration?"

Operator-named edge hardware (§1g):
  "Sharevdi Fanless Firewall Mini PC Firewall Router Intel J3710/N3710
   Quad Core, 4X Intel 2.5GbE i226-V LAN Ports, 8G DDR3 128G SSD AES NI
   Network Gateway Test with pf-Sense/opn-Sense"

CLI:
  network-topology.py detect [--json|--human]
                            Detect the full topology (interface +
                            gateway + ISP NAT + OPNsense NAT + VPN
                            bridge state).

  network-topology.py opnsense status [--host H] [--json|--human]
                            OPNsense reachability + API connectivity
                            tier (reachable / authenticated / full-api).

  network-topology.py opnsense capabilities [--json|--human]
                            What integration features are unlocked
                            based on detected OPNsense state.

  network-topology.py interfaces [--json|--human]
                            Per-interface state (MAC, IP, MTU, link
                            speed, gateway).

  network-topology.py nat-chain [--json|--human]
                            NAT layers detected: how many hops between
                            workstation and public IPv4. Operator-named:
                            workstation → OPNsense (NAT 2) → ISP router
                            (NAT 1) → public.

Exit codes:
  0 ok
  1 unknown subcommand
  2 detection failed (e.g., no network access)

Layer B metric (SDD-016):
  sovereign_os_operator_network_topology_query_total{verb,result}

Operator-environment env vars:
  SOVEREIGN_OS_OPNSENSE_HOST    OPNsense management address (default:
                                 auto-detected from default gateway)
  SOVEREIGN_OS_OPNSENSE_API_KEY API key for unlocked-capability tier
                                 (NEVER stored in-repo per operator
                                  mandate "Operator-supplied keys NEVER
                                  in-repo"). When set + reachable,
                                  unlocks full-api tier.
  SOVEREIGN_OS_OPNSENSE_API_SECRET  Companion secret (same mandate)
  SOVEREIGN_OS_OPNSENSE_API_PORT    HTTPS port (default: 443)
  SOVEREIGN_OS_DRY_RUN          Logs intent; no probes/writes.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

# Metrics output dir
METRICS_DIR = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
))
DRY_RUN = bool(os.environ.get("SOVEREIGN_OS_DRY_RUN"))

# Operator-named edge hardware (§1g verbatim spec)
OPERATOR_NAMED_EDGE_HARDWARE = {
    "model": "Sharevdi Fanless Firewall Mini PC",
    "cpu": "Intel J3710/N3710 Quad Core",
    "lan_ports": "4× Intel 2.5GbE i226-V",
    "ram": "8G DDR3",
    "storage": "128G SSD",
    "features": "AES-NI",
    "firmware": "pfSense/OPNsense",
}

# RFC 1918 private ranges + RFC 6598 CGNAT range
PRIVATE_NETS = [
    ("10.0.0.0", 8),       # RFC 1918 — most home LANs
    ("172.16.0.0", 12),    # RFC 1918 — Docker default
    ("192.168.0.0", 16),   # RFC 1918 — common home/office
    ("100.64.0.0", 10),    # RFC 6598 — CGNAT
]


def _emit_metric(name: str, verb: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises.

    Signature: first arg is the metric NAME (the literal that the
    metric-inventory-lockstep lint at R443 detects via regex match
    on `_?emit_metric("sovereign_os_...`)."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {name}"
            f"{{verb=\"{verb}\",result=\"{result}\"}} 1\n"
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-operator-network-topology.prom"
        line = (
            f'{name}'
            f'{{verb="{verb}",result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


# -------------------- detection primitives --------------------


def _ip_to_int(ip: str) -> int:
    try:
        return sum(int(o) << (8 * (3 - i))
                   for i, o in enumerate(ip.split(".")))
    except (ValueError, AttributeError):
        return 0


def _is_private_ipv4(ip: str) -> bool:
    """RFC 1918 + RFC 6598 (CGNAT)."""
    if not ip or ":" in ip:
        return False
    n = _ip_to_int(ip)
    for net, bits in PRIVATE_NETS:
        net_int = _ip_to_int(net)
        mask = (-1 << (32 - bits)) & 0xFFFFFFFF
        if (n & mask) == (net_int & mask):
            return True
    return False


def _run(cmd: list[str], timeout: int = 3) -> tuple[int, str, str]:
    """Run a command, return (rc, stdout, stderr). Never raises."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout, r.stderr
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return -1, "", ""


def detect_interfaces() -> list[dict]:
    """Enumerate IPv4 interfaces with MTU + link state."""
    out = []
    rc, stdout, _ = _run(["ip", "-j", "addr"], timeout=3)
    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            for iface in data:
                name = iface.get("ifname", "?")
                if name == "lo":
                    continue
                addrs = []
                for ai in iface.get("addr_info") or []:
                    if ai.get("family") == "inet":
                        addrs.append(f"{ai.get('local')}/{ai.get('prefixlen')}")
                out.append({
                    "name": name,
                    "mac": iface.get("address", ""),
                    "mtu": iface.get("mtu"),
                    "state": iface.get("operstate", "UNKNOWN"),
                    "addrs": addrs,
                    "type": iface.get("link_type", ""),
                })
        except json.JSONDecodeError:
            pass
    return out


def detect_default_gateway() -> dict:
    """Default gateway + interface + metric."""
    rc, stdout, _ = _run(["ip", "-j", "route", "show", "default"], timeout=3)
    if rc != 0 or not stdout.strip():
        return {}
    try:
        data = json.loads(stdout)
        if not data:
            return {}
        r = data[0]
        return {
            "gateway": r.get("gateway"),
            "device": r.get("dev"),
            "metric": r.get("metric", 0),
            "protocol": r.get("protocol", "?"),
        }
    except json.JSONDecodeError:
        return {}


def detect_nat_chain() -> dict:
    """Detect NAT layers via traceroute-like reachability checks.

    Operator-named topology:
      workstation (RFC1918 IP) → OPNsense (NAT 2, RFC1918) →
      ISP router (NAT 1, often RFC1918 LAN side, public WAN side) →
      public Internet (public IPv4)

    We can't actually traceroute without privilege escalation in many
    containers, so we do a SAFE heuristic detection:
      - Workstation IP is private → at least 1 NAT layer
      - Default gateway is private → at least 1 NAT layer (the gateway
        we route through)
      - Compare workstation /24 to gateway IP → are they on the same LAN?

    This gives operator-readable structure without requiring root."""
    gw = detect_default_gateway()
    if not gw:
        return {
            "available": False,
            "reason": "no default gateway detected",
        }

    gateway_ip = gw.get("gateway", "")
    device = gw.get("device", "")

    # Find our IP on that device
    interfaces = detect_interfaces()
    own_ip = None
    for iface in interfaces:
        if iface.get("name") == device:
            for a in iface.get("addrs") or []:
                if "/" in a:
                    own_ip = a.split("/")[0]
                    break
            break

    if not own_ip:
        return {
            "available": False,
            "reason": f"no IPv4 address on device {device}",
        }

    # Classify
    workstation_is_private = _is_private_ipv4(own_ip)
    gateway_is_private = _is_private_ipv4(gateway_ip)

    # Estimate NAT layers
    nat_layers: list[dict] = []
    if workstation_is_private:
        nat_layers.append({
            "layer": "workstation-to-LAN",
            "workstation_ip": own_ip,
            "gateway_ip": gateway_ip,
            "private_to_private": gateway_is_private,
        })

    # The operator-named topology: 2 NAT layers (OPNsense + ISP router)
    # The workstation only sees the IMMEDIATE gateway. To detect the
    # 2nd NAT we'd need to query OPNsense's WAN-side IP via the
    # OPNsense API — which is precisely why §1g says "I can even
    # create a user and an API key and then it unlock other
    # capabilities".

    # Public-IP detection (operator-discoverable: am I behind NAT at all?)
    public_ip_hint = None
    # SAFE check: try a stunserver-style probe? Skip in default mode
    # (requires outbound DNS + UDP); just report what we can see.

    return {
        "available": True,
        "workstation_ip": own_ip,
        "workstation_is_private": workstation_is_private,
        "default_gateway": gateway_ip,
        "gateway_is_private": gateway_is_private,
        "device": device,
        "nat_layers_visible": len(nat_layers),
        "nat_layers": nat_layers,
        "note": (
            "Visible NAT layers count from the workstation's vantage. "
            "Per operator §1g topology (workstation → OPNsense → ISP "
            "router → public), there are typically 2 NAT layers BUT "
            "the 2nd is invisible without querying OPNsense's WAN-side "
            "IP. Configure SOVEREIGN_OS_OPNSENSE_API_KEY + use "
            "`opnsense status` to unlock full topology view."
        ),
    }


def detect_vpn_bridge() -> dict:
    """Detect VPN tunnel interfaces (wireguard, openvpn, tailscale)."""
    interfaces = detect_interfaces()
    candidates = []
    for iface in interfaces:
        name = iface.get("name", "")
        link_type = iface.get("type", "")
        # Common VPN interface names
        if any(p in name for p in ("wg", "tun", "tap", "tailscale",
                                     "ts", "wgX", "wg-")):
            candidates.append({
                "name": name,
                "state": iface.get("state"),
                "addrs": iface.get("addrs") or [],
                "kind": (
                    "wireguard" if "wg" in name else
                    "tailscale" if "tail" in name or name.startswith("ts") else
                    "openvpn" if name.startswith(("tun", "tap")) else
                    "other"
                ),
            })
    return {
        "vpn_active": bool(candidates),
        "count": len(candidates),
        "interfaces": candidates,
    }


def detect_opnsense_state() -> dict:
    """OPNsense reachability + API connectivity tier."""
    # Operator escape hatch: SOVEREIGN_OS_OPNSENSE_DISABLE=1 short-circuits
    # the entire detection (gateway lookup + TCP probe of ports 443/80/22)
    # so an operator who knowingly has no upstream OPNsense — or a CI
    # environment that lacks network egress to the runner's gateway —
    # gets an instant tier="disabled" instead of multi-second probing.
    if os.environ.get("SOVEREIGN_OS_OPNSENSE_DISABLE", "") in ("1", "true", "yes"):
        return {
            "tier": "disabled",
            "host": None,
            "reason": "SOVEREIGN_OS_OPNSENSE_DISABLE set",
        }

    host = os.environ.get("SOVEREIGN_OS_OPNSENSE_HOST", "")
    api_key = os.environ.get("SOVEREIGN_OS_OPNSENSE_API_KEY", "")
    api_secret = os.environ.get("SOVEREIGN_OS_OPNSENSE_API_SECRET", "")
    api_port = os.environ.get("SOVEREIGN_OS_OPNSENSE_API_PORT", "443")

    # Auto-detect host: default gateway IP if not configured
    if not host:
        gw = detect_default_gateway()
        host = gw.get("gateway", "")

    if not host:
        return {
            "tier": "absent",
            "reason": "no OPNSENSE_HOST configured and no default gateway",
            "host": None,
        }

    # Tier 1: reachable (TCP/443 + TCP/22 + TCP/80)
    reachable_ports = []
    for port_try in (443, 80, 22):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex((host, port_try)) == 0:
                    reachable_ports.append(port_try)
        except (OSError, socket.error):
            pass

    if not reachable_ports:
        return {
            "tier": "unreachable",
            "host": host,
            "reason": "no TCP/22/80/443 reachable on candidate host",
            "next_step": (
                "Confirm OPNsense is at this address. Override with "
                "SOVEREIGN_OS_OPNSENSE_HOST=<ip>."
            ),
        }

    # Tier 2: API credentials configured?
    if not api_key or not api_secret:
        return {
            "tier": "reachable-no-credentials",
            "host": host,
            "reachable_ports": reachable_ports,
            "reason": "OPNsense reachable but no API credentials configured",
            "next_step": (
                "Per operator §1g 'I can even create a user and an API "
                "key': in OPNsense create a user + API key + secret, "
                "then export SOVEREIGN_OS_OPNSENSE_API_KEY + "
                "SOVEREIGN_OS_OPNSENSE_API_SECRET to unlock the "
                "full-api tier."
            ),
            "unlocks": "topology / capabilities / state-awareness verbs "
                        "currently disabled",
        }

    # Tier 3: try a no-op API call to verify credentials
    # OPNsense API endpoint /api/core/firmware/status is a safe read-only
    api_url = f"https://{host}:{api_port}/api/core/firmware/status"
    # We don't have requests stdlib; use curl as a safe probe
    rc, stdout, stderr = _run([
        "curl", "-sS", "-k", "--max-time", "3",
        "-u", f"{api_key}:{api_secret}",
        api_url,
    ], timeout=5)
    if rc == 0 and stdout:
        try:
            payload = json.loads(stdout)
            return {
                "tier": "full-api",
                "host": host,
                "reachable_ports": reachable_ports,
                "api_url": api_url,
                "api_response_keys": list(payload.keys())[:10],
                "unlocks": (
                    "Per operator §1g: integration features unlocked. "
                    "topology / capabilities / state-awareness fully "
                    "available."
                ),
            }
        except json.JSONDecodeError:
            return {
                "tier": "reachable-credentials-rejected",
                "host": host,
                "reachable_ports": reachable_ports,
                "reason": "API responded but not JSON; key/secret may be wrong",
            }
    return {
        "tier": "reachable-curl-failed",
        "host": host,
        "reachable_ports": reachable_ports,
        "reason": (
            f"curl probe failed (rc={rc}); install curl, or check "
            f"key+secret, or verify HTTPS port."
        ),
    }


def detect_capabilities() -> dict:
    """What integration features are unlocked based on OPNsense state."""
    opnsense = detect_opnsense_state()
    tier = opnsense.get("tier", "absent")

    # Operator-named capability tiers
    matrix = {
        "absent": {
            "unlocked": [],
            "available": [
                "workstation-local-firewall (no edge — install IPS-class "
                "alternative on workstation per E11.M9)"
            ],
        },
        "unreachable": {
            "unlocked": [],
            "available": [
                "workstation-local-firewall (edge present but not "
                "reachable from workstation)"
            ],
        },
        "reachable-no-credentials": {
            "unlocked": [
                "topology-passive-detection (NAT layers from workstation "
                "vantage only)",
                "reachability-monitoring (ping + TCP-probe)",
            ],
            "available": [
                "Configure API key + secret to unlock the full-api tier.",
            ],
        },
        "reachable-credentials-rejected": {
            "unlocked": [
                "topology-passive-detection",
                "reachability-monitoring",
            ],
            "available": [
                "Verify API key + secret in OPNsense System → Access → Users.",
            ],
        },
        "reachable-curl-failed": {
            "unlocked": [
                "topology-passive-detection",
                "reachability-monitoring",
            ],
            "available": [
                "Install curl (or python3-requests) to enable API probe.",
            ],
        },
        "full-api": {
            "unlocked": [
                "topology-passive-detection",
                "reachability-monitoring",
                "topology-active-detection (WAN-side IP via OPNsense API)",
                "firewall-rules-read (OPNsense rule inspection)",
                "interface-state-read (per-interface live status)",
                "vpn-tunnel-state-read",
                "system-status-read (CPU / RAM / temp via API)",
            ],
            "available": [],
        },
    }
    info = matrix.get(tier, matrix["absent"])
    return {
        "tier": tier,
        "unlocked_count": len(info["unlocked"]),
        "unlocked": info["unlocked"],
        "next_to_unlock": info["available"],
    }


# -------------------- CLI verbs --------------------


def cmd_detect(args) -> int:
    interfaces = detect_interfaces()
    gateway = detect_default_gateway()
    nat_chain = detect_nat_chain()
    vpn = detect_vpn_bridge()
    opnsense = detect_opnsense_state()
    capabilities = detect_capabilities()

    out = {
        "interfaces_count": len(interfaces),
        "default_gateway": gateway,
        "nat_chain": nat_chain,
        "vpn_bridge": vpn,
        "opnsense": opnsense,
        "capabilities": capabilities,
        "operator_named_edge_hardware": OPERATOR_NAMED_EDGE_HARDWARE,
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print("── network-topology.detect ──")
        print(f"  Interfaces: {len(interfaces)}")
        if gateway:
            print(f"  Default gateway: {gateway.get('gateway')} via {gateway.get('device')}")
        if nat_chain.get("available"):
            print(f"  Visible NAT layers: {nat_chain['nat_layers_visible']}")
            print(f"  Workstation IP: {nat_chain['workstation_ip']} (private={nat_chain['workstation_is_private']})")
        print(f"  VPN bridge: {'ACTIVE' if vpn['vpn_active'] else 'absent'} "
              f"({vpn['count']} interface(s))")
        print(f"  OPNsense tier: {opnsense.get('tier')}")
        print(f"  Capabilities unlocked: {capabilities['unlocked_count']}/{capabilities['unlocked_count'] + len(capabilities['next_to_unlock'])}")
        if capabilities['next_to_unlock']:
            print(f"  Next-to-unlock: {capabilities['next_to_unlock'][0]}")
    _emit_metric("sovereign_os_operator_network_topology_query_total", "detect", "ok")
    return 0


def cmd_opnsense(args) -> int:
    sub = args.opnsense_verb
    if sub == "status":
        out = detect_opnsense_state()
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(f"── network-topology.opnsense.status ──")
            for k, v in out.items():
                if isinstance(v, list):
                    v = ", ".join(str(x) for x in v) if v else "(none)"
                print(f"  {k:<22} {v}")
        _emit_metric("sovereign_os_operator_network_topology_query_total", "opnsense_status", out.get("tier", "unknown"))
        return 0
    if sub == "capabilities":
        out = detect_capabilities()
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(f"── network-topology.opnsense.capabilities (tier={out['tier']}) ──")
            print(f"  Unlocked ({out['unlocked_count']}):")
            for c in out["unlocked"]:
                print(f"    ✓ {c}")
            if out["next_to_unlock"]:
                print(f"  Next to unlock:")
                for c in out["next_to_unlock"]:
                    print(f"    → {c}")
        _emit_metric("sovereign_os_operator_network_topology_query_total", "opnsense_capabilities", out.get("tier", "unknown"))
        return 0
    if sub == "watch":
        return cmd_opnsense_watch(args)
    sys.stderr.write(f"unknown opnsense subcommand: {sub}\n")
    return 1


def cmd_interfaces(args) -> int:
    interfaces = detect_interfaces()
    if args.fmt == "json":
        print(json.dumps({"interfaces": interfaces}, indent=2))
    else:
        print(f"── network-topology.interfaces ({len(interfaces)}) ──")
        print(f"  {'NAME':<14} {'STATE':<8} {'MTU':>6}  {'ADDRS'}")
        for i in interfaces:
            addrs = ",".join(i.get("addrs") or []) or "-"
            print(f"  {i.get('name'):<14} {i.get('state'):<8} {str(i.get('mtu') or '-'):>6}  {addrs}")
    _emit_metric("sovereign_os_operator_network_topology_query_total", "interfaces", "ok")
    return 0


def cmd_nat_chain(args) -> int:
    out = detect_nat_chain()
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print("── network-topology.nat-chain ──")
        for k, v in out.items():
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            print(f"  {k:<22} {v}")
    _emit_metric("sovereign_os_operator_network_topology_query_total", "nat_chain",
                  "ok" if out.get("available") else "unavailable")
    return 0


def cmd_opnsense_watch(args) -> int:
    """R483 (E11.M8+) — OPNsense status TUI surface.

    Closes surface-map waiver-slot 'tui: FUTURE — OPNsense status TUI
    worthwhile' for the network-edge module. Refreshes the opnsense
    state + capabilities view every N seconds (default 5s, floored
    ≥1s) until Ctrl-C or --iterations N exhausts.

    Pairs with the existing one-shot `opnsense status` + `opnsense
    capabilities` verbs — same data, presented as a live-refresh TUI.

    Operator-discoverable: SOVEREIGN_OS_DRY_RUN=1 short-circuits to a
    single render (so L3 tests stay deterministic).
    """
    refresh = max(1, int(args.refresh))
    iterations = int(args.iterations)
    dry_run = os.environ.get("SOVEREIGN_OS_DRY_RUN", "") == "1"
    if dry_run and iterations == 0:
        iterations = 1

    frame = 0
    try:
        while True:
            state = detect_opnsense_state()
            caps = detect_capabilities()
            # ANSI clear-screen + home cursor (TUI refresh surface)
            sys.stdout.write("\x1b[2J\x1b[H")
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            print(f"── network-topology.opnsense watch  frame={frame}  "
                  f"now={now}  refresh={refresh}s ──")
            print("  (Ctrl-C to exit)" if iterations == 0
                  else f"  (iterations remaining: {iterations - frame})")
            print()
            print(f"  Tier:        {state.get('tier', 'unknown')}")
            print(f"  Host:        {state.get('host') or '(none)'}")
            print(f"  Reachable:   {state.get('reachable')}")
            print(f"  API status:  {state.get('api_status', 'n/a')}")
            print()
            print(f"  Capabilities unlocked: "
                  f"{caps['unlocked_count']}/"
                  f"{caps['unlocked_count'] + len(caps['next_to_unlock'])}")
            for c in caps.get("unlocked", []):
                print(f"    ✓ {c}")
            if caps.get("next_to_unlock"):
                print(f"  Next to unlock:")
                for c in caps["next_to_unlock"]:
                    print(f"    → {c}")
            sys.stdout.flush()
            _emit_metric(
                "sovereign_os_operator_network_topology_query_total",
                "opnsense_watch", state.get("tier", "unknown"),
            )
            frame += 1
            if iterations > 0 and frame >= iterations:
                break
            if dry_run:
                break
            time.sleep(refresh)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="network-topology.py",
        description=(
            "R449 (E11.M8) — sovereign-os network topology detection "
            "(§1g multi-NAT / VPN bridge / OPNsense integration)"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")
        sp.set_defaults(fmt="human")

    sp_detect = sub.add_parser("detect",
                                help="detect full network topology")
    add_fmt(sp_detect)

    sp_opn = sub.add_parser("opnsense", help="OPNsense state + capabilities")
    sp_opn.add_argument("opnsense_verb",
                         choices=["status", "capabilities", "watch"])
    sp_opn.add_argument("--refresh", type=int, default=5,
                         help="watch refresh seconds (min 1; default 5)")
    sp_opn.add_argument("--iterations", type=int, default=0,
                         help="watch bounded loop (0 = until Ctrl-C)")
    add_fmt(sp_opn)

    sp_iface = sub.add_parser("interfaces", help="per-interface state")
    add_fmt(sp_iface)

    sp_nat = sub.add_parser("nat-chain", help="NAT-layer detection")
    add_fmt(sp_nat)

    args = p.parse_args(argv)
    if args.cmd == "detect":
        return cmd_detect(args)
    if args.cmd == "opnsense":
        return cmd_opnsense(args)
    if args.cmd == "interfaces":
        return cmd_interfaces(args)
    if args.cmd == "nat-chain":
        return cmd_nat_chain(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
