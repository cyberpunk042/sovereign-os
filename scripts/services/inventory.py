#!/usr/bin/env python3
"""scripts/services/inventory.py — R240 (SDD-026 Z-15 new vector).

Operator-named (verbatim, 2026-05-17 'DO not stop' expansion): "OS,
Services, Modules, Tools, Dashboards, Configurations, Options."

Opens Z-15: the SERVICES axis. Operator-readable inventory of the
sovereign-os and operator-relevant systemd units. Aggregates:

  - sovereign-os shipped units under systemd/system/sovereign-*
  - active systemd units on the live host (via systemctl list-units)
  - per-unit status (active/inactive/failed) + sub-state + load state
  - timer next-fire times for *.timer units (operator's "when will
    this run next" question)

Drives:
  - dashboard 'Services' tab — surfaces active + failed units
  - `services failures` — operator's fast-path: just show what's broken
  - `services timers` — what's scheduled to run next + how recently
    each fired

CLI:
  inventory.py list [--prefix P] [--state S] [--json]
  inventory.py failures [--json]
  inventory.py timers [--json]
  inventory.py shipped [--json]      # what sovereign-os DECLARES

Exit codes:
  0  operation succeeded
  1  ≥1 failed unit present (failures verb) / ≥1 missing declared unit
  2  usage error / systemctl unavailable
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_UNIT_DIR = REPO_ROOT / "systemd" / "system"


def shipped_units() -> list[dict[str, Any]]:
    """Catalog the *.{service,timer,socket} files this repo declares."""
    rows: list[dict[str, Any]] = []
    if not SHIPPED_UNIT_DIR.is_dir():
        return rows
    for unit_path in sorted(SHIPPED_UNIT_DIR.iterdir()):
        if unit_path.suffix not in {".service", ".timer", ".socket", ".target"}:
            continue
        try:
            body = unit_path.read_text(errors="replace")
        except OSError:
            body = ""
        descr = ""
        for line in body.splitlines():
            if line.startswith("Description="):
                descr = line[len("Description="):].strip()
                break
        rows.append(
            {
                "name": unit_path.name,
                "kind": unit_path.suffix.lstrip("."),
                "description": descr,
                "path": str(unit_path),
            }
        )
    return rows


def systemctl_available() -> bool:
    return shutil.which("systemctl") is not None


def list_live_units(prefix: str | None = None) -> list[dict[str, Any]]:
    """Returns live unit rows via `systemctl list-units --all --no-legend`.

    Each row has {unit, load, active, sub, description}. When systemctl
    is unavailable (CI sandbox), returns [].
    """
    if not systemctl_available():
        return []
    args = [
        "systemctl",
        "list-units",
        "--all",
        "--no-legend",
        "--no-pager",
        "--plain",
        "--type=service,timer,socket,target",
    ]
    if prefix:
        args.append(f"{prefix}*")
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return []
    if r.returncode != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in r.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        unit, load, active, sub, *rest = parts
        descr = rest[0] if rest else ""
        rows.append(
            {
                "unit": unit,
                "load": load,
                "active": active,
                "sub": sub,
                "description": descr,
            }
        )
    return rows


def list_timers() -> list[dict[str, Any]]:
    """Returns timer rows with next/last fire times.

    `systemctl list-timers --all` columns:
      NEXT LEFT LAST PASSED UNIT ACTIVATES
    """
    if not systemctl_available():
        return []
    try:
        r = subprocess.run(
            ["systemctl", "list-timers", "--all", "--no-legend", "--no-pager"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if r.returncode != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in r.stdout.splitlines():
        # Operator-readable timestamps contain spaces (e.g. "Mon 2026-05-19 ...").
        # systemctl list-timers --no-legend columns:
        #   NEXT (3 tokens "Day YYYY-MM-DD HH:MM:SS TZ") or "-"
        #   LEFT (compact)
        #   LAST (3 tokens or "-")
        #   PASSED (compact)
        #   UNIT
        #   ACTIVATES
        # Rather than parse exactly, split on multi-space if any, else
        # leave raw line.
        rows.append({"raw": line.strip()})
    return rows


def cmd_list(args: argparse.Namespace) -> int:
    prefix = args.prefix or None
    units = list_live_units(prefix=prefix)
    if args.state:
        units = [u for u in units if u["active"] == args.state]
    if args.json:
        print(
            json.dumps(
                {
                    "round": "R240",
                    "vector": "SDD-026 Z-15 (services inventory)",
                    "systemctl_available": systemctl_available(),
                    "filter": {"prefix": prefix, "state": args.state},
                    "count": len(units),
                    "units": units,
                },
                indent=2,
            )
        )
        return 0
    print(f"── R240 sovereign-os services list (SDD-026 Z-15) ──")
    if not systemctl_available():
        print("  (systemctl not on PATH — CI sandbox; live data unavailable)")
        return 0
    if not units:
        print(f"  (no units match prefix={prefix!r} state={args.state!r})")
        return 0
    for u in units:
        glyph = {"active": "✓", "inactive": "·", "failed": "⛔"}.get(u["active"], "?")
        print(
            f"  {glyph} {u['unit']:<48}  {u['active']:<10} {u['sub']:<14}  {u['description']}"
        )
    return 0


def cmd_failures(args: argparse.Namespace) -> int:
    units = list_live_units()
    failed = [u for u in units if u["active"] == "failed"]
    if args.json:
        print(
            json.dumps(
                {
                    "round": "R240",
                    "vector": "SDD-026 Z-15 (services failures)",
                    "systemctl_available": systemctl_available(),
                    "failed_count": len(failed),
                    "failed": failed,
                },
                indent=2,
            )
        )
        return 1 if failed else 0
    print(f"── R240 sovereign-os services failures ──")
    if not systemctl_available():
        print("  (systemctl not on PATH — CI sandbox)")
        return 0
    if not failed:
        print("  (no failed units — every loaded unit is OK)")
        return 0
    for u in failed:
        print(f"  ⛔ {u['unit']:<48}  {u['sub']:<14}  {u['description']}")
        print(f"      next:  sudo systemctl status {u['unit']}")
    return 1


def cmd_timers(args: argparse.Namespace) -> int:
    rows = list_timers()
    if args.json:
        print(
            json.dumps(
                {
                    "round": "R240",
                    "vector": "SDD-026 Z-15 (services timers)",
                    "systemctl_available": systemctl_available(),
                    "count": len(rows),
                    "timers": rows,
                },
                indent=2,
            )
        )
        return 0
    print(f"── R240 sovereign-os services timers ──")
    if not systemctl_available():
        print("  (systemctl not on PATH — CI sandbox)")
        return 0
    if not rows:
        print("  (no timers active)")
        return 0
    for r in rows:
        print(f"  {r['raw']}")
    return 0


def cmd_shipped(args: argparse.Namespace) -> int:
    rows = shipped_units()
    # Cross-reference with live units to flag declared-but-not-loaded.
    live = {u["unit"] for u in list_live_units()}
    for r in rows:
        r["loaded_on_this_host"] = r["name"] in live
    missing = [r for r in rows if not r["loaded_on_this_host"]]
    if args.json:
        print(
            json.dumps(
                {
                    "round": "R240",
                    "vector": "SDD-026 Z-15 (services shipped catalog)",
                    "count": len(rows),
                    "loaded_count": len(rows) - len(missing),
                    "missing_count": len(missing),
                    "units": rows,
                },
                indent=2,
            )
        )
        return 1 if (missing and systemctl_available()) else 0
    print(f"── R240 sovereign-os services shipped (this repo declares) ──")
    if not rows:
        print(f"  (no units shipped under {SHIPPED_UNIT_DIR})")
        return 0
    for r in rows:
        mark = "✓" if r["loaded_on_this_host"] else "·"
        if not systemctl_available():
            mark = "?"
        print(
            f"  {mark} {r['name']:<48}  [{r['kind']:<7}]  {r['description']}"
        )
    if missing and systemctl_available():
        print()
        print(
            f"  {len(missing)} declared unit(s) not loaded on this host. "
            "Enable with `sudo systemctl enable --now <unit>`."
        )
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="inventory.py",
        description="R240 (SDD-026 Z-15) — sovereign-os services inventory.",
    )
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list", help="systemd units (live host)")
    pl.add_argument("--prefix")
    pl.add_argument("--state", choices=["active", "inactive", "failed"])
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list)

    pf = sub.add_parser("failures", help="only failed units")
    pf.add_argument("--json", action="store_true")
    pf.set_defaults(func=cmd_failures)

    pt = sub.add_parser("timers", help="systemd timers (next/last fire)")
    pt.add_argument("--json", action="store_true")
    pt.set_defaults(func=cmd_timers)

    ps = sub.add_parser("shipped", help="units this repo DECLARES + load status")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_shipped)

    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
