#!/usr/bin/env python3
"""scripts/operator/approvals-api.py — read-only HTTP API + webapp host for the
D-06 pending-approvals cockpit dashboard (M060 R10088-R10092).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for the
approvals module. It imports the SAME core the CLI uses
(scripts/lifecycle/approval-queue.py) so the dashboard and `sovereign-osctl
approvals` never drift.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Operator-controlled axiom (M065): "No PR opens past a gate without operator
sign-off." Read-only surface — approve/deny/defer + gate sign-off are
MS003-signed CLI verbs (MS043 R10212), never web mutations.

Endpoints (the exact contract webapp/d-06-pending-approvals/index.html fetches):
  GET /api/approvals/pending     full model (approvals/gates/profile/summary)
  GET /api/operator-key/status   MS003 operator-key presence status
  GET /api/approvals/stream      Server-Sent Events (approval-added events)
  GET /webapp/ | /webapp/index.html   the D-06 dashboard
  GET /version | /healthz | /

Env (all overridable):
  APPROVALS_API_BIND             (default 127.0.0.1)
  APPROVALS_API_PORT             (default 8110)
  APPROVALS_API_DRY_RUN          (set=1 → print config + exit)
  APPROVALS_WEBAPP_PATH          (override the on-disk webapp asset)
  APPROVALS_STREAM_INTERVAL      (SSE poll seconds, default 3.0)
  SOVEREIGN_OS_APPROVALS         (the approval-queue registry json)
  SOVEREIGN_OS_OPERATOR_KEY[_STATUS] (operator-key presence / status)
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

API_BIND = os.environ.get("APPROVALS_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("APPROVALS_API_PORT", "8110"))
DRY_RUN = bool(os.environ.get("APPROVALS_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("APPROVALS_STREAM_INTERVAL", "3.0"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_approvals_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "APPROVALS_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-06-pending-approvals" / "index.html"),
))

# Import the approval-queue core (hyphenated filename → importlib) so the API
# serves the SAME data model as the CLI (no drift).
_CORE_PATH = _REPO_ROOT / "scripts" / "lifecycle" / "approval-queue.py"
_spec = importlib.util.spec_from_file_location("_approvalqueue_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load approval-queue.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-approvals-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "approvals-api",
        "version": API_VERSION,
        "module": "d-06-pending-approvals",
        "catalog_source": "M060 R10088-R10092 + M065 Five Stage Gates + MS039/MS040/MS041",
        "core": str(_CORE_PATH),
        "approvals_queue": str(_core.APPROVALS_QUEUE),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class ApprovalsAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-approvals-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "approvals-api")
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
        self.send_header("X-Sovereign-Module", "d-06-pending-approvals-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """Server-Sent Events: emit `approval-added` (the name the D-06 webapp
        listens for) only when the queue changes; heartbeat otherwise."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "approvals-api")
        self.end_headers()
        _emit_metric("stream", "open")
        last_sig = None
        try:
            while True:
                try:
                    st = _core.APPROVALS_QUEUE.stat()
                    sig = (st.st_size, st.st_mtime)
                except OSError:
                    sig = (0, 0.0)
                if sig != last_sig:
                    last_sig = sig
                    self.wfile.write(
                        f"event: approval-added\ndata: {json.dumps(_core.pending()['summary'])}\n\n".encode("utf-8")
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
        if path == "/api/approvals/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/approvals/pending":
                self._send_json(200, _core.pending())
                _emit_metric("pending", "ok")
                return
            if path == "/api/operator-key/status":
                self._send_json(200, _core.operator_key_status())
                _emit_metric("operator_key", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/approvals/pending", "/api/operator-key/status",
                          "/api/approvals/stream", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — approve/deny/defer + gate sign-off are "
                     "MS003-signed CLI verbs (M065: no gate passes without "
                     "operator sign-off)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] approvals-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), ApprovalsAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="approvals read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one snapshot, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_pending": _core.pending(),
                          "operator_key": _core.operator_key_status()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
