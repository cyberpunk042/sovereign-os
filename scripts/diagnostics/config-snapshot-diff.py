#!/usr/bin/env python3
"""scripts/diagnostics/config-snapshot-diff.py — R335 (E2.M26).

Given two R332 config snapshots, emit per-overlay drift:
  - added_overlays:    in B but not A
  - removed_overlays:  in A but not B
  - changed_overlays:  sha256 differs (with per-key dotted-path diff)
  - identical_overlays: sha256 matches

Sibling to R334 snapshot-diff (which diffs RUNTIME state). R335
diffs CONFIG state — the operator-pinned overlays.

CLI:
  config-snapshot-diff.py diff --before A --after B
                              [--config P] [--json|--human]

Operator-overlay (R283/SDD-030):
/etc/sovereign-os/config-snapshot-diff.toml — no knobs at present.

Exit codes:
  0  no overlay changes
  1  ≥1 added / removed / changed overlay
  2  usage error / snapshot unreadable / round mismatch
"""
from __future__ import annotations

import argparse
import base64
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

try:
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R335"
SDD_VECTOR = "E2.M26"


DEFAULTS: dict[str, Any] = {}


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("config-snapshot-diff", DEFAULTS,
                                    explicit_path=overlay_path)
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def load_snapshot(path: Path) -> tuple[dict | None, str | None]:
    if not path.is_file():
        return None, f"snapshot not found: {path}"
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"read failed: {e}"
    try:
        d = json.loads(body)
    except json.JSONDecodeError as e:
        return None, f"json parse failed: {e}"
    if not isinstance(d, dict):
        return None, "snapshot root is not an object"
    if d.get("round") != "R332":
        return None, (f"snapshot round mismatch: expected R332, "
                       f"got {d.get('round')}")
    return d, None


def _flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            new = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(_flatten(v, new))
            else:
                out[new] = v
    return out


def _parse_overlay_body(body_b64: str) -> dict[str, Any] | None:
    if tomllib is None:
        return None
    try:
        raw = base64.b64decode(body_b64, validate=True)
        return tomllib.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, tomllib.TOMLDecodeError,
             UnicodeDecodeError):
        return None


def derive_key_diff(body_a_b64: str, body_b_b64: str) -> dict[str, Any]:
    """Per-key dotted-path diff between two overlay bodies."""
    a = _parse_overlay_body(body_a_b64)
    b = _parse_overlay_body(body_b_b64)
    if a is None or b is None:
        return {"parsable": False, "added": [], "removed": [], "changed": []}
    flat_a = _flatten(a)
    flat_b = _flatten(b)
    keys_a = set(flat_a.keys())
    keys_b = set(flat_b.keys())
    added = sorted(keys_b - keys_a)
    removed = sorted(keys_a - keys_b)
    changed = sorted(k for k in (keys_a & keys_b) if flat_a[k] != flat_b[k])
    return {
        "parsable": True,
        "added": [{"key": k, "value": flat_b[k]} for k in added],
        "removed": [{"key": k, "value": flat_a[k]} for k in removed],
        "changed": [{"key": k, "before": flat_a[k], "after": flat_b[k]}
                     for k in changed],
    }


def derive_diff(snap_a: dict, snap_b: dict) -> dict[str, Any]:
    by_a = {o["overlay_file"]: o for o in snap_a.get("overlays", [])
             if isinstance(o, dict) and o.get("overlay_file")}
    by_b = {o["overlay_file"]: o for o in snap_b.get("overlays", [])
             if isinstance(o, dict) and o.get("overlay_file")}

    names_a = set(by_a.keys())
    names_b = set(by_b.keys())

    added = sorted(names_b - names_a)
    removed = sorted(names_a - names_b)
    common = sorted(names_a & names_b)

    changed: list[dict[str, Any]] = []
    identical: list[str] = []
    for name in common:
        a, b = by_a[name], by_b[name]
        if a.get("sha256") == b.get("sha256"):
            identical.append(name)
            continue
        kd = derive_key_diff(a.get("body_b64", ""), b.get("body_b64", ""))
        changed.append({
            "overlay_file": name,
            "sha256_before": a.get("sha256"),
            "sha256_after": b.get("sha256"),
            "size_before": a.get("size_bytes"),
            "size_after": b.get("size_bytes"),
            "key_diff": kd,
        })

    return {
        "added_overlays": [{"overlay_file": n,
                             "sha256": by_b[n].get("sha256"),
                             "size_bytes": by_b[n].get("size_bytes")}
                            for n in added],
        "removed_overlays": [{"overlay_file": n,
                                "sha256": by_a[n].get("sha256"),
                                "size_bytes": by_a[n].get("size_bytes")}
                              for n in removed],
        "changed_overlays": changed,
        "identical_overlays": identical,
    }


