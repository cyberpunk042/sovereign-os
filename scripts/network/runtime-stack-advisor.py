#!/usr/bin/env python3
"""scripts/network/runtime-stack-advisor.py — R319 (E3.M7).

Stop-hook flagged (verbatim): "no comprehensive DNS/Cloudflared/
Tailscale/Traefik network advisor surface beyond install-mode
(R310)". Closes E3.M7 — fills the gap with a per-service runtime
probe + troubleshoot guide layer on top of R263 posture / R268 DNS /
R220 network-state.

scripts/network/runtime-stack-advisor.py + sovereign-osctl
network-stack:

  network-stack status                 [--config P] [--json|--human]
                                          probe all services; per-service
                                          installed / running / healthy
                                          + aggregate verdict
  network-stack list                   [--config P] [--json|--human]
                                          catalog of services + axes
  network-stack troubleshoot <service> [--config P] [--json|--human]
                                          operator-pull diagnostic steps

5 services across 3 axes (tunnel / reverse-proxy / dns / ids):
  tailscale         tunnel
  cloudflared       tunnel
  traefik           reverse-proxy
  systemd-resolved  dns
  suricata          ids

Per-service probe = systemctl is-active for the unit name; per-service
troubleshoot guide = 4-7 operator-runnable diagnostic steps that walk
the OS check / config check / log check / restart procedure.

Operator-overlay (R283/SDD-030): /etc/sovereign-os/network-stack-
advisor.toml adds [[services]] entries OR overrides per-service
fields.

Exit codes:
  0  all probable services healthy
  1  ≥1 service missing or unhealthy
  2  usage error
"""
from __future__ import annotations

import argparse
import json
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
ROUND = "R319"
SDD_VECTOR = "E3.M7"


DEFAULT_SERVICES: list[dict[str, Any]] = [
    {
        "name": "tailscale",
        "axis": "tunnel",
        "unit": "tailscaled.service",
        "expected_when": "always (sovereign-os network baseline)",
        "binary": "tailscale",
        "config_path": "/var/lib/tailscale/tailscaled.state",
        "troubleshoot": [
            "1. Check daemon: `systemctl status tailscaled`",
            "2. Check connectivity: `tailscale status`",
            "3. Verify auth: `tailscale up` (operator re-auth if "
            "needed; needs auth-key for unattended)",
            "4. Check DNS: `tailscale netcheck` reveals NAT type + "
            "DERP-region selected",
            "5. Logs: `journalctl -u tailscaled -n 200 --no-pager`",
            "6. Network: `ip addr show tailscale0` confirms the "
            "interface has a 100.64.0.0/10 address",
        ],
    },
    {
        "name": "cloudflared",
        "axis": "tunnel",
        "unit": "cloudflared.service",
        "expected_when": "operator declares cf-tunnel in /etc/sovereign-os/...",
        "binary": "cloudflared",
        "config_path": "/etc/cloudflared/config.yml",
        "troubleshoot": [
            "1. Check daemon: `systemctl status cloudflared`",
            "2. Validate config: `cloudflared tunnel ingress validate`",
            "3. Check tunnel state: `cloudflared tunnel list`",
            "4. Token: verify /etc/cloudflared/cert.pem present + "
            "not expired",
            "5. Logs: `journalctl -u cloudflared -n 200 --no-pager`",
            "6. Connectivity: `cloudflared tunnel info <tunnel-name>` "
            "shows connector status from CF side",
        ],
    },
    {
        "name": "traefik",
        "axis": "reverse-proxy",
        "unit": "traefik.service",
        "expected_when": "operator deploys via container or system; "
                          "see R310 install-mode",
        "binary": "traefik",
        "config_path": "/etc/traefik/traefik.yml",
        "troubleshoot": [
            "1. Check daemon: `systemctl status traefik` "
            "(system mode) OR `docker ps` (container mode)",
            "2. API ping: `curl http://localhost:8080/ping` should "
            "return 'OK'",
            "3. Routers: `curl http://localhost:8080/api/http/routers "
            "| jq` reveals dynamic config state",
            "4. Cert resolvers: check ACME storage path "
            "/etc/traefik/acme.json (mode 0600)",
            "5. Logs: `journalctl -u traefik -n 200 --no-pager`",
            "6. Backend reach: from traefik container/host, curl "
            "each backend service URL",
        ],
    },
    {
        "name": "systemd-resolved",
        "axis": "dns",
        "unit": "systemd-resolved.service",
        "expected_when": "always (Debian 13 default DNS resolver)",
        "binary": "resolvectl",
        "config_path": "/etc/systemd/resolved.conf",
        "troubleshoot": [
            "1. Check daemon: `systemctl status systemd-resolved`",
            "2. Current resolvers: `resolvectl status` shows per-link DNS",
            "3. Test resolution: `resolvectl query example.com`",
            "4. Verify upstream: `resolvectl statistics`",
            "5. DNSSEC state: `resolvectl dnssec` reports per-link mode",
            "6. Compare to R268 DNS posture advisor for "
            "Cloudflare/Quad9/AdGuard recommendations",
        ],
    },
    {
        "name": "suricata",
        "axis": "ids",
        "unit": "suricata.service",
        "expected_when": "operator installs selfdef suricata module",
        "binary": "suricata",
        "config_path": "/etc/suricata/suricata.yaml",
        "troubleshoot": [
            "1. Check daemon: `systemctl status suricata`",
            "2. Rule load: `suricata --build-info | grep rule` shows "
            "rule count loaded",
            "3. EVE JSON output: `tail -n 50 /var/log/suricata/eve.json "
            "| jq` reveals recent events",
            "4. AF_PACKET interface: `journalctl -u suricata` shows "
            "interface bind state",
            "5. Drop test: temporarily trigger ICMP rule + verify EVE "
            "logs the alert",
            "6. Compose with selfdef-collector-tetragon for combined "
            "L3/L7 visibility",
        ],
    },
]


