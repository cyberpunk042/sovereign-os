#!/usr/bin/env python3
"""scripts/history/aggregate.py — R246 (SDD-026 Z-16 new vector).

Operator-named (verbatim, 2026-05-17 'DO not stop' expansion): "OS,
Services, Modules, Tools, Dashboards, Configurations, Options.
Network, App, & In between."

Opens Z-16: cross-cutting OPERATOR TIMELINE. Aggregates every JSONL
state file the operator-facing surfaces write into ONE chronological
view. So far:

  R228 notify-events       /var/log/sovereign-os/notify.jsonl
  R232 models eval         /var/lib/sovereign-os/models-eval.jsonl
  R244 fine-tune           /var/lib/sovereign-os/fine-tune.jsonl
  (extensible — operator points at additional .jsonl files via
   SOVEREIGN_OS_HISTORY_EXTRA_PATHS=path1:path2:...)

Each row is normalized into the operator-readable shape:
  { source, timestamp, kind, detail, raw }

CLI:
  aggregate.py timeline [--source S] [--since ISO] [--limit N] [--json]
  aggregate.py summary [--json]    counts per source + last-event timestamp

Exit codes:
  0  rendered
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Default sources — each entry: {source_id, path, ts_field, kind_extractor}.
DEFAULT_SOURCES: list[dict[str, Any]] = [
    {
        "source": "notify-events",
        "path": "/var/log/sovereign-os/notify.jsonl",
        "ts_field": "emitted_at",
        "kind_template": "notify:{probe}",
        "detail_template": "{severity} — {detail}",
    },
    {
        "source": "models-eval",
        "path": "/var/lib/sovereign-os/models-eval.jsonl",
        "ts_field": "started_at",
        "kind_template": "eval:{benchmark}",
        "detail_template": "{model_id} → {outcome} (rc={rc}, {duration_s}s)",
    },
    {
        "source": "fine-tune",
        "path": "/var/lib/sovereign-os/fine-tune.jsonl",
        "ts_field": "started_at",
        "kind_template": "fine-tune:{method}",
        "detail_template": "{base_id} ← {dataset} → {outcome} (rc={rc}, {duration_s}s)",
    },
]


def expand_extra_sources() -> list[dict[str, Any]]:
    """SOVEREIGN_OS_HISTORY_EXTRA_PATHS=path1:path2 → add as `extra` sources."""
    raw = os.environ.get("SOVEREIGN_OS_HISTORY_EXTRA_PATHS", "").strip()
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for p in raw.split(":"):
        p = p.strip()
        if not p:
            continue
        out.append(
            {
                "source": f"extra:{Path(p).name}",
                "path": p,
                "ts_field": "timestamp",
                "kind_template": "extra",
                "detail_template": "{raw}",
            }
        )
    return out


def env_override(default_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SOVEREIGN_OS_HISTORY_STATE_DIR=/some/dir → reroute every default path
    under that dir (preserves basenames). Used by L3 to point at temp dirs."""
    base = os.environ.get("SOVEREIGN_OS_HISTORY_STATE_DIR")
    if not base:
        return default_sources
    rerouted = []
    for s in default_sources:
        d = dict(s)
        d["path"] = str(Path(base) / Path(s["path"]).name)
        rerouted.append(d)
    return rerouted


def render_template(tpl: str, row: dict[str, Any]) -> str:
    try:
        return tpl.format(**row)
    except (KeyError, ValueError):
        return tpl  # fallback: literal template


def read_rows(source: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(source["path"])
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = row.get(source["ts_field"]) or ""
            out.append(
                {
                    "source": source["source"],
                    "timestamp": ts,
                    "kind": render_template(source["kind_template"], row),
                    "detail": render_template(source["detail_template"], row),
                    "raw": row,
                }
            )
    except OSError:
        return []
    return out


def all_sources() -> list[dict[str, Any]]:
    return env_override(DEFAULT_SOURCES) + expand_extra_sources()


def gather(filter_source: str | None) -> list[dict[str, Any]]:
    sources = all_sources()
    if filter_source:
        sources = [s for s in sources if s["source"] == filter_source]
    rows: list[dict[str, Any]] = []
    for s in sources:
        rows.extend(read_rows(s))
    # Sort by timestamp ascending (lexicographic = chronological for ISO-8601).
    rows.sort(key=lambda r: r["timestamp"])
    return rows


def cmd_timeline(args: argparse.Namespace) -> int:
    rows = gather(args.source)
    if args.since:
        rows = [r for r in rows if r["timestamp"] >= args.since]
    if args.limit:
        rows = rows[-int(args.limit):]
    out = {
        "round": "R246",
        "vector": "SDD-026 Z-16 (history timeline)",
        "filter": {"source": args.source, "since": args.since},
        "count": len(rows),
        "events": rows,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R246 sovereign-os history timeline (SDD-026 Z-16) ──")
    if args.source:
        print(f"  filter: source={args.source}")
    print(f"  events: {len(rows)}")
    print()
    if not rows:
        print("  (no events in any source — surfaces ship empty until they record)")
        return 0
    for r in rows:
        print(f"  {r['timestamp']:<22}  [{r['source']:<14}]  {r['kind']:<24}  {r['detail']}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    by_source: dict[str, dict[str, Any]] = {}
    for s in all_sources():
        rows = read_rows(s)
        last_ts = rows[-1]["timestamp"] if rows else None
        by_source[s["source"]] = {
            "path": s["path"],
            "event_count": len(rows),
            "last_event_ts": last_ts,
            "exists": Path(s["path"]).exists(),
        }
    total = sum(b["event_count"] for b in by_source.values())
    out = {
        "round": "R246",
        "vector": "SDD-026 Z-16 (history summary)",
        "total_events": total,
        "sources": by_source,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R246 sovereign-os history summary ──")
    print(f"  total events:  {total}")
    for name, info in by_source.items():
        mark = "✓" if info["exists"] else "·"
        print(
            f"  {mark} {name:<14}  count={info['event_count']:<6}"
            f"  last={info['last_event_ts'] or '(none)'}"
            f"  path={info['path']}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aggregate.py",
        description="R246 (SDD-026 Z-16) — operator-timeline JSONL aggregator.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    pt = sub.add_parser("timeline", help="chronological event view across sources")
    pt.add_argument("--source", help="restrict to one source id")
    pt.add_argument("--since", help="ISO-8601 lower-bound timestamp (lexicographic)")
    pt.add_argument("--limit", type=int)
    pt.add_argument("--json", action="store_true")
    pt.set_defaults(func=cmd_timeline)
    ps = sub.add_parser("summary", help="per-source counts + last-event timestamp")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_summary)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
