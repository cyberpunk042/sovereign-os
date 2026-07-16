"""Cockpit wasm master-dashboard banner — contract test.

The banner bridges sovereign-cockpit-banner-state into the master-dashboard
so the severity is computed by the crate in wasm, not re-implemented in JS.
Audit F-2026-001 / SDD-974.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = REPO_ROOT / "webapp" / "master-dashboard" / "index.html"
API = REPO_ROOT / "scripts" / "operator" / "cockpit-bridge-api.py"


def _read(path: Path) -> str:
    return path.read_text()


# ──────────────────────────────────────────── master-dashboard banner


def test_banner_dom_element_present():
    body = _read(DASHBOARD)
    assert 'id="cockpit-wasm-banner"' in body
    assert 'role="status"' in body and 'aria-live="polite"' in body


def test_banner_dom_labels_present():
    body = _read(DASHBOARD)
    for id_ in ("cockpit-wasm-label", "cockpit-wasm-detail", "cockpit-wasm-meta"):
        assert f'id="{id_}"' in body, f"banner missing label span id={id_!r}"


def test_banner_links_to_bridge_surface():
    body = _read(DASHBOARD)
    assert "/_shared/cockpit-wasm/" in body


def test_render_function_present_and_polls_canonical_endpoint():
    body = _read(DASHBOARD)
    assert "async function renderCockpitWasmBanner()" in body
    assert "/signals.json" in body


def test_render_invoked_on_grid_refresh():
    body = _read(DASHBOARD)
    grid_start = body.find("async function renderM060Grid()")
    assert grid_start != -1
    next_fn = body.find("\nasync function ", grid_start + 1)
    if next_fn == -1:
        next_fn = body.find("\nfunction ", grid_start + 1)
    grid_body = body[grid_start:next_fn if next_fn > 0 else len(body)]
    assert "renderCockpitWasmBanner()" in grid_body


def test_banner_handles_all_canonical_states():
    body = _read(DASHBOARD)
    canonical_states = ["calm", "notice", "warn", "critical", "unknown", "offline", "unreachable"]
    for state in canonical_states:
        css_selector = f".cockpit-wasm-banner.{state}"
        assert css_selector in body, f"banner CSS missing class selector for state {state!r}"
    fn_start = body.find("async function renderCockpitWasmBanner()")
    next_fn = body.find("\nasync function ", fn_start + 1)
    if next_fn == -1:
        next_fn = body.find("\nfunction ", fn_start + 1)
    fn_body = body[fn_start:next_fn if next_fn > 0 else len(body)]
    for state in canonical_states:
        assert f'"{state}"' in fn_body, f"renderCockpitWasmBanner knownStates missing state {state!r}"


def test_render_imports_wasm_module():
    body = _read(DASHBOARD)
    # The import() lives in _initCockpitWasm right before renderCockpitWasmBanner.
    start = body.find("async function _initCockpitWasm()")
    next_fn = body.find("\nasync function ", start + 1)
    if next_fn == -1:
        next_fn = body.find("\nfunction ", start + 1)
    fn_body = body[start:next_fn if next_fn > 0 else len(body)]
    assert "cockpit_wasm.js" in fn_body
    assert "import(" in fn_body


def test_render_degrades_gracefully():
    body = _read(DASHBOARD)
    fn_start = body.find("async function renderCockpitWasmBanner()")
    next_fn = body.find("\nasync function ", fn_start + 1)
    if next_fn == -1:
        next_fn = body.find("\nfunction ", fn_start + 1)
    fn_body = body[fn_start:next_fn if next_fn > 0 else len(body)]
    assert "catch" in fn_body
    assert "offline" in fn_body
    assert "unreachable" in fn_body


def test_demo_data_includes_signals_json():
    body = _read(DASHBOARD)
    assert '"/signals.json"' in body
    assert "mode:" in body
    assert "worst_thermal:" in body


# ──────────────────────────────────────────────── bridge api


def test_api_has_cors_headers():
    body = _read(API)
    assert "Access-Control-Allow-Origin" in body
