#!/usr/bin/env python3
"""scripts/operator/hardware-pressure-api.py — read-only HTTP API + webapp
host for the D-09 hardware-pressure cockpit dashboard (M060 R10102-R10105).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for
the hardware-pressure module. It imports the SAME core the CLI uses
(scripts/hardware/hardware-pressure.py) so the dashboard and `sovereign-osctl
hardware-pressure` never drift.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Per §1g 8-surface contract: "...not just API ... but also Dashboards and Web
Apps and Services".

Sovereignty (stdlib-only, zero deps):
  - http.server + BaseHTTPRequestHandler; loopback-bind by default
  - read-only (no mutation verbs — pressure is observed, not set here)
  - same-origin webapp (no CDN, no cross-origin script per §1g UX rule)

Endpoints (the exact contract webapp/d-09-hardware-pressure/index.html fetches):
  GET /api/hardware/pressure       full snapshot (psi/ccd/gpu/zfs/backpressure)
  GET /api/hardware/zfs/datasets   ZFS datasets + pool latency only
  GET /api/hardware/stream         Server-Sent Events live snapshot stream
  GET /webapp/  | /webapp/index.html   the D-09 single-file dashboard
  GET /version | /healthz | /

Env (all overridable):
  HARDWARE_PRESSURE_API_BIND     (default 127.0.0.1)
  HARDWARE_PRESSURE_API_PORT     (default 8097)
  HARDWARE_PRESSURE_API_DRY_RUN  (set=1 → print config + exit)
  HARDWARE_PRESSURE_WEBAPP_PATH  (override the on-disk webapp asset)
  HARDWARE_PRESSURE_STREAM_INTERVAL (SSE push seconds, default 2.0)
  SOVEREIGN_OS_METRICS_DIR       (node_exporter textfile collector dir)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("HARDWARE_PRESSURE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("HARDWARE_PRESSURE_API_PORT", "8097"))
DRY_RUN = bool(os.environ.get("HARDWARE_PRESSURE_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("HARDWARE_PRESSURE_STREAM_INTERVAL", "2.0"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_hardware_pressure_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "HARDWARE_PRESSURE_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-09-hardware-pressure" / "index.html"),
))

# Import the hardware-pressure core (hyphenated filename → importlib) so the
# API serves the SAME data model as the CLI (no drift).
_CORE_PATH = _REPO_ROOT / "scripts" / "hardware" / "hardware-pressure.py"
_spec = importlib.util.spec_from_file_location("_hwpressure_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load hardware-pressure.py "
        f"from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-hardware-pressure-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "hardware-pressure-api",
        "version": API_VERSION,
        "module": "d-09-hardware-pressure",
        "catalog_source": "M060 R10102-R10105",
        "core": str(_CORE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class HardwarePressureAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-hardware-pressure-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "hardware-pressure-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        try:
            body = WEBAPP_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {"error": f"webapp asset unreadable: {e}",
                                  "expected_path": str(WEBAPP_PATH)})
            _emit_metric("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "d-09-hardware-pressure-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """Server-Sent Events: push a fresh snapshot every STREAM_INTERVAL
        seconds until the client disconnects. Read-only, same-origin."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "hardware-pressure-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                payload = json.dumps(_core.snapshot())
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(STREAM_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return  # client went away — normal SSE lifecycle

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path in ("/", "/healthz"):
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return
        if path in ("/webapp", "/webapp/index.html"):
            self._send_webapp()
            return
        if path == "/api/hardware/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/hardware/pressure":
                self._send_json(200, _core.snapshot())
                _emit_metric("pressure", "ok")
                return
            if path == "/api/hardware/zfs/datasets":
                self._send_json(200, _core.collect_zfs())
                _emit_metric("zfs_datasets", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/hardware/pressure", "/api/hardware/zfs/datasets",
                          "/api/hardware/stream", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — hardware pressure is observed, not set",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] hardware-pressure-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), HardwarePressureAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="hardware-pressure read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one snapshot, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_snapshot": _core.snapshot()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
