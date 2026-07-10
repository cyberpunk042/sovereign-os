#!/usr/bin/env python3
"""controls-audit.py — Phase 3 (operability) read-only audit.

Enumerates, per cockpit panel, the panel-specific ACTION affordances and
classifies each as:
  - exec-rail : wired to the sanctioned R10274 exec-rail (jumpToControl(<cid>) →
                the control card executes via /api/control/execute, dry-run +
                operator-key + type-to-confirm). Actions run from the cockpit.
  - copy-only : still emits a shell command to the clipboard (copyCmd / emit /
                navigator.clipboard.writeText) — the operator must paste + run it.
  - neutral   : navigation / scroll / view-only (no action, nothing to wire).

Output: a per-panel table + a ranked worklist (panels with the most copy-only
actions first) — the sequence for the Phase-3 wiring PRs. Read-only; no changes.

This deliberately looks only at PANEL-SPECIFIC buttons — the shared
SovereignControlSurface control cards (which already execute via the exec-rail,
with a copy fallback by design) are excluded so the audit measures the gap, not
the baseline.

Usage: python3 scripts/webapp/controls-audit.py [--json] [--worklist]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"

# Panel-specific affordance signatures (the shared SovereignControlSurface control
# cards are excluded: they already execute via the exec-rail with a copy fallback by
# design — its internal clipboard helper is `copy(text, opts)` /
# `navigator.clipboard.writeText`, which we deliberately DON'T count).
# A panel that WIRES an action to the exec-rail calls jumpToControl(<cid>); a panel
# that leaves an action copy-only defines/calls copyCmd()/emit()/copyApply() that
# writes a `sovereign-osctl …` command to the clipboard for the operator to paste.
EXEC_RAIL = re.compile(r"jumpToControl\s*\(")
COPY_CMD = re.compile(r"\b(?:copyCmd|copyApply)\s*\(")
# an `emit(<cmd>)` call that actually copies (some panels neutralize emit to a no-op —
# those don't count). We treat a defined-and-called emit that writes to the clipboard
# as copy-only; the neutralized ones are `function emit(){}`-shaped and excluded.
EMIT_ACTIVE = re.compile(r"function emit\([^)]*\)\s*\{[^}]*clipboard")


def classify_panel(slug: str, html: str) -> dict:
    exec_rail = len(EXEC_RAIL.findall(html))
    copy_only = len(COPY_CMD.findall(html)) + (1 if EMIT_ACTIVE.search(html) else 0)
    return {
        "slug": slug,
        "exec_rail": exec_rail,
        "copy_only": copy_only,
        "status": (
            "wired" if exec_rail and not copy_only
            else "partial" if exec_rail and copy_only
            else "copy-only" if copy_only
            else "no-actions"
        ),
    }


def audit() -> list[dict]:
    rows = []
    for idx in sorted(WEBAPP.glob("*/index.html")):
        rows.append(classify_panel(idx.parent.name, idx.read_text(encoding="utf-8")))
    return rows


def main() -> int:
    rows = audit()
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
        return 0

    worklist = sorted(
        [r for r in rows if r["copy_only"] > 0],
        key=lambda r: (-r["copy_only"], r["slug"]),
    )
    wired = [r for r in rows if r["status"] == "wired"]
    no_actions = [r for r in rows if r["status"] == "no-actions"]

    print(f"Controls audit — {len(rows)} panels")
    print(f"  exec-rail wired (no copy-only): {len(wired)}")
    print(f"  copy-only command emits present: {len(worklist)}")
    print(f"  no panel-specific actions:       {len(no_actions)}")
    print()
    print("Ranked wiring worklist (most copy-only emits first):")
    print(f"  {'panel':32} {'exec-rail':>9} {'copy-only':>9}  status")
    for r in worklist:
        print(f"  {r['slug']:32} {r['exec_rail']:>9} {r['copy_only']:>9}  {r['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
