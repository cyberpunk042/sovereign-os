#!/usr/bin/env python3
"""scripts/cockpit/kernel-keyring-evictions-queue.py — SDD-076 MS5b.

Twelfth in the IPS-duodectet cockpit family. Extends the
undectet-paired-handle row to the duodectet at the kernel-keyring axis.

Reads /var/lib/selfdef/kernel-keyring-evictions/pending-restores.json.
Path overridable via SOVEREIGN_OS_KERNEL_KEYRING_EVICTIONS_PENDING_PATH.

UX note: kernel-keyring entries that have been invalidated/unlinked
are gone. The "restore" command is queue-clear + audit only — operator
must re-provision the key material (re-fetch TGT, re-register session
key, etc.) to recover. The footer of every queue rendering surfaces
this caveat.
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
        "SOVEREIGN_OS_KERNEL_KEYRING_EVICTIONS_PENDING_PATH",
        "/var/lib/selfdef/kernel-keyring-evictions/pending-restores.json",
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
        if "key_spec" not in entry or "handle" not in entry:
            continue
        out.append(entry)
    out.sort(key=lambda e: e.get("seconds_remaining", 0))
    return out


def render_restore_command(entry: dict[str, Any]) -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get(
            "Active", handle.get("NotFound", str(entry.get("key_spec", "?")))
        )
    else:
        handle_str = str(handle)
    safe_handle = str(handle_str).replace("'", "'\\''")
    return f"selfdefctl restore-key '{safe_handle}'"


def render_key_spec(entry: dict[str, Any]) -> str:
    spec = entry.get("key_spec", "?")
    if not isinstance(spec, str):
        spec = str(spec)
    if len(spec) <= 24:
        return spec
    return spec[:21] + "..."


def render_key_type(entry: dict[str, Any]) -> str:
    kt = entry.get("key_type", "?")
    if isinstance(kt, str):
        return kt
    return str(kt)


def render_scope(entry: dict[str, Any]) -> str:
    scope = entry.get("scope", "TargetedKey")
    if isinstance(scope, str):
        return scope
    return str(scope)


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return (
            "no pending operator-restore decisions\n"
            "(note: kernel-keyring entries that have been invalidated/unlinked "
            "are gone — restore is queue-clear + audit only)\n"
        )
    lines = [
        "SDD-076 — pending operator-kernel-keyring-eviction-restore queue",
        f"{'─' * 24} {'─' * 6} {'─' * 6} {'─' * 12} {'─' * 18}",
        f"{'key-spec':<24} {'type':<6} {'evict':<6} {'scope':<12} {'left':<18}",
        f"{'─' * 24} {'─' * 6} {'─' * 6} {'─' * 12} {'─' * 18}",
    ]
    for entry in queue:
        spec = render_key_spec(entry)[:24]
        ktype = render_key_type(entry)[:6]
        n_keys = str(entry.get("keys_evicted", 0))[:6]
        scope = render_scope(entry)[:12]
        left = f"{entry.get('seconds_remaining', 0)}s"[:18]
        lines.append(f"{spec:<24} {ktype:<6} {n_keys:<6} {scope:<12} {left:<18}")
        lines.append(f"  restore: $ {render_restore_command(entry)}")
        lines.append(f"  reason:  {str(entry.get('original_reason', ''))[:64]}")
        lines.append("")
    lines.append(f"{'─' * 24} {'─' * 6} {'─' * 6} {'─' * 12} {'─' * 18}")
    lines.append(
        f"{len(queue)} entries · sorted by urgency · note: kernel-keyring entries "
        "that were invalidated/unlinked are gone — restore is queue-clear + audit only "
        "(operator must re-provision key material to recover)"
    )
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "restore_command": render_restore_command(entry),
         "key_spec_display": render_key_spec(entry),
         "key_type_display": render_key_type(entry),
         "scope_display": render_scope(entry)}
        for entry in queue
    ]
    return json.dumps(
        {
            "queue": enriched,
            "count": len(enriched),
            "irreversibility_note": "kernel-keyring entries that have been invalidated/unlinked are gone — restore is queue-clear + audit only",
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
