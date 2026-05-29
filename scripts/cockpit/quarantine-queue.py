#!/usr/bin/env python3
"""scripts/cockpit/quarantine-queue.py — SDD-066 MS5b operator-UX
consumer for the selfdef process-quarantine pending-release queue.

Companion to scripts/cockpit/blockset-queue.py (SDD-065 MS5b);
same shape, different domain.

Reads the selfdef-side pending-releases JSON snapshot (written by
selfdefd from its in-memory backend's `pending_releases()` call)
and surfaces it for the operator. Two modes:

  --json    machine-readable JSON for the dashboard card
  default   human-readable table with pre-rendered
            `selfdefctl release-pid <handle>` AND
            `selfdefctl kill-quarantined <handle> --signal TERM`
            commands per entry, so operator decides:
            release-now / kill-now / let-kernel-TTL-expire.

The JSON snapshot path is conventional:
  /var/lib/selfdef/quarantine/pending-releases.json

Overridable via SOVEREIGN_OS_QUARANTINE_PENDING_PATH for testing.

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
        "SOVEREIGN_OS_QUARANTINE_PENDING_PATH",
        "/var/lib/selfdef/quarantine/pending-releases.json",
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
    return f"selfdefctl release-pid '{safe_handle}'"


def render_kill_command(entry: dict[str, Any], signal: str = "TERM") -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get("Active", str(entry.get("pid", "?")))
    else:
        handle_str = str(handle)
    safe_handle = handle_str.replace("'", "'\\''")
    return f"selfdefctl kill-quarantined '{safe_handle}' --signal {signal}"


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return "no pending operator-release decisions\n"
    lines = [
        "SDD-066 — pending operator-release queue",
        f"{'─' * 8} {'─' * 6} {'─' * 8} {'─' * 40}",
        f"{'pid':<8} {'left':<6} {'scope':<8} {'reason':<40}",
        f"{'─' * 8} {'─' * 6} {'─' * 8} {'─' * 40}",
    ]
    for entry in queue:
        pid = str(entry.get("pid", "?"))[:8]
        left = f"{entry.get('seconds_remaining', 0)}s"[:6]
        scope = str(entry.get("scope", "Process"))[:8]
        reason = str(entry.get("original_reason", ""))[:40]
        lines.append(f"{pid:<8} {left:<6} {scope:<8} {reason:<40}")
        lines.append(f"  release: $ {render_release_command(entry)}")
        lines.append(f"  kill:    $ {render_kill_command(entry, 'TERM')}")
        lines.append("")
    lines.append(f"{'─' * 8} {'─' * 6} {'─' * 8} {'─' * 40}")
    lines.append(
        f"{len(queue)} entries · sorted by urgency (least-time-left first)"
    )
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {
            **entry,
            "release_command": render_release_command(entry),
            "kill_term_command": render_kill_command(entry, "TERM"),
            "kill_kill_command": render_kill_command(entry, "KILL"),
        }
        for entry in queue
    ]
    return json.dumps({"queue": enriched, "count": len(enriched)}, indent=2)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON for the dashboard card")
    p.add_argument("--path", default=str(DEFAULT_PATH),
                   help="override the pending-releases snapshot path")
    args = p.parse_args(argv)
    queue = load_queue(Path(args.path))
    if args.json:
        print(render_json(queue))
    else:
        sys.stdout.write(render_human(queue))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
