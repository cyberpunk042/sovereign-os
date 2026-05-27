#!/usr/bin/env python3
"""scripts/operator/super-model-api.py — read-only HTTP API + webapp host for
the D-19 super-model-manifest cockpit dashboard (M060 R10124-R10125).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for the
super-model-manifest module. sovereign-os-NATIVE (the super-model manifest is
sovereign-os's own version + module-version table). Serves the SAME data model
the CLI uses (scripts/manifest/super-model-manifest.py).

Read-only — the manifest is computed from the repo (git + the milestone catalog
+ the editorial config); nothing is mutated here.

Endpoints (the exact contract webapp/d-19-super-model-manifest/index.html fetches):
  GET /api/d-19/snapshot     full model (version + phases + milestones + cross_refs)
  GET /webapp/ | /webapp/index.html   the D-19 dashboard
  GET /version | /healthz | /

Env:
  SUPER_MODEL_API_BIND (default 127.0.0.1) · SUPER_MODEL_API_PORT (default 8119)
  · SUPER_MODEL_API_DRY_RUN · SUPER_MODEL_WEBAPP_PATH · SOVEREIGN_OS_MILESTONES_DIR
  · SOVEREIGN_OS_SUPER_MODEL_MANIFEST · SOVEREIGN_OS_METRICS_DIR
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("SUPER_MODEL_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("SUPER_MODEL_API_PORT", "8119"))
DRY_RUN = bool(os.environ.get("SUPER_MODEL_API_DRY_RUN"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_super_model_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "SUPER_MODEL_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-19-super-model-manifest" / "index.html"),
))

_CORE_PATH = _REPO_ROOT / "scripts" / "manifest" / "super-model-manifest.py"
_spec = importlib.util.spec_from_file_location("_supermodel_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load super-model-manifest.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-super-model-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "super-model-api",
        "version": API_VERSION,
        "module": "d-19-super-model-manifest",
        "catalog_source": "M060 R10124-R10125 + live milestone catalog + git + M053 phases",
        "core": str(_CORE_PATH),
        "manifest_config": str(_core.MANIFEST_TOML),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class SuperModelAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-super-model-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "super-model-api")
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
        self.send_header("X-Sovereign-Module", "d-19-super-model-manifest-webapp")
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
            if path == "/api/d-19/snapshot":
                self._send_json(200, _core.snapshot())
                _emit_metric("snapshot", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/d-19/snapshot", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — the super-model manifest is computed "
                     "from the repo (git + catalog + config), not mutated here",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] super-model-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), SuperModelAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="super-model read-only API + webapp host")
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
