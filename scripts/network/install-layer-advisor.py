#!/usr/bin/env python3
"""scripts/network/install-layer-advisor.py — R297 (E2.M11).

Operator-named (§1b mandate row, verbatim): "the DNS, the Cloudflared
? the tailscale, Traefik, non docker vs docker install ? when
possible ? container level vs system level". Closes E2.M11.

Focused advisor for the 4 specific NETWORK components the operator
named: DNS resolver, Cloudflared (Cloudflare Tunnel), Tailscale,
Traefik (reverse proxy). For EACH, declares:

  - supported install layers           (docker / system / both)
  - operator-recommended default       (per §1b preferences)
  - per-layer pros / cons              (operator-readable)
  - per-layer install command surface  (operator runs by hand)
  - coexistence notes                  (when components share a layer)

Operator-pull: list / show / coexist / recommend. Read-only — never
installs. Operator runs the listed commands.

Operator-overlay (R283/SDD-030): /etc/sovereign-os/network-install-
advisor.toml. Lists REPLACE — operator's catalog overrides defaults.

CLI:
  install-layer-advisor.py list      [--config P] [--json|--human]
  install-layer-advisor.py show      <component> [--config P] [--json|--human]
  install-layer-advisor.py coexist   [--config P] [--json|--human]
  install-layer-advisor.py recommend [--config P] [--json|--human]

Exit codes:
  0  rendered
  1  unknown component
  2  usage error
"""
from __future__ import annotations

import argparse
import json
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
ROUND = "R297"
SDD_VECTOR = "E2.M11"


