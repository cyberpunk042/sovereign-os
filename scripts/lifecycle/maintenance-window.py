#!/usr/bin/env python3
"""scripts/lifecycle/maintenance-window.py — R323 (E2.M19).

Operator-named (§1b mandate row, verbatim): "schedule/planifest/
graceful on all levels, orderly". Closes E2.M19.

Operator declares named maintenance windows + cron-like schedule.
Other advisors / R308 autohealth / R318 heat-oc-throttle query
`can-run-now <window>` before mutating any state. Discipline:
NO graceful action fires outside its declared window unless the
operator passes an explicit `--force` (R308 + R318 already require
their own gates, so this is defense-in-depth).

CLI:
  maintenance-window.py list                  [--config P] [--json|--human]
  maintenance-window.py show       <window>   [--config P] [--json|--human]
  maintenance-window.py can-run-now <window>  [--config P] [--json|--human]
                                                rc=0 if window is active
                                                rc=1 if outside window
                                                rc=2 if unknown window
  maintenance-window.py active     [--config P] [--json|--human]
                                                list windows active now

Operator-overlay (R283/SDD-030):
/etc/sovereign-os/maintenance-window.toml
  [[windows]]
  name     = "<name>"
  axis     = "<axis>"      e.g. lifecycle / observability
  schedule = "<cron-like>"  e.g. "Tue 02:00-04:00 UTC"
  days     = ["Mon", "Tue"]  OR ["daily"]
  start    = "HH:MM"        local OR UTC per `timezone`
  end      = "HH:MM"
  timezone = "UTC" | "local"
  description = "<text>"

Defaults ship 3 named windows.

Exit codes:
  0  window active now (can-run-now) OR rendered (list/show/active)
  1  window inactive (can-run-now) OR unknown window
  2  usage error
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R323"
SDD_VECTOR = "E2.M19"


DEFAULT_WINDOWS: list[dict[str, Any]] = [
    {
        "name": "daily-light-touch",
        "axis": "lifecycle",
        "schedule": "daily 03:30-04:00 UTC",
        "days": ["daily"],
        "start": "03:30",
        "end": "04:00",
        "timezone": "UTC",
        "description": "Daily 30-min window for light-touch tasks "
                       "(log rotate, journal vacuum, R298 storage "
                       "cleanup, autohealth notify dispatch).",
    },
    {
        "name": "weekly-deep-maintenance",
        "axis": "lifecycle",
        "schedule": "Tue 02:00-04:00 UTC",
        "days": ["Tue"],
        "start": "02:00",
        "end": "04:00",
        "timezone": "UTC",
        "description": "Weekly 2-hour window for heavier maintenance "
                       "(R262 drain, R318 heat-OC throttle apply, "
                       "model swap, NVMe TRIM).",
    },
    {
        "name": "operator-on-call-only",
        "axis": "lifecycle",
        "schedule": "Mon-Fri 09:00-17:00 UTC",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "start": "09:00",
        "end": "17:00",
        "timezone": "UTC",
        "description": "Window for any action that REQUIRES operator "
                       "to be available (interactive prompts, BIOS "
                       "flash, physical OC switch flip per R313).",
    },
]


def load_state(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    windows = list(DEFAULT_WINDOWS)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "maintenance-window", {"windows": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("windows"):
            windows = list(loaded["windows"])
    return windows, meta


def _parse_hhmm(s: str) -> tuple[int, int] | None:
    try:
        h, m = s.split(":")
        return (int(h), int(m))
    except (ValueError, AttributeError):
        return None


def is_active(window: dict, now: dt.datetime | None = None) -> bool:
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    days_decl = window.get("days") or ["daily"]
    days_norm = [d.lower() for d in days_decl]
    # Translate to weekday abbreviations.
    weekday_abbr = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    today_abbr = weekday_abbr[now.weekday()]
    if "daily" not in days_norm and today_abbr not in days_norm:
        return False
    start = _parse_hhmm(window.get("start", ""))
    end = _parse_hhmm(window.get("end", ""))
    if start is None or end is None:
        return False
    tz = (window.get("timezone") or "UTC").lower()
    # Snap `now` to the requested timezone (UTC or local).
    if tz == "local":
        now_tz = now.astimezone()
    else:
        now_tz = now.astimezone(dt.timezone.utc)
    cur_minutes = now_tz.hour * 60 + now_tz.minute
    start_minutes = start[0] * 60 + start[1]
    end_minutes = end[0] * 60 + end[1]
    # Cross-midnight window (start > end) is supported via wrap.
    if start_minutes <= end_minutes:
        return start_minutes <= cur_minutes < end_minutes
    return cur_minutes >= start_minutes or cur_minutes < end_minutes


def resolve(windows: list[dict], name: str) -> dict | None:
    for w in windows:
        if isinstance(w, dict) and w.get("name") == name:
            return w
    return None


def render_list_human(entries: list[dict], now: dt.datetime) -> str:
    lines = [f"── R323 sovereign-os maintenance windows (E2.M19) ──",
             f"  windows: {len(entries)}    now (UTC): "
             f"{now.strftime('%a %H:%M')}", ""]
    for w in entries:
        active = is_active(w, now)
        mark = "ACTIVE" if active else "      "
        lines.append(f"  [{mark}] {w.get('name'):28s}  {w.get('schedule')}")
        desc = (w.get("description") or "").strip()
        if desc:
            lines.append(f"            {desc[:90]}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(w: dict, now: dt.datetime) -> str:
    active = is_active(w, now)
    lines = [f"── R323 maintenance window: {w.get('name')} (E2.M19) ──",
             f"  axis:        {w.get('axis')}",
             f"  schedule:    {w.get('schedule')}",
             f"  days:        {w.get('days')}",
             f"  start:       {w.get('start')}",
             f"  end:         {w.get('end')}",
             f"  timezone:    {w.get('timezone')}",
             f"  active now:  {active}",
             ""]
    if w.get("description"):
        lines.append(f"  description: {w['description']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="maintenance-window.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("window")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pc = sub.add_parser("can-run-now")
    pc.add_argument("window")
    pc.add_argument("--config", type=Path)
    fc = pc.add_mutually_exclusive_group()
    fc.add_argument("--json", dest="fmt", action="store_const", const="json")
    fc.add_argument("--human", dest="fmt", action="store_const", const="human")
    pc.set_defaults(fmt="json")

    pa = sub.add_parser("active")
    pa.add_argument("--config", type=Path)
    fa = pa.add_mutually_exclusive_group()
    fa.add_argument("--json", dest="fmt", action="store_const", const="json")
    fa.add_argument("--human", dest="fmt", action="store_const", const="human")
    pa.set_defaults(fmt="json")

    args = p.parse_args(argv)
    windows, meta = load_state(args.config)
    now = dt.datetime.now(dt.timezone.utc)

    if args.verb == "list":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "now_utc": now.isoformat(),
                "total_count": len(windows),
                "windows": [{**w, "active_now": is_active(w, now)}
                              for w in windows],
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(windows, now), end="")
        return 0

    if args.verb == "show":
        w = resolve(windows, args.window)
        if w is None:
            print(json.dumps({
                "error": f"unknown window: {args.window}",
                "known": [x.get("name") for x in windows if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "window": w,
                "active_now": is_active(w, now),
                "now_utc": now.isoformat(),
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(w, now), end="")
        return 0

    if args.verb == "can-run-now":
        w = resolve(windows, args.window)
        if w is None:
            print(json.dumps({
                "error": f"unknown window: {args.window}",
                "known": [x.get("name") for x in windows if isinstance(x, dict)],
                "round": ROUND,
                "rc": 2,
            }, indent=2), file=sys.stderr)
            return 2
        active = is_active(w, now)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "window": w.get("name"),
                "active_now": active,
                "now_utc": now.isoformat(),
                "rc": 0 if active else 1,
                "verdict": "can-run" if active else "outside-window",
            }, indent=2))
        else:
            print(f"── R323 can-run-now {w.get('name')} (E2.M19) ──")
            print(f"  active now: {active}")
            print(f"  verdict:    {'can-run' if active else 'outside-window'}")
        return 0 if active else 1

    if args.verb == "active":
        active = [w for w in windows if is_active(w, now)]
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "now_utc": now.isoformat(),
                "active_count": len(active),
                "active_windows": [w.get("name") for w in active],
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R323 active windows now (E2.M19) ──")
            print(f"  now (UTC): {now.strftime('%a %H:%M')}")
            print(f"  active: {len(active)}")
            for w in active:
                print(f"    {w.get('name'):28s}  {w.get('schedule')}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
