"""R343 (E9.M16) — SDD-035 workload-mode adoption doctrine L1 lint.

Pins the cross-advisor pattern proven across R339-R342 so future
adopters follow the same shape + any drift fails at push-time.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_PATH = REPO_ROOT / "docs" / "sdd" / "035-workload-mode-adoption-doctrine.md"
COORDINATOR = REPO_ROOT / "scripts" / "intelligence" / "workload-mode.py"


# Adopter registry. (script_rel_path, adopter_round, expected_helper_fn_or_None)
# helper_fn=None means the adopter uses a derive-shape helper instead
# of the standard _apply_mode_modulation.
ADOPTERS = [
    ("scripts/hardware/fan-advisor.py",                  "R339",
     "_read_canonical_mode"),
    ("scripts/hardware/cpu-hotswap.py",                  "R340",
     "_read_canonical_mode"),
    ("scripts/hardware/thermal-oc-budget.py",            "R341",
     "_read_canonical_mode"),
    ("scripts/hardware/memory-pressure-oc-damper.py",    "R342",
     "_read_canonical_mode"),
    # R344 (E2.M32): first post-SDD-035 adopter validates contract
    # generalizes beyond the original 4-set.
    ("scripts/hardware/xmp-oc-room-advisor.py",          "R344",
     "_read_canonical_mode"),
    # R345 (E2.M33): closes SDD-035 deferred candidate R293
    # power-profiles — different shape (profile-name string) but
    # same contract.
    ("scripts/power/profiles.py",                        "R345",
     "_read_canonical_mode"),
]


REQUIRED_SDD_SECTIONS = [
    "## Mission",
    "## The contract — every R338 adopter MUST",
    "## Current adopter registry",
    "## L1 lint enforcement",
    "## What this SDD does NOT do",
    "## Future-quarter adoption candidates",
    "## Doctrine evolution",
]


def _read(rel: str) -> str:
    p = REPO_ROOT / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def test_sdd_035_exists():
    assert SDD_PATH.is_file(), f"missing {SDD_PATH}"


def test_sdd_035_has_required_sections():
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SDD_SECTIONS if s not in body]
    assert not missing, (
        f"SDD-035 missing required sections: {missing}.\n"
        "If a section was deliberately renamed, update "
        "REQUIRED_SDD_SECTIONS in this test in the same commit."
    )


def test_sdd_035_cross_links_all_adopter_rounds():
    body = SDD_PATH.read_text(encoding="utf-8")
    for _, adopter_round, _ in ADOPTERS:
        assert adopter_round in body, (
            f"SDD-035 must cross-ref adopter round {adopter_round}"
        )


def test_workload_mode_coordinator_present():
    assert COORDINATOR.is_file(), (
        f"R338 workload-mode coordinator script missing: {COORDINATOR}"
    )


def test_coordinator_declares_4_named_modes():
    body = _read("scripts/intelligence/workload-mode.py")
    for mode in ("idle", "inference-ready", "training", "oc-burst"):
        assert f'"{mode}"' in body, f"R338 missing mode: {mode}"


def test_each_adopter_carries_follow_knob():
    for rel, _, _ in ADOPTERS:
        body = _read(rel)
        assert body, f"empty adopter script: {rel}"
        assert "follow_workload_mode_coordinator" in body, (
            f"{rel} missing follow_workload_mode_coordinator knob "
            "(SDD-035 opt-out contract)"
        )
        assert "workload_mode_overlay_path" in body, (
            f"{rel} missing workload_mode_overlay_path knob"
        )


def test_each_adopter_defines_canonical_reader():
    for rel, _, expected_fn in ADOPTERS:
        body = _read(rel)
        # Match `def _read_canonical_mode(` (or future derive-shape helper).
        assert f"def {expected_fn}(" in body, (
            f"{rel} missing {expected_fn} helper (SDD-035 contract)"
        )


def test_each_adopter_emits_workload_mode_fields_in_json():
    for rel, _, _ in ADOPTERS:
        body = _read(rel)
        # Either the modulation wrapper OR direct emit in build_report:
        # all adopters write a "workload_mode_canonical" +
        # "workload_mode_source" key into the returned dict.
        assert '"workload_mode_canonical"' in body, (
            f"{rel} must emit workload_mode_canonical field "
            "(SDD-035 output contract)"
        )
        assert '"workload_mode_source"' in body, (
            f"{rel} must emit workload_mode_source field"
        )


def test_each_adopter_handles_R338_canonical_source_tag():
    """Source tag 'R338-canonical' must appear in adopter code so the
    NEVER-raise canonical resolver produces audit-trail-friendly source
    strings."""
    for rel, _, _ in ADOPTERS:
        body = _read(rel)
        assert '"R338-canonical"' in body, (
            f"{rel} must use 'R338-canonical' source tag (audit contract)"
        )


def test_each_adopter_carries_workload_mode_to_shape_map():
    """Each adopter must expose a WORKLOAD_MODE_TO_<SHAPE> map per
    SDD-035 §3 — operator audits the per-mode action via this map."""
    pattern = re.compile(r"^WORKLOAD_MODE_TO_[A-Z_]+\s*[:=]", re.M)
    # R337 fan-advisor uses a different shape (MODE_CATALOG drives the
    # per-mode duty curves directly); allow either pattern.
    for rel, _, _ in ADOPTERS:
        body = _read(rel)
        has_map = bool(pattern.search(body))
        has_mode_catalog = "MODE_CATALOG" in body
        assert has_map or has_mode_catalog, (
            f"{rel} must expose a WORKLOAD_MODE_TO_<SHAPE> map OR a "
            "MODE_CATALOG with per-mode action data (SDD-035 §3)"
        )


# The 4 canonical modes the coordinator declares (locked by
# test_coordinator_declares_4_named_modes).
CANONICAL_MODES = ("idle", "inference-ready", "training", "oc-burst")


def test_each_adopter_covers_all_4_canonical_modes():
    """SDD-035 lockstep: it is not enough that an adopter HAS a per-mode
    map (test_each_adopter_carries_workload_mode_to_shape_map) — the map
    MUST carry an entry for every canonical mode. Otherwise an adopter
    could silently drop e.g. 'inference-ready' and, when the operator
    selects that mode, modulate nothing (or fall through to a default) with
    no signal — exactly the minimization §1g forbids, and the failure mode
    that motivated this gate. Each canonical mode string must appear as a
    quoted literal in the adopter source (the map/catalog keys are the only
    place all four co-occur)."""
    for rel, _, _ in ADOPTERS:
        body = _read(rel)
        missing = [
            m for m in CANONICAL_MODES
            if f'"{m}"' not in body and f"'{m}'" not in body
        ]
        assert not missing, (
            f"{rel} does not cover canonical workload mode(s) {missing} in "
            f"its per-mode map — every adopter MUST modulate all of "
            f"{CANONICAL_MODES} (SDD-035 adopter↔coordinator mode lockstep)"
        )


def test_sdd_035_documents_never_raise_contract():
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "NEVER-raise" in body or "NEVER raise" in body, (
        "SDD-035 must document the NEVER-raise contract (inherited from "
        "SDD-032 helper library)"
    )


def test_sdd_035_documents_precedence_rules():
    body = SDD_PATH.read_text(encoding="utf-8")
    # The 3-tier resolution doctrine must be documented.
    assert "Three-tier" in body or "three-tier" in body or "precedence" in body.lower()
    # The source tag values must appear (operator audit-trail).
    for tag in ("R338-canonical", "explicit"):
        assert tag in body, f"SDD-035 must document source tag: {tag}"
