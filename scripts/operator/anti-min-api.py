#!/usr/bin/env python3
"""
scripts/operator/anti-min-api.py — Read-only HTTP API + webapp for
the §1g/§1h anti-minimization-audit inspection surface (R524, E5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

Third and final commit in the anti-min tier-3 surface-expansion arc
(R522 TUI → R523 MCP → R524 API + webapp + service). Drains the
anti-min api:FUTURE + webapp:FUTURE waivers AND REPLACES the prior
service:not-applicable waiver with a REAL systemd-managed read-only
daemon — same pattern R510 (global-history) / R515 (trinity) /
R518 (router) / R521 (compliance) used to flip a previously-applicable
waiver into a shipped service. Lands anti-min as the SEVENTH §1g
module at full 8-surface structural ceiling (after edge-firewall
R506, network-edge R509, global-history R512, trinity R515, router
R518, compliance R521).

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1, port 8098 — sister to the
    R515 trinity-api 8095 / R518 router-api 8096 / R521 compliance-api
    8097)
  - Read-only verbs only — anti-minimization-audit has NO mutation
    verbs at any surface (the R474 `anti-min-waiver:` annotations are
    operator-authored in-source markers, NOT something a daemon
    toggles). Operator §17 sovereignty boundary preserved.

Read-only endpoints (R524 v1):
  GET /version                         — service version + module identity
  GET /patterns                        — list 8 R456 operator-named patterns
  GET /report                          — full 8-pattern audit summary
  GET /scan?pattern=<p>[&limit=N]      — scan results for one pattern (or
                                         all when pattern omitted)
  GET /waivers                         — active R474 `anti-min-waiver:`
                                         annotations across the tree
  GET /module?name=<n>                 — per-module surface/doc/minimize audit
  GET /cross-module[?threshold=N]      — cross-module short-on-both-axes
                                         priority ranking (default thr=3)
  GET /selfdef                         — R466 cross-repo selfdef
                                         AuditManifest discovery
  GET /webapp/                         — R524 single-file monochrome SPA
                                         mirroring the read-only verbs
                                         (operator-§1g: zero external deps)
  GET /healthz                         — API daemon liveness (always 200)

Layer-B metric (sister to R519+R520+R521 compliance + R522+R523 anti-min):

  sovereign_os_operator_anti_min_api_request_total{endpoint,result}

Env vars (all overridable):
  ANTI_MIN_API_BIND           (default: 127.0.0.1)
  ANTI_MIN_API_PORT           (default: 8098)
  ANTI_MIN_WEBAPP_PATH        (default: <repo>/webapp/anti-minimization-audit/index.html)
  SOVEREIGN_OS_METRICS_DIR    (default: /var/lib/node_exporter/textfile_collector)
  ANTI_MIN_API_DRY_RUN        (default: unset; set to 1 = print and exit)
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

API_BIND = os.environ.get("ANTI_MIN_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("ANTI_MIN_API_PORT", "8098"))
DRY_RUN = bool(os.environ.get("ANTI_MIN_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_anti_min_api_request_total
#   anti-minimization-audit read-only REST API request count.
# TYPE sovereign_os_operator_anti_min_api_request_total counter
METRIC_NAME = "sovereign_os_operator_anti_min_api_request_total"

API_VERSION = "1.0.0-R524"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "anti-minimization-audit" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "ANTI_MIN_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# Importlib-load anti-minimization-audit.py (R456) directly — same data
# model the CLI + TUI + MCP surfaces serve. No drift.
_CORE_PATH = _REPO_ROOT / "scripts" / "operator" / "anti-minimization-audit.py"
_spec = importlib.util.spec_from_file_location(
    "_anti_min_core", _CORE_PATH
)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load anti-minimization-audit.py "
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
            METRICS_DIR, "sovereign-os-anti-min-api.prom"
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
        "module": "anti-min-api",
        "version": API_VERSION,
        "shipped_in": (
            "R524 (E5++ read-only REST API + webapp + systemd service)"
        ),
        "source": "scripts/operator/anti-min-api.py",
        "data_source": str(_CORE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "verbs": [
            "patterns", "report", "scan", "waivers",
            "module", "cross-module", "selfdef",
        ],
        "spec_ref": "R456",
        "standing_rule": "We do not minimize anything.",
    }


def _patterns_payload() -> dict:
    return {"patterns": _core.PATTERNS, "count": len(_core.PATTERNS)}


def _report_payload() -> dict:
    summary: dict[str, int] = {}
    for p in _core.PATTERN_IDS:
        scanner = _core.PATTERN_SCANNERS[p]
        if p in ("surface-gap", "doc-gap"):
            summary[p] = len(scanner())
        else:
            summary[p] = len(scanner(limit=None))
    total = sum(summary.values())
    return {"summary": summary, "total": total}


def _scan_payload(pattern: str | None, limit: int | None) -> dict:
    if pattern and pattern not in _core.PATTERN_IDS:
        return {
            "error": f"unknown pattern: {pattern!r}",
            "known": _core.PATTERN_IDS,
        }
    pats = [pattern] if pattern else _core.PATTERN_IDS
    results: dict[str, list[dict]] = {}
    for p in pats:
        scanner = _core.PATTERN_SCANNERS[p]
        if p in ("surface-gap", "doc-gap"):
            results[p] = scanner()
        else:
            results[p] = scanner(limit=limit)
    total = sum(len(v) for v in results.values())
    return {
        "results": results,
        "total_matches": total,
        "limit": limit,
        "patterns_scanned": pats,
    }


def _waivers_payload() -> dict:
    matches: list[dict] = []
    for f in _core._iter_scan_files():
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = _core._WAIVER_RE.search(line)
            if not m:
                continue
            matches.append({
                "file": str(f.relative_to(_core.REPO_ROOT)),
                "line": i,
                "anchor": m.group("anchor"),
                "rationale": m.group("rationale")[:160],
            })
    return {"waivers": matches, "count": len(matches)}


def _module_payload(name: str) -> dict:
    args = types.SimpleNamespace(name=name, fmt="json")
    # Replay cmd_module's logic without invoking the print path. Easier:
    # delegate to the scanners directly to keep the response shape stable.
    import re as _re
    surface_gaps = [
        g for g in _core.scan_surface_gap() if g["module"] == name
    ]
    doc_gaps = [
        g for g in _core.scan_doc_gap() if g["module"] == name
    ]
    name_re = _re.compile(
        _re.escape(name).replace(r"\-", r"[-_]"), _re.IGNORECASE,
    )
    minimize_re = _re.compile(
        "|".join(_re.escape(p) for p in _core.MINIMIZE_PHRASES),
        _re.IGNORECASE,
    )
    minimize_in_module: list[dict] = []
    for f in _core._iter_scan_files():
        if not name_re.search(f.name):
            continue
        for lineno, line in _core._grep_lines(f, minimize_re):
            minimize_in_module.append({
                "file": str(f.relative_to(_core.REPO_ROOT)),
                "line": lineno,
                "text": line[:160],
            })
    return {
        "module": name,
        "surface_gaps": surface_gaps,
        "doc_gaps": doc_gaps,
        "minimize_phrases_in_module_files": minimize_in_module,
    }


def _cross_module_payload(threshold: int) -> dict:
    surface = _core.scan_surface_gap(threshold=threshold)
    doc = _core.scan_doc_gap(threshold=threshold)
    surface_ids = {g["module"] for g in surface}
    doc_ids = {g["module"] for g in doc}
    short_both = sorted(surface_ids & doc_ids)
    short_only_surface = sorted(surface_ids - doc_ids)
    short_only_doc = sorted(doc_ids - surface_ids)
    return {
        "threshold": threshold,
        "short_on_both_axes": short_both,
        "short_only_surface": short_only_surface,
        "short_only_doc": short_only_doc,
    }


def _selfdef_payload() -> dict:
    valid, invalid = _core.load_selfdef_audit_manifests()
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


class AntiMinAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-anti-min-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "anti-min-api")
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
        self.send_header("X-Sovereign-Module", "anti-min-webapp")
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
            if path == "/patterns":
                self._send_json(200, _patterns_payload())
                _emit_metric("patterns", "ok")
                return
            if path == "/report":
                self._send_json(200, _report_payload())
                _emit_metric("report", "ok")
                return
            if path == "/scan":
                pattern = _parse_str(parsed.query, "pattern")
                limit = _parse_int(
                    parsed.query, "limit", default=None,
                    minimum=1, ceiling=10000,
                )
                payload = _scan_payload(pattern, limit)
                status = 400 if "error" in payload else 200
                self._send_json(status, payload)
                _emit_metric("scan", "400" if status == 400 else "ok")
                return
            if path == "/waivers":
                self._send_json(200, _waivers_payload())
                _emit_metric("waivers", "ok")
                return
            if path == "/module":
                name = _parse_str(parsed.query, "name")
                if not name:
                    self._send_json(400, {
                        "error": "missing required query param: name",
                    })
                    _emit_metric("module", "400")
                    return
                self._send_json(200, _module_payload(name))
                _emit_metric("module", "ok")
                return
            if path == "/cross-module":
                threshold = _parse_int(
                    parsed.query, "threshold", default=3,
                    minimum=1, ceiling=8,
                )
                self._send_json(200, _cross_module_payload(threshold))
                _emit_metric("cross-module", "ok")
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
                "/version", "/patterns", "/report", "/scan",
                "/waivers", "/module", "/cross-module", "/selfdef",
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
            "error": "read-only surface — anti-minimization-audit has "
                     "NO mutation verbs at any surface (the R474 "
                     "`anti-min-waiver:` annotations are operator-"
                     "authored in-source markers, NOT something this "
                     "daemon toggles). Operator §17 sovereignty "
                     "boundary preserved.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] anti-min-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_CORE_PATH}", flush=True)
    print(f"  endpoints:   /version /patterns /report /scan /waivers "
          f"/module /cross-module /selfdef /webapp/ + /healthz",
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
        httpd = HTTPServer((bind, port), AntiMinAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] anti-min-api shutdown requested.", flush=True)
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
