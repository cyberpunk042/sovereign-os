"""Text-wrapping contract (SDD-138) — no aggressive mid-word breaking.

`word-break:break-all` breaks a string at ANY character, always — so a long
hash or log token is chopped mid-word even when it would have fit, and (on a
`<pre>` that also sets `overflow-x:auto`) it forces a wrap that defeats the
horizontal scroller. The graceful idiom is `overflow-wrap:anywhere`: it breaks
an otherwise-unbreakable string ONLY when it would overflow, and it lets the
element's min-content shrink (so it never forces a grid to overflow, pairing
with the SDD-137 minmax(0,1fr) work).

This pins the cleanup: no panel keeps `word-break:break-all` in its CSS.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP = REPO_ROOT / "webapp"

_BREAK_ALL_RE = re.compile(r"word-break\s*:\s*break-all")


def test_no_panel_uses_aggressive_word_break_all():
    offenders: list[str] = []
    for idx in sorted(WEBAPP.glob("*/index.html")):
        for i, line in enumerate(idx.read_text(encoding="utf-8").splitlines(), 1):
            if _BREAK_ALL_RE.search(line):
                offenders.append(f"{idx.parent.name}:{i}")
    assert not offenders, (
        "word-break:break-all breaks strings mid-word unconditionally — use "
        "overflow-wrap:anywhere (breaks only on overflow, lets the box shrink):\n  "
        + "\n  ".join(offenders)
    )


def test_the_cleaned_panels_use_overflow_wrap_anywhere():
    """The 4 panels that carried break-all now wrap long hashes/log lines with
    overflow-wrap:anywhere."""
    for slug in ("d-05-traces", "d-16-audit", "global-history", "network-edge"):
        body = (WEBAPP / slug / "index.html").read_text(encoding="utf-8")
        assert "overflow-wrap:anywhere" in body, (
            f"{slug}: expected overflow-wrap:anywhere after the word-break:break-all cleanup"
        )
