#!/usr/bin/env python3
"""scripts/diagnostics/ms022-doctor.py — MS022 SSE quota chain triage.

Single-command operator triage across the 4 consumer-side MS022
surfaces (proxy daemon, master-dashboard banner, Grafana dashboard,
Prometheus alert rules) AND the selfdef-side producer (the 6
`selfdef_sse_subscribers_*` gauges shipped at selfdef commit 77b4499).

Probes in order:

  1. proxy-daemon   /healthz on sovereign-ms022-sse-quota-api
                    (loopback :7711 by default)
  2. proxy-state    /api/ms022/state — verifies the proxy can
                    classify the producer (proves the parser
                    + threshold lockstep are both working)
  3. proxy-envelope /api/ms022/sse-quota — full envelope, used
                    by the master-dashboard banner. We check the
                    JSON shape matches what the banner expects.
  4. systemd-unit   sovereign-ms022-sse-quota-api.service —
                    systemctl is-active + show ExecMainStatus
                    so the operator sees if systemd considers it
                    healthy.
  5. master-banner  GET /api/ms022/sse-quota proxied through
                    the master-dashboard origin (when reachable)

Three-tier severity matching the cli-mirror/m060 doctor conventions:

  0  GREEN  every check passes
  1  YELLOW at least one operator-actionable degradation
  2  RED    structural break (proxy not running, etc.)

Read-only across the chain (R10212 + R10115). Stdlib-only Python; no
deps.

  ms022-doctor [--json]     full triage table OR JSON
  ms022-doctor [--strict]   require state=ok (else exit 1)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

PROXY_URL = os.environ.get(
    "SOVEREIGN_OS_MS022_PROXY_URL",
    "http://127.0.0.1:7711",
)
MASTER_DASHBOARD_URL = os.environ.get(
    "SOVEREIGN_OS_BASE_URL",
    "http://localhost",
)
PROXY_UNIT = "sovereign-ms022-sse-quota-api.service"

# Severity ordering — Pass < Warn < Fail.
SEV_PASS, SEV_WARN, SEV_FAIL = 0, 1, 2
SEV_LABEL = {SEV_PASS: "OK   ", SEV_WARN: "WARN ", SEV_FAIL: "FAIL "}
SEV_JSON = {SEV_PASS: "pass", SEV_WARN: "warn", SEV_FAIL: "fail"}


def _fetch_json(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            ConnectionError, OSError, json.JSONDecodeError):
        return None


def check_proxy_daemon_health() -> dict[str, Any]:
    """Hit /healthz — proves the proxy daemon is at least answering."""
    body = _fetch_json(f"{PROXY_URL}/healthz")
    if body is None:
        return {
            "name": "proxy-daemon",
            "severity": SEV_FAIL,
            "detail": (
                f"{PROXY_URL}/healthz unreachable — proxy daemon down "
                f"or bound to a different host:port"
            ),
            "fix": (
                "systemctl status sovereign-ms022-sse-quota-api.service "
                "(install via sovereign-osctl install if absent)"
            ),
        }
    return {
        "name": "proxy-daemon",
        "severity": SEV_PASS,
        "detail": f"{PROXY_URL}/healthz returns {body.get('status', '?')}",
        "fix": "",
    }


def check_proxy_state() -> dict[str, Any]:
    """Hit /api/ms022/state — proves the parser + classifier round-trip
    works AND tells us the upstream SSE quota state in one call."""
    body = _fetch_json(f"{PROXY_URL}/api/ms022/state")
    if body is None:
        return {
            "name": "proxy-state",
            "severity": SEV_FAIL,
            "detail": "/api/ms022/state did not return parseable JSON",
            "fix": (
                "journalctl -u sovereign-ms022-sse-quota-api.service -n 50"
            ),
        }
    state = body.get("state", "unknown")
    if state == "unreachable":
        return {
            "name": "proxy-state",
            "severity": SEV_WARN,
            "detail": (
                "proxy reports state=unreachable — selfdefd /metrics not "
                "served (UNIX socket missing AND TCP fallback unset/failed)"
            ),
            "fix": "verify selfdefd is up on the IPS host; check SELFDEF_SOCKET path",
        }
    if state == "saturated":
        return {
            "name": "proxy-state",
            "severity": SEV_FAIL,
            "detail": "SSE quota SATURATED — clients getting HTTP 429",
            "fix": (
                "ssh <selfdef-host> sudo systemctl restart selfdefd "
                "(clears leaked subscribers); see Grafana for per-token table"
            ),
        }
    if state == "approaching":
        return {
            "name": "proxy-state",
            "severity": SEV_WARN,
            "detail": "SSE quota approaching saturation (>0.85 OR ≥1 token saturated)",
            "fix": (
                "drill into Grafana /d/sovereign-os-ms022-sse-quota; "
                "rotate heaviest token OR raise [api].max_sse_subscribers"
            ),
        }
    if state == "ok":
        return {
            "name": "proxy-state",
            "severity": SEV_PASS,
            "detail": "SSE quota ok",
            "fix": "",
        }
    return {
        "name": "proxy-state",
        "severity": SEV_WARN,
        "detail": f"proxy reports state={state!r}",
        "fix": "",
    }


def check_proxy_envelope_shape() -> dict[str, Any]:
    """Hit /api/ms022/sse-quota and verify the JSON shape matches what
    the master-dashboard banner consumes. Drift here = banner breaks."""
    body = _fetch_json(f"{PROXY_URL}/api/ms022/sse-quota")
    if body is None:
        return {
            "name": "proxy-envelope",
            "severity": SEV_FAIL,
            "detail": "/api/ms022/sse-quota did not return parseable JSON",
            "fix": "see proxy-daemon check",
        }
    required = {"state", "metrics", "thresholds"}
    missing = required - set(body)
    if missing:
        return {
            "name": "proxy-envelope",
            "severity": SEV_FAIL,
            "detail": (
                f"envelope missing required keys: {sorted(missing)!r} — "
                f"master-dashboard banner would render incorrectly"
            ),
            "fix": "verify scripts/operator/ms022-sse-quota-api.py is current",
        }
    return {
        "name": "proxy-envelope",
        "severity": SEV_PASS,
        "detail": "envelope shape matches master-dashboard banner contract",
        "fix": "",
    }


def check_systemd_unit() -> dict[str, Any]:
    """`systemctl show` on the proxy unit. Same shape as the cli-mirror
    doctor's systemd check — bus-unreachable → WARN."""
    probe = subprocess.run(
        ["systemctl", "show", PROXY_UNIT,
         "--property=ActiveState,Result,LoadState"],
        capture_output=True, text=True, check=False,
    )
    stderr = probe.stderr or ""
    if probe.returncode != 0 and "could not be found" not in stderr:
        return {
            "name": "systemd-unit",
            "severity": SEV_WARN,
            "detail": f"systemctl show returned {probe.returncode}",
            "fix": "verify systemd is the init system",
        }
    if ("System has not been booted with systemd" in stderr
            or "Failed to connect to bus" in stderr
            or not probe.stdout.strip()):
        return {
            "name": "systemd-unit",
            "severity": SEV_WARN,
            "detail": (
                "systemctl present but systemd bus unreachable "
                "(container / non-systemd host)"
            ),
            "fix": "non-actionable in this environment",
        }
    load_state = active_state = result = "unknown"
    for line in probe.stdout.splitlines():
        if line.startswith("LoadState="):    load_state = line.split("=", 1)[1]
        if line.startswith("ActiveState="):  active_state = line.split("=", 1)[1]
        if line.startswith("Result="):       result = line.split("=", 1)[1]
    if load_state == "not-found":
        return {
            "name": "systemd-unit",
            "severity": SEV_WARN,
            "detail": f"{PROXY_UNIT} not installed",
            "fix": "install via the sovereign-os deb / copy to /lib/systemd/system",
        }
    if active_state == "active" and result == "success":
        return {
            "name": "systemd-unit",
            "severity": SEV_PASS,
            "detail": f"{PROXY_UNIT} active",
            "fix": "",
        }
    if active_state == "failed" or result != "success":
        return {
            "name": "systemd-unit",
            "severity": SEV_FAIL,
            "detail": (
                f"{PROXY_UNIT} state={load_state}/{active_state}/{result}"
            ),
            "fix": f"journalctl -u {PROXY_UNIT} -n 50",
        }
    return {
        "name": "systemd-unit",
        "severity": SEV_WARN,
        "detail": f"{PROXY_UNIT} state={active_state} (not active)",
        "fix": f"systemctl start {PROXY_UNIT}",
    }


