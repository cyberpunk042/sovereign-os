"""SDD-106 — the models-catalog browser's client-side export contract.

`webapp/models-catalog/index.html` already has client-side column sort + 6-facet
filter; this locks the added CSV+JSON export that completes the sort/filter/export
triad. The export is a pure client-side read-compute (R10212): it serializes the
DERIVED (filtered+sorted) rows via the single-source `sortedFiltered()` — exactly
what's on screen (SB-077) — with NO new fetch / EventSource / server mutation.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "webapp" / "models-catalog" / "index.html"


def _html() -> str:
    assert PANEL.is_file(), f"missing {PANEL}"
    return PANEL.read_text(encoding="utf-8")


def test_export_buttons_present():
    html = _html()
    assert 'id="export-csv"' in html, "models-catalog must ship a CSV export button"
    assert 'id="export-json"' in html, "models-catalog must ship a JSON export button"


def test_export_serializes_the_derived_set_not_raw_models():
    """SB-077 — export must read `sortedFiltered()` (the on-screen filtered+sorted
    set), NOT dump raw `MODELS`. Both exporters + render() read the one helper."""
    html = _html()
    assert "function sortedFiltered()" in html, (
        "the single-source sortedFiltered() helper must exist"
    )
    # render() reads the helper (no separate sort path that could diverge)
    assert re.search(r"const rows = sortedFiltered\(\)", html), (
        "render() must read sortedFiltered() (single source of the on-screen rows)"
    )
    for fn in ("function exportCsv()", "function exportJson()"):
        assert fn in html, f"missing {fn}"
    # each exporter serializes the derived set
    assert "JSON.stringify(sortedFiltered()" in html, (
        "exportJson must serialize sortedFiltered() (the derived set)"
    )
    assert re.search(r"const rows = sortedFiltered\(\);[\s\S]{0,400}EXPORT_COLS", html), (
        "exportCsv must build its CSV from sortedFiltered() rows"
    )


def test_csv_uses_the_cell_escaper():
    """The CSV cell escaper (quote fields containing "/,/newline) must be present —
    the reused d-11-adapter-status idiom."""
    html = _html()
    assert 'replace(/"/g, \'""\')' in html or 'replace(/"/g,\'""\')' in html, (
        "CSV export must escape embedded quotes"
    )
    assert re.search(r'/\[",\\n\]/', html), "CSV export must quote fields with , \" or newline"


def test_export_is_a_client_side_blob_download():
    """Pure client-side file download — Blob + object URL + <a download>."""
    html = _html()
    assert "new Blob(" in html, "export must build a Blob"
    assert "URL.createObjectURL" in html and "revokeObjectURL" in html, (
        "export must create + revoke an object URL"
    )
    assert ".download =" in html or "a.download" in html, (
        "export must set the <a download> filename"
    )


def _export_region(html: str) -> str:
    """The SDD-106 export code only — from its marker comment to `load();`. (The
    panel also inlines the shared control-surface component, whose sanctioned
    exec-rail POST is pre-existing + unrelated; this scopes the R10212 guard to
    what THIS increment added.)"""
    m = re.search(r"//\s*.*export the DERIVED set \(SDD-106\)[\s\S]*?\nload\(\);", html)
    assert m, "export region markers not found"
    return m.group(0)


def test_data_load_is_the_single_catalog_fetch():
    """R10212 — the catalog data is loaded by exactly one fetch, of the served
    catalog JSON. (The export adds no data fetch — asserted below.)"""
    html = _html()
    catalog_fetches = re.findall(r'fetch\(\s*["\']/models-catalog\.json["\']', html)
    assert len(catalog_fetches) == 1, (
        f"there must be exactly one catalog data fetch; found {len(catalog_fetches)}"
    )


def test_export_region_adds_no_fetch_or_stream():
    """R10212 — the export is a recompute of the already-loaded MODELS[]; the added
    export code must contain NO fetch / EventSource / mutation of its own."""
    region = _export_region(_html())
    assert "fetch(" not in region, "the export must not fetch (recompute of MODELS[])"
    assert "EventSource" not in region, "the export must not open an SSE stream"
    for verb in ("POST", "PUT", "DELETE"):
        assert f"method: '{verb}'" not in region and f'method: "{verb}"' not in region, (
            f"the export is read-only; found a {verb} in the export code"
        )


# ── SDD-108: view-state persistence (remember filter + sort) ────────────────────

def test_view_persistence_present_and_keyed():
    """The panel persists the filter + sort to a distinct localStorage key + schema."""
    html = _html()
    assert 'VKEY = "sovereign-os.models-catalog.view"' in html, (
        "view-state must use its own distinct localStorage key (not the personalization key)"
    )
    assert "VSCHEMA = 1" in html, "view-state must declare a schema version"
    assert "function saveView()" in html and "function restoreView()" in html, (
        "view-state must define saveView() + restoreView()"
    )
    assert "localStorage.setItem(VKEY" in html and "localStorage.getItem(VKEY" in html, (
        "view-state must read/write VKEY"
    )


def test_view_restore_is_schema_guarded_and_restored_before_render():
    """restoreView must schema-guard the stored state and run in load() AFTER the
    options are built but BEFORE the first render (so a restored select value sticks
    and there's no double-render). A garbage entry falls back to defaults."""
    html = _html()
    assert "v.schema !== VSCHEMA" in html, "restoreView must reject a mismatched schema"
    assert re.search(r"buildFilters\(\);\s*restoreView\(\);(?:\s*renderStats\(\);)?\s*render\(\)", html), (
        "load() must call restoreView() after buildFilters() and before render()"
    )
    # try/catch fallback (never crashes on garbage / storage-unavailable)
    assert "catch (e) { return; }" in html or "catch (e) {" in html, (
        "restoreView must fall back to defaults on a parse/storage error"
    )


def test_view_saved_on_change_and_clearable():
    """saveView is wired to the filter + sort changes; a #clear-view escape hatch
    resets and forgets the saved view (removeItem)."""
    html = _html()
    assert "saveView(); render()" in html, "a filter/sort change must saveView() then render()"
    assert 'id="clear-view"' in html, "the panel must offer a clear-view escape hatch"
    assert "function clearView()" in html and "localStorage.removeItem(VKEY)" in html, (
        "clearView must reset + removeItem(VKEY)"
    )


def test_view_persistence_adds_no_fetch():
    """R10212 — view persistence is pure localStorage; it adds no fetch/stream. (The
    single-catalog-fetch guard above already re-asserts the whole-file fetch shape.)"""
    html = _html()
    # the saveView/restoreView/clearView block references localStorage, not fetch
    m = re.search(r"function saveView\(\)[\s\S]*?function clearView\(\)[\s\S]*?\n\}", html)
    assert m, "view-state functions block not found"
    assert "fetch(" not in m.group(0) and "EventSource" not in m.group(0), (
        "view persistence must be pure client-side (no fetch/stream)"
    )
