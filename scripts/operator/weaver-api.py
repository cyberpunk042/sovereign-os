#!/usr/bin/env python3
"""
scripts/operator/weaver-api.py — Read-only HTTP API + webapp for the
§1g weaver (master spec § 7.1 / § 21 atomic-state) inspection surface
(R536, E5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim, R453):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

Third and final commit in the weaver tier-3 surface-expansion arc
(R534 TUI -> R535 MCP -> R536 API + webapp + service). Drains the
weaver api:FUTURE + webapp:FUTURE waivers AND REPLACES the prior
service:not-applicable waiver with a REAL systemd-managed read-only
daemon — same pattern R510 (global-history) / R515 (trinity) / R518
(router) / R521 (compliance) / R524 (anti-min) / R527 (doc-coverage)
/ R530 (ux-design-audit) / R533 (surface-map) used to flip a
previously-applicable waiver into a shipped service. Lands weaver as
the ELEVENTH §1g module at full 8-surface structural ceiling.

Operator §17 sovereignty boundary (the load-bearing R536 invariant):
the weaver API exposes ONLY read-only inspection — `list` (LIVE
state-fabric presence + size + mtime) and `state-files` (STATIC
master spec § 7.1 catalog). The mutation verb `write` (atomic-state
commit) and the runtime-arg verb `read` (per-file read) are
intentionally NOT exposed via the API: state-fabric writes are
sovereignty-critical and stay manual + CLI-gated. This matches the
R535 MCP surface decision verbatim.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1, port 8102 — sister to the
    R515 trinity-api 8095 / R518 router-api 8096 / R521 compliance-
    api 8097 / R524 anti-min-api 8098 / R527 doc-coverage-api 8099 /
    R530 ux-design-audit-api 8100 / R533 surface-map-api 8101)
  - Read-only verbs at the API surface — mutation stays CLI-gated.

Read-only endpoints (R536 v1):
  GET /version                 — service version + module identity
  GET /list                    — LIVE 4-state-fabric file inventory
                                 (master spec § 21 atomic-state list)
  GET /state-files             — STATIC master spec § 7.1 catalog
  GET /webapp/                 — R536 single-file monochrome SPA
                                 mirroring the read-only verbs
                                 (operator-§1g: zero external deps)
  GET /healthz                 — API daemon liveness (always 200)

Layer-B metric (sister to R533 surface-map / R530 ux-design-audit):

  sovereign_os_operator_weaver_api_request_total{endpoint,result}

Env vars (all overridable):
  WEAVER_API_BIND          (default: 127.0.0.1)
  WEAVER_API_PORT          (default: 8102)
  WEAVER_WEBAPP_PATH       (default: <repo>/webapp/weaver/index.html)
  SOVEREIGN_OS_METRICS_DIR (default: /var/lib/node_exporter/textfile_collector)
  WEAVER_API_DRY_RUN       (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("WEAVER_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("WEAVER_API_PORT", "8102"))
DRY_RUN = bool(os.environ.get("WEAVER_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_weaver_api_request_total
#   weaver read-only REST API request count.
# TYPE sovereign_os_operator_weaver_api_request_total counter
METRIC_NAME = "sovereign_os_operator_weaver_api_request_total"

API_VERSION = "1.0.0-R536"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "weaver" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "WEAVER_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# Importlib-load atomic-state.py — the master spec § 21.1 primitive
# that the CLI, TUI, and R535 MCP surfaces share. No drift across
# surfaces; the daemon is a thin HTTP wrapper over the same data.
_CORE_PATH = _REPO_ROOT / "scripts" / "weaver" / "atomic-state.py"
_spec = importlib.util.spec_from_file_location(
    "_weaver_atomic_state_core", _CORE_PATH
)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load atomic-state.py "
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
            METRICS_DIR, "sovereign-os-weaver-api.prom"
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
        "module": "weaver-api",
        "version": API_VERSION,
        "shipped_in": (
            "R536 (E5++ read-only REST API + webapp + systemd service)"
        ),
        "source": "scripts/operator/weaver-api.py",
        "data_source": str(_CORE_PATH),
        "context_dir": _core.CONTEXT_DIR,
        "webapp_path": str(WEBAPP_PATH),
        "state_files": list(_core.STATE_FILES),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "verbs": ["list", "state-files"],
        "cli_gated_verbs": ["write", "read"],
        "sovereignty_boundary": (
            "operator §17 — state-fabric writes are sovereignty-"
            "critical and stay manual + CLI-gated. The mutation verb "
            "`write` (atomic-state commit) and the runtime-arg verb "
            "`read` (per-file read) are intentionally NOT exposed via "
            "the API surface."
        ),
        "spec_ref": "master spec § 7.1 / § 21 (Atomic State Protocol)",
        "standing_rule": (
            "everything is not just core, not just cli, not just TUI, "
            "not just API, not just tool and MCP but also Dashboards "
            "and Web Apps and Services."
        ),
    }


def _list_payload() -> dict:
    """LIVE 4-state-fabric file inventory under CONTEXT_DIR."""
    rows = []
    for name in _core.STATE_FILES:
        path = os.path.join(_core.CONTEXT_DIR, name)
        if os.path.exists(path):
            st = os.stat(path)
            rows.append({
                "name": name,
                "present": True,
                "size_bytes": st.st_size,
                "mtime_epoch": int(st.st_mtime),
                "mtime_iso": time.strftime(
                    "%Y-%m-%dT%H:%M:%S",
                    time.localtime(st.st_mtime),
                ),
            })
        else:
            rows.append({
                "name": name,
                "present": False,
                "size_bytes": None,
                "mtime_epoch": None,
                "mtime_iso": None,
            })
    return {
        "context_dir": _core.CONTEXT_DIR,
        "files": rows,
        "count": len(rows),
        "count_present": sum(1 for r in rows if r["present"]),
    }


def _state_files_payload() -> dict:
    """STATIC master spec § 7.1 catalog (operator-named vocabulary)."""
    rows = [
        {
            "id": "IDENTITY.md",
            "label": "Identity (master spec § 7.1)",
            "master_spec_ref": "§ 7.1 / § 21",
            "operator_named": "IDENTITY",
        },
        {
            "id": "SOUL.md",
            "label": "Soul (master spec § 7.1)",
            "master_spec_ref": "§ 7.1 / § 21",
            "operator_named": "SOUL",
        },
        {
            "id": "AGENTS.md",
            "label": "Agents (master spec § 7.1)",
            "master_spec_ref": "§ 7.1 / § 21",
            "operator_named": "AGENTS",
        },
        {
            "id": "CLAUDE.md",
            "label": "Claude — agent runtime context (master spec § 7.1)",
            "master_spec_ref": "§ 7.1 / § 21",
            "operator_named": "CLAUDE",
        },
    ]
    return {
        "files": rows,
        "count": len(rows),
        "context_dir": _core.CONTEXT_DIR,
        "spec_anchor": "master spec § 7.1 + § 21 (Atomic State Protocol)",
    }


class WeaverAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-weaver-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "weaver-api")
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
        self.send_header("X-Sovereign-Module", "weaver-webapp")
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
            _emit_metric(
                "healthz" if path == "/healthz" else "root", "ok"
            )
            return

        if path in ("/webapp", "/webapp/index.html"):
            self._send_webapp()
            return

        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/list":
                self._send_json(200, _list_payload())
                _emit_metric("list", "ok")
                return
            if path == "/state-files":
                self._send_json(200, _state_files_payload())
                _emit_metric("state_files", "ok")
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
                "/version", "/list", "/state-files",
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
            "error": "read-only surface — atomic-state writes are "
                     "sovereignty-critical and stay manual + CLI-"
                     "gated. The operator §17 sovereignty boundary "
                     "applies — `weaver write` (master spec § 21.1 "
                     "atomic commit) and `weaver read` (per-file "
                     "read with runtime arg) are intentionally NOT "
                     "exposed via the API. Use `sovereign-osctl "
                     "weaver write` from the CLI surface instead. "
                     "Remediation: invoke the CLI directly — no "
                     "mutation routes exist on this daemon.",
            "allowed": ["GET", "HEAD"],
            "cli_gated_verbs": ["write", "read"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] weaver-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_CORE_PATH}", flush=True)
    print(f"  context dir: {_core.CONTEXT_DIR}", flush=True)
    print(
        f"  endpoints:   /version /list /state-files /webapp/ + /healthz",
        flush=True,
    )
    print(f"  webapp:      {WEBAPP_PATH}", flush=True)
    print(
        "  sovereignty: write + read stay CLI-only "
        "(operator §17 boundary)",
        flush=True,
    )
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
        httpd = HTTPServer((bind, port), WeaverAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] weaver-api shutdown requested.", flush=True)
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
