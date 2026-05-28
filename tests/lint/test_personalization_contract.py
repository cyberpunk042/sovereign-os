"""M060 R10137/R10140/R10141 — personalization webapp + apply-snippet contract.

The operator's standing direction (2026-05-19) catalogues 3 non-negotiable
personalization R-rows:

  R10137 — Dashboard styling — dark mode + light mode + auto-from-system
  R10140 — Dashboard styling — operator-configurable accent color
  R10141 — Dashboard styling — operator-configurable typography scale

This contract guards:

  1. The personalization control surface at /webapp/personalization/
     ships the 3 controls (theme + accent + typography).
  2. The apply-snippet is embedded in the master-dashboard <head> so
     prefs apply pre-paint (no FOUC) on the cockpit's entry point.
  3. Per-dashboard rollout: each D-NN dashboard that adopts the
     snippet reads from the SAME localStorage key (sovereign-os.
     personalization, schema v1) so prefs are coherent across all
     surfaces.

Per "Respect the projects": personalization is a CLIENT-SIDE preference
layer (localStorage on the operator's browser). The server NEVER mutates
prefs and the apply-snippet NEVER ships prefs anywhere — read-only doctrine
applies to this surface like every other cockpit webapp.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONALIZATION = REPO_ROOT / "webapp" / "personalization" / "index.html"
MASTER_DASHBOARD = REPO_ROOT / "webapp" / "master-dashboard" / "index.html"

# The single source of truth for the localStorage key + schema version.
EXPECTED_KEY = "sovereign-os.personalization"
EXPECTED_SCHEMA = "1"


def test_personalization_page_exists():
    assert PERSONALIZATION.is_file(), (
        f"personalization control surface missing: {PERSONALIZATION}"
    )


def test_personalization_page_ships_three_controls():
    """R10137 + R10140 + R10141 — all 3 controls present."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    # R10137 theme: 3 buttons (auto/dark/light)
    for theme in ("data-theme=\"auto\"", "data-theme=\"dark\"", "data-theme=\"light\""):
        assert theme in html, f"R10137 missing theme button: {theme}"
    # R10140 accent: swatches + custom hex input
    assert "accent-control" in html and "swatches" in html, (
        "R10140 missing accent swatch control"
    )
    assert "accent-custom" in html and "#RRGGBB" in html.upper() or "rrggbb" in html.lower(), (
        "R10140 missing custom-hex accent input"
    )
    # R10141 typography: at least 3 scale buttons (compact/default/large)
    for scale in ("data-scale=\"0.85\"", "data-scale=\"1\"", "data-scale=\"1.15\""):
        assert scale in html, f"R10141 missing typography button: {scale}"


def test_personalization_page_uses_canonical_localstorage_key():
    """All apply-snippets must read/write the SAME localStorage key
    so prefs are coherent across the cockpit. Schema-version v1."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    assert EXPECTED_KEY in html, (
        f"personalization page must use canonical localStorage key "
        f"{EXPECTED_KEY!r}"
    )
    assert "SCHEMA_V = 1" in html or "SCHEMA_V=1" in html, (
        "personalization page must declare schema v1"
    )


def test_personalization_page_is_client_side_only():
    """Server NEVER mutates prefs. The page must NOT POST/PUT/DELETE
    to any /api/ endpoint."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    for forbidden in ("method: 'POST'", "method:'POST'", "method=\"POST\"",
                      "method: 'PUT'", "method:'PUT'", "method=\"PUT\"",
                      "method: 'DELETE'", "method:'DELETE'", "method=\"DELETE\""):
        assert forbidden not in html, (
            f"personalization is CLIENT-SIDE only; found server-mutation: {forbidden!r}"
        )


def test_master_dashboard_embeds_apply_snippet():
    """The master-dashboard (cockpit entry point) MUST embed the
    apply-snippet in <head> so prefs apply pre-paint."""
    html = MASTER_DASHBOARD.read_text(encoding="utf-8")
    head_split = html.split("</head>", 1)
    assert len(head_split) == 2, "master-dashboard <head> not found"
    head = head_split[0]
    assert EXPECTED_KEY in head, (
        "master-dashboard <head> must contain the personalization apply-snippet"
    )
    # apply-snippet writes to documentElement attributes/style
    assert "setAttribute('data-theme'" in head or "setAttribute(\"data-theme\"" in head, (
        "apply-snippet must set data-theme on documentElement"
    )
    assert "setProperty('--accent'" in head or "setProperty(\"--accent\"" in head, (
        "apply-snippet must set --accent custom property"
    )
    assert "--font-scale" in head, (
        "apply-snippet must set --font-scale custom property"
    )


def test_master_dashboard_honors_font_scale():
    """Master-dashboard's html/body font-size MUST honor the --font-scale
    custom property (calc(... * var(--font-scale))) so R10141 actually
    takes effect."""
    html = MASTER_DASHBOARD.read_text(encoding="utf-8")
    # Look for calc(<base> * var(--font-scale)) on html or body font-size
    assert "calc(14px * var(--font-scale" in html or \
           "calc(14px*var(--font-scale" in html, (
        "master-dashboard must honor --font-scale in its base font-size "
        "(via calc(14px * var(--font-scale, 1)))"
    )


def test_master_dashboard_honors_light_theme():
    """Master-dashboard MUST declare a html[data-theme=\"light\"] override
    so R10137 light mode actually renders."""
    html = MASTER_DASHBOARD.read_text(encoding="utf-8")
    assert "html[data-theme=\"light\"]" in html or \
           "html[data-theme='light']" in html, (
        "master-dashboard must declare html[data-theme=\"light\"] override "
        "for R10137 light mode"
    )


def test_master_dashboard_links_to_personalization():
    """A discoverable link to /webapp/personalization/ MUST be present
    in master-dashboard so the operator can reach the controls without
    typing the URL by hand."""
    html = MASTER_DASHBOARD.read_text(encoding="utf-8")
    assert "../personalization/" in html or \
           "/webapp/personalization/" in html, (
        "master-dashboard must link to /webapp/personalization/"
    )


def test_personalization_page_metadata_cites_catalog():
    """Operator-§1g visibility: the personalization page MUST cite its
    catalog source (M060 R10137/R10140/R10141) in its meta."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    assert "R10137" in html and "R10140" in html and "R10141" in html, (
        "personalization page must cite all 3 catalog R-rows"
    )
    assert "M060" in html, "personalization page must cite M060 milestone"
