"""SDD-109 — D-19 super-model-manifest client-side export contract.

`webapp/d-19-super-model-manifest/index.html` renders the M001..M080 module
manifest with status + family filter chips; this locks the added CSV+JSON export
that lets the operator take the manifest as a hand-off / audit artifact. The
export is a pure client-side read-compute (R10212): it serializes the DERIVED
(chip-filtered) rows via the single-source `filteredMs()` — exactly what's on
screen (SB-077) — with NO new fetch / EventSource / server mutation of its own.
(The panel also inlines the shared control-surface component, whose sanctioned
exec-rail POST is pre-existing + unrelated; the R10212 guard is scoped to the
export code this increment added.)

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "webapp" / "d-19-super-model-manifest" / "index.html"


def _html() -> str:
    assert PANEL.is_file(), f"missing {PANEL}"
    return PANEL.read_text(encoding="utf-8")


def _export_region(html: str) -> str:
    m = re.search(r"//\s*.*export the DERIVED \(chip-filtered\) manifest \(SDD-109\)"
                  r"[\s\S]*?addEventListener\('click', exportJson\);", html)
    assert m, "export region markers not found"
    return m.group(0)


def test_export_buttons_present():
    html = _html()
    assert 'id="export-csv"' in html, "d-19 must ship a CSV export button"
    assert 'id="export-json"' in html, "d-19 must ship a JSON export button"


def test_export_serializes_the_derived_set_not_raw_milestones():
    """SB-077 — export must read `filteredMs()` (the on-screen chip-filtered set),
    NOT dump raw `milestones`. Both exporters + renderMs() read the one helper."""
    html = _html()
    assert "function filteredMs()" in html, "the single-source filteredMs() helper must exist"
    assert re.search(r"const rows = filteredMs\(\)", html), (
        "renderMs() must read filteredMs() (single source of the on-screen rows)"
    )
    for fn in ("function exportCsv()", "function exportJson()"):
        assert fn in html, f"missing {fn}"
    assert "JSON.stringify(filteredMs()" in html, (
        "exportJson must serialize filteredMs() (the derived set)"
    )
    assert re.search(r"const rows = filteredMs\(\);[\s\S]{0,300}EXPORT_COLS", html), (
        "exportCsv must build its CSV from filteredMs() rows"
    )


def test_csv_uses_the_cell_escaper():
    html = _html()
    assert 'replace(/"/g, \'""\')' in html or 'replace(/"/g,\'""\')' in html, (
        "CSV export must escape embedded quotes"
    )
    assert re.search(r'/\[",\\n\]/', html), "CSV export must quote fields with , \" or newline"


def test_export_is_a_client_side_blob_download():
    html = _html()
    assert "new Blob(" in html, "export must build a Blob"
    assert "URL.createObjectURL" in html and "revokeObjectURL" in html, (
        "export must create + revoke an object URL"
    )
    assert ".download =" in html or "a.download" in html, (
        "export must set the <a download> filename"
    )


def test_data_load_is_the_single_snapshot_fetch():
    """R10212 — the manifest is loaded by exactly one fetch, of the snapshot API."""
    html = _html()
    fetches = re.findall(r'fetch\(\s*["\']/api/d-19/snapshot["\']', html)
    assert len(fetches) == 1, (
        f"there must be exactly one snapshot data fetch; found {len(fetches)}"
    )


def test_export_region_adds_no_fetch_or_stream():
    """R10212 — the export is a recompute of the already-loaded milestones[]; the
    added export code must contain NO fetch / EventSource / mutation of its own."""
    region = _export_region(_html())
    assert "fetch(" not in region, "the export must not fetch (recompute of milestones[])"
    assert "EventSource" not in region, "the export must not open an SSE stream"
    for verb in ("POST", "PUT", "DELETE"):
        assert f"method: '{verb}'" not in region and f'method: "{verb}"' not in region, (
            f"the export is read-only; found a {verb} in the export code"
        )
