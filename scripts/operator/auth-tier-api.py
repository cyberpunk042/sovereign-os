#!/usr/bin/env python3
"""
scripts/operator/auth-tier-api.py — Read-only HTTP API for the
auth-tier registry (R501, E11.M7++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

This ships the `api` surface of the §1g 8-surface delivery ladder for
the `auth-tier` module. The CLI (`sovereign-osctl auth-tier <verb>`)
already covers ad-hoc operator queries; this API surface gives OTHER
consumers (the upcoming MCP server, the upcoming webapp tier-3 shell,
automation scripts, monitoring) a stable wire contract.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1) — operator decides about exposure
  - Read-only verbs only (mutation `set` stays CLI-only — operator §17
    sacrosanct sovereignty boundary)

Read-only endpoints (R501 v1, R503 webapp):
  GET /version                 — service version + module identity
  GET /tiers                   — AUTH_TIERS ladder (operator-named levels)
  GET /registry                — current per-dashboard tier registry
  GET /show?dashboard=<name>   — per-dashboard tier resolution
  GET /matrix                  — upgrade-priority matrix across all dashboards
  GET /healthz                 — API daemon liveness (always 200)
  GET /webapp/                 — single-file operator-§1g webapp (R503)
  GET /webapp/index.html       — alias for /webapp/

All responses are JSON (Content-Type: application/json). On error the
body is {"error": "..."} with a 4xx/5xx status.

Layer-B metric (sister to the CLI `_query_total{verb,tier,result}`):

  sovereign_os_operator_auth_tier_api_request_total{endpoint,result}

Env vars (all overridable):
  AUTH_TIER_API_BIND              (default: 127.0.0.1)
  AUTH_TIER_API_PORT              (default: 8091)
  SOVEREIGN_OS_METRICS_DIR        (default: /var/lib/node_exporter/textfile_collector)
  AUTH_TIER_API_DRY_RUN           (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("AUTH_TIER_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("AUTH_TIER_API_PORT", "8091"))
DRY_RUN = bool(os.environ.get("AUTH_TIER_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_auth_tier_api_request_total auth-tier read-only
#   REST API request count (endpoint, result).
# TYPE sovereign_os_operator_auth_tier_api_request_total counter
METRIC_NAME = "sovereign_os_operator_auth_tier_api_request_total"

API_VERSION = "1.1.0-R503"

# R503 webapp surface — single-file monochrome SPA shipped under
# webapp/auth-tier/index.html in the repo. Operator can override the
# on-disk path via env (e.g., post-install relocation to /usr/share).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "auth-tier" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "AUTH_TIER_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# auth-tier CLI module — import directly so the API serves from the
# SAME data model the operator-facing CLI uses (no drift).
_THIS_DIR = Path(__file__).resolve().parent
_AT_PATH = _THIS_DIR / "auth-tier.py"
_spec = importlib.util.spec_from_file_location("_at_core", _AT_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load auth-tier.py "
        f"from {_AT_PATH}\n"
    )
    sys.exit(1)
_at = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_at)


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
            METRICS_DIR, "sovereign-os-auth-tier-api.prom"
        )
        line = (
            f"{METRIC_NAME}{{endpoint=\"{endpoint}\","
            f"result=\"{result}\"}} 1\n"
        )
        with open(prom_path, "a") as f:
            f.write(line)
    except OSError:
        pass


def _tiers_payload() -> dict:
    return {
        "count": len(_at.AUTH_TIERS),
        "tiers": _at.AUTH_TIERS,
        "known_tier_names": _at.KNOWN_TIER_NAMES,
    }


def _registry_payload() -> dict:
    registry = _at.load_registry()
    return {
        "config_path": str(_at.CONFIG_PATH),
        "config_present": _at.CONFIG_PATH.is_file(),
        "count": len(registry),
        "dashboards": registry,
    }


def _show_payload(dashboard: str) -> tuple[int, dict]:
    if not dashboard:
        return 400, {"error": "missing required query param: dashboard"}
    registry = _at.load_registry()
    info = registry.get(dashboard)
    if not info:
        return 404, {
            "error": f"unknown dashboard: {dashboard!r}",
            "known": sorted(registry.keys()),
        }
    current = _at._resolve_tier(info.get("current_tier", ""))
    recommended = _at._resolve_tier(info.get("recommended_tier", ""))
    out = {
        "dashboard": dashboard,
        "current": current,
        "recommended": recommended,
        "rationale": info.get("rationale", ""),
        "upgrade_required": bool(
            current and recommended
            and current["level"] < recommended["level"]
        ),
        "allowed_transitions": _at.KNOWN_TIER_NAMES,
    }
    return 200, out


def _matrix_payload() -> dict:
    registry = _at.load_registry()
    rows = []
    for name, info in registry.items():
        cur = _at._resolve_tier(info.get("current_tier", "no-auth"))
        rec = _at._resolve_tier(info.get("recommended_tier", "no-auth"))
        rows.append({
            "dashboard": name,
            "current": cur["tier"] if cur else "?",
            "current_level": cur["level"] if cur else -1,
            "recommended": rec["tier"] if rec else "?",
            "recommended_level": rec["level"] if rec else -1,
            "upgrade_levels": (
                rec["level"] - cur["level"]
                if cur and rec else 0
            ),
            "rationale": info.get("rationale", ""),
        })
    rows.sort(key=lambda r: r["upgrade_levels"], reverse=True)
    upgrades_pending = sum(1 for r in rows if r["upgrade_levels"] > 0)
    return {
        "count": len(rows),
        "upgrades_pending": upgrades_pending,
        "matrix": rows,
    }


def _version_payload() -> dict:
    return {
        "module": "auth-tier-api",
        "version": API_VERSION,
        "shipped_in": "R501 (E11.M7++) + R502 (E11.M7++ MCP surface) + R503 (E11.M7++ webapp surface)",
        "source": "scripts/operator/auth-tier-api.py",
        "data_source": str(_AT_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "dashboard", "api", "service",
                     "mcp", "webapp"],
        "standing_rule": "We do not minimize anything.",
    }


class AuthTierAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-auth-tier-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "auth-tier-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        """R503 — serve the single-file monochrome webapp from disk.
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
        self.send_header("X-Sovereign-Module", "auth-tier-webapp")
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
            if path == "/tiers":
                self._send_json(200, _tiers_payload())
                _emit_metric("tiers", "ok")
                return
            if path == "/registry":
                self._send_json(200, _registry_payload())
                _emit_metric("registry", "ok")
                return
            if path == "/show":
                dashboard = (query.get("dashboard") or [""])[0]
                status, payload = _show_payload(dashboard)
                self._send_json(status, payload)
                _emit_metric(
                    "show",
                    "ok" if status == 200
                    else ("400" if status == 400 else "404"),
                )
                return
            if path == "/matrix":
                self._send_json(200, _matrix_payload())
                _emit_metric("matrix", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return

        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/version", "/tiers", "/registry", "/show",
                          "/matrix", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self):    self._reject_mutation()  # noqa: E704 N802
    def do_PUT(self):     self._reject_mutation()  # noqa: E704 N802
    def do_DELETE(self):  self._reject_mutation()  # noqa: E704 N802
    def do_PATCH(self):   self._reject_mutation()  # noqa: E704 N802

    def _reject_mutation(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — mutation verb `set` stays "
                     "CLI-only (operator §17 sovereignty boundary). "
                     "Use sovereign-osctl auth-tier set.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] auth-tier-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_AT_PATH}", flush=True)
    print(f"  endpoints:   /version /tiers /registry /show /matrix + /healthz",
          flush=True)
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
        httpd = HTTPServer((bind, port), AuthTierAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — {e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] auth-tier-api shutdown requested.", flush=True)
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