def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_SERVICES)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "network-stack-advisor", {"services": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("services"):
            # Overlay services replace by `name` match; new names append.
            by_name = {s["name"]: s for s in catalog
                        if isinstance(s, dict) and s.get("name")}
            for s in cfg["services"]:
                if isinstance(s, dict) and s.get("name"):
                    by_name[s["name"]] = s
            catalog = list(by_name.values())
    return catalog, meta


def probe_service(service: dict) -> dict[str, Any]:
    """Per-service probe via systemctl is-active + which <binary>."""
    out: dict[str, Any] = {
        "name": service.get("name"),
        "axis": service.get("axis"),
        "unit": service.get("unit"),
        "installed": None,
        "running": None,
        "healthy": None,
        "detail": "",
    }
    bin_name = service.get("binary")
    if bin_name:
        try:
            r = subprocess.run(
                ["which", bin_name], capture_output=True,
                text=True, timeout=3, check=False,
            )
            out["installed"] = (r.returncode == 0
                                  and bool((r.stdout or "").strip()))
        except (OSError, subprocess.TimeoutExpired):
            out["installed"] = None
    unit = service.get("unit")
    if unit:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True, text=True, timeout=3, check=False,
            )
            state = (r.stdout or "").strip()
            out["running"] = (state == "active")
            out["detail"] = f"systemctl is-active={state}"
        except (OSError, subprocess.TimeoutExpired):
            out["running"] = None
            out["detail"] = "systemctl probe failed"
    # Healthy = installed AND running. None when probe failed.
    if out["installed"] is None or out["running"] is None:
        out["healthy"] = None
    else:
        out["healthy"] = bool(out["installed"] and out["running"])
    return out


def aggregate(probes: list[dict]) -> tuple[str, int, dict]:
    healthy = sum(1 for p in probes if p.get("healthy") is True)
    unhealthy = sum(1 for p in probes if p.get("healthy") is False)
    unprobed = sum(1 for p in probes if p.get("healthy") is None)
    if unhealthy > 0:
        return "degraded", 1, {"healthy": healthy, "unhealthy": unhealthy,
                                 "unprobed": unprobed}
    return "ok", 0, {"healthy": healthy, "unhealthy": unhealthy,
                       "unprobed": unprobed}


