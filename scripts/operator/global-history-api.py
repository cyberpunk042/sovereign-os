#!/usr/bin/env python3
"""
scripts/operator/global-history-api.py — Read-only HTTP API for the
global-history multi-source event surface (R510, E11.M5++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

This ships the `api` surface of the §1g 8-surface delivery ladder for
the `global-history` module. The CLI (`sovereign-osctl global-history
<verb>`) already covers ad-hoc operator queries; this API surface
gives OTHER consumers (the upcoming MCP server, the upcoming webapp
tier-3 shell, automation scripts, monitoring, the master-dashboard
/history subpath) a stable wire contract.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1)
  - Read-only verbs only — global-history is a query surface; the
    underlying logs (apt / dpkg / shell / osctl / events / modules)
    are mutated by other processes, never by this surface. The R510
    daemon also replaces the prior surface-map waiver
    `service: "not applicable — query surface, read-only"` — the
    daemon IS a real service, just a read-only one.

Read-only endpoints (R510 v1):
  GET /version                     — service version + module identity
  GET /sources                     — enumerate KNOWN_SOURCES with
                                     path/exists status (mirrors
                                     `global-history sources`)
  GET /recent[?since=&source=&limit=]
                                   — recent events across sources
                                     (mirrors `global-history recent`)
  GET /summary                     — 7-day per-source summary (mirrors
                                     `global-history summary`)
  GET /delta?since=ISO[&source=]   — events since timestamp (mirrors
                                     `global-history delta`)
  GET /healthz                     — API daemon liveness (always 200)

Layer-B metric (sister to the CLI's `_query_total{verb,source,result}`):

  sovereign_os_operator_global_history_api_request_total{endpoint,result}

Env vars (all overridable):
  GLOBAL_HISTORY_API_BIND        (default: 127.0.0.1)
  GLOBAL_HISTORY_API_PORT        (default: 8094)
  SOVEREIGN_OS_METRICS_DIR       (default: /var/lib/node_exporter/textfile_collector)
  GLOBAL_HISTORY_API_DRY_RUN     (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("GLOBAL_HISTORY_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("GLOBAL_HISTORY_API_PORT", "8094"))
DRY_RUN = bool(os.environ.get("GLOBAL_HISTORY_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_global_history_api_request_total
#   global-history read-only REST API request count (endpoint, result).
# TYPE sovereign_os_operator_global_history_api_request_total counter
METRIC_NAME = "sovereign_os_operator_global_history_api_request_total"

API_VERSION = "1.0.0-R510"

# global-history CLI module — import directly so the API serves from
# the SAME data model the operator-facing CLI uses (no drift).
_THIS_DIR = Path(__file__).resolve().parent
_GH_PATH = _THIS_DIR / "global-history.py"
_spec = importlib.util.spec_from_file_location("_gh_core", _GH_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load global-history.py "
        f"from {_GH_PATH}\n"
    )
    sys.exit(1)
_gh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gh)


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
            METRICS_DIR, "sovereign-os-global-history-api.prom"
        )
        line = (
            f"{METRIC_NAME}{{endpoint=\"{endpoint}\","
            f"result=\"{result}\"}} 1\n"
        )
        with open(prom_path, "a") as f:
            f.write(line)
    except OSError:
        pass


def _parse_sources(raw: str | None) -> list[str]:
    if not raw:
        return list(_gh.KNOWN_SOURCES)
    if raw == "all":
        return list(_gh.KNOWN_SOURCES)
    out = [s.strip() for s in raw.split(",") if s.strip()]
    return out or list(_gh.KNOWN_SOURCES)


def _sources_payload() -> dict:
    """Mirror of cmd_sources output (no argparse path)."""
    path_map = {
        "apt": _gh.APT_LOG,
        "dpkg": _gh.DPKG_LOG,
        "shell": _gh.SHELL_HISTORY,
        "osctl": _gh.OSCTL_HISTORY_DIR,
        "events": _gh.EVENTS_DIR,
        "modules": _gh.MODULES_LOG,
    }
    out = []
    for s in _gh.KNOWN_SOURCES:
        p = path_map[s]
        out.append({
            "source": s,
            "path": str(p),
            "exists": p.exists(),
            "is_dir": p.is_dir(),
            "is_file": p.is_file(),
        })
    return {"sources": out}


def _recent_payload(since: str, sources_raw: str | None,
                    limit: int) -> dict:
    since_dt = _gh.parse_since(since)
    sources = _parse_sources(sources_raw)
    events = _gh.collect(since_dt, sources)
    events = events[:limit]
    return {
        "since": since_dt.isoformat(),
        "sources": sources,
        "limit": limit,
        "count": len(events),
        "events": events,
    }


def _summary_payload() -> dict:
    sources = list(_gh.KNOWN_SOURCES)
    since = datetime.now(timezone.utc) - timedelta(days=7)
    out = {}
    for s in sources:
        reader = _gh.SOURCE_READERS.get(s)
        if not reader:
            continue
        events = reader(since)
        last = max((e["timestamp"] for e in events), default=None)
        out[s] = {
            "count_7d": len(events),
            "last_event": last,
            "available": last is not None or len(events) > 0,
        }
    return {"window_days": 7, "sources": out}


def _delta_payload(since_iso: str, sources_raw: str | None) -> dict:
    since_dt = _gh.parse_since(since_iso)
    sources = _parse_sources(sources_raw)
    events = _gh.collect(since_dt, sources)
    return {
        "since": since_dt.isoformat(),
        "sources": sources,
        "count": len(events),
        "events": events,
    }


def _version_payload() -> dict:
    return {
        "module": "global-history-api",
        "version": API_VERSION,
        "shipped_in": (
            "R510 (E11.M5++ read-only REST API + systemd service)"
        ),
        "source": "scripts/operator/global-history-api.py",
        "data_source": str(_GH_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard", "api", "service",
        ],
        "known_sources": list(_gh.KNOWN_SOURCES),
        "standing_rule": "We do not minimize anything.",
    }


class GlobalHistoryAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-global-history-api/{API_VERSION}"
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
        self.send_header("X-Sovereign-Module", "global-history-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/healthz" or path == "/":
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return

        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/sources":
                self._send_json(200, _sources_payload())
                _emit_metric("sources", "ok")
                return
            if path == "/recent":
                since = qs.get("since", ["24h"])[0]
                sources_raw = qs.get("source", [None])[0]
                try:
                    limit = int(qs.get("limit", ["200"])[0])
                except ValueError:
                    self._send_json(400, {
                        "error": "limit must be an integer",
                    })
                    _emit_metric("recent", "400")
                    return
                self._send_json(
                    200, _recent_payload(since, sources_raw, limit)
                )
                _emit_metric("recent", "ok")
                return
            if path == "/summary":
                self._send_json(200, _summary_payload())
                _emit_metric("summary", "ok")
                return
            if path == "/delta":
                since_iso = qs.get("since", [None])[0]
                if not since_iso:
                    self._send_json(400, {
                        "error": "missing required ?since=<ISO timestamp> "
                                 "query parameter",
                    })
                    _emit_metric("delta", "400")
                    return
                sources_raw = qs.get("source", [None])[0]
                self._send_json(
                    200, _delta_payload(since_iso, sources_raw)
                )
                _emit_metric("delta", "ok")
                return
        except ValueError as e:
            self._send_json(400, {"error": str(e)})
            _emit_metric(
                path.lstrip("/").replace("-", "_").replace("/", "_")
                or "unknown",
                "400",
            )
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
            "available": ["/version", "/sources", "/recent", "/summary",
                          "/delta", "/healthz"],
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
            "error": "read-only surface — global-history has no mutation "
                     "verbs at any surface (operator §17 sovereignty "
                     "boundary). The underlying logs (apt / dpkg / shell "
                     "/ osctl / events / modules) are mutated by their "
                     "owning processes, never by this surface.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] global-history-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_GH_PATH}", flush=True)
    print(f"  endpoints:   /version /sources /recent /summary /delta "
          f"+ /healthz", flush=True)
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
        httpd = HTTPServer((bind, port), GlobalHistoryAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — "
            f"{e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] global-history-api shutdown requested.", flush=True)
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
