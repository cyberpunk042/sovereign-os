#!/usr/bin/env python3
"""
scripts/operator/surface-map-api.py — Read-only HTTP API + webapp for
the §1g/§1h surface-map inspection surface (R533, E5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

Third and final commit in the surface-map tier-3 surface-expansion
arc (R531 TUI → R532 MCP → R533 API + webapp + service). Drains the
surface-map api:FUTURE + webapp:FUTURE waivers AND REPLACES the
prior service:not-applicable waiver with a REAL systemd-managed
read-only daemon — same pattern R510 (global-history) / R515
(trinity) / R518 (router) / R521 (compliance) / R524 (anti-min) /
R527 (doc-coverage) / R530 (ux-design-audit) used to flip a
previously-applicable waiver into a shipped service. Lands surface-
map as the TENTH §1g module at full 8-surface structural ceiling
(after edge-firewall R506, network-edge R509, global-history R512,
trinity R515, router R518, compliance R521, anti-min R524, doc-
coverage R527, ux-design-audit R530).

Eating-our-own-dogfood — surface-map is THE §1g coverage instrument
itself; having it sit at less-than-ceiling while other modules pass
their own contracts would be hypocritical. R531-R533 fix that.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1, port 8101 — sister to the
    R515 trinity-api 8095 / R518 router-api 8096 / R521 compliance-
    api 8097 / R524 anti-min-api 8098 / R527 doc-coverage-api 8099 /
    R530 ux-design-audit-api 8100)
  - Read-only verbs only — surface-map has NO mutation verbs at any
    surface (the coverage matrix is a query; remediation lives in
    the audited modules themselves). Operator §17 sovereignty
    boundary preserved.

Read-only endpoints (R533 v1):
  GET /version                        — service version + module identity
  GET /surfaces                       — list 8 §1g operator-named surfaces
  GET /modules                        — operator-facing modules tracked
  GET /coverage[?module=<m>]          — module × surface coverage matrix
  GET /gaps[?threshold=N]             — modules below surface threshold
  GET /waivers[?module=<m>]           — per-module explicit waivers
  GET /selfdef                        — R462 cross-repo selfdef
                                        SurfaceManifest discovery
  GET /webapp/                        — R533 single-file monochrome SPA
                                        mirroring the read-only verbs
                                        (operator-§1g: zero external deps)
  GET /healthz                        — API daemon liveness (always 200)

Layer-B metric (sister to R530 ux-design-audit + R527 doc-coverage):

  sovereign_os_operator_surface_map_api_request_total{endpoint,result}

Env vars (all overridable):
  SURFACE_MAP_API_BIND     (default: 127.0.0.1)
  SURFACE_MAP_API_PORT     (default: 8101)
  SURFACE_MAP_WEBAPP_PATH  (default: <repo>/webapp/surface-map/index.html)
  SOVEREIGN_OS_METRICS_DIR (default: /var/lib/node_exporter/textfile_collector)
  SURFACE_MAP_API_DRY_RUN  (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("SURFACE_MAP_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("SURFACE_MAP_API_PORT", "8101"))
DRY_RUN = bool(os.environ.get("SURFACE_MAP_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_surface_map_api_request_total
#   surface-map read-only REST API request count.
# TYPE sovereign_os_operator_surface_map_api_request_total counter
METRIC_NAME = "sovereign_os_operator_surface_map_api_request_total"

API_VERSION = "1.0.0-R533"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "surface-map" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "SURFACE_MAP_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# Importlib-load surface-map.py (R453) directly — same data model
# the CLI + TUI + MCP surfaces serve. No drift.
_CORE_PATH = _REPO_ROOT / "scripts" / "operator" / "surface-map.py"
_spec = importlib.util.spec_from_file_location(
    "_surface_map_core", _CORE_PATH
)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load surface-map.py "
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
            METRICS_DIR, "sovereign-os-surface-map-api.prom"
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
        "module": "surface-map-api",
        "version": API_VERSION,
        "shipped_in": (
            "R533 (E5++ read-only REST API + webapp + systemd service)"
        ),
        "source": "scripts/operator/surface-map-api.py",
        "data_source": str(_CORE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "verbs": [
            "surfaces", "modules", "coverage", "gaps",
            "waivers", "selfdef",
        ],
        "spec_ref": "R453",
        "standing_rule": (
            "everything is not just core, not just cli, not just TUI, "
            "not just API, not just tool and MCP but also Dashboards "
            "and Web Apps and Services."
        ),
    }


def _surfaces_payload() -> dict:
    return {
        "surfaces": _core.SURFACES,
        "count": len(_core.SURFACES),
    }


def _modules_payload() -> dict:
    rows = []
    for mod_id in _core.KNOWN_MODULES:
        cov = _core.coverage_for(mod_id)
        rows.append({
            "id": mod_id,
            "surface_count": cov.get("surface_count", 0),
            "structural_waiver_count": cov.get(
                "structural_waiver_count", 0),
            "future_waiver_count": cov.get("future_waiver_count", 0),
            "at_structural_ceiling": cov.get(
                "at_structural_ceiling", False),
            "shipped_in": cov.get("shipped_in", ""),
        })
    return {"modules": rows, "count": len(rows)}


def _coverage_payload(module: str | None) -> dict:
    if module is None:
        rows = [_core.coverage_for(m) for m in _core.KNOWN_MODULES]
        rows.sort(
            key=lambda r: (
                -(r.get("future_waiver_count", 0)
                  + (8 - r.get("surface_count", 0))),
                r.get("module", ""),
            )
        )
        return {"coverage": rows, "count": len(rows)}
    if module not in _core.KNOWN_MODULES:
        return {
            "error": f"unknown module: {module!r}",
            "known": _core.KNOWN_MODULES,
        }
    return {"coverage": [_core.coverage_for(module)], "count": 1}


def _gaps_payload(threshold: int) -> dict:
    rows = []
    for mod_id in _core.KNOWN_MODULES:
        cov = _core.coverage_for(mod_id)
        sc = cov.get("surface_count", 0)
        if cov.get("at_structural_ceiling"):
            # R478 — structural-ceiling modules are NOT gap candidates.
            continue
        if sc < threshold:
            rows.append({
                "module": mod_id,
                "surface_count": sc,
                "shortfall": threshold - sc,
                "future_waiver_count": cov.get(
                    "future_waiver_count", 0),
            })
    rows.sort(key=lambda r: r["shortfall"], reverse=True)
    return {
        "threshold": threshold,
        "below_threshold": rows,
        "count": len(rows),
    }


def _waivers_payload(module: str | None) -> dict:
    if module is None:
        rows = []
        for mod_id in _core.KNOWN_MODULES:
            entry = _core.MODULE_COVERAGE[mod_id]
            for surface_id, rationale in (
                entry.get("waivers") or {}
            ).items():
                rows.append({
                    "module": mod_id,
                    "surface": surface_id,
                    "rationale": rationale,
                    "waiver_class": _core._classify_waiver(rationale),
                })
        return {"waivers": rows, "count": len(rows)}
    if module not in _core.KNOWN_MODULES:
        return {
            "error": f"unknown module: {module!r}",
            "known": _core.KNOWN_MODULES,
        }
    entry = _core.MODULE_COVERAGE[module]
    rows = []
    for surface_id, rationale in (entry.get("waivers") or {}).items():
        rows.append({
            "module": module,
            "surface": surface_id,
            "rationale": rationale,
            "waiver_class": _core._classify_waiver(rationale),
        })
    return {"waivers": rows, "count": len(rows)}


def _selfdef_payload() -> dict:
    valid, invalid = _core.load_selfdef_surface_manifests()
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


class SurfaceMapAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-surface-map-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "surface-map-api")
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
        self.send_header("X-Sovereign-Module", "surface-map-webapp")
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
            if path == "/surfaces":
                self._send_json(200, _surfaces_payload())
                _emit_metric("surfaces", "ok")
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
            if path == "/gaps":
                threshold = _parse_int(
                    parsed.query, "threshold",
                    default=_core.DEFAULT_THRESHOLD,
                    minimum=1, ceiling=8,
                )
                self._send_json(200, _gaps_payload(threshold))
                _emit_metric("gaps", "ok")
                return
            if path == "/waivers":
                module = _parse_str(parsed.query, "module")
                payload = _waivers_payload(module)
                status = 400 if "error" in payload else 200
                self._send_json(status, payload)
                _emit_metric("waivers", "400" if status == 400 else "ok")
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
                "/version", "/surfaces", "/modules",
                "/coverage", "/gaps", "/waivers", "/selfdef",
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
            "error": "read-only surface — surface-map has NO mutation "
                     "verbs at any surface (the coverage matrix is a "
                     "query; remediation lives in the audited modules "
                     "themselves, NOT in this daemon). The operator "
                     "§17 sovereignty boundary applies — no "
                     "`surface-map-waiver-set` mutation here.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] surface-map-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_CORE_PATH}", flush=True)
    print(f"  endpoints:   /version /surfaces /modules /coverage /gaps "
          f"/waivers /selfdef /webapp/ + /healthz",
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
        httpd = HTTPServer((bind, port), SurfaceMapAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] surface-map-api shutdown requested.",
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
