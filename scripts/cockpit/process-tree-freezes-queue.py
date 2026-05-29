#!/usr/bin/env python3
"""scripts/cockpit/process-tree-freezes-queue.py — SDD-072 MS5b.

Eighth in the IPS-octet cockpit family. Extends the
septet-paired-handle row to the octet at the process-graph
containment axis.

Reads /var/lib/selfdef/process-tree-freezes/pending-thaws.json.
Path overridable via SOVEREIGN_OS_PROCESS_TREE_FREEZES_PENDING_PATH.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(
    os.environ.get(
        "SOVEREIGN_OS_PROCESS_TREE_FREEZES_PENDING_PATH",
        "/var/lib/selfdef/process-tree-freezes/pending-thaws.json",
    )
)


def load_queue(path: Path = DEFAULT_PATH) -> list[dict[str, Any]]:
    try:
        raw = path.read_text()
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        if "root_pid" not in entry or "handle" not in entry:
            continue
        out.append(entry)
    out.sort(key=lambda e: e.get("seconds_remaining", 0))
    return out


def render_thaw_command(entry: dict[str, Any]) -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get("Active", str(entry.get("root_pid", "?")))
    else:
        handle_str = str(handle)
    safe_handle = handle_str.replace("'", "'\\''")
    return f"selfdefctl thaw-tree '{safe_handle}'"


def render_scope(entry: dict[str, Any]) -> str:
    scope = entry.get("scope", "Descendants")
    if isinstance(scope, str):
        return scope
    return str(scope)


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return "no pending operator-thaw decisions\n"
    lines = [
        "SDD-072 — pending operator-process-tree-thaw queue",
        f"{'─' * 10} {'─' * 6} {'─' * 6} {'─' * 18} {'─' * 28}",
        f"{'root_pid':<10} {'pids':<6} {'left':<6} {'scope':<18} {'reason':<28}",
        f"{'─' * 10} {'─' * 6} {'─' * 6} {'─' * 18} {'─' * 28}",
    ]
    for entry in queue:
        root = str(entry.get("root_pid", "?"))[:10]
        pids = str(entry.get("frozen_pid_count", "?"))[:6]
        left = f"{entry.get('seconds_remaining', 0)}s"[:6]
        scope = render_scope(entry)[:18]
        reason = str(entry.get("original_reason", ""))[:28]
        lines.append(f"{root:<10} {pids:<6} {left:<6} {scope:<18} {reason:<28}")
        lines.append(f"  thaw: $ {render_thaw_command(entry)}")
        lines.append("")
    lines.append(f"{'─' * 10} {'─' * 6} {'─' * 6} {'─' * 18} {'─' * 28}")
    lines.append(f"{len(queue)} entries · sorted by urgency")
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "thaw_command": render_thaw_command(entry),
         "scope_display": render_scope(entry)}
        for entry in queue
    ]
    return json.dumps({"queue": enriched, "count": len(enriched)}, indent=2)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true")
    p.add_argument("--path", default=str(DEFAULT_PATH))
    args = p.parse_args(argv)
    queue = load_queue(Path(args.path))
    if args.json:
        print(render_json(queue))
    else:
        sys.stdout.write(render_human(queue))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
