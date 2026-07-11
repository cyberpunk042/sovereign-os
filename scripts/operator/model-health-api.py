#!/usr/bin/env python3
"""scripts/operator/model-health-api.py — read-only HTTP API + webapp host
for the D-03 model-health cockpit dashboard (M060 R10069-R10074).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for
the model-health module. It imports the SAME core the CLI uses
(scripts/inference/model-health.py) so the dashboard and `sovereign-osctl
model-health` never drift.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Per §1g 8-surface contract: "...not just API ... but also Dashboards and Web
Apps and Services".

Sovereignty (stdlib-only, zero deps):
  - http.server + BaseHTTPRequestHandler; loopback-bind by default
  - read-only (load/unload are MS003-signed CLI verbs, never web mutations)
  - same-origin webapp (no CDN, no cross-origin script per §1g UX rule)

Endpoints (the exact contract webapp/d-03-model-health/index.html fetches):
  GET /api/models/health     full snapshot (summary/roles/gpus/latency/kvcache)
  GET /api/models/catalog    catalog rows grouped by SRP role
  GET /api/models/gpus       live nvidia-smi GPU table only
  GET /api/models/stream     Server-Sent Events (model-state-change events)
  GET /webapp/ | /webapp/index.html   the D-03 single-file dashboard
  GET /version | /healthz | /

Env (all overridable):
  MODEL_HEALTH_API_BIND      (default 127.0.0.1)
  MODEL_HEALTH_API_PORT      (default 8104)
  MODEL_HEALTH_API_DRY_RUN   (set=1 → print config + exit)
  MODEL_HEALTH_WEBAPP_PATH   (override the on-disk webapp asset)
  MODEL_HEALTH_STREAM_INTERVAL (SSE push seconds, default 3.0)
  SOVEREIGN_OS_METRICS_DIR   (node_exporter textfile collector dir)
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

API_BIND = os.environ.get("MODEL_HEALTH_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("MODEL_HEALTH_API_PORT", "8104"))
DRY_RUN = bool(os.environ.get("MODEL_HEALTH_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("MODEL_HEALTH_STREAM_INTERVAL", "3.0"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_model_health_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "MODEL_HEALTH_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-03-model-health" / "index.html"),
))

# Import the model-health core (hyphenated filename → importlib) so the API
# serves the SAME data model as the CLI (no drift).
_CORE_PATH = _REPO_ROOT / "scripts" / "inference" / "model-health.py"
_spec = importlib.util.spec_from_file_location("_modelhealth_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load model-health.py "
        f"from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

# Shared read-only probe of the live sovereign-gatewayd (:8787) — surfaced here
# so the model-health cockpit shows the running brain's sovereignty tripwire +
# routing ledger + persisted memory alongside the tier backends. Server-side
# (a browser can't cross-origin fetch :8787); best-effort load so a missing
# helper degrades /api/models/gateway to "unavailable", never a daemon crash.
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
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-model-health-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "model-health-api",
        "version": API_VERSION,
        "module": "d-03-model-health",
        "catalog_source": "M060 R10069-R10074 + M075 SRP topology + M073/M077/M080",
        "core": str(_CORE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class ModelHealthAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-model-health-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "model-health-api")
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
        self.send_header("X-Sovereign-Module", "d-03-model-health-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """Server-Sent Events: push a fresh snapshot every STREAM_INTERVAL
        seconds as a `model-state-change` event (the name the D-03 webapp
        listens for) until the client disconnects. Read-only, same-origin."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "model-health-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                payload = json.dumps(_core.snapshot())
                self.wfile.write(
                    f"event: model-state-change\ndata: {payload}\n\n".encode("utf-8")
                )
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
        if path == "/api/models/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/models/health":
                self._send_json(200, _core.snapshot())
                _emit_metric("health", "ok")
                return
            if path == "/api/models/catalog":
                self._send_json(200, _core.catalog_by_role())
                _emit_metric("catalog", "ok")
                return
            if path == "/api/models/gpus":
                self._send_json(200, {"gpus": _core.collect_gpus()})
                _emit_metric("gpus", "ok")
                return
            if path == "/api/models/gateway":
                # Live read-only probe of sovereign-gatewayd (:8787): the
                # sovereign router in front of every model. Never mutates.
                if _gateway_probe is None:
                    self._send_json(200, {
                        "up": False,
                        "error": "gateway_probe helper unavailable",
                    })
                else:
                    self._send_json(200, _gateway_probe.probe_gateway())
                _emit_metric("gateway", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/models/health", "/api/models/catalog",
                          "/api/models/gpus", "/api/models/gateway",
                          "/api/models/stream",
                          "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — model load/unload are MS003-signed "
                     "CLI verbs, never web mutations",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] model-health-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), ModelHealthAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="model-health read-only API + webapp host")
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
