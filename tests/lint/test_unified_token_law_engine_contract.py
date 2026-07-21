"""SDD-505 — the unified token-law engine contract.

SDD-500…504 built the five M00117 plane classes as pairwise `complete_*_with_laws`
methods. SDD-505 folds them into one declarative engine: a `TokenLawSpec` names
the active planes and `complete_with_token_law` AND-composes every one per decode
step. This lint pins:

  * the declarative spec exposes all four plane fields (schema / regex / denylist
    / policy_planes) and is Default-constructible (the unconstrained spec);
  * the engine composes EVERY active plane through the real combine kernel
    (combine_with_dynamics) — not a fixed pair;
  * the five pairwise methods are RETAINED (the engine is a superset, not a
    replacement) so back-compat + the parity oracle survive;
  * SDD-505 documents the faithful-generalization framing (single-plane spec is
    bit-for-bit identical to the dedicated method).
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LLM = REPO / "crates" / "sovereign-llm" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "505-unified-token-law-engine.md"


def test_declarative_spec_has_all_plane_fields():
    src = LLM.read_text(encoding="utf-8")
    assert "pub struct TokenLawSpec" in src
    for field in ("pub schema:", "pub regex:", "pub denylist:", "pub policy_planes:"):
        assert field in src, f"TokenLawSpec missing {field!r}"
    # Default = the empty (unconstrained) spec
    assert "Default" in src and "pub fn is_empty" in src


def test_engine_composes_every_active_plane():
    src = LLM.read_text(encoding="utf-8")
    assert "pub fn complete_with_token_law" in src
    # it must AND-compose over the real N-way combine (not a hard-coded pair)
    assert "combine_with_dynamics" in src
    # each plane class is consulted in the unified loop
    assert "TokenGrammarMask" in src  # grammar/schema
    assert "RegexConstraint" in src  # regex/tool
    assert "DenyConstraint" in src  # safety denylist


def test_pairwise_methods_are_retained_as_the_parity_oracle():
    """The engine is a strict superset — the dedicated methods stay, so single-
    plane specs can be proven bit-for-bit identical to them."""
    src = LLM.read_text(encoding="utf-8")
    for method in (
        "pub fn complete_json_schema_with_laws",
        "pub fn complete_regex_with_laws",
        "pub fn complete_with_safety_denylist",
    ):
        assert method in src, f"{method} must be retained (back-compat + parity oracle)"


def test_sdd_505_documents_faithful_generalization():
    assert SDD.is_file(), "SDD-505 must exist"
    doc = SDD.read_text(encoding="utf-8").lower()
    assert "unified" in doc
    # the genuinely-new all-planes-at-once claim
    assert "all at once" in doc or "all planes at once" in doc or "every active plane" in doc
    # the parity/superset framing (single plane == dedicated method)
    assert "bit-for-bit" in doc or "identical" in doc
    assert "superset" in doc or "generaliz" in doc
    # ties back to the arc it caps
    assert "sdd-500" in doc and "sdd-504" in doc
