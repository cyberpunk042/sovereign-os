"""Load-time quantization picker (SDD-049) — shared component + lockstep.

The picker groups the catalog by base model and lets the operator pick a model
then its quantization; the choice RESOLVES a catalog id and fills the signed
`model-load` control, whose dry-run + key + type-to-confirm path performs the
actual load. It is a canonical webapp/_shared/quant-picker.{css,js}, inlined
verbatim into every panel that carries a #quant-picker + the model-load control
(D-03 the model-health load panel, D-21 lm-orchestration), kept in lockstep here
(the single-file / no-external-script doctrine). Read-only: the widget only reads
by-base (GET) and populates the control — it never mutates (R10212).

D-23 (the read-only catalog browse, no load control) surfaces the same by-base
grouping as a compare-quantizations metadata section instead.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHARED_CSS = REPO / "webapp" / "_shared" / "quant-picker.css"
SHARED_JS = REPO / "webapp" / "_shared" / "quant-picker.js"
PICKER_PANELS = [
    REPO / "webapp" / "d-03-model-health" / "index.html",
    REPO / "webapp" / "d-21-lm-orchestration" / "index.html",
]
CATALOG_PANEL = REPO / "webapp" / "d-23-models-catalog" / "index.html"
API = REPO / "scripts" / "operator" / "models-catalog-api.py"


def test_canonical_shared_component_exists_and_is_read_only():
    assert SHARED_CSS.is_file(), f"missing {SHARED_CSS}"
    assert SHARED_JS.is_file(), f"missing {SHARED_JS}"
    js = SHARED_JS.read_text(encoding="utf-8")
    assert "/api/models-catalog/by-base" in js, "picker must read the by-base endpoint"
    assert '[data-cid="model-load"]' in js and 'input.cs-arg[data-argkey="id"]' in js, (
        "picker must fill the signed model-load control's id arg"
    )
    # never mutates — only the by-base GET; the write path is the signed control
    assert 'method:"POST"' not in js.replace(" ", "") and "method:'POST'" not in js.replace(" ", ""), (
        "the picker must only READ (GET by-base); the write path stays the signed control"
    )


def test_every_picker_panel_inlines_the_canonical_verbatim():
    """Single-file doctrine + no external <script src>: each panel with the picker
    inlines the canonical css + js byte-for-byte (lockstep — no drift between the
    two copies, the class of copy-paste bug this guards)."""
    css = SHARED_CSS.read_text(encoding="utf-8").strip()
    js = SHARED_JS.read_text(encoding="utf-8").strip()
    drift = []
    for panel in PICKER_PANELS:
        html = panel.read_text(encoding="utf-8")
        slug = panel.parent.name
        if 'id="quant-picker"' not in html or 'id="qp-base"' not in html or 'id="qp-variants"' not in html:
            drift.append(f"{slug}: missing the #quant-picker section")
        if css not in html:
            drift.append(f"{slug}: drifted from canonical quant-picker.css")
        if js not in html:
            drift.append(f"{slug}: drifted from canonical quant-picker.js")
        # each panel must actually carry the model-load control the picker targets
        if 'filterSlug' not in html or 'control-surface' not in html:
            drift.append(f"{slug}: no control-surface for the picker to hand off to")
    assert not drift, "quant-picker lockstep drift: " + "; ".join(drift)


def test_by_base_endpoint_wired_and_daemon_read_only():
    src = API.read_text(encoding="utf-8")
    assert '"/api/models-catalog/by-base"' in src and "def by_base_view" in src
    assert "def do_POST" in src and "_reject" in src, "catalog daemon must reject writes (R10212)"


def test_catalog_browse_surfaces_quantization_variants():
    """D-23 (the read-only catalog browse) surfaces the multi-quant models as a
    'quantization variants' section from the same by-base endpoint — its own
    stated purpose is comparing quantizations of the same base. No load here."""
    html = CATALOG_PANEL.read_text(encoding="utf-8")
    assert 'id="quant-variants"' in html, "D-23 must carry the quantization-variants section"
    assert "/api/models-catalog/by-base" in html and "renderQuantVariants" in html
    assert "sovereign-osctl models" in html or "R10212" in html, (
        "D-23 must keep its read-only / signed-load framing"
    )
    # D-23 DEMO path must make no fetch (regex mirrors test_demo_mode_contract)
    m = re.search(r"if \(demoActive\(\)\) \{(.*?)\n    \}", html, re.DOTALL)
    assert m and "fetch(" not in m.group(1), "D-23 DEMO render path must make NO fetch"