def filter_axis(catalog: list[dict], axis: str | None) -> list[dict]:
    if axis is None:
        return list(catalog)
    return [s for s in catalog if isinstance(s, dict) and s.get("axis") == axis]


def resolve(catalog: list[dict], name: str) -> dict | None:
    for s in catalog:
        if isinstance(s, dict) and s.get("name") == name:
            return s
    return None


def render_list_human(entries: list[dict]) -> str:
    lines = [f"── R319 sovereign-os network runtime-stack (E3.M7) ──",
             f"  services: {len(entries)}", ""]
    axes = sorted({s.get("axis", "?") for s in entries if isinstance(s, dict)})
    for axis in axes:
        items = [s for s in entries if s.get("axis") == axis]
        if not items:
            continue
        lines.append(f"  ── {axis} ──")
        for s in items:
            lines.append(f"    {s.get('name'):20s}  unit={s.get('unit')}")
        lines.append("")
    return "\n".join(lines)


def render_status_human(probes: list[dict], verdict: str,
                         rc: int, counts: dict) -> str:
    lines = [f"── R319 network runtime-stack status (E3.M7) ──",
             f"  verdict: {verdict} (rc={rc})",
             f"  healthy: {counts['healthy']}  "
             f"unhealthy: {counts['unhealthy']}  "
             f"unprobed: {counts['unprobed']}",
             ""]
    for p in probes:
        if p.get("healthy") is True:
            mark = "OK"
        elif p.get("healthy") is False:
            mark = "!!"
        else:
            mark = "??"
        lines.append(f"  [{mark}] {p.get('name'):20s} unit={p.get('unit')} "
                      f"installed={p.get('installed')} "
                      f"running={p.get('running')}")
        if p.get("detail"):
            lines.append(f"        {p['detail']}")
    return "\n".join(lines) + "\n"


def render_troubleshoot_human(service: dict) -> str:
    lines = [f"── R319 troubleshoot: {service.get('name')} (E3.M7) ──",
             f"  axis:        {service.get('axis')}",
             f"  unit:        {service.get('unit')}",
             f"  binary:      {service.get('binary')}",
             f"  config_path: {service.get('config_path')}",
             ""]
    lines.append("  diagnostic steps:")
    for step in service.get("troubleshoot", []):
        lines.append(f"    {step}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="runtime-stack-advisor.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--axis")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    pst = sub.add_parser("status")
    pst.add_argument("--config", type=Path)
    fst = pst.add_mutually_exclusive_group()
    fst.add_argument("--json", dest="fmt", action="store_const", const="json")
    fst.add_argument("--human", dest="fmt", action="store_const", const="human")
    pst.set_defaults(fmt="json")

    pt = sub.add_parser("troubleshoot")
    pt.add_argument("service")
    pt.add_argument("--config", type=Path)
    ft = pt.add_mutually_exclusive_group()
    ft.add_argument("--json", dest="fmt", action="store_const", const="json")
    ft.add_argument("--human", dest="fmt", action="store_const", const="human")
    pt.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta = load_catalog(args.config)

    if args.verb == "list":
        entries = filter_axis(catalog, args.axis)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "axis_filter": args.axis,
                "total_count": len(catalog),
                "filtered_count": len(entries),
                "services": entries,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(entries), end="")
        return 0

    if args.verb == "status":
        probes = [probe_service(s) for s in catalog if isinstance(s, dict)]
        verdict, rc, counts = aggregate(probes)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "verdict": verdict,
                "rc": rc,
                "counts": counts,
                "probes": probes,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_status_human(probes, verdict, rc, counts), end="")
        return rc

    if args.verb == "troubleshoot":
        target = resolve(catalog, args.service)
        if target is None:
            print(json.dumps({
                "error": f"unknown service: {args.service}",
                "known": [s.get("name") for s in catalog if isinstance(s, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "service": target,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_troubleshoot_human(target), end="")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
