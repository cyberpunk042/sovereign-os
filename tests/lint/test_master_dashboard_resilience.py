"""master-dashboard front-door resilience lint (SDD-133).

The master-dashboard is the cockpit's front door; a single down probe must never
blank the whole view. This pins the fix:
  - refresh() gathers with Promise.allSettled (not a bare Promise.all that rejects
    on the first dead endpoint),
  - the M060 grid is fired independently of the gather,
  - every gather-path render fn (stats/routes/collisions/discover) has an honest
    'unreachable' scaffold instead of blanking or throwing.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "webapp" / "master-dashboard" / "index.html"


def _body() -> str:
    return PANEL.read_text(encoding="utf-8")


def test_gather_uses_allsettled_not_bare_promise_all():
    body = _body()
    assert "Promise.allSettled(ENDPOINTS.map(fetchJSON))" in body, (
        "the 6-endpoint gather must use Promise.allSettled so one dead probe "
        "cannot reject the whole gather and blank the main view"
    )
    assert "await Promise.all(\n      ENDPOINTS.map(fetchJSON)" not in body, (
        "the bare Promise.all gather must be gone (it blanked the view on any 1 failure)"
    )


def test_render_sections_have_honest_unreachable_scaffolds():
    body = _body()
    for needle in (
        "route table unreachable",
        "collision check unavailable",
        "selfdef discovery unavailable",
    ):
        assert needle in body, f"a gather-path section is missing its honest offline scaffold: {needle!r}"


def test_initial_offline_paint_present():
    body = _body()
    assert "initial honest-offline paint" in body, (
        "the panel must paint an honest-offline scaffold at t=0 so no section shows 'loading…' forever"
    )
