"""R546 (E5++) — surface-map Grafana dashboard milestone + selfdef panel
contract lint.

Operator-§1g coverage symmetry: every parameterless `surface-map` verb
exposed via MCP MUST have a corresponding stat card on the
sovereign-os-surface-map Grafana dashboard. R540 promoted `milestone`
to MCP (surface-map-milestone); R544 promoted `selfdef` to MCP
(surface-map-selfdef); R545 promoted `gaps` to MCP (surface-map-gaps);
all three verbs need a corresponding dashboard verb-stat card.

The original R493 dashboard shipped 6 verb-stat cards (surfaces /
modules / coverage / gaps / waivers); R546 extends the verb-stat row
with 2 more cards (milestone + selfdef) — closing the §1g 8-surface
dashboard-coverage symmetry against the MCP family
(surface-map-surfaces / -modules / -coverage / -milestone / -selfdef
/ -gaps).

Per operator §1g 8-surface delivery contract anchor verbatim (R453):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
   you covered all angles and levels and layers and even if then
   improve it. Do not minimize or settle for less."
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = (
    REPO_ROOT
    / "docs"
    / "observability"
    / "dashboards"
    / "sovereign-os-surface-map.json"
)

MILESTONE_EXPR = (
    'sum(sovereign_os_operator_surface_map_query_total'
    '{verb="milestone"})'
)
SELFDEF_EXPR = (
    'sum(sovereign_os_operator_surface_map_query_total'
    '{verb="selfdef"})'
)


def _load():
    return json.loads(DASHBOARD.read_text())


def _panels_by_title():
    return {p["title"]: p for p in _load()["panels"]}


def test_dashboard_parseable():
    """The R546 edit MUST not break the JSON shape."""
    data = _load()
    assert isinstance(data, dict)
    assert isinstance(data.get("panels"), list)
    assert data["panels"], "dashboard must have at least one panel"


def test_r546_milestone_stat_panel_present():
    """R540 promoted `milestone` to MCP; R546 adds a stat card so the
    dashboard verb-row covers it."""
    panels = _panels_by_title()
    assert "milestone verb (count)" in panels, (
        f"R546: dashboard must include 'milestone verb (count)' stat "
        f"panel; got titles {sorted(panels.keys())}"
    )
    p = panels["milestone verb (count)"]
    assert p["type"] == "stat", (
        f"R546: milestone panel must be type=stat; got {p['type']}"
    )
    exprs = [t.get("expr", "") for t in p.get("targets", [])]
    assert MILESTONE_EXPR in exprs, (
        f"R546: milestone panel must query "
        f"{MILESTONE_EXPR!r}; got {exprs!r}"
    )


def test_r546_selfdef_stat_panel_present():
    """R544 promoted `selfdef` to MCP; R546 adds a stat card so the
    dashboard verb-row covers it."""
    panels = _panels_by_title()
    assert "selfdef verb (count)" in panels, (
        f"R546: dashboard must include 'selfdef verb (count)' stat "
        f"panel; got titles {sorted(panels.keys())}"
    )
    p = panels["selfdef verb (count)"]
    assert p["type"] == "stat", (
        f"R546: selfdef panel must be type=stat; got {p['type']}"
    )
    exprs = [t.get("expr", "") for t in p.get("targets", [])]
    assert SELFDEF_EXPR in exprs, (
        f"R546: selfdef panel must query "
        f"{SELFDEF_EXPR!r}; got {exprs!r}"
    )


def test_r546_new_panels_have_descriptions():
    """Operator-§1g UX rule: every stat card carries a one-paragraph
    description so the operator's first read of the panel is
    self-contained."""
    panels = _panels_by_title()
    for title in ("milestone verb (count)", "selfdef verb (count)"):
        desc = panels[title].get("description", "")
        assert len(desc) >= 60, (
            f"R546: {title!r} description too thin "
            f"({len(desc)} chars); operator-§1g rule: substantive"
        )


def test_r546_milestone_description_cites_r540():
    panels = _panels_by_title()
    desc = panels["milestone verb (count)"].get("description", "")
    low = desc.lower()
    assert "r540" in low, (
        f"R546: milestone panel description must cite R540 (the "
        f"ceiling-closure rollup it surfaces); got {desc!r}"
    )


def test_r546_selfdef_description_cites_r462():
    panels = _panels_by_title()
    desc = panels["selfdef verb (count)"].get("description", "")
    low = desc.lower()
    assert "r462" in low, (
        f"R546: selfdef panel description must cite R462 (the "
        f"cross-repo SurfaceManifest contract); got {desc!r}"
    )


def test_r546_dashboard_tag_present():
    data = _load()
    tags = data.get("tags", [])
    assert "R546" in tags, (
        f"R546: dashboard tags must include 'R546' anchor; got {tags!r}"
    )


def test_r546_no_panel_gridpos_overlap():
    """R546 added 2 panels at y=20; the text panel (which previously
    sat at y=20) MUST shift so panel rectangles don't overlap on the
    Grafana grid (operator-§1g UX rule: dashboard must be legible)."""
    panels = _load()["panels"]
    # Build rectangle list, then pairwise-check for overlap.
    rects = []
    for p in panels:
        gp = p["gridPos"]
        x0, y0 = gp["x"], gp["y"]
        x1, y1 = x0 + gp["w"], y0 + gp["h"]
        rects.append((p["title"], x0, y0, x1, y1))
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            # Strict overlap: rectangles share a non-zero area.
            ax0, ay0, ax1, ay1 = a[1], a[2], a[3], a[4]
            bx0, by0, bx1, by1 = b[1], b[2], b[3], b[4]
            ovx = max(0, min(ax1, bx1) - max(ax0, bx0))
            ovy = max(0, min(ay1, by1) - max(ay0, by0))
            assert ovx * ovy == 0, (
                f"R546: panels overlap on grid — "
                f"{a[0]!r} ({ax0},{ay0})-({ax1},{ay1}) vs "
                f"{b[0]!r} ({bx0},{by0})-({bx1},{by1})"
            )


def test_r546_text_panel_shifted_below_new_stats():
    """The new stat cards sit at y=20 h=4 (so bottom edge y=24); the
    text panel MUST start at y>=24 to clear them."""
    panels = _panels_by_title()
    text_title = "surface-map §1g verbatim + 8-surface ladder"
    assert text_title in panels, (
        f"R546: text-panel title missing — refactor likely renamed it; "
        f"got titles {sorted(panels.keys())}"
    )
    gp = panels[text_title]["gridPos"]
    assert gp["y"] >= 24, (
        f"R546: text panel must shift to y>=24 (was y=20); got y={gp['y']}"
    )


def test_r546_new_stats_at_expected_row():
    """The R546 stat cards live on the y=20 row (the row immediately
    below the result-distribution / current-state row at y=12 h=8 →
    bottom y=20)."""
    panels = _panels_by_title()
    for title in ("milestone verb (count)", "selfdef verb (count)"):
        gp = panels[title]["gridPos"]
        assert gp["y"] == 20, (
            f"R546: {title!r} must sit at y=20; got y={gp['y']}"
        )
        assert gp["h"] == 4, (
            f"R546: {title!r} must be h=4 (stat-card standard); "
            f"got h={gp['h']}"
        )


def test_r546_verb_stat_family_complete():
    """Operator-§1g coverage symmetry: the dashboard MUST surface a
    stat card for EVERY parameterless surface-map verb exposed on the
    MCP family (surfaces / modules / coverage / gaps / waivers /
    milestone / selfdef). `waivers` is included even though it's
    CLI-only on MCP — R493 shipped it as a dashboard card so operators
    can monitor waiver-query volume without filesystem scans."""
    panels = _panels_by_title()
    expected_titles = {
        "surfaces verb (count)",
        "modules verb (count)",
        "coverage verb (count)",
        "gaps verb (count)",
        "waivers verb (count)",
        "milestone verb (count)",
        "selfdef verb (count)",
    }
    missing = expected_titles - set(panels.keys())
    assert not missing, (
        f"R546: dashboard missing verb-stat panels: {missing}"
    )


def test_r546_comment_anchors_round():
    data = _load()
    comment = data.get("_comment", "")
    assert "R546" in comment, (
        f"R546: dashboard _comment must anchor R546; got {comment!r}"
    )
