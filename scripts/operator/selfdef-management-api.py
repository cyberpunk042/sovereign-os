#!/usr/bin/env python3
"""scripts/operator/selfdef-management-api.py — read-only HTTP API + webapp
host for the D-25 "selfdef management" cockpit dashboard.

CROSS-REPO CONSUMER (R10212 — the load-bearing constraint). sovereign-os is
the CONSUMER; selfdef is the PRODUCER (the IPS). This panel READS selfdef
state and NEVER writes it: it reuses the already-sanctioned M060 consumer
proxy (scripts/operator/m060-health.py `probe()` — UNIX socket
$SELFDEF_SOCKET → TCP $SELFDEF_API_URL+$SELFDEF_API_TOKEN, graceful
`unreachable` envelope) and adds NO new selfdef access path. The selfdef
on/off lifecycle stays a signed CLI verb (`sovereign-osctl selfdef {on|off}`,
already the SDD-045 control-surface `selfdef` control scoped to this panel) —
clipboard-copy only, never an HTTP mutation.

Flips the dashboard-catalog `selfdef-management` planned surface to live. It
is the management OVERVIEW of the IPS (reachability + M060 mirror-chain
health + pointers to the per-domain mirror panels D-13..D-18); the per-domain
detail lives in those panels.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."

Endpoints (the exact contract webapp/d-25-selfdef-management/index.html fetches):
  GET /api/selfdef-management/state   derived selfdef state + M060 chain health
  GET /api/selfdef-management/stream   Server-Sent Events (state-change)
  GET /control-systems                 SDD-045 control registry (for the on/off control)
  GET /webapp/ | /webapp/index.html    the D-25 single-file dashboard
  GET /version | /healthz | /

Env: SELFDEF_MGMT_API_BIND / _PORT (default 127.0.0.1 / 8125),
     SELFDEF_MGMT_API_DRY_RUN, SELFDEF_MGMT_WEBAPP_PATH,
     SELFDEF_MGMT_STREAM_INTERVAL (default 15.0),
     SELFDEF_SOCKET / SELFDEF_API_URL / SELFDEF_API_TOKEN (selfdef-side, read-only).
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
from typing import Any

API_BIND = os.environ.get("SELFDEF_MGMT_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("SELFDEF_MGMT_API_PORT", "8125"))
DRY_RUN = bool(os.environ.get("SELFDEF_MGMT_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("SELFDEF_MGMT_STREAM_INTERVAL", "15.0"))
API_VERSION = "1.0.0"
SHIPPED_IN = "D-25-selfdef-management"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_selfdef_management_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "SELFDEF_MGMT_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-25-selfdef-management" / "index.html"),
))

# Reuse the SANCTIONED M060 consumer proxy (READ-ONLY; socket+TCP fallback +
# graceful-unreachable envelope). No new selfdef access path is introduced.
_CORE_PATH = _REPO_ROOT / "scripts" / "operator" / "m060-health.py"
_spec = importlib.util.spec_from_file_location("_m060_health_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(f"[FATAL STRUCTURAL FRICTION] cannot load {_CORE_PATH}\n")
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

_CONTROL_SYSTEMS_FILE = _REPO_ROOT / "config" / "control-systems.yaml"

# The 6 per-domain mirror panels this overview points at (D-13..D-18).
MIRROR_PANELS = [
    {"slot": "D-13", "dir": "d-13-filesystem-grants", "label": "filesystem grants"},
    {"slot": "D-14", "dir": "d-14-capability-tokens", "label": "capability tokens"},
    {"slot": "D-15", "dir": "d-15-sandboxes", "label": "sandboxes"},
    {"slot": "D-16", "dir": "d-16-audit", "label": "audit chain"},
    {"slot": "D-17", "dir": "d-17-quarantine", "label": "quarantine"},
    {"slot": "D-18", "dir": "d-18-trust-scores", "label": "trust scores"},
]

# selfdef enablement/reachability derived from the M060 chain state (READ-ONLY —
# the consumer never asserts the producer's on/off; it reports what it observes).
_STATE_MEANING = {
    "online":      ("running",     "IPS reachable; all mirrors fresh + parseable"),
    "degraded":    ("running",     "IPS reachable; partial mirror population or a parse fault"),
    "stale":       ("running",     "IPS reachable but mirror loop is stuck/paused (>5m)"),
    "offline":     ("not-running", "no mirror artifacts — daemon down OR mirror dir unset"),
    "unreachable": ("unreachable", "cannot reach the selfdef daemon (socket + TCP both failed)"),
}


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-selfdef-management-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _load_control_systems():
    try:
        import yaml  # optional
    except ImportError:
        return None
    try:
        return yaml.safe_load(_CONTROL_SYSTEMS_FILE.read_text())
    except OSError:
        return None


def state_view() -> dict[str, Any]:
    """Derived selfdef management overview from the M060 chain probe (the
    sanctioned read-only consumer path). Never writes; degrades to
    `unreachable` when the selfdef daemon is absent (the dev/CI case)."""
    chain = _core.probe()
    st = chain.get("state", "unreachable")
    enablement, detail = _STATE_MEANING.get(st, ("unknown", "unrecognized chain state"))
    return {
        "schema_version": "1.0.0",
        "selfdef": {
            "enablement": enablement,     # running / not-running / unreachable / unknown
            "detail": detail,
            "chain_state": st,            # online/degraded/stale/offline/unreachable
            "on_off_cli": "sovereign-osctl selfdef {on|off}",   # signed CLI verb (copy-only)
            "status_cli": "sovereign-osctl selfdef status",
        },
        "m060_chain": {
            "state": st,
            "artifacts_present": chain.get("artifacts_present"),
            "artifacts_expected": chain.get("artifacts_expected"),
            "newest_age_seconds": chain.get("newest_age_seconds"),
            "mirror_dir": chain.get("mirror_dir"),
            "artifacts": chain.get("artifacts", []),
        },
        "mirror_panels": MIRROR_PANELS,
    }


def _version_payload() -> dict:
    return {
        "service": "selfdef-management-api",
        "version": API_VERSION,
        "module": "d-25-selfdef-management",
        "shipped_in": SHIPPED_IN,
        "catalog_source": "reuses scripts/operator/m060-health.py probe() "
                          "(READ-ONLY M060 consumer proxy — R10212)",
        "core": str(_CORE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class SelfdefMgmtAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-selfdef-management-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "selfdef-management-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        try:
            body = WEBAPP_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {"error": f"webapp asset unreadable: {e}"})
            _emit_metric("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "d-25-selfdef-management-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "selfdef-management-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                self.wfile.write(
                    f"event: state-change\ndata: {json.dumps(state_view())}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(STREAM_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

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
        if path == "/api/selfdef-management/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload()); _emit_metric("version", "ok"); return
            if path == "/api/selfdef-management/state":
                self._send_json(200, state_view()); _emit_metric("state", "ok"); return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/selfdef-management/state",
                          "/api/selfdef-management/stream", "/control-systems",
                          "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        # R10212: sovereign-os is the READ-ONLY consumer. selfdef mutation
        # (on/off/lifecycle) is a signed `sovereign-osctl selfdef` CLI verb on
        # the IPS side — NEVER an HTTP mutation from the cockpit.
        self._send_json(405, {
            "error": "read-only consumer — selfdef on/off/lifecycle are signed "
                     "`sovereign-osctl selfdef` CLI verbs on the IPS side (R10212)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] selfdef-management-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), SelfdefMgmtAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="selfdef-management read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one state view + exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(), "state": state_view()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
