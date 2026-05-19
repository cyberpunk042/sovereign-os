"""R542 (E5++) — surface-map webapp milestone panel contract lint.

R540 landed `surface-map milestone --json`. R541 added /milestone over
HTTP + MCP. R542 surfaces the R540 rollup in the surface-map webapp
itself — operator-§1g UX rule: the §1g coverage instrument's OWN
webapp must show the ceiling-closure state at a glance, not require
a CLI/MCP/API round-trip.

Per operator §1g 8-surface delivery contract anchor verbatim (R453):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Static-only checks (webapp is single-file zero-deps; no JS execution
required to assert the milestone panel is wired).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_HTML = REPO_ROOT / "webapp" / "surface-map" / "index.html"


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"missing webapp asset: {WEBAPP_HTML}"


def test_webapp_meta_records_r542():
    """The x-sovereign-shipped-in meta MUST advertise R542 so anyone
    inspecting the asset (or its rendered DOM) can trace the panel
    back to its commit."""
    html = WEBAPP_HTML.read_text()
    m = re.search(
        r'name="x-sovereign-shipped-in"\s+content="([^"]+)"', html
    )
    assert m is not None, "missing x-sovereign-shipped-in meta"
    content = m.group(1)
    assert "R533" in content, "must keep R533 lineage"
    assert "R542" in content, (
        f"x-sovereign-shipped-in must advertise R542; got {content!r}"
    )


def test_milestone_panel_section_present():
    """The webapp body MUST contain the milestone rollup section
    heading citing R540 (the rollup it surfaces)."""
    html = WEBAPP_HTML.read_text()
    low = html.lower()
    assert "milestone rollup" in low, (
        "webapp must surface the R540 milestone rollup section"
    )
    assert "r540" in low, "milestone panel must cite R540"


def test_milestone_panel_stat_ids_present():
    """The four R540 milestone stats MUST have DOM hooks for the
    refresh logic. The IDs lock the operator-named shape into the
    asset itself (so a future refactor can't silently lose a stat)."""
    html = WEBAPP_HTML.read_text()
    for stat_id in ("ms-total", "ms-ceiling", "ms-full8", "ms-future"):
        assert f'id="{stat_id}"' in html, (
            f"milestone panel missing stat hook id={stat_id!r}"
        )
    for prose_id in ("ms-historic", "ms-fullset"):
        assert f'id="{prose_id}"' in html, (
            f"milestone panel missing prose hook id={prose_id!r}"
        )


def test_milestone_panel_refresh_function_wired():
    """`refreshMilestone()` MUST be defined and called from
    `refreshAll()` — operator-§1g UX rule: the panel auto-refreshes
    alongside the rest of the webapp."""
    html = WEBAPP_HTML.read_text()
    assert "async function refreshMilestone()" in html, (
        "refreshMilestone() must be defined"
    )
    assert "refreshMilestone()" in html.split(
        "async function refreshAll()"
    )[1], (
        "refreshMilestone() must be invoked from refreshAll()"
    )


def test_milestone_panel_fetches_milestone_endpoint():
    """The panel logic MUST hit the R541 /milestone endpoint exactly
    — not a parallel implementation, not a CLI shellout, not the
    aggregated /modules response."""
    html = WEBAPP_HTML.read_text()
    assert 'fetchJSON("/milestone")' in html, (
        "refreshMilestone() must fetch /milestone (the R541 endpoint)"
    )


def test_milestone_panel_uses_canonical_payload_keys():
    """The panel logic MUST read the canonical R540 keys — total_
    modules / at_structural_ceiling_count / full_8_surface_count /
    zero_future_waivers / future_carrying_count / historic_anchor /
    at_full_8_surfaces. Locks the shape against silent renames."""
    html = WEBAPP_HTML.read_text()
    for key in (
        "total_modules",
        "at_structural_ceiling_count",
        "full_8_surface_count",
        "zero_future_waivers",
        "future_carrying_count",
        "historic_anchor",
        "at_full_8_surfaces",
        "all_at_structural_ceiling",
    ):
        assert key in html, (
            f"milestone panel logic must read R540 key {key!r}"
        )


def test_milestone_panel_uses_same_origin_fetch():
    """Sovereignty-clean: the milestone fetch path MUST be same-
    origin relative — no http://, https://, or // prefixes."""
    html = WEBAPP_HTML.read_text()
    for m in re.finditer(r'fetchJSON\(\s*["\']([^"\']+)["\']', html):
        url = m.group(1)
        assert not url.startswith(("http://", "https://", "//")), (
            f"fetchJSON({url!r}) must be same-origin"
        )


def test_webapp_footer_advertises_r540_r541_r542():
    """Footer prose MUST trace the milestone arc R540 → R541 → R542
    so the operator (and audit replay) can see the lineage."""
    html = WEBAPP_HTML.read_text()
    footer_start = html.lower().find("<footer")
    footer_end = html.lower().find("</footer>", footer_start)
    assert footer_start >= 0 and footer_end > footer_start, (
        "webapp must have a footer block"
    )
    footer = html[footer_start:footer_end]
    assert "R540" in footer, "footer must cite R540"
    assert "R541" in footer, "footer must cite R541"
    assert "R542" in footer, "footer must cite R542"


def test_webapp_zero_external_deps_post_r542():
    """R542 added DOM + JS in-place — must still be zero-deps."""
    html = WEBAPP_HTML.read_text()
    bad_patterns = [
        r'src\s*=\s*["\']https?://',
        r'href\s*=\s*["\']https?://',
        r'src\s*=\s*["\']//',
        r'href\s*=\s*["\']//',
        r'@import\s+url\(\s*["\']?https?://',
        r'<script[^>]*\bsrc\s*=\s*["\'][^"\']*\.js["\']',
    ]
    for pat in bad_patterns:
        m = re.search(pat, html, re.IGNORECASE)
        assert not m, (
            f"webapp violates zero-deps rule: matched {pat!r}"
        )


def test_milestone_panel_after_stats_before_surfaces():
    """Operator-§1g UX layout invariant: milestone rollup is HIGH-
    SIGNAL information (system-wide ceiling state) — it MUST appear
    above the 8-surface ladder + below the top stats strip."""
    html = WEBAPP_HTML.read_text()
    i_stats = html.find('id="stats"')
    i_milestone = html.lower().find("milestone rollup")
    i_surfaces = html.find("8 operator-named")
    assert i_stats >= 0 and i_milestone >= 0 and i_surfaces >= 0
    assert i_stats < i_milestone < i_surfaces, (
        "R542 layout: milestone panel must sit between top stats and "
        "the 8-surface ladder"
    )
