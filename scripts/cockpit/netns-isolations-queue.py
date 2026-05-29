#!/usr/bin/env python3
"""scripts/cockpit/netns-isolations-queue.py — SDD-070 MS5b.

Sixth in the IPS-hexet cockpit family. Extends the
pentet-paired-handle row to the hexet at the kernel-containment axis.

Reads /var/lib/selfdef/netns-isolations/pending-releases.json.
Path overridable via SOVEREIGN_OS_NETNS_ISOLATIONS_PENDING_PATH.
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
        "SOVEREIGN_OS_NETNS_ISOLATIONS_PENDING_PATH",
        "/var/lib/selfdef/netns-isolations/pending-releases.json",
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
        if "pid" not in entry or "handle" not in entry:
            continue
        out.append(entry)
    out.sort(key=lambda e: e.get("seconds_remaining", 0))
    return out


def render_release_command(entry: dict[str, Any]) -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get("Active", str(entry.get("pid", "?")))
    else:
        handle_str = str(handle)
    safe_handle = handle_str.replace("'", "'\\''")
    return f"selfdefctl release-isolation '{safe_handle}'"


def render_scope(entry: dict[str, Any]) -> str:
    scope = entry.get("scope", "NetOnly")
    if isinstance(scope, str):
        return scope
    return str(scope)


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return "no pending operator-release decisions\n"
    lines = [
        "SDD-070 — pending operator-netns-isolation-release queue",
        f"{'─' * 8} {'─' * 6} {'─' * 14} {'─' * 32}",
        f"{'pid':<8} {'left':<6} {'scope':<14} {'reason':<32}",
        f"{'─' * 8} {'─' * 6} {'─' * 14} {'─' * 32}",
    ]
    for entry in queue:
        pid = str(entry.get("pid", "?"))[:8]
        left = f"{entry.get('seconds_remaining', 0)}s"[:6]
        scope = render_scope(entry)[:14]
        reason = str(entry.get("original_reason", ""))[:32]
        lines.append(f"{pid:<8} {left:<6} {scope:<14} {reason:<32}")
        lines.append(f"  release: $ {render_release_command(entry)}")
        lines.append("")
    lines.append(f"{'─' * 8} {'─' * 6} {'─' * 14} {'─' * 32}")
    lines.append(f"{len(queue)} entries · sorted by urgency")
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "release_command": render_release_command(entry),
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
