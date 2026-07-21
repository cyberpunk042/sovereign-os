"""SDD-502 — incremental Earley parser contract.

SDD-500/501 both flagged the honest-perf caveat: the grammar mask re-parsed the
whole prefix every token. SDD-502 closes it with an incremental Earley chart —
the committed prefix is parsed once and each candidate token is validated by a
feed-then-rollback, bit-for-bit identical to the from-scratch recognizer. This
lint pins:

  * the incremental substrate exists in sovereign-cfg-grammar (EarleyChart +
    start_chart / feed / rollback_to) and stays unsafe-free;
  * the from-scratch oracle (allowed_next / is_live_prefix) is PRESERVED — it is
    what the incremental path is tested against, not replaced;
  * TokenGrammarMask::mask is rewired to the incremental path (start_chart /
    rollback) and no longer does a per-token is_live_prefix full re-parse;
  * the stateful IncrementalGrammarMask exists AND its char-concatenative
    boundary is documented, so no caller wires it into a merge-BPE loop blindly;
  * SDD-502 documents the exact-parity + char-concatenative honesty.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CFG = REPO / "crates" / "sovereign-cfg-grammar" / "src" / "lib.rs"
MASK = REPO / "crates" / "sovereign-token-grammar-mask" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "502-incremental-grammar-parser.md"


def test_cfg_grammar_has_the_incremental_substrate():
    src = CFG.read_text(encoding="utf-8")
    assert "pub struct EarleyChart" in src
    assert "pub fn start_chart" in src
    assert "pub fn feed" in src
    assert "pub fn rollback_to" in src
    assert "pub fn next_set" in src
    # complexity win, not an unsafe micro-opt
    assert "#![forbid(unsafe_code)]" in src


def test_from_scratch_oracle_is_preserved():
    """The incremental path's parity oracle must still exist — removing it would
    delete the very thing that proves the rewrite is exact."""
    src = CFG.read_text(encoding="utf-8")
    assert "pub fn allowed_next" in src
    assert "pub fn is_live_prefix" in src
    assert "fn parse_chart" in src, "the from-scratch chart builder stays the oracle"


def test_mask_is_rewired_to_the_incremental_path():
    src = MASK.read_text(encoding="utf-8")
    # mask() now parses once into a chart and validates by feed+rollback
    assert "start_chart" in src
    assert "rollback_to" in src
    assert "token_keeps_live" in src, "the feed-based per-token validator"
    # the production path must NOT re-parse per token via the old
    # `self.grammar.is_live_prefix(prefix + token)` concatenation (the quadratic
    # path the incremental rewrite removes). Tests may still use a local
    # `g.is_live_prefix` as the brute-force parity oracle — that is expected.
    assert "self.grammar.is_live_prefix" not in src, (
        "mask() must not re-parse prefix+token per token — that is the cost "
        "the incremental path removes"
    )


def test_stateful_masker_documents_its_char_concatenative_boundary():
    src = MASK.read_text(encoding="utf-8")
    assert "pub struct IncrementalGrammarMask" in src
    assert "pub fn advance" in src
    low = src.lower()
    # the honest boundary: only safe for char-concatenative tokenizers
    assert "char-concatenative" in low or "concatenative" in low
    assert "byte-level bpe" in low or "byte-bpe" in low or "byte-level" in low


def test_sdd_502_documents_parity_and_the_boundary():
    assert SDD.is_file(), "SDD-502 must exist"
    doc = SDD.read_text(encoding="utf-8").lower()
    assert "incremental" in doc
    # exact-parity is the acceptance claim
    assert "bit-for-bit" in doc or "identical" in doc
    assert "parity" in doc
    # the honest char-concatenative caveat for the stateful path
    assert "concatenative" in doc
    # ties back to the caveat it closes
    assert "sdd-501" in doc
