#!/usr/bin/env python3
"""scripts/diagnostics/snapshot-diff.py — R334 (E2.M25).

Given two R322 unified state snapshots, emit per-probe diff:
  - rc_changes: probes whose rc flipped between A and B
  - verdict_changes: probes whose verdict text changed
  - new_attention: probes attention-worthy in B but not A (regression)
  - resolved_attention: probes attention-worthy in A but not B (improvement)
  - new_probes: probes present in B but not A (catalog growth)
  - removed_probes: probes in A but not B (catalog shrink)

Operator-pull "what changed between snapshot A and snapshot B?"
Pairs with R322 for pre/post-change auditing.

CLI:
  snapshot-diff.py diff --before <PATH> --after <PATH>
                        [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): N/A — this verb is stateless
read-only over two file paths.

Exit codes:
  0  no rc changes, no new attention items (safe)
  1  ≥1 new-attention or rc regression
  2  usage error / snapshot unreadable
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


SCHEMA_VERSION = "1.0.0"
ROUND = "R334"
SDD_VECTOR = "E2.M25"


DEFAULTS: dict[str, Any] = {}


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("snapshot-diff", DEFAULTS,
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
    if d.get("round") != "R322":
        return None, (f"snapshot round mismatch: expected R322, "
                       f"got {d.get('round')}")
    return d, None


def index_probes(snap: dict) -> dict[str, dict]:
    """Index probes by name for fast lookup."""
    out = {}
    for p in snap.get("probes", []):
        if isinstance(p, dict) and p.get("name"):
            out[p["name"]] = p
    return out


def extract_verdict(probe: dict) -> str | None:
    """Pull verdict from probe's nested output dict."""
    out = probe.get("output") or {}
    if not isinstance(out, dict):
        return None
    return out.get("verdict") or out.get("status")


def derive_diff(snap_a: dict, snap_b: dict) -> dict[str, Any]:
    probes_a = index_probes(snap_a)
    probes_b = index_probes(snap_b)

    names_a = set(probes_a.keys())
    names_b = set(probes_b.keys())

    new_probes = sorted(names_b - names_a)
    removed_probes = sorted(names_a - names_b)
    common = sorted(names_a & names_b)

    rc_changes: list[dict[str, Any]] = []
    verdict_changes: list[dict[str, Any]] = []
    new_attention: list[dict[str, Any]] = []
    resolved_attention: list[dict[str, Any]] = []

    for name in common:
        a, b = probes_a[name], probes_b[name]
        rc_a, rc_b = a.get("rc"), b.get("rc")
        v_a, v_b = extract_verdict(a), extract_verdict(b)
        if rc_a != rc_b:
            rc_changes.append({
                "probe": name,
                "axis": b.get("axis"),
                "rc_before": rc_a,
                "rc_after": rc_b,
            })
        if v_a != v_b and (v_a or v_b):
            verdict_changes.append({
                "probe": name,
                "axis": b.get("axis"),
                "verdict_before": v_a,
                "verdict_after": v_b,
            })
        # Attention transitions: rc=0 ↔ rc∈{1,2}
        a_attn = rc_a in (1, 2)
        b_attn = rc_b in (1, 2)
        if not a_attn and b_attn:
            new_attention.append({
                "probe": name,
                "axis": b.get("axis"),
                "rc": rc_b,
                "verdict": v_b,
            })
        if a_attn and not b_attn:
            resolved_attention.append({
                "probe": name,
                "axis": b.get("axis"),
                "rc_before": rc_a,
                "verdict_before": v_a,
            })

    return {
        "rc_changes": rc_changes,
        "verdict_changes": verdict_changes,
        "new_attention": new_attention,
        "resolved_attention": resolved_attention,
        "new_probes": new_probes,
        "removed_probes": removed_probes,
    }


def render_human(snap_a: dict, snap_b: dict, diff: dict) -> str:
    lines = [f"── R334 sovereign-os snapshot-diff (E2.M25) ──",
             f"  before: {snap_a.get('snapshot_at')}",
             f"  after:  {snap_b.get('snapshot_at')}", ""]
    lines.append(f"  rc changes:         {len(diff['rc_changes'])}")
    lines.append(f"  verdict changes:    {len(diff['verdict_changes'])}")
    lines.append(f"  new attention:      {len(diff['new_attention'])}")
    lines.append(f"  resolved attention: {len(diff['resolved_attention'])}")
    lines.append(f"  new probes:         {len(diff['new_probes'])}")
    lines.append(f"  removed probes:     {len(diff['removed_probes'])}")
    if diff["rc_changes"]:
        lines.append("")
        lines.append("  rc changes:")
        for c in diff["rc_changes"]:
            arrow = f"{c['rc_before']}→{c['rc_after']}"
            lines.append(f"    [{arrow}] {c['probe']:28s} ({c['axis']})")
    if diff["new_attention"]:
        lines.append("")
        lines.append("  NEW attention (regression):")
        for c in diff["new_attention"]:
            lines.append(f"    [!!] {c['probe']:28s} ({c['axis']}) "
                          f"rc={c['rc']}  verdict={c['verdict']}")
    if diff["resolved_attention"]:
        lines.append("")
        lines.append("  RESOLVED attention (improvement):")
        for c in diff["resolved_attention"]:
            lines.append(f"    [OK] {c['probe']:28s} ({c['axis']}) "
                          f"was rc={c['rc_before']} {c['verdict_before']}")
    if diff["new_probes"]:
        lines.append("")
        lines.append(f"  new probes (catalog growth): {diff['new_probes']}")
    if diff["removed_probes"]:
        lines.append(f"  removed probes (catalog shrink): {diff['removed_probes']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="snapshot-diff.py")
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
    rc = 1 if (diff["new_attention"]
                or any(c["rc_after"] in (1, 2) for c in diff["rc_changes"])) else 0

    if args.fmt == "json":
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "before_path": str(args.before),
            "after_path": str(args.after),
            "before_snapshot_at": snap_a.get("snapshot_at"),
            "after_snapshot_at": snap_b.get("snapshot_at"),
            "diff": diff,
            "rc": rc,
            "overlay": meta,
        }, indent=2))
    else:
        print(render_human(snap_a, snap_b, diff), end="")
    return rc


if __name__ == "__main__":
    sys.exit(main())
