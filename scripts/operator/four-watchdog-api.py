#!/usr/bin/env python3
"""scripts/operator/four-watchdog-api.py — read-only HTTP API host for
the four-watchdog (IPS spine) observability surface.

CROSS-REPO MIRROR — parses node_exporter's `/metrics` exposition for
the `selfdef_four_watchdog_*` gauges shipped by the selfdef-side
wrapper at `packaging/scripts/four-watchdog-textfile.sh` (selfdef
commits `7869a45` + `a009b39`). Emits a compact JSON envelope the
master-dashboard's four-watchdog banner consumes.

Project boundary R10212: pure observability proxy. The enforcement
(the 4 watchdogs themselves + their alert classifier) lives in
selfdefd; this script never mutates anything.

Endpoints (the exact contract webapp/master-dashboard/index.html fetches):
  GET /api/four-watchdog/state    full state envelope
  GET /version | /healthz | /

State derivation (matches the 4 sovereign-os alert rules):
  - ok                   worst_severity == 0  AND emit_failed == 0
  - warn                 worst_severity == 1  AND emit_failed == 0
  - critical             worst_severity >= 2  AND emit_failed == 0
  - observer-fault       emit_failed > 0  OR  observer-age > 300
  - unreachable          this script could not reach node_exporter

The observer-fault state takes precedence over rollup-severity per
the wrapper's honest-offline contract: when emit_failed=1 OR the
observer is silent, the other gauges cannot be trusted as fresh.

Sovereignty: stdlib-only. Absent metric → unreachable envelope
(graceful), never a crash.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

API_VERSION = "1.0.0"
API_BIND = os.environ.get("FOUR_WATCHDOG_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("FOUR_WATCHDOG_API_PORT", "7712"))
DRY_RUN = bool(os.environ.get("FOUR_WATCHDOG_API_DRY_RUN"))

NODE_EXPORTER_URL = os.environ.get(
    "NODE_EXPORTER_URL", "http://localhost:9100/metrics",
)

# Severity ladder — locked by the cross-surface threshold-lockstep
# contract test. Drift here = page severity ≠ banner color.
SEVERITY_OK = 0
SEVERITY_WARN = 1
SEVERITY_CRITICAL = 2
SEVERITY_UNKNOWN = -1

# Observer-silent threshold (matches the alert rule + the M060 chain
# stale-age threshold — locked by the cross-surface threshold-lockstep
# contract test).
OBSERVER_SILENT_THRESHOLD_SECS = 300


def _fetch_metrics_text() -> str | None:
    """Fetch node_exporter's /metrics body. Returns None when
    unreachable — banner renders 'unreachable' state in that case."""
    try:
        with urllib.request.urlopen(NODE_EXPORTER_URL, timeout=3) as r:
            return r.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError,
            ConnectionError, OSError):
        return None


_METRIC_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)(?:\{([^}]*)\})?\s+([0-9.eE+\-]+)$"
)


def _parse_metrics(body: str) -> dict[str, Any]:
    """Extract the 4 canonical four-watchdog gauges from a Prometheus
    exposition body. Missing metrics fall back to None so the banner
    renders 'unknown' rather than a fabricated zero."""
    out: dict[str, Any] = {
        "worst_severity": None,
        "last_run_unix": None,
        "textfile_emit_failed": None,
        "per_alert": [],  # [{alert, ms, series, severity}, ...]
    }
    for line in body.splitlines():
        if not line or line.startswith("#"):
            continue
        m = _METRIC_RE.match(line)
        if m is None:
            continue
        name, labels_str, value_str = m.group(1), m.group(2), m.group(3)
        try:
            value = float(value_str)
        except ValueError:
            continue
        if name == "selfdef_four_watchdog_worst_severity":
            out["worst_severity"] = int(value)
        elif name == "selfdef_four_watchdog_last_run_unix":
            out["last_run_unix"] = int(value)
        elif name == "selfdef_four_watchdog_textfile_emit_failed":
            out["textfile_emit_failed"] = int(value)
        elif name == "selfdef_four_watchdog_severity":
            labels = _parse_labels(labels_str or "")
            out["per_alert"].append({
                "alert":    labels.get("alert", ""),
                "ms":       labels.get("ms", ""),
                "series":   labels.get("series", ""),
                "severity": int(value),
            })
    out["per_alert"].sort(key=lambda r: (r["ms"], r["alert"]))
    return out


def _parse_labels(labels_str: str) -> dict[str, str]:
    """Trivial label-parser for Prometheus exposition's
    `{name="value",other="x"}` shape. Stdlib-only."""
    out: dict[str, str] = {}
    for part in labels_str.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip().strip('"')
    return out


def _classify_state(metrics: dict[str, Any], now_unix: int) -> str:
    """Derive the banner state from the gauges. Observer-fault takes
    precedence over rollup-severity per the honest-offline contract."""
    emit_failed = metrics.get("textfile_emit_failed")
    last_run = metrics.get("last_run_unix")
    worst = metrics.get("worst_severity")

    # Observer-fault paths take precedence.
    if emit_failed is not None and emit_failed > 0:
        return "observer-fault"
    if last_run is not None and (now_unix - last_run) > OBSERVER_SILENT_THRESHOLD_SECS:
        return "observer-fault"

    # Rollup-severity classification.
    if worst is None:
        return "unknown"
    if worst >= SEVERITY_CRITICAL:
        return "critical"
    if worst == SEVERITY_WARN:
        return "warn"
    if worst == SEVERITY_OK:
        return "ok"
    return "unknown"


def _build_envelope() -> dict[str, Any]:
    """Build the JSON envelope the banner + dashboard consume."""
    import time as _time
    now = int(_time.time())
    body = _fetch_metrics_text()
    if body is None:
        return {
            "state": "unreachable",
            "metrics": None,
            "thresholds": {
                "observer_silent_secs": OBSERVER_SILENT_THRESHOLD_SECS,
                "severity_critical_min": SEVERITY_CRITICAL,
            },
            "version": API_VERSION,
        }
    metrics = _parse_metrics(body)
    state = _classify_state(metrics, now)
    age = (
        now - metrics["last_run_unix"]
        if metrics["last_run_unix"] is not None
        else None
    )
    return {
        "state": state,
        "metrics": {
            "worst_severity": metrics["worst_severity"],
            "last_run_unix": metrics["last_run_unix"],
            "observer_age_seconds": age,
            "textfile_emit_failed": metrics["textfile_emit_failed"],
            "per_alert": metrics["per_alert"],
        },
        "thresholds": {
            "observer_silent_secs": OBSERVER_SILENT_THRESHOLD_SECS,
            "severity_critical_min": SEVERITY_CRITICAL,
        },
        "version": API_VERSION,
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        # Quiet by default; systemd journal captures stderr.
        sys.stderr.write("four-watchdog-api: " + (fmt % args) + "\n")

    def _send_json(self, payload: dict[str, Any], code: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 — http.server protocol
        path = self.path.split("?", 1)[0]
        if path == "/api/four-watchdog/state":
            self._send_json(_build_envelope())
        elif path == "/healthz":
            self._send_json({"status": "ok", "version": API_VERSION})
        elif path == "/version":
            self._send_json({
                "version": API_VERSION,
                "states": [
                    "ok", "warn", "critical",
                    "observer-fault", "unreachable", "unknown",
                ],
                "thresholds": {
                    "observer_silent_secs": OBSERVER_SILENT_THRESHOLD_SECS,
                    "severity_critical_min": SEVERITY_CRITICAL,
                },
            })
        elif path == "/":
            self._send_json({
                "service": "four-watchdog-api",
                "version": API_VERSION,
                "endpoints": [
                    "/api/four-watchdog/state",
                    "/version", "/healthz", "/",
                ],
            })
        else:
            self._send_json({"error": "not found"}, code=404)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--bind", default=API_BIND,
        help="bind address (default 127.0.0.1; honors $FOUR_WATCHDOG_API_BIND)",
    )
    p.add_argument(
        "--port", type=int, default=API_PORT,
        help="bind port (default 7712; honors $FOUR_WATCHDOG_API_PORT)",
    )
    p.add_argument(
        "--print-once", action="store_true",
        help="print the envelope to stdout once and exit (for testing / CI)",
    )
    args = p.parse_args(argv)

    if args.print_once:
        print(json.dumps(_build_envelope(), indent=2))
        return 0
    if DRY_RUN:
        print(f"DRY_RUN: would bind {args.bind}:{args.port}")
        return 0

    srv = ThreadingHTTPServer((args.bind, args.port), _Handler)
    sys.stderr.write(
        f"four-watchdog-api: listening on http://{args.bind}:{args.port}\n"
    )
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
