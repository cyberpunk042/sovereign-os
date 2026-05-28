#!/usr/bin/env python3
"""scripts/operator/m060-health.py — READ-ONLY consumer of the selfdef
M060 chain-health endpoint.

CROSS-REPO HEALTH PROBE: queries the selfdef daemon's
`GET /v1/m060/health` and returns the structured health report
covering all 10 mirror artifacts (active-profile + audit +
capability-tokens + cli + grants + quarantine + rules + sandboxes
+ trust-scores + tui). Used by:

- the D-00 master-dashboard's chain-health banner (poll every 30s)
- the MCP tool `selfdef-m060-health` (operator + agent observability)
- the m060-smoke diagnostic + ops scripts

Connection strategy mirrors the other mirror readers:
  1. UNIX socket at $SELFDEF_SOCKET (default /run/selfdef.sock) if present
  2. TCP at $SELFDEF_API_URL with Bearer $SELFDEF_API_TOKEN if set
  3. Otherwise return a graceful "unreachable" report — no crash

State values from the daemon (verbatim per
selfdef-api::m060_health::classify_state):
  - online   = all 10 present + fresh + parseable
  - degraded = some present + some absent OR any parse-fails
  - stale    = newest artifact age > 5 min
  - offline  = zero present (daemon not running OR mirror_dir unset)

Plus this script's own state value when the API is unreachable:
  - unreachable = no socket + no API URL OR HTTP failed

Sovereignty: stdlib-only. Read-only — never mutates anything.

  m060-health.py probe [--json]    full per-artifact report
  m060-health.py state [--json]    bare state string (online/...)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

SOCKET_PATH = os.environ.get("SELFDEF_SOCKET", "/run/selfdef.sock")


def _curl_get(args: list[str], timeout: int = 5) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["curl", "-s", "--fail", "--max-time", str(timeout), *args],
            capture_output=True, text=True, check=False, timeout=timeout + 2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""
    if proc.returncode != 0:
        return False, ""
    return True, proc.stdout


def _probe_via_socket() -> tuple[bool, dict[str, Any] | None]:
    if not os.path.exists(SOCKET_PATH):
        return False, None
    ok, body = _curl_get([
        "--unix-socket", SOCKET_PATH,
        "http://localhost/v1/m060/health",
    ])
    if not ok:
        return False, None
    try:
        return True, json.loads(body)
    except json.JSONDecodeError:
        return False, None


def _probe_via_tcp() -> tuple[bool, dict[str, Any] | None]:
    url = os.environ.get("SELFDEF_API_URL")
    token = os.environ.get("SELFDEF_API_TOKEN")
    if not url or not token:
        return False, None
    ok, body = _curl_get([
        "-H", f"Authorization: Bearer {token}",
        f"{url.rstrip('/')}/v1/m060/health",
    ])
    if not ok:
        return False, None
    try:
        return True, json.loads(body)
    except json.JSONDecodeError:
        return False, None


def probe() -> dict[str, Any]:
    """Return the full health report, with a graceful unreachable
    envelope when neither transport works."""
    for fn in (_probe_via_socket, _probe_via_tcp):
        ok, payload = fn()
        if ok and isinstance(payload, dict):
            payload.setdefault("mirror_status", "online")
            payload.setdefault("source", "selfdef /v1/m060/health")
            return payload
    return {
        "schema_version": "1.0.0",
        "mirror_status": "unreachable",
        "source": "selfdef /v1/m060/health",
        "state": "unreachable",
        "mirror_dir": "",
        "artifacts_present": 0,
        "artifacts_expected": 10,
        "newest_age_seconds": None,
        "artifacts": [],
        "_hint": (
            "selfdefd not reachable: no UNIX socket at "
            f"{SOCKET_PATH} and SELFDEF_API_URL+SELFDEF_API_TOKEN not "
            "set. Start selfdefd or export the TCP transport env vars."
        ),
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef M060 chain-health probe")
    sub = p.add_subparsers(dest="cmd")
    for name in ("probe", "state"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "probe"
    payload = probe()
    if cmd == "state":
        _print({"state": payload.get("state", "unreachable")})
    else:
        _print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
