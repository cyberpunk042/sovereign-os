#!/usr/bin/env python3
"""scripts/cockpit/socket-fd-revocations-queue.py — SDD-073 MS5b.

Ninth in the IPS-nonet cockpit family. Extends the
octet-paired-handle row to the nonet at the per-connection
severance axis.

Reads /var/lib/selfdef/socket-fd-revocations/pending-restores.json.
Path overridable via SOVEREIGN_OS_SOCKET_FD_REVOCATIONS_PENDING_PATH.
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
        "SOVEREIGN_OS_SOCKET_FD_REVOCATIONS_PENDING_PATH",
        "/var/lib/selfdef/socket-fd-revocations/pending-restores.json",
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
        if "pid" not in entry or "fd" not in entry or "handle" not in entry:
            continue
        out.append(entry)
    out.sort(key=lambda e: e.get("seconds_remaining", 0))
    return out


def render_restore_command(entry: dict[str, Any]) -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get(
            "Active", handle.get("Stale", f"{entry.get('pid', '?')}:{entry.get('fd', '?')}")
        )
    else:
        handle_str = str(handle)
    safe_handle = handle_str.replace("'", "'\\''")
    return f"selfdefctl restore-fd '{safe_handle}'"


def render_protocol(entry: dict[str, Any]) -> str:
    protocol = entry.get("protocol", "Any")
    if isinstance(protocol, str):
        return protocol
    return str(protocol)


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return "no pending operator-restore decisions\n"
    lines = [
        "SDD-073 — pending operator-socket-fd-restore queue",
        f"{'─' * 8} {'─' * 4} {'─' * 6} {'─' * 8} {'─' * 30}",
        f"{'pid':<8} {'fd':<4} {'left':<6} {'proto':<8} {'reason':<30}",
        f"{'─' * 8} {'─' * 4} {'─' * 6} {'─' * 8} {'─' * 30}",
    ]
    for entry in queue:
        pid = str(entry.get("pid", "?"))[:8]
        fd = str(entry.get("fd", "?"))[:4]
        left = f"{entry.get('seconds_remaining', 0)}s"[:6]
        protocol = render_protocol(entry)[:8]
        reason = str(entry.get("original_reason", ""))[:30]
        lines.append(f"{pid:<8} {fd:<4} {left:<6} {protocol:<8} {reason:<30}")
        lines.append(f"  restore: $ {render_restore_command(entry)}")
        lines.append("")
    lines.append(f"{'─' * 8} {'─' * 4} {'─' * 6} {'─' * 8} {'─' * 30}")
    lines.append(
        f"{len(queue)} entries · sorted by urgency · note: restore is "
        "audit-log + queue-clear only (fds are not reopenable)"
    )
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "restore_command": render_restore_command(entry),
         "protocol_display": render_protocol(entry)}
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
