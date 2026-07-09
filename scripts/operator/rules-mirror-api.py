#!/usr/bin/env python3
"""scripts/operator/rules-mirror-api.py — read-only HTTP API + webapp host for the
D-12 networking cockpit dashboard (M060 R10113 + R10212).

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for the
sovereign-os nftables rules MIRROR. It imports the SAME core the CLI uses
(scripts/mirror/selfdef-rules-mirror.py) so the dashboard and `sovereign-osctl
rules-mirror` never drift.

CROSS-REPO MIRROR — the authoritative nftables Ring-0-4 ruleset lives in selfdef
(the IPS). This surface renders selfdef's MS007 typed-mirror snapshot READ-ONLY.
Rules are installed/removed by `selfdefctl` + `nft` at the IPS layer ONLY (R10113 +
MS043 R10212). sovereign-os NEVER runs nft or mutates IPS state — every HTTP verb
except GET/HEAD → 405.

Endpoints (the exact contract webapp/d-12-networking/index.html fetches):
  GET /api/d-12/snapshot     full model (summaries/rules, MS039 5-ring)
  GET /api/d-12/stream       Server-Sent Events (snapshot events, live refresh)
  GET /webapp/ | /webapp/index.html   the D-12 dashboard
  GET /version | /healthz | /control-systems | /

Env (all overridable):
  RULES_MIRROR_API_BIND          (default 127.0.0.1)
  RULES_MIRROR_API_PORT          (default 8133)
  RULES_MIRROR_API_DRY_RUN       (set=1 → print config + exit)
  RULES_MIRROR_WEBAPP_PATH       (override the on-disk webapp asset)
  RULES_MIRROR_STREAM_INTERVAL   (SSE push seconds, default 5.0)
  SOVEREIGN_OS_SELFDEF_RULES_MIRROR (the selfdef-published mirror artifact)
  SOVEREIGN_OS_METRICS_DIR        (node_exporter textfile collector dir)
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

API_BIND = os.environ.get("RULES_MIRROR_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("RULES_MIRROR_API_PORT", "8133"))
DRY_RUN = bool(os.environ.get("RULES_MIRROR_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("RULES_MIRROR_STREAM_INTERVAL", "5.0"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_rules_mirror_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "RULES_MIRROR_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-12-networking" / "index.html"),
))

# Import the mirror core (hyphenated filename → importlib).
_CORE_PATH = _REPO_ROOT / "scripts" / "mirror" / "selfdef-rules-mirror.py"
_spec = importlib.util.spec_from_file_location("_rulesmirror_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load selfdef-rules-mirror.py from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

# Optional shared control-systems loader (served at /control-systems), mirroring the
# other cockpit daemons; degrades to an empty registry when unavailable.
try:
    _CS_PATH = _REPO_ROOT / "config" / "control-systems.yaml"

    def _load_control_systems():
        import yaml  # noqa: PLC0415 — optional dep, only for /control-systems
        if not _CS_PATH.is_file():
            return None
        return yaml.safe_load(_CS_PATH.read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    def _load_control_systems():
        return None


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-rules-mirror-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "rules-mirror-api",
        "version": API_VERSION,
        "module": "d-12-networking",
        "catalog_source": "M060 R10113 + selfdef MS024/MS038/MS039 Ring-0-4 + MS007 mirror",
        "core": str(_CORE_PATH),
        "mirror_artifact": str(_core.RULES_MIRROR),
        "mirror_doctrine": "READ-ONLY consumer of selfdef-rules-mirror; nft rule "
                           "ops are selfdefctl + MS003 (IPS) only (R10113)",
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class RulesMirrorAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-rules-mirror-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "rules-mirror-api")
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
        self.send_header("X-Sovereign-Module", "d-12-networking-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """SSE: push a fresh snapshot every STREAM_INTERVAL seconds as a `snapshot`
        event (live refresh) until the client disconnects. Read-only, same-origin."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "rules-mirror-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                payload = json.dumps(_core.snapshot())
                self.wfile.write(f"event: snapshot\ndata: {payload}\n\n".encode("utf-8"))
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
        if path in ("/control-systems", "/control-systems.json"):
            cs = _load_control_systems()
            self._send_json(200, cs if cs is not None else {"systems": []})
            _emit_metric("control-systems", "ok")
            return
        if path in ("/webapp", "/webapp/index.html"):
            self._send_webapp()
            return
        if path == "/api/d-12/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/d-12/snapshot":
                self._send_json(200, _core.snapshot())
                _emit_metric("snapshot", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/d-12/snapshot", "/api/d-12/stream", "/version",
                          "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only MIRROR — nftables rule ops are selfdefctl + MS003 "
                     "verbs on the IPS side only (R10113); sovereign-os never runs "
                     "nft or mutates IPS state",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] rules-mirror-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), RulesMirrorAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="rules-mirror read-only API + webapp host")
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
