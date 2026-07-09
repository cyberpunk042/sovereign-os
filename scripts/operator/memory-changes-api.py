#!/usr/bin/env python3
"""scripts/operator/memory-changes-api.py — read-only HTTP API + webapp host for
the D-07 memory-changes cockpit dashboard (M060 R10093-R10096).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for the
memory-changes module. It imports the SAME core the CLI uses
(scripts/intelligence/memory-changes.py) so the dashboard and `sovereign-osctl
memory-changes` never drift.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Read-only surface — memory promote/pin/forget + change approve/reject are
MS003-signed CLI verbs (MS043 R10212), never web mutations.

Endpoints (the exact contract webapp/d-07-memory-changes/index.html fetches):
  GET /api/d-07/snapshot     full model (counts/lifecycle/diffs/pending)
  GET /api/d-07/entries      the addressable M028 memory entries (SDD-060 list view)
  GET /api/d-07/navigate     the RLM memory navigator (SDD-068 M00472) — read-compute query
  GET /api/d-07/stream       Server-Sent Events (snapshot events)
  GET /webapp/ | /webapp/index.html   the D-07 dashboard
  GET /version | /healthz | /

Env (all overridable):
  MEMORY_CHANGES_API_BIND        (default 127.0.0.1)
  MEMORY_CHANGES_API_PORT        (default 8112)
  MEMORY_CHANGES_API_DRY_RUN     (set=1 → print config + exit)
  MEMORY_CHANGES_WEBAPP_PATH     (override the on-disk webapp asset)
  MEMORY_CHANGES_STREAM_INTERVAL (SSE poll seconds, default 5.0)
  SOVEREIGN_OS_MEMORY_STATE      (the Memory OS published state json)
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

API_BIND = os.environ.get("MEMORY_CHANGES_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("MEMORY_CHANGES_API_PORT", "8112"))
DRY_RUN = bool(os.environ.get("MEMORY_CHANGES_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("MEMORY_CHANGES_STREAM_INTERVAL", "5.0"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_memory_changes_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "MEMORY_CHANGES_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-07-memory-changes" / "index.html"),
))

# Import the memory-changes core (hyphenated filename → importlib).
_CORE_PATH = _REPO_ROOT / "scripts" / "intelligence" / "memory-changes.py"
_spec = importlib.util.spec_from_file_location("_memorychanges_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load memory-changes.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

# Import the memory-STORE (SDD-059/060) — the addressable mem-<id> entries, a SECOND
# read source alongside the projection core. Used read-only (`store_list()`); the
# core stays a pure projection reader. If the store module is unavailable the entries
# endpoint degrades to an empty list (never a crash).
_STORE_PATH = _REPO_ROOT / "scripts" / "intelligence" / "memory-store.py"
_store = None
try:
    _store_spec = importlib.util.spec_from_file_location("_memorystore_core", _STORE_PATH)
    if _store_spec is not None and _store_spec.loader is not None:
        _store = importlib.util.module_from_spec(_store_spec)
        _store_spec.loader.exec_module(_store)
except Exception as _e:  # noqa: BLE001 — degrade to empty entries, never fail the daemon
    sys.stderr.write(f"[warn] memory-store unavailable ({_e}); /api/d-07/entries → []\n")

# Import the RLM memory NAVIGATOR (SDD-068 M00472) — the read-compute query engine that
# powers the read-only GET /api/d-07/navigate. Degrade-to-None like the store block; the
# navigate endpoint then answers 503 (never a crash). The navigator NEVER mutates the
# store (read-compute); the daemon stays 405 on all POST/PUT/DELETE (R10212).
_NAV_PATH = _REPO_ROOT / "scripts" / "intelligence" / "memory-navigate.py"
_navigator = None
try:
    _nav_spec = importlib.util.spec_from_file_location("_memorynavigate_core", _NAV_PATH)
    if _nav_spec is not None and _nav_spec.loader is not None:
        _navigator = importlib.util.module_from_spec(_nav_spec)
        _nav_spec.loader.exec_module(_navigator)
except Exception as _e:  # noqa: BLE001 — navigate endpoint → 503, never fail the daemon
    sys.stderr.write(f"[warn] memory-navigate unavailable ({_e}); /api/d-07/navigate → 503\n")


def _navigate_payload(qs: dict) -> dict:
    """The RLM navigator answer for GET /api/d-07/navigate. Read-only; honest-defers
    (never fabricates) when the LM is unreachable / the store is empty."""
    def _one(k):
        v = qs.get(k)
        return v[0] if isinstance(v, list) and v else None
    q = _one("q") or ""
    mtype = _one("type")
    try:
        mtype = int(mtype) if mtype is not None else None
    except (TypeError, ValueError):
        mtype = None
    limit = _one("limit")
    try:
        limit = int(limit) if limit is not None else 5
    except (TypeError, ValueError):
        limit = 5
    compose = _one("compose") not in ("0", "false", "no")
    return _navigator.navigate(
        q, mtype=mtype, stage=_one("stage"), topic=_one("topic"),
        verb=_one("verb"), at=_one("at"), limit=limit, compose=compose)


def _entries_payload() -> dict:
    """The addressable M028 memory entries (SDD-060 list view). Read-only projection
    of the store; empty-safe when the store module/file is absent."""
    entries = []
    if _store is not None:
        try:
            entries = _store.store_list()
        except Exception:  # noqa: BLE001 — store read error → empty, never crash
            entries = []
    return {"schema_version": getattr(_core, "SCHEMA_VERSION", "1.0.0"),
            "entries": entries}


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-memory-changes-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "memory-changes-api",
        "version": API_VERSION,
        "module": "d-07-memory-changes",
        "catalog_source": "M060 R10093-R10096 + M028 8 memory types + 11-stage lifecycle + MS039 7 trust dims",
        "core": str(_CORE_PATH),
        "store": str(_STORE_PATH),
        "memory_state": str(_core.MEMORY_STATE),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class MemoryChangesAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-memory-changes-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "memory-changes-api")
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
        self.send_header("X-Sovereign-Module", "d-07-memory-changes-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """Server-Sent Events: push a `snapshot` event (the name the D-07 webapp
        listens for) every STREAM_INTERVAL seconds. Read-only."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "memory-changes-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                self.wfile.write(
                    f"event: snapshot\ndata: {json.dumps(_core.snapshot())}\n\n".encode("utf-8")
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
        if path == "/api/d-07/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/d-07/snapshot":
                self._send_json(200, _core.snapshot())
                _emit_metric("snapshot", "ok")
                return
            if path == "/api/d-07/entries":
                self._send_json(200, _entries_payload())
                _emit_metric("entries", "ok")
                return
            if path == "/api/d-07/navigate":
                # SDD-068 — the RLM navigator (read-compute; NEVER mutates the store).
                if _navigator is None:
                    self._send_json(503, {"error": "memory navigator unavailable"})
                    _emit_metric("navigate", "503")
                    return
                qs = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                self._send_json(200, _navigate_payload(qs))
                _emit_metric("navigate", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/d-07/snapshot", "/api/d-07/entries", "/api/d-07/navigate",
                          "/api/d-07/stream", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — memory promote/pin/forget + change "
                     "approve/reject are MS003-signed CLI verbs (MS043 R10212)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] memory-changes-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), MemoryChangesAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="memory-changes read-only API + webapp host")
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
