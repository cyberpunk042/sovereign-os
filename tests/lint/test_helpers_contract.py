"""SDD-073 — canonical helpers contract (esc / fmtBytes / fmtNum).

Mirrors test_app_shell_contract.py: a single source-of-truth block lives at
webapp/_shared/helpers.js and is duplicated verbatim into each adopted panel's
<head>. This lint enforces:

  * the canonical source exists and carries the BEGIN/END markers;
  * every ADOPTED panel embeds the BYTE-IDENTICAL block;
  * the helpers are defined before any panel-specific script runs.

Adoption is opt-in: only panels in ADOPTED_HELPERS_PANELS are checked, so
the rollout proceeds one panel at a time. Keep this list in lockstep with
ADOPTED_PANELS in scripts/webapp/sync-helpers.py.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED = REPO_ROOT / "webapp" / "_shared" / "helpers.js"

BEGIN = "/* HELPERS:BEGIN M073"
END = "/* HELPERS:END M073 */"
_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)

# Opt-in adoption list — grow one/few at a time (lockstep with the generator).
ADOPTED_HELPERS_PANELS = [
    "d-03-model-health",
    "d-04-costs",
    "d-09-hardware-pressure",
    "d-11-adapter-status",
]

PANEL_HELPER = {
    "d-03-model-health": "fmtBytes",
    "d-04-costs": "fmtNum",
    "d-09-hardware-pressure": "fmtBytes",
    "d-11-adapter-status": "fmtBytes",
}


def _canonical_block() -> str:
    src = SHARED.read_text(encoding="utf-8")
    m = _BLOCK_RE.search(src)
    assert m, f"canonical helpers block markers missing in {SHARED}"
    return m.group(0)


def test_adoption_lists_are_nonempty_and_in_lockstep():
    """A vacuous rollout must never pass CI: generator and contract own the same,
    non-empty panel set."""
    import runpy

    sync = runpy.run_path(str(REPO_ROOT / "scripts" / "webapp" / "sync-helpers.py"))
    assert ADOPTED_HELPERS_PANELS, "helpers rollout must adopt at least one panel"
    assert sync["ADOPTED_PANELS"] == ADOPTED_HELPERS_PANELS


def test_adopted_panel_helper_has_one_definition():
    """The helper adopted by each pilot panel is defined exactly once: in the
    canonical block, never again in panel-specific code."""
    for slug, helper in PANEL_HELPER.items():
        html = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        assert html.count(f"function {helper}(") == 1, (
            f"{slug}: {helper} must be defined only by the canonical helpers block"
        )


def test_shared_helpers_snippet_exists():
    """The canonical source-of-truth block MUST live at
    webapp/_shared/helpers.js so adopters copy it verbatim and
    this contract has a single source of truth."""
    assert SHARED.is_file(), f"canonical helpers snippet missing: {SHARED}"
    src = SHARED.read_text(encoding="utf-8")
    assert BEGIN in src and END in src, "helpers snippet missing BEGIN/END markers"


def test_shared_helpers_snippet_defines_esc():
    """The canonical block MUST define esc() with the standard
    HTML-escape mapping (ampersand, less-than, greater-than, quote)."""
    src = SHARED.read_text(encoding="utf-8")
    assert "function esc(" in src, "helpers.js must define esc()"
    assert "&amp;" in src and "&lt;" in src and "&gt;" in src and "&quot;" in src, (
        "esc() must escape & < > \""
    )


def test_shared_helpers_snippet_defines_fmtbytes():
    """The canonical block MUST define fmtBytes() with B/K/M/G/T units."""
    src = SHARED.read_text(encoding="utf-8")
    assert "function fmtBytes(" in src, "helpers.js must define fmtBytes()"
    for unit in ("'B'", "'K'", "'M'", "'G'", "'T'"):
        assert unit in src, f"fmtBytes() must cover unit {unit}"


def test_shared_helpers_snippet_defines_fmtnum():
    """The canonical block MUST define fmtNum()."""
    src = SHARED.read_text(encoding="utf-8")
    assert "function fmtNum(" in src, "helpers.js must define fmtNum()"


def test_shared_helpers_is_client_side_only():
    """The helpers block must make no network calls."""
    src = SHARED.read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "EventSource"):
        assert forbidden not in src, (
            f"helpers.js must be client-side only; found {forbidden!r}"
        )


def test_adopted_panels_embed_identical_block():
    """Every ADOPTED panel MUST embed the byte-identical canonical block."""
    block = _canonical_block()
    for slug in ADOPTED_HELPERS_PANELS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        assert path.is_file(), f"adopted panel missing: {path}"
        html = path.read_text(encoding="utf-8")
        m = _BLOCK_RE.search(html)
        assert m, f"{slug}: helpers block missing (run sync-helpers.py --apply)"
        assert m.group(0) == block, (
            f"{slug}: helpers block differs from canonical "
            f"(run: python3 scripts/webapp/sync-helpers.py --apply)"
        )


def test_adopted_panels_place_block_in_head():
    """The block MUST sit inside <head> so helpers are defined before
    any panel-specific <script> runs."""
    head_re = re.compile(r"(?mi)^[ \t]*<head[^>]*>")
    endhead_re = re.compile(r"(?mi)^[ \t]*</head\s*>")
    for slug in ADOPTED_HELPERS_PANELS:
        html = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        hm = head_re.search(html)
        em = endhead_re.search(html)
        assert hm and em, f"{slug}: no <head> or </head> tag"
        blk = _BLOCK_RE.search(html)
        assert blk, f"{slug}: helpers block missing"
        assert hm.start() < blk.start() < em.start(), (
            f"{slug}: helpers block must be inside <head>"
        )
