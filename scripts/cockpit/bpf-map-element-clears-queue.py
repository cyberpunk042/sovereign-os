#!/usr/bin/env python3
"""scripts/cockpit/bpf-map-element-clears-queue.py — SDD-078 MS5b.

Fourteenth in the IPS-quattuordectet cockpit family. Extends the
tridectet-paired-handle row to the quattuordectet at the eBPF
map state axis.

Reads /var/lib/selfdef/bpf-map-element-clears/pending-restores.json.
Path overridable via SOVEREIGN_OS_BPF_MAP_ELEMENT_CLEARS_PENDING_PATH.

UX note: BPF map element clears are one-way at the kernel level —
selfdef did not snapshot prior values. The "restore" command is
queue-clear + audit only; the owning BPF program's control plane
must re-populate the map through its normal data path (operator
must restart that plane or wait for natural re-population).
Every queue rendering surfaces this caveat in the footer plus a
per-row requires_owning_program_repopulation flag.
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
        "SOVEREIGN_OS_BPF_MAP_ELEMENT_CLEARS_PENDING_PATH",
        "/var/lib/selfdef/bpf-map-element-clears/pending-restores.json",
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
        if "map_spec" not in entry or "handle" not in entry:
            continue
        out.append(entry)
    out.sort(key=lambda e: e.get("seconds_remaining", 0))
    return out


def render_restore_command(entry: dict[str, Any]) -> str:
    handle = entry.get("handle", {})
    if isinstance(handle, dict):
        handle_str = handle.get(
            "Active",
            handle.get(
                "MapNotFound",
                handle.get(
                    "AmbiguousName",
                    handle.get(
                        "KeySizeMismatch",
                        handle.get(
                            "KeyNotFound",
                            handle.get(
                                "BpfMapAccessDenied",
                                str(entry.get("map_spec", "?")),
                            ),
                        ),
                    ),
                ),
            ),
        )
    else:
        handle_str = str(handle)
    safe_handle = str(handle_str).replace("'", "'\\''")
    return f"selfdefctl restore-bpf-map '{safe_handle}'"


def render_map_spec(entry: dict[str, Any]) -> str:
    ms = entry.get("map_spec", "?")
    if not isinstance(ms, str):
        ms = str(ms)
    if len(ms) <= 32:
        return ms
    return ms[:29] + "..."


def render_scope(entry: dict[str, Any]) -> str:
    scope = entry.get("scope", "Element")
    if isinstance(scope, str):
        return scope
    return str(scope)


def render_key_hex(entry: dict[str, Any]) -> str:
    key = entry.get("key_hex")
    if key is None or not isinstance(key, str):
        return "—"
    if len(key) <= 16:
        return key
    return key[:13] + "..."


def render_human(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return (
            "no pending operator-restore decisions\n"
            "(note: BPF map element clears are one-way at the kernel level — "
            "selfdef did not snapshot prior values; restore is queue-clear + audit only)\n"
        )
    lines = [
        "SDD-078 — pending operator-bpf-map-element-clear-restore queue",
        f"{'─' * 32} {'─' * 8} {'─' * 16} {'─' * 8} {'─' * 8}",
        f"{'map-spec':<32} {'scope':<8} {'key':<16} {'cleared':<8} {'left':<8}",
        f"{'─' * 32} {'─' * 8} {'─' * 16} {'─' * 8} {'─' * 8}",
    ]
    for entry in queue:
        spec = render_map_spec(entry)[:32]
        scope = render_scope(entry)[:8]
        key_hex = render_key_hex(entry)[:16]
        n_cleared = str(entry.get("elements_cleared", 0))[:8]
        left = f"{entry.get('seconds_remaining', 0)}s"[:8]
        lines.append(f"{spec:<32} {scope:<8} {key_hex:<16} {n_cleared:<8} {left:<8}")
        lines.append(f"  restore: $ {render_restore_command(entry)}")
        lines.append(f"  reason:  {str(entry.get('original_reason', ''))[:64]}")
        if entry.get("requires_owning_program_repopulation", False):
            lines.append(
                "  NOTE:    requires_owning_program_repopulation — restore is queue-clear + "
                "audit only; the owning BPF program's control plane must re-add elements"
            )
        lines.append("")
    lines.append(f"{'─' * 32} {'─' * 8} {'─' * 16} {'─' * 8} {'─' * 8}")
    lines.append(
        f"{len(queue)} entries · sorted by urgency · note: BPF map element clears are "
        "one-way at the kernel level — selfdef did not snapshot prior values; "
        "the owning BPF program's control plane must re-populate the map"
    )
    return "\n".join(lines) + "\n"


def render_json(queue: list[dict[str, Any]]) -> str:
    enriched = [
        {**entry, "restore_command": render_restore_command(entry),
         "map_spec_display": render_map_spec(entry),
         "scope_display": render_scope(entry),
         "key_display": render_key_hex(entry)}
        for entry in queue
    ]
    return json.dumps(
        {
            "queue": enriched,
            "count": len(enriched),
            "irreversibility_note": "BPF map element clears are one-way at the kernel level — selfdef did not snapshot prior values; the owning BPF program's control plane must re-add elements",
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
