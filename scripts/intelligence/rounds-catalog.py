#!/usr/bin/env python3
"""scripts/intelligence/rounds-catalog.py — R321 (E9.M9).

Meta-navigation surface for the perpetual E9.M3 intake loop. Parses
docs/standing-directives/2026-05-17-operator-mandate.md to extract
every shipped sovereign-os round + its Epic/Module mapping, then
exposes operator-pull verbs for navigation across the 300+ round
codebase.

CLI:
  rounds-catalog.py list             [--config P] [--json|--human]
                                       every shipped round + module
  rounds-catalog.py show    <round>  [--config P] [--json|--human]
  rounds-catalog.py by-epic <epic>   [--config P] [--json|--human]
                                       (e.g. E1 / E2 / ...)
  rounds-catalog.py recent  [--n N]  [--config P] [--json|--human]
                                       last N rounds by numeric order

Operator-overlay (R283/SDD-030): /etc/sovereign-os/rounds-catalog.toml
can override the mandate_path (e.g. point at a fleet-aggregated file).

Exit codes:
  0  rendered
  1  unknown round / no matches
  2  usage error / mandate file unreadable
"""
from __future__ import annotations

import argparse
import json
import re
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
ROUND = "R321"
SDD_VECTOR = "E9.M9"


DEFAULTS = {
    "mandate_path": str(
        REPO_ROOT / "docs" / "standing-directives"
                  / "2026-05-17-operator-mandate.md"
    ),
}


# Regex for mandate table rows like:
# | E1.M16 | **256 GB ...** | ✓ shipped | R279 |
ROW_RE = re.compile(
    r"^\|\s*(E\d+\.M\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$"
)

# Round ID extractor — recognizes R<n>, R<n>+, SD-R<n>, R<n>-R<m>.
ROUND_RE = re.compile(r"(SD-R\d+|R\d+\+?)")


def parse_mandate(path: Path) -> list[dict[str, Any]]:
    """Walk the mandate file, return [{module, title, status, rounds:[...]}]."""
    if not path.is_file():
        return []
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in body.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        module, title, status, rounds_cell = m.groups()
        # Skip the header row.
        if module.upper() == "ID" or module.lower() == "module":
            continue
        rounds = ROUND_RE.findall(rounds_cell)
        # De-dup but preserve order.
        seen: set[str] = set()
        rounds_dedup = []
        for r in rounds:
            if r not in seen:
                rounds_dedup.append(r)
                seen.add(r)
        out.append({
            "module": module,
            "epic": module.split(".")[0],
            "title": title.strip().strip("*").strip(),
            "status": status.strip(),
            "rounds": rounds_dedup,
            "rounds_raw": rounds_cell.strip(),
        })
    return out


def expand_rounds(rows: list[dict]) -> list[dict[str, Any]]:
    """Flatten module rows into per-round entries (1 row → N rounds)."""
    out: list[dict[str, Any]] = []
    for r in rows:
        if not r.get("rounds"):
            continue
        for rnd in r["rounds"]:
            out.append({
                "round": rnd,
                "module": r["module"],
                "epic": r["epic"],
                "title": r["title"],
                "status": r["status"],
                "rounds_raw": r["rounds_raw"],
            })
    return out


