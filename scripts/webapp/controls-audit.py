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

# Classification is by the ACTION's true nature (not just the presence of a copy
# helper — several panels keep a defined-but-dead copyCmd/actionCmd or a neutralized
# emit that copies nothing). The reliable signals:
#   - a panel WIRES actions to the exec-rail iff it calls jumpToControl(<cid>) (the
#     control card then executes via /api/control/execute).
#   - a panel that emits a `selfdefctl …` command to the clipboard is copy-only BY
#     DESIGN: selfdef/perimeter are PROXY_ONLY / SELFDEF_OWNED (control-surface.js
#     PROXY_ONLY + _action_exec.SELFDEF_OWNED) — the web may NEVER execute them
#     locally (R10212), so they render copy-only and this is correct, not a gap.
#   - a panel that copies a non-selfdef `sovereign-os…ctl …` (or `sovereign-os-*`)
#     command to the clipboard WITHOUT a jumpToControl is a real wiring GAP — but
#     only wireable once a matching control exists in config/control-systems.yaml
#     with the panel in its applies_to.
EXEC_RAIL = re.compile(r"jumpToControl\s*\(")
# selfdefctl in a clipboard/emit context → proxy-only (copy-only by design)
PROXY_COPY = re.compile(r"clipboard\.writeText\([^)]*selfdefctl|emit\(\s*['\"`][^'\"`]*selfdefctl")
# a sovereign command copied to the clipboard (the real gap signal), excluding selfdefctl
CLIP = re.compile(r"clipboard\.writeText\(\s*([^)]*)")


def _copies_wireable_cmd(html: str) -> bool:
    # a literal, non-selfdef sovereign command copied to the clipboard — via emit('…')
    # (e.g. d-20's `emit('sudo /usr/bin/sovereign-os-peace-check …')`) or writeText('…')
    for m in re.finditer(r"(?:emit|writeText)\(\s*['\"`]([^'\"`]*sovereign-os[^'\"`]*)['\"`]", html):
        if "selfdefctl" not in m.group(1):
            return True
    # data-cmd tiles copied via copyCmd(node) (e.g. profile-generation's generate-runtime)
    return bool(re.search(r"sovereign-osctl[^'\"`<]*generate-runtime", html))


def classify_panel(slug: str, html: str) -> dict:
    exec_rail = len(EXEC_RAIL.findall(html))
    proxy = bool(PROXY_COPY.search(html))
    wireable = _copies_wireable_cmd(html) and not exec_rail
    if exec_rail:
        status = "wired"
    elif proxy:
        status = "proxy-copy-only"       # copy-only by R10212 design — NOT a wiring gap
    elif wireable:
        status = "wireable-gap"          # real gap (needs a matching registry control)
    else:
        status = "no-actions"
    return {
        "slug": slug,
        "exec_rail": exec_rail,
        "proxy_copy": proxy,
        "wireable_gap": wireable,
        "status": status,
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

    wired = [r for r in rows if r["status"] == "wired"]
    proxy = [r for r in rows if r["status"] == "proxy-copy-only"]
    gaps = sorted([r for r in rows if r["status"] == "wireable-gap"], key=lambda r: r["slug"])
    no_actions = [r for r in rows if r["status"] == "no-actions"]

    print(f"Controls audit — {len(rows)} panels")
    print(f"  wired (actions execute via the exec-rail):  {len(wired)}")
    print(f"  proxy-copy-only (selfdef/perimeter — copy-only BY R10212 design, not a gap): {len(proxy)}")
    print(f"  wireable-gap (real gap — needs a matching registry control):  {len(gaps)}")
    print(f"  no panel-specific actions:                  {len(no_actions)}")
    print()
    print("Wiring worklist (the ONLY genuine gaps — each needs a new control-systems entry first):")
    for r in gaps:
        print(f"  {r['slug']}")
    print()
    print("proxy-copy-only (leave as-is — R10212 forbids local execution of selfdef/perimeter):")
    print("  " + ", ".join(r["slug"] for r in proxy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
