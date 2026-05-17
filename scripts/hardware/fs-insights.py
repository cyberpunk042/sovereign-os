#!/usr/bin/env python3
"""scripts/hardware/fs-insights.py — R222 (SDD-026 Z-10).

Operator-named: "to see all the logs files and need for log rotate,
track files system usage and for each partitions and global and
such. Offer insights."

Two sub-modes:

  usage      Per-partition disk usage + global summary. Highlights
             partitions ≥ operator threshold (default 80%). Read-only;
             pure `df` parsing — no privilege required.

  log-audit  Scan common log dirs and flag files larger than the
             operator's rotate threshold (default 100 MiB). Reports
             per-file size + suggested rotate command. Operator-
             actionable: each flagged line is the exact path the
             logrotate config needs.

Both modes:
  - JSON output for the future Z-1 dashboard via --json
  - Exit codes: 0 healthy / 1 attention-needed / 2 usage-error

Composes with:
  - R219 gpu-watch + R220 network status (same operator-card UX)
  - The future Z-6 autohealth notifier (fs-insights warnings become
    fan-out events)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_LOG_DIRS = [
    "/var/log",
    "/var/log/journal",
    "/var/log/sovereign-os",
    "/root/.sovereign-os/log",
]


# --------------------------------------------------------- usage subcmd


def parse_df_posix(stdout: str) -> list[dict[str, Any]]:
    """Parse `df -kP` output into structured rows."""
    rows: list[dict[str, Any]] = []
    lines = stdout.strip().splitlines()
    if not lines:
        return rows
    # Skip header
    for line in lines[1:]:
        # df -kP guarantees space-separated columns:
        # Filesystem 1024-blocks Used Available Capacity Mounted-on
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        try:
            total_kb = int(parts[1])
            used_kb = int(parts[2])
            avail_kb = int(parts[3])
        except ValueError:
            continue
        capacity = parts[4].rstrip("%")
        try:
            cap_pct = int(capacity)
        except ValueError:
            cap_pct = 0
        rows.append(
            {
                "filesystem": parts[0],
                "mount": parts[5],
                "total_bytes": total_kb * 1024,
                "used_bytes": used_kb * 1024,
                "available_bytes": avail_kb * 1024,
                "use_pct": cap_pct,
            }
        )
    return rows


def fmt_bytes(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    v = float(n)
    for u in units:
        if v < 1024 or u == units[-1]:
            return f"{v:.1f} {u}"
        v /= 1024
    return f"{n} B"


def is_real_filesystem(row: dict[str, Any]) -> bool:
    """Skip tmpfs/devtmpfs/overlay/squashfs — operator cares about
    the persistent partitions, not the kernel pseudo-fs."""
    fs = row["filesystem"]
    mount = row["mount"]
    if fs in {"tmpfs", "devtmpfs", "udev", "none"}:
        return False
    if mount.startswith("/sys") or mount.startswith("/proc") or mount.startswith("/dev"):
        return False
    if mount.startswith("/run") and "lock" in mount.lower():
        return False
    if row["total_bytes"] == 0:
        return False
    return True


def cmd_usage(threshold_pct: int, json_out: bool, include_pseudo: bool) -> int:
    if not shutil.which("df"):
        print("ERROR df binary missing", file=sys.stderr)
        return 2
    try:
        r = subprocess.run(["df", "-kP"], capture_output=True, text=True, timeout=10, check=False)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"ERROR df invocation failed: {e}", file=sys.stderr)
        return 2
    rows = parse_df_posix(r.stdout)
    if not include_pseudo:
        rows = [r_ for r_ in rows if is_real_filesystem(r_)]
    # Sort by use_pct descending (most-full first).
    rows.sort(key=lambda x: x["use_pct"], reverse=True)
    flagged = [r_ for r_ in rows if r_["use_pct"] >= threshold_pct]
    total_real_bytes = sum(r_["total_bytes"] for r_ in rows)
    total_used_bytes = sum(r_["used_bytes"] for r_ in rows)
    global_use_pct = int(100 * total_used_bytes / total_real_bytes) if total_real_bytes else 0
    if json_out:
        print(
            json.dumps(
                {
                    "partitions": rows,
                    "global_total_bytes": total_real_bytes,
                    "global_used_bytes": total_used_bytes,
                    "global_use_pct": global_use_pct,
                    "threshold_pct": threshold_pct,
                    "flagged_count": len(flagged),
                },
                indent=2,
            )
        )
        return 1 if flagged else 0
    print("── R222 sovereign-os fs-insights: usage (SDD-026 Z-10) ──")
    print(f"  global: {fmt_bytes(total_used_bytes)} / {fmt_bytes(total_real_bytes)}  ({global_use_pct}%)")
    print()
    print(f"  {'use%':>5}  {'used':>10}  {'total':>10}  mount  (filesystem)")
    for r_ in rows:
        marker = "⚠" if r_["use_pct"] >= threshold_pct else " "
        print(
            f"  {r_['use_pct']:>3}% {marker}  "
            f"{fmt_bytes(r_['used_bytes']):>10}  "
            f"{fmt_bytes(r_['total_bytes']):>10}  "
            f"{r_['mount']}  ({r_['filesystem']})"
        )
    if flagged:
        print()
        print(
            f"  ⚠ {len(flagged)} partition(s) ≥ {threshold_pct}% — "
            "operator should investigate growth + prune or expand."
        )
    return 1 if flagged else 0


# --------------------------------------------------------- log-audit subcmd


def scan_logs(roots: list[str], threshold_bytes: int) -> list[dict[str, Any]]:
    """Walk each root, return per-file rows with size + flag marker."""
    rows: list[dict[str, Any]] = []
    for root in roots:
        p = Path(root)
        if not p.is_dir():
            continue
        for entry in p.rglob("*"):
            if not entry.is_file():
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            rows.append(
                {
                    "path": str(entry),
                    "size_bytes": size,
                    "flagged": size >= threshold_bytes,
                }
            )
    rows.sort(key=lambda x: x["size_bytes"], reverse=True)
    return rows


def cmd_log_audit(
    threshold_bytes: int,
    json_out: bool,
    roots: list[str],
    max_rows: int,
) -> int:
    rows = scan_logs(roots, threshold_bytes)
    flagged = [r_ for r_ in rows if r_["flagged"]]
    if json_out:
        print(
            json.dumps(
                {
                    "log_roots": roots,
                    "threshold_bytes": threshold_bytes,
                    "files": rows[:max_rows],
                    "files_truncated": len(rows) > max_rows,
                    "flagged_count": len(flagged),
                },
                indent=2,
            )
        )
        return 1 if flagged else 0
    print("── R222 sovereign-os fs-insights: log-audit (SDD-026 Z-10) ──")
    print(f"  scanned roots: {', '.join(roots)}")
    print(f"  rotate threshold: {fmt_bytes(threshold_bytes)}")
    print()
    if not rows:
        print("  (no log files found at the scanned roots)")
        return 0
    print(f"  {'size':>10}  flag  path")
    for r_ in rows[:max_rows]:
        marker = "⚠" if r_["flagged"] else " "
        print(f"  {fmt_bytes(r_['size_bytes']):>10}  {marker}    {r_['path']}")
    if len(rows) > max_rows:
        print(f"  ... ({len(rows) - max_rows} more file(s) omitted; use --json or --max-rows N to see them)")
    if flagged:
        print()
        print(
            f"  ⚠ {len(flagged)} file(s) ≥ {fmt_bytes(threshold_bytes)} — "
            "add to /etc/logrotate.d/ with `rotate 4 / size 100M / compress`."
        )
    return 1 if flagged else 0


# --------------------------------------------------------- entrypoint


def main() -> int:
    p = argparse.ArgumentParser(description="R222 (SDD-026 Z-10) — fs + log insights.")
    sub = p.add_subparsers(dest="action", required=True)

    p_usage = sub.add_parser("usage", help="per-partition + global disk usage")
    p_usage.add_argument(
        "--threshold-pct",
        type=int,
        default=80,
        help="flag partitions whose use%% >= this (default 80)",
    )
    p_usage.add_argument(
        "--include-pseudo",
        action="store_true",
        help="include tmpfs/devtmpfs/overlay (default: real partitions only)",
    )
    p_usage.add_argument("--json", action="store_true")

    p_log = sub.add_parser("log-audit", help="scan log dirs + flag oversized files")
    p_log.add_argument(
        "--threshold-bytes",
        type=int,
        default=100 * 1024 * 1024,
        help="flag files this size or larger (default 100 MiB)",
    )
    p_log.add_argument(
        "--root",
        action="append",
        dest="roots",
        help=(
            "log root to scan (repeat); default: "
            f"{', '.join(DEFAULT_LOG_DIRS)}"
        ),
    )
    p_log.add_argument(
        "--max-rows",
        type=int,
        default=30,
        help="max rows in tabular output (default 30; JSON honors this too)",
    )
    p_log.add_argument("--json", action="store_true")

    args = p.parse_args()
    if args.action == "usage":
        return cmd_usage(args.threshold_pct, args.json, args.include_pseudo)
    if args.action == "log-audit":
        roots = args.roots if args.roots else DEFAULT_LOG_DIRS
        return cmd_log_audit(args.threshold_bytes, args.json, roots, args.max_rows)
    return 2


if __name__ == "__main__":
    sys.exit(main())
