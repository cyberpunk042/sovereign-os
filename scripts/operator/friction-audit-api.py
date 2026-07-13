#!/usr/bin/env python3
"""scripts/operator/friction-audit-api.py — read-only HTTP API + webapp host for
the D-26 friction-audit cockpit dashboard (M060 boot-time friction-audit gate).

The `api` + `service` + `webapp` surfaces for the friction-audit module. The
panel renders its 6-gate table with the REAL sovereign-cockpit-friction-audit-panel
crate in-browser (wasm); this daemon only supplies the Panel snapshot it consumes.

HONESTY RULE (cross-repo, sacrosanct): selfdef owns the authority. selfdef writes
the verdict ring at /var/cache/selfdef/friction-audit/ring; sovereign-os only
renders it. So this API reads that ring if selfdef has written it, and otherwise
returns an EMPTY, honest-deferred Panel (every gate renders Gray "—" in the crate).
It NEVER fabricates PASS/FAIL.

Endpoints (the exact contract webapp/d-26-friction-audit/index.html fetches):
  GET /api/d-26/snapshot     the friction-audit Panel {schema_version, entries, now_ms}
  GET /webapp/ | /webapp/index.html   the D-26 dashboard
  GET /version | /healthz | /

Env:
  FRICTION_AUDIT_API_BIND (default 127.0.0.1) · FRICTION_AUDIT_API_PORT (default 8143)
  FRICTION_AUDIT_API_DRY_RUN · FRICTION_AUDIT_WEBAPP_PATH · FRICTION_AUDIT_RING_DIR
  SOVEREIGN_OS_METRICS_DIR
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("FRICTION_AUDIT_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("FRICTION_AUDIT_API_PORT", "8143"))
DRY_RUN = bool(os.environ.get("FRICTION_AUDIT_API_DRY_RUN"))
API_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

# selfdef-owned verdict ring (this box only reads it; selfdef writes it).
RING_DIR = Path(os.environ.get("FRICTION_AUDIT_RING_DIR", "/var/cache/selfdef/friction-audit/ring"))
# The 6 gates the crate renders, in fixed order.
GATES = ("pcie", "zfs", "memory", "immutability", "signature", "timeout")

METRICS_DIR = os.environ.get("SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector")
METRIC_NAME = "sovereign_os_operator_friction_audit_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "FRICTION_AUDIT_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-26-friction-audit" / "index.html"),
))


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-friction-audit-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def snapshot() -> dict:
    """Build the friction-audit Panel the crate consumes. Reads selfdef's ring when
    present; otherwise an empty (honest-deferred) Panel. Entries are keyed exactly
    how the crate looks them up: serde_json::to_string(gate) — i.e. the QUOTED gate
    token (`"pcie"`). Never fabricates a verdict."""
    entries: dict[str, dict] = {}
    if RING_DIR.is_dir():
        for f in sorted(RING_DIR.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            gate = rec.get("gate")
            if gate not in GATES:
                continue
            # only keep well-formed entries; never invent a status
            if rec.get("status") not in ("pass", "fail", "skip", "override"):
                continue
            entries[json.dumps(gate)] = {
                "gate": gate,
                "status": rec["status"],
                "ts_ms": int(rec.get("ts_ms", 0)),
                "hostname": str(rec.get("hostname", "")),
            }
    return {
        "schema_version": SCHEMA_VERSION,
        "now_ms": int(time.time() * 1000),
        "entries": entries,
        "ring_present": RING_DIR.is_dir(),
        "note": None if entries else "selfdef friction-audit ring absent/empty — every gate renders Gray '—' (honest-deferred)",
    }


def _version_payload() -> dict:
    return {
        "service": "friction-audit-api",
        "version": API_VERSION,
        "module": "d-26-friction-audit",
        "catalog_source": "M060 friction-audit boot-time gate + sovereign-cockpit-friction-audit-panel",
        "ring_dir": str(RING_DIR),
        "ring_present": RING_DIR.is_dir(),
        "gates": list(GATES),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "api", "webapp", "service"],
        "standing_rule": "selfdef owns the authority; the cockpit renders, never fabricates.",
    }


class FrictionAuditAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-friction-audit-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "friction-audit-api")
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
        self.send_header("X-Sovereign-Module", "d-26-friction-audit-webapp")
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
            if path == "/api/d-26/snapshot":
                self._send_json(200, snapshot())
                _emit_metric("snapshot", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/d-26/snapshot", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — selfdef writes the friction-audit verdict ring; "
                     "the cockpit only renders it",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] friction-audit-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), FrictionAuditAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="friction-audit read-only API + webapp host")
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
