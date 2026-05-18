#!/usr/bin/env python3
"""scripts/interop/mcp-aggregate.py — R286 (E7.M5).

Operator-named (§1b mandate row): "Cross-repo MCP-tool aggregator
(sovereign-os surfaces selfdef tools too)". Also closes Q-019
("lifecycle-management MCP for sovereign-os") referenced in SDD-002
§4 / §Q-D.

Emits a unified manifest of MCP tools spanning sovereign-os local
read-only verbs PLUS, when --upstream-selfdef <host>:<port> is given,
the selfdef MCP TCP transport (SD-R94) is referenced as a proxy
namespace. The manifest is the deliverable: any MCP-aware client
(Claude Code, custom agents, the operator's REPL) consumes it to know
which tools are available + how to invoke them across both repos.

Operator-overlay-doctrine (R283 / SDD-030) honoured: the optional
config file `/etc/sovereign-os/mcp-aggregate.toml` (or
SOVEREIGN_OS_OVERLAY_MCP_AGGREGATE env var, or --config <path>) lets
the operator add/remove/relabel tools without editing this script.

CLI:
  mcp-aggregate.py manifest [--upstream-selfdef <host>:<port>]
                            [--config <path>]
                            [--json|--human]
  mcp-aggregate.py probe-upstream <host>:<port>
                            (TCP connect probe; reports reachable=true/false)

Exit codes:
  0  manifest emitted / probe succeeded
  1  probe failed (host unreachable / port closed)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Bring in the R283 operator-overlay helper so this verb composes
# cleanly with every other operator-pull surface.
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover - helper is shipped in-repo
    load_with_overlay = None  # fallback handled below


SCHEMA_VERSION = "1.0.0"
ROUND = "R286"
SDD_VECTOR = "E7.M5 / closes Q-019 referenced in SDD-002"


# ---- Local sovereign-os tool registry ---------------------------------
#
# Each entry advertises one read-only MCP tool exposed by sovereign-os.
# Mutating verbs (apply / set / write) are deliberately excluded from
# the default aggregate: lifecycle-management surfaces require their
# own triple-gate UX (SOVEREIGN_OS_CONFIRM_DESTROY=YES) which an MCP
# tool can't model safely without per-tool consent flow. Future round
# (Q-019 follow-on) can opt-in mutating tools behind an explicit
# `--include-mutating` flag with the same gate semantics as
# SELFDEF_MCP_ALLOW_WRITES=YES (SD-R96).
#
# Operator-mandate cross-axis coverage (each axis the operator named
# in §1b "all the angles" gets at least one MCP-tool entry):
#
#   Hardware/CPU/GPU/PSU/Memory : hardware, gpu-watch, gpu-card-advisor,
#                                 cpu-mode, memory-profile, memory-pressure,
#                                 ram-advisor, bios-info, power-status,
#                                 wasm-aot, zmm-ternary
#   Network/DNS/Reverse-proxy   : network, net-perf, dns-advisor,
#                                 reverse-proxy, perimeter
#   Modules / install layer     : install-paths, services-advisor
#   Health / observability      : health, severity, insights, fs, raid,
#                                 service-deps, services, events
#   Kernel / virt / pcie        : kernel, virt-info, pcie-policy
#   Dashboard / notify          : dashboard (grid), notify
#   AI / model lifecycle        : (model registry — sovereign-os ships
#                                  via `models` verb; surfaced read-only)
LOCAL_TOOLS = [
    # ── Hardware / CPU / GPU / PSU / Memory ─────────────────────
    {
        "name": "hardware",
        "summary": "Host hardware probe (CPU + memory + GPU + storage).",
        "argv": ["sovereign-osctl", "hardware", "--json"],
        "categories": ["hardware", "cpu", "gpu", "memory"],
    },
    {
        "name": "gpu-watch",
        "summary": "Live GPU watt + temperature + utilization (RTX 3090 / RTX PRO 6000).",
        "argv": ["sovereign-osctl", "gpu-watch", "--json"],
        "categories": ["gpu", "power", "thermal"],
    },
    {
        "name": "gpu-card-advisor",
        "summary": "Per-card advisories for RTX 3090 + RTX PRO 6000 dual-rig.",
        "argv": ["sovereign-osctl", "gpu-card-advisor", "--json"],
        "categories": ["gpu", "advisor"],
    },
    {
        "name": "cpu-mode",
        "summary": "CPU governor / mode hotswap + auto recommender.",
        "argv": ["sovereign-osctl", "cpu-mode", "show", "--json"],
        "categories": ["cpu", "lifecycle"],
    },
    {
        "name": "memory-profile",
        "summary": "Memory posture + XMP/EXPO detection.",
        "argv": ["sovereign-osctl", "memory-profile", "--json"],
        "categories": ["memory", "bios"],
    },
    {
        "name": "memory-pressure",
        "summary": "OOM watcher + memory-pressure Layer B metrics.",
        "argv": ["sovereign-osctl", "memory-pressure", "--json"],
        "categories": ["memory", "observability"],
    },
    {
        "name": "ram-advisor",
        "summary": "256 GB DDR5 advisor (ZFS ARC clamp, GGUF / model budget).",
        "argv": ["sovereign-osctl", "ram-advisor", "--json"],
        "categories": ["memory", "advisor", "ai"],
    },
    {
        "name": "bios-info",
        "summary": "BIOS + baseboard + ASUS ProArt X870E-CREATOR WIFI specifics.",
        "argv": ["sovereign-osctl", "bios-info", "--json"],
        "categories": ["bios", "board"],
    },
    {
        "name": "power-status",
        "summary": "PSU wattage budget + UPS battery + OC-mode multiplier.",
        "argv": ["sovereign-osctl", "power-status", "--json"],
        "categories": ["power", "psu", "ups"],
    },
    {
        "name": "wasm-aot",
        "summary": "Wasm-to-AVX-512 AOT pipeline (znver5 enforcement).",
        "argv": ["sovereign-osctl", "wasm-aot", "status", "--json"],
        "categories": ["cpu", "ai", "ahead-of-time"],
    },
    {
        "name": "zmm-ternary",
        "summary": "1-bit / ternary ZMM-register utilization probe (VPDPBUSD path).",
        "argv": ["sovereign-osctl", "zmm-ternary", "status", "--json"],
        "categories": ["cpu", "ai", "avx512"],
    },
    # ── Network / DNS / Reverse-proxy / Perimeter ────────────────
    {
        "name": "network",
        "summary": "Network interfaces + addresses + routing.",
        "argv": ["sovereign-osctl", "network", "--json"],
        "categories": ["network"],
    },
    {
        "name": "net-perf",
        "summary": "Network performance baseline (in/out).",
        "argv": ["sovereign-osctl", "net-perf", "status", "--json"],
        "categories": ["network", "observability"],
    },
    {
        "name": "dns-advisor",
        "summary": "DNS posture + advisories.",
        "argv": ["sovereign-osctl", "dns-advisor", "--json"],
        "categories": ["network", "dns", "advisor"],
    },
    {
        "name": "reverse-proxy",
        "summary": "Reverse-proxy (Traefik) posture + bind-iface check.",
        "argv": ["sovereign-osctl", "reverse-proxy", "status", "--json"],
        "categories": ["network", "proxy"],
    },
    {
        "name": "perimeter",
        "summary": "Perimeter posture (admin-iface guard).",
        "argv": ["sovereign-osctl", "perimeter", "--json"],
        "categories": ["network", "security"],
    },
    # ── Modules / install layer ──────────────────────────────────
    {
        "name": "install-paths",
        "summary": "Per-feature install-layer matrix (container vs system).",
        "argv": ["sovereign-osctl", "install-paths", "show", "--json"],
        "categories": ["modules", "install"],
    },
    {
        "name": "services-advisor",
        "summary": "Recommended services posture for this host.",
        "argv": ["sovereign-osctl", "services-advisor", "--json"],
        "categories": ["services", "advisor"],
    },
    # ── Health / observability / events ──────────────────────────
    {
        "name": "health",
        "summary": "Aggregate health rollup (severity + actionable).",
        "argv": ["sovereign-osctl", "health", "--json"],
        "categories": ["health", "doctor"],
    },
    {
        "name": "severity",
        "summary": "Cross-component severity rollup.",
        "argv": ["sovereign-osctl", "severity", "--json"],
        "categories": ["health", "rollup"],
    },
    {
        "name": "insights",
        "summary": "fs/log/telemetry synthesizer with prioritized insights.",
        "argv": ["sovereign-osctl", "insights", "--json"],
        "categories": ["observability", "insights"],
    },
    {
        "name": "fs",
        "summary": "Filesystem usage + partition rollup.",
        "argv": ["sovereign-osctl", "fs", "--json"],
        "categories": ["storage", "filesystem"],
    },
    {
        "name": "raid",
        "summary": "Software RAID observation.",
        "argv": ["sovereign-osctl", "raid", "--json"],
        "categories": ["storage", "raid"],
    },
    {
        "name": "service-deps",
        "summary": "Service dependency graph (drain ordering).",
        "argv": ["sovereign-osctl", "service-deps", "--json"],
        "categories": ["services", "graph"],
    },
    {
        "name": "services",
        "summary": "systemd services inventory + failures + timers.",
        "argv": ["sovereign-osctl", "services", "--json"],
        "categories": ["services"],
    },
    {
        "name": "events",
        "summary": "Aggregated event timeline (audit + notify + lifecycle).",
        "argv": ["sovereign-osctl", "events", "--json"],
        "categories": ["events", "audit"],
    },
    # ── Kernel / virt / pcie ─────────────────────────────────────
    {
        "name": "kernel",
        "summary": "Per-workload kernel tuning presets (sysctl + cmdline).",
        "argv": ["sovereign-osctl", "kernel", "list", "--json"],
        "categories": ["kernel", "tuning"],
    },
    {
        "name": "virt-info",
        "summary": "Virtualization probe (KVM + IOMMU + PCIe + runtimes).",
        "argv": ["sovereign-osctl", "virt-info", "--json"],
        "categories": ["virt", "pcie"],
    },
    {
        "name": "pcie-policy",
        "summary": "PCIe lane allocation policy advisor (dual-GPU split).",
        "argv": ["sovereign-osctl", "pcie-policy", "--json"],
        "categories": ["pcie", "advisor"],
    },
    # ── Dashboard / notify ───────────────────────────────────────
    {
        "name": "dashboard-grid",
        "summary": "1-line-per-card dashboard rollup (terminal view).",
        "argv": ["sovereign-osctl", "dashboard", "grid", "--json"],
        "categories": ["dashboard", "rollup"],
    },
    {
        "name": "notify-list",
        "summary": "Notification channels + recent deliveries.",
        "argv": ["sovereign-osctl", "notify", "list", "--json"],
        "categories": ["notify"],
    },
    # ── Master-dashboard (R499 — E11.M2++ MCP surface) ──────────────
    # Closes master-dashboard mcp:FUTURE waiver. Read-only mirror of
    # the R498 REST surface (scripts/operator/master-dashboard-api.py).
    # Mutation verbs (render / install) stay CLI-only — operator §17
    # sovereignty boundary.
    {
        "name": "master-dashboard-list",
        "summary": "Master-dashboard aggregator: list all dashboard routes (slug → port + subpath + label).",
        "argv": ["sovereign-osctl", "master-dashboard", "list", "--json"],
        "categories": ["master-dashboard", "aggregator", "operator-§1g"],
    },
    {
        "name": "master-dashboard-routes",
        "summary": "Master-dashboard aggregator: routing table the reverse-proxy would emit (per-port-direct / reverse-proxied / alternative-aggregator modes).",
        "argv": ["sovereign-osctl", "master-dashboard", "routes", "--json"],
        "categories": ["master-dashboard", "routing", "operator-§1g"],
    },
    {
        "name": "master-dashboard-collisions",
        "summary": "Master-dashboard aggregator: port + subpath collision detection across built-in routes and selfdef cross-repo manifests.",
        "argv": ["sovereign-osctl", "master-dashboard", "collisions", "--json"],
        "categories": ["master-dashboard", "validation", "operator-§1g"],
    },
    {
        "name": "master-dashboard-health",
        "summary": "Master-dashboard aggregator: TCP-probe every upstream dashboard port (Trinity tiers / router / Grafana / textfile-collector).",
        "argv": ["sovereign-osctl", "master-dashboard", "health", "--json"],
        "categories": ["master-dashboard", "observability", "operator-§1g"],
    },
    {
        "name": "master-dashboard-discover",
        "summary": "Master-dashboard aggregator: load selfdef cross-repo dashboard manifests under /etc/selfdef/dashboards/ (SD-R-DASHBOARD-MANIFEST-1).",
        "argv": ["sovereign-osctl", "master-dashboard", "discover", "--json"],
        "categories": ["master-dashboard", "cross-repo", "operator-§1g"],
    },
]


# ---- Upstream selfdef proxy descriptor --------------------------------
#
# When --upstream-selfdef <host>:<port> is given, the manifest carries
# a proxy descriptor — operator MCP clients connect to selfdef
# directly via the SD-R94 TCP transport. We don't actually proxy
# bytes in this round (that's its own SDD); we ANNOUNCE the upstream
# in the manifest so a client can wire both endpoints.
def upstream_descriptor(spec: str) -> dict:
    """Validate `<host>:<port>` and return a descriptor dict."""
    if ":" not in spec:
        raise SystemExit(f"--upstream-selfdef expects host:port; got {spec!r}")
    host, port_s = spec.rsplit(":", 1)
    try:
        port = int(port_s)
    except ValueError as e:
        raise SystemExit(f"invalid port in --upstream-selfdef: {port_s!r}") from e
    if not 1 <= port <= 65535:
        raise SystemExit(f"port out of range in --upstream-selfdef: {port}")
    return {
        "host": host,
        "port": port,
        "transport": "tcp",
        "protocol": "selfdef-mcp/SD-R94",
        "tool_namespace": "selfdef",
        "_notes": (
            "Tools in the `selfdef` namespace are proxied by connecting "
            "to this TCP endpoint with the SD-R94 MCP transport. "
            "Write-tools require SELFDEF_MCP_ALLOW_WRITES=YES on the "
            "selfdef side (SD-R96)."
        ),
    }


def probe_upstream(spec: str, timeout: float = 2.0) -> dict:
    """TCP connect probe to the upstream selfdef MCP endpoint."""
    desc = upstream_descriptor(spec)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    reachable = False
    err = None
    try:
        s.connect((desc["host"], desc["port"]))
        reachable = True
    except OSError as e:
        err = f"{type(e).__name__}: {e}"
    finally:
        s.close()
    return {
        "host": desc["host"],
        "port": desc["port"],
        "reachable": reachable,
        "timeout_s": timeout,
        "error": err,
    }


# ---- Manifest assembly ------------------------------------------------
def build_manifest(
    upstream_selfdef: str | None,
    overlay_path: Path | None,
) -> dict:
    # Operator overlay (R283) — optional add / remove / relabel.
    overlay_meta = {
        "_source": "(defaults — no overlay loaded)",
        "_overlay_keys": [],
    }
    overlay_extras: list[dict] = []
    overlay_exclude: set[str] = set()
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "mcp-aggregate",
            {"extra_tools": [], "exclude_tools": []},
            explicit_path=overlay_path,
        )
        overlay_meta["_source"] = cfg.get("_source", overlay_meta["_source"])
        overlay_meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            overlay_meta["_parse_error"] = cfg["_parse_error"]
        # Operator may carry [[extra_tools]] / exclude_tools = [...]
        for entry in cfg.get("extra_tools") or []:
            if isinstance(entry, dict) and "name" in entry and "argv" in entry:
                overlay_extras.append(
                    {
                        "name": str(entry["name"]),
                        "summary": str(entry.get("summary", "")),
                        "argv": [str(x) for x in entry["argv"]],
                        "categories": [str(c) for c in entry.get("categories", [])],
                        "namespace": "sovereign-os",
                        "transport": "exec",
                        "_source": "operator-overlay",
                    }
                )
        for n in cfg.get("exclude_tools") or []:
            overlay_exclude.add(str(n))

    tools: list[dict] = []
    for t in LOCAL_TOOLS:
        if t["name"] in overlay_exclude:
            continue
        tools.append(
            {
                "name": t["name"],
                "namespace": "sovereign-os",
                "summary": t["summary"],
                "transport": "exec",
                "argv": list(t["argv"]),
                "categories": list(t.get("categories", [])),
            }
        )
    tools.extend(overlay_extras)

    sources = [
        {
            "namespace": "sovereign-os",
            "transport": "exec",
            "tool_count": sum(1 for t in tools if t["namespace"] == "sovereign-os"),
        }
    ]
    upstream = None
    if upstream_selfdef:
        upstream = upstream_descriptor(upstream_selfdef)
        sources.append(
            {
                "namespace": upstream["tool_namespace"],
                "transport": upstream["transport"],
                "host": upstream["host"],
                "port": upstream["port"],
                "protocol": upstream["protocol"],
                "tool_count": "see selfdef.mcp_tools()",
            }
        )

    doc = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "sources": sources,
        "tools": tools,
        "tool_count": len(tools),
        "upstream_selfdef": upstream,
        "overlay": overlay_meta,
    }
    return doc


def render_human(doc: dict) -> str:
    lines = []
    lines.append(f"── R286 sovereign-os MCP-tool aggregate (E7.M5) ──")
    lines.append(f"  schema_version: {doc['schema_version']}")
    lines.append(f"  tool_count:     {doc['tool_count']}")
    if doc["upstream_selfdef"]:
        u = doc["upstream_selfdef"]
        lines.append(f"  upstream:       {u['host']}:{u['port']} "
                     f"({u['protocol']})")
    else:
        lines.append("  upstream:       (none — local sovereign-os tools only)")
    lines.append("")
    lines.append("Tools (namespace::name — summary):")
    for t in doc["tools"]:
        lines.append(f"  {t['namespace']}::{t['name']}")
        lines.append(f"     {t['summary']}")
    overlay_keys = doc.get("overlay", {}).get("_overlay_keys") or []
    if overlay_keys:
        lines.append("")
        lines.append(f"Overlay keys applied: {', '.join(overlay_keys)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mcp-aggregate.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pm = sub.add_parser("manifest", help="emit unified MCP-tool manifest")
    pm.add_argument("--upstream-selfdef", metavar="HOST:PORT",
                    help="reference a selfdef MCP TCP endpoint (SD-R94)")
    pm.add_argument("--config", type=Path, metavar="PATH",
                    help="explicit operator-overlay TOML path")
    fmt = pm.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
    fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
    pm.set_defaults(fmt="json")

    pp = sub.add_parser("probe-upstream", help="TCP-connect probe")
    pp.add_argument("upstream", metavar="HOST:PORT")
    pp.add_argument("--timeout", type=float, default=2.0)
    pp.add_argument("--json", action="store_true")

    args = p.parse_args(argv)

    if args.verb == "manifest":
        doc = build_manifest(args.upstream_selfdef, args.config)
        if args.fmt == "json":
            print(json.dumps(doc, indent=2))
        else:
            print(render_human(doc), end="")
        return 0

    if args.verb == "probe-upstream":
        res = probe_upstream(args.upstream, timeout=args.timeout)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            mark = "REACHABLE" if res["reachable"] else "UNREACHABLE"
            print(f"{mark}  {res['host']}:{res['port']}  (timeout {res['timeout_s']}s)")
            if res["error"]:
                print(f"  error: {res['error']}")
        return 0 if res["reachable"] else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
