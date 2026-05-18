#!/usr/bin/env python3
"""
scripts/operator/auditor-api.py — Read-only HTTP API + webapp for the
§1g auditor (master spec §§ 10, 17 Module 3) inspection surface
(R539, E5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim, R453):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

Third and final commit in the auditor tier-3 surface-expansion arc
(R537 TUI -> R538 MCP -> R539 API + webapp). Drains the auditor
api:FUTURE + webapp:FUTURE waivers. Lands auditor as the TWELFTH §1g
module at full 8-surface structural ceiling (core / cli / tui / api /
mcp / service / dashboard / webapp). This DIFFERS from the R510 /
R515 / R518 / R521 / R524 / R527 / R530 / R533 / R536 ceiling-
promotion pattern in that the auditor `service` surface ALREADY
shipped (R155 guardian-core systemd daemon — a SECURITY daemon
performing neutralization, not an inspection daemon). The R539 API
daemon is a SECOND, SEPARATE systemd-managed daemon that exists
PURELY as a read-only inspection surface — orthogonal to the
guardian-core neutralization daemon.

Operator §17 sovereignty boundary (the load-bearing R539 invariant):
the auditor API exposes ONLY read-only inspection — `status` (brief
tier panel), `last-violation` (last security_audit.log entry), and
`history` (bounded tail of security_audit.log). The neutralization
path (Tetragon kernel hook → SIGKILL via guardian-core) is CCD-
triggered + CLI-gated and is intentionally NOT exposed via the API.
This matches the R538 MCP surface decision verbatim.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1, port 8103 — sister to the
    R515 trinity-api 8095 / R518 router-api 8096 / R521 compliance-
    api 8097 / R524 anti-min-api 8098 / R527 doc-coverage-api 8099 /
    R530 ux-design-audit-api 8100 / R533 surface-map-api 8101 /
    R536 weaver-api 8102)
  - Read-only verbs at the API surface — neutralization stays CLI-
    gated.

Read-only endpoints (R539 v1):
  GET /version                 — service version + module identity
  GET /status                  — brief Auditor tier panel (delegates
                                 to scripts/trinity/trinity-inspect.py
                                 auditor_payload — same data the CLI/
                                 TUI/MCP surfaces share, no drift)
  GET /last-violation          — last entry of security_audit.log
  GET /history?n=N             — tail -N (default 20, max 1000)
                                 entries of security_audit.log
  GET /webapp/                 — R539 single-file monochrome SPA
                                 mirroring the read-only verbs
                                 (operator-§1g: zero external deps)
  GET /healthz                 — API daemon liveness (always 200)

Mutation methods (POST/PUT/DELETE/PATCH) → 405 with operator §17
remediation guidance (use the CLI / CCD-triggered neutralization
path; the API is inspection only).

Layer-B metric (sister to R536 weaver-api / R533 surface-map):

  sovereign_os_operator_auditor_api_request_total{endpoint,result}

Env vars (all overridable):
  AUDITOR_API_BIND         (default: 127.0.0.1)
  AUDITOR_API_PORT         (default: 8103)
  AUDITOR_WEBAPP_PATH      (default: <repo>/webapp/auditor/index.html)
  AUDITOR_AUDIT_LOG        (default: /mnt/vault/context/security_audit.log)
  SOVEREIGN_OS_METRICS_DIR (default: /var/lib/node_exporter/textfile_collector)
  AUDITOR_API_DRY_RUN      (default: unset; set to 1 = print and exit)
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

API_BIND = os.environ.get("AUDITOR_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("AUDITOR_API_PORT", "8103"))
DRY_RUN = bool(os.environ.get("AUDITOR_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

AUDIT_LOG = os.environ.get(
    "AUDITOR_AUDIT_LOG",
    "/mnt/vault/context/security_audit.log",
)

# HELP sovereign_os_operator_auditor_api_request_total
#   auditor read-only REST API request count.
# TYPE sovereign_os_operator_auditor_api_request_total counter
METRIC_NAME = "sovereign_os_operator_auditor_api_request_total"

API_VERSION = "1.0.0-R539"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "auditor" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "AUDITOR_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# Importlib-load trinity-inspect.py — the R514 JSON inspection helper
# that the CLI (--json), TUI watch panel via _trinity_auditor_brief,
# and R538 MCP surface (auditor-status tool) share. No drift across
# surfaces; the daemon is a thin HTTP wrapper over the same data.
_CORE_PATH = _REPO_ROOT / "scripts" / "trinity" / "trinity-inspect.py"
_spec = importlib.util.spec_from_file_location(
    "_auditor_inspect_core", _CORE_PATH
)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load trinity-inspect.py "
        f"from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

# Default history N (sister to the osctl auditor history default).
HISTORY_DEFAULT_N = 20
HISTORY_MAX_N = 1000

SOVEREIGNTY_BOUNDARY_TEXT = (
    "operator §17 — neutralization is sovereignty-critical and stays "
    "CCD-triggered + CLI-gated. The neutralization path (Tetragon "
    "kernel hook → SIGKILL via guardian-core) is intentionally NOT "
    "exposed via the API surface. This API is read-only inspection "
    "only."
)


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
            METRICS_DIR, "sovereign-os-auditor-api.prom"
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
        "module": "auditor-api",
        "version": API_VERSION,
        "shipped_in": (
            "R539 (E5++ read-only REST API + webapp). Companion to "
            "R155 guardian-core service (separate systemd unit "
            "performing neutralization; this API is inspection only)."
        ),
        "source": "scripts/operator/auditor-api.py",
        "data_source": str(_CORE_PATH),
        "audit_log": AUDIT_LOG,
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "verbs": ["status", "last-violation", "history"],
        "cli_gated_verbs": ["neutralize", "kill", "purge"],
        "sovereignty_boundary": SOVEREIGNTY_BOUNDARY_TEXT,
        "spec_ref": (
            "master spec § 17 Module 3 (Immutable Gatekeeper) + "
            "§ 10 (Native Guardian Loop)"
        ),
        "standing_rule": (
            "everything is not just core, not just cli, not just TUI, "
            "not just API, not just tool and MCP but also Dashboards "
            "and Web Apps and Services."
        ),
    }


def _status_payload() -> dict:
    """Brief Auditor tier panel — delegates to trinity-inspect's
    auditor_payload so CLI/TUI/MCP/API share the same data."""
    return _core.auditor_payload()


def _read_audit_lines() -> tuple[bool, list[str], str | None]:
    """Return (present, lines, error_or_None)."""
    if not os.path.isfile(AUDIT_LOG):
        return False, [], None
    try:
        with open(AUDIT_LOG, "r", encoding="utf-8", errors="replace") as fh:
            return True, fh.readlines(), None
    except OSError as e:
        return True, [], f"{type(e).__name__}: {e}"


def _last_violation_payload() -> dict:
    present, lines, err = _read_audit_lines()
    payload = {
        "module": "auditor",
        "verb": "last-violation",
        "spec_ref": "master spec § 10 (Native Guardian Loop)",
        "log_path": AUDIT_LOG,
        "present": present,
        "sovereignty_boundary": SOVEREIGNTY_BOUNDARY_TEXT,
        "line": None,
    }
    if err is not None:
        payload["error"] = err
    if present and lines:
        payload["line"] = lines[-1].rstrip("\n")
        payload["total_lines"] = len(lines)
    elif present:
        payload["total_lines"] = 0
    return payload


def _history_payload(n: int) -> dict:
    if n < 1:
        n = HISTORY_DEFAULT_N
    if n > HISTORY_MAX_N:
        n = HISTORY_MAX_N
    present, lines, err = _read_audit_lines()
    tail = lines[-n:] if n <= len(lines) else lines
    out = {
        "module": "auditor",
        "verb": "history",
        "spec_ref": "master spec § 10 (Native Guardian Loop)",
        "log_path": AUDIT_LOG,
        "present": present,
        "requested_n": n,
        "max_n": HISTORY_MAX_N,
        "sovereignty_boundary": SOVEREIGNTY_BOUNDARY_TEXT,
        "lines": [ln.rstrip("\n") for ln in tail],
        "count": len(tail),
    }
    if err is not None:
        out["error"] = err
    if present:
        out["total_lines"] = len(lines)
    return out


class AuditorAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-auditor-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "auditor-api")
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
        self.send_header("X-Sovereign-Module", "auditor-webapp")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)

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
            if path == "/status":
                self._send_json(200, _status_payload())
                _emit_metric("status", "ok")
                return
            if path == "/last-violation":
                self._send_json(200, _last_violation_payload())
                _emit_metric("last_violation", "ok")
                return
            if path == "/history":
                n_raw = (query.get("n") or [str(HISTORY_DEFAULT_N)])[0]
                try:
                    n = int(n_raw)
                except ValueError:
                    n = HISTORY_DEFAULT_N
                self._send_json(200, _history_payload(n))
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
            "available": [
                "/version", "/status", "/last-violation",
                "/history?n=N", "/webapp/", "/healthz",
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
            "error": "read-only surface — neutralization is "
                     "sovereignty-critical and stays CCD-triggered + "
                     "CLI-gated. The operator §17 sovereignty "
                     "boundary applies — the Tetragon kernel hook → "
                     "SIGKILL via guardian-core path is intentionally "
                     "NOT exposed via the API. Use the CCD-triggered "
                     "neutralization path or `sovereign-osctl "
                     "auditor` from the CLI surface instead. "
                     "Remediation: invoke the CLI directly — no "
                     "mutation routes exist on this daemon.",
            "allowed": ["GET", "HEAD"],
            "cli_gated_verbs": ["neutralize", "kill", "purge"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] auditor-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_CORE_PATH}", flush=True)
    print(f"  audit log:   {AUDIT_LOG}", flush=True)
    print(
        f"  endpoints:   /version /status /last-violation /history "
        f"/webapp/ + /healthz",
        flush=True,
    )
    print(f"  webapp:      {WEBAPP_PATH}", flush=True)
    print(
        "  sovereignty: neutralization stays CCD-triggered + CLI-only "
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
        httpd = HTTPServer((bind, port), AuditorAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] auditor-api shutdown requested.", flush=True)
        httpd.server_close()
    return 0


def main(argv: list[str]) -> int:
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    if "--version" in argv:
        print(json.dumps(_version_payload(), indent=2))
        return 0
    return serve()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
