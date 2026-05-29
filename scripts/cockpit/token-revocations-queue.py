#!/usr/bin/env python3
"""scripts/cockpit/token-revocations-queue.py — SDD-068 MS5b
operator-UX consumer for the selfdef API/web-token revocation
pending-restore queue.

Fourth in the IPS-quartet cockpit family (after blockset, quarantine,
revocations). Completes the quartet-paired-handle row in the
operator dashboard.

Reads /var/lib/selfdef/token-revocations/pending-restores.json.
Path overridable via SOVEREIGN_OS_TOKEN_REVOCATIONS_PENDING_PATH.

Two modes:
  --json    machine-readable for the dashboard card
  default   human-readable table with pre-rendered
            `selfdefctl restore-tokens '<handle>'` commands

Honest-offline: missing/invalid file → empty queue, exit 0.

Standing rule: We do not minimize anything.
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
        "SOVEREIGN_OS_TOKEN_REVOCATIONS_PENDING_PATH",
        "/var/lib/selfdef/token-revocations/pending-restores.json",
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
        if "principal" not in entry or "handle" not in entry:
            continue
        out.append(entry)
    out.sort(key=lambda e: e.get("seconds_remaining", 0))
    return out


def render_restore_command(entry: dict[str, Any]) -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get("Active", str(entry.get("principal", "?")))
    else:
        handle_str = str(handle)
    safe_handle = handle_str.replace("'", "'\\''")
    return f"selfdefctl restore-tokens '{safe_handle}'"


def render_classes(entry: dict[str, Any]) -> str:
    """Token class mask serializes as 'All' string or
    {'Specific': [...]} dict — render compact display."""
    classes = entry.get("token_classes", "All")
    if isinstance(classes, str):
        return classes
    if isinstance(classes, dict):
        if "Specific" in classes:
            items = classes["Specific"]
            names = []
            for c in items:
                if isinstance(c, str):
                    names.append(c)
                elif isinstance(c, dict) and "Other" in c:
                    names.append(f"other:{c['Other']}")
                else:
                    names.append(str(c))
            return ",".join(names)
    return str(classes)


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return "no pending operator-restore decisions\n"
    lines = [
        "SDD-068 — pending operator-token-restore queue",
        f"{'─' * 14} {'─' * 6} {'─' * 16} {'─' * 32}",
        f"{'principal':<14} {'left':<6} {'classes':<16} {'reason':<32}",
        f"{'─' * 14} {'─' * 6} {'─' * 16} {'─' * 32}",
    ]
    for entry in queue:
        principal = str(entry.get("principal", "?"))[:14]
        left = f"{entry.get('seconds_remaining', 0)}s"[:6]
        classes = render_classes(entry)[:16]
        reason = str(entry.get("original_reason", ""))[:32]
        lines.append(f"{principal:<14} {left:<6} {classes:<16} {reason:<32}")
        lines.append(f"  restore: $ {render_restore_command(entry)}")
        lines.append("")
    lines.append(f"{'─' * 14} {'─' * 6} {'─' * 16} {'─' * 32}")
    lines.append(
        f"{len(queue)} entries · sorted by urgency (least-time-left first)"
    )
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {
            **entry,
            "restore_command": render_restore_command(entry),
            "classes_display": render_classes(entry),
        }
        for entry in queue
    ]
    return json.dumps({"queue": enriched, "count": len(enriched)}, indent=2)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON for the dashboard card")
    p.add_argument("--path", default=str(DEFAULT_PATH),
                   help="override the pending-restores snapshot path")
    args = p.parse_args(argv)
    queue = load_queue(Path(args.path))
    if args.json:
        print(render_json(queue))
    else:
        sys.stdout.write(render_human(queue))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
