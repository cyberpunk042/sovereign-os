#!/usr/bin/env python3
"""scripts/cockpit/revocations-queue.py — SDD-067 MS5b operator-UX
consumer for the selfdef session-revocation pending-restore queue.

Third in the IPS-trio cockpit family (after blockset-queue.py for
SDD-065 + quarantine-queue.py for SDD-066). Same shape, different
domain.

Reads the selfdef-side pending-restores JSON snapshot (written by
selfdefd from its in-memory backend's `pending_restores()` call)
and surfaces it for the operator. Two modes:

  --json    machine-readable JSON for the dashboard card
  default   human-readable table with pre-rendered
            `selfdefctl restore-sessions <handle>` commands per
            entry, so operator decides: restore-now / let-TTL-
            expire-naturally.

The JSON snapshot path is conventional:
  /var/lib/selfdef/revocations/pending-restores.json

Overridable via SOVEREIGN_OS_REVOCATIONS_PENDING_PATH for testing.

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
        "SOVEREIGN_OS_REVOCATIONS_PENDING_PATH",
        "/var/lib/selfdef/revocations/pending-restores.json",
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
        if "user" not in entry or "handle" not in entry:
            continue
        out.append(entry)
    out.sort(key=lambda e: e.get("seconds_remaining", 0))
    return out


def render_restore_command(entry: dict[str, Any]) -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get("Active", str(entry.get("user", "?")))
    else:
        handle_str = str(handle)
    safe_handle = handle_str.replace("'", "'\\''")
    return f"selfdefctl restore-sessions '{safe_handle}'"


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return "no pending operator-restore decisions\n"
    lines = [
        "SDD-067 — pending operator-restore queue",
        f"{'─' * 14} {'─' * 6} {'─' * 8} {'─' * 40}",
        f"{'user':<14} {'left':<6} {'scope':<8} {'reason':<40}",
        f"{'─' * 14} {'─' * 6} {'─' * 8} {'─' * 40}",
    ]
    for entry in queue:
        user = str(entry.get("user", "?"))[:14]
        left = f"{entry.get('seconds_remaining', 0)}s"[:6]
        scope_raw = entry.get("scope", "Local")
        scope = str(scope_raw)[:8] if not isinstance(scope_raw, dict) else "SrcIp"
        reason = str(entry.get("original_reason", ""))[:40]
        lines.append(f"{user:<14} {left:<6} {scope:<8} {reason:<40}")
        lines.append(f"  restore: $ {render_restore_command(entry)}")
        lines.append("")
    lines.append(f"{'─' * 14} {'─' * 6} {'─' * 8} {'─' * 40}")
    lines.append(
        f"{len(queue)} entries · sorted by urgency (least-time-left first)"
    )
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "restore_command": render_restore_command(entry)}
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
