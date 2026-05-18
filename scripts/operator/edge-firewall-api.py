#!/usr/bin/env python3
"""
scripts/operator/edge-firewall-api.py — Read-only HTTP API for the
edge-firewall workstation-side enforcement-candidate registry
(R504, E11.M9++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

This ships the `api` surface of the §1g 8-surface delivery ladder for
the `edge-firewall` module. The CLI (`sovereign-osctl edge-firewall
<verb>`) already covers ad-hoc operator queries; this API surface gives
OTHER consumers (the upcoming MCP server, the upcoming webapp tier-3
shell, automation scripts, monitoring) a stable wire contract.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1)
  - Read-only verbs only (mutation `install` + interactive `wizard`
    stay CLI-only — operator §17 sacrosanct sovereignty boundary)

Read-only endpoints (R504 v1, R506 webapp):
  GET /version                     — service version + module identity
  GET /state                       — local + upstream firewall state
  GET /candidates                  — CANDIDATES registry (5 options)
  GET /recommend                   — recommendations for current state
  GET /install-plan?candidate=<id> — install plan for a named candidate
  GET /healthz                     — API daemon liveness (always 200)
  GET /webapp/                     — single-file operator-§1g webapp (R506)
  GET /webapp/index.html           — alias for /webapp/

Layer-B metric (sister to the CLI's `_query_total{verb,candidate,result}`):

  sovereign_os_operator_edge_firewall_api_request_total{endpoint,result}

Env vars (all overridable):
  EDGE_FIREWALL_API_BIND          (default: 127.0.0.1)
  EDGE_FIREWALL_API_PORT          (default: 8092)
  SOVEREIGN_OS_METRICS_DIR        (default: /var/lib/node_exporter/textfile_collector)
  EDGE_FIREWALL_API_DRY_RUN       (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("EDGE_FIREWALL_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("EDGE_FIREWALL_API_PORT", "8092"))
DRY_RUN = bool(os.environ.get("EDGE_FIREWALL_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_edge_firewall_api_request_total edge-firewall
#   read-only REST API request count (endpoint, result).
# TYPE sovereign_os_operator_edge_firewall_api_request_total counter
METRIC_NAME = "sovereign_os_operator_edge_firewall_api_request_total"

API_VERSION = "1.1.0-R506"

# R506 webapp surface — single-file monochrome SPA shipped under
# webapp/edge-firewall/index.html in the repo. Operator can override
# the on-disk path via env (e.g., post-install relocation to
# /usr/share).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "edge-firewall" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "EDGE_FIREWALL_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# edge-firewall CLI module — import directly so the API serves from
# the SAME data model the operator-facing CLI uses (no drift).
_THIS_DIR = Path(__file__).resolve().parent
_EF_PATH = _THIS_DIR / "edge-firewall.py"
_spec = importlib.util.spec_from_file_location("_ef_core", _EF_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load edge-firewall.py "
        f"from {_EF_PATH}\n"
    )
    sys.exit(1)
_ef = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ef)


def _emit_metric(endpoint: str, result: str) -> None:
    """Best-effort textfile-collector emit (Layer B per SDD-016)."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {METRIC_NAME}"
            f"{{endpoint=\"{endpoint}\",result=\"{result}\"}} 1\n"
        )
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom_path = os.path.join(
            METRICS_DIR, "sovereign-os-edge-firewall-api.prom"
        )
        line = (
            f"{METRIC_NAME}{{endpoint=\"{endpoint}\","
            f"result=\"{result}\"}} 1\n"
        )
        with open(prom_path, "a") as f:
            f.write(line)
    except OSError:
        pass


def _state_payload() -> dict:
    return {
        "local": _ef.detect_local_state(),
        "upstream": _ef.detect_upstream_state(),
    }


def _candidates_payload() -> dict:
    return {
        "count": len(_ef.CANDIDATES),
        "candidates": _ef.CANDIDATES,
        "known_candidate_ids": _ef.KNOWN_CANDIDATE_IDS,
    }


