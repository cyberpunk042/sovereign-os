"""SDD-503 — real constraint-source planes contract.

SDD-501 made policy planes compose, but they were hand-built caller-supplied
bitsets. SDD-503 derives planes from REAL constraint sources and composes several
at once: grammar ∧ regex ∧ policy, AND-combined through the real token_law_combine
kernel. This lint pins:

  * the multi-dynamic primitive (combine_with_dynamics) exists and goes through
    the real kernel — not a hand-rolled AND — and combine_with delegates to it;
  * regex is wired as a real composable source (complete_regex_with_laws) and the
    two-dynamic-source method (grammar ∧ regex ∧ policy) exists;
  * the HONEST boundary is documented in SDD-503: the safety scanners are NOT
    shipped as planes (a substring ban is not a per-token property), so no future
    reader wires a text-scanner in as a token-law plane.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TLM = REPO / "crates" / "sovereign-token-law-mask" / "src" / "lib.rs"
LLM = REPO / "crates" / "sovereign-llm" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "503-real-constraint-source-planes.md"


def test_multi_dynamic_primitive_over_the_real_kernel():
    src = TLM.read_text(encoding="utf-8")
    assert "pub fn combine_with_dynamics" in src, "the N-dynamic-source composer"
    # it must go through the REAL M00117 kernel, not a hand-rolled intersection
    assert "token_law_combine" in src
    assert "LawCombine::And" in src
    # combine_with (SDD-501) is preserved as the single-source case
    assert "pub fn combine_with" in src
    assert "self.combine_with_dynamics(&[dynamic_allow_ids])" in src, (
        "combine_with must delegate to combine_with_dynamics so SDD-501 stays exact"
    )
    assert "#![forbid(unsafe_code)]" in src


def test_regex_is_a_real_composable_source():
    src = LLM.read_text(encoding="utf-8")
    # regex plane ∧ policy — regex as a real source (SDD-500 Q4 / SDD-501 non-goal)
    assert "pub fn complete_regex_with_laws" in src
    assert "allowed_token_ids" in src, "the regex source's plane shape"
    # two dynamic sources at once — grammar ∧ regex ∧ policy
    assert "pub fn complete_json_schema_and_regex_with_laws" in src
    assert "combine_with_dynamics" in src, "the multi-source composition is used"


def test_sdd_503_documents_the_safety_not_a_plane_boundary():
    assert SDD.is_file(), "SDD-503 must exist"
    doc = SDD.read_text(encoding="utf-8").lower()
    # the genuinely-new capability
    assert "grammar ∧ regex ∧ policy" in doc or "grammar ∧ regex" in doc
    # the honest boundary: safety scanners are substring, not per-token → not a plane
    assert "substring" in doc
    assert "secret-scan" in doc or "safety scanner" in doc or "safety scanners" in doc
    assert "text→token" in doc or "text-scanner" in doc or "not shipped as a plane" in doc or "not a per-token" in doc
    # ties back to the tracked step it closes
    assert "sdd-501" in doc
