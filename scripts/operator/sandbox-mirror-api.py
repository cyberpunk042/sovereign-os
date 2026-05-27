#!/usr/bin/env python3
"""scripts/operator/sandbox-mirror-api.py — read-only HTTP API + webapp host for
the D-15 sandboxes cockpit dashboard (M060 R10118-R10119).

CROSS-REPO MIRROR — renders selfdef's MS007 sandbox mirror READ-ONLY. The
authoritative sandbox-allocation state lives in selfdef (MS032 sandbox-tiers +
MS036 tool-sandboxes). sandbox checkpoint/release are selfdefctl + MS003 verbs
on the IPS side ONLY (R10119 + MS043 R10212). Every mutation verb → 405.

Endpoints (the exact contract webapp/d-15-sandboxes/index.html fetches):
  GET /api/d-15/snapshot     full model (tier summaries + allocations)
  GET /webapp/ | /webapp/index.html   the D-15 dashboard
  GET /version | /healthz | /

Env:
  SANDBOX_MIRROR_API_BIND (default 127.0.0.1) · SANDBOX_MIRROR_API_PORT (default
  8116) · SANDBOX_MIRROR_API_DRY_RUN · SANDBOX_MIRROR_WEBAPP_PATH ·
  SOVEREIGN_OS_SELFDEF_SANDBOX_MIRROR · SOVEREIGN_OS_METRICS_DIR
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("SANDBOX_MIRROR_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("SANDBOX_MIRROR_API_PORT", "8116"))
DRY_RUN = bool(os.environ.get("SANDBOX_MIRROR_API_DRY_RUN"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_sandbox_mirror_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "SANDBOX_MIRROR_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-15-sandboxes" / "index.html"),
))

_CORE_PATH = _REPO_ROOT / "scripts" / "mirror" / "selfdef-sandbox-mirror.py"
_spec = importlib.util.spec_from_file_location("_sandboxmirror_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load selfdef-sandbox-mirror.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-sandbox-mirror-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "sandbox-mirror-api",
        "version": API_VERSION,
        "module": "d-15-sandboxes",
        "catalog_source": "M060 R10118-R10119 + selfdef MS032/MS036 + MS007 mirror",
        "core": str(_CORE_PATH),
        "mirror_artifact": str(_core.SANDBOX_MIRROR),
        "mirror_doctrine": "READ-ONLY consumer of selfdef-sandbox-mirror; "
                           "checkpoint/release are selfdefctl + MS003 (IPS) only (R10119)",
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class SandboxMirrorAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-sandbox-mirror-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "sandbox-mirror-api")
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
        self.send_header("X-Sovereign-Module", "d-15-sandboxes-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
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
            if path == "/api/d-15/snapshot":
                self._send_json(200, _core.snapshot())
                _emit_metric("snapshot", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/d-15/snapshot", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only MIRROR — sandbox checkpoint/release are "
                     "selfdefctl + MS003 verbs on the IPS side only (R10119)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] sandbox-mirror-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), SandboxMirrorAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="sandbox-mirror read-only API + webapp host")
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
