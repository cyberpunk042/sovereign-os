#!/usr/bin/env python3
"""
scripts/operator/router-api.py — Read-only HTTP API + webapp for the
Inference Router inspection surface (R518, E5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

This closes the router webapp:FUTURE waiver — the LAST remaining
waiver for the router module. Raises the router surface count from
7 → 8 shipped surfaces (core / cli / tui / api / service / dashboard
/ mcp / webapp). Third and last commit in the router tier-3 surface-
expansion arc (R516 TUI → R517 MCP → R518 API + webapp).

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1, port 8096 — sister to the
    R515 trinity-api port 8095)
  - Read-only verbs only — router has no mutation verbs at any
    inspection surface. The router's mutation lives at request-
    routing time, not in the inspection daemon; the routing-tier
    selection is driven by the SDD-011 5-rule ladder + the actual
    HTTP request shape sent to the sovereign-router.service at port
    8080. The inspection surface (this daemon) observes router state
    without touching it.

Read-only endpoints (R518 v1):
  GET /version                     — service version + module identity
  GET /status                      — router service + listen + backends
  GET /rules                       — 5 SDD-011 routing rules (first-match)
  GET /metrics                     — Layer B textfile-collector counters
  GET /webapp/                     — R518 single-file monochrome SPA
                                     mirroring the read-only verbs
                                     (operator-§1g: zero external deps)
  GET /healthz                     — API daemon liveness (always 200)

Layer-B metric (sister to the R515 trinity-api surface):

  sovereign_os_operator_router_api_request_total{endpoint,result}

Env vars (all overridable):
  ROUTER_API_BIND                (default: 127.0.0.1)
  ROUTER_API_PORT                (default: 8096)
  ROUTER_WEBAPP_PATH             (default: <repo>/webapp/router/index.html)
  SOVEREIGN_OS_METRICS_DIR       (default: /var/lib/node_exporter/textfile_collector)
  ROUTER_API_DRY_RUN             (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("ROUTER_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("ROUTER_API_PORT", "8096"))
DRY_RUN = bool(os.environ.get("ROUTER_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_router_api_request_total
#   router read-only REST API request count (endpoint, result).
# TYPE sovereign_os_operator_router_api_request_total counter
METRIC_NAME = "sovereign_os_operator_router_api_request_total"

API_VERSION = "1.0.0-R518"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "router" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "ROUTER_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# Import the R517 inspection helper so the API serves from the SAME
# data model the MCP surface uses (no drift).
_INSPECT_PATH = _REPO_ROOT / "scripts" / "inference" / "router-inspect.py"
_spec = importlib.util.spec_from_file_location(
    "_router_inspect", _INSPECT_PATH
)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load router-inspect.py "
        f"from {_INSPECT_PATH}\n"
    )
    sys.exit(1)
_inspect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_inspect)


def _emit_metric(endpoint: str, result: str) -> None:
    """Best-effort textfile-collector emit (Layer B per SDD-016)."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {METRIC_NAME}"
            f"{{endpoint=\"{endpoint}\",result=\"{result}\"}} 1\n"
        )
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom_path = os.path.join(
            METRICS_DIR, "sovereign-os-router-api.prom"
        )
        line = (
            f"{METRIC_NAME}{{endpoint=\"{endpoint}\","
            f"result=\"{result}\"}} 1\n"
        )
        with open(prom_path, "a") as f:
            f.write(line)
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "module": "router-api",
        "version": API_VERSION,
        "shipped_in": (
            "R518 (E5++ read-only REST API + webapp + systemd service)"
        ),
        "source": "scripts/operator/router-api.py",
        "data_source": str(_INSPECT_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "verbs": ["status", "rules", "metrics"],
        "spec_ref": "SDD-011",
        "standing_rule": "We do not minimize anything.",
    }


_VERB_FN = {
    "status":  _inspect.status_payload,
    "rules":   _inspect.rules_payload,
    "metrics": _inspect.metrics_payload,
}


class RouterAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-router-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write(
            f"[api] {self.address_string()} {format % args}\n"
        )

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "router-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        try:
            body = WEBAPP_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {
                "error": f"webapp asset unreadable: {e}",
                "webapp_path": str(WEBAPP_PATH),
            })
            _emit_metric("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "router-webapp")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/healthz" or path == "/":
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return

        if path in ("/webapp", "/webapp/index.html"):
            self._send_webapp()
            return

        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path in ("/status", "/rules", "/metrics"):
                verb = path.lstrip("/")
                self._send_json(200, _VERB_FN[verb]())
                _emit_metric(verb, "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(
                path.lstrip("/").replace("-", "_").replace("/", "_")
                or "unknown",
                "500",
            )
            return

        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/version", "/status", "/rules", "/metrics",
                          "/webapp/", "/healthz"],
        })
        _emit_metric(
            path.lstrip("/").replace("-", "_").replace("/", "_")
            or "unknown",
            "404",
        )

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self):    self._reject_mutation()  # noqa: E704 N802
    def do_PUT(self):     self._reject_mutation()  # noqa: E704 N802
    def do_DELETE(self):  self._reject_mutation()  # noqa: E704 N802
    def do_PATCH(self):   self._reject_mutation()  # noqa: E704 N802

    def _reject_mutation(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — router inspection has no "
                     "mutation verbs at any surface (operator §17 "
                     "sovereignty boundary). The routing-tier selection "
                     "is driven by the SDD-011 5-rule ladder + the "
                     "actual HTTP request shape sent to "
                     "sovereign-router.service at 127.0.0.1:8080, never "
                     "by this inspection surface.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] router-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_INSPECT_PATH}", flush=True)
    print(f"  endpoints:   /version /status /rules /metrics /webapp/ "
          f"+ /healthz", flush=True)
    print(f"  webapp:      {WEBAPP_PATH}", flush=True)
    if bind != "127.0.0.1":
        print(
            f"  WARNING: bind={bind!r} is NOT loopback — operator "
            f"explicitly exposed this surface beyond the host.",
            flush=True,
        )
    if DRY_RUN:
        print("  DRY-RUN: configuration validated, not serving.",
              flush=True)
        return 0

    try:
        httpd = HTTPServer((bind, port), RouterAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] router-api shutdown requested.", flush=True)
        httpd.server_close()
        return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "dry-run":
        global DRY_RUN  # noqa: PLW0603
        DRY_RUN = True
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    return serve()


if __name__ == "__main__":
    sys.exit(main())
