"""M060 F05100 + WCAG 2.1 AA — accessibility apply-snippet contract.

The operator's standing direction catalogues F05100 as non-negotiable:

  F05100 — UX coherence — accessibility (WCAG 2.1 AA minimum:
           contrast / keyboard / screen-reader / focus visible)

This contract guards:

  1. The canonical a11y-snippet source lives at
     webapp/_shared/a11y-snippet.html (single source of truth).
  2. Every adopted dashboard embeds the snippet so:
       - :focus-visible ring on every interactive element
       - skip-to-content link (visually hidden until keyboard-focused)
       - @media (prefers-reduced-motion: reduce) respect operator OS pref
  3. The snippet is CLIENT-SIDE only (pure CSS + 1 anchor injection)
     per the read-only doctrine.

Adoption tracks the nav-snippet rollout in lock-step (a dashboard
with focus-visible but no nav, or nav with no focus-visible, would
be a partial-coverage bug).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
A11Y_SHARED = REPO_ROOT / "webapp" / "_shared" / "a11y-snippet.html"

# Locked in step with ADOPTED_NAV_DASHBOARDS — keep them aligned.
ADOPTED_A11Y_DASHBOARDS = [
    "master-dashboard",
    "d-01-active-sessions",
    "d-02-profile-choices",
    "d-03-model-health",
    "d-04-costs",
    "d-05-traces",
    "d-06-pending-approvals",
    "d-07-memory-changes",
    "d-08-rollback-points",
    "d-09-hardware-pressure",
    "d-10-eval-history",
    "d-11-adapter-status",
    "d-13-filesystem-grants",
    "d-14-capability-tokens",
    "d-15-sandboxes",
    "d-16-audit",
    "d-17-quarantine",
    "d-18-trust-scores",
    "d-19-super-model-manifest",
    "d-20-peace-machine-health",
    "network-edge",
    "edge-firewall",
    "personalization",
    # Orthogonal cockpit webapps (completes 100% rollout):
    "auditor",
    "ux-design-audit",
    "anti-minimization-audit",
    "compliance",
    "global-history",
    "surface-map",
    "router",
    "doc-coverage",
    "weaver",
    "trinity",
    "auth-tier",
    "d-12-networking",
]


def test_shared_a11y_snippet_exists():
    """The canonical a11y-snippet source MUST live at
    webapp/_shared/a11y-snippet.html as the single source of truth."""
    assert A11Y_SHARED.is_file(), f"canonical a11y-snippet missing: {A11Y_SHARED}"


def test_shared_a11y_snippet_covers_focus_visible():
    """The snippet MUST style :focus-visible on every interactive
    element type per WCAG 2.1 AA."""
    src = A11Y_SHARED.read_text(encoding="utf-8")
    # Cover the standard interactive elements
    for selector in ("a:focus-visible", "button:focus-visible",
                     "input:focus-visible", "select:focus-visible",
                     "textarea:focus-visible"):
        assert selector in src, f"a11y-snippet missing focus-visible: {selector}"
    # The rule must produce a visible outline (not display:none / opacity:0)
    assert "outline:" in src or "outline: " in src, (
        "a11y-snippet :focus-visible rule must produce a visible outline"
    )


def test_shared_a11y_snippet_has_skip_link():
    """A skip-to-content link MUST exist for keyboard/screen-reader
    users (visually hidden until focused, then becomes a high-contrast
    badge)."""
    src = A11Y_SHARED.read_text(encoding="utf-8")
    assert "so-skip-link" in src, "a11y-snippet must define .so-skip-link"
    assert "skip to content" in src.lower(), (
        "a11y-snippet must expose 'skip to content' text"
    )


def test_shared_a11y_snippet_respects_reduced_motion():
    """The snippet MUST respect prefers-reduced-motion (WCAG 2.3.3)."""
    src = A11Y_SHARED.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in src, (
        "a11y-snippet must respect prefers-reduced-motion"
    )


def test_shared_a11y_snippet_is_client_side_only():
    """A11y snippet is pure CSS + 1 anchor injection — no server calls."""
    src = A11Y_SHARED.read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "method: 'POST'",
                      "method:'POST'", "method=\"POST\"",
                      "window.location.href ="):
        assert forbidden not in src, (
            f"a11y-snippet must be client-side only; found {forbidden!r}"
        )


def test_all_adopted_dashboards_embed_a11y_snippet():
    """Every adopted dashboard MUST embed the a11y snippet (detected
    by the .so-skip-link marker class)."""
    for slug in ADOPTED_A11Y_DASHBOARDS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        assert path.is_file(), f"adopted dashboard missing: {path}"
        html = path.read_text(encoding="utf-8")
        assert "so-skip-link" in html, (
            f"{slug}: a11y-snippet missing .so-skip-link marker"
        )
        assert ":focus-visible" in html, (
            f"{slug}: a11y-snippet missing :focus-visible rules"
        )


def test_a11y_rollout_locked_with_nav_rollout():
    """The a11y rollout and the nav-snippet rollout MUST be in
    lock-step — a dashboard with one but not the other is a partial-
    coverage bug. Catches drift the moment a new dashboard adopts
    one snippet and forgets the other."""
    from tests.lint.test_keyboard_nav_contract import ADOPTED_NAV_DASHBOARDS as NAV
    nav_set = set(NAV)
    a11y_set = set(ADOPTED_A11Y_DASHBOARDS)
    missing_a11y = nav_set - a11y_set
    missing_nav = a11y_set - nav_set
    assert not missing_a11y, (
        f"Dashboards with nav but no a11y: {sorted(missing_a11y)}"
    )
    assert not missing_nav, (
        f"Dashboards with a11y but no nav: {sorted(missing_nav)}"
    )
