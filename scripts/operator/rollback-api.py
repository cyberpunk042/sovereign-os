#!/usr/bin/env python3
"""scripts/operator/rollback-api.py — read-only HTTP API + webapp host for the
D-08 rollback-points cockpit dashboard (M060 R10097-R10101).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for the
rollback module. It imports the SAME core the CLI uses
(scripts/lifecycle/rollback-points.py) so the dashboard and `sovereign-osctl
rollback` never drift.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Read-only surface — rollback-apply + snapshot create/prune are MS003-signed CLI
verbs (MS043 R10212); the dashboard emits the CLI string, the daemon never
mutates. The preview endpoint is a dry-run (R10099) with no side effects.

Endpoints (the exact contract webapp/d-08-rollback-points/index.html fetches):
  GET /api/d-08/snapshot       full model (snapshots + commit/snapshot timeline)
  GET /api/d-08/preview?to=<id>  dry-run rollback plan for a target snapshot
  GET /webapp/ | /webapp/index.html   the D-08 dashboard
  GET /version | /healthz | /

Env (all overridable):
  ROLLBACK_API_BIND          (default 127.0.0.1)
  ROLLBACK_API_PORT          (default 8111)
  ROLLBACK_API_DRY_RUN       (set=1 → print config + exit)
  ROLLBACK_WEBAPP_PATH       (override the on-disk webapp asset)
  SOVEREIGN_OS_GIT_REPO      (the repo the commit history is read from)
  SOVEREIGN_OS_ROLLBACK_LOG  (past rollback-apply events for "last rollback")
  SOVEREIGN_OS_METRICS_DIR   (node_exporter textfile collector dir)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("ROLLBACK_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("ROLLBACK_API_PORT", "8111"))
DRY_RUN = bool(os.environ.get("ROLLBACK_API_DRY_RUN"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_rollback_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "ROLLBACK_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-08-rollback-points" / "index.html"),
))

# Import the rollback-points core (hyphenated filename → importlib).
_CORE_PATH = _REPO_ROOT / "scripts" / "lifecycle" / "rollback-points.py"
_spec = importlib.util.spec_from_file_location("_rollbackpoints_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load rollback-points.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-rollback-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "rollback-api",
        "version": API_VERSION,
        "module": "d-08-rollback-points",
        "catalog_source": "M060 R10097-R10101 + M068 ZFS + M047 continuity + MS041 + MS003",
        "core": str(_CORE_PATH),
        "git_repo": str(_core.GIT_REPO),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class RollbackAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-rollback-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "rollback-api")
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
        self.send_header("X-Sovereign-Module", "d-08-rollback-points-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

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
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/d-08/snapshot":
                self._send_json(200, _core.snapshot())
                _emit_metric("snapshot", "ok")
                return
            if path == "/api/d-08/preview":
                to = (qs.get("to") or [""])[0]
                if not to:
                    self._send_json(400, {"error": "missing ?to=<snapshot-id>"})
                    _emit_metric("preview", "400")
                    return
                self._send_json(200, _core.preview(to))
                _emit_metric("preview", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/d-08/snapshot", "/api/d-08/preview?to=<id>",
                          "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — rollback-apply + snapshot create/prune "
                     "are MS003-signed CLI verbs (MS043 R10212); preview is dry-run",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] rollback-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), RollbackAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="rollback read-only API + webapp host")
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
