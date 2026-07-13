"""Standing-mandate navigation-map completeness (F-2026-039 / SDD-975).

`docs/standing-directives/2026-05-17-operator-mandate.md` is a ~640 KB single file
(its mandate-table rows are multi-KB each), which makes it slow to open and hard to
diff. SDD-975 adds a section-level navigation companion
(`…-operator-mandate-NAVIGATION.md`) so a reader can jump to the right section
without loading the whole file — it reproduces no content (the mandate stays the
single sacrosanct source), only a map of its structure.

This lint keeps the map complete: every `##` / `###` section heading in the mandate
must appear in the NAVIGATION companion. So a heading added, renamed, or removed in
the mandate can't silently diverge from its navigation map. It deliberately checks
HEADINGS only (not the `E11.M###` table rows) — adding a mandate row does not change
a heading, so routine per-SDD mandate-row appends need no update here, keeping this
off the hot path of the most-appended file in the repo.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SD_DIR = REPO_ROOT / "docs" / "standing-directives"
MANDATE = SD_DIR / "2026-05-17-operator-mandate.md"
NAV = SD_DIR / "2026-05-17-operator-mandate-NAVIGATION.md"

# ## or ### headings (skip the H1 title); strip a trailing {#explicit-anchor}.
_HEADING_RE = re.compile(r"(?m)^#{2,3}\s+(.*?)\s*$")
_ANCHOR_SUFFIX_RE = re.compile(r"\s*\{#[^}]+\}\s*$")


def _mandate_headings() -> list[str]:
    out: list[str] = []
    for raw in _HEADING_RE.findall(MANDATE.read_text(encoding="utf-8")):
        text = _ANCHOR_SUFFIX_RE.sub("", raw).strip()
        if text:
            out.append(text)
    return out


def test_navigation_companion_exists():
    assert NAV.is_file(), f"missing navigation companion {NAV} (SDD-975)"
    assert MANDATE.is_file(), f"missing mandate file {MANDATE}"


def test_every_mandate_heading_is_navigable():
    nav = NAV.read_text(encoding="utf-8")
    missing = [h for h in _mandate_headings() if h not in nav]
    assert not missing, (
        "these mandate section headings are not reflected in the NAVIGATION companion "
        "(add/rename/remove them there too, so the map stays complete): " + repr(missing)
    )


def test_navigation_links_the_mandate():
    """The companion must point back at the mandate file (it's a map OF it, not a fork)."""
    nav = NAV.read_text(encoding="utf-8")
    assert "2026-05-17-operator-mandate.md" in nav, (
        "NAVIGATION companion does not link the mandate file it indexes"
    )
