"""R348 (E9.M17) — Layer 1 lint pinning scripts/lib/inventory_consult
public API per SDD-032 §4 helper-library doctrine.

A future refactor that renames find_advisor_caveats / caveats_matching
or breaks the NEVER-raise contract takes down R315 xmp-oc-room-advisor
+ R252 power-status (current consumers) AND any future adopter. This
lint catches the break at push-time.
"""
from __future__ import annotations

import importlib.util
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "scripts" / "lib" / "inventory_consult.py"


def _load_helper():
    spec = importlib.util.spec_from_file_location(
        "inventory_consult_under_test", HELPER_PATH,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_helper_file_exists():
    assert HELPER_PATH.is_file(), f"missing {HELPER_PATH}"


def test_helper_exports_find_advisor_caveats():
    mod = _load_helper()
    assert hasattr(mod, "find_advisor_caveats"), (
        "scripts/lib/inventory_consult.find_advisor_caveats missing "
        "(SDD-032 §4 public API contract — consumers R315 + R252)"
    )
    assert callable(mod.find_advisor_caveats)


def test_helper_exports_caveats_matching():
    mod = _load_helper()
    assert hasattr(mod, "caveats_matching"), (
        "scripts/lib/inventory_consult.caveats_matching missing "
        "(SDD-032 §4 public API contract)"
    )
    assert callable(mod.caveats_matching)


def test_find_advisor_caveats_never_raises_on_empty_round():
    mod = _load_helper()
    # Empty round_id → []
    assert mod.find_advisor_caveats("") == []
    # Round_id matching nothing → []
    assert mod.find_advisor_caveats("R99999") == []


def test_find_advisor_caveats_returns_list_of_dicts():
    mod = _load_helper()
    # R315 is a known adopter with at least one caveat in catalog.
    out = mod.find_advisor_caveats("R315")
    assert isinstance(out, list)
    if out:
        cv = out[0]
        for k in ("slot", "caveat", "severity"):
            assert k in cv, (k, cv)
        assert cv["severity"] in ("warn", "info")


def test_caveats_matching_filters_by_contains_any():
    mod = _load_helper()
    base = mod.find_advisor_caveats("R315")
    if not base:
        return  # tolerated — catalog may rotate
    # contains_any = ["impossible-substring-xyz"] → []
    filtered = mod.caveats_matching("R315", contains_any=["xyz-nonexistent-zzz"])
    assert filtered == []


def test_caveats_matching_contains_all_requires_all_substrings():
    mod = _load_helper()
    # Even when one substring matches, all-substrings missing → []
    filtered = mod.caveats_matching(
        "R315",
        contains_all=["xmp", "xyz-nonexistent-zzz"],
    )
    assert filtered == []


def test_helper_consumers_present():
    """Known consumers (R315, R252) currently import the helper.
    Catches if a refactor drops the import line accidentally."""
    r315 = (REPO_ROOT / "scripts" / "hardware"
            / "xmp-oc-room-advisor.py").read_text()
    assert "from inventory_consult import find_advisor_caveats" in r315, (
        "R315 xmp-oc-room-advisor lost its inventory_consult import"
    )
    r252 = (REPO_ROOT / "scripts" / "hardware"
            / "power-status.py").read_text()
    assert "from inventory_consult import find_advisor_caveats" in r252, (
        "R252 power-status lost its inventory_consult import"
    )
