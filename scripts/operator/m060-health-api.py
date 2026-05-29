#!/usr/bin/env python3
"""scripts/operator/m060-health-api.py — read-only HTTP API host for the
M060 cross-repo chain-health observability surface.

CROSS-REPO MIRROR — proxies the selfdef daemon's authoritative
`GET /v1/m060/health` endpoint into the sovereign-os webapp layer.
Used by the D-00 master-dashboard's chain-health banner (R10212
read-only).

Endpoints (the exact contract webapp/master-dashboard/index.html fetches):
  GET /api/m060/health     full per-artifact health report
  GET /api/m060/state      bare state string (online/.../unreachable)
  GET /version | /healthz | /

Per the selfdef-side endpoint, state values are:
  - online       all 10 mirrors fresh + parseable
  - degraded     partial population OR any artifact fails JSON-parse
  - stale        newest artifact age > 5 min (loop stuck OR paused)
  - offline      zero artifacts present (daemon not running OR
                 selfdef_mirror_dir unset)
  - unreachable  this script could not reach the selfdef daemon
                 (UNIX socket missing AND TCP fallback unset/failed)

Connection strategy mirrors the other m060 mirror reader scripts:
  1. UNIX socket at $SELFDEF_SOCKET (default /run/selfdef.sock)
  2. TCP at $SELFDEF_API_URL with Bearer $SELFDEF_API_TOKEN

The transport is delegated to scripts/operator/m060-health.py (the
core proxy logic + graceful-unreachable envelope) so this api host
remains a thin HTTP wrapper — same pattern as audit-mirror-api,
quarantine-mirror-api, etc.

Env:
  M060_HEALTH_API_BIND (default 127.0.0.1) ·
  M060_HEALTH_API_PORT (default 8160)      ·
  M060_HEALTH_API_DRY_RUN                  ·
  SELFDEF_SOCKET / SELFDEF_API_URL / SELFDEF_API_TOKEN (selfdef-side)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("M060_HEALTH_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("M060_HEALTH_API_PORT", "8160"))
DRY_RUN = bool(os.environ.get("M060_HEALTH_API_DRY_RUN"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_m060_health_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORE_PATH = _REPO_ROOT / "scripts" / "operator" / "m060-health.py"
_spec = importlib.util.spec_from_file_location("_m060_health_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load m060-health.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-m060-health-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "m060-health-api",
        "version": API_VERSION,
        "module": "m060-health-observability",
        "catalog_source": "selfdef-api::m060_health (GET /v1/m060/health) — 10-mirror chain health probe (M060 cross-repo arc)",
        "core": str(_CORE_PATH),
        "selfdef_endpoint": "/v1/m060/health",
        "mirror_doctrine": "READ-ONLY observability proxy of the selfdef daemon's /v1/m060/health probe; no mutation surfaces",
        "surfaces": ["api", "webapp-banner", "mcp"],
        "states": ["online", "degraded", "stale", "offline", "unreachable"],
        "standing_rule": "We do not minimize anything.",
    }


class M060HealthAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-m060-health-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "m060-health-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        # CORS: the master-dashboard fetches this from the same origin
        # in production, but during local dev (different ports) the
        # banner needs to load. Read-only GETs only — no preflight
        # exposure concern.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path in ("/", "/healthz"):
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/m060/health":
                payload = _core.probe()
                self._send_json(200, payload)
                _emit_metric("health", payload.get("state", "unknown"))
                return
            if path == "/api/m060/state":
                payload = _core.probe()
                self._send_json(200, {"state": payload.get("state", "unreachable")})
                _emit_metric("state", payload.get("state", "unknown"))
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/m060/health", "/api/m060/state",
                          "/version", "/healthz"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only observability MIRROR — chain health is a "
                     "proxy of selfdef /v1/m060/health; no mutation surface (R10212)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] m060-health-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), M060HealthAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="M060 chain-health read-only API")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="probe once, print result, exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_probe": _core.probe()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
