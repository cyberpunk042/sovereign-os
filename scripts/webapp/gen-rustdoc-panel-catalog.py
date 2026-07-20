#!/usr/bin/env python3
"""gen-rustdoc-panel-catalog.py — generate the rustdoc-panel crate catalog.

Reads every workspace crate manifest (crates/*/Cargo.toml), extracts name +
description, and writes webapp/rustdoc-panel/catalog.json so the panel can
render a searchable, filterable list of all 717 crates with descriptions and
source links.

Follows the house generator pattern (SDD-958 / SDD-995 / SDD-972):
  --apply   (default) — regenerate and write
  --check   — regen in-memory, compare, exit 1 on drift, exit 0 if synced
  --list    — print crate count + first/last few names, write nothing

Usage:
  python3 scripts/webapp/gen-rustdoc-panel-catalog.py
  python3 scripts/webapp/gen-rustdoc-panel-catalog.py --check   # CI gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CRATES_DIR = REPO_ROOT / "crates"
OUT = REPO_ROOT / "webapp" / "rustdoc-panel" / "catalog.json"


def _extract(cargo_toml: Path) -> dict[str, str] | None:
    """Parse a minimal subset of Cargo.toml (tomllib is 3.11+; fallback to
    hand-parse for the two keys we need, since the pytest lint job may not
    have tomllib)."""
    try:
        import tomllib
        data = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
        pkg = data.get("package", {})
        name = pkg.get("name", "")
        desc = pkg.get("description", "")
        if not name:
            return None
        return {"name": name, "description": desc or ""}
    except Exception:
        # Fallback: regex-parse the two lines we care about
        text = cargo_toml.read_text(encoding="utf-8")
        name = ""
        desc = ""
        for line in text.splitlines():
            if line.strip().startswith("name =") and not name:
                name = line.split("=", 1)[1].strip().strip('"').strip("'")
            if line.strip().startswith("description =") and not desc:
                desc = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not name:
            return None
        return {"name": name, "description": desc}


def render() -> str:
    crates: list[dict[str, str]] = []
    for path in sorted(CRATES_DIR.glob("*/Cargo.toml")):
        info = _extract(path)
        if info:
            crates.append(info)
    crates.sort(key=lambda c: c["name"])
    return json.dumps({
        "schema_version": "1.0.0",
        "generated_by": "scripts/webapp/gen-rustdoc-panel-catalog.py",
        "count": len(crates),
        "crates": crates,
    }, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="drift-gate: exit 1 if committed catalog is stale")
    ap.add_argument("--list", action="store_true", help="print summary and exit without writing")
    args = ap.parse_args()

    current = render()

    if args.list:
        data = json.loads(current)
        print(f"crates: {data['count']}")
        names = [c["name"] for c in data["crates"]]
        print(f"first: {names[0]}")
        print(f"last:  {names[-1]}")
        return 0

    if args.check:
        if not OUT.is_file():
            print(f"DRIFT: {OUT} does not exist")
            return 1
        committed = OUT.read_text(encoding="utf-8")
        if committed != current:
            print(f"DRIFT: {OUT} differs from rendered catalog")
            return 1
        print(f"SYNC:  {OUT} is current ({json.loads(current)['count']} crates)")
        return 0

    OUT.write_text(current, encoding="utf-8")
    print(f"WROTE {OUT} ({json.loads(current)['count']} crates)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
