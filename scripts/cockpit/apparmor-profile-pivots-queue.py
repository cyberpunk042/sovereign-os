#!/usr/bin/env python3
"""scripts/cockpit/apparmor-profile-pivots-queue.py — SDD-077 MS5b.

Thirteenth in the IPS-tridectet cockpit family. Extends the
duodectet-paired-handle row to the tridectet at the MAC
(Mandatory Access Control) policy axis.

Reads /var/lib/selfdef/apparmor-profile-pivots/pending-restores.json.
Path overridable via SOVEREIGN_OS_APPARMOR_PROFILE_PIVOTS_PENDING_PATH.

UX note: AppArmor profile pivots are one-way at the kernel level.
The "restore" command is queue-clear + audit only — operator must
restart the process under its original profile via the init system
to recover. Every queue rendering surfaces this caveat in the
footer plus a per-row requires_process_restart flag.
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
        "SOVEREIGN_OS_APPARMOR_PROFILE_PIVOTS_PENDING_PATH",
        "/var/lib/selfdef/apparmor-profile-pivots/pending-restores.json",
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
        if "pid" not in entry or "target_profile" not in entry or "handle" not in entry:
            continue
        out.append(entry)
    out.sort(key=lambda e: e.get("seconds_remaining", 0))
    return out


def render_restore_command(entry: dict[str, Any]) -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get(
            "Active",
            handle.get("Denied", handle.get("NoTarget", handle.get("Stale", str(entry.get("pid", "?"))))),
        )
    else:
        handle_str = str(handle)
    safe_handle = str(handle_str).replace("'", "'\\''")
    return f"selfdefctl restore-profile '{safe_handle}'"


def render_target_profile(entry: dict[str, Any]) -> str:
    tp = entry.get("target_profile", "?")
    if not isinstance(tp, str):
        tp = str(tp)
    if len(tp) <= 28:
        return tp
    return tp[:25] + "..."


def render_original_profile(entry: dict[str, Any]) -> str:
    op = entry.get("original_profile", "?")
    if not isinstance(op, str):
        op = str(op)
    if len(op) <= 20:
        return op
    return op[:17] + "..."


def render_scope(entry: dict[str, Any]) -> str:
    scope = entry.get("scope", "Profile")
    if isinstance(scope, str):
        return scope
    return str(scope)


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return (
            "no pending operator-restore decisions\n"
            "(note: AppArmor profile pivots are one-way at the kernel level — "
            "restore is queue-clear + audit only)\n"
        )
    lines = [
        "SDD-077 — pending operator-apparmor-profile-pivot-restore queue",
        f"{'─' * 7} {'─' * 28} {'─' * 20} {'─' * 8} {'─' * 12}",
        f"{'pid':<7} {'target-profile':<28} {'was':<20} {'scope':<8} {'left':<12}",
        f"{'─' * 7} {'─' * 28} {'─' * 20} {'─' * 8} {'─' * 12}",
    ]
    for entry in queue:
        pid = str(entry.get("pid", "?"))[:7]
        target = render_target_profile(entry)[:28]
        original = render_original_profile(entry)[:20]
        scope = render_scope(entry)[:8]
        left = f"{entry.get('seconds_remaining', 0)}s"[:12]
        lines.append(f"{pid:<7} {target:<28} {original:<20} {scope:<8} {left:<12}")
        lines.append(f"  restore: $ {render_restore_command(entry)}")
        lines.append(f"  reason:  {str(entry.get('original_reason', ''))[:64]}")
        if entry.get("requires_process_restart", False):
            lines.append(
                "  NOTE:    requires_process_restart — restore is queue-clear + "
                "audit only; operator must restart process under original profile"
            )
        lines.append("")
    lines.append(f"{'─' * 7} {'─' * 28} {'─' * 20} {'─' * 8} {'─' * 12}")
    lines.append(
        f"{len(queue)} entries · sorted by urgency · note: AppArmor profile pivots "
        "are one-way at the kernel level — restore is queue-clear + audit only "
        "(operator must restart the process under its original profile via the init system)"
    )
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "restore_command": render_restore_command(entry),
         "target_profile_display": render_target_profile(entry),
         "original_profile_display": render_original_profile(entry),
         "scope_display": render_scope(entry)}
        for entry in queue
    ]
    return json.dumps(
        {
            "queue": enriched,
            "count": len(enriched),
            "irreversibility_note": "AppArmor profile pivots are one-way at the kernel level — restore is queue-clear + audit only; operator must restart the process under its original profile via the init system",
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
