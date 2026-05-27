#!/usr/bin/env python3
"""scripts/operator/sessions-api.py — read-only HTTP API + webapp host for the
D-01 active-sessions cockpit dashboard (M060 R10059-R10062).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for the
sessions module. It imports the SAME core the CLI uses
(scripts/lifecycle/session-registry.py) so the dashboard and `sovereign-osctl
sessions` never drift.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Read-only surface — hibernate/resume/kill are MS003-signed CLI verbs (MS043
R10212), never web mutations (the dashboard copies the CLI command instead).

Endpoints (the exact contract webapp/d-01-active-sessions/index.html fetches):
  GET /api/sessions/active   full model (sessions + summary)
  GET /api/sessions/stream   Server-Sent Events (session-step-advance events)
  GET /webapp/ | /webapp/index.html   the D-01 dashboard
  GET /version | /healthz | /

Env (all overridable):
  SESSIONS_API_BIND             (default 127.0.0.1)
  SESSIONS_API_PORT             (default 8109)
  SESSIONS_API_DRY_RUN          (set=1 → print config + exit)
  SESSIONS_WEBAPP_PATH          (override the on-disk webapp asset)
  SESSIONS_STREAM_INTERVAL      (SSE poll seconds, default 3.0)
  SOVEREIGN_OS_SESSION_REGISTRY (the M057 lifecycle-engine session registry)
  SOVEREIGN_OS_METRICS_DIR      (node_exporter textfile collector dir)
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

API_BIND = os.environ.get("SESSIONS_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("SESSIONS_API_PORT", "8109"))
DRY_RUN = bool(os.environ.get("SESSIONS_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("SESSIONS_STREAM_INTERVAL", "3.0"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_sessions_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "SESSIONS_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-01-active-sessions" / "index.html"),
))

# Import the session-registry core (hyphenated filename → importlib) so the API
# serves the SAME data model as the CLI (no drift).
_CORE_PATH = _REPO_ROOT / "scripts" / "lifecycle" / "session-registry.py"
_spec = importlib.util.spec_from_file_location("_sessionregistry_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load session-registry.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-sessions-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "sessions-api",
        "version": API_VERSION,
        "module": "d-01-active-sessions",
        "catalog_source": "M060 R10059-R10062 + M057 12-step lifecycle + M047 CRIU + M075 SRP",
        "core": str(_CORE_PATH),
        "session_registry": str(_core.SESSION_REGISTRY),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class SessionsAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-sessions-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "sessions-api")
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
        self.send_header("X-Sovereign-Module", "d-01-active-sessions-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """Server-Sent Events: emit `session-step-advance` (the name the D-01
        webapp listens for) only when the registry changes; heartbeat otherwise."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "sessions-api")
        self.end_headers()
        _emit_metric("stream", "open")
        last_sig = None
        try:
            while True:
                try:
                    st = _core.SESSION_REGISTRY.stat()
                    sig = (st.st_size, st.st_mtime)
                except OSError:
                    sig = (0, 0.0)
                if sig != last_sig:
                    last_sig = sig
                    summary = _core.active()["summary"]
                    self.wfile.write(
                        f"event: session-step-advance\ndata: {json.dumps(summary)}\n\n".encode("utf-8")
                    )
                else:
                    self.wfile.write(b": heartbeat\n\n")
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
        if path == "/api/sessions/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/sessions/active":
                self._send_json(200, _core.active())
                _emit_metric("active", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/sessions/active", "/api/sessions/stream",
                          "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — hibernate/resume/kill are MS003-signed "
                     "CLI verbs (MS043 R10212)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] sessions-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), SessionsAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="sessions read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one snapshot, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_active": _core.active()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
