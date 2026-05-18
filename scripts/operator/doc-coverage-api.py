#!/usr/bin/env python3
"""
scripts/operator/doc-coverage-api.py — Read-only HTTP API + webapp for
the §1g/§1h doc-coverage inspection surface (R527, E5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

Third and final commit in the doc-coverage tier-3 surface-expansion
arc (R525 TUI → R526 MCP → R527 API + webapp + service). Drains the
doc-coverage api:FUTURE + webapp:FUTURE waivers AND REPLACES the prior
service:not-applicable waiver with a REAL systemd-managed read-only
daemon — same pattern R510 (global-history) / R515 (trinity) /
R518 (router) / R521 (compliance) / R524 (anti-min) used to flip a
previously-applicable waiver into a shipped service. Lands
doc-coverage as the EIGHTH §1g module at full 8-surface structural
ceiling (after edge-firewall R506, network-edge R509, global-history
R512, trinity R515, router R518, compliance R521, anti-min R524).

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1, port 8099 — sister to the
    R515 trinity-api 8095 / R518 router-api 8096 / R521 compliance-api
    8097 / R524 anti-min-api 8098)
  - Read-only verbs only — doc-coverage has NO mutation verbs at any
    surface (docs ARE the source of truth; the daemon scans, it does
    not author). Operator §17 sovereignty boundary preserved.

Read-only endpoints (R527 v1):
  GET /version                         — service version + module identity
  GET /kinds                           — list 6 R454 operator-named doc surfaces
  GET /modules                         — operator-facing modules tracked
  GET /coverage[?module=<m>]           — module × doc-surface matrix
  GET /scan[?module=<m>]               — per-module presence/absence
  GET /gaps[?threshold=N][&module=<m>] — modules below doc-surface threshold
  GET /selfdef                         — R471 cross-repo selfdef
                                         DocManifest discovery
  GET /webapp/                         — R527 single-file monochrome SPA
                                         mirroring the read-only verbs
                                         (operator-§1g: zero external deps)
  GET /healthz                         — API daemon liveness (always 200)

Layer-B metric (sister to R519+R520+R521 compliance + R522-R524 anti-min):

  sovereign_os_operator_doc_coverage_api_request_total{endpoint,result}

Env vars (all overridable):
  DOC_COVERAGE_API_BIND      (default: 127.0.0.1)
  DOC_COVERAGE_API_PORT      (default: 8099)
  DOC_COVERAGE_WEBAPP_PATH   (default: <repo>/webapp/doc-coverage/index.html)
  SOVEREIGN_OS_METRICS_DIR   (default: /var/lib/node_exporter/textfile_collector)
  DOC_COVERAGE_API_DRY_RUN   (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("DOC_COVERAGE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("DOC_COVERAGE_API_PORT", "8099"))
DRY_RUN = bool(os.environ.get("DOC_COVERAGE_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_doc_coverage_api_request_total
#   doc-coverage read-only REST API request count.
# TYPE sovereign_os_operator_doc_coverage_api_request_total counter
METRIC_NAME = "sovereign_os_operator_doc_coverage_api_request_total"

API_VERSION = "1.0.0-R527"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "doc-coverage" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "DOC_COVERAGE_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# Importlib-load doc-coverage.py (R454) directly — same data model the
# CLI + TUI + MCP surfaces serve. No drift.
_CORE_PATH = _REPO_ROOT / "scripts" / "operator" / "doc-coverage.py"
_spec = importlib.util.spec_from_file_location(
    "_doc_coverage_core", _CORE_PATH
)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load doc-coverage.py "
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
            METRICS_DIR, "sovereign-os-doc-coverage-api.prom"
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
        "module": "doc-coverage-api",
        "version": API_VERSION,
        "shipped_in": (
            "R527 (E5++ read-only REST API + webapp + systemd service)"
        ),
        "source": "scripts/operator/doc-coverage-api.py",
        "data_source": str(_CORE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "verbs": [
            "kinds", "modules", "coverage", "scan", "gaps", "selfdef",
        ],
        "spec_ref": "R454",
        "standing_rule": "docs ARE the source of truth.",
    }


def _kinds_payload() -> dict:
    return {"kinds": _core.DOC_KINDS, "count": len(_core.DOC_KINDS)}


def _modules_payload() -> dict:
    return {
        "modules": [
            {"id": m["id"], "patterns": m["patterns"]}
            for m in _core.MODULES
        ],
        "count": len(_core.MODULES),
    }


def _coverage_payload(module: str | None) -> dict:
    if module is not None:
        target = [m for m in _core.MODULES if m["id"] == module]
        if not target:
            return {
                "error": f"unknown module: {module!r}",
                "known": _core.MODULE_IDS,
            }
    else:
        target = _core.MODULES
    rows = [_core.scan_module(m) for m in target]
    rows.sort(key=lambda r: r["doc_surface_count"])
    matrix = []
    for r in rows:
        matrix.append({
            "module": r["module"],
            "doc_surface_count": r["doc_surface_count"],
            "cells": [
                {
                    "kind": k["id"],
                    "state": "shipped" if k["id"] in r["present_in"]
                             else "gap",
                }
                for k in _core.DOC_KINDS
            ],
        })
    return {"coverage": matrix, "count": len(matrix)}


def _scan_payload(module: str | None) -> dict:
    if module is not None:
        target = [m for m in _core.MODULES if m["id"] == module]
        if not target:
            return {
                "error": f"unknown module: {module!r}",
                "known": _core.MODULE_IDS,
            }
    else:
        target = _core.MODULES
    rows = [_core.scan_module(m) for m in target]
    return {"scan": rows, "count": len(rows)}


def _gaps_payload(threshold: int, module: str | None) -> dict:
    if module is not None:
        target = [m for m in _core.MODULES if m["id"] == module]
        if not target:
            return {
                "error": f"unknown module: {module!r}",
                "known": _core.MODULE_IDS,
            }
    else:
        target = _core.MODULES
    below = []
    for m in target:
        cov = _core.scan_module(m)
        if cov["doc_surface_count"] < threshold:
            below.append({
                "module": m["id"],
                "doc_surface_count": cov["doc_surface_count"],
                "shortfall": threshold - cov["doc_surface_count"],
                "missing_from": cov["missing_from"],
            })
    below.sort(key=lambda r: r["shortfall"], reverse=True)
    return {
        "threshold": threshold,
        "below_threshold": below,
        "count": len(below),
    }


def _selfdef_payload() -> dict:
    valid, invalid = _core.load_selfdef_doc_manifests()
    return {
        "valid": valid,
        "invalid": invalid,
        "count_valid": len(valid),
        "count_invalid": len(invalid),
    }


def _parse_int(query: str, key: str, default: int | None,
               minimum: int = 1, ceiling: int | None = None) -> int | None:
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


class DocCoverageAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-doc-coverage-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "doc-coverage-api")
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
        self.send_header("X-Sovereign-Module", "doc-coverage-webapp")
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
            if path == "/kinds":
                self._send_json(200, _kinds_payload())
                _emit_metric("kinds", "ok")
                return
            if path == "/modules":
                self._send_json(200, _modules_payload())
                _emit_metric("modules", "ok")
                return
            if path == "/coverage":
                module = _parse_str(parsed.query, "module")
                payload = _coverage_payload(module)
                status = 400 if "error" in payload else 200
                self._send_json(status, payload)
                _emit_metric("coverage", "400" if status == 400 else "ok")
                return
            if path == "/scan":
                module = _parse_str(parsed.query, "module")
                payload = _scan_payload(module)
                status = 400 if "error" in payload else 200
                self._send_json(status, payload)
                _emit_metric("scan", "400" if status == 400 else "ok")
                return
            if path == "/gaps":
                threshold = _parse_int(
                    parsed.query, "threshold",
                    default=_core.DEFAULT_THRESHOLD,
                    minimum=1, ceiling=6,
                )
                module = _parse_str(parsed.query, "module")
                payload = _gaps_payload(threshold, module)
                status = 400 if "error" in payload else 200
                self._send_json(status, payload)
                _emit_metric("gaps", "400" if status == 400 else "ok")
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
                "/version", "/kinds", "/modules", "/coverage",
                "/scan", "/gaps", "/selfdef",
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
            "error": "read-only surface — doc-coverage has NO mutation "
                     "verbs at any surface (docs ARE the source of "
                     "truth; this daemon scans, it does not author). "
                     "The operator §17 sovereignty boundary applies — "
                     "no `doc-coverage-waiver` mutation here.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] doc-coverage-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_CORE_PATH}", flush=True)
    print(f"  endpoints:   /version /kinds /modules /coverage /scan "
          f"/gaps /selfdef /webapp/ + /healthz",
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
        httpd = HTTPServer((bind, port), DocCoverageAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] doc-coverage-api shutdown requested.", flush=True)
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
