#!/usr/bin/env python3
"""scripts/operator/traces-api.py — read-only HTTP API + webapp host for the
D-05 traces cockpit dashboard (M060 R10083-R10087).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for
the traces module. It imports the SAME core the CLI uses
(scripts/observability/trace-store.py) so the dashboard and `sovereign-osctl
traces` never drift.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Read-only surface — spans are observed, never mutated; MS009 replay-verify is
an MS003-signed CLI verb, never a web mutation.

Endpoints (the exact contract webapp/d-05-traces/index.html fetches):
  GET /api/traces/spans?q=&severity=&ocsf_class=&window=   filtered span search
  GET /api/traces/<trace_id>                               every span in a trace
  GET /api/traces/stream                                   SSE (span-added events)
  GET /webapp/ | /webapp/index.html                        the D-05 dashboard
  GET /version | /healthz | /

Env (all overridable):
  TRACES_API_BIND            (default 127.0.0.1)
  TRACES_API_PORT            (default 8105)
  TRACES_API_DRY_RUN         (set=1 → print config + exit)
  TRACES_WEBAPP_PATH         (override the on-disk webapp asset)
  TRACES_STREAM_INTERVAL     (SSE poll seconds, default 3.0)
  SOVEREIGN_OS_SPAN_STORE    (the JSONL span log the core reads)
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

API_BIND = os.environ.get("TRACES_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("TRACES_API_PORT", "8105"))
DRY_RUN = bool(os.environ.get("TRACES_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("TRACES_STREAM_INTERVAL", "3.0"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_traces_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "TRACES_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-05-traces" / "index.html"),
))

# Import the trace-store core (hyphenated filename → importlib) so the API
# serves the SAME data model as the CLI (no drift).
_CORE_PATH = _REPO_ROOT / "scripts" / "observability" / "trace-store.py"
_spec = importlib.util.spec_from_file_location("_tracestore_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load trace-store.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-traces-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "traces-api",
        "version": API_VERSION,
        "module": "d-05-traces",
        "catalog_source": "M060 R10083-R10087 + M049 13-field span + MS026 OCSF + MS009 replay",
        "core": str(_CORE_PATH),
        "span_store": str(_core.SPAN_STORE),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class TracesAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-traces-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "traces-api")
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
        self.send_header("X-Sovereign-Module", "d-05-traces-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """Server-Sent Events: emit a `span-added` event (the name the D-05
        webapp listens for) only when the span store actually grows; otherwise
        a heartbeat comment keeps the connection warm. Read-only, same-origin."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "traces-api")
        self.end_headers()
        _emit_metric("stream", "open")
        last_sig = None
        try:
            while True:
                sig = _core.store_signature()
                if sig != last_sig:
                    last_sig = sig
                    summary = _core.query_spans("", "", "", 3600)["summary"]
                    self.wfile.write(
                        f"event: span-added\ndata: {json.dumps(summary)}\n\n".encode("utf-8")
                    )
                else:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
                time.sleep(STREAM_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return  # client went away — normal SSE lifecycle

    def do_GET(self) -> None:  # noqa: N802
        split = urllib.parse.urlsplit(self.path)
        path = split.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(split.query)
        if path in ("/", "/healthz"):
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return
        if path in ("/webapp", "/webapp/index.html"):
            self._send_webapp()
            return
        if path == "/api/traces/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/traces/spans":
                def one(k: str, default: str = "") -> str:
                    return (qs.get(k) or [default])[0]
                try:
                    window = int(one("window", "3600"))
                except ValueError:
                    window = 3600
                self._send_json(200, _core.query_spans(
                    q=one("q"), severity=one("severity"),
                    ocsf_class=one("ocsf_class"), window_secs=window,
                ))
                _emit_metric("spans", "ok")
                return
            if path.startswith("/api/traces/"):
                trace_id = urllib.parse.unquote(path[len("/api/traces/"):])
                if trace_id:
                    self._send_json(200, _core.get_trace(trace_id))
                    _emit_metric("trace", "ok")
                    return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/traces/spans", "/api/traces/<trace_id>",
                          "/api/traces/stream", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — spans are observed, not mutated; "
                     "MS009 replay-verify is an MS003-signed CLI verb",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] traces-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), TracesAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="traces read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one query, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_query": _core.query_spans("", "", "", 3600)}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
