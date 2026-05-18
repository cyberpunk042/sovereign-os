"""R367 (E10.M11) — SDD-037 verbatim-preservation doctrine L1 lint.

Pins:
- SDD-037 exists with 7 required sections
- architecture-qa.py catalog floor: ≥4 Q-NN + ≥3 G-NN + ≥10 C-NN
- coverage-map.py catalog floor: ≥30 A-NN
- Every architecture-qa item has non-empty spec_ref
- Every coverage-map axis has ≥1 implementing verb
- 4-binary Tetragon allowlist bidirectional consistency: appears in
  BOTH C-14 concept text AND tetragon-policy-load.sh script
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_PATH = REPO_ROOT / "docs" / "sdd" / "037-verbatim-preservation-doctrine.md"
ARCH_QA = REPO_ROOT / "scripts" / "intelligence" / "architecture-qa.py"
COVERAGE = REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py"
TETRAGON_SCRIPT = (REPO_ROOT / "scripts" / "hooks" / "post-install"
                   / "tetragon-policy-load.sh")


REQUIRED_SDD_SECTIONS = [
    "## Mission",
    "## The contract — every verbatim-preservation round MUST",
    "## Current shipped surface",
    "## L1 lint enforcement",
    "## What this SDD does NOT do",
    "## Future verbatim-surface additions",
    "## Doctrine evolution",
]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sdd_037_exists():
    assert SDD_PATH.is_file(), f"missing {SDD_PATH}"


def test_sdd_037_has_required_sections():
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SDD_SECTIONS if s not in body]
    assert not missing, (
        f"SDD-037 missing required sections: {missing}.\n"
        "Update REQUIRED_SDD_SECTIONS in tests/lint/"
        "test_verbatim_preservation_doctrine.py in the same commit if "
        "a section was deliberately renamed."
    )


def test_sdd_037_documents_typo_preservation():
    body = SDD_PATH.read_text(encoding="utf-8")
    # The typo-preservation rule is load-bearing for /goal contract.
    assert "Proto-Programing" in body, "SDD-037 must cite operator typo example"
    assert "planifest" in body, "SDD-037 must cite operator typo example"


def test_sdd_037_cross_links_origin_rounds():
    """SDD-037 must cross-reference the R355-R366 rounds that originated
    the doctrine."""
    body = SDD_PATH.read_text(encoding="utf-8")
    for ref in ("R355", "R357", "R358", "R359", "R362", "R363",
                "R364", "R365", "R366"):
        assert ref in body, f"SDD-037 must cross-ref {ref}"


def test_architecture_qa_catalog_floor():
    """Catalog floor: ≥4 Q-NN + ≥3 G-NN + ≥10 C-NN."""
    mod = _load_module(ARCH_QA, "architecture_qa_lint")
    assert len(mod.ARCHITECTURE_QUESTIONS) >= 4, (
        f"questions catalog below floor: {len(mod.ARCHITECTURE_QUESTIONS)}"
    )
    assert len(mod.ARCHITECTURE_GOTCHAS) >= 3, (
        f"gotchas catalog below floor: {len(mod.ARCHITECTURE_GOTCHAS)}"
    )
    assert len(mod.ARCHITECTURE_CONCEPTS) >= 10, (
        f"concepts catalog below floor: {len(mod.ARCHITECTURE_CONCEPTS)}"
    )


def test_architecture_qa_all_items_have_spec_ref():
    mod = _load_module(ARCH_QA, "architecture_qa_lint")
    for kind, items, label in (
        ("question", mod.ARCHITECTURE_QUESTIONS, "Q-NN"),
        ("gotcha", mod.ARCHITECTURE_GOTCHAS, "G-NN"),
        ("concept", mod.ARCHITECTURE_CONCEPTS, "C-NN"),
    ):
        for item in items:
            assert item.get("spec_ref"), (
                f"{label} {item.get('id', '?')} ({kind}) missing spec_ref"
            )
            assert len(item["spec_ref"]) >= 10, (
                f"{label} {item.get('id')} spec_ref too terse"
            )


def test_coverage_map_catalog_floor():
    """coverage-map floor: ≥30 A-NN."""
    mod = _load_module(COVERAGE, "coverage_map_lint")
    assert len(mod.DEFAULT_AXES) >= 30, (
        f"axes catalog below floor: {len(mod.DEFAULT_AXES)}"
    )


def test_coverage_map_every_axis_has_verb():
    """SDD-037 §1 invariant: every axis has ≥1 implementing verb (no
    orphan operator demand)."""
    mod = _load_module(COVERAGE, "coverage_map_lint")
    for axis in mod.DEFAULT_AXES:
        verbs = axis.get("implementing_verbs") or []
        assert len(verbs) >= 1, (
            f"axis {axis.get('id', '?')} has no implementing_verbs — "
            "violates SDD-037 §1 'every axis has ≥1 verb' invariant"
        )


def test_coverage_map_status_values_valid():
    """Status MUST be one of {✓ shipped, partial, TODO}."""
    mod = _load_module(COVERAGE, "coverage_map_lint")
    valid = {"✓ shipped", "partial", "TODO"}
    for axis in mod.DEFAULT_AXES:
        s = axis.get("status")
        assert s in valid, (
            f"axis {axis.get('id', '?')} has invalid status: {s!r}"
        )


def test_tetragon_allowlist_bidirectional_consistency():
    """The 4-binary Tetragon allowlist (R362 doctrine) must appear in
    BOTH C-14 concept text AND tetragon-policy-load.sh script."""
    mod = _load_module(ARCH_QA, "architecture_qa_for_tetragon_lint")
    c14 = next((c for c in mod.ARCHITECTURE_CONCEPTS
                 if c.get("id") == "C-14"), None)
    assert c14 is not None, "C-14 (Tetragon TracingPolicy) missing"

    allowlist = [
        "/usr/bin/python3",
        "/usr/bin/nvidia-smi",
        "/usr/local/bin/vllm",
        "/usr/bin/podman",
    ]
    for binary in allowlist:
        assert binary in c14["explanation"], (
            f"C-14 concept text missing operator-verbatim allowlist binary: "
            f"{binary}"
        )

    if TETRAGON_SCRIPT.is_file():
        script_body = TETRAGON_SCRIPT.read_text(encoding="utf-8")
        for binary in allowlist:
            assert binary in script_body, (
                f"tetragon-policy-load.sh missing allowlist binary {binary} "
                "— BIDIRECTIONAL consistency violation (R362 contract): "
                "C-14 concept text and shipped policy script must agree on "
                "the 4-binary allowlist"
            )


def test_architecture_qa_concept_ids_monotonic():
    """C-NN IDs should be monotonically numbered (gaps allowed for
    operator-overlay slots but no duplicates)."""
    mod = _load_module(ARCH_QA, "architecture_qa_monotonic_lint")
    ids = [c.get("id") for c in mod.ARCHITECTURE_CONCEPTS]
    # No duplicates
    assert len(ids) == len(set(ids)), (
        f"duplicate concept IDs: {[i for i in ids if ids.count(i) > 1]}"
    )
    # All match C-NN pattern
    pattern = re.compile(r"^C-\d{2,}$")
    for i in ids:
        assert pattern.match(i or ""), f"non-conforming concept ID: {i!r}"


def test_coverage_map_axis_ids_monotonic():
    """A-NN IDs no duplicates + match pattern."""
    mod = _load_module(COVERAGE, "coverage_map_monotonic_lint")
    ids = [a.get("id") for a in mod.DEFAULT_AXES]
    assert len(ids) == len(set(ids)), (
        f"duplicate axis IDs: {[i for i in ids if ids.count(i) > 1]}"
    )
    pattern = re.compile(r"^A-\d{2,}$")
    for i in ids:
        assert pattern.match(i or ""), f"non-conforming axis ID: {i!r}"