def render_human(snap_a: dict, snap_b: dict, diff: dict) -> str:
    lines = [f"── R335 sovereign-os config-snapshot-diff (E2.M26) ──",
             f"  before: {snap_a.get('captured_at')} "
             f"({snap_a.get('host')})",
             f"  after:  {snap_b.get('captured_at')} "
             f"({snap_b.get('host')})", ""]
    lines.append(f"  added overlays:     {len(diff['added_overlays'])}")
    lines.append(f"  removed overlays:   {len(diff['removed_overlays'])}")
    lines.append(f"  changed overlays:   {len(diff['changed_overlays'])}")
    lines.append(f"  identical overlays: {len(diff['identical_overlays'])}")
    for a in diff["added_overlays"]:
        lines.append(f"    [ADD ] {a['overlay_file']:36s}  "
                      f"{a['size_bytes']}B  sha256={a['sha256'][:12]}…")
    for r in diff["removed_overlays"]:
        lines.append(f"    [REM ] {r['overlay_file']:36s}  "
                      f"sha256={r['sha256'][:12]}…")
    for c in diff["changed_overlays"]:
        lines.append(f"    [CHG ] {c['overlay_file']:36s}  "
                      f"{c['size_before']}→{c['size_after']}B  "
                      f"sha256 {c['sha256_before'][:8]}…→"
                      f"{c['sha256_after'][:8]}…")
        kd = c.get("key_diff", {})
        if kd.get("parsable"):
            for k in kd.get("added", [])[:5]:
                lines.append(f"            + {k['key']} = {k['value']!r}")
            for k in kd.get("removed", [])[:5]:
                lines.append(f"            - {k['key']} = {k['value']!r}")
            for k in kd.get("changed", [])[:5]:
                lines.append(f"            ~ {k['key']}: {k['before']!r} → {k['after']!r}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="config-snapshot-diff.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("diff")
    pd.add_argument("--before", type=Path, required=True)
    pd.add_argument("--after", type=Path, required=True)
    pd.add_argument("--config", type=Path)
    fd = pd.add_mutually_exclusive_group()
    fd.add_argument("--json", dest="fmt", action="store_const", const="json")
    fd.add_argument("--human", dest="fmt", action="store_const", const="human")
    pd.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)

    snap_a, err_a = load_snapshot(args.before)
    if snap_a is None:
        print(json.dumps({"error": f"before: {err_a}", "round": ROUND,
                           "rc": 2}, indent=2), file=sys.stderr)
        return 2
    snap_b, err_b = load_snapshot(args.after)
    if snap_b is None:
        print(json.dumps({"error": f"after: {err_b}", "round": ROUND,
                           "rc": 2}, indent=2), file=sys.stderr)
        return 2

    diff = derive_diff(snap_a, snap_b)
    any_change = (diff["added_overlays"] or diff["removed_overlays"]
                   or diff["changed_overlays"])
    rc = 1 if any_change else 0

    if args.fmt == "json":
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "before_path": str(args.before),
            "after_path": str(args.after),
            "before_captured_at": snap_a.get("captured_at"),
            "after_captured_at": snap_b.get("captured_at"),
            "before_host": snap_a.get("host"),
            "after_host": snap_b.get("host"),
            "diff": diff,
            "rc": rc,
            "overlay": meta,
        }, indent=2))
    else:
        print(render_human(snap_a, snap_b, diff), end="")
    return rc


if __name__ == "__main__":
    sys.exit(main())
