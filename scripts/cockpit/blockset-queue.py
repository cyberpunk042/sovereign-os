#!/usr/bin/env python3
"""scripts/cockpit/blockset-queue.py — SDD-065 MS5b operator-UX
consumer for the selfdef pending-extension queue.

Reads the selfdef-side pending-extension JSON snapshot (written
by selfdefd from its in-memory backend's `pending_extensions()`
call) and surfaces it for the operator. Two modes:

  --json    Emit the queue as machine-readable JSON. The
            sovereign-os dashboard card consumes this.
  (default) Human-readable terminal table with the operator-
            runnable `selfdefctl block-ip ... --authority
            operator-overridden` command pre-rendered for each
            entry — operator copies + pastes.

The JSON snapshot path is conventional:
  /var/lib/selfdef/blockset/pending-extensions.json

Overridable via SOVEREIGN_OS_BLOCKSET_PENDING_PATH for testing.

Honest-offline: if the file doesn't exist or can't be parsed,
emit an empty queue rather than failing — selfdefd may not be
running, the dashboard renders "no pending" gracefully.

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
        "SOVEREIGN_OS_BLOCKSET_PENDING_PATH",
        "/var/lib/selfdef/blockset/pending-extensions.json",
    )
)


def load_queue(path: Path = DEFAULT_PATH) -> list[dict[str, Any]]:
    """Read the JSON snapshot. Honest-offline on missing/invalid."""
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
        if "addr" not in entry or "handle" not in entry:
            continue
        out.append(entry)
    # Most-urgent first (smallest seconds_remaining) — matches
    # selfdef-blockset-backend's stable ordering.
    out.sort(key=lambda e: e.get("seconds_remaining", 0))
    return out


def render_extend_command(entry: dict[str, Any], duration: str = "24h") -> str:
    """Render the operator-runnable selfdefctl invocation."""
    addr = entry.get("addr", "?")
    reason = entry.get("original_reason", "responder-tier extension")
    # Quote-safe — the reason contains arbitrary text from the
    # correlator. Use $'...' bash quoting + escape backslashes/quotes.
    safe_reason = reason.replace("\\", "\\\\").replace("'", "'\\''")
    return (
        f"selfdefctl block-ip {addr} "
        f"--duration {duration} "
        f"--authority operator-overridden "
        f"--reason $'{safe_reason} (operator-extended via cockpit)'"
    )


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return "no pending operator-extension decisions\n"
    lines = [
        "SDD-065 — pending operator-extension queue",
        f"{'─' * 18} {'─' * 60}",
        f"{'addr':<18} {'left':<6} {'reason':<40}",
        f"{'─' * 18} {'─' * 60}",
    ]
    for entry in queue:
        addr = str(entry.get("addr", "?"))[:18]
        left = f"{entry.get('seconds_remaining', 0)}s"[:6]
        reason = str(entry.get("original_reason", ""))[:40]
        lines.append(f"{addr:<18} {left:<6} {reason:<40}")
        lines.append(f"  $ {render_extend_command(entry)}")
        lines.append("")
    lines.append(f"{'─' * 18} {'─' * 60}")
    lines.append(f"{len(queue)} entries · sorted by urgency (least-time-left first)")
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "extend_24h_command": render_extend_command(entry, "24h")}
        for entry in queue
    ]
    return json.dumps({"queue": enriched, "count": len(enriched)}, indent=2)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON for the dashboard card")
    p.add_argument("--path", default=str(DEFAULT_PATH),
                   help="override the pending-extensions snapshot path")
    args = p.parse_args(argv)
    queue = load_queue(Path(args.path))
    if args.json:
        print(render_json(queue))
    else:
        sys.stdout.write(render_human(queue))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
