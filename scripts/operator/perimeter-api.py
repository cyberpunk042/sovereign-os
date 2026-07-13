#!/usr/bin/env python3
"""scripts/operator/perimeter-api.py — read-only HTTP API + webapp host for the D-28
perimeter cockpit dashboard (selfdef IPS security perimeter, Tetragon sovereign-kernel-fence).

The panel renders its table with the REAL sovereign-cockpit-perimeter-panel crate in-browser
(wasm); this daemon only supplies the Panel snapshot it consumes.

HONESTY RULE (cross-repo, sacrosanct): selfdef owns the authority. selfdef enforces the
Tetragon fence and writes its verdict ring at /var/cache/selfdef/perimeter/ring, the active
extension manifests under /etc/selfdef/perimeter-extensions, and the TracingPolicy;
sovereign-os only renders them. So this API reads those if present, and otherwise returns an
EMPTY, honest-deferred Panel. It NEVER fabricates a verdict or an extension.

Endpoints:
  GET /api/d-28/snapshot     the perimeter Panel {schema_version, recent_verdicts, active_extensions, policy_present, now_ms}
  GET /webapp/ | /webapp/index.html   the D-28 dashboard
  GET /version | /healthz | /

Env:
  PERIMETER_API_BIND (default 127.0.0.1) · PERIMETER_API_PORT (default 8145)
  PERIMETER_API_DRY_RUN · PERIMETER_WEBAPP_PATH · PERIMETER_RING_DIR · PERIMETER_EXT_DIR
  PERIMETER_POLICY · SOVEREIGN_OS_METRICS_DIR
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("PERIMETER_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("PERIMETER_API_PORT", "8145"))
DRY_RUN = bool(os.environ.get("PERIMETER_API_DRY_RUN"))
API_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

RING_DIR = Path(os.environ.get("PERIMETER_RING_DIR", "/var/cache/selfdef/perimeter/ring"))
EXT_DIR = Path(os.environ.get("PERIMETER_EXT_DIR", "/etc/selfdef/perimeter-extensions"))
POLICY_PATH = Path(os.environ.get("PERIMETER_POLICY", "/etc/selfdef/perimeter-tracingpolicy.yaml"))

METRICS_DIR = os.environ.get("SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector")
METRIC_NAME = "sovereign_os_operator_perimeter_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "PERIMETER_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-28-perimeter" / "index.html"),
))


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-perimeter-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def snapshot() -> dict:
    """Build the perimeter Panel the crate consumes. Reads selfdef's verdict ring + extension
    manifests + TracingPolicy when present; otherwise empty (honest-deferred). Never fabricates."""
    verdicts: list[dict] = []
    if RING_DIR.is_dir():
        recs = []
        for f in sorted(RING_DIR.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            outcome = rec.get("outcome")
            # outcome is the adjacently-tagged {"outcome": "...", "detail": ...} object the crate expects
            if not isinstance(outcome, dict) or "outcome" not in outcome:
                continue
            recs.append({
                "outcome": outcome,
                "attempted_binary_path": str(rec.get("attempted_binary_path", "")),
                "attempting_pid": int(rec.get("attempting_pid", 0)),
                "process_cmdline": str(rec.get("process_cmdline", "")),
                "ts_ms": int(rec.get("ts_ms", 0)),
                "hostname": str(rec.get("hostname", "")),
            })
        recs.sort(key=lambda e: e["ts_ms"], reverse=True)
        verdicts = recs[:16]

    extensions: list[dict] = []
    if EXT_DIR.is_dir():
        for f in sorted(EXT_DIR.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if "extension_id" not in rec:
                continue
            extensions.append({
                "extension_id": str(rec.get("extension_id", "")),
                "binary_paths": rec.get("binary_paths", []) if isinstance(rec.get("binary_paths"), list) else [],
                "expires_at_ms": int(rec.get("expires_at_ms", 0)),
                "signer_kid": str(rec.get("signer_kid", "")),
                "auditor_kid": str(rec.get("auditor_kid", "")),
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "now_ms": int(time.time() * 1000),
        "policy_present": POLICY_PATH.exists(),
        "recent_verdicts": verdicts,
        "active_extensions": extensions,
        "ring_present": RING_DIR.is_dir(),
        "note": None if (verdicts or extensions) else "selfdef perimeter ring/extensions absent — the aggregate reports the degraded state (honest-deferred); nothing is fabricated",
    }


def _version_payload() -> dict:
    return {
        "service": "perimeter-api",
        "version": API_VERSION,
        "module": "d-28-perimeter",
        "catalog_source": "selfdef IPS security perimeter (Tetragon sovereign-kernel-fence) + sovereign-cockpit-perimeter-panel",
        "ring_dir": str(RING_DIR),
        "ring_present": RING_DIR.is_dir(),
        "ext_dir": str(EXT_DIR),
        "policy_path": str(POLICY_PATH),
        "policy_present": POLICY_PATH.exists(),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "api", "webapp", "service"],
        "standing_rule": "selfdef owns the authority; the cockpit renders, never fabricates.",
    }


class PerimeterAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-perimeter-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "perimeter-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        try:
            body = WEBAPP_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {"error": f"webapp asset unreadable: {e}", "expected_path": str(WEBAPP_PATH)})
            _emit_metric("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "d-28-perimeter-webapp")
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
            if path == "/api/d-28/snapshot":
                self._send_json(200, snapshot())
                _emit_metric("snapshot", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/d-28/snapshot", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — selfdef enforces the perimeter fence and writes its "
                     "verdict ring; the cockpit only renders it",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] perimeter-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), PerimeterAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="perimeter read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true", help="build one snapshot, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(), "sample_snapshot": snapshot()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
