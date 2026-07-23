"""SDD-516 — the PII-completion token-law plane contract (M00155 DEEPEN).

SDD-513's entropy plane is an explicitly HEURISTIC statistical threshold; its own
scope note named the exact-shape v2: a well-defined-completion PII projection.
This lint pins that seventh plane — a new `sovereign-token-law-pii` crate that
bans the token which *completes* a `sovereign-pii-redact` detection, wired
first-class through the fuse engine + the llm/gatewayd serving boundaries:

  * the crate reuses `sovereign-pii-redact::detect` wholesale (one definition),
    is windowed, and a disabled constraint is an all-safe identity;
  * the fuse engine gains `pii` as a DISTINCT MaskLayerSet name (not folded into
    the `safety` alias) with a FuseSession `pii_tail` for the incremental path;
  * llm `TokenLawSpec.pii` + gatewayd `ServingTokenLaw.pii` + `layers_active`;
  * SDD-516 documents the well-defined-completion framing + the windowed parity.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PII = REPO / "crates" / "sovereign-token-law-pii" / "src" / "lib.rs"
PII_TOML = REPO / "crates" / "sovereign-token-law-pii" / "Cargo.toml"
FUSE = REPO / "crates" / "sovereign-token-law-fuse" / "src" / "lib.rs"
LLM = REPO / "crates" / "sovereign-llm" / "src" / "lib.rs"
GW = REPO / "crates" / "sovereign-gatewayd" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "516-token-law-pii-plane.md"


def test_pii_crate_reuses_the_redactor_and_is_a_windowed_identity_when_off():
    src = PII.read_text(encoding="utf-8")
    assert "pub struct PiiConstraint" in src
    assert "pub fn safe_token_ids(&self, generated: &str, vocab: &[&str]) -> Vec<usize>" in src
    # Reuses the post-hoc redactor's detector wholesale — one definition.
    assert "use sovereign_pii_redact::detect;" in src
    assert "detect(&candidate)" in src
    # Disabled (window 0) is an all-safe identity; the completion test.
    assert "if self.window == 0" in src
    assert "d.end > base_len" in src, "ban iff the candidate CLOSES a detection"
    deps = PII_TOML.read_text(encoding="utf-8").split("[dependencies]", 1)[1]
    assert 'path = "../sovereign-pii-redact"' in deps


def test_fuse_engine_wires_pii_as_a_distinct_seventh_plane():
    src = FUSE.read_text(encoding="utf-8")
    assert "use sovereign_token_law_pii::PiiConstraint;" in src
    # MaskLayerSet gains a distinct `pii` bool, NOT folded into `safety`.
    assert "pub pii: bool" in src
    assert '"pii" => self.pii = true,' in src
    # FuseLayers / CompiledFuse / FuseRequest carry the plane + wire type + session tail.
    assert "pub pii: Option<PiiConstraint>" in src
    assert "pub struct PiiRequest" in src
    assert "pii_tail: String" in src
    # Fused into the mask under the "pii" layer name + the parity test.
    assert '"pii"' in src
    assert "pii_session_is_bit_for_bit_identical_to_stateless" in src


def test_llm_and_gatewayd_expose_the_pii_plane():
    llm = LLM.read_text(encoding="utf-8")
    assert "pub pii: Option<sovereign_token_law_pii::PiiConstraint>" in llm
    assert "pii: spec.pii" in llm
    gw = GW.read_text(encoding="utf-8")
    assert "pub pii: Option<sovereign_token_law_fuse::PiiRequest>" in gw
    assert "PiiRequest::to_constraint" in gw


def test_sdd_516_documents_the_well_defined_completion_framing():
    assert SDD.is_file(), "SDD-516 must exist"
    text = SDD.read_text(encoding="utf-8")
    assert text.startswith("# SDD-516 —"), "H1 must be the canonical SDD-516 heading"
    low = text.lower()
    assert "well-defined" in low, "the well-defined-completion distinction must be documented"
    assert "bit-for-bit" in low, "the windowed parity claim must be stated"
    assert "opt-in" in low and "backstop" in low, "the honesty framing must be documented"
    assert "deepen" in low
