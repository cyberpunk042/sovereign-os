#!/usr/bin/env python3
"""scripts/diagnostics/apply-audit.py — R327 (E9.M11) query CLI.

Operator-pull query surface over the apply-audit log written by
scripts/lib/apply_audit.py.

CLI:
  apply-audit.py list      [--verb V] [--wrote-only] [--limit N]
                            [--config P] [--json|--human]
                              all rows (most-recent-last)

  apply-audit.py tail      [--n N] [--config P] [--json|--human]
                              last N rows (default 20)

  apply-audit.py by-verb   <verb> [--config P] [--json|--human]
                              all rows for one verb

  apply-audit.py audit     [--config P] [--json|--human]
                              rollup: total rows, by-verb counts,
                              gate-violation count, wrote count

Operator-overlay (R283/SDD-030):
/etc/sovereign-os/apply-audit.toml — sets audit_path_override.

Exit codes:
  0  rendered (empty log is rc=0)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "scripts" / "lib"
sys.path.insert(0, str(LIB_PATH))

import apply_audit  # noqa: E402

try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R327"
SDD_VECTOR = "E9.M11"


DEFAULTS = {
    "audit_path_override": "",
}


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("apply-audit", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def _override(cfg: dict) -> Path | None:
    o = cfg.get("audit_path_override", "")
    return Path(o) if o else None


def derive_audit(rows: list[dict]) -> dict[str, Any]:
    by_verb: dict[str, int] = {}
    gate_violations = 0
    wrote_count = 0
    for r in rows:
        v = r.get("verb", "?")
        by_verb[v] = by_verb.get(v, 0) + 1
        if not r.get("gates_satisfied"):
            gate_violations += 1
        if r.get("wrote"):
            wrote_count += 1
    return {
        "total_rows": len(rows),
        "by_verb": dict(sorted(by_verb.items())),
        "gate_violations": gate_violations,
        "wrote_count": wrote_count,
    }


def render_list_human(rows: list[dict]) -> str:
    lines = [f"── R327 sovereign-os apply audit (E9.M11) ──",
             f"  row count: {len(rows)}", ""]
    for r in rows[-30:]:
        mark = "WROTE" if r.get("wrote") else "dry  "
        lines.append(f"  [{mark}] {r.get('tick_at'):<22s} {r.get('verb'):>32s}  "
                      f"rc={r.get('rc')} gates_ok={r.get('gates_satisfied')}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="apply-audit.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--verb")
    pl.add_argument("--wrote-only", action="store_true")
    pl.add_argument("--limit", type=int)
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    pt = sub.add_parser("tail")
    pt.add_argument("--n", type=int, default=20)
    pt.add_argument("--config", type=Path)
    ft = pt.add_mutually_exclusive_group()
    ft.add_argument("--json", dest="fmt", action="store_const", const="json")
    ft.add_argument("--human", dest="fmt", action="store_const", const="human")
    pt.set_defaults(fmt="json")

    pbv = sub.add_parser("by-verb")
    pbv.add_argument("verb_name")
    pbv.add_argument("--config", type=Path)
    fbv = pbv.add_mutually_exclusive_group()
    fbv.add_argument("--json", dest="fmt", action="store_const", const="json")
    fbv.add_argument("--human", dest="fmt", action="store_const", const="human")
    pbv.set_defaults(fmt="json")

    pa = sub.add_parser("audit")
    pa.add_argument("--config", type=Path)
    fa = pa.add_mutually_exclusive_group()
    fa.add_argument("--json", dest="fmt", action="store_const", const="json")
    fa.add_argument("--human", dest="fmt", action="store_const", const="human")
    pa.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)
    override = _override(cfg)

    if args.cmd == "list":
        rows = apply_audit.query(
            audit_path_override=override,
            verb=args.verb,
            wrote_only=args.wrote_only,
            limit=args.limit,
        )
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "verb_filter": args.verb,
                "wrote_only": args.wrote_only,
                "limit": args.limit,
                "row_count": len(rows),
                "rows": rows,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(rows), end="")
        return 0

    if args.cmd == "tail":
        rows = apply_audit.query(audit_path_override=override,
                                  limit=args.n)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "n": args.n,
                "row_count": len(rows),
                "rows": rows,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(rows), end="")
        return 0

    if args.cmd == "by-verb":
        rows = apply_audit.query(audit_path_override=override,
                                  verb=args.verb_name)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "verb_queried": args.verb_name,
                "row_count": len(rows),
                "rows": rows,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R327 by-verb {args.verb_name} (E9.M11) ──")
            print(f"  rows: {len(rows)}")
            for r in rows[-30:]:
                mark = "WROTE" if r.get("wrote") else "dry  "
                print(f"  [{mark}] {r.get('tick_at'):<22s} "
                      f"rc={r.get('rc')} gates_ok={r.get('gates_satisfied')}")
        return 0

    if args.cmd == "audit":
        rows = apply_audit.query(audit_path_override=override)
        a = derive_audit(rows)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                **a,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R327 apply-audit rollup (E9.M11) ──")
            print(f"  total rows:       {a['total_rows']}")
            print(f"  wrote count:      {a['wrote_count']}")
            print(f"  gate violations:  {a['gate_violations']}")
            print(f"  by verb:")
            for v, n in a["by_verb"].items():
                print(f"    {v:>32s}: {n}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
