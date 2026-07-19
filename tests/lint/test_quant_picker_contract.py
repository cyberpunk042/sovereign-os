"""Load-time quantization picker on D-03 (SDD-049).

The model-health panel carries a picker that groups the catalog by base model
and lets the operator pick a model then its quantization — the choice RESOLVES a
catalog id and fills the signed `model-load` control, whose dry-run + key +
type-to-confirm path performs the actual load. This locks that the picker is
present, reads the read-only by-base endpoint, and hands off to the signed
control rather than mutating anything itself (R10212).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "webapp" / "d-03-model-health" / "index.html"
API = REPO / "scripts" / "operator" / "models-catalog-api.py"


def _panel() -> str:
    return PANEL.read_text(encoding="utf-8")


def test_picker_present_on_model_health_panel():
    html = _panel()
    assert 'id="quant-picker"' in html, "D-03 must carry the quantization picker"
    assert 'id="qp-base"' in html and 'id="qp-variants"' in html, (
        "picker needs the base <select> + the variant button group"
    )


def test_picker_reads_the_readonly_by_base_endpoint():
    html = _panel()
    assert "/api/models-catalog/by-base" in html, (
        "picker must source variants from the read-only by-base endpoint"
    )
    # the endpoint is wired + the catalog daemon stays read-only
    src = API.read_text(encoding="utf-8")
    assert '"/api/models-catalog/by-base"' in src and "def by_base_view" in src
    assert "def do_POST" in src and "_reject" in src, "catalog daemon must reject writes"


def test_picker_hands_off_to_the_signed_model_load_control():
    """The picker never mutates — it resolves a catalog id and fills the signed
    model-load control (whose Execute is the R10274 control-exec path). It must
    target that control's id input, not POST anything itself."""
    html = _panel()
    assert '[data-cid="model-load"]' in html, "picker must target the model-load control card"
    assert 'input.cs-arg[data-argkey="id"]' in html, (
        "picker must fill the model-load id arg so the operator executes via the signed control"
    )
    # the picker's own fetch is a GET (the by-base read); it introduces no POST —
    # scope the check to the picker <script> block.
    m = re.search(r'id="quant-picker".*?<script>(.*?)</script>', html, re.DOTALL)
    assert m, "picker script block not found"
    picker_js = m.group(1)
    assert "fetch(" in picker_js and "method:'POST'" not in picker_js.replace(" ", ""), (
        "the picker must only READ (GET by-base); the write path stays the signed control"
    )
