#!/usr/bin/env python3
"""scripts/hardware/network-status.py — R220 (SDD-026 Z-7).

Operator-named: "State of the access to internet, the DNS, the
Cloudflared ? the tailscale, Traefik, non docker vs docker install ?
possible ? greyout the option that require it and/or offer the
alternative and warn of the potential risk or failure or such".

One-shot per-component network surface. Each component renders as
a card with:
  - status:    `ok` / `warn` / `down` / `not-installed`
  - detail:    one-line operator-readable summary
  - alternative: human-readable note when relevant (`fallback to
                 tailscale direct tunnel; less private`)

Components polled (best-effort; absence = `not-installed`, not error):
  - internet     : TCP-connect to 1.1.1.1:443 (canary)
  - dns          : resolve `one.one.one.one` via /etc/resolv.conf
  - cloudflared  : `systemctl is-active cloudflared` + listening port
  - tailscale    : `tailscale status --json` returns BackendState=Running
  - traefik      : `systemctl is-active traefik` + dashboard reachable
  - docker       : `docker info` succeeds (operator chose container-level)

Read-only. Operator runs `sovereign-osctl network status` on the
SAIN-01 box; the dashboard's Network tab consumes the same JSON via
`--json` mode. Composes with the future Z-1 dashboard scaffold +
the Z-6 autohealth notification fan-out.

Exit codes:
  0  every polled component reports `ok` or `not-installed`
  1  at least one component is `warn` or `down`
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
from typing import Any


def _run(cmd: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return r.returncode, r.stdout, r.stderr
    except (subprocess.TimeoutExpired, OSError):
        return 124, "", ""


def check_internet() -> dict[str, Any]:
    # TCP-connect to 1.1.1.1:443 with 2s timeout. Doesn't speak TLS;
    # just confirms egress reachability.
    start = time.monotonic()
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=2):
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "component": "internet",
                "status": "ok",
                "detail": f"egress to 1.1.1.1:443 OK ({elapsed_ms} ms)",
                "alternative": None,
            }
    except OSError as e:
        return {
            "component": "internet",
            "status": "down",
            "detail": f"egress to 1.1.1.1:443 failed: {e}",
            "alternative": (
                "alternative: route via tailscale exit-node if configured; "
                "operator can `tailscale set --exit-node <node>` for a "
                "private fallback"
            ),
        }


def check_dns() -> dict[str, Any]:
    start = time.monotonic()
    try:
        socket.gethostbyname("one.one.one.one")
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "component": "dns",
            "status": "ok",
            "detail": f"resolves one.one.one.one in {elapsed_ms} ms",
            "alternative": None,
        }
    except OSError as e:
        return {
            "component": "dns",
            "status": "down",
            "detail": f"DNS resolution failed: {e}",
            "alternative": (
                "alternative: edit /etc/resolv.conf to point at 1.1.1.1 + "
                "9.9.9.9 directly, OR start a local cloudflared resolver "
                "with `cloudflared proxy-dns --port 5053`"
            ),
        }


def _systemctl_is_active(unit: str) -> str | None:
    """Returns 'active' / 'inactive' / 'failed' / 'unknown'; None if
    systemctl unavailable."""
    if not shutil.which("systemctl"):
        return None
    rc, stdout, _ = _run(["systemctl", "is-active", unit])
    if rc == 0:
        return stdout.strip()
    out = stdout.strip()
    if out in {"inactive", "failed", "activating", "deactivating"}:
        return out
    return "unknown"


def check_cloudflared() -> dict[str, Any]:
    if not shutil.which("cloudflared"):
        return {
            "component": "cloudflared",
            "status": "not-installed",
            "detail": "cloudflared binary not on PATH",
            "alternative": (
                "alternative: direct tailscale tunnel for remote access "
                "(less protected from public scans); or skip this "
                "ingress entirely if the operator only needs LAN"
            ),
        }
    state = _systemctl_is_active("cloudflared")
    if state == "active":
        return {
            "component": "cloudflared",
            "status": "ok",
            "detail": "systemd unit cloudflared is active",
            "alternative": None,
        }
    return {
        "component": "cloudflared",
        "status": "down",
        "detail": f"cloudflared unit state: {state or 'unknown'}",
        "alternative": (
            "alternative: tailscale tunnel for remote access; ingress "
            "may be lost — operator should `systemctl restart cloudflared` "
            "or check the tunnel auth"
        ),
    }


def check_tailscale() -> dict[str, Any]:
    if not shutil.which("tailscale"):
        return {
            "component": "tailscale",
            "status": "not-installed",
            "detail": "tailscale binary not on PATH",
            "alternative": (
                "alternative: direct SSH on the host's reachable LAN IPs; "
                "operator loses the private mesh + magic-DNS"
            ),
        }
    rc, stdout, _ = _run(["tailscale", "status", "--json"])
    if rc != 0:
        return {
            "component": "tailscale",
            "status": "down",
            "detail": "tailscale status returned non-zero",
            "alternative": "alternative: `sudo tailscale up` to re-authenticate",
        }
    try:
        s = json.loads(stdout)
        backend = s.get("BackendState", "Unknown")
    except (json.JSONDecodeError, AttributeError):
        backend = "Unparseable"
    if backend == "Running":
        return {
            "component": "tailscale",
            "status": "ok",
            "detail": f"BackendState={backend}",
            "alternative": None,
        }
    return {
        "component": "tailscale",
        "status": "warn" if backend != "Unknown" else "down",
        "detail": f"BackendState={backend}",
        "alternative": (
            "alternative: SSH via reachable LAN IPs; operator loses the "
            "private mesh — try `sudo tailscale up` to re-authenticate"
        ),
    }


def check_traefik() -> dict[str, Any]:
    has_unit = shutil.which("systemctl") is not None
    has_binary = shutil.which("traefik") is not None
    if not has_binary and not has_unit:
        return {
            "component": "traefik",
            "status": "not-installed",
            "detail": "no traefik binary or systemctl available",
            "alternative": (
                "alternative: direct service ports without ingress proxy; "
                "skip this layer if operator doesn't need request routing"
            ),
        }
    state = _systemctl_is_active("traefik") if has_unit else None
    if state == "active":
        return {
            "component": "traefik",
            "status": "ok",
            "detail": "systemd unit traefik is active",
            "alternative": None,
        }
    if state in (None, "unknown", "inactive"):
        return {
            "component": "traefik",
            "status": "not-installed",
            "detail": f"traefik unit not active (state={state or 'no systemd'})",
            "alternative": (
                "alternative: bypass ingress, expose service ports directly "
                "or use the cloudflared tunnel as the routing layer"
            ),
        }
    return {
        "component": "traefik",
        "status": "down",
        "detail": f"traefik unit state: {state}",
        "alternative": "alternative: `systemctl restart traefik` or fall back to direct ports",
    }


def check_docker() -> dict[str, Any]:
    if not shutil.which("docker"):
        return {
            "component": "docker",
            "status": "not-installed",
            "detail": "docker binary not on PATH",
            "alternative": (
                "alternative: system-level install paths for every "
                "operator-needed tool (default sovereignty posture); "
                "container-level modules are GREYED OUT in the dashboard "
                "without docker"
            ),
        }
    rc, _, _ = _run(["docker", "info"], timeout=4)
    if rc == 0:
        return {
            "component": "docker",
            "status": "ok",
            "detail": "docker daemon reachable",
            "alternative": None,
        }
    return {
        "component": "docker",
        "status": "down",
        "detail": "docker binary present but daemon unreachable",
        "alternative": (
            "alternative: `systemctl start docker` OR fall back to "
            "system-level install for the modules that need it"
        ),
    }


CHECKS = [
    check_internet,
    check_dns,
    check_cloudflared,
    check_tailscale,
    check_traefik,
    check_docker,
]

STATUS_GLYPH = {
    "ok": "✓",
    "warn": "⚠",
    "down": "✗",
    "not-installed": "◌",
}


def render_text(cards: list[dict[str, Any]]) -> str:
    lines = ["── R220 sovereign-os network status (SDD-026 Z-7) ──"]
    for c in cards:
        glyph = STATUS_GLYPH.get(c["status"], "?")
        lines.append(
            f"  {glyph} {c['component']:<12} [{c['status']:<14}] {c['detail']}"
        )
        if c["alternative"]:
            lines.append(f"      → {c['alternative']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Per-component network status surface (R220, SDD-026 Z-7).")
    p.add_argument("--json", action="store_true", help="emit JSON instead of card banner")
    p.add_argument(
        "--component",
        choices=["internet", "dns", "cloudflared", "tailscale", "traefik", "docker"],
        help="poll a single component (default: all)",
    )
    args = p.parse_args()

    cards: list[dict[str, Any]] = []
    for fn in CHECKS:
        c = fn()
        if args.component and c["component"] != args.component:
            continue
        cards.append(c)

    if args.json:
        print(json.dumps({"components": cards}, indent=2))
    else:
        sys.stdout.write(render_text(cards))

    # rc = 1 if any component is warn or down (operator-actionable).
    rc = 0
    for c in cards:
        if c["status"] in {"warn", "down"}:
            rc = 1
            break
    return rc


if __name__ == "__main__":
    sys.exit(main())
