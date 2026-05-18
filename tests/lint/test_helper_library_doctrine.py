"""R330 (E9.M13) — SDD-032 helper-library doctrine L1 lint.
R348 (E9.M17): extended to four modules (inventory_consult added).

Pins:
- The four helper modules exist at expected paths
- Each module exposes its declared public API surface
- NEVER-raise contracts documented in module docstrings
- SDD-032 carries required sections (similar to R326 pattern)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "lib"
SDD_PATH = REPO_ROOT / "docs" / "sdd" / "032-helper-library-doctrine.md"


# Required public symbols per helper module.
EXPECTED_API = {
    "operator_overlay": {
        "load_with_overlay", "resolve_overlay_path",
        "deep_merge", "collect_overlay_keys", "_env_var_name",
    },
    "apply_audit": {
        "record_apply", "query",
    },
    "safe_apply": {
        "evaluate_triple_gate", "check_maintenance_window",
        "run_apply_safe",
    },
    # R348 (E9.M17): R317 catalog cross-binding helper.
    "inventory_consult": {
        "find_advisor_caveats", "caveats_matching",
    },
}


REQUIRED_SDD_SECTIONS = [
    "## Mission",
    "## The library — four public modules",
    "## Import convention",
    "## NEVER-raise contract",
    "## L1 lint enforcement",
    "## What this SDD does NOT do",
    "## Future helper-library evolution",
]


def _load_module(name: str):
    """Load a helper module from scripts/lib/<name>.py without
    polluting global state."""
    src = LIB_DIR / f"{name}.py"
    if not src.is_file():
        return None
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    spec = importlib.util.spec_from_file_location(name, src)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_lib_dir_exists():
    assert LIB_DIR.is_dir(), f"missing {LIB_DIR}"


def test_all_helper_modules_present():
    for name in EXPECTED_API:
        path = LIB_DIR / f"{name}.py"
        assert path.is_file(), f"missing helper module: {path}"


def test_operator_overlay_public_api():
    mod = _load_module("operator_overlay")
    assert mod is not None, "operator_overlay failed to import"
    for sym in EXPECTED_API["operator_overlay"]:
        assert hasattr(mod, sym), (
            f"operator_overlay missing public symbol: {sym}"
        )


def test_apply_audit_public_api():
    mod = _load_module("apply_audit")
    assert mod is not None, "apply_audit failed to import"
    for sym in EXPECTED_API["apply_audit"]:
        assert hasattr(mod, sym), (
            f"apply_audit missing public symbol: {sym}"
        )


def test_safe_apply_public_api():
    mod = _load_module("safe_apply")
    assert mod is not None, "safe_apply failed to import"
    for sym in EXPECTED_API["safe_apply"]:
        assert hasattr(mod, sym), (
            f"safe_apply missing public symbol: {sym}"
        )


def test_inventory_consult_public_api():
    mod = _load_module("inventory_consult")
    assert mod is not None, "inventory_consult failed to import"
    for sym in EXPECTED_API["inventory_consult"]:
        assert hasattr(mod, sym), (
            f"inventory_consult missing public symbol: {sym}"
        )


def test_never_raise_contract_documented_apply_audit():
    """apply_audit must document the NEVER-raise contract."""
    mod = _load_module("apply_audit")
    doc = (mod.__doc__ or "") + " " + (getattr(mod.record_apply, "__doc__", "") or "")
    assert "NEVER raises" in doc or "NEVER raise" in doc, (
        "apply_audit must document the NEVER-raise contract "
        "(record_apply.__doc__ or module __doc__)"
    )


def test_never_raise_contract_documented_safe_apply():
    """safe_apply must document the NEVER-raise contract."""
    mod = _load_module("safe_apply")
    doc = (mod.__doc__ or "")
    if hasattr(mod, "run_apply_safe"):
        doc += " " + (getattr(mod.run_apply_safe, "__doc__", "") or "")
    assert "NEVER raise" in doc or "NEVER raises" in doc, (
        "safe_apply must document NEVER-raise contract"
    )


def test_sdd_032_exists():
    assert SDD_PATH.is_file(), f"missing {SDD_PATH}"


def test_sdd_032_has_required_sections():
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SDD_SECTIONS if s not in body]
    assert not missing, (
        f"SDD-032 missing required sections: {missing}.\n"
        "If you deliberately renamed a section, update "
        "REQUIRED_SDD_SECTIONS in tests/lint/test_helper_library_doctrine.py"
        " in the same commit."
    )


def test_sdd_032_cross_links_origin_rounds():
    """SDD-032 must cross-ref the rounds that originated each helper."""
    body = SDD_PATH.read_text(encoding="utf-8")
    # R283 → operator_overlay; R327 → apply_audit; R328 → safe_apply;
    # R348 → inventory_consult (R347 inline pattern promoted).
    for ref in ("R283", "R327", "R328", "R348"):
        assert ref in body, f"SDD-032 must cross-ref {ref}"


def test_sdd_032_documents_import_convention():
    body = SDD_PATH.read_text(encoding="utf-8")
    # The standard import preamble must appear so future authors
    # see the pattern.
    assert "sys.path.insert(0, str(REPO_ROOT" in body, (
        "SDD-032 must show the sys.path.insert convention for "
        "scripts/lib/ imports"
    )
    assert "from operator_overlay import load_with_overlay" in body
    assert "from safe_apply import run_apply_safe" in body
