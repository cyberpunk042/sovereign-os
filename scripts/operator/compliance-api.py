#!/usr/bin/env python3
"""
scripts/operator/compliance-api.py — Read-only HTTP API + webapp for
the §1g/§1h compliance dashboard inspection surface (R521, E5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

This closes the compliance api:FUTURE + webapp:FUTURE waivers AND
replaces the prior service:not-applicable waiver with a REAL systemd-
managed read-only daemon — same pattern R510 (global-history),
R515 (trinity) and R518 (router) used to flip a previously-applicable
waiver into a shipped service. Third and final commit in the
compliance tier-3 surface-expansion arc (R519 TUI → R520 MCP → R521
API + webapp + service). Lands compliance as the SIXTH §1g module at
full 8-surface structural ceiling (after edge-firewall R506, network-
edge R509, global-history R512, trinity R515, router R518).

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1, port 8097 — sister to the
    R515 trinity-api port 8095 and the R518 router-api port 8096)
  - Read-only verbs only — compliance has mutation in exactly ONE
    place (the triple-gated `compliance snapshot` CLI verb that
    appends to the /var/lib/sovereign-os/compliance/snapshots.jsonl
    history journal). Per operator §17 sovereignty boundary, mutation
    stays CLI-only — this daemon NEVER appends to or rewrites the
    journal; it can only READ history entries that the operator has
    chosen to record.

Read-only endpoints (R521 v1):
  GET /version                     — service version + module identity
  GET /status                      — full §1g/§1h rollup (4 instruments
                                     + 5 selfdef cross-repo axes)
  GET /worst[?limit=N]             — top-N modules by composite gap
                                     (default 10, max 50)
  GET /history[?limit=N]           — recent compliance snapshots from
                                     the journal (default 10, max 100)
  GET /webapp/                     — R521 single-file monochrome SPA
                                     mirroring the read-only verbs
                                     (operator-§1g: zero external deps)
  GET /healthz                     — API daemon liveness (always 200)

Layer-B metric (sister to the R519 + R520 compliance surfaces):

  sovereign_os_operator_compliance_api_request_total{endpoint,result}

Env vars (all overridable):
  COMPLIANCE_API_BIND            (default: 127.0.0.1)
  COMPLIANCE_API_PORT            (default: 8097)
  COMPLIANCE_WEBAPP_PATH         (default: <repo>/webapp/compliance/index.html)
  SOVEREIGN_OS_METRICS_DIR       (default: /var/lib/node_exporter/textfile_collector)
  COMPLIANCE_API_DRY_RUN         (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("COMPLIANCE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("COMPLIANCE_API_PORT", "8097"))
DRY_RUN = bool(os.environ.get("COMPLIANCE_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_compliance_api_request_total
#   compliance read-only REST API request count (endpoint, result).
# TYPE sovereign_os_operator_compliance_api_request_total counter
METRIC_NAME = "sovereign_os_operator_compliance_api_request_total"

API_VERSION = "1.0.0-R521"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "compliance" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "COMPLIANCE_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# Importlib-load compliance.py (R458 aggregator) directly — same data
# model the CLI + TUI + MCP surfaces serve. No drift.
_COMPLIANCE_PATH = _REPO_ROOT / "scripts" / "operator" / "compliance.py"
_spec = importlib.util.spec_from_file_location(
    "_compliance_core", _COMPLIANCE_PATH
)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load compliance.py from "
        f"{_COMPLIANCE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)


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
            METRICS_DIR, "sovereign-os-compliance-api.prom"
        )
        line = (
            f"{METRIC_NAME}{{endpoint=\"{endpoint}\","
            f"result=\"{result}\"}} 1\n"
        )
        with open(prom_path, "a") as f:
            f.write(line)
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "module": "compliance-api",
        "version": API_VERSION,
        "shipped_in": (
            "R521 (E5++ read-only REST API + webapp + systemd service)"
        ),
        "source": "scripts/operator/compliance-api.py",
        "data_source": str(_COMPLIANCE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "verbs": ["status", "worst", "history"],
        "spec_ref": "R458",
        "standing_rule": "We do not minimize anything.",
    }


def _status_payload() -> dict:
    return _core.collect_status()


def _worst_payload(limit: int) -> dict:
    status = _core.collect_status()
    ranked = _core.compute_worst(status)
    capped = ranked[:limit]
    return {
        "worst": capped,
        "count": len(capped),
        "ranked_total": len(ranked),
        "limit": limit,
    }


def _history_payload(limit: int) -> dict:
    """Read-only journal read. Same shape as cmd_history. The daemon
    NEVER writes to this file — operator §17 boundary preserved."""
    path = _core.SNAPSHOT_PATH
    snapshots: list[dict] = []
    if path.is_file():
        try:
            for line in path.read_text(
                encoding="utf-8"
            ).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    snapshots.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
    capped = snapshots[-limit:]
    return {
        "history": capped,
        "count": len(capped),
        "total_journaled": len(snapshots),
        "path": str(path),
        "limit": limit,
    }


def _parse_limit(query: str, default: int, ceiling: int) -> int:
    qs = urllib.parse.parse_qs(query)
    raw = qs.get("limit", [str(default)])[0]
    try:
        n = int(raw)
    except ValueError:
        n = default
    if n < 1:
        n = 1
    if n > ceiling:
        n = ceiling
    return n


class ComplianceAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-compliance-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "compliance-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        try:
            body = WEBAPP_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {
                "error": f"webapp asset unreadable: {e}",
                "webapp_path": str(WEBAPP_PATH),
            })
            _emit_metric("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "compliance-webapp")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/healthz" or path == "/":
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
            if path == "/status":
                self._send_json(200, _status_payload())
                _emit_metric("status", "ok")
                return
            if path == "/worst":
                limit = _parse_limit(parsed.query, default=10, ceiling=50)
                self._send_json(200, _worst_payload(limit))
                _emit_metric("worst", "ok")
                return
            if path == "/history":
                limit = _parse_limit(parsed.query, default=10, ceiling=100)
                self._send_json(200, _history_payload(limit))
                _emit_metric("history", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(
                path.lstrip("/").replace("-", "_").replace("/", "_")
                or "unknown",
                "500",
            )
            return

        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/version", "/status", "/worst", "/history",
                          "/webapp/", "/healthz"],
        })
        _emit_metric(
            path.lstrip("/").replace("-", "_").replace("/", "_")
            or "unknown",
            "404",
        )

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self):    self._reject_mutation()  # noqa: E704 N802
    def do_PUT(self):     self._reject_mutation()  # noqa: E704 N802
    def do_DELETE(self):  self._reject_mutation()  # noqa: E704 N802
    def do_PATCH(self):   self._reject_mutation()  # noqa: E704 N802

    def _reject_mutation(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — compliance inspection is "
                     "read-only at every surface (operator §17 "
                     "sovereignty boundary). The triple-gated "
                     "`compliance snapshot` CLI verb is the ONLY "
                     "mutation in the compliance module, and it "
                     "remains CLI-only by design — it writes to "
                     "/var/lib/sovereign-os/compliance/snapshots.jsonl, "
                     "served back (read-only) via GET /history. The "
                     "API daemon NEVER appends to or rewrites the "
                     "journal.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] compliance-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_COMPLIANCE_PATH}", flush=True)
    print(f"  endpoints:   /version /status /worst /history /webapp/ "
          f"+ /healthz", flush=True)
    print(f"  webapp:      {WEBAPP_PATH}", flush=True)
    if bind != "127.0.0.1":
        print(
            f"  WARNING: bind={bind!r} is NOT loopback — operator "
            f"explicitly exposed this surface beyond the host.",
            flush=True,
        )
    if DRY_RUN:
        print("  DRY-RUN: configuration validated, not serving.",
              flush=True)
        return 0

    try:
        httpd = HTTPServer((bind, port), ComplianceAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] compliance-api shutdown requested.", flush=True)
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
