"""ux-design-audit score baseline + regression guard (SDD-139).

The ux-design-audit producer (scripts/operator/ux-design-audit.py) computes a
six-dimension UX score for each of the 9 operator modules (action-budget /
discoverable / recoverable / next-step / operator-named / readable-30s). It is
real + computed, but nothing pinned the SCORES — the existing ux lints assert
the machinery exists, not that a module holds its score. So a module could
silently drop a dimension and every lint stayed green.

This mirrors the controls-audit trio (scripts/webapp/controls-audit.py +
controls-audit-baseline.json + tests/lint/test_controls_audit_baseline.py):
rerun `score --json`, compare against the committed baseline, and fail on any
score REGRESSION. Raising a score is fine (regenerate the baseline in the same
PR); dropping one is the guard.

Regenerate the baseline when a module's score legitimately changes:
    python3 scripts/operator/ux-design-audit.py score --json \
        > scripts/operator/ux-design-audit-baseline.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "operator" / "ux-design-audit.py"
BASELINE = REPO / "scripts" / "operator" / "ux-design-audit-baseline.json"


def _run_score() -> dict:
    out = subprocess.run(
        [sys.executable, str(TOOL), "score", "--json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def _by_module(payload: dict) -> dict[str, dict]:
    return {r["module"]: r for r in payload["scores"]}


def test_score_runs_and_covers_all_nine_modules():
    live = _run_score()
    assert live["count"] == len(live["scores"]), "count must match the scores list length"
    assert len(live["scores"]) == 9, f"expected 9 scored modules, got {len(live['scores'])}"


def test_baseline_current_and_no_module_score_regressed():
    live = _by_module(_run_score())
    baseline = _by_module(json.loads(BASELINE.read_text(encoding="utf-8")))
    assert live.keys() == baseline.keys(), (
        f"module set drift — only live: {live.keys() - baseline.keys()}; "
        f"only baseline: {baseline.keys() - live.keys()}"
    )
    # the durable guard: a module must NEVER drop below its baseline score
    regressions = [
        f"{m}: {baseline[m]['score']}→{live[m]['score']}"
        for m in baseline
        if live[m]["score"] < baseline[m]["score"]
    ]
    assert not regressions, (
        "ux-design-audit module scores regressed (a dimension was lost):\n  "
        + "\n  ".join(regressions)
    )
    # baseline must be current — a raised score means the PR forgot to regenerate it
    stale = [m for m in baseline if live[m] != baseline[m]]
    assert not stale, (
        f"baseline stale for {stale} — regenerate: "
        f"python3 scripts/operator/ux-design-audit.py score --json "
        f"> scripts/operator/ux-design-audit-baseline.json"
    )
