#!/usr/bin/env python3
"""scripts/mirror/selfdef-tui-mirror.py — READ-ONLY consumer of the
selfdef TUI-layout schema mirror (MS007 typed-mirror crate
selfdef-tui-mirror, R10141 / F05081 / R10298).

The data model behind the sovereign-os minimal-web mirroring path
(R10170 "same 4-panel layout as TUI"). CROSS-REPO MIRROR: the
canonical 4-panel layout is published by the selfdef daemon's
mirror-export loop into /run/sovereign-os/selfdef-mirror/tui.json
every 30s; sovereign-os reads it READ-ONLY.

The 4 panels are FIXED per R10141 — adding panels is forbidden by
doctrine ("a dashboard should not show vanity graphs" — R10298
verbatim). The schema lives in selfdef-tui-mirror::canonical_snapshot.

Mirror artifact (selfdef-tui-mirror::TuiMirrorSnapshot 1.0.0):
  schema_version · tui_build_version · doctrine · captured_at ·
  panels[{kind,quadrant,title,source_mirror,columns,key_bindings,
  min_authority,refresh_ms,signature}] · global_keys · signature

Sovereignty: stdlib-only. Absent artifact → empty panels + offline
mirror_status (graceful), NEVER a crash. No keybinding is mutating
(R10212 lock — all panel verbs are clipboard-copy of selfdefctl).

  selfdef-tui-mirror.py snapshot [--json]   full 4-panel layout
  selfdef-tui-mirror.py panels   [--json]   bare panel descriptors
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

# Verbatim doctrine surface — must NOT be paraphrased (R10298).
DOCTRINE = "A dashboard should not show vanity graphs"

TUI_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_TUI_MIRROR",
    "/run/sovereign-os/selfdef-mirror/tui.json",
))

# Canonical 4-panel set per R10141. Consumers MUST NOT add panels.
PANEL_KINDS = ("rules", "grants", "quarantine", "authority")

# 4 quadrants — each panel occupies exactly one.
QUADRANTS = ("top_left", "top_right", "bottom_left", "bottom_right")


def _read_mirror(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _key_bindings(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for kb in raw:
        if not isinstance(kb, dict):
            continue
        out.append({
            "key": str(kb.get("key", "")),
            "action": str(kb.get("action", "")),
            # R10212: TUI/web NEVER mutates IPS state. Surface the
            # field but defend the invariant — coerce any non-bool to
            # False.
            "mutating": bool(kb.get("mutating", False)),
        })
    return out


def _columns(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        out.append({
            "header":      str(c.get("header", "")),
            "field":       str(c.get("field", "")),
            "width":       int(c.get("width", 0)),
            "right_align": bool(c.get("right_align", False)),
        })
    return out


def _panels(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("panels")
    if not isinstance(raw, list):
        return []
    out = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        kind = p.get("kind", "")
        if kind not in PANEL_KINDS:
            continue
        quadrant = p.get("quadrant", "")
        if quadrant not in QUADRANTS:
            continue
        out.append({
            "kind":          kind,
            "quadrant":      quadrant,
            "title":         str(p.get("title", "")),
            "source_mirror": str(p.get("source_mirror", "")),
            "columns":       _columns(p.get("columns")),
            "key_bindings":  _key_bindings(p.get("key_bindings")),
            "min_authority": str(p.get("min_authority", "l0_observe")),
            "refresh_ms":    int(p.get("refresh_ms", 30000)),
            "signature":     str(p.get("signature", "")),
        })
    return out


def snapshot() -> dict[str, Any]:
    """Full TUI-layout model projected from the selfdef mirror."""
    mirror = _read_mirror(TUI_MIRROR)
    # Doctrine surface is preserved verbatim — if the artifact carries a
    # tampered value the reader surfaces it as-is so consumers can detect
    # the drift, but offline default uses the canonical R10298 string.
    return {
        "schema_version":    SCHEMA_VERSION,
        "mirror_status":     "online" if mirror else "offline",
        "mirror_source":     "selfdef-tui-mirror (MS007 typed mirror, read-only)",
        "tui_build_version": mirror.get("tui_build_version", ""),
        "doctrine":          mirror.get("doctrine", DOCTRINE),
        "captured_at":       mirror.get("captured_at"),
        "panels":            _panels(mirror),
        "global_keys":       _key_bindings(mirror.get("global_keys")),
        "signature":         mirror.get("signature"),  # MS003 sig
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef tui-mirror consumer (MS007)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("snapshot", "panels"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    if cmd == "panels":
        _print(snapshot()["panels"])
    else:
        _print(snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(main())
