#!/usr/bin/env python3
"""scripts/hardware/selfdef-resources-audit.py — audit per-module
[resources] declarations across the selfdef catalog (R198).

selfdef cycle-3 SD-R61 added optional [resources] blocks to module.toml
surfacing cpu_max / memory_max / io_weight / time_max_seconds as env
vars to apply.sh. This script walks the catalog + reports which
modules declare quotas + their values. Operators verify their
catalog has the discipline they expect before deploying.

CLI:
  selfdef-resources-audit.py                # human catalog overview
  selfdef-resources-audit.py --json         # machine-readable

Exit codes:
  0  audit complete (regardless of how many modules have/lack quotas)
  2  arg / I/O error

Per-module state:
  unquota'd  — no [resources] block (cycle-2 default)
  partial    — [resources] block but some fields unset
  full       — every quota field declared
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_MODULES_DIR = Path("/usr/share/selfdef/modules")
QUOTA_FIELDS = ["cpu_max", "memory_max", "io_weight", "time_max_seconds"]


def parse_resources_block(manifest_path: Path) -> dict | None:
    """Minimal TOML reader — same pattern as selfdef-signing-audit.py.
    Returns the [resources] block dict or None when absent."""
    if not manifest_path.exists():
        return None
    section: str | None = None
    out: dict = {}
    found = False
    for raw in manifest_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            if section == "resources":
                found = True
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip(",")
        if section == "resources":
            if v.startswith('"') and v.endswith('"'):
                out[k] = v[1:-1]
            else:
                try:
                    out[k] = int(v)
                except ValueError:
                    out[k] = v
    return out if found else None


def classify(module_dir: Path) -> dict:
    manifest = module_dir / "module.toml"
    res = parse_resources_block(manifest)
    name = module_dir.name
    if res is None:
        return {
            "name": name,
            "has_resources_block": False,
            "state": "unquota'd",
            "fields": {},
        }
    set_fields = [f for f in QUOTA_FIELDS if f in res]
    state = "full" if len(set_fields) == len(QUOTA_FIELDS) else "partial"
    return {
        "name": name,
        "has_resources_block": True,
        "state": state,
        "fields": {f: res.get(f) for f in QUOTA_FIELDS},
    }


def walk_catalog(dir_: Path) -> list[dict]:
    if not dir_.exists() or not dir_.is_dir():
        return []
    out = []
    for entry in sorted(dir_.iterdir()):
        if (entry / "module.toml").exists():
            out.append(classify(entry))
    return out


def main() -> int:
    p = argparse.ArgumentParser(
        description="audit selfdef per-module [resources] declarations (R198)"
    )
    p.add_argument(
        "--dir",
        type=Path,
        default=Path(os.environ.get("SELFDEF_MODULES_DIR", str(DEFAULT_MODULES_DIR))),
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    rows = walk_catalog(args.dir)
    if not rows:
        sys.stderr.write(f"no modules found in {args.dir}\n")
        return 2
    counts = {
        "unquotad": sum(1 for r in rows if r["state"] == "unquota'd"),
        "partial": sum(1 for r in rows if r["state"] == "partial"),
        "full": sum(1 for r in rows if r["state"] == "full"),
    }
    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "modules_dir": str(args.dir),
                    "total": len(rows),
                    "counts": counts,
                    "modules": rows,
                },
                indent=2,
            )
        )
        return 0

    print("# R198: selfdef per-module [resources] audit")
    print(f"# {len(rows)} module(s) in {args.dir}")
    print(
        f"# counts: unquotad={counts['unquotad']}"
        f" partial={counts['partial']} full={counts['full']}"
    )
    print()
    header = f"{'STATE':<10}  {'MODULE':<28}  cpu_max  memory_max  io_weight  time_max"
    print(header)
    for r in rows:
        marker = {"unquota'd": " ", "partial": "·", "full": "✓"}.get(r["state"], "?")
        cpu = r["fields"].get("cpu_max") or "-"
        mem = r["fields"].get("memory_max") or "-"
        io = r["fields"].get("io_weight")
        io = str(io) if io is not None else "-"
        tm = r["fields"].get("time_max_seconds")
        tm = str(tm) if tm is not None else "-"
        print(
            f"{marker} {r['state']:<8}  {r['name']:<28}  {cpu:<7}  {mem:<10}  {io:<9}  {tm}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
