"""SDD-514 — the incremental token-law fusion contract (M00155 DEEPEN).

`CompiledFuse::fused_mask(generated)` is stateless — each decode step re-walks
every plane from the start of the whole prefix, so a decode is O(n²). This lint
pins the incremental `FuseSession` that carries per-plane committed state and
advances by only the newly-committed token (O(n)), non-breaking, behind a proven
parity invariant:

  * a `FuseSession` + `CompiledFuse::session()`, with `fused_mask` untouched and a
    shared `compose()` so stateless and incremental produce bit-identical masks;
  * the plane primitives (`*_state`/`*_from`) on deny + regex, with the existing
    stateless methods DELEGATING through them (parity kept);
  * both decode-loop consumers migrated (gatewayd `FuseStepper`, llm session);
  * a parity test that walks all planes + off-pattern + eos.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FUSE = REPO / "crates" / "sovereign-token-law-fuse" / "src" / "lib.rs"
DENY = REPO / "crates" / "sovereign-token-law-deny" / "src" / "lib.rs"
REGEX = REPO / "crates" / "sovereign-regex-constrain" / "src" / "lib.rs"
GW = REPO / "crates" / "sovereign-gatewayd" / "src" / "lib.rs"
LLM = REPO / "crates" / "sovereign-llm" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "514-token-law-incremental-fusion.md"


def test_fuse_session_exists_and_shares_the_compose_tail():
    src = FUSE.read_text(encoding="utf-8")
    assert "pub struct FuseSession" in src
    assert "pub fn session(&self) -> FuseSession" in src
    assert "pub fn advance_token(&mut self, id: usize) -> FusedMask" in src
    assert "pub fn advance_str(&mut self, delta: &str) -> FusedMask" in src
    # A shared composition tail so stateless fused_mask and the session are
    # bit-for-bit identical (the parity invariant).
    assert "fn compose(" in src
    assert "self.compose(" in src, "fused_mask must route through the shared compose()"
    # fused_mask is preserved (non-breaking).
    assert "pub fn fused_mask(&self, generated: &str) -> FusedMask" in src
    # The load-bearing parity test.
    assert "session_is_bit_for_bit_identical_to_stateless_across_all_planes" in src
    assert "session_matches_stateless_off_pattern_and_at_eos" in src


def test_deny_plane_exposes_incremental_primitives_and_delegates():
    src = DENY.read_text(encoding="utf-8")
    assert "pub use sovereign_aho_corasick::AcState;" in src
    for m in ("pub fn start_state(&self) -> AcState",
              "pub fn advance_state(&self",
              "pub fn safe_token_ids_from(&self"):
        assert m in src, f"deny plane missing {m!r}"
    # The stateless method delegates through the primitives (single source, parity).
    assert "self.safe_token_ids_from(base, vocab)" in src


def test_regex_plane_exposes_incremental_primitives_and_delegates():
    src = REGEX.read_text(encoding="utf-8")
    # positive regex: advance returns Option (None = off-pattern, sticky dead).
    assert "pub fn advance_state(&self, base: &BTreeSet<usize>, text: &str) -> Option<BTreeSet<usize>>" in src
    assert "pub fn allowed_token_ids_from(&self" in src
    # negated regex: unanchored, never dead.
    assert "pub fn safe_token_ids_from(&self" in src
    # delegation (parity).
    assert "self.allowed_token_ids_from(&base, vocab)" in src
    assert "self.safe_token_ids_from(&base, vocab)" in src


def test_consumers_migrated_to_the_incremental_session():
    gw = GW.read_text(encoding="utf-8")
    assert "struct FuseStepper" in gw
    assert "FuseStepper::new(cf)" in gw
    assert "stepper.next(g)" in gw
    # the old stateless whole-prefix step is gone.
    assert "fn token_law_step(" not in gw, "the O(n²) token_law_step must be replaced"
    llm = LLM.read_text(encoding="utf-8")
    assert "let mut session = compiled.session();" in llm
    assert "session.advance_token(id)" in llm


def test_sdd_514_documents_the_parity_invariant():
    assert SDD.is_file(), "SDD-514 must exist"
    text = SDD.read_text(encoding="utf-8")
    assert text.startswith("# SDD-514 —"), "H1 must be the canonical SDD-514 heading"
    low = text.lower()
    assert "parity" in low, "the parity invariant must be documented"
    assert "bit-for-bit" in low
    assert "o(n" in low, "the complexity claim must be stated"
    assert "deepen" in low
