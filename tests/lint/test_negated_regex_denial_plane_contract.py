"""SDD-506 — the negated-regex denial plane contract.

SDD-504 added a negative *literal-substring* plane; SDD-506 adds a negative
*regex* plane: the output must never MATCH a forbidden pattern anywhere. The one
genuinely-new engine primitive is an UNANCHORED NFA search (the anchored is_match
can't answer "matches any substring"). This lint pins:

  * the unanchored search mode on sovereign-regex-nfa (start_unanchored /
    step_unanchored / matches_anywhere) — the anchored is_match stays too;
  * the negative-regex constraint (RegexDenyConstraint) lives beside the positive
    RegexConstraint in sovereign-regex-constrain (no new crate) and emits the
    allow-list shape (safe_token_ids) a token-law plane consumes, over the real
    unanchored NFA;
  * the unified engine (SDD-505) gained a regex_denylist plane;
  * SDD-506 documents the unanchored crux + the honest empty-match caveat.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NFA = REPO / "crates" / "sovereign-regex-nfa" / "src" / "lib.rs"
CONSTRAIN = REPO / "crates" / "sovereign-regex-constrain" / "src" / "lib.rs"
LLM = REPO / "crates" / "sovereign-llm" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "506-negated-regex-denial-plane.md"


def test_nfa_has_unanchored_search():
    src = NFA.read_text(encoding="utf-8")
    assert "pub fn start_unanchored" in src
    assert "pub fn step_unanchored" in src
    assert "pub fn matches_anywhere" in src
    # the anchored whole-string match is preserved (still the default question)
    assert "pub fn is_match" in src


def test_negative_regex_constraint_over_the_unanchored_nfa():
    src = CONSTRAIN.read_text(encoding="utf-8")
    assert "pub struct RegexDenyConstraint" in src
    assert "pub fn safe_token_ids" in src, "the allow-list shape the plane consumes"
    # it must drive the UNANCHORED NFA, not reimplement matching
    assert "step_unanchored" in src
    assert "is_accepting" in src
    # and it lives beside the positive constraint (no new crate)
    assert "pub struct RegexConstraint" in src
    assert "#![forbid(unsafe_code)]" in src


def test_unified_engine_gained_the_regex_denylist_plane():
    src = LLM.read_text(encoding="utf-8")
    assert "pub regex_denylist:" in src, "TokenLawSpec must carry the negative-regex plane"
    assert "RegexDenyConstraint" in src, "the engine composes it"
    # is_empty must account for the new plane
    assert "regex_denylist.is_empty()" in src


def test_sdd_506_documents_the_unanchored_crux_and_caveat():
    assert SDD.is_file(), "SDD-506 must exist"
    doc = SDD.read_text(encoding="utf-8").lower()
    assert "unanchored" in doc
    assert "match" in doc and "anywhere" in doc
    # the honest empty-match caveat (a pattern matching empty forbids everything)
    assert "empty string" in doc
    # ties back to the future it closes
    assert "sdd-504" in doc
