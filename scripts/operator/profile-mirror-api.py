#!/usr/bin/env python3
"""scripts/operator/profile-mirror-api.py — read-only HTTP API + webapp host for
the D-02 profile-choices cockpit dashboard (M060 R10063-R10068).

CROSS-REPO MIRROR — renders selfdef's MS007 active-profile mirror READ-ONLY.
The authoritative profile-authority state lives in selfdef (MS040 six-profile
matrix + MS039 L0..L6 + Ring 0..4). Profile switches are `sovereign profile set`
/ selfdefctl + MS003-signed verbs on the IPS side ONLY (MS043 R10212). Every
mutation verb → 405.

Endpoints (the exact contract webapp/d-02-profile-choices/index.html fetches):
  GET /api/profile/show      active profile + envelope + transition history
  GET /webapp/ | /webapp/index.html   the D-02 dashboard
  GET /version | /healthz | /

Env:
  PROFILE_MIRROR_API_BIND (default 127.0.0.1) · PROFILE_MIRROR_API_PORT (default
  8117) · PROFILE_MIRROR_API_DRY_RUN · PROFILE_MIRROR_WEBAPP_PATH ·
  SOVEREIGN_OS_SELFDEF_PROFILE_MIRROR · SOVEREIGN_OS_METRICS_DIR
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("PROFILE_MIRROR_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("PROFILE_MIRROR_API_PORT", "8117"))
DRY_RUN = bool(os.environ.get("PROFILE_MIRROR_API_DRY_RUN"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_profile_mirror_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "PROFILE_MIRROR_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-02-profile-choices" / "index.html"),
))

_CORE_PATH = _REPO_ROOT / "scripts" / "mirror" / "selfdef-profile-mirror.py"
_spec = importlib.util.spec_from_file_location("_profilemirror_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load selfdef-profile-mirror.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-profile-mirror-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "profile-mirror-api",
        "version": API_VERSION,
        "module": "d-02-profile-choices",
        "catalog_source": "M060 R10063-R10068 + selfdef MS040 six-profile + MS039 L0..L6 + MS007 mirror",
        "core": str(_CORE_PATH),
        "mirror_artifact": str(_core.PROFILE_MIRROR),
        "mirror_doctrine": "READ-ONLY consumer of selfdef-profile-mirror; "
                           "profile switch is `sovereign profile set` + MS003 (IPS) only (R10212)",
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class ProfileMirrorAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-profile-mirror-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "profile-mirror-api")
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
        self.send_header("X-Sovereign-Module", "d-02-profile-choices-webapp")
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
            if path == "/api/profile/show":
                self._send_json(200, _core.show())
                _emit_metric("show", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/profile/show", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only MIRROR — profile switch is `sovereign profile "
                     "set` + MS003 on the IPS side only (R10212)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] profile-mirror-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), ProfileMirrorAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="profile-mirror read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one snapshot, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(), "sample_show": _core.show()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
