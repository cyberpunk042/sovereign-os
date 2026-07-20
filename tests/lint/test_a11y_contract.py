"""SDD-073 — canonical a11y snippet contract (focus-visible / skip-link / reduced-motion).

Mirrors test_app_shell_contract.py: a single source-of-truth block lives at
webapp/_shared/a11y-snippet.html and is duplicated verbatim into each adopted
panel's <head>. This lint enforces:

  * the canonical source exists and carries the BEGIN/END markers;
  * every ADOPTED panel embeds the BYTE-IDENTICAL block;
  * the a11y block is defined before any panel-specific script runs.

Adoption is opt-in: only panels in ADOPTED_A11Y_PANELS are checked, so
the rollout proceeds one panel at a time. Keep this list in lockstep with
ADOPTED_PANELS in scripts/webapp/sync-a11y.py.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED = REPO_ROOT / "webapp" / "_shared" / "a11y-snippet.html"

BEGIN = "<!-- A11Y:BEGIN M060 -->"
END = "<!-- A11Y:END M060 -->"
_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)

# Opt-in adoption list — grow one/few at a time (lockstep with the generator).
ADOPTED_A11Y_PANELS: list[str] = [
    "brain",
]


def _canonical_block() -> str:
    src = SHARED.read_text(encoding="utf-8")
    m = _BLOCK_RE.search(src)
    assert m, f"canonical a11y block markers missing in {SHARED}"
    block = m.group(0)
    if block.endswith("\n"):
        block = block[:-1]
    return block


def test_adoption_lists_are_nonempty_and_in_lockstep():
    """A vacuous rollout must never pass CI: generator and contract own the same,
    non-empty panel set."""
    import runpy

    sync = runpy.run_path(str(REPO_ROOT / "scripts" / "webapp" / "sync-a11y.py"))
    assert ADOPTED_A11Y_PANELS, "a11y rollout must adopt at least one panel"
    assert sync["ADOPTED_PANELS"] == ADOPTED_A11Y_PANELS


def test_shared_a11y_snippet_exists():
    """The canonical source-of-truth block MUST live at
    webapp/_shared/a11y-snippet.html so adopters copy it verbatim and
    this contract has a single source of truth."""
    assert SHARED.is_file(), f"canonical a11y snippet missing: {SHARED}"
    src = SHARED.read_text(encoding="utf-8")
    assert BEGIN in src and END in src, "a11y snippet missing BEGIN/END markers"


def test_shared_a11y_snippet_has_skip_link():
    """The canonical block MUST ship the WCAG 2.4.1 skip-to-content link."""
    src = SHARED.read_text(encoding="utf-8")
    assert ".so-skip-link" in src, "a11y snippet missing skip-link CSS"
    assert "skip to content" in src, "a11y snippet missing skip-link text"


def test_shared_a11y_snippet_has_focus_visible():
    """The canonical block MUST ship the WCAG 2.1 AA focus-visible ring."""
    src = SHARED.read_text(encoding="utf-8")
    assert ":focus-visible" in src, "a11y snippet missing :focus-visible rule"


def test_shared_a11y_snippet_has_reduced_motion():
    """The canonical block MUST respect prefers-reduced-motion."""
    src = SHARED.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in src, "a11y snippet missing reduced-motion guard"


def test_adopted_panels_have_byte_identical_block():
    """Every adopted panel embeds the EXACT canonical block (byte-for-byte)."""
    canonical = _canonical_block()
    for slug in ADOPTED_A11Y_PANELS:
        html = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        m = _BLOCK_RE.search(html)
        assert m, f"{slug}: a11y block markers missing"
        panel_block = m.group(0)
        if panel_block.endswith("\n"):
            panel_block = panel_block[:-1]
        assert panel_block == canonical, (
            f"{slug}: a11y block drifts from canonical\n"
            f"  canonical len={len(canonical)}  panel len={len(panel_block)}"
        )
