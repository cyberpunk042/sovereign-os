"""Cross-panel deep-link resolution lint (SDD-135).

Every sibling deep link a panel renders — `href="../<slug>/"` — must point at a
real `webapp/<slug>/` directory. This guards the SDD-135 D-xx linkify work AND
catches the class of bug it fixed: 10 panels linked `../d-00-master/`, a slug
that does not exist (the master dashboard's real slug is `master-dashboard`), so
the front-door link silently 404'd.

The app-shell's own dynamic navigation (`'../'+it.dir+'/'`) is keyed off the
GROUPS catalog whose dirs are real webapp panels, so only literal `../<slug>/`
hrefs in panel HTML are checked here.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"

# literal single-segment sibling links: href="../<slug>/" optionally followed by
# ?query, #frag, or index.html — the forms panels actually author.
_HREF_RE = re.compile(r'href="\.\./([a-z0-9][a-z0-9-]*)/(?:index\.html)?(?:[?#][^"]*)?"')


def _panel_dirs() -> set[str]:
    return {p.name for p in WEBAPP.iterdir() if p.is_dir() and (p / "index.html").exists()}


def test_every_sibling_deep_link_resolves_to_a_real_panel():
    panels = _panel_dirs()
    broken: list[str] = []
    for idx in sorted(WEBAPP.glob("*/index.html")):
        body = idx.read_text(encoding="utf-8")
        for slug in set(_HREF_RE.findall(body)):
            if slug not in panels:
                broken.append(f"{idx.parent.name} → ../{slug}/ (no such panel)")
    assert not broken, "cross-panel deep links pointing at non-existent slugs:\n  " + "\n  ".join(sorted(broken))


def test_no_panel_links_the_stale_d00_master_slug():
    """Regression guard for the exact SDD-135 fix — the master dashboard is
    `master-dashboard`, never `d-00-master`."""
    offenders = [
        idx.parent.name
        for idx in WEBAPP.glob("*/index.html")
        if "d-00-master/" in idx.read_text(encoding="utf-8")
    ]
    assert not offenders, f"panels still link the non-existent d-00-master slug: {sorted(offenders)}"


def test_app_shell_linkify_helper_present_and_non_mutating():
    """The SDD-135 linkify pass must be in the synced app-shell, keyed off the
    GROUPS catalog, and must not introduce any network call (R10212)."""
    snippet = (WEBAPP / "_shared" / "app-shell-snippet.html").read_text(encoding="utf-8")
    assert "function linkifyDxx(" in snippet, "the linkifyDxx pass must live in the shared app-shell"
    assert "ID2DIR" in snippet, "linkify must resolve D-xx via an ID2DIR map built from GROUPS"
    # the helper creates anchors only — it must not fetch/POST/mutate
    block = snippet[snippet.index("function linkifyDxx(") : snippet.index("var lastMatched=null;")]
    for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "method=\"post\""):
        assert forbidden not in block, f"linkifyDxx must stay non-mutating (found {forbidden!r})"
