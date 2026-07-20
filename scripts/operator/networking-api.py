#!/usr/bin/env python3
"""
scripts/operator/networking-api.py — Unified read-only HTTP API for the
networking triplet: network-edge (R507), edge-firewall (R504), and
D-12 networking rules-mirror (R10113).

Replaces three separate API daemons with one unified surface while preserving
all endpoint contracts. Each concern keeps its own endpoint namespace so the
panels fetch from the same origin without cross-concern collision.

Backward-compatible root paths (preserved from the individual daemons):
  GET /detect, /interfaces, /nat-chain, /opnsense/status, /opnsense/capabilities
  GET /state, /candidates, /recommend, /install-plan
  GET /api/d-12/snapshot, /api/d-12/stream
  GET /version | /healthz | /control-systems

Namespaced paths (new, for unified consumers):
  GET /network-edge/version, /network-edge/detect, /network-edge/interfaces, ...
  GET /edge-firewall/version, /edge-firewall/state, /edge-firewall/candidates, ...
  GET /api/d-12/snapshot, /api/d-12/stream

Webapp paths:
  GET /webapp/network-edge/        network-edge panel
  GET /webapp/edge-firewall/       edge-firewall panel
  GET /webapp/d-12-networking/     D-12 networking panel
  GET /webapp/                     unified landing page
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

API_BIND = os.environ.get("NETWORKING_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("NETWORKING_API_PORT", "8139"))
DRY_RUN = bool(os.environ.get("NETWORKING_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("NETWORKING_API_STREAM_INTERVAL", "5.0"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

METRIC_NAME = "sovereign_os_operator_networking_api_request_total"
API_VERSION = "1.0.0-unified"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_THIS_DIR = Path(__file__).resolve().parent

# ── Import the three backing cores ──
_NE_PATH = _THIS_DIR / "network-topology.py"
_EF_PATH = _THIS_DIR / "edge-firewall.py"
_RM_PATH = _REPO_ROOT / "scripts" / "mirror" / "selfdef-rules-mirror.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        sys.stderr.write(f"[FATAL] cannot load {path}\n")
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ne = _load_module("_ne_core", _NE_PATH)
_ef = _load_module("_ef_core", _EF_PATH)
_rm = _load_module("_rm_core", _RM_PATH)

# ── Webapp paths ──
_WEBAPP_PATHS = {
    "/webapp/network-edge": _REPO_ROOT / "webapp" / "network-edge" / "index.html",
    "/webapp/edge-firewall": _REPO_ROOT / "webapp" / "edge-firewall" / "index.html",
    "/webapp/d-12-networking": _REPO_ROOT / "webapp" / "d-12-networking" / "index.html",
}

# ── Metrics ──
def _emit(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-networking-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


# ── Payload builders ──
def _ne_version() -> dict:
    return {
        "module": "network-edge-api",
        "version": "1.1.0-R509",
        "shipped_in": "R507+R509 via unified networking-api",
        "source": "scripts/operator/networking-api.py",
        "data_source": str(_NE_PATH),
        "surfaces": ["core", "cli", "tui", "dashboard", "api", "service", "mcp", "webapp"],
        "standing_rule": "We do not minimize anything.",
    }


def _ef_version() -> dict:
    return {
        "module": "edge-firewall-api",
        "version": "1.1.0-R506",
        "shipped_in": "R504+R506 via unified networking-api",
        "source": "scripts/operator/networking-api.py",
        "data_source": str(_EF_PATH),
        "surfaces": ["core", "cli", "tui", "dashboard", "api", "service", "mcp", "webapp"],
        "standing_rule": "We do not minimize anything.",
    }


def _rm_version() -> dict:
    return {
        "service": "rules-mirror-api",
        "version": "1.0.0",
        "module": "d-12-networking",
        "core": str(_RM_PATH),
        "mirror_artifact": str(_rm.RULES_MIRROR),
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


def _unified_version() -> dict:
    return {
        "module": "networking-api",
        "version": API_VERSION,
        "components": {
            "network-edge": _ne_version(),
            "edge-firewall": _ef_version(),
            "rules-mirror": _rm_version(),
        },
        "standing_rule": "We do not minimize anything.",
    }


# Optional shared control-systems loader
try:
    _CS_PATH = _REPO_ROOT / "config" / "control-systems.yaml"

    def _load_control_systems():
        import yaml  # noqa: PLC0415
        if not _CS_PATH.is_file():
            return None
        return yaml.safe_load(_CS_PATH.read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    def _load_control_systems():
        return None


# ── Handler ──
class NetworkingAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-networking-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "networking-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self, path: str) -> None:
        webapp_path = _WEBAPP_PATHS.get(path)
        if webapp_path is None:
            self._send_json(404, {"error": f"unknown webapp path: {path!r}"})
            _emit("webapp", "404")
            return
        try:
            data = webapp_path.read_bytes()
        except OSError as e:
            self._send_json(500, {"error": f"webapp asset unreadable: {e}",
                                  "expected_path": str(webapp_path)})
            _emit("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Sovereign-Module", "networking-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(data)
        _emit("webapp", "ok")

    def _send_landing(self) -> None:
        body = (
            "<!DOCTYPE html><html><head><meta charset=utf-8><title>Networking</title>"
            "<style>body{font-family:system-ui;background:#0a0a0a;color:#eee;padding:2rem}"
            "a{color:#9bd1ff}</style></head><body>"
            "<h1>sovereign-os networking</h1><ul>"
            '<li><a href="/webapp/network-edge/">Network Edge</a></li>'
            '<li><a href="/webapp/edge-firewall/">Edge Firewall</a></li>'
            '<li><a href="/webapp/d-12-networking/">D-12 Networking</a></li>'
            "</ul></body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        _emit("webapp", "ok")

    def _send_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "networking-api")
        self.end_headers()
        _emit("stream", "open")
        try:
            while True:
                payload = json.dumps(_rm.snapshot())
                self.wfile.write(f"event: snapshot\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(STREAM_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/healthz"):
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit("healthz", "ok")
            return

        if path == "/version":
            self._send_json(200, _unified_version())
            _emit("version", "ok")
            return

        if path in ("/control-systems", "/control-systems.json"):
            cs = _load_control_systems()
            self._send_json(200, cs if cs is not None else {"systems": []})
            _emit("control-systems", "ok")
            return

        if path == "/webapp":
            self._send_landing()
            return

        if path in _WEBAPP_PATHS:
            self._send_webapp(path)
            return

        if path == "/api/d-12/stream":
            self._send_stream()
            return

        try:
            # ── network-edge (backward-compatible root + namespaced) ──
            if path in ("/detect", "/network-edge/detect"):
                self._send_json(200, {
                    "interfaces_count": len(_ne.detect_interfaces()),
                    "interfaces": _ne.detect_interfaces(),
                    "default_gateway": _ne.detect_default_gateway(),
                    "nat_chain": _ne.detect_nat_chain(),
                    "vpn_bridge": _ne.detect_vpn_bridge(),
                    "opnsense": _ne.detect_opnsense_state(),
                    "capabilities": _ne.detect_capabilities(),
                    "operator_named_edge_hardware": _ne.OPERATOR_NAMED_EDGE_HARDWARE,
                })
                _emit("ne_detect", "ok")
                return
            if path in ("/interfaces", "/network-edge/interfaces"):
                ifaces = _ne.detect_interfaces()
                self._send_json(200, {"count": len(ifaces), "interfaces": ifaces})
                _emit("ne_interfaces", "ok")
                return
            if path in ("/nat-chain", "/network-edge/nat-chain"):
                self._send_json(200, _ne.detect_nat_chain())
                _emit("ne_nat_chain", "ok")
                return
            if path in ("/opnsense/status", "/network-edge/opnsense/status"):
                self._send_json(200, _ne.detect_opnsense_state())
                _emit("ne_opnsense_status", "ok")
                return
            if path in ("/opnsense/capabilities", "/network-edge/opnsense/capabilities"):
                self._send_json(200, _ne.detect_capabilities())
                _emit("ne_opnsense_capabilities", "ok")
                return
            if path == "/network-edge/version":
                self._send_json(200, _ne_version())
                _emit("ne_version", "ok")
                return

            # ── edge-firewall (backward-compatible root + namespaced) ──
            if path in ("/state", "/edge-firewall/state"):
                self._send_json(200, {"local": _ef.detect_local_state(),
                                      "upstream": _ef.detect_upstream_state()})
                _emit("ef_state", "ok")
                return
            if path in ("/candidates", "/edge-firewall/candidates"):
                self._send_json(200, {"count": len(_ef.CANDIDATES),
                                      "candidates": _ef.CANDIDATES,
                                      "known_candidate_ids": _ef.KNOWN_CANDIDATE_IDS})
                _emit("ef_candidates", "ok")
                return
            if path in ("/recommend", "/edge-firewall/recommend"):
                local = _ef.detect_local_state()
                upstream = _ef.detect_upstream_state()
                recs = _ef.recommend_for_state(local, upstream)
                self._send_json(200, {"upstream_tier": upstream.get("tier", "unknown"),
                                        "count": len(recs), "recommendations": recs})
                _emit("ef_recommend", "ok")
                return
            if path in ("/install-plan", "/edge-firewall/install-plan"):
                cid = (query.get("candidate") or [""])[0]
                if not cid:
                    self._send_json(400, {"error": "missing required query param: candidate",
                                          "known": _ef.KNOWN_CANDIDATE_IDS})
                    _emit("ef_install_plan", "400")
                    return
                cand = _ef._candidate(cid)
                if cand is None:
                    self._send_json(404, {"error": f"unknown candidate: {cid!r}",
                                          "known": _ef.KNOWN_CANDIDATE_IDS})
                    _emit("ef_install_plan", "404")
                    return
                plan = {
                    "candidate": cand["id"],
                    "label": cand["label"],
                    "perf_cost_disclosed": cand["perf_cost"],
                    "apt_packages": cand["apt_packages"],
                    "systemd_units": cand["systemd_units"],
                    "config_paths_touched": cand["config_paths"],
                    "install_steps": [
                        "apt-get update",
                        f"apt-get install -y {' '.join(cand['apt_packages'])}",
                        *[f"systemctl enable {u}" for u in cand["systemd_units"]],
                        *[f"systemctl start {u}" for u in cand["systemd_units"]],
                    ],
                    "rollback_steps": [
                        *[f"systemctl stop {u}" for u in cand["systemd_units"]],
                        *[f"systemctl disable {u}" for u in cand["systemd_units"]],
                        f"apt-get remove -y {' '.join(cand['apt_packages'])}",
                    ],
                    "next_action": (
                        f"Run via CLI: sovereign-osctl edge-firewall install "
                        f"{cand['id']} --apply --confirm-install"
                    ),
                    "wire_contract": (
                        "This is a PLAN — read-only. Actual mutation requires "
                        "the CLI `install` verb with --apply --confirm-install "
                        "(operator §17 sovereignty boundary)."
                    ),
                }
                self._send_json(200, plan)
                _emit("ef_install_plan", "ok")
                return
            if path == "/edge-firewall/version":
                self._send_json(200, _ef_version())
                _emit("ef_version", "ok")
                return

            # ── rules-mirror (unchanged paths) ──
            if path == "/api/d-12/snapshot":
                self._send_json(200, _rm.snapshot())
                _emit("rm_snapshot", "ok")
                return

        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit(path.lstrip("/").replace("/", "_") or "unknown", "500")
            return

        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": [
                "/version", "/healthz", "/control-systems",
                "/detect", "/interfaces", "/nat-chain",
                "/opnsense/status", "/opnsense/capabilities",
                "/state", "/candidates", "/recommend", "/install-plan",
                "/api/d-12/snapshot", "/api/d-12/stream",
                "/network-edge/version", "/network-edge/detect",
                "/network-edge/interfaces", "/network-edge/nat-chain",
                "/network-edge/opnsense/status", "/network-edge/opnsense/capabilities",
                "/edge-firewall/version", "/edge-firewall/state",
                "/edge-firewall/candidates", "/edge-firewall/recommend",
                "/edge-firewall/install-plan",
                "/webapp/network-edge/", "/webapp/edge-firewall/",
                "/webapp/d-12-networking/", "/webapp/",
            ],
        })
        _emit(path.lstrip("/").replace("/", "_") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only unified networking surface — mutation verbs stay "
                     "CLI-only (operator §17 sovereignty boundary).",
            "allowed": ["GET", "HEAD"],
        })
        _emit(self.command.lower(), "405")

    def do_POST(self):    self._reject()   # noqa: E704 N802
    def do_PUT(self):     self._reject()   # noqa: E704 N802
    def do_DELETE(self):  self._reject()   # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] networking-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    if bind != "127.0.0.1":
        print(f"  WARNING: bind={bind!r} is NOT loopback", flush=True)
    if DRY_RUN:
        print("  DRY-RUN: configuration validated.", flush=True)
        return 0
    httpd = ThreadingHTTPServer((bind, port), NetworkingAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutdown", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Unified networking read-only API")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    args = p.parse_args(argv)
    if DRY_RUN:
        print("DRY-RUN: validated.")
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