# ── Network component install-layer catalog ─────────────────────────
#
# Each entry: name, layers[], default_layer, coexistence notes.
DEFAULT_CATALOG: list[dict[str, Any]] = [
    # ── DNS resolver ──────────────────────────────────────────
    {
        "name": "dns",
        "category": "dns-resolver",
        "summary": "Local DNS resolver — caches + recursively resolves "
                   "for the host and (optionally) the LAN.",
        "default_layer": "system",
        "layers": [
            {
                "layer": "system",
                "supported": True,
                "install": ["apt install -y systemd-resolved", "systemctl enable --now systemd-resolved"],
                "pros": [
                    "Already shipped on Debian 13 (no extra package).",
                    "Integrates with networkd / NetworkManager nameserver lists.",
                    "DNSSEC verification + DNS-over-TLS support.",
                ],
                "cons": [
                    "Less flexible than dnsmasq for LAN-wide hairpin DNS.",
                ],
            },
            {
                "layer": "docker",
                "supported": True,
                "install": [
                    "docker run -d --name dns --network host "
                    "-v /etc/dnsmasq.conf:/etc/dnsmasq.conf:ro "
                    "andyshinn/dnsmasq",
                ],
                "pros": [
                    "Easier to swap resolvers (pi-hole / adguard / etc).",
                    "Operator can pin a specific upstream config.",
                ],
                "cons": [
                    "Conflicts with systemd-resolved on port 53 — "
                    "operator must disable resolved.",
                    "Container start ordering matters at boot.",
                ],
            },
        ],
    },
    # ── Cloudflared (Cloudflare Tunnel) ───────────────────────
    {
        "name": "cloudflared",
        "category": "ingress-tunnel",
        "summary": "Cloudflare Tunnel egress-only ingress — no inbound "
                   "ports opened; dashboard reachable via *.example.com.",
        "default_layer": "system",
        "layers": [
            {
                "layer": "system",
                "supported": True,
                "install": [
                    "curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | "
                    "sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg",
                    "echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] "
                    "https://pkg.cloudflare.com/cloudflared bookworm main' | "
                    "sudo tee /etc/apt/sources.list.d/cloudflared.list",
                    "sudo apt update && sudo apt install -y cloudflared",
                    "sudo cloudflared service install <TUNNEL-TOKEN>",
                ],
                "pros": [
                    "First-party Debian package + systemd unit.",
                    "Auto-restart on update; survives reboots cleanly.",
                    "Operator's preferred for SAIN-01 (always-on host).",
                ],
                "cons": [
                    "Token persists in /etc/cloudflared/cert.pem — "
                    "operator must protect host root.",
                ],
            },
            {
                "layer": "docker",
                "supported": True,
                "install": [
                    "docker run -d --name cloudflared --restart unless-stopped "
                    "cloudflare/cloudflared:latest tunnel --no-autoupdate run "
                    "--token <TUNNEL-TOKEN>",
                ],
                "pros": [
                    "No host-level dependency on cloudflared APT repo.",
                    "Easier to rotate tunnels across hosts.",
                ],
                "cons": [
                    "Network namespace adds a small latency tax.",
                    "Docker must be running before the tunnel comes up — "
                    "ordering matters if cloudflared serves dashboard.",
                ],
            },
        ],
    },
    # ── Tailscale ─────────────────────────────────────────────
    {
        "name": "tailscale",
        "category": "private-mesh-vpn",
        "summary": "WireGuard-based mesh VPN — operator devices "
                   "see each other on private IPs without port-forward.",
        "default_layer": "system",
        "layers": [
            {
                "layer": "system",
                "supported": True,
                "install": [
                    "curl -fsSL https://tailscale.com/install.sh | sh",
                    "sudo tailscale up --authkey <KEY> --ssh "
                    "--advertise-tags=tag:sain01",
                ],
                "pros": [
                    "Kernel WireGuard module (best perf).",
                    "Magic-DNS works for host applications without "
                    "tunnel-pierce config.",
                    "tailscale serve / funnel = HTTPS dashboard "
                    "without Cloudflare.",
                ],
                "cons": [
                    "Operator-trusted curl-shell install (defense-in-"
                    "depth: SDD-030 R283 operator-deps gating).",
                ],
            },
            {
                "layer": "docker",
                "supported": True,
                "install": [
                    "docker run -d --name tailscale --network host "
                    "--cap-add NET_ADMIN --cap-add NET_RAW "
                    "-v tailscale-state:/var/lib/tailscale "
                    "-v /dev/net/tun:/dev/net/tun "
                    "tailscale/tailscale:latest",
                    "docker exec tailscale tailscale up --authkey <KEY>",
                ],
                "pros": [
                    "No host kernel module dependency.",
                    "Easy to wipe / re-auth without touching host.",
                ],
                "cons": [
                    "Magic-DNS doesn't propagate to host /etc/resolv.conf "
                    "unless operator wires it.",
                    "tailscale-serve port-binding gets messier under "
                    "docker NET_ADMIN.",
                ],
            },
        ],
    },
    # ── Traefik ────────────────────────────────────────────────
    {
        "name": "traefik",
        "category": "reverse-proxy",
        "summary": "Reverse proxy — multiplexes one host:port across "
                   "many backends with Let's Encrypt TLS automation.",
        "default_layer": "docker",
        "layers": [
            {
                "layer": "docker",
                "supported": True,
                "install": [
                    "docker network create traefik-proxy",
                    "docker run -d --name traefik --restart unless-stopped "
                    "--network traefik-proxy "
                    "-p 80:80 -p 443:443 "
                    "-v /var/run/docker.sock:/var/run/docker.sock:ro "
                    "-v /etc/traefik:/etc/traefik:ro "
                    "traefik:v3 "
                    "--providers.docker --providers.docker.exposedbydefault=false",
                ],
                "pros": [
                    "Native docker label-based routing — services "
                    "self-advertise via labels.",
                    "Hot-reload on container start/stop without "
                    "config edits.",
                    "Operator-preferred (§1b implicit — Traefik named "
                    "alongside Tailscale / Cloudflared as default).",
                ],
                "cons": [
                    "/var/run/docker.sock mount = full container "
                    "control — protect host root.",
                ],
            },
            {
                "layer": "system",
                "supported": True,
                "install": [
                    "apt install -y traefik",
                    "edit /etc/traefik/traefik.yml + /etc/traefik/dynamic/",
                    "systemctl enable --now traefik",
                ],
                "pros": [
                    "No docker dependency.",
                    "Easier to introspect from host (systemctl / journalctl).",
                ],
                "cons": [
                    "File-provider config requires explicit edits "
                    "per service — no auto-discovery.",
                    "Less common pattern — fewer reference recipes.",
                ],
            },
        ],
    },
]