def round_sort_key(round_id: str) -> tuple[int, int]:
    """Sort key — SD-R rounds (selfdef) sorted separately from R rounds."""
    if round_id.startswith("SD-R"):
        try:
            return (1, int(round_id[4:].rstrip("+")))
        except ValueError:
            return (1, 0)
    if round_id.startswith("R"):
        try:
            return (0, int(round_id[1:].rstrip("+")))
        except ValueError:
            return (0, 0)
    return (2, 0)


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("rounds-catalog", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def render_list_human(rounds: list[dict]) -> str:
    lines = [f"── R321 sovereign-os rounds catalog (E9.M9) ──",
             f"  total rounds: {len(rounds)}", ""]
    # Group by epic.
    by_epic: dict[str, list[dict]] = {}
    for r in rounds:
        by_epic.setdefault(r["epic"], []).append(r)
    for epic in sorted(by_epic.keys()):
        items = sorted(by_epic[epic], key=lambda r: round_sort_key(r["round"]))
        lines.append(f"  ── {epic} ({len(items)} rounds) ──")
        for r in items:
            lines.append(f"    {r['round']:>10s}  {r['module']:>10s}  "
                          f"{r['title'][:70]}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(matches: list[dict]) -> str:
    lines = [f"── R321 round show (E9.M9) ──"]
    for r in matches:
        lines.append("")
        lines.append(f"  {r['round']}  ({r['module']} — {r['epic']})")
        lines.append(f"    status: {r['status']}")
        lines.append(f"    title:  {r['title']}")
        if r.get("rounds_raw") and r["rounds_raw"] != r["round"]:
            lines.append(f"    full cell: {r['rounds_raw']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="rounds-catalog.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("round")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pe = sub.add_parser("by-epic")
    pe.add_argument("epic")
    pe.add_argument("--config", type=Path)
    fe = pe.add_mutually_exclusive_group()
    fe.add_argument("--json", dest="fmt", action="store_const", const="json")
    fe.add_argument("--human", dest="fmt", action="store_const", const="human")
    pe.set_defaults(fmt="json")

    pr = sub.add_parser("recent")
    pr.add_argument("--n", type=int, default=10)
    pr.add_argument("--config", type=Path)
    fr = pr.add_mutually_exclusive_group()
    fr.add_argument("--json", dest="fmt", action="store_const", const="json")
    fr.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)
    mandate_path = Path(cfg["mandate_path"])
    if not mandate_path.is_file():
        print(json.dumps({
            "error": f"mandate file not found: {mandate_path}",
            "round": ROUND,
        }, indent=2), file=sys.stderr)
        return 2

    rows = parse_mandate(mandate_path)
    rounds = expand_rounds(rows)

    if args.verb == "list":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "mandate_path": str(mandate_path),
                "module_count": len(rows),
                "round_count": len(rounds),
                "rounds": rounds,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(rounds), end="")
        return 0

    if args.verb == "show":
        # Accept R280, r280, 280, or SD-R97 — normalize.
        q = args.round.strip()
        if q.lower().startswith("sd-r"):
            q = "SD-R" + q[4:]
        elif q.lower().startswith("r"):
            q = "R" + q[1:]
        elif q.isdigit():
            q = "R" + q
        matches = [r for r in rounds if r["round"] == q
                    or r["round"].rstrip("+") == q.rstrip("+")]
        if not matches:
            print(json.dumps({
                "error": f"round not found in mandate: {q}",
                "round": ROUND,
                "queried": q,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "queried": q,
                "matches": matches,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(matches), end="")
        return 0

    if args.verb == "by-epic":
        e = args.epic.strip().upper()
        if not e.startswith("E"):
            e = "E" + e
        matches = [r for r in rounds if r["epic"] == e]
        if not matches:
            print(json.dumps({
                "error": f"no rounds in epic: {e}",
                "round": ROUND,
                "queried": e,
            }, indent=2), file=sys.stderr)
            return 1
        # Sort within epic.
        matches.sort(key=lambda r: round_sort_key(r["round"]))
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "epic": e,
                "match_count": len(matches),
                "rounds": matches,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R321 by-epic {e} (E9.M9) — {len(matches)} rounds ──")
            for r in matches:
                print(f"  {r['round']:>10s}  {r['module']:>10s}  "
                      f"{r['title'][:70]}")
        return 0

    if args.verb == "recent":
        # Take last N by numeric sort.
        sorted_rounds = sorted(rounds, key=lambda r: round_sort_key(r["round"]))
        recent = sorted_rounds[-args.n:]
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "n": args.n,
                "rounds": recent,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R321 recent {args.n} rounds (E9.M9) ──")
            for r in recent:
                print(f"  {r['round']:>10s}  {r['module']:>10s}  "
                      f"{r['title'][:70]}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
