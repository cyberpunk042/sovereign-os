#!/usr/bin/env python3
"""scripts/intelligence/memory-changes.py — Memory OS graph-diff + admission
core (M060 D-07 / R10093-R10096).

The data model behind the D-07 memory-changes cockpit dashboard. Reads the
Memory OS (M028) published state and projects it onto the dashboard shape:
per-type memory counts, 11-stage admission-lifecycle occupancy, the graph diff
between two memory snapshot versions, and the queue of pending promote/pin/
forget operations awaiting operator sign-off.

  M028 8 memory types (E0260 + E0265 reward, verbatim):
    working · episodic · semantic · procedural · temporal · value · kv · reward
  M028 11-stage admission lifecycle (M00471, verbatim):
    observe · classify · quarantine · link · score · store-raw · extract ·
    verify · promote · decay · archive
  MS039 7 trust dimensions (the D-07 filter set):
    trust · value · freshness · permission · topic · user-scope · failure-relevance

Sovereignty: stdlib-only. The state path follows the /run/sovereign-os/*.json
convention. Absent state → all counts 0 + empty diff/pending + profile=private
(graceful), NEVER a crash. Mutations (promote/pin/forget) are MS003-signed CLI
verbs (MS043 R10212) — this surface is read-only. This is the `core` surface of
the §1g 8-surface ladder for the memory-changes module; `scripts/operator/
memory-changes-api.py` serves it, `sovereign-osctl memory-changes` drives it,
the D-07 webapp renders it.

  memory-changes.py snapshot  [--json]   full dashboard model
  memory-changes.py types     [--json]   the 8 memory-type counts only
  memory-changes.py lifecycle [--json]   the 11-stage occupancy only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

MEMORY_STATE = Path(os.environ.get(
    "SOVEREIGN_OS_MEMORY_STATE", "/run/sovereign-os/memory.json",
))

# M028 verbatim.
MEMORY_TYPES = ("working", "episodic", "semantic", "procedural",
                "temporal", "value", "kv", "reward")
LIFECYCLE_STAGES = ("observe", "classify", "quarantine", "link", "score",
                    "store-raw", "extract", "verify", "promote", "decay", "archive")
# MS039 verbatim (the D-07 trust-dimension filter set).
TRUST_DIMENSIONS = ("trust", "value", "freshness", "permission",
                    "topic", "user-scope", "failure-relevance")
_VALID_DIFF_OP = frozenset({"added", "changed", "removed"})
_VALID_PENDING_OP = frozenset({"promote", "pin", "forget"})


def _read_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _counts(state: dict[str, Any]) -> dict[str, int]:
    raw = state.get("counts") or {}
    out = {t: 0 for t in MEMORY_TYPES}
    for t in MEMORY_TYPES:
        v = raw.get(t)
        if isinstance(v, (int, float)):
            out[t] = int(v)
    return out


def _lifecycle(state: dict[str, Any]) -> list[list[Any]]:
    """11-stage occupancy as [[stage, count], ...] in canonical order."""
    raw = state.get("lifecycle") or {}
    # accept either a {stage:count} map or a [[stage,count]] list
    if isinstance(raw, list):
        raw = {row[0]: row[1] for row in raw if isinstance(row, (list, tuple)) and len(row) >= 2}
    out = []
    for stage in LIFECYCLE_STAGES:
        v = raw.get(stage)
        out.append([stage, int(v) if isinstance(v, (int, float)) else 0])
    return out


def _diffs(state: dict[str, Any]) -> list[dict[str, str]]:
    raw = state.get("diffs")
    if not isinstance(raw, list):
        return []
    out = []
    for d in raw:
        if not isinstance(d, dict):
            continue
        op = d.get("op")
        if op not in _VALID_DIFF_OP:
            op = "changed"
        out.append({"op": op, "text": str(d.get("text", ""))})
    return out


def _pending(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = state.get("pending")
    if not isinstance(raw, list):
        return []
    out = []
    for p in raw:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        op = p.get("op")
        if op not in _VALID_PENDING_OP:
            op = "promote"
        out.append({
            "id": str(p["id"]),
            "op": op,
            "mtype": p.get("mtype", "semantic"),
            "scope": p.get("scope", ""),
            "delta": p.get("delta", ""),
            "requester": p.get("requester", "unknown"),
        })
    return out


def snapshot() -> dict[str, Any]:
    """The full D-07 dashboard model."""
    state = _read_state(MEMORY_STATE)
    return {
        "schema_version": SCHEMA_VERSION,
        "counts": _counts(state),
        "profile": state.get("profile", "private"),
        "lifecycle": _lifecycle(state),
        "diffBase": state.get("diffBase", "—"),
        "diffHead": state.get("diffHead", "—"),
        "diffs": _diffs(state),
        "pending": _pending(state),
        "trust_dimensions": list(TRUST_DIMENSIONS),
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Memory OS graph-diff core (M060 D-07)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("snapshot", "types", "lifecycle"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    if cmd == "types":
        _print(snapshot()["counts"])
    elif cmd == "lifecycle":
        _print(snapshot()["lifecycle"])
    else:
        _print(snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(main())
