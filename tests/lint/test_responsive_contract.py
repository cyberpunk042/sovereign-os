"""M060 F05099 + R10142 — responsive-layout apply-snippet contract.

The operator's standing direction catalogues F05099 as non-negotiable:

  F05099 — UX coherence — responsive design works on phone / tablet
           / desktop / 4K (operator runs the cockpit on multiple
           form factors)

This contract guards:

  1. The canonical responsive-snippet source lives at
     webapp/_shared/responsive-snippet.html (single source of truth).
  2. Every adopted dashboard embeds the snippet so the cockpit
     adapts coherently across the 4 form factors (phone ≤600px,
     tablet 601-1024px, desktop ≥1025px, 4K ≥2400px).
  3. The snippet is CSS-only (no JS) per the read-only doctrine.

Adoption tracks the a11y rollout in lock-step (which itself tracks
the nav rollout) — a dashboard with a11y but no responsive (or vice
versa) is a partial-coverage bug.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESPONSIVE_SHARED = REPO_ROOT / "webapp" / "_shared" / "responsive-snippet.html"


def test_shared_responsive_snippet_exists():
    assert RESPONSIVE_SHARED.is_file(), (
        f"canonical responsive-snippet missing: {RESPONSIVE_SHARED}"
    )


def test_shared_responsive_snippet_covers_phone_breakpoint():
    """Phone (≤600px) MUST trigger a media query so the cockpit is
    usable on a phone screen."""
    src = RESPONSIVE_SHARED.read_text(encoding="utf-8")
    assert "@media (max-width: 600px)" in src, (
        "responsive-snippet must declare phone breakpoint (≤600px)"
    )


def test_shared_responsive_snippet_covers_tablet_breakpoint():
    """Tablet (601-1024px) MUST trigger a media query."""
    src = RESPONSIVE_SHARED.read_text(encoding="utf-8")
    assert "(min-width: 601px) and (max-width: 1024px)" in src, (
        "responsive-snippet must declare tablet breakpoint (601-1024px)"
    )


def test_shared_responsive_snippet_covers_4k_breakpoint():
    """4K / ultra-wide (≥2400px) MUST raise body width so content
    isn't marooned in a thin center column on a huge display."""
    src = RESPONSIVE_SHARED.read_text(encoding="utf-8")
    assert "@media (min-width: 2400px)" in src, (
        "responsive-snippet must declare 4K breakpoint (≥2400px)"
    )


def test_shared_responsive_snippet_is_css_only():
    """The snippet is CSS-only — no JS, no fetch/XHR/server-mutation."""
    src = RESPONSIVE_SHARED.read_text(encoding="utf-8")
    for forbidden in ("<script", "fetch(", "XMLHttpRequest"):
        assert forbidden not in src, (
            f"responsive-snippet must be CSS-only; found {forbidden!r}"
        )


def test_all_adopted_dashboards_embed_responsive_snippet():
    """Every dashboard listed in the a11y rollout MUST also embed
    the responsive snippet (locked rollout step)."""
    # Reuse the a11y adoption list so the two rollouts stay locked.
    from tests.lint.test_a11y_contract import ADOPTED_A11Y_PANELS
    for slug in ADOPTED_A11Y_PANELS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        html = path.read_text(encoding="utf-8")
        # Unique responsive-snippet marker — the 4K breakpoint
        assert "@media (min-width: 2400px)" in html, (
            f"{slug}: responsive-snippet missing (no 4K breakpoint marker)"
        )
        assert "@media (max-width: 600px)" in html, (
            f"{slug}: responsive-snippet missing (no phone breakpoint marker)"
        )


def test_responsive_palette_fits_narrow_viewport():
    """On phone, the M060 keyboard palette MUST shrink so it doesn't
    overflow the viewport. This is the canonical example of why
    responsive + nav must roll in lock-step."""
    src = RESPONSIVE_SHARED.read_text(encoding="utf-8")
    assert ".so-palette-box" in src and "width: 96vw" in src, (
        "responsive-snippet must shrink .so-palette-box on phone "
        "(so the keyboard palette overlay fits narrow viewports)"
    )
