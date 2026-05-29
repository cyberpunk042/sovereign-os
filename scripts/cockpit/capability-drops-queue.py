#!/usr/bin/env python3
"""scripts/cockpit/capability-drops-queue.py — SDD-075 MS5b.

Eleventh in the IPS-undectet cockpit family. Extends the
dectet-paired-handle row to the undectet at the per-process
privilege-set axis.

Reads /var/lib/selfdef/capability-drops/pending-restores.json.
Path overridable via SOVEREIGN_OS_CAPABILITY_DROPS_PENDING_PATH.

UX note: capability drops are irreversible at the kernel level.
The "restore" command is queue-clear + audit only — operator
must restart the process to recover the dropped capability.
The footer of every queue rendering surfaces this caveat.
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
        "SOVEREIGN_OS_CAPABILITY_DROPS_PENDING_PATH",
        "/var/lib/selfdef/capability-drops/pending-restores.json",
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


def render_restore_command(entry: dict[str, Any]) -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get(
            "Active", handle.get("Redundant", str(entry.get("pid", "?")))
        )
    else:
        handle_str = str(handle)
    safe_handle = handle_str.replace("'", "'\\''")
    return f"selfdefctl restore-cap '{safe_handle}'"


def render_caps(entry: dict[str, Any]) -> str:
    caps = entry.get("caps", [])
    if not isinstance(caps, list):
        return "?"
    joined = ",".join(str(c) for c in caps)
    if len(joined) <= 30:
        return joined
    return joined[:27] + "..."


def render_scope(entry: dict[str, Any]) -> str:
    scope = entry.get("scope", "AllSets")
    if isinstance(scope, str):
        return scope
    return str(scope)


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return (
            "no pending operator-restore decisions\n"
            "(note: capability drops are irreversible at the kernel level — "
            "restore is queue-clear + audit only)\n"
        )
    lines = [
        "SDD-075 — pending operator-capability-drop-restore queue",
        f"{'─' * 8} {'─' * 4} {'─' * 6} {'─' * 10} {'─' * 30}",
        f"{'pid':<8} {'caps':<4} {'left':<6} {'scope':<10} {'cap-names':<30}",
        f"{'─' * 8} {'─' * 4} {'─' * 6} {'─' * 10} {'─' * 30}",
    ]
    for entry in queue:
        pid = str(entry.get("pid", "?"))[:8]
        n_caps = str(entry.get("caps_dropped", 0))[:4]
        left = f"{entry.get('seconds_remaining', 0)}s"[:6]
        scope = render_scope(entry)[:10]
        cap_names = render_caps(entry)[:30]
        lines.append(f"{pid:<8} {n_caps:<4} {left:<6} {scope:<10} {cap_names:<30}")
        lines.append(f"  restore: $ {render_restore_command(entry)}")
        lines.append(f"  reason:  {str(entry.get('original_reason', ''))[:64]}")
        lines.append("")
    lines.append(f"{'─' * 8} {'─' * 4} {'─' * 6} {'─' * 10} {'─' * 30}")
    lines.append(
        f"{len(queue)} entries · sorted by urgency · note: capability drops are "
        "irreversible at kernel level — restore is queue-clear + audit only "
        "(operator must restart the process to recover the dropped capability)"
    )
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "restore_command": render_restore_command(entry),
         "caps_display": render_caps(entry),
         "scope_display": render_scope(entry)}
        for entry in queue
    ]
    return json.dumps(
        {
            "queue": enriched,
            "count": len(enriched),
            "irreversibility_note": "capability drops are irreversible at the kernel level — restore is queue-clear + audit only",
        },
        indent=2,
    )


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