def check_master_banner_proxied() -> dict[str, Any]:
    """Hit the master-dashboard origin's /api/ms022/sse-quota — that's
    the URL the banner actually fetches. When the master-dashboard +
    proxy share an origin (default), this is redundant with
    check_proxy_envelope_shape; when they don't, this catches a
    proxy-config gap."""
    url = f"{MASTER_DASHBOARD_URL.rstrip('/')}/api/ms022/sse-quota"
    body = _fetch_json(url)
    if body is None:
        return {
            "name": "master-banner",
            "severity": SEV_WARN,
            "detail": (
                f"{url} unreachable — banner would stay state=unknown"
            ),
            "fix": (
                "configure the master-dashboard's reverse proxy to forward "
                "/api/ms022/* to the proxy daemon (default :7711)"
            ),
        }
    if body.get("state") not in ("ok", "approaching", "saturated", "unreachable"):
        return {
            "name": "master-banner",
            "severity": SEV_WARN,
            "detail": (
                f"banner endpoint returns state={body.get('state')!r} "
                f"(expected one of ok/approaching/saturated/unreachable)"
            ),
            "fix": "verify the proxy daemon version + the classifier contract",
        }
    return {
        "name": "master-banner",
        "severity": SEV_PASS,
        "detail": f"banner endpoint returns state={body.get('state')!r}",
        "fix": "",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--strict", action="store_true",
        help="require state=ok across every check (else exit 1)",
    )
    args = p.parse_args(argv)

    checks = [
        check_proxy_daemon_health(),
        check_proxy_state(),
        check_proxy_envelope_shape(),
        check_systemd_unit(),
        check_master_banner_proxied(),
    ]
    worst = max(c["severity"] for c in checks)

    if args.json:
        print(json.dumps({
            "domain": "MS022",
            "worst_severity": SEV_JSON[worst],
            "checks": [{
                "name": c["name"],
                "severity": SEV_JSON[c["severity"]],
                "detail": c["detail"],
                "fix": c["fix"],
            } for c in checks],
        }, indent=2))
    else:
        print("MS022 SSE quota chain triage")
        print("============================")
        for c in checks:
            print(f"{SEV_LABEL[c['severity']]} {c['name']:<16} {c['detail']}")
            if c["fix"]:
                print(f"      └─ fix: {c['fix']}")
        print()
        if worst == SEV_PASS:
            print("verdict: GREEN — chain healthy")
        elif worst == SEV_WARN:
            print("verdict: YELLOW — at least one operator-actionable degradation")
        else:
            print("verdict: RED — structural break; see fix lines above")

    if args.strict and worst != SEV_PASS:
        return 1
    return {SEV_PASS: 0, SEV_WARN: 1, SEV_FAIL: 2}[worst]


if __name__ == "__main__":
    sys.exit(main())
