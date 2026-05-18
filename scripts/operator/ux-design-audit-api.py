#!/usr/bin/env python3
"""
scripts/operator/ux-design-audit-api.py — Read-only HTTP API + webapp
for the §1g/§1h ux-design-audit inspection surface (R530, E5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

Per operator §1g verbatim (R457 anchor):

  "everything will also need to go through a thorough UX Design stage
  in order to be of quality"

Third and final commit in the ux-design-audit tier-3 surface-expansion
arc (R528 TUI → R529 MCP → R530 API + webapp + service). Drains the
ux-design-audit api:FUTURE + webapp:FUTURE waivers AND REPLACES the
prior service:not-applicable waiver with a REAL systemd-managed
read-only daemon — same pattern R510 (global-history) / R515
(trinity) / R518 (router) / R521 (compliance) / R524 (anti-min) /
R527 (doc-coverage) used to flip a previously-applicable waiver into
a shipped service. Lands ux-design-audit as the NINTH §1g module at
full 8-surface structural ceiling (after edge-firewall R506, network-
edge R509, global-history R512, trinity R515, router R518, compliance
R521, anti-min R524, doc-coverage R527).

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1, port 8100 — sister to the
    R515 trinity-api 8095 / R518 router-api 8096 / R521 compliance-
    api 8097 / R524 anti-min-api 8098 / R527 doc-coverage-api 8099)
  - Read-only verbs only — ux-design-audit has NO mutation verbs at
    any surface (audit is a query; remediation lives in the audited
    modules themselves). Operator §17 sovereignty boundary preserved.

Read-only endpoints (R530 v1):
  GET /version                        — service version + module identity
  GET /dimensions                     — list 6 R457 operator-named UX dimensions
  GET /modules                        — operator-facing modules audited
  GET /audit[?module=<m>]             — per-module per-dimension audit
  GET /score[?module=<m>]             — per-module X/6 score (sorted)
  GET /report[?threshold=N]           — modules below UX threshold
  GET /selfdef                        — R464 cross-repo selfdef
                                        UxChecklist discovery
  GET /webapp/                        — R530 single-file monochrome SPA
                                        mirroring the read-only verbs
                                        (operator-§1g: zero external deps)
  GET /healthz                        — API daemon liveness (always 200)

Layer-B metric (sister to R527 doc-coverage + R524 anti-min):

  sovereign_os_operator_ux_design_audit_api_request_total{endpoint,result}

Env vars (all overridable):
  UX_DESIGN_AUDIT_API_BIND     (default: 127.0.0.1)
  UX_DESIGN_AUDIT_API_PORT     (default: 8100)
  UX_DESIGN_AUDIT_WEBAPP_PATH  (default: <repo>/webapp/ux-design-audit/index.html)
  SOVEREIGN_OS_METRICS_DIR     (default: /var/lib/node_exporter/textfile_collector)
  UX_DESIGN_AUDIT_API_DRY_RUN  (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("UX_DESIGN_AUDIT_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("UX_DESIGN_AUDIT_API_PORT", "8100"))
DRY_RUN = bool(os.environ.get("UX_DESIGN_AUDIT_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_ux_design_audit_api_request_total
#   ux-design-audit read-only REST API request count.
# TYPE sovereign_os_operator_ux_design_audit_api_request_total counter
METRIC_NAME = "sovereign_os_operator_ux_design_audit_api_request_total"

API_VERSION = "1.0.0-R530"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "ux-design-audit" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "UX_DESIGN_AUDIT_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# Importlib-load ux-design-audit.py (R457) directly — same data model
# the CLI + TUI + MCP surfaces serve. No drift.
_CORE_PATH = _REPO_ROOT / "scripts" / "operator" / "ux-design-audit.py"
_spec = importlib.util.spec_from_file_location(
    "_ux_design_audit_core", _CORE_PATH
)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load ux-design-audit.py "
        f"from {_CORE_PATH}\n"
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
            METRICS_DIR, "sovereign-os-ux-design-audit-api.prom"
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
        "module": "ux-design-audit-api",
        "version": API_VERSION,
        "shipped_in": (
            "R530 (E5++ read-only REST API + webapp + systemd service)"
        ),
        "source": "scripts/operator/ux-design-audit-api.py",
        "data_source": str(_CORE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "verbs": [
            "dimensions", "modules", "audit", "score",
            "report", "selfdef",
        ],
        "spec_ref": "R457",
        "standing_rule": (
            "everything will also need to go through a thorough UX "
            "Design stage in order to be of quality."
        ),
    }


def _dimensions_payload() -> dict:
    return {
        "dimensions": _core.DIMENSIONS,
        "count": len(_core.DIMENSIONS),
    }


def _modules_payload() -> dict:
    return {
        "modules": [
            {"id": m["id"], "verb_count": len(m["verbs"]),
             "verbs": m["verbs"]}
            for m in _core.MODULES
        ],
        "count": len(_core.MODULES),
    }


def _resolve_module(module: str | None) -> list[dict] | None:
    if module is None:
        return _core.MODULES
    for m in _core.MODULES:
        if m["id"] == module:
            return [m]
    return None


def _audit_payload(module: str | None) -> dict:
    target = _resolve_module(module)
    if target is None:
        return {
            "error": f"unknown module: {module!r}",
            "known": _core.MODULE_IDS,
        }
    rows = [_core.audit_module(m) for m in target]
    return {"audit": rows, "count": len(rows)}


def _score_payload(module: str | None) -> dict:
    target = _resolve_module(module)
    if target is None:
        return {
            "error": f"unknown module: {module!r}",
            "known": _core.MODULE_IDS,
        }
    rows = []
    for m in target:
        a = _core.audit_module(m)
        rows.append({"module": m["id"], "score": a["score"],
                     "total": a["total"]})
    rows.sort(key=lambda r: r["score"])
    return {"scores": rows, "count": len(rows)}


def _report_payload(threshold: int) -> dict:
    rows = []
    for m in _core.MODULES:
        a = _core.audit_module(m)
        if a["score"] < threshold:
            rows.append({
                "module": m["id"],
                "score": a["score"],
                "total": a["total"],
                "shortfall": threshold - a["score"],
                "missing_dimensions": [
                    r["dimension"]
                    for r in a["results"] if not r["passed"]
                ],
            })
    rows.sort(key=lambda r: r["shortfall"], reverse=True)
    return {
        "threshold": threshold,
        "below_threshold": rows,
        "count": len(rows),
    }


def _selfdef_payload() -> dict:
    valid, invalid = _core.load_selfdef_ux_checklists()
    return {
        "valid": valid,
        "invalid": invalid,
        "count_valid": len(valid),
        "count_invalid": len(invalid),
    }


def _parse_int(query: str, key: str, default: int,
               minimum: int = 1, ceiling: int | None = None) -> int:
    qs = urllib.parse.parse_qs(query)
    if key not in qs:
        return default
    raw = qs[key][0]
    try:
        n = int(raw)
    except ValueError:
        return default
    if n < minimum:
        n = minimum
    if ceiling is not None and n > ceiling:
        n = ceiling
    return n


def _parse_str(query: str, key: str) -> str | None:
    qs = urllib.parse.parse_qs(query)
    if key not in qs:
        return None
    val = qs[key][0].strip()
    return val or None


class UxDesignAuditAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-ux-design-audit-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "ux-design-audit-api")
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
        self.send_header("X-Sovereign-Module", "ux-design-audit-webapp")
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
            if path == "/dimensions":
                self._send_json(200, _dimensions_payload())
                _emit_metric("dimensions", "ok")
                return
            if path == "/modules":
                self._send_json(200, _modules_payload())
                _emit_metric("modules", "ok")
                return
            if path == "/audit":
                module = _parse_str(parsed.query, "module")
                payload = _audit_payload(module)
                status = 400 if "error" in payload else 200
                self._send_json(status, payload)
                _emit_metric("audit", "400" if status == 400 else "ok")
                return
            if path == "/score":
                module = _parse_str(parsed.query, "module")
                payload = _score_payload(module)
                status = 400 if "error" in payload else 200
                self._send_json(status, payload)
                _emit_metric("score", "400" if status == 400 else "ok")
                return
            if path == "/report":
                threshold = _parse_int(
                    parsed.query, "threshold",
                    default=_core.DEFAULT_THRESHOLD,
                    minimum=1, ceiling=6,
                )
                payload = _report_payload(threshold)
                self._send_json(200, payload)
                _emit_metric("report", "ok")
                return
            if path == "/selfdef":
                self._send_json(200, _selfdef_payload())
                _emit_metric("selfdef", "ok")
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
            "available": [
                "/version", "/dimensions", "/modules",
                "/audit", "/score", "/report", "/selfdef",
                "/webapp/", "/healthz",
            ],
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
            "error": "read-only surface — ux-design-audit has NO "
                     "mutation verbs at any surface (audit is a "
                     "query; remediation lives in the audited "
                     "modules themselves, NOT in this daemon). "
                     "The operator §17 sovereignty boundary applies "
                     "— no `ux-design-audit-waiver` mutation here.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] ux-design-audit-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_CORE_PATH}", flush=True)
    print(f"  endpoints:   /version /dimensions /modules /audit /score "
          f"/report /selfdef /webapp/ + /healthz",
          flush=True)
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
        httpd = HTTPServer((bind, port), UxDesignAuditAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] ux-design-audit-api shutdown requested.",
              flush=True)
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
