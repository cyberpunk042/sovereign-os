"""SDD-501 — multi-plane token-law composition contract.

SDD-500 gave the M002 bit-machine one per-token call site (mask logits with one
caller-supplied bitset). SDD-501 realizes M00117 *composition*: several
independent token-law planes (grammar / schema / tool / safety / route)
AND-combined per step through the real `token_law_combine` kernel, so one running
model is confined by all of them at once. This lint pins:

  * the packer + the plane set live in `sovereign-token-law-mask` (no new crate)
    and combine via the REAL simd kernel — not a reimplementation;
  * the decoder-stack carries the M002-native dynamic loop
    (`generate_dynamic_token_law_until`) that applies a packed `Vec<u64>` mask;
  * `sovereign-llm` composes the grammar plane (`TokenGrammarMask`) with caller
    policy planes (`TokenLawPlanes`) in one production method;
  * the HONEST caveats stay documented in SDD-501 — the external-proxy path is
    still out of scope (inherited from SDD-500) and the perf boundary (the
    grammar mask re-parses per step) is stated, so no reader over-claims speed
    or coverage.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TLM = REPO / "crates" / "sovereign-token-law-mask" / "src" / "lib.rs"
STACK = REPO / "crates" / "sovereign-decoder-stack" / "src" / "lib.rs"
LLM = REPO / "crates" / "sovereign-llm" / "src" / "lib.rs"
LLM_CARGO = REPO / "crates" / "sovereign-llm" / "Cargo.toml"
SDD = REPO / "docs" / "sdd" / "501-multi-plane-token-law-composition.md"
INVENTORY = REPO / "crates" / "sovereign-token-law-mask" / "Cargo.toml"


def test_packer_and_planes_compose_over_the_real_kernel():
    src = TLM.read_text(encoding="utf-8")
    assert "pub fn pack_allowed" in src, "the ids->bitset packer must exist"
    assert "pub struct TokenLawPlanes" in src
    assert "pub fn combine_with" in src, "grammar plane ∧ static planes"
    assert "pub fn combine_static" in src
    # the composition must go through the REAL M00117 kernel, not a hand-rolled AND
    assert "token_law_combine" in src
    assert "LawCombine::And" in src
    assert "#![forbid(unsafe_code)]" in src


def test_no_new_crate_composition_lives_beside_the_sdd_500_mask():
    """SDD-501 adds NO crate — the packer + planes are in the SDD-500 crate,
    which stays a plain library that ties to the simd kernel."""
    assert TLM.is_file()
    cargo = INVENTORY.read_text(encoding="utf-8")
    assert 'name = "sovereign-token-law-mask"' in cargo


def test_decoder_stack_has_the_m002_native_dynamic_loop():
    stack = STACK.read_text(encoding="utf-8")
    assert "pub fn generate_dynamic_token_law_until" in stack
    # the loop applies the packed Vec<u64> mask (the SDD-500 -inf mask), staying
    # in the bit domain — no round-trip back to a LogitMask/HashSet
    assert "sovereign_token_law_mask::mask_logits(&allow, &mut logits)" in stack


def test_llm_composes_grammar_with_policy_planes():
    llm = LLM.read_text(encoding="utf-8")
    assert "pub fn complete_json_schema_with_laws" in llm
    assert "TokenGrammarMask" in llm, "the grammar plane"
    assert "TokenLawPlanes" in llm, "the policy planes"
    assert "combine_with" in llm, "grammar ∧ policy per step"
    assert "generate_dynamic_token_law_until" in llm, "drives the M002 loop"
    assert "sovereign-token-law-mask" in LLM_CARGO.read_text(encoding="utf-8")


def test_sdd_501_documents_the_honest_boundaries():
    assert SDD.is_file(), "SDD-501 must exist"
    doc = SDD.read_text(encoding="utf-8").lower()
    # scope honesty (inherited from SDD-500): in-repo, not the external proxy
    assert "in-repo" in doc
    assert "external-proxy" in doc or "external proxy" in doc
    assert "no logit" in doc or "out-of-process" in doc
    # perf honesty: the grammar mask re-parses each step — not an accelerated path
    assert "re-parse" in doc
    assert "correctness" in doc
    # ties back to SDD-500
    assert "sdd-500" in doc


def test_crate_source_cites_sdd_501():
    """The composition primitives should cite their design so a reader lands on
    the honesty caveats."""
    assert "SDD-501" in TLM.read_text(encoding="utf-8")
