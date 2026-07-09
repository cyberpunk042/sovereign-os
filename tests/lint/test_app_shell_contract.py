"""SDD-067 — app-shell contract (the 5th canonical per-panel snippet).

Mirrors test_keyboard_nav_contract.py: a single source-of-truth block lives at
webapp/_shared/app-shell-snippet.html and is duplicated verbatim into each
ADOPTED panel's <body>. This lint enforces:

  * the canonical source exists and carries the BEGIN/END markers;
  * the catalog inside it covers the full D-00..D-25 panel set;
  * every ADOPTED panel embeds the BYTE-IDENTICAL block;
  * the chrome stays non-mutating (no fetch/XHR/form POST in the block) —
    per the design grammar, chrome navigates + explains, never executes.

Adoption is opt-in: only panels in ADOPTED_APP_SHELL_PANELS are checked, so
the ~50 not-yet-adopted panels stay green while the rollout proceeds one panel
at a time. Keep this list in lockstep with ADOPTED_PANELS in
scripts/webapp/sync-app-shell.py.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED = REPO_ROOT / "webapp" / "_shared" / "app-shell-snippet.html"

BEGIN = "<!-- APP-SHELL:BEGIN M067 -->"
END = "<!-- APP-SHELL:END M067 -->"
_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)

# Opt-in adoption list — grow one/few at a time (lockstep with the generator).
ADOPTED_APP_SHELL_PANELS = [
    "master-dashboard",
    "d-04-costs",
]


def _canonical_block() -> str:
    src = SHARED.read_text(encoding="utf-8")
    m = _BLOCK_RE.search(src)
    assert m, f"canonical app-shell block markers missing in {SHARED}"
    return m.group(0)


def test_shared_app_shell_snippet_exists():
    """The canonical source-of-truth block MUST live at
    webapp/_shared/app-shell-snippet.html so adopters copy it verbatim and
    this contract has a single source of truth."""
    assert SHARED.is_file(), f"canonical app-shell snippet missing: {SHARED}"
    src = SHARED.read_text(encoding="utf-8")
    assert BEGIN in src and END in src, "app-shell snippet missing BEGIN/END markers"


def test_app_shell_catalog_covers_full_panel_set():
    """The sidemenu catalog MUST include every D-00..D-25 id so no panel is
    unreachable from the shell."""
    src = SHARED.read_text(encoding="utf-8")
    for n in range(0, 26):
        if n == 12:
            continue  # D-12 ships as the split panels D-12a / D-12b (below)
        did = f"D-{n:02d}"
        assert f"'{did}'" in src, f"app-shell catalog missing {did}"
    # the two D-12 split panels
    for did in ("D-12a", "D-12b"):
        assert f"'{did}'" in src, f"app-shell catalog missing {did}"


def test_app_shell_reuses_personalization_key():
    """The theme toggle MUST read/write the SAME personalization localStorage
    object the panels already use — one source of truth, no divergence."""
    src = SHARED.read_text(encoding="utf-8")
    assert "sovereign-os.personalization" in src, (
        "app-shell theme toggle must use the sovereign-os.personalization key"
    )


def test_app_shell_chrome_is_non_mutating():
    """Per the design grammar the chrome navigates + explains; it MUST NOT
    execute anything server-side. The block carries no fetch/XHR/form POST."""
    block = _canonical_block()
    for forbidden in ("fetch(", "XMLHttpRequest", "navigator.sendBeacon", "method=\"post\"", "method='post'"):
        assert forbidden.lower() not in block.lower(), (
            f"app-shell block must be non-mutating; found: {forbidden}"
        )


def test_app_shell_respects_reduced_motion():
    """Hover/transition feel MUST be gated behind prefers-reduced-motion."""
    src = SHARED.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in src, (
        "app-shell must gate motion behind prefers-reduced-motion"
    )


def test_adopted_panels_embed_identical_block():
    """Every ADOPTED panel MUST embed the byte-identical canonical block."""
    block = _canonical_block()
    for slug in ADOPTED_APP_SHELL_PANELS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        assert path.is_file(), f"adopted panel missing: {path}"
        html = path.read_text(encoding="utf-8")
        m = _BLOCK_RE.search(html)
        assert m, f"{slug}: app-shell block missing (run sync-app-shell.py --apply)"
        assert m.group(0) == block, (
            f"{slug}: app-shell block differs from canonical "
            f"(run: python3 scripts/webapp/sync-app-shell.py --apply)"
        )


def test_adopted_panels_keep_their_head_snippets():
    """Adopting the shell MUST NOT displace the existing canonical <head>
    stack — the palette + personalization must still be present."""
    for slug in ADOPTED_APP_SHELL_PANELS:
        html = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        assert "so-palette-backdrop" in html, f"{slug}: keyboard-nav palette snippet lost"
        assert "sovereign-os.personalization" in html, f"{slug}: personalization snippet lost"
