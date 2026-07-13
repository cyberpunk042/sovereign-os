"""Cockpit wasm-bridge contract (audit F-2026-001 / SDD-969).

The 413 `sovereign-cockpit-*` crates encode the cockpit's UX-state logic in
typed, tested Rust — but the webapp is hand-written HTML/JS, so nothing runs
them and every panel re-implements that logic (and can silently drift). The
`cockpit-wasm` bridge compiles a wasm-bindgen facade over those crates so a
panel calls the REAL Rust decision function. First crate bridged:
`sovereign-cockpit-banner-state`.

This lint keeps the bridge honest end-to-end: the facade crate stays out of the
workspace (wasm-bindgen needs `unsafe`; `sovereign-simd` is the one sanctioned
unsafe crate), the committed artifact is a real wasm module exporting the
functions the panel binds, the panel imports it, and the read-only serving api +
unit agree on the port and ship the `application/wasm` MIME.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRATE = REPO / "cockpit-wasm"
ARTIFACT = REPO / "webapp" / "_shared" / "cockpit-wasm"
# Served demonstrator, co-located with the wasm under _shared (not a nav panel;
# nav-panel promotion is a follow-up per SDD-969).
PANEL = ARTIFACT / "demo.html"
API = REPO / "scripts" / "operator" / "cockpit-bridge-api.py"
UNIT = REPO / "systemd" / "system" / "sovereign-cockpit-bridge-api.service"

EXPORTS = ["banner_severity", "banner_state", "banner_validate", "schema_version"]


def test_facade_crate_exists_and_is_excluded_from_workspace():
    assert (CRATE / "Cargo.toml").is_file(), "cockpit-wasm/Cargo.toml missing"
    assert (CRATE / "src" / "lib.rs").is_file(), "cockpit-wasm/src/lib.rs missing"
    root = (REPO / "Cargo.toml").read_text(encoding="utf-8")
    # It must be excluded: wasm-bindgen emits unsafe glue; the workspace keeps
    # sovereign-simd as its ONE sanctioned unsafe crate.
    m = re.search(r"(?ms)^\[workspace\].*?(?=^\[[a-z])", root)
    assert m and "cockpit-wasm" in m.group(0) and "exclude" in m.group(0), (
        "cockpit-wasm must be in root Cargo.toml [workspace].exclude"
    )


def test_facade_cargo_is_a_wasm_cdylib():
    cargo = (CRATE / "Cargo.toml").read_text(encoding="utf-8")
    assert "wasm-bindgen" in cargo, "facade must depend on wasm-bindgen"
    assert "cdylib" in cargo, "facade [lib] crate-type must include cdylib (for wasm)"
    assert 'unsafe_code = "allow"' in cargo, (
        "facade must document the wasm-bindgen unsafe-glue allowance in [lints.rust]"
    )
    # It bridges a real cockpit crate (path dep), not a toy.
    assert "sovereign-cockpit-banner-state" in cargo, (
        "first bridged crate sovereign-cockpit-banner-state must be a dependency"
    )


def test_committed_artifact_is_a_real_wasm_module():
    js = ARTIFACT / "cockpit_wasm.js"
    wasm = ARTIFACT / "cockpit_wasm_bg.wasm"
    assert js.is_file(), f"missing built glue {js} (run cockpit-wasm/build.sh)"
    assert wasm.is_file(), f"missing built wasm {wasm} (run cockpit-wasm/build.sh)"
    assert wasm.read_bytes()[:4] == b"\x00asm", "artifact is not a valid wasm module (bad magic)"


def test_glue_exports_the_bridge_surface():
    js = (ARTIFACT / "cockpit_wasm.js").read_text(encoding="utf-8")
    missing = [e for e in EXPORTS if e not in js]
    assert not missing, f"built glue does not export: {missing}"


def test_demo_imports_the_real_module():
    assert PANEL.is_file(), f"missing demo page {PANEL}"
    html = PANEL.read_text(encoding="utf-8")
    assert "_shared/cockpit-wasm/cockpit_wasm.js" in html, (
        "demo must import the committed wasm module"
    )
    assert "banner_severity" in html, "demo must call the real crate logic (banner_severity)"
    # Honest offline degradation (panels-always-visible-offline doctrine).
    assert re.search(r"catch\b", html), "demo must degrade gracefully when the wasm is absent"


def test_api_serves_wasm_mime_read_only_on_its_port():
    assert API.is_file(), f"missing {API}"
    src = API.read_text(encoding="utf-8")
    assert '"application/wasm"' in src, "api must serve .wasm as application/wasm"
    assert "8137" in src, "api must bind its declared port 8137"
    assert "405" in src, "api must be read-only (POST -> 405)"


def test_unit_matches_the_api_port():
    assert UNIT.is_file(), f"missing {UNIT}"
    unit = UNIT.read_text(encoding="utf-8")
    m = re.search(r"Environment=COCKPIT_BRIDGE_API_PORT=(\d+)", unit)
    assert m and m.group(1) == "8137", "unit COCKPIT_BRIDGE_API_PORT must be 8137"


def test_build_script_is_reproducible_and_executable():
    build = CRATE / "build.sh"
    assert build.is_file(), "cockpit-wasm/build.sh missing (reproduces the artifact)"
    import os
    assert os.access(build, os.X_OK), "cockpit-wasm/build.sh must be executable"
