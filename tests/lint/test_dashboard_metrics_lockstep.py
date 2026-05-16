"""Layer 1 lint — every sovereign_os_ metric referenced in a dashboard
JSON MUST also be emitted by some script in the repo (via emit_metric,
emit_metric_set, or written directly as a metric line).

Catches dashboard drift: a dashboard panel showing a metric that no
script emits is a silent operator-confusion bug ("why is this panel
empty?"). Closing the lockstep at lint time means the dashboard is
self-consistent with the code that powers it.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DASH_DIR = REPO_ROOT / "docs" / "observability" / "dashboards"

# Where metrics can be emitted from. We scan these for any
# 'sovereign_os_<...>' literal that looks like a metric name.
EMITTING_SOURCES = [
    REPO_ROOT / "scripts",
    REPO_ROOT / "systemd" / "system",
    # Future: any new emitter directory lands here
]

# Pattern: sovereign_os_ followed by underscore-separated identifiers
METRIC_NAME_RE = re.compile(r"\bsovereign_os_[a-z][a-z0-9_]*\b")


def _emitted_metric_names() -> set[str]:
    """Collect every sovereign_os_<name> token that appears in the
    emitting source tree. Includes label names + sub-strings, so this
    is a superset of actual metric names — but we just need the metric
    name itself to appear SOMEWHERE in source for the lockstep gate."""
    seen: set[str] = set()
    for root in EMITTING_SOURCES:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            # Skip binary / non-text files
            try:
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            for m in METRIC_NAME_RE.findall(text):
                seen.add(m)
    return seen


def _dashboard_metric_refs(dash: pathlib.Path) -> set[str]:
    """Extract every sovereign_os_<name> from PromQL expressions in a
    dashboard JSON (specifically from panels[*].targets[*].expr)."""
    data = json.loads(dash.read_text())
    refs: set[str] = set()
    for panel in data.get("panels") or []:
        for tgt in panel.get("targets") or []:
            expr = tgt.get("expr") or ""
            for m in METRIC_NAME_RE.findall(expr):
                refs.add(m)
    return refs


def _dashboards() -> list[pathlib.Path]:
    return sorted(DASH_DIR.glob("*.json"))


def test_emitting_sources_present():
    for root in EMITTING_SOURCES:
        assert root.is_dir(), f"emitting source dir missing: {root}"


def test_dashboards_present():
    assert len(_dashboards()) >= 2


@pytest.mark.parametrize("dash", _dashboards(), ids=lambda p: p.name)
def test_dashboard_metrics_have_emitter(dash: pathlib.Path):
    """Every metric the dashboard references must appear in some
    emitting source file. Failure means the panel will show empty
    in production — the dashboard and the emit code have drifted."""
    refs = _dashboard_metric_refs(dash)
    if not refs:
        pytest.skip(f"{dash.name} has no metric references to check")

    emitted = _emitted_metric_names()
    orphans = sorted(r for r in refs if r not in emitted)
    assert not orphans, (
        f"{dash.name} references {len(orphans)} metric(s) with no emitter "
        f"in the source tree: {orphans}. Either fix the dashboard "
        f"expression or add an emit_metric call in the relevant script."
    )
