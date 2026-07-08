#!/usr/bin/env python3
"""scripts/cockpit/env-scrubs-queue.py — SDD-074 MS5b.

Tenth in the IPS-dectet cockpit family. Extends the
nonet-paired-handle row to the dectet at the in-memory
secret-residency axis.

Reads /var/lib/selfdef/env-scrubs/pending-restores.json.
Path overridable via SOVEREIGN_OS_ENV_SCRUBS_PENDING_PATH.

UX note: variable NAMES are displayed in the human-table because
the operator needs to see them to assess scope, but they're
truncated by default to 24 chars per entry — the operator can
toggle full display via --show-full-names. Full names always in
audit log.
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
        "SOVEREIGN_OS_ENV_SCRUBS_PENDING_PATH",
        "/var/lib/selfdef/env-scrubs/pending-restores.json",
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
        handle_str = handle.get("Active", handle.get("NoMatch", str(entry.get("pid", "?"))))
    else:
        handle_str = str(handle)
    safe_handle = handle_str.replace("'", "'\\''")
    return f"selfdefctl restore-env '{safe_handle}'"


def render_vars(entry: dict[str, Any], show_full: bool) -> str:
    vars_list = entry.get("vars", [])
    if not isinstance(vars_list, list):
        return "?"
    joined = ",".join(str(v) for v in vars_list)
    if show_full or len(joined) <= 24:
        return joined
    return joined[:21] + "..."


def render_human(queue: list[dict[str, Any]], show_full_names: bool) -> str:
    if not queue:
        return "no pending operator-restore decisions\n"
    lines = [
        "SDD-074 — pending operator-env-scrub-restore queue",
        f"{'─' * 8} {'─' * 6} {'─' * 4} {'─' * 24} {'─' * 22}",
        f"{'pid':<8} {'left':<6} {'vars':<4} {'var-names':<24} {'reason':<22}",
        f"{'─' * 8} {'─' * 6} {'─' * 4} {'─' * 24} {'─' * 22}",
    ]
    for entry in queue:
        pid = str(entry.get("pid", "?"))[:8]
        left = f"{entry.get('seconds_remaining', 0)}s"[:6]
        n_vars = str(entry.get("vars_scrubbed", 0))[:4]
        names = render_vars(entry, show_full_names)[:24] if not show_full_names else render_vars(entry, True)
        reason = str(entry.get("original_reason", ""))[:22]
        lines.append(f"{pid:<8} {left:<6} {n_vars:<4} {names:<24} {reason:<22}")
        lines.append(f"  restore: $ {render_restore_command(entry)}")
        lines.append("")
    lines.append(f"{'─' * 8} {'─' * 6} {'─' * 4} {'─' * 24} {'─' * 22}")
    lines.append(
        f"{len(queue)} entries · sorted by urgency · note: restore is "
        "queue-clear + audit only (scrubbed memory is gone)"
    )
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "restore_command": render_restore_command(entry),
         "vars_display": render_vars(entry, True)}
        for entry in queue
    ]
    return json.dumps({"queue": enriched, "count": len(enriched)}, indent=2)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true")
    p.add_argument("--path", default=str(DEFAULT_PATH))
    p.add_argument(
        "--show-full-names",
        action="store_true",
        help="Show full variable names (default: truncate at 24 chars for UX)",
    )
    args = p.parse_args(argv)
    queue = load_queue(Path(args.path))
    if args.json:
        print(render_json(queue))
    else:
        sys.stdout.write(render_human(queue, args.show_full_names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