def _recommend_payload() -> dict:
    local = _ef.detect_local_state()
    upstream = _ef.detect_upstream_state()
    recs = _ef.recommend_for_state(local, upstream)
    return {
        "upstream_tier": upstream.get("tier", "unknown"),
        "count": len(recs),
        "recommendations": recs,
    }


def _install_plan_payload(candidate_id: str) -> tuple[int, dict]:
    if not candidate_id:
        return 400, {
            "error": "missing required query param: candidate",
            "known": _ef.KNOWN_CANDIDATE_IDS,
        }
    cand = _ef._candidate(candidate_id)
    if cand is None:
        return 404, {
            "error": f"unknown candidate: {candidate_id!r}",
            "known": _ef.KNOWN_CANDIDATE_IDS,
        }
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
    return 200, plan


def _version_payload() -> dict:
    return {
        "module": "edge-firewall-api",
        "version": API_VERSION,
        "shipped_in": "R504 (E11.M9++) + R505 (E11.M9++ MCP surface) + R506 (E11.M9++ webapp surface)",
        "source": "scripts/operator/edge-firewall-api.py",
        "data_source": str(_EF_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "tui", "dashboard", "api", "service",
                     "mcp", "webapp"],
        "standing_rule": "We do not minimize anything.",
    }


class EdgeFirewallAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-edge-firewall-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write(
            f"[api] {self.address_string()} {format % args}\n"
        )

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "edge-firewall-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        """R506 — serve the single-file monochrome webapp from disk.
        Read-only; same-origin with the JSON endpoints (no CORS dance,
        no CDN, no cross-origin script loads — operator-§1g UX rule)."""
        try:
            body = WEBAPP_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {
                "error": f"webapp asset unreadable: {e}",
                "expected_path": str(WEBAPP_PATH),
            })
            _emit_metric("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "edge-firewall-webapp")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/healthz" or path == "/":
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return

        if path in ("/webapp", "/webapp/", "/webapp/index.html"):
            self._send_webapp()
            return

        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/state":
                self._send_json(200, _state_payload())
                _emit_metric("state", "ok")
                return
            if path == "/candidates":
                self._send_json(200, _candidates_payload())
                _emit_metric("candidates", "ok")
                return
            if path == "/recommend":
                self._send_json(200, _recommend_payload())
                _emit_metric("recommend", "ok")
                return
            if path == "/install-plan":
                cid = (query.get("candidate") or [""])[0]
                status, payload = _install_plan_payload(cid)
                self._send_json(status, payload)
                _emit_metric(
                    "install_plan",
                    "ok" if status == 200
                    else ("400" if status == 400 else "404"),
                )
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/").replace("-", "_") or "unknown",
                         "500")
            return

        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/version", "/state", "/candidates",
                          "/recommend", "/install-plan", "/healthz",
                          "/webapp/"],
        })
        _emit_metric(path.lstrip("/").replace("-", "_") or "unknown",
                     "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self):    self._reject_mutation()  # noqa: E704 N802
    def do_PUT(self):     self._reject_mutation()  # noqa: E704 N802
    def do_DELETE(self):  self._reject_mutation()  # noqa: E704 N802
    def do_PATCH(self):   self._reject_mutation()  # noqa: E704 N802

    def _reject_mutation(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — mutation verbs `install` and "
                     "interactive `wizard` stay CLI-only (operator §17 "
                     "sovereignty boundary). Use sovereign-osctl "
                     "edge-firewall install/wizard.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] edge-firewall-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_EF_PATH}", flush=True)
    print(f"  endpoints:   /version /state /candidates /recommend "
          f"/install-plan + /healthz", flush=True)
    if bind != "127.0.0.1":
        print(
            f"  WARNING: bind={bind!r} is NOT loopback — operator "
            f"explicitly exposed this surface beyond the host.",
            flush=True,
        )
    if DRY_RUN:
        print("  DRY-RUN: configuration validated, not serving.", flush=True)
        return 0

    try:
        httpd = HTTPServer((bind, port), EdgeFirewallAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — {e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] edge-firewall-api shutdown requested.", flush=True)
        httpd.server_close()
        return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "dry-run":
        global DRY_RUN  # noqa: PLW0603
        DRY_RUN = True
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    return serve()


if __name__ == "__main__":
    sys.exit(main())
