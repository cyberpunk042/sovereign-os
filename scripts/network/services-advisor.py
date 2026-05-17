#!/usr/bin/env python3
"""scripts/network/services-advisor.py — R263 (SDD-026 Z-7 expansion).

Operator-named (verbatim, 2026-05-17 expansion): "the Cloudflared ?
the tailscale, Traefik [...] container level vs system level".

R220 ships generic network-status (probes 8 components including
cloudflared/tailscale/traefik). R237 ships install-paths matrix.
R263 closes the operator-specific advisory layer: per-network-service
deep probe + posture verdict + actionable hints.

Probes (read-only):
  cloudflared      systemctl status + `cloudflared tunnel info` +
                   /etc/cloudflared/ existence
  tailscale        `tailscale status` + tailscaled service +
                   /var/lib/tailscale/ existence
  traefik          systemctl status + config under /etc/traefik/
                   OR docker container detection

Each probe returns:
  installed     binary present
  service_state systemctl is-active (when applicable)
  configured    config files exist OR daemon reports healthy state
  posture       ok / attention / not-installed / degraded
  advisory      actionable hint when posture != ok

CLI:
  services-advisor.py cloudflared [--json]
  services-advisor.py tailscale [--json]
  services-advisor.py traefik [--json]
  services-advisor.py show [--json]            all three

Exit codes:
  0  rendered
  1  ≥1 advisory at attention/degraded severity
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


def systemctl_is_active(unit: str) -> str:
    """Returns: active / inactive / failed / unavailable."""
    if not shutil.which("systemctl"):
        return "unavailable"
    try:
        r = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return "unavailable"
    state = (r.stdout or r.stderr or "").strip()
    return state if state else "unknown"


def probe_cloudflared() -> dict[str, Any]:
    binary = shutil.which("cloudflared")
    config_dir = Path("/etc/cloudflared")
    config_present = config_dir.is_dir()
    service_state = systemctl_is_active("cloudflared.service") if binary else "n/a"

    # Tunnel info — best-effort, may need credentials.
    tunnels_count = None
    if binary:
        try:
            r = subprocess.run(
                ["cloudflared", "tunnel", "list", "--output", "json"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if r.returncode == 0 and r.stdout.strip():
                try:
                    tunnels_count = len(json.loads(r.stdout))
                except json.JSONDecodeError:
                    pass
        except (subprocess.TimeoutExpired, OSError):
            pass

    if binary is None:
        posture = "not-installed"
        advisory = (
            "cloudflared not installed. Operator-pull: `curl -L "
            "https://github.com/cloudflare/cloudflared/releases/latest/download/"
            "cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x "
            "/usr/local/bin/cloudflared` then `cloudflared tunnel login`."
        )
    elif not config_present:
        posture = "attention"
        advisory = (
            f"cloudflared installed but /etc/cloudflared/ missing. Run "
            f"`cloudflared tunnel login` + create a tunnel config to bring this "
            f"to ok."
        )
    elif service_state == "active":
        posture = "ok"
        advisory = None
    elif service_state == "inactive":
        posture = "attention"
        advisory = (
            "cloudflared installed + configured but service inactive. "
            "`sudo systemctl enable --now cloudflared.service`"
        )
    elif service_state == "failed":
        posture = "degraded"
        advisory = (
            "cloudflared service is in 'failed' state. "
            "`systemctl status cloudflared.service` for diagnostic."
        )
    else:
        posture = "attention"
        advisory = f"cloudflared service state = {service_state!r}"

    return {
        "service": "cloudflared",
        "installed": binary is not None,
        "binary_path": binary,
        "configured": config_present,
        "service_state": service_state,
        "tunnels_count": tunnels_count,
        "posture": posture,
        "advisory": advisory,
    }


def probe_tailscale() -> dict[str, Any]:
    binary = shutil.which("tailscale")
    state_dir = Path("/var/lib/tailscale")
    state_present = state_dir.is_dir()
    service_state = systemctl_is_active("tailscaled.service") if binary else "n/a"

    backend_state = None
    auth_state = None
    peers_count = None
    if binary:
        try:
            r = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if r.returncode == 0 and r.stdout.strip():
                try:
                    js = json.loads(r.stdout)
                    backend_state = js.get("BackendState")
                    auth_state = js.get("AuthURL") or "authenticated"
                    peers_count = len(js.get("Peer") or {})
                except json.JSONDecodeError:
                    pass
        except (subprocess.TimeoutExpired, OSError):
            pass

    if binary is None:
        posture = "not-installed"
        advisory = (
            "tailscale not installed. Operator-pull: `curl -fsSL "
            "https://tailscale.com/install.sh | sh` then `sudo tailscale up`."
        )
    elif service_state == "active" and backend_state == "Running":
        posture = "ok"
        advisory = None
    elif service_state == "active" and backend_state in {"NeedsLogin", "Stopped"}:
        posture = "attention"
        advisory = (
            f"tailscale daemon running but backend={backend_state!r}. "
            "`sudo tailscale up` to authenticate."
        )
    elif service_state == "inactive":
        posture = "attention"
        advisory = "tailscale installed but tailscaled.service inactive. `sudo systemctl enable --now tailscaled.service`"
    elif service_state == "failed":
        posture = "degraded"
        advisory = "tailscaled.service is in 'failed' state. `systemctl status tailscaled.service`"
    elif not state_present:
        posture = "attention"
        advisory = "tailscale installed but /var/lib/tailscale missing. First-run setup pending."
    else:
        posture = "attention"
        advisory = f"tailscale service state = {service_state!r}, backend={backend_state!r}"

    return {
        "service": "tailscale",
        "installed": binary is not None,
        "binary_path": binary,
        "configured": state_present,
        "service_state": service_state,
        "backend_state": backend_state,
        "peers_count": peers_count,
        "posture": posture,
        "advisory": advisory,
    }


def probe_traefik() -> dict[str, Any]:
    binary = shutil.which("traefik")
    config_dir = Path("/etc/traefik")
    config_present = config_dir.is_dir()
    service_state = systemctl_is_active("traefik.service") if binary else "n/a"

    # Docker-container Traefik is operator-named; detect that path.
    docker_traefik = False
    if shutil.which("docker"):
        try:
            r = subprocess.run(
                ["docker", "ps", "--filter", "ancestor=traefik", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if r.returncode == 0:
                docker_traefik = bool(r.stdout.strip())
        except (subprocess.TimeoutExpired, OSError):
            pass

    if binary is None and not docker_traefik:
        posture = "not-installed"
        advisory = (
            "traefik not installed (system OR docker). Two operator-pull paths: "
            "system → `apt install traefik`; docker → `docker run -d "
            "-p 80:80 -v $PWD/traefik.yml:/etc/traefik/traefik.yml traefik`. "
            "Per SDD-026 Z-8: container-vs-system install matrix flags which "
            "path is greyed-out based on R220 network-status."
        )
    elif docker_traefik and not binary:
        posture = "ok"
        advisory = (
            "traefik running as docker container — system-level "
            "/etc/traefik/ inert. Operator-pull: `docker logs <name>` for "
            "diagnostics."
        )
    elif binary and not config_present:
        posture = "attention"
        advisory = (
            "traefik installed at system level but /etc/traefik/ missing. "
            "Drop a traefik.yml + dynamic config in /etc/traefik/ to bring "
            "this to ok."
        )
    elif binary and service_state == "active":
        posture = "ok"
        advisory = None
    elif binary and service_state == "inactive":
        posture = "attention"
        advisory = "traefik.service inactive. `sudo systemctl enable --now traefik.service`"
    elif binary and service_state == "failed":
        posture = "degraded"
        advisory = "traefik.service is in 'failed' state. `systemctl status traefik.service`"
    else:
        posture = "attention"
        advisory = f"traefik posture unclear: binary={bool(binary)} docker={docker_traefik} state={service_state!r}"

    return {
        "service": "traefik",
        "installed": binary is not None,
        "binary_path": binary,
        "docker_container_present": docker_traefik,
        "configured": config_present,
        "service_state": service_state,
        "posture": posture,
        "advisory": advisory,
    }


PROBES = {
    "cloudflared": probe_cloudflared,
    "tailscale": probe_tailscale,
    "traefik": probe_traefik,
}


def _render_one(d: dict[str, Any]) -> None:
    glyph = {
        "ok": "✓",
        "attention": "⚠",
        "degraded": "⛔",
        "not-installed": "·",
    }.get(d.get("posture"), "?")
    print(f"  {glyph} {d['service']:<14} posture={d['posture']:<14} installed={d.get('installed')}")
    if d.get("service_state") and d["service_state"] != "n/a":
        print(f"        service_state={d['service_state']}")
    if d.get("advisory"):
        print(f"        advisory: {d['advisory']}")


def cmd_one(name: str, args: argparse.Namespace) -> int:
    fn = PROBES[name]
    out = fn()
    out_full = {
        "round": "R263",
        "vector": "SDD-026 Z-7 expansion (services-advisor)",
        **out,
    }
    if args.json:
        print(json.dumps(out_full, indent=2))
    else:
        print(f"── R263 sovereign-os services-advisor {name} ──")
        _render_one(out)
    return 1 if out.get("posture") in {"attention", "degraded"} else 0


def cmd_show(args: argparse.Namespace) -> int:
    results = {n: fn() for n, fn in PROBES.items()}
    out = {
        "round": "R263",
        "vector": "SDD-026 Z-7 expansion (services-advisor)",
        "results": results,
        "summary": {
            "ok": sum(1 for r in results.values() if r["posture"] == "ok"),
            "attention": sum(1 for r in results.values() if r["posture"] == "attention"),
            "degraded": sum(1 for r in results.values() if r["posture"] == "degraded"),
            "not_installed": sum(1 for r in results.values() if r["posture"] == "not-installed"),
        },
    }
    any_action = any(r["posture"] in {"attention", "degraded"} for r in results.values())
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"── R263 sovereign-os services-advisor show ──")
        print(f"  summary: {out['summary']}")
        print()
        for n in PROBES:
            _render_one(results[n])
    return 1 if any_action else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="services-advisor.py",
        description="R263 (SDD-026 Z-7) — cloudflared / tailscale / traefik posture advisor.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    for name in PROBES:
        sp = sub.add_parser(name, help=f"posture for {name}")
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=lambda a, n=name: cmd_one(n, a))
    ps = sub.add_parser("show", help="all three services in one snapshot")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_show)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
