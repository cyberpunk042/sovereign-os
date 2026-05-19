"""R547 (E5++) — dashboards README R546 anchor lint.

R546 added `milestone` + `selfdef` stat cards to the
`sovereign-os-surface-map.json` Grafana dashboard. The corresponding
row in `docs/observability/dashboards/README.md` and the metric-
inventory description for `sovereign_os_operator_surface_map_query_total`
MUST surface those additions so operators reading the README see
the same verb-coverage symmetry the dashboard ships.

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
   you covered all angles and levels and layers and even if then
   improve it. Do not minimize or settle for less."

A dashboard change that doesn't echo into the doc surface is a
doc-gap anti-min pattern — exactly the kind of regression this test
fails loud on.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = (
    REPO_ROOT
    / "docs"
    / "observability"
    / "dashboards"
    / "README.md"
)


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_surface_map_row_anchors_r546():
    """The surface-map row MUST anchor R546 — operators scanning the
    table see at-a-glance that the verb-stat coverage was expanded."""
    txt = _readme()
    # Locate the surface-map dashboard row.
    rows = [
        line for line in txt.splitlines()
        if line.startswith("|") and "sovereign-os-surface-map.json" in line
    ]
    assert rows, "README must contain a row for sovereign-os-surface-map.json"
    assert len(rows) == 1, (
        f"README must have exactly one surface-map dashboard row; "
        f"got {len(rows)}"
    )
    row = rows[0]
    assert "R546" in row, (
        f"R547: surface-map dashboard README row must anchor R546; "
        f"got {row!r}"
    )


def test_readme_surface_map_row_mentions_milestone_and_selfdef_verbs():
    """The verb-counter list in the surface-map row MUST surface
    `milestone` and `selfdef` — the two verbs R546 promoted onto the
    dashboard."""
    txt = _readme()
    rows = [
        line for line in txt.splitlines()
        if line.startswith("|") and "sovereign-os-surface-map.json" in line
    ]
    row = rows[0].lower()
    assert "milestone" in row, (
        f"R547: surface-map dashboard row must mention `milestone` "
        f"verb (R546 added the stat card); got {rows[0]!r}"
    )
    assert "selfdef" in row, (
        f"R547: surface-map dashboard row must mention `selfdef` "
        f"verb (R546 added the stat card); got {rows[0]!r}"
    )


def test_metric_inventory_lists_milestone_and_selfdef_verbs():
    """The metric inventory entry for
    `sovereign_os_operator_surface_map_query_total` MUST list the
    `milestone` and `selfdef` verbs — those are emitted by the
    R540/R532+ verb invocations and must be discoverable from the
    metric inventory."""
    txt = _readme()
    # Locate the surface-map metric inventory line.
    lines = [
        line for line in txt.splitlines()
        if "sovereign_os_operator_surface_map_query_total" in line
    ]
    assert lines, (
        "README metric inventory must list "
        "sovereign_os_operator_surface_map_query_total"
    )
    # The README has TWO references: one in the dashboard row + one in
    # the metric inventory. We need the inventory description line —
    # it's the longer one that describes the verb vocabulary.
    long_lines = [
        line for line in lines
        if "verb=" in line.lower() and "result=" in line.lower()
    ]
    assert long_lines, (
        "README must have a metric-inventory line describing the verb "
        "vocabulary for sovereign_os_operator_surface_map_query_total"
    )
    inv = long_lines[0].lower()
    assert "milestone" in inv, (
        f"R547: metric inventory must list `milestone` verb; "
        f"got {long_lines[0]!r}"
    )
    assert "selfdef" in inv, (
        f"R547: metric inventory must list `selfdef` verb; "
        f"got {long_lines[0]!r}"
    )


def test_metric_inventory_cites_r540_and_r546():
    """The metric-inventory description for surface-map MUST cite R540
    (the milestone-verb origin) and R546 (the dashboard verb-row
    symmetry closure) so operators can trace where each verb came
    from."""
    txt = _readme()
    long_lines = [
        line for line in txt.splitlines()
        if "sovereign_os_operator_surface_map_query_total" in line
        and "verb=" in line.lower() and "result=" in line.lower()
    ]
    inv = long_lines[0]
    assert "R540" in inv, (
        f"R547: metric inventory must cite R540 (milestone verb "
        f"origin); got {inv!r}"
    )
    assert "R546" in inv, (
        f"R547: metric inventory must cite R546 (dashboard verb-row "
        f"symmetry closure); got {inv!r}"
    )
