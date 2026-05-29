#!/usr/bin/env python3
"""scripts/operator/ms022-sse-quota-api.py — read-only HTTP API host for
the MS022 SSE subscriber-quota observability surface.

CROSS-REPO MIRROR — parses the selfdef daemon's Prometheus `/metrics`
exposition (`selfdef_sse_subscribers_*` gauges shipped at selfdef
commit `77b4499`) and emits a compact JSON envelope the
master-dashboard's MS022 banner consumes. Project boundary R10212:
pure observability proxy; no mutation surface.

Endpoints (the exact contract webapp/master-dashboard/index.html fetches):
  GET /api/ms022/sse-quota     full quota state envelope
  GET /api/ms022/state         bare state string (ok/approaching/saturated/unreachable)
  GET /version | /healthz | /

State derivation (matches the 3 sovereign-os alert rules):
  - ok           saturation <= 0.85 AND per_token_saturated == 0
  - approaching  saturation > 0.85 OR per_token_saturated > 0
  - saturated    saturation >= 1.0
  - unreachable  this script could not reach selfdefd's /metrics

Connection strategy mirrors m060-health-api.py: UNIX socket at
$SELFDEF_SOCKET (default /run/selfdef.sock); TCP at
$SELFDEF_API_URL with Bearer $SELFDEF_API_TOKEN.

Sovereignty: stdlib-only. Absent metric → unreachable envelope
(graceful), never a crash.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

API_VERSION = "1.0.0"
API_BIND = os.environ.get("MS022_SSE_QUOTA_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("MS022_SSE_QUOTA_API_PORT", "7711"))
DRY_RUN = bool(os.environ.get("MS022_SSE_QUOTA_API_DRY_RUN"))

SELFDEF_SOCKET = os.environ.get("SELFDEF_SOCKET", "/run/selfdef.sock")
SELFDEF_API_URL = os.environ.get("SELFDEF_API_URL")
SELFDEF_API_TOKEN = os.environ.get("SELFDEF_API_TOKEN")

# Thresholds matching the sovereign-os alert rules:
#   MS022SseGlobalQuotaApproaching > 0.85
#   MS022SseGlobalQuotaSaturated   >= 1.0
APPROACHING_THRESHOLD = 0.85
SATURATED_THRESHOLD = 1.0


def _fetch_metrics_text() -> str | None:
    """Fetch selfdefd's /metrics body. Returns None on unreachable."""
    if os.path.exists(SELFDEF_SOCKET):
        try:
            r = subprocess.run(
                ["curl", "-s", "--unix-socket", SELFDEF_SOCKET,
                 "http://localhost/metrics"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if r.returncode == 0 and r.stdout:
                return r.stdout
        except (subprocess.TimeoutExpired, OSError):
            pass
    if SELFDEF_API_URL and SELFDEF_API_TOKEN:
        try:
            r = subprocess.run(
                ["curl", "-s", "-H", f"Authorization: Bearer {SELFDEF_API_TOKEN}",
                 f"{SELFDEF_API_URL.rstrip('/')}/metrics"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if r.returncode == 0 and r.stdout:
                return r.stdout
        except (subprocess.TimeoutExpired, OSError):
            pass
    return None


_METRIC_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\{([^}]*)\})?\s+([0-9.eE+\-]+)$")


def _parse_metrics(body: str) -> dict[str, Any]:
    """Extract the 6 sse_quota gauges from a Prometheus exposition body.

    Returns a dict with the canonical keys the banner consumes. Missing
    metrics fall back to None so the banner can render "unknown" rather
    than a fake zero."""
    out: dict[str, Any] = {
        "global_active": None,
        "global_cap": None,
        "global_saturation": None,
        "per_token_cap": None,
        "per_token_saturated": None,
        "per_token_counts": [],  # [{token_fp, subscribers}, ...]
    }
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _METRIC_RE.match(line)
        if not m:
            continue
        name, labels, value_str = m.group(1), m.group(2) or "", m.group(3)
        try:
            value = float(value_str)
        except ValueError:
            continue
        if name == "selfdef_sse_subscribers_global_active":
            out["global_active"] = int(value)
        elif name == "selfdef_sse_subscribers_global_cap":
            out["global_cap"] = int(value)
        elif name == "selfdef_sse_subscribers_global_saturation":
            out["global_saturation"] = value
        elif name == "selfdef_sse_subscribers_per_token_cap":
            out["per_token_cap"] = int(value)
        elif name == "selfdef_sse_subscribers_per_token_saturated":
            out["per_token_saturated"] = int(value)
        elif name == "selfdef_sse_subscribers_per_token":
            # token_fp="abcdef12"
            fp_match = re.search(r'token_fp="([^"]+)"', labels)
            if fp_match:
                out["per_token_counts"].append({
                    "token_fp": fp_match.group(1),
                    "subscribers": int(value),
                })
    # Sort per-token by descending count for stable banner / topN.
    out["per_token_counts"].sort(key=lambda r: (-r["subscribers"], r["token_fp"]))
    return out


def _classify_state(parsed: dict[str, Any]) -> str:
    """Derive the banner state matching the alert thresholds."""
    sat = parsed.get("global_saturation")
    per_token_saturated = parsed.get("per_token_saturated") or 0
    if sat is None:
        return "unreachable"
    if sat >= SATURATED_THRESHOLD:
        return "saturated"
    if sat > APPROACHING_THRESHOLD or per_token_saturated > 0:
        return "approaching"
    return "ok"


def probe() -> dict[str, Any]:
    """One-shot probe — fetch + parse + classify. Used by the GET
    handlers + by --self-check."""
    body = _fetch_metrics_text()
    if body is None:
        return {
            "state": "unreachable",
            "detail": "selfdefd /metrics unreachable (UNIX socket missing AND TCP fallback unset/failed)",
            "metrics": None,
        }
    parsed = _parse_metrics(body)
    return {
        "state": _classify_state(parsed),
        "detail": None,
        "metrics": parsed,
        "thresholds": {
            "approaching": APPROACHING_THRESHOLD,
            "saturated": SATURATED_THRESHOLD,
        },
    }


def _version_payload() -> dict[str, Any]:
    return {
        "version": API_VERSION,
        "selfdef_metric_prefix": "selfdef_sse_subscribers_",
        "mirror_doctrine": "READ-ONLY observability proxy of selfdef /metrics SSE quota gauges; no mutation surfaces",
        "surfaces": ["api", "webapp-banner"],
        "states": ["ok", "approaching", "saturated", "unreachable"],
        "thresholds": {
            "approaching": APPROACHING_THRESHOLD,
            "saturated": SATURATED_THRESHOLD,
        },
        "standing_rule": "We do not minimize anything.",
    }


class MS022SseQuotaAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-ms022-sse-quota-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "ms022-sse-quota-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path in ("/", "/healthz"):
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                return
            if path == "/api/ms022/sse-quota":
                self._send_json(200, probe())
                return
            if path == "/api/ms022/state":
                self._send_json(200, {"state": probe()["state"]})
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/ms022/sse-quota", "/api/ms022/state",
                          "/version", "/healthz"],
        })

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only observability MIRROR — SSE quota state is a "
                     "proxy of selfdef /metrics gauges; no mutation surface (R10212)",
            "allowed": ["GET", "HEAD"],
        })

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] ms022-sse-quota-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), MS022SseQuotaAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MS022 SSE quota read-only API")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="probe once, print result, exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_probe": probe()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
