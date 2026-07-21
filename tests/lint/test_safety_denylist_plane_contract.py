"""SDD-504 — safety denylist negative-plane contract.

SDD-503 deferred the safety source because a substring ban is not a per-token
property. SDD-504 realizes it: an incremental Aho-Corasick walk that bans exactly
the tokens which would COMPLETE a banned match, exposed as a token-law plane. This
lint pins:

  * the automaton exposes an incremental scan-state API (start/advance/hits) — the
    seam that lets a decode loop probe a candidate from a committed state;
  * the negative-plane crate exists, is unsafe-free, and emits the allow-list
    shape (safe_token_ids) the token-law planes consume — over the REAL automaton;
  * sovereign-llm wires both the pure denylist and the positive∧negative
    (regex ∧ denylist) composition;
  * SDD-504 documents the HONEST boundary — entropy/checksum detectors
    (secret-scan, pii-redact) are NOT per-token and stay post-hoc scanners, not
    planes — so no future reader wires an entropy scanner in as a plane.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AC = REPO / "crates" / "sovereign-aho-corasick" / "src" / "lib.rs"
DENY = REPO / "crates" / "sovereign-token-law-deny" / "src" / "lib.rs"
DENY_CARGO = REPO / "crates" / "sovereign-token-law-deny" / "Cargo.toml"
LLM = REPO / "crates" / "sovereign-llm" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "504-safety-denylist-negative-plane.md"


def test_aho_corasick_exposes_incremental_scan_state():
    src = AC.read_text(encoding="utf-8")
    assert "pub struct AcState" in src
    assert "pub fn start(" in src
    assert "pub fn advance(" in src
    assert "pub fn hits(" in src


def test_negative_plane_crate_over_the_real_automaton():
    src = DENY.read_text(encoding="utf-8")
    assert "pub struct DenyConstraint" in src
    assert "pub fn safe_token_ids" in src, "the allow-list shape the planes consume"
    # it must drive the REAL automaton incrementally, not reimplement matching
    assert "AhoCorasick" in src
    assert "advance" in src and "hits" in src
    assert "#![forbid(unsafe_code)]" in src
    # and actually depend on the aho-corasick crate
    cargo = tomllib.loads(DENY_CARGO.read_text(encoding="utf-8"))
    deps = cargo.get("dependencies", {})
    assert "sovereign-aho-corasick" in deps, "the negative plane composes the real automaton"


def test_llm_wires_pure_and_composed_denylist():
    src = LLM.read_text(encoding="utf-8")
    assert "pub fn complete_with_safety_denylist" in src, "the pure negative plane"
    assert "pub fn complete_regex_with_safety_denylist" in src, "positive ∧ negative"
    assert "safe_token_ids" in src, "the safe allow-list drives the mask"
    # the composed method intersects the regex (positive) and denylist (negative)
    assert "combine_with_dynamics" in src


def test_sdd_504_documents_the_structural_detectors_boundary():
    assert SDD.is_file(), "SDD-504 must exist"
    doc = SDD.read_text(encoding="utf-8").lower()
    # the genuinely-new framing
    assert "negative" in doc and "per-token" in doc
    assert "span token boundaries" in doc or "span" in doc
    # the honest boundary: entropy/checksum detectors are not planes
    assert "entropy" in doc
    assert "post-hoc scanner" in doc or "not a plane" in doc or "not planes" in doc
    assert "secret-scan" in doc and "pii-redact" in doc
    # ties back to the deferral it closes
    assert "sdd-503" in doc
