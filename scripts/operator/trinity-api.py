#!/usr/bin/env python3
"""
scripts/operator/trinity-api.py — Read-only HTTP API + webapp for the
Genesis Trinity inspection surface (R515, E5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

This closes the trinity webapp:FUTURE waiver — the LAST remaining
waiver for the trinity module. It also takes the nominal master-
spec § 17 lineage `api` + `service` claims and makes them REAL — same
pattern R510 used for global-history when it replaced the prior
service:not-applicable waiver with a real systemd-managed daemon.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1, port 8095)
  - Read-only verbs only — trinity has no mutation verbs at any surface
    (operator §17 sovereignty boundary; the pinned-process state
    fabric is mutated by `trinity profile switch <id>`, NOT by the
    inspection daemon).

Read-only endpoints (R515 v1):
  GET /version                     — service version + module identity
  GET /tiers                       — all 3 tier inspections (status)
  GET /tiers/pulse                 — Pulse tier (Vector Core, CCD0)
  GET /tiers/weaver                — Weaver tier (Sandboxed Fabric)
  GET /tiers/auditor               — Auditor tier (Immutable Gatekeeper)
  GET /webapp/                     — R515 single-file monochrome SPA
                                     mirroring the read-only verbs
                                     (operator-§1g: zero external deps)
  GET /healthz                     — API daemon liveness (always 200)

Layer-B metric (sister to the R513/R514 trinity surfaces):

  sovereign_os_operator_trinity_api_request_total{endpoint,result}

Env vars (all overridable):
  TRINITY_API_BIND               (default: 127.0.0.1)
  TRINITY_API_PORT               (default: 8095)
  TRINITY_WEBAPP_PATH            (default: <repo>/webapp/trinity/index.html)
  SOVEREIGN_OS_METRICS_DIR       (default: /var/lib/node_exporter/textfile_collector)
  TRINITY_API_DRY_RUN            (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("TRINITY_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("TRINITY_API_PORT", "8095"))
DRY_RUN = bool(os.environ.get("TRINITY_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_trinity_api_request_total
#   trinity read-only REST API request count (endpoint, result).
# TYPE sovereign_os_operator_trinity_api_request_total counter
METRIC_NAME = "sovereign_os_operator_trinity_api_request_total"

API_VERSION = "1.0.0-R515"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "trinity" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "TRINITY_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# Import the R514 inspection helper so the API serves from the SAME
# data model the MCP surface uses (no drift).
_INSPECT_PATH = _REPO_ROOT / "scripts" / "trinity" / "trinity-inspect.py"
_spec = importlib.util.spec_from_file_location(
    "_trinity_inspect", _INSPECT_PATH
)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load trinity-inspect.py "
        f"from {_INSPECT_PATH}\n"
    )
    sys.exit(1)
_inspect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_inspect)

# Import the shared, read-only probe of the live sovereign-gatewayd (:8787).
# A browser can't cross-origin fetch :8787 from this same-origin panel, so the
# daemon probes the gateway server-side and serves it at /gateway — the cockpit
# thereby reflects the REAL running brain (routing ledger, sovereignty tripwire,
# persisted memory). Load is best-effort: a missing helper degrades /gateway to
# a structured "unavailable", never a daemon crash.
_GATEWAY_PROBE_PATH = _REPO_ROOT / "scripts" / "operator" / "lib" / "gateway_probe.py"
try:
    _gspec = importlib.util.spec_from_file_location(
        "_gateway_probe", _GATEWAY_PROBE_PATH
    )
    _gateway_probe = importlib.util.module_from_spec(_gspec)  # type: ignore[arg-type]
    _gspec.loader.exec_module(_gateway_probe)  # type: ignore[union-attr]
except (OSError, ImportError, AttributeError):
    _gateway_probe = None


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
            METRICS_DIR, "sovereign-os-trinity-api.prom"
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
        "module": "trinity-api",
        "version": API_VERSION,
        "shipped_in": (
            "R515 (E5++ read-only REST API + webapp + systemd service)"
        ),
        "source": "scripts/operator/trinity-api.py",
        "data_source": str(_INSPECT_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "tiers": ["pulse", "weaver", "auditor"],
        "standing_rule": "We do not minimize anything.",
    }


_TIER_FN = {
    "pulse":   _inspect.pulse_payload,
    "weaver":  _inspect.weaver_payload,
    "auditor": _inspect.auditor_payload,
}


class TrinityAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-trinity-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "trinity-api")
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
        self.send_header("X-Sovereign-Module", "trinity-webapp")
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
            if path == "/tiers":
                self._send_json(200, _inspect.status_payload())
                _emit_metric("tiers", "ok")
                return
            if path == "/gateway":
                # Live read-only probe of sovereign-gatewayd (:8787): the running
                # cortex daemon the Trinity cycle executes on. Never mutates.
                if _gateway_probe is None:
                    self._send_json(200, {
                        "up": False,
                        "error": "gateway_probe helper unavailable",
                    })
                else:
                    self._send_json(200, _gateway_probe.probe_gateway())
                _emit_metric("gateway", "ok")
                return
            if path.startswith("/tiers/"):
                tier = path[len("/tiers/"):]
                fn = _TIER_FN.get(tier)
                if fn is None:
                    self._send_json(404, {
                        "error": f"unknown tier: {tier!r}",
                        "available": sorted(_TIER_FN.keys()),
                    })
                    _emit_metric("tier_unknown", "404")
                    return
                self._send_json(200, fn())
                _emit_metric(f"tier_{tier}", "ok")
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
            "available": ["/version", "/tiers", "/tiers/<name>",
                          "/gateway", "/webapp/", "/healthz"],
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
            "error": "read-only surface — trinity has no mutation verbs "
                     "at any surface (operator §17 sovereignty "
                     "boundary). The pinned-process state fabric (pulse "
                     "/ weaver / auditor) is mutated by `trinity "
                     "profile switch <id>`, never by this surface.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] trinity-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_INSPECT_PATH}", flush=True)
    print(f"  endpoints:   /version /tiers /tiers/<name> /gateway /webapp/ "
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
        httpd = HTTPServer((bind, port), TrinityAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] trinity-api shutdown requested.", flush=True)
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
