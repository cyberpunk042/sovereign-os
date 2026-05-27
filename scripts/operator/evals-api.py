#!/usr/bin/env python3
"""scripts/operator/evals-api.py — read-only HTTP API + webapp host for the
D-10 eval-history cockpit dashboard (M060 R10106-R10108).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for the
eval module. It imports the SAME core the CLI uses
(scripts/observability/eval-tracker.py) so the dashboard and `sovereign-osctl
evals` never drift.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Read-only surface — eval runs + adapter promotion are MS003-signed CLI verbs,
never web mutations. The M079 WB/BB disaggregation invariant is enforced in the
core, not here.

Endpoints (the exact contract webapp/d-10-eval-history/index.html fetches):
  GET /api/evals/summary     full model (summary/suites/tasks/models/candidates)
  GET /api/evals/stream      Server-Sent Events (eval-run-complete events)
  GET /webapp/ | /webapp/index.html   the D-10 dashboard
  GET /version | /healthz | /

Env (all overridable):
  EVALS_API_BIND             (default 127.0.0.1)
  EVALS_API_PORT             (default 8108)
  EVALS_API_DRY_RUN          (set=1 → print config + exit)
  EVALS_WEBAPP_PATH          (override the on-disk webapp asset)
  EVALS_STREAM_INTERVAL      (SSE poll seconds, default 15.0)
  SOVEREIGN_OS_EVAL_STORE    (the JSONL eval-run log the core aggregates)
  SOVEREIGN_OS_ADAPTER_REGISTRY (promotion registry for the candidate list)
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

API_BIND = os.environ.get("EVALS_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("EVALS_API_PORT", "8108"))
DRY_RUN = bool(os.environ.get("EVALS_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("EVALS_STREAM_INTERVAL", "15.0"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_evals_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "EVALS_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-10-eval-history" / "index.html"),
))

# Import the eval-tracker core (hyphenated filename → importlib) so the API
# serves the SAME data model as the CLI (no drift).
_CORE_PATH = _REPO_ROOT / "scripts" / "observability" / "eval-tracker.py"
_spec = importlib.util.spec_from_file_location("_evaltracker_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load eval-tracker.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-evals-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "evals-api",
        "version": API_VERSION,
        "module": "d-10-eval-history",
        "catalog_source": "M060 R10106-R10108 + M048 Eval-Value + M046 + M078 + M079 WB/BB + M080",
        "core": str(_CORE_PATH),
        "eval_store": str(_core.EVAL_STORE),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class EvalsAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-evals-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "evals-api")
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
        self.send_header("X-Sovereign-Module", "d-10-eval-history-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """Server-Sent Events: push an `eval-run-complete` event (the name the
        D-10 webapp listens for) every STREAM_INTERVAL seconds. Read-only."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "evals-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                summ = _core.summary()["summary"]
                self.wfile.write(
                    f"event: eval-run-complete\ndata: {json.dumps(summ)}\n\n".encode("utf-8")
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
        if path == "/api/evals/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/evals/summary":
                self._send_json(200, _core.summary())
                _emit_metric("summary", "ok")
                return
            if path == "/api/evals/candidates":
                self._send_json(200, {"candidates": _core.summary()["candidates"]})
                _emit_metric("candidates", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/evals/summary", "/api/evals/candidates",
                          "/api/evals/stream", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — eval runs + adapter promotion are "
                     "MS003-signed CLI verbs",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] evals-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), EvalsAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="evals read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one summary, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_summary": _core.summary()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
