"""Phase 3 controls-audit baseline lint (SDD-130).

Runs scripts/webapp/controls-audit.py and compares against the committed baseline
(scripts/webapp/controls-audit-baseline.json). This pins the operability progress:
- a panel that is exec-rail 'wired' must NOT regress to copy-only,
- the audit stays runnable + covers every panel.

Each Phase-3 wiring PR updates the baseline (a panel moves copy-only → wired), so
the baseline is the live progress tracker; a regression (wired → copy-only, or a
new un-audited copy-only action) fails here.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "webapp" / "controls-audit.py"
BASELINE = REPO / "scripts" / "webapp" / "controls-audit-baseline.json"


def _run_audit() -> list[dict]:
    out = subprocess.run(
        [sys.executable, str(TOOL), "--json"], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


def test_audit_runs_and_covers_every_panel():
    live = _run_audit()
    n_panels = len(list((REPO / "webapp").glob("*/index.html")))
    assert len(live) == n_panels, f"audit covered {len(live)} of {n_panels} panels"


def test_baseline_is_current_and_no_wired_panel_regressed():
    live = {r["slug"]: r for r in _run_audit()}
    baseline = {r["slug"]: r for r in json.loads(BASELINE.read_text(encoding="utf-8"))}
    # baseline must match the live audit exactly — each Phase-3 wiring PR regenerates
    # it (`make controls-audit JSON=1 > scripts/webapp/controls-audit-baseline.json`),
    # so drift here means the baseline wasn't refreshed OR an action regressed.
    assert live.keys() == baseline.keys(), (
        f"panel set drift — only live: {live.keys() - baseline.keys()}; "
        f"only baseline: {baseline.keys() - live.keys()}"
    )
    regressions = [
        slug for slug, b in baseline.items()
        if b["status"] == "wired" and live[slug]["status"] != "wired"
    ]
    assert not regressions, f"exec-rail-wired panels regressed to copy-only: {regressions}"
    stale = [slug for slug in baseline if live[slug] != baseline[slug]]
    assert not stale, (
        f"baseline stale for {stale} — regenerate: "
        f"python3 scripts/webapp/controls-audit.py --json > scripts/webapp/controls-audit-baseline.json"
    )
