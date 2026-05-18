#!/usr/bin/env python3
"""scripts/operator/global-history.py — R448 (E11.M5).

Operator §1g verbatim:
  "Some kind of global history too. tracking things happening, delta,
   differentials... apt changes and operations, or any cli or tool call
   I guess, in the management. more reliable and adapted than simply
   aggregating the .bash_history's."

The §1g surface for "what happened on this system in the last N
hours/days?" — a unified read-only operator-discoverable view across
multiple state-recording sources.

Sources aggregated (operator-discoverable; --source <name> filters):
  1. apt       — /var/log/apt/history.log (install/remove/upgrade
                  operations with timestamps + initiator user)
  2. dpkg      — /var/log/dpkg.log (lower-level package state changes)
  3. shell     — ~/.bash_history with timestamps when HISTTIMEFORMAT
                  was set during the writes (operator-discoverable
                  fallback to file-mtime if no timestamps embedded)
  4. osctl     — ~/.sovereign-os/history/*.jsonl (every sovereign-osctl
                  invocation when the operator has shipped the
                  per-call logger; sentinel-aware)
  5. events    — cross-cutting JSONL state files (notify-events,
                  models-eval, fine-tune — same sources `osctl events`
                  reads from); included here for the unified surface
  6. modules   — selfdef + sovereign-os module install/uninstall
                  events (when selfdef event-log surface ships)

Distinct from:
  - `sovereign-osctl history` — build-run log viewer (BUILD pipeline)
  - `sovereign-osctl events` — JSONL state-file aggregator (Layer A
                                cross-cutting)
  - `sovereign-osctl journal` — systemd-journal viewer (Layer B)

This is the §1g "operator-discoverable: what changed in the last N
hours/days?" surface. Single coherent view; per-source filterable.

CLI:
  global-history.py recent [--since <iso|relative>] [--limit N]
                            [--source <s1,s2,...>] [--json|--human]
                            Chronological recent-events view.
                            Default: --since=24h, --limit=50.

  global-history.py summary [--source <s1,s2,...>] [--json|--human]
                            Per-source count + last-event timestamp.
                            Operator's "is each source live?" answer.

  global-history.py sources [--json|--human]
                            List the 6 known sources + their status
                            (available, last-write timestamp, count
                            of entries in the last 24h).

  global-history.py delta <since-iso> [--source ...] [--json|--human]
                            Delta view: events since the given
                            timestamp. Operator-discoverable for
                            "what happened since I last checked?"

Exit codes:
  0 ok
  1 unknown subcommand / source / no sources available
  2 argument parse error

Layer B metric (SDD-016):
  sovereign_os_operator_global_history_query_total{verb,source,result}
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

# Operator-named source taxonomy
KNOWN_SOURCES = ["apt", "dpkg", "shell", "osctl", "events", "modules"]

# Source path defaults (operator-overridable via env)
APT_LOG = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_GLOBAL_HISTORY_APT_LOG",
    "/var/log/apt/history.log"
))
DPKG_LOG = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_GLOBAL_HISTORY_DPKG_LOG",
    "/var/log/dpkg.log"
))
SHELL_HISTORY = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_GLOBAL_HISTORY_SHELL",
    os.path.expanduser("~/.bash_history")
))
OSCTL_HISTORY_DIR = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_GLOBAL_HISTORY_OSCTL_DIR",
    os.path.expanduser("~/.sovereign-os/history")
))
EVENTS_DIR = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_GLOBAL_HISTORY_EVENTS_DIR",
    os.path.expanduser("~/.sovereign-os/state")
))
MODULES_LOG = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_GLOBAL_HISTORY_MODULES_LOG",
    "/var/log/sovereign-os/modules.jsonl"
))

# Metrics output dir
METRICS_DIR = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
))
DRY_RUN = bool(os.environ.get("SOVEREIGN_OS_DRY_RUN"))


# Metric name (operator-discoverable; matches docs/observability/dashboards/README.md
# inventory and tests/lint/test_metric_inventory_lockstep.py emit detection)
_METRIC_NAME = "sovereign_os_operator_global_history_query_total"


def _emit_metric(name: str, verb: str, source: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises.

    Signature mirrors the established Python emitter pattern in
    scripts/weaver/atomic-state.py + scripts/auditor/guardian-core.py
    so the metric-inventory-lockstep lint detects the metric name."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {name}"
            f"{{verb=\"{verb}\",source=\"{source}\",result=\"{result}\"}} 1\n"
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-operator-global-history.prom"
        line = (
            f'{name}'
            f'{{verb="{verb}",source="{source}",result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


def parse_since(since: str) -> datetime:
    """Operator-friendly: accept ISO 8601 OR relative like '24h', '7d'."""
    if not since:
        return datetime.now(timezone.utc) - timedelta(hours=24)
    if re.match(r"^\d+[hdwm]$", since):
        n = int(since[:-1])
        unit = since[-1]
        delta = {
            "h": timedelta(hours=n),
            "d": timedelta(days=n),
            "w": timedelta(weeks=n),
            "m": timedelta(days=n * 30),  # operator-approximate "month"
        }[unit]
        return datetime.now(timezone.utc) - delta
    # Try ISO 8601
    try:
        dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        sys.stderr.write(f"error: cannot parse --since={since!r}\n")
        sys.stderr.write(
            "  accepted: ISO 8601 (2026-05-18T10:00:00Z) "
            "or relative (24h, 7d, 2w, 1m)\n"
        )
        sys.exit(2)


# -------------------- source readers --------------------


def _read_apt(since: datetime) -> list[dict]:
    """Parse /var/log/apt/history.log apt event blocks.

    Each event block is shaped like:
        Start-Date: 2026-05-15  10:23:14
        Commandline: apt install ...
        Install: foo:amd64 (1.2.3, automatic)
        End-Date: 2026-05-15  10:23:18
    """
    if not APT_LOG.is_file():
        return []
    events = []
    block: dict[str, str] = {}
    try:
        for line in APT_LOG.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            line = line.strip()
            if not line:
                if block.get("Start-Date"):
                    events.append(block)
                    block = {}
                continue
            if ":" in line:
                k, _, v = line.partition(":")
                block[k.strip()] = v.strip()
        if block.get("Start-Date"):
            events.append(block)
    except OSError:
        return []

    out = []
    for b in events:
        sd = b.get("Start-Date", "")
        try:
            dt = datetime.strptime(sd, "%Y-%m-%d  %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        if dt < since:
            continue
        action = "unknown"
        detail = ""
        for k in ("Install", "Remove", "Upgrade", "Purge", "Downgrade"):
            if k in b:
                action = k.lower()
                detail = b[k][:120]
                break
        out.append({
            "source": "apt",
            "timestamp": dt.isoformat(),
            "action": action,
            "commandline": b.get("Commandline", "")[:200],
            "detail": detail,
        })
    return out


def _read_dpkg(since: datetime) -> list[dict]:
    """Parse /var/log/dpkg.log (one event per line)."""
    if not DPKG_LOG.is_file():
        return []
    out = []
    try:
        for line in DPKG_LOG.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            # Format: 2026-05-15 10:23:15 status installed foo:amd64 1.2.3-1
            m = re.match(
                r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(.+)$",
                line,
            )
            if not m:
                continue
            try:
                dt = datetime.strptime(
                    m.group(1), "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if dt < since:
                continue
            out.append({
                "source": "dpkg",
                "timestamp": dt.isoformat(),
                "action": m.group(2),
                "detail": m.group(3)[:200],
            })
    except OSError:
        return []
    return out


def _read_shell(since: datetime) -> list[dict]:
    """Read bash history. If HISTTIMEFORMAT was set, the file has
    interleaved timestamp lines (#<unix-epoch>) before each command;
    otherwise we fall back to file-mtime + line-order ordering."""
    if not SHELL_HISTORY.is_file():
        return []
    out = []
    try:
        lines = SHELL_HISTORY.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except OSError:
        return []
    pending_ts = None
    for raw in lines:
        ts_match = re.match(r"^#(\d+)$", raw)
        if ts_match:
            try:
                pending_ts = datetime.fromtimestamp(
                    int(ts_match.group(1)), tz=timezone.utc
                )
            except (ValueError, OSError):
                pending_ts = None
            continue
        if not raw.strip():
            continue
        ts = pending_ts or datetime.fromtimestamp(
            SHELL_HISTORY.stat().st_mtime, tz=timezone.utc
        )
        pending_ts = None
        if ts < since:
            continue
        out.append({
            "source": "shell",
            "timestamp": ts.isoformat(),
            "action": "exec",
            "detail": raw[:200],
            "timestamps_embedded": ts_match is not None,
        })
    return out


def _read_jsonl_dir(dir_path: pathlib.Path, source_name: str,
                     since: datetime) -> list[dict]:
    if not dir_path.is_dir():
        return []
    out = []
    for f in sorted(dir_path.glob("*.jsonl")):
        try:
            for line in f.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = obj.get("timestamp") or obj.get("ts")
                if not ts_str:
                    continue
                try:
                    dt = datetime.fromisoformat(
                        str(ts_str).replace("Z", "+00:00")
                    )
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if dt < since:
                    continue
                out.append({
                    "source": source_name,
                    "timestamp": dt.isoformat(),
                    "action": obj.get("action") or obj.get("event")
                              or obj.get("verb") or "event",
                    "detail": json.dumps(obj)[:200],
                })
        except OSError:
            continue
    return out


def _read_osctl(since: datetime) -> list[dict]:
    return _read_jsonl_dir(OSCTL_HISTORY_DIR, "osctl", since)


def _read_events(since: datetime) -> list[dict]:
    return _read_jsonl_dir(EVENTS_DIR, "events", since)


def _read_modules(since: datetime) -> list[dict]:
    """Modules log: single JSONL file."""
    if not MODULES_LOG.is_file():
        return []
    parent = MODULES_LOG.parent
    if not parent.is_dir():
        return []
    out = []
    try:
        for line in MODULES_LOG.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_str = obj.get("timestamp") or obj.get("ts")
            if not ts_str:
                continue
            try:
                dt = datetime.fromisoformat(
                    str(ts_str).replace("Z", "+00:00")
                )
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if dt < since:
                continue
            out.append({
                "source": "modules",
                "timestamp": dt.isoformat(),
                "action": obj.get("event") or obj.get("action") or "module",
                "detail": json.dumps(obj)[:200],
            })
    except OSError:
        pass
    return out


SOURCE_READERS = {
    "apt": _read_apt,
    "dpkg": _read_dpkg,
    "shell": _read_shell,
    "osctl": _read_osctl,
    "events": _read_events,
    "modules": _read_modules,
}


def collect(since: datetime, sources: list[str]) -> list[dict]:
    """Aggregate across all requested sources, sorted by timestamp desc."""
    out = []
    for s in sources:
        reader = SOURCE_READERS.get(s)
        if reader:
            out.extend(reader(since))
    out.sort(key=lambda e: e["timestamp"], reverse=True)
    return out


# -------------------- CLI verbs --------------------


def cmd_recent(args) -> int:
    since = parse_since(args.since)
    sources = args.source.split(",") if args.source else KNOWN_SOURCES
    events = collect(since, sources)
    events = events[:args.limit]
    if args.fmt == "json":
        print(json.dumps({
            "since": since.isoformat(),
            "sources": sources,
            "limit": args.limit,
            "count": len(events),
            "events": events,
        }, indent=2))
    else:
        print(f"── global-history.recent since={since.isoformat()} "
              f"sources={','.join(sources)} count={len(events)} ──")
        for e in events:
            print(f"  {e['timestamp']}  [{e['source']:<8}] {e['action']:<10}  {e['detail'][:100]}")
    _emit_metric("sovereign_os_operator_global_history_query_total", "recent", ",".join(sources), "ok")
    return 0


def cmd_summary(args) -> int:
    sources = args.source.split(",") if args.source else KNOWN_SOURCES
    # 7-day window for summary
    since = datetime.now(timezone.utc) - timedelta(days=7)
    out = {}
    for s in sources:
        reader = SOURCE_READERS.get(s)
        if not reader:
            continue
        events = reader(since)
        last = max((e["timestamp"] for e in events), default=None)
        out[s] = {
            "count_7d": len(events),
            "last_event": last,
            "available": last is not None or len(events) > 0,
        }
    if args.fmt == "json":
        print(json.dumps({
            "window_days": 7,
            "sources": out,
        }, indent=2))
    else:
        print(f"── global-history.summary (7-day window) ──")
        print(f"  {'SOURCE':<10} {'COUNT':>6}  {'LAST EVENT':<30}")
        for s, info in out.items():
            print(f"  {s:<10} {info['count_7d']:>6}  {info['last_event'] or '(none)':<30}")
    _emit_metric("sovereign_os_operator_global_history_query_total", "summary", ",".join(sources), "ok")
    return 0


def cmd_sources(args) -> int:
    """Status of each known source: available + sample path."""
    out = []
    for s in KNOWN_SOURCES:
        path_map = {
            "apt": APT_LOG,
            "dpkg": DPKG_LOG,
            "shell": SHELL_HISTORY,
            "osctl": OSCTL_HISTORY_DIR,
            "events": EVENTS_DIR,
            "modules": MODULES_LOG,
        }
        p = path_map[s]
        out.append({
            "source": s,
            "path": str(p),
            "exists": p.exists(),
            "is_dir": p.is_dir(),
            "is_file": p.is_file(),
        })
    if args.fmt == "json":
        print(json.dumps({"sources": out}, indent=2))
    else:
        print(f"── global-history.sources ──")
        print(f"  {'SOURCE':<10} {'EXISTS':<8} {'PATH'}")
        for s in out:
            marker = "✓" if s["exists"] else "✗"
            print(f"  {s['source']:<10} {marker:<8} {s['path']}")
    _emit_metric("sovereign_os_operator_global_history_query_total", "sources", "all", "ok")
    return 0


def cmd_delta(args) -> int:
    """Delta: events since the given timestamp (operator-discoverable
    'what changed since I last checked')."""
    since = parse_since(args.since_iso)
    sources = args.source.split(",") if args.source else KNOWN_SOURCES
    events = collect(since, sources)
    if args.fmt == "json":
        print(json.dumps({
            "since": since.isoformat(),
            "count": len(events),
            "events": events,
        }, indent=2))
    else:
        print(f"── global-history.delta since={since.isoformat()} "
              f"count={len(events)} ──")
        for e in events:
            print(f"  {e['timestamp']}  [{e['source']:<8}] {e['action']:<10}  {e['detail'][:100]}")
    _emit_metric("sovereign_os_operator_global_history_query_total", "delta", ",".join(sources), "ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="global-history.py",
        description="R448 (E11.M5) — sovereign-os global history "
                     "(§1g delta/differential surface)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")
        sp.set_defaults(fmt="human")

    sp_recent = sub.add_parser("recent",
                                help="chronological recent events")
    sp_recent.add_argument("--since", default="24h",
                            help="ISO 8601 or relative (24h/7d/2w/1m); "
                                  "default: 24h")
    sp_recent.add_argument("--limit", type=int, default=50)
    sp_recent.add_argument("--source", default="",
                            help="comma-separated source filter")
    add_fmt(sp_recent)

    sp_summary = sub.add_parser("summary",
                                 help="per-source count + last event")
    sp_summary.add_argument("--source", default="")
    add_fmt(sp_summary)

    sp_sources = sub.add_parser("sources",
                                 help="enumerate known sources + status")
    add_fmt(sp_sources)

    sp_delta = sub.add_parser("delta",
                               help="delta view since timestamp")
    sp_delta.add_argument("since_iso",
                           help="ISO 8601 or relative")
    sp_delta.add_argument("--source", default="")
    add_fmt(sp_delta)

    args = p.parse_args(argv)

    if args.cmd == "recent":
        return cmd_recent(args)
    if args.cmd == "summary":
        return cmd_summary(args)
    if args.cmd == "sources":
        return cmd_sources(args)
    if args.cmd == "delta":
        return cmd_delta(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
