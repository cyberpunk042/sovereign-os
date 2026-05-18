#!/usr/bin/env python3
"""
scripts/operator/network-edge-api.py — Read-only HTTP API for the
network-edge / OPNsense detection surface (R507, E11.M8++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

This ships the `api` surface of the §1g 8-surface delivery ladder for
the `network-edge` module. The CLI (`sovereign-osctl network-edge
<verb>`) already covers ad-hoc operator queries; this API surface
gives OTHER consumers (the upcoming MCP server, the upcoming webapp
tier-3 shell, automation scripts, monitoring) a stable wire contract.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1)
  - Read-only verbs only (network-edge has no mutation verbs — the
    upstream OPNsense is queried, never modified by this surface;
    actual OPNsense config changes are operator-driven via the
    OPNsense UI / API directly, outside the sovereign-os boundary)

Read-only endpoints (R507 v1, R509 webapp v2):
  GET /version                     — service version + module identity
  GET /detect                      — full network-edge detection bundle
                                     (interfaces + gateway + nat-chain +
                                     vpn + opnsense + capabilities)
  GET /interfaces                  — per-interface state
  GET /nat-chain                   — NAT-layer visibility from
                                     workstation
  GET /opnsense/status             — OPNsense reachability + tier
  GET /opnsense/capabilities       — capability ladder for the
                                     current OPNsense tier
  GET /webapp/                     — R509 single-file monochrome SPA
                                     mirroring the read-only verbs
                                     (operator-§1g: zero external deps)
  GET /healthz                     — API daemon liveness (always 200)

Layer-B metric (sister to the CLI's `_query_total{verb,result}`):

  sovereign_os_operator_network_edge_api_request_total{endpoint,result}

Env vars (all overridable):
  NETWORK_EDGE_API_BIND          (default: 127.0.0.1)
  NETWORK_EDGE_API_PORT          (default: 8093)
  NETWORK_EDGE_WEBAPP_PATH       (default: <repo>/webapp/network-edge/index.html)
  SOVEREIGN_OS_METRICS_DIR       (default: /var/lib/node_exporter/textfile_collector)
  NETWORK_EDGE_API_DRY_RUN       (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("NETWORK_EDGE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("NETWORK_EDGE_API_PORT", "8093"))
DRY_RUN = bool(os.environ.get("NETWORK_EDGE_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_network_edge_api_request_total network-edge
#   read-only REST API request count (endpoint, result).
# TYPE sovereign_os_operator_network_edge_api_request_total counter
METRIC_NAME = "sovereign_os_operator_network_edge_api_request_total"

API_VERSION = "1.1.0-R509"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "network-edge" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "NETWORK_EDGE_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# network-edge CLI module — import directly so the API serves from the
# SAME data model the operator-facing CLI uses (no drift). The CLI
# dispatches `network-edge` to `network-topology.py` (R449 lineage).
_THIS_DIR = Path(__file__).resolve().parent
_NE_PATH = _THIS_DIR / "network-topology.py"
_spec = importlib.util.spec_from_file_location("_ne_core", _NE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load network-topology.py "
        f"from {_NE_PATH}\n"
    )
    sys.exit(1)
_ne = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ne)


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
            METRICS_DIR, "sovereign-os-network-edge-api.prom"
        )
        line = (
            f"{METRIC_NAME}{{endpoint=\"{endpoint}\","
            f"result=\"{result}\"}} 1\n"
        )
        with open(prom_path, "a") as f:
            f.write(line)
    except OSError:
        pass


def _detect_payload() -> dict:
    interfaces = _ne.detect_interfaces()
    return {
        "interfaces_count": len(interfaces),
        "interfaces": interfaces,
        "default_gateway": _ne.detect_default_gateway(),
        "nat_chain": _ne.detect_nat_chain(),
        "vpn_bridge": _ne.detect_vpn_bridge(),
        "opnsense": _ne.detect_opnsense_state(),
        "capabilities": _ne.detect_capabilities(),
        "operator_named_edge_hardware":
            _ne.OPERATOR_NAMED_EDGE_HARDWARE,
    }


def _interfaces_payload() -> dict:
    interfaces = _ne.detect_interfaces()
    return {"count": len(interfaces), "interfaces": interfaces}


def _nat_chain_payload() -> dict:
    return _ne.detect_nat_chain()


def _opnsense_status_payload() -> dict:
    return _ne.detect_opnsense_state()


def _opnsense_capabilities_payload() -> dict:
    return _ne.detect_capabilities()


def _version_payload() -> dict:
    return {
        "module": "network-edge-api",
        "version": API_VERSION,
        "shipped_in": (
            "R507 (E11.M8++ read-only REST API + systemd service) + "
            "R508 (E11.M8++ MCP surface) + "
            "R509 (E11.M8++ webapp surface)"
        ),
        "source": "scripts/operator/network-edge-api.py",
        "data_source": str(_NE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "standing_rule": "We do not minimize anything.",
    }


class NetworkEdgeAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-network-edge-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "network-edge-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        """Serve the R509 single-file SPA from the SAME host:port as
        the JSON endpoints (operator-§1g: same-origin, zero CORS).
        Headers carry the webapp module identity + framing/MIME hardening
        (X-Frame-Options=DENY, X-Content-Type-Options=nosniff)."""
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
        self.send_header("X-Sovereign-Module", "network-edge-webapp")
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
            if path == "/detect":
                self._send_json(200, _detect_payload())
                _emit_metric("detect", "ok")
                return
            if path == "/interfaces":
                self._send_json(200, _interfaces_payload())
                _emit_metric("interfaces", "ok")
                return
            if path == "/nat-chain":
                self._send_json(200, _nat_chain_payload())
                _emit_metric("nat_chain", "ok")
                return
            if path == "/opnsense/status":
                self._send_json(200, _opnsense_status_payload())
                _emit_metric("opnsense_status", "ok")
                return
            if path == "/opnsense/capabilities":
                self._send_json(200, _opnsense_capabilities_payload())
                _emit_metric("opnsense_capabilities", "ok")
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
            "available": ["/version", "/detect", "/interfaces",
                          "/nat-chain", "/opnsense/status",
                          "/opnsense/capabilities", "/webapp/",
                          "/healthz"],
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
            "error": "read-only surface — network-edge has no mutation "
                     "verbs at any surface (operator §17 sovereignty "
                     "boundary). OPNsense config changes are operator-"
                     "driven via the OPNsense UI / API directly, "
                     "outside the sovereign-os boundary.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] network-edge-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_NE_PATH}", flush=True)
    print(f"  endpoints:   /version /detect /interfaces /nat-chain "
          f"/opnsense/status /opnsense/capabilities /webapp/ + /healthz",
          flush=True)
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
        httpd = HTTPServer((bind, port), NetworkEdgeAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] network-edge-api shutdown requested.", flush=True)
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
