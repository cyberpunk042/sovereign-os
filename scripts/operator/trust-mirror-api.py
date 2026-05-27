#!/usr/bin/env python3
"""scripts/operator/trust-mirror-api.py — read-only HTTP API + webapp host for
the D-18 trust-scores cockpit dashboard (M060 R10123).

CROSS-REPO MIRROR — renders selfdef's MS007 trust-score mirror READ-ONLY. The
authoritative per-tool trust scores live in selfdef (MS042 trust-score tracker,
SDD-064 /v1/trust-scores). Score reset is a selfdefctl + MS003 verb on the IPS
side ONLY (MS043 R10212). Every mutation verb → 405.

Endpoints (the exact contract webapp/d-18-trust-scores/index.html fetches):
  GET /api/d-18/snapshot     full model (tools w/ score history + bands)
  GET /webapp/ | /webapp/index.html   the D-18 dashboard
  GET /version | /healthz | /

Env:
  TRUST_MIRROR_API_BIND (default 127.0.0.1) · TRUST_MIRROR_API_PORT (default
  8115) · TRUST_MIRROR_API_DRY_RUN · TRUST_MIRROR_WEBAPP_PATH ·
  SOVEREIGN_OS_SELFDEF_TRUST_MIRROR · SOVEREIGN_OS_METRICS_DIR
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("TRUST_MIRROR_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("TRUST_MIRROR_API_PORT", "8115"))
DRY_RUN = bool(os.environ.get("TRUST_MIRROR_API_DRY_RUN"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_trust_mirror_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "TRUST_MIRROR_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-18-trust-scores" / "index.html"),
))

_CORE_PATH = _REPO_ROOT / "scripts" / "mirror" / "selfdef-trust-score-mirror.py"
_spec = importlib.util.spec_from_file_location("_trustmirror_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load selfdef-trust-score-mirror.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-trust-mirror-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "trust-mirror-api",
        "version": API_VERSION,
        "module": "d-18-trust-scores",
        "catalog_source": "M060 R10123 + selfdef MS042 (SDD-064 /v1/trust-scores) + MS007 mirror",
        "core": str(_CORE_PATH),
        "mirror_artifact": str(_core.TRUST_MIRROR),
        "mirror_doctrine": "READ-ONLY consumer of selfdef-trust-score-mirror; "
                           "score reset is selfdefctl + MS003 (IPS) only (R10212)",
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class TrustMirrorAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-trust-mirror-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "trust-mirror-api")
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
        self.send_header("X-Sovereign-Module", "d-18-trust-scores-webapp")
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
            if path == "/api/d-18/snapshot":
                self._send_json(200, _core.snapshot())
                _emit_metric("snapshot", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/d-18/snapshot", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only MIRROR — trust-score reset is a selfdefctl + "
                     "MS003 verb on the IPS side only (R10212)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] trust-mirror-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), TrustMirrorAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="trust-mirror read-only API + webapp host")
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
