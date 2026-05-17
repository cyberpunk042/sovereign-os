#!/usr/bin/env python3
"""scripts/fleet/snapshot-aggregator.py — R324 (E2.M20).

Operator-pull fleet-tier extension of the R322 unified state
snapshot. Ingests one snapshot-per-host (R322 JSON output) from a
directory OR stdin, then emits cross-host rollups:

  - per-axis verdict distribution
  - per-host summary (probe counts + failed counts + outlier flag)
  - outlier detection (hosts with >2x the median failed_count)
  - fleet-wide aggregate verdict

Operator's eventual Stage-2+ fleet deploy can run `sovereign-osctl
snapshot snapshot --json` on each host (cron) + ship outputs to a
central directory + run R324 aggregator over that directory.

CLI:
  snapshot-aggregator.py aggregate [--snapshots-dir D]
                                    [--config P] [--json|--human]
                                      ingest snapshots; emit
                                      cross-host rollup

  snapshot-aggregator.py by-axis   [--snapshots-dir D] [--axis X]
                                    [--config P] [--json|--human]
                                      per-axis verdict distribution
                                      across hosts

  snapshot-aggregator.py outliers  [--snapshots-dir D]
                                    [--config P] [--json|--human]
                                      hosts with >2x median failures

Input sources (highest precedence first):
  1. --snapshots-dir <dir>      glob *.json
  2. /var/lib/sovereign-os/fleet-snapshots/  default dir
  3. stdin (one JSON object per line OR one JSON array)

Operator-overlay (R283/SDD-030):
/etc/sovereign-os/snapshot-aggregator.toml
  - default_snapshots_dir       path override
  - outlier_threshold_x         multiplier vs median for outlier
                                 (default 2.0)

Exit codes:
  0  rendered (any state)
  1  no snapshots found / readable
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import statistics
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
ROUND = "R324"
SDD_VECTOR = "E2.M20"


DEFAULTS = {
    "default_snapshots_dir": "/var/lib/sovereign-os/fleet-snapshots",
    "outlier_threshold_x": 2.0,
}


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("snapshot-aggregator", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def collect_snapshots(snapshots_dir: Path | None) -> list[dict[str, Any]]:
    """Read snapshots from dir (*.json files); fall back to stdin."""
    out: list[dict[str, Any]] = []
    if snapshots_dir is not None and snapshots_dir.is_dir():
        for path in sorted(snapshots_dir.glob("*.json")):
            try:
                body = path.read_text(encoding="utf-8")
                doc = json.loads(body)
                if isinstance(doc, dict):
                    doc["_source_file"] = str(path)
                    out.append(doc)
            except (OSError, json.JSONDecodeError):
                continue
        return out
    # stdin fallback — accept either NDJSON or a single JSON array.
    if not sys.stdin.isatty():
        body = sys.stdin.read()
        if not body.strip():
            return out
        # Try array first.
        try:
            arr = json.loads(body)
            if isinstance(arr, list):
                for d in arr:
                    if isinstance(d, dict):
                        out.append(d)
                return out
            if isinstance(arr, dict):
                return [arr]
        except json.JSONDecodeError:
            pass
        # NDJSON fallback.
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if isinstance(d, dict):
                    out.append(d)
            except json.JSONDecodeError:
                continue
    return out


def derive_host_summary(snap: dict) -> dict[str, Any]:
    """Per-host: probe_count + failed_count + axes covered + verdict map."""
    probes = snap.get("probes", []) if isinstance(snap, dict) else []
    probe_count = len(probes)
    failed = sum(1 for p in probes if isinstance(p, dict)
                  and p.get("rc") not in (0, None))
    axes_seen = set()
    verdicts: dict[str, str] = {}
    for p in probes:
        if not isinstance(p, dict):
            continue
        axes_seen.add(p.get("axis", "?"))
        out = p.get("output") or {}
        if isinstance(out, dict):
            v = out.get("verdict") or out.get("status")
            if v:
                verdicts[p.get("name", "?")] = v
    return {
        "host_source": snap.get("_source_file", "(stdin)"),
        "snapshot_at": snap.get("snapshot_at"),
        "probe_count": probe_count,
        "failed_count": failed,
        "axes_count": len(axes_seen),
        "axes": sorted(axes_seen),
        "verdicts": verdicts,
    }


def derive_axis_distribution(snaps: list[dict]) -> dict[str, dict[str, int]]:
    """Per-axis: { verdict_name → count_of_hosts_with_that_verdict_in_axis }."""
    by_axis: dict[str, dict[str, int]] = {}
    for snap in snaps:
        for p in snap.get("probes", []):
            if not isinstance(p, dict):
                continue
            axis = p.get("axis", "?")
            out = p.get("output") or {}
            verdict = (out.get("verdict") or out.get("status") or "no-verdict") \
                if isinstance(out, dict) else "no-output"
            by_axis.setdefault(axis, {})
            by_axis[axis][verdict] = by_axis[axis].get(verdict, 0) + 1
    return by_axis


def derive_outliers(host_summaries: list[dict],
                     threshold_x: float) -> list[dict]:
    """Hosts whose failed_count exceeds median × threshold_x."""
    fails = [h["failed_count"] for h in host_summaries
              if isinstance(h.get("failed_count"), int)]
    if not fails:
        return []
    median = statistics.median(fails) if fails else 0
    if median == 0:
        # All hosts have 0 failures — outliers = any host with ≥1.
        return [h for h in host_summaries if h["failed_count"] > 0]
    cutoff = median * threshold_x
    return [h for h in host_summaries if h["failed_count"] > cutoff]


def aggregate_verdict(host_summaries: list[dict]) -> tuple[str, int]:
    if not host_summaries:
        return "no-snapshots", 1
    any_fail = any(h["failed_count"] > 0 for h in host_summaries)
    if any_fail:
        return "fleet-has-failures", 0
    return "fleet-all-clear", 0


def render_aggregate_human(doc: dict) -> str:
    lines = [f"── R324 sovereign-os fleet snapshot aggregator (E2.M20) ──",
             f"  hosts ingested:  {doc['host_count']}",
             f"  fleet verdict:   {doc['verdict']}",
             f"  outliers:        {len(doc['outliers'])}",
             ""]
    lines.append("  per-host summary:")
    for h in doc["host_summaries"][:20]:
        lines.append(f"    {Path(h['host_source']).name:40s}  "
                      f"probes={h['probe_count']}  fail={h['failed_count']}  "
                      f"axes={h['axes_count']}")
    if doc["outliers"]:
        lines.append("")
        lines.append("  outliers (>median × threshold):")
        for o in doc["outliers"]:
            lines.append(f"    {Path(o['host_source']).name}  "
                          f"fail={o['failed_count']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="snapshot-aggregator.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("aggregate", "outliers"):
        sp = sub.add_parser(verb)
        sp.add_argument("--snapshots-dir", type=Path)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")
    pba = sub.add_parser("by-axis")
    pba.add_argument("--snapshots-dir", type=Path)
    pba.add_argument("--axis")
    pba.add_argument("--config", type=Path)
    fba = pba.add_mutually_exclusive_group()
    fba.add_argument("--json", dest="fmt", action="store_const", const="json")
    fba.add_argument("--human", dest="fmt", action="store_const", const="human")
    pba.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)

    snaps_dir = args.snapshots_dir if args.snapshots_dir \
        else Path(cfg["default_snapshots_dir"])
    snaps = collect_snapshots(snaps_dir)

    if not snaps:
        print(json.dumps({
            "error": ("no snapshots found in "
                      f"{snaps_dir} (pass --snapshots-dir or "
                      "pipe JSON via stdin)"),
            "round": ROUND,
            "rc": 1,
        }, indent=2), file=sys.stderr)
        return 1

    host_summaries = [derive_host_summary(s) for s in snaps]
    axis_dist = derive_axis_distribution(snaps)
    outliers = derive_outliers(host_summaries, float(cfg["outlier_threshold_x"]))
    verdict, _ = aggregate_verdict(host_summaries)

    if args.verb == "aggregate":
        doc = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "host_count": len(snaps),
            "host_summaries": host_summaries,
            "verdict": verdict,
            "outliers": outliers,
            "axis_distribution": axis_dist,
            "config": cfg,
            "overlay": meta,
        }
        if args.fmt == "json":
            print(json.dumps(doc, indent=2))
        else:
            print(render_aggregate_human(doc), end="")
        return 0

    if args.verb == "by-axis":
        if args.axis:
            dist = {args.axis: axis_dist.get(args.axis, {})}
        else:
            dist = axis_dist
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "host_count": len(snaps),
                "axis_filter": args.axis,
                "axis_distribution": dist,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R324 by-axis (E2.M20) — {len(snaps)} hosts ──")
            for axis, verdicts in sorted(dist.items()):
                print(f"  ── {axis} ──")
                for v, n in sorted(verdicts.items()):
                    print(f"    {v:>30s}: {n}")
        return 0

    if args.verb == "outliers":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "host_count": len(snaps),
                "outlier_count": len(outliers),
                "outliers": outliers,
                "outlier_threshold_x": cfg["outlier_threshold_x"],
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R324 outliers (E2.M20) — {len(outliers)} of "
                  f"{len(snaps)} hosts ──")
            for o in outliers:
                print(f"  {Path(o['host_source']).name:40s}  "
                      f"fail={o['failed_count']}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
