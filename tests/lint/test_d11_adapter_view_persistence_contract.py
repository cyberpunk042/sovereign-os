"""SDD-110 — D-11 adapter-status view-state persistence contract.

`webapp/d-11-adapter-status/index.html` already has CSV export + 4 filter selects;
this locks the added view-state persistence that remembers the filters across
reloads. Pure client-side (localStorage): a distinct key + schema guard; seeded
ONCE from refresh() after #base-filter's options exist (the panel is SSE-refreshed
and its base options are rebuilt each refresh). R10212 — no new fetch/EventSource/
mutation of its own; the pre-existing inventory fetch + adapter SSE stream are
unrelated. SB-077 — restoreView never crashes or applies invalid state.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "webapp" / "d-11-adapter-status" / "index.html"


def _html() -> str:
    assert PANEL.is_file(), f"missing {PANEL}"
    return PANEL.read_text(encoding="utf-8")


def test_view_persistence_present_and_keyed():
    html = _html()
    assert 'VKEY = "sovereign-os.d-11-adapter-status.view"' in html, (
        "view-state must use its own distinct localStorage key (not the personalization key)"
    )
    assert "VSCHEMA = 1" in html, "view-state must declare a schema version"
    assert "function saveView()" in html and "function restoreView()" in html, (
        "view-state must define saveView() + restoreView()"
    )
    assert "localStorage.setItem(VKEY" in html and "localStorage.getItem(VKEY" in html, (
        "view-state must read/write VKEY"
    )


def test_view_restore_is_schema_guarded_and_seeded_once_in_refresh():
    """restoreView must schema-guard the stored state; the seed runs ONCE via the
    viewRestored flag inside refresh() (after #base-filter options are rebuilt, so a
    restored base value sticks). A garbage entry falls back to defaults."""
    html = _html()
    assert "v.schema !== VSCHEMA" in html, "restoreView must reject a mismatched schema"
    assert "let viewRestored = false" in html, "a viewRestored one-shot flag must exist"
    assert re.search(r"if \(!viewRestored\)\s*\{\s*restoreView\(\);\s*viewRestored = true;", html), (
        "refresh() must seed the view once via `if (!viewRestored) { restoreView(); viewRestored = true; }`"
    )
    assert "catch (e) { return; }" in html, (
        "restoreView must fall back to defaults on a parse/storage error"
    )
    # stale-option guard — only apply a value still present as an <option>
    assert re.search(r"\.options\].some\(o => o\.value === val\)", html), (
        "restoreView must drop a stale value not in the select's options"
    )


def test_view_saved_on_filter_change_and_clearable():
    """saveView is wired to the 4 filters' change; a #clear-view escape hatch resets
    and forgets the saved view (removeItem)."""
    html = _html()
    assert re.search(r"VIEW_FILTER_IDS\.forEach\(id => \$\(id\)\.addEventListener\('change'", html), (
        "each filter change must persist the view"
    )
    assert 'id="clear-view"' in html, "the panel must offer a clear-view escape hatch"
    assert "function clearView()" in html and "localStorage.removeItem(VKEY)" in html, (
        "clearView must reset + removeItem(VKEY)"
    )


def test_view_persistence_adds_no_fetch_or_stream():
    """R10212 — view persistence is pure localStorage; the saveView/restoreView/
    clearView block adds no fetch/EventSource of its own. (The pre-existing
    inventory fetch + adapter SSE stream elsewhere in the panel are unrelated.)"""
    html = _html()
    m = re.search(r"function saveView\(\)[\s\S]*?function clearView\(\)[\s\S]*?\n\}", html)
    assert m, "view-state functions block not found"
    block = m.group(0)
    assert "fetch(" not in block and "EventSource" not in block, (
        "view persistence must be pure client-side (no fetch/stream)"
    )
