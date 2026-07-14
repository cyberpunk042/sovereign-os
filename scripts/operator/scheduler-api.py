#!/usr/bin/env python3
"""scripts/operator/scheduler-api.py — read-only HTTP API + webapp host for the D-29
scheduler cockpit dashboard (selfdef IPS Goldilocks Scheduler).

The panel renders its table with the REAL sovereign-cockpit-scheduler-panel crate in-browser
(wasm); this daemon only supplies the Panel snapshot it consumes.

HONESTY RULE (cross-repo, sacrosanct): selfdef owns the authority. selfdef runs the Goldilocks
Scheduler and writes its decision ring at /var/cache/selfdef/scheduler/ring (+ the audit log at
/mnt/vault/context/scheduler_audit.log); sovereign-os only renders it. So this API reads that ring
if present, and otherwise returns an EMPTY, honest-deferred Panel (the crate still renders the six
backpressure surfaces). It NEVER fabricates a routing decision.

Endpoints:
  GET /api/d-29/snapshot     the scheduler Panel {schema_version, recent_decisions, audit_log_present, now_ms}
  GET /webapp/ | /webapp/index.html   the D-29 dashboard
  GET /version | /healthz | /

Env:
  SCHEDULER_API_BIND (default 127.0.0.1) · SCHEDULER_API_PORT (default 8146)
  SCHEDULER_API_DRY_RUN · SCHEDULER_WEBAPP_PATH · SCHEDULER_RING_DIR · SCHEDULER_AUDIT_LOG
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

API_BIND = os.environ.get("SCHEDULER_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("SCHEDULER_API_PORT", "8146"))
DRY_RUN = bool(os.environ.get("SCHEDULER_API_DRY_RUN"))
API_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

RING_DIR = Path(os.environ.get("SCHEDULER_RING_DIR", "/var/cache/selfdef/scheduler/ring"))
AUDIT_LOG = Path(os.environ.get("SCHEDULER_AUDIT_LOG", "/mnt/vault/context/scheduler_audit.log"))
_PROFILES = ("fast", "careful", "private", "autonomous", "experimental", "production")
_ROUTES = ("blackwell", "rtx4090", "cpu", "hybrid", "hibernate")
_AXES = ("latency", "cost", "risk", "energy", "human_attention", "hardware_pressure", "compound")
_BP = ("blackwell_vram_high", "gpu3090_busy", "cpu_pressure", "ram_pressure", "io_pressure", "human_gate_queue_high")

METRICS_DIR = os.environ.get("SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector")
METRIC_NAME = "sovereign_os_operator_scheduler_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "SCHEDULER_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-29-scheduler" / "index.html"),
))


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-scheduler-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def snapshot() -> dict:
    """Build the scheduler Panel the crate consumes. Reads selfdef's decision ring when present
    (newest-first, capped at 16); otherwise empty (honest-deferred). Only well-formed decisions —
    a complete 7-axis score + 6-field backpressure — are kept. Never fabricates a route."""
    decisions: list[dict] = []
    if RING_DIR.is_dir():
        recs = []
        for f in sorted(RING_DIR.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            ax, bp = rec.get("axis_scores"), rec.get("backpressure")
            if rec.get("profile") not in _PROFILES or rec.get("route") not in _ROUTES:
                continue
            if not (isinstance(ax, dict) and all(k in ax for k in _AXES)):
                continue
            if not (isinstance(bp, dict) and all(k in bp for k in _BP)):
                continue
            recs.append({
                "request_id": str(rec.get("request_id", "")),
                "profile": rec["profile"],
                "route": rec["route"],
                "axis_scores": {k: float(ax[k]) for k in _AXES},
                "backpressure": {k: bool(bp[k]) for k in _BP},
                "ts_ms": int(rec.get("ts_ms", 0)),
                "hostname": str(rec.get("hostname", "")),
                "override_signer_kid": rec.get("override_signer_kid"),
            })
        recs.sort(key=lambda e: e["ts_ms"], reverse=True)
        decisions = recs[:16]
    return {
        "schema_version": SCHEMA_VERSION,
        "now_ms": int(time.time() * 1000),
        "audit_log_present": AUDIT_LOG.exists(),
        "recent_decisions": decisions,
        "ring_present": RING_DIR.is_dir(),
        "note": None if decisions else "selfdef scheduler ring absent/empty — the 6 backpressure surfaces still render (honest-deferred); no route is fabricated",
    }


def _version_payload() -> dict:
    return {
        "service": "scheduler-api",
        "version": API_VERSION,
        "module": "d-29-scheduler",
        "catalog_source": "selfdef IPS Goldilocks Scheduler + sovereign-cockpit-scheduler-panel",
        "ring_dir": str(RING_DIR),
        "ring_present": RING_DIR.is_dir(),
        "audit_log": str(AUDIT_LOG),
        "audit_log_present": AUDIT_LOG.exists(),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "api", "webapp", "service"],
        "standing_rule": "selfdef owns the authority; the cockpit renders, never fabricates.",
    }


class SchedulerAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-scheduler-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "scheduler-api")
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
        self.send_header("X-Sovereign-Module", "d-29-scheduler-webapp")
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
            if path == "/api/d-29/snapshot":
                self._send_json(200, snapshot())
                _emit_metric("snapshot", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/d-29/snapshot", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — selfdef runs the Goldilocks Scheduler and writes its "
                     "decision ring; the cockpit only renders it",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] scheduler-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), SchedulerAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="scheduler read-only API + webapp host")
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
