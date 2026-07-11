"""M090 — guided-course contract (the 6th canonical per-panel snippet).

Sibling of test_app_shell_contract.py. A single source-of-truth block lives at
webapp/_shared/course-snippet.html and is duplicated verbatim (just before
</body>) into each adopted panel by scripts/webapp/sync-course.py. This lint
enforces:

  * the canonical source exists and carries the BEGIN/END markers;
  * every adopted panel embeds the BYTE-IDENTICAL block, after the app-shell
    block (so window.__soCatalog is set before the course reads it);
  * the course is client-only (no fetch/XHR/sendBeacon/form-POST) — even the
    app-shell's one sanctioned loopback chat is NOT present here; the course
    only navigates + explains;
  * motion is gated behind prefers-reduced-motion;
  * the course REUSES the app-shell catalog (window.__soCatalog) instead of
    duplicating the per-panel narratives — config/dashboard-catalog.yaml stays
    the single source of truth;
  * the course is disambiguated from the Assistant: its own #so-course-* IDs and
    its own sovereign-os.course key, and it never touches #so-assist or the
    sovereign-os.assist key.

Adoption is the app-shell adopted set (the course needs window.__soCatalog,
which the app-shell provides), imported from the app-shell contract so the two
rollouts stay in lockstep automatically.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.lint.test_app_shell_contract import ADOPTED_APP_SHELL_PANELS as ADOPTED_COURSE_PANELS

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED = REPO_ROOT / "webapp" / "_shared" / "course-snippet.html"

BEGIN = "<!-- COURSE:BEGIN M090 -->"
END = "<!-- COURSE:END M090 -->"
_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
_APP_SHELL_BLOCK_RE = re.compile(
    re.escape("<!-- APP-SHELL:BEGIN M067 -->") + r".*?" + re.escape("<!-- APP-SHELL:END M067 -->"),
    re.DOTALL,
)


def _canonical_block() -> str:
    src = SHARED.read_text(encoding="utf-8")
    m = _BLOCK_RE.search(src)
    assert m, f"canonical course block markers missing in {SHARED}"
    return m.group(0)


def test_shared_course_snippet_exists():
    """The canonical source-of-truth block MUST live at
    webapp/_shared/course-snippet.html so adopters copy it verbatim and this
    contract has a single source of truth."""
    assert SHARED.is_file(), f"canonical course snippet missing: {SHARED}"
    src = SHARED.read_text(encoding="utf-8")
    assert BEGIN in src and END in src, "course snippet missing BEGIN/END markers"


def test_course_is_client_only_non_mutating():
    """The course navigates + explains; it MUST NOT execute anything
    server-side. Unlike the app-shell it has NO sanctioned fetch — no
    fetch/XHR/sendBeacon/form-POST at all. Navigation is location.href only."""
    block = _canonical_block()
    low = block.lower()
    for forbidden in ("fetch(", "xmlhttprequest", "navigator.sendbeacon",
                      'method="post"', "method='post'", "method: 'post'"):
        assert forbidden not in low, (
            f"course block must be client-only + non-mutating; found: {forbidden}"
        )
    assert "location.href" in block, (
        "course auto-travel must use location.href (client-side navigation)"
    )


def test_course_respects_reduced_motion():
    """Transition feel MUST be gated behind prefers-reduced-motion."""
    src = SHARED.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in src, (
        "course must gate motion behind prefers-reduced-motion"
    )


def test_course_reuses_catalog_not_duplicates_it():
    """The course MUST reuse the app-shell catalog narratives via
    window.__soCatalog rather than duplicating them — dashboard-catalog.yaml
    stays the single source of truth."""
    block = _canonical_block()
    assert "__soCatalog" in block, (
        "course must read window.__soCatalog (reuse, not duplicate, the panel "
        "narratives)"
    )


def test_course_is_disambiguated_from_assistant():
    """The course is NOT the Assistant: it MUST use its own #so-course-* IDs and
    its own sovereign-os.course key, and MUST NOT reuse #so-assist or the
    sovereign-os.assist key."""
    block = _canonical_block()
    assert "sovereign-os.course" in block, "course must use its own sovereign-os.course key"
    assert "so-course-rail" in block, "course must use its own #so-course-* IDs"
    # It must never USE the assist key as a string literal (a prose comment that
    # names it to explain the separation is fine).
    assert "'sovereign-os.assist'" not in block and '"sovereign-os.assist"' not in block, (
        "course must NOT read/write the Assistant's sovereign-os.assist key"
    )
    # The course may READ the assistant's open state via CSS (body.so-assist-open,
    # to tuck the rail), but it must never CREATE/replace the Assistant aside.
    assert 'id="so-assist"' not in block and "id='so-assist'" not in block, (
        "course must never create/replace the Assistant aside (#so-assist)"
    )


def test_course_uses_its_own_schema_guarded_state():
    """Persistence MUST be schema-guarded (schema:1) like the other
    localStorage users, with its own key."""
    block = _canonical_block()
    assert "CSCHEMA" in block and "schema" in block, (
        "course state must be schema-guarded"
    )


def test_adopted_panels_embed_identical_block():
    """Every adopted panel MUST embed the byte-identical canonical block."""
    block = _canonical_block()
    for slug in ADOPTED_COURSE_PANELS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        assert path.is_file(), f"adopted panel missing: {path}"
        html = path.read_text(encoding="utf-8")
        m = _BLOCK_RE.search(html)
        assert m, f"{slug}: course block missing (run sync-course.py --apply)"
        assert m.group(0) == block, (
            f"{slug}: course block differs from canonical "
            f"(run: python3 scripts/webapp/sync-course.py --apply)"
        )


def test_course_block_parses_after_app_shell_block():
    """The course block MUST sit AFTER the app-shell block so window.__soCatalog
    (set by the app-shell at parse time) is defined before the course runs."""
    for slug in ADOPTED_COURSE_PANELS:
        html = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        shell = _APP_SHELL_BLOCK_RE.search(html)
        course = _BLOCK_RE.search(html)
        assert shell, f"{slug}: app-shell block missing"
        assert course, f"{slug}: course block missing"
        assert course.start() > shell.end(), (
            f"{slug}: course block must come AFTER the app-shell block "
            f"(so window.__soCatalog is set first)"
        )
