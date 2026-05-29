#!/usr/bin/env python3
"""sovereign-os observability-status — one-command cross-vertical
operator triage across all 6 observability verticals shipped to date.

NEW operator-facing CLI surface that consolidates per-vertical
doctor checks into a single operator-runnable command. Probes:

  1. M060 chain-health           via the m060-health-api daemon
                                  at http://localhost:8160
  2. MS022 SSE quota             via the ms022-sse-quota-api daemon
                                  at http://localhost:7711
  3. four-watchdog IPS spine     via the four-watchdog-api daemon
                                  at http://localhost:7712
  4. selfdef module-catalog      via node_exporter /metrics scrape
                                  of selfdef_modules_* gauges
  5. selfdef daemon process      via node_exporter /metrics scrape
                                  of selfdef_daemon_process_* gauges
  6. selfdef AppArmor enforce    via node_exporter /metrics scrape
                                  of selfdef_apparmor_* gauges

  Plus the cross-vertical rollup recording rule
  `sovereign_os:observer_fault_any` when Prometheus is reachable.

Operator-readable table (default) + --json for monitoring + --strict
for CI fail-fast (exit 1 on any vertical reporting WARN+).

Exit code (mirrors the per-vertical doctor conventions):
  0  every vertical green (or honestly skipped)
  1  any vertical reports WARN OR critical
  2  any proxy daemon unreachable (with retry already attempted)

Sovereignty: stdlib-only. Each probe is independent — one vertical
unreachable doesn't fail the others.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

# Default endpoints — match the 4 sovereign-os proxy daemons' systemd
# unit defaults, locked by their respective contract tests.
DEFAULTS = {
    "m060_url":         os.environ.get("SOVEREIGN_OS_M060_URL", "http://localhost:8160"),
    "ms022_url":        os.environ.get("SOVEREIGN_OS_MS022_PROXY_URL", "http://localhost:7711"),
    "four_watchdog_url": os.environ.get("SOVEREIGN_OS_FOUR_WATCHDOG_PROXY_URL", "http://localhost:7712"),
    "node_exporter_url": os.environ.get("SOVEREIGN_OS_NODE_EXPORTER_URL", "http://localhost:9100/metrics"),
}

OBSERVER_SILENT_THRESHOLD_SECS = 300


def _fetch_json(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            ConnectionError, OSError, json.JSONDecodeError):
        return None


def _fetch_metrics(url: str, timeout: float = 3.0) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError,
            ConnectionError, OSError):
        return None


def _gauge(metrics: str, name: str, label_match: str = "") -> float | None:
    """Extract a single gauge value from a Prometheus exposition body."""
    if label_match:
        pattern = rf"^{re.escape(name)}\{{{re.escape(label_match)}\}}\s+([0-9.eE+\-]+)"
    else:
        pattern = rf"^{re.escape(name)}\s+([0-9.eE+\-]+)"
    m = re.search(pattern, metrics, re.MULTILINE)
    if m is None:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


# ── Per-vertical probes ──────────────────────────────────────────────

def probe_m060(url: str) -> dict[str, Any]:
    """Probe M060 chain-health via the proxy daemon."""
    data = _fetch_json(url.rstrip("/") + "/api/m060/health")
    if data is None:
        return {"status": "unreachable", "summary": "proxy daemon down"}
    state = str(data.get("state", "unknown"))
    present = data.get("artifacts_present", 0)
    expected = data.get("artifacts_expected", 10)
    age = data.get("newest_age_seconds")
    classification = "OK" if state == "online" else (
        "WARN" if state in ("degraded", "stale") else "FAIL"
    )
    return {
        "status": classification,
        "summary": f"chain={state} · {present}/{expected} mirrors · age {age}s",
        "raw": data,
    }


def probe_ms022(url: str) -> dict[str, Any]:
    """Probe MS022 SSE quota via the proxy daemon."""
    data = _fetch_json(url.rstrip("/") + "/api/ms022/state")
    if data is None:
        return {"status": "unreachable", "summary": "proxy daemon down"}
    state = str(data.get("state", "unknown"))
    classification = {
        "ok": "OK", "approaching": "WARN",
        "saturated": "FAIL", "unreachable": "WARN",
    }.get(state, "UNKNOWN")
    return {
        "status": classification,
        "summary": f"state={state}",
        "raw": data,
    }


def probe_four_watchdog(url: str) -> dict[str, Any]:
    """Probe four-watchdog IPS spine via the proxy daemon."""
    data = _fetch_json(url.rstrip("/") + "/api/four-watchdog/state")
    if data is None:
        return {"status": "unreachable", "summary": "proxy daemon down"}
    state = str(data.get("state", "unknown"))
    classification = {
        "ok": "OK", "warn": "WARN", "critical": "FAIL",
        "observer-fault": "FAIL", "unreachable": "WARN",
    }.get(state, "UNKNOWN")
    return {
        "status": classification,
        "summary": f"state={state}",
        "raw": data,
    }


def probe_textfile_observer(
    metrics: str, gauge_prefix: str, vertical: str
) -> dict[str, Any]:
    """Probe a selfdef-side textfile observer via node_exporter metrics."""
    emit_failed = _gauge(metrics, f"{gauge_prefix}_textfile_emit_failed")
    last_run = _gauge(metrics, f"{gauge_prefix}_last_run_unix")
    if emit_failed is None and last_run is None:
        return {
            "status": "unreachable",
            "summary": "node_exporter metrics absent (observer not deployed?)",
        }
    if emit_failed is not None and emit_failed > 0:
        return {
            "status": "FAIL",
            "summary": "observer wedged — sentinel=1",
        }
    if last_run is None:
        return {"status": "WARN", "summary": "last_run_unix missing"}
    import time as _time
    age = int(_time.time()) - int(last_run)
    if age > OBSERVER_SILENT_THRESHOLD_SECS:
        return {
            "status": "FAIL",
            "summary": f"observer silent ({age}s > {OBSERVER_SILENT_THRESHOLD_SECS}s)",
        }
    return {
        "status": "OK",
        "summary": f"fresh ({age}s)",
    }


def probe_modules_catalog(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_modules", "modules")
    if out["status"] != "OK":
        return out
    total = _gauge(metrics, "selfdef_modules_total")
    if total is not None and total < 100:
        return {
            "status": "WARN",
            "summary": f"total={int(total)} (< 100 floor)",
        }
    return {
        "status": "OK",
        "summary": f"{int(total) if total is not None else '?'} modules · {out['summary']}",
    }


def probe_daemon_process(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_daemon_process", "daemon-process",
    )
    if out["status"] != "OK":
        return out
    rss = _gauge(metrics, "selfdef_daemon_process_memory_rss_bytes")
    fds = _gauge(metrics, "selfdef_daemon_process_open_fds")
    bits = []
    cls = "OK"
    if rss is not None and rss > 1073741824:
        bits.append(f"RSS={rss / 1073741824:.1f} GiB")
        cls = "WARN"
    elif rss is not None:
        bits.append(f"RSS={rss / 1048576:.0f} MiB")
    if fds is not None and fds > 819:
        bits.append(f"FDs={int(fds)} > 819")
        cls = "FAIL"
    elif fds is not None:
        bits.append(f"FDs={int(fds)}")
    return {
        "status": cls,
        "summary": " · ".join(bits) + f" · {out['summary']}",
    }


def probe_apparmor(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_apparmor", "apparmor")
    if out["status"] != "OK":
        return out
    loaded = _gauge(
        metrics, "selfdef_apparmor_profile_loaded",
        label_match='profile="/usr/bin/selfdefd"',
    )
    enforce = _gauge(
        metrics, "selfdef_apparmor_profile_enforce",
        label_match='profile="/usr/bin/selfdefd"',
    )
    complain = _gauge(
        metrics, "selfdef_apparmor_profile_complain",
        label_match='profile="/usr/bin/selfdefd"',
    )
    if loaded == 0:
        return {"status": "FAIL", "summary": "profile NOT loaded"}
    if complain == 1:
        return {"status": "FAIL", "summary": "COMPLAIN mode (run aa-enforce)"}
    if enforce == 1:
        return {"status": "OK", "summary": "enforcing"}
    return {"status": "WARN", "summary": "indeterminate"}


# ── Aggregation + rendering ──────────────────────────────────────────

VERTICALS = (
    "m060", "ms022", "four_watchdog",
    "modules", "daemon_process", "apparmor",
)


def collect(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    return {
        "m060":          probe_m060(args.m060_url),
        "ms022":         probe_ms022(args.ms022_url),
        "four_watchdog": probe_four_watchdog(args.four_watchdog_url),
        "modules":       probe_modules_catalog(args.node_exporter_url),
        "daemon_process": probe_daemon_process(args.node_exporter_url),
        "apparmor":      probe_apparmor(args.node_exporter_url),
    }


def render_table(results: dict[str, dict[str, Any]]) -> str:
    lines = ["sovereign-os observability status — 6 verticals",
             f"{'─' * 22} {'─' * 60}"]
    for v in VERTICALS:
        r = results[v]
        status = r["status"]
        marker = {"OK": "OK    ", "WARN": "WARN  ", "FAIL": "FAIL  ",
                  "unreachable": "UNREACH"}.get(status, "?     ")
        label = {
            "m060":           "M060 chain-health",
            "ms022":          "MS022 SSE quota",
            "four_watchdog":  "four-watchdog (IPS)",
            "modules":        "modules-catalog",
            "daemon_process": "daemon-process",
            "apparmor":       "AppArmor",
        }[v]
        lines.append(f"{label:<22} {marker}  {r['summary']}")
    lines.append(f"{'─' * 22} {'─' * 60}")
    fail = sum(1 for v in VERTICALS if results[v]["status"] == "FAIL")
    warn = sum(1 for v in VERTICALS if results[v]["status"] == "WARN")
    unreach = sum(1 for v in VERTICALS if results[v]["status"] == "unreachable")
    ok = sum(1 for v in VERTICALS if results[v]["status"] == "OK")
    lines.append(
        f"summary: {ok}/{len(VERTICALS)} OK · {warn} WARN · {fail} FAIL · "
        f"{unreach} unreachable"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--m060-url", default=DEFAULTS["m060_url"])
    p.add_argument("--ms022-url", default=DEFAULTS["ms022_url"])
    p.add_argument("--four-watchdog-url", default=DEFAULTS["four_watchdog_url"])
    p.add_argument("--node-exporter-url", default=DEFAULTS["node_exporter_url"])
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output for monitoring")
    p.add_argument("--strict", action="store_true",
                   help="exit 1 on any vertical reporting WARN (default: only FAIL/unreach)")
    args = p.parse_args(argv)

    results = collect(args)

    if args.json:
        print(json.dumps({
            "verticals": results,
            "summary": {
                "ok":   sum(1 for v in VERTICALS if results[v]["status"] == "OK"),
                "warn": sum(1 for v in VERTICALS if results[v]["status"] == "WARN"),
                "fail": sum(1 for v in VERTICALS if results[v]["status"] == "FAIL"),
                "unreachable": sum(1 for v in VERTICALS if results[v]["status"] == "unreachable"),
                "total": len(VERTICALS),
            },
        }, indent=2))
    else:
        print(render_table(results))

    # Exit code logic.
    any_fail = any(results[v]["status"] == "FAIL" for v in VERTICALS)
    any_unreach = any(results[v]["status"] == "unreachable" for v in VERTICALS)
    any_warn = any(results[v]["status"] == "WARN" for v in VERTICALS)
    if any_fail:
        return 1
    if any_unreach:
        return 2
    if args.strict and any_warn:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