# ── Lookups ─────────────────────────────────────────────────────────
def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_CATALOG)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "network-install-advisor",
            {"components": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("components"):
            catalog = list(cfg["components"])
    return catalog, meta


def resolve_component(catalog: list[dict], name: str) -> dict | None:
    for c in catalog:
        if isinstance(c, dict) and c.get("name") == name:
            return c
    return None


def coexistence_table(catalog: list[dict]) -> list[dict[str, Any]]:
    """For each component, list the layer it defaults to + any
    coexistence conflict (e.g. dnsmasq + systemd-resolved on port 53)."""
    rows = []
    for c in catalog:
        if not isinstance(c, dict):
            continue
        rows.append({
            "name": c.get("name"),
            "default_layer": c.get("default_layer"),
            "layers_supported": [l.get("layer") for l in (c.get("layers") or [])
                                 if isinstance(l, dict) and l.get("supported")],
        })
    # Cross-component conflict flags (operator-readable).
    notes = []
    if any(r["name"] == "dns" and "system" in r["layers_supported"] for r in rows):
        notes.append(
            "dns@system uses port 53 — docker dns containers conflict; "
            "operator must disable systemd-resolved first."
        )
    if any(r["name"] == "traefik" and r["default_layer"] == "docker" for r in rows):
        notes.append(
            "traefik@docker requires /var/run/docker.sock — only run "
            "Traefik in this layer when the host is single-tenant."
        )
    return {"rows": rows, "coexistence_notes": notes}


# ── Renderers ───────────────────────────────────────────────────────
def render_list_human(catalog: list[dict], meta: dict) -> str:
    lines = ["── R297 sovereign-os network install-layer advisor (E2.M11) ──"]
    lines.append(f"  source:   {meta.get('_source')}")
    lines.append(f"  components: {len(catalog)}")
    lines.append("")
    for c in catalog:
        if not isinstance(c, dict):
            continue
        lines.append(f"  • {c.get('name')}  ({c.get('category')})")
        lines.append(f"      default-layer: {c.get('default_layer')}")
        lines.append(f"      summary:       {c.get('summary')}")
        for l in (c.get("layers") or []):
            mark = "OK" if l.get("supported") else "--"
            lines.append(f"      [{mark}] {l.get('layer')}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(c: dict) -> str:
    lines = [f"── R297 {c.get('name')} install-layer detail (E2.M11) ──"]
    lines.append(f"  category:       {c.get('category')}")
    lines.append(f"  default layer:  {c.get('default_layer')}")
    lines.append(f"  summary:        {c.get('summary')}")
    lines.append("")
    for l in (c.get("layers") or []):
        lines.append(f"  ── {l.get('layer')} ──")
        lines.append(f"    supported: {l.get('supported')}")
        lines.append(f"    install commands:")
        for s in (l.get("install") or []):
            lines.append(f"      $ {s}")
        if l.get("pros"):
            lines.append(f"    pros:")
            for p in l["pros"]:
                lines.append(f"      + {p}")
        if l.get("cons"):
            lines.append(f"    cons:")
            for p in l["cons"]:
                lines.append(f"      − {p}")
        lines.append("")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="install-layer-advisor.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("component")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pc = sub.add_parser("coexist")
    pc.add_argument("--config", type=Path)
    fc = pc.add_mutually_exclusive_group()
    fc.add_argument("--json", dest="fmt", action="store_const", const="json")
    fc.add_argument("--human", dest="fmt", action="store_const", const="human")
    pc.set_defaults(fmt="json")

    pr = sub.add_parser("recommend")
    pr.add_argument("--config", type=Path)
    fr = pr.add_mutually_exclusive_group()
    fr.add_argument("--json", dest="fmt", action="store_const", const="json")
    fr.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta = load_catalog(args.config)

    if args.verb == "list":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "component_count": len(catalog),
                "components": catalog,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(catalog, meta), end="")
        return 0

    if args.verb == "show":
        c = resolve_component(catalog, args.component)
        if c is None:
            print(json.dumps({
                "error": f"unknown component: {args.component}",
                "known": [x.get("name") for x in catalog if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "component": c,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(c), end="")
        return 0

    if args.verb == "coexist":
        ct = coexistence_table(catalog)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "rows": ct["rows"],
                "coexistence_notes": ct["coexistence_notes"],
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R297 coexistence table (E2.M11) ──")
            for r in ct["rows"]:
                print(f"  • {r['name']}: default={r['default_layer']}, "
                      f"layers={', '.join(r['layers_supported'])}")
            print()
            for n in ct["coexistence_notes"]:
                print(f"  ! {n}")
        return 0

    if args.verb == "recommend":
        recs = [
            {
                "component": c.get("name"),
                "recommended_layer": c.get("default_layer"),
            }
            for c in catalog if isinstance(c, dict)
        ]
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "recommendations": recs,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R297 operator-default recommendations (E2.M11) ──")
            for r in recs:
                print(f"  • {r['component']} → {r['recommended_layer']}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
