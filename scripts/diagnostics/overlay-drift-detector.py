#!/usr/bin/env python3
"""scripts/diagnostics/overlay-drift-detector.py — R325 (E2.M21).

Operator-pull "what have I customized on this host?" surface.
Scans /etc/sovereign-os/*.toml + parses each file directly + emits
per-overlay drift report listing which knobs the operator has
overridden vs shipped defaults.

Composes:
  - R283 operator-overlay-doctrine (SDD-030) — knows where overlays live
  - R322 state snapshot — overlays drive what each advisor returns

CLI:
  overlay-drift-detector.py list   [--overlay-dir D] [--config P]
                                    [--json|--human]
                                    every .toml overlay + its key count

  overlay-drift-detector.py show   <overlay> [--overlay-dir D]
                                    [--config P] [--json|--human]
                                    full key-value dump for one overlay

  overlay-drift-detector.py audit  [--overlay-dir D] [--config P]
                                    [--json|--human]
                                    cross-overlay rollup: total keys,
                                    by-script count, parse-error count

Operator-overlay (R283/SDD-030):
/etc/sovereign-os/overlay-drift-detector.toml
  - default_overlay_dir   /etc/sovereign-os
  - sample_dirs           [/etc/sovereign-os, ~/.config/sovereign-os]

Exit codes:
  0  rendered
  1  overlay-dir not found
  2  usage error
"""
from __future__ import annotations

import argparse
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

# Python 3.11+ has tomllib; older falls back to tomli.
try:
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R325"
SDD_VECTOR = "E2.M21"


DEFAULTS = {
    "default_overlay_dir": "/etc/sovereign-os",
}


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("overlay-drift-detector", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def collect_overlays(overlay_dir: Path) -> list[dict[str, Any]]:
    """Walk overlay_dir; parse each *.toml; return per-overlay entry."""
    if not overlay_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(overlay_dir.glob("*.toml")):
        # Inferred consumer is always derived from filename — set
        # first so it's present even when parse fails.
        entry: dict[str, Any] = {
            "overlay_file": path.name,
            "overlay_path": str(path),
            "size_bytes": path.stat().st_size if path.is_file() else 0,
            "parse_error": None,
            "keys": [],
            "key_count": 0,
            "table_count": 0,
            "inferred_consumer_script_basename": f"{path.stem}.py",
        }
        if tomllib is None:
            entry["parse_error"] = "tomllib not available"
            out.append(entry)
            continue
        try:
            body = path.read_bytes()
        except OSError as e:
            entry["parse_error"] = f"read: {e}"
            out.append(entry)
            continue
        try:
            parsed = tomllib.loads(body.decode("utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
            entry["parse_error"] = f"parse: {e}"
            out.append(entry)
            continue
        flat = _flatten(parsed)
        entry["keys"] = sorted(flat.keys())
        entry["key_count"] = len(flat)
        entry["table_count"] = sum(1 for v in parsed.values()
                                     if isinstance(v, dict))
        out.append(entry)
    return out


def _flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            new_prefix = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(_flatten(v, new_prefix))
            else:
                out[new_prefix] = v
    return out


def derive_audit(overlays: list[dict]) -> dict[str, Any]:
    total = len(overlays)
    parsed_ok = sum(1 for o in overlays if not o.get("parse_error"))
    parse_errors = sum(1 for o in overlays if o.get("parse_error"))
    total_keys = sum(o.get("key_count", 0) for o in overlays)
    return {
        "overlay_count": total,
        "parsed_ok": parsed_ok,
        "parse_errors": parse_errors,
        "total_keys_overridden": total_keys,
    }


def resolve(overlays: list[dict], name: str) -> dict | None:
    for o in overlays:
        if isinstance(o, dict) and (o.get("overlay_file") == name
                                       or o.get("overlay_file") == f"{name}.toml"):
            return o
    return None


def render_list_human(overlays: list[dict], overlay_dir: Path) -> str:
    lines = [f"── R325 sovereign-os overlay drift (E2.M21) ──",
             f"  overlay_dir: {overlay_dir}",
             f"  overlays:    {len(overlays)}", ""]
    for o in overlays:
        if o.get("parse_error"):
            mark = "ERR"
        elif o.get("key_count", 0) > 0:
            mark = "SET"
        else:
            mark = "---"
        lines.append(f"  [{mark}] {o.get('overlay_file'):40s}  "
                      f"keys={o.get('key_count')}")
        if o.get("parse_error"):
            lines.append(f"          parse_error: {o['parse_error']}")
    return "\n".join(lines)


def render_show_human(o: dict) -> str:
    lines = [f"── R325 overlay: {o.get('overlay_file')} (E2.M21) ──",
             f"  path:                   {o.get('overlay_path')}",
             f"  size:                   {o.get('size_bytes')} bytes",
             f"  inferred consumer:      {o.get('inferred_consumer_script_basename')}",
             f"  key count:              {o.get('key_count')}",
             f"  table count:            {o.get('table_count')}",
             ""]
    if o.get("parse_error"):
        lines.append(f"  parse_error: {o['parse_error']}")
        return "\n".join(lines) + "\n"
    lines.append("  operator-set dotted-path keys:")
    for k in o.get("keys", []):
        lines.append(f"    {k}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="overlay-drift-detector.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--overlay-dir", type=Path)
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("overlay")
    ps.add_argument("--overlay-dir", type=Path)
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pa = sub.add_parser("audit")
    pa.add_argument("--overlay-dir", type=Path)
    pa.add_argument("--config", type=Path)
    fa = pa.add_mutually_exclusive_group()
    fa.add_argument("--json", dest="fmt", action="store_const", const="json")
    fa.add_argument("--human", dest="fmt", action="store_const", const="human")
    pa.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)
    overlay_dir = args.overlay_dir if args.overlay_dir \
        else Path(cfg["default_overlay_dir"])

    if not overlay_dir.is_dir():
        # Not a hard error — operator may have zero overlays.
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "overlay_dir": str(overlay_dir),
                "exists": False,
                "overlays": [],
                "audit": {
                    "overlay_count": 0,
                    "parsed_ok": 0,
                    "parse_errors": 0,
                    "total_keys_overridden": 0,
                },
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R325 (E2.M21) ──")
            print(f"  overlay_dir: {overlay_dir} (not found)")
            print(f"  no overlays — operator host is on shipped defaults")
        return 1

    overlays = collect_overlays(overlay_dir)

    if args.verb == "list":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "overlay_dir": str(overlay_dir),
                "exists": True,
                "overlay_count": len(overlays),
                "overlays": overlays,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(overlays, overlay_dir), end="")
        return 0

    if args.verb == "show":
        o = resolve(overlays, args.overlay)
        if o is None:
            print(json.dumps({
                "error": f"overlay not found: {args.overlay}",
                "known": [x.get("overlay_file") for x in overlays
                           if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "overlay": o,
                "overlay_dir": str(overlay_dir),
                "config_overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(o), end="")
        return 0

    if args.verb == "audit":
        a = derive_audit(overlays)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "overlay_dir": str(overlay_dir),
                "audit": a,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R325 overlay drift audit (E2.M21) ──")
            print(f"  overlay_dir:           {overlay_dir}")
            print(f"  overlay_count:         {a['overlay_count']}")
            print(f"  parsed_ok:             {a['parsed_ok']}")
            print(f"  parse_errors:          {a['parse_errors']}")
            print(f"  total_keys_overridden: {a['total_keys_overridden']}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
