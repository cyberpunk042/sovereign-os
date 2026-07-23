"""SDD-513 — the entropy token-law plane contract (M00155 DEEPEN).

The M00117 planes turn STRUCTURAL text constraints into per-token allow-lists
(grammar/regex keep a pattern reachable; the deny plane bans the token that
COMPLETES a substring — exact per-step guarantees). Secret leakage is
STATISTICAL (a high-entropy run, not a fixed substring), so the deny plane's own
scope note defers it to a post-hoc scanner. This lint pins the entropy plane that
projects that detector to the token level as an explicitly HEURISTIC plane:

  * a new crate mirroring the deny plane's `safe_token_ids` shape, sharing the
    secret-scanner's exact `shannon_entropy` definition + thresholds;
  * a SIXTH engine plane wired through fuse/llm/gatewayd, with a DISTINCT layer
    name that is NOT folded into the `safety` alias;
  * the honesty framing: heuristic + monotone/windowed + a complement to (never a
    replacement for) the exact post-hoc scan.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRATE = REPO / "crates" / "sovereign-token-law-entropy" / "src" / "lib.rs"
CRATE_TOML = REPO / "crates" / "sovereign-token-law-entropy" / "Cargo.toml"
SECRET = REPO / "crates" / "sovereign-secret-scan" / "src" / "lib.rs"
FUSE = REPO / "crates" / "sovereign-token-law-fuse" / "src" / "lib.rs"
LLM = REPO / "crates" / "sovereign-llm" / "src" / "lib.rs"
GW_LIB = REPO / "crates" / "sovereign-gatewayd" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "513-token-law-entropy-plane.md"


def test_entropy_crate_mirrors_the_deny_plane_shape():
    src = CRATE.read_text(encoding="utf-8")
    assert "pub struct EntropyConstraint" in src
    # The allow-list shape every token-law plane consumes.
    assert "pub fn safe_token_ids(&self, generated: &str, vocab: &[&str]) -> Vec<usize>" in src
    assert "#![forbid(unsafe_code)]" in src
    # A disabled constraint must be an all-safe identity (clean no-op composition).
    assert "return (0..vocab.len()).collect()" in src
    # It shares the scanner's exact definition, not a private re-implementation.
    assert "sovereign_secret_scan" in src
    assert "shannon_entropy" in src


def test_entropy_crate_deps_the_secret_scanner_only():
    deps = CRATE_TOML.read_text(encoding="utf-8").split("[dependencies]", 1)[1]
    assert 'path = "../sovereign-secret-scan"' in deps
    # A light plane crate — no transformer / decode stack.
    assert "sovereign-decoder-stack" not in deps
    assert "sovereign-llm" not in deps


def test_secret_scanner_shares_one_entropy_definition():
    # `shannon_entropy` is public so the plane and the post-hoc scan agree.
    assert "pub fn shannon_entropy" in SECRET.read_text(encoding="utf-8")


def test_fuse_engine_gains_a_sixth_plane_with_a_distinct_name():
    src = FUSE.read_text(encoding="utf-8")
    assert "use sovereign_token_law_entropy::EntropyConstraint;" in src
    # The layer bit + the request wire field + the fused_mask block.
    assert "pub entropy: bool" in src
    assert "pub entropy: Option<EntropyConstraint>" in src
    assert "pub struct EntropyRequest" in src
    assert 'layer: "entropy"' in src
    # DISTINCT name: `entropy` is its own token, NOT added to the `safety` alias
    # (which must stay exactly denylist+regex_denylist).
    assert '"entropy" => self.entropy = true' in src
    safety_arm = src.split('"safety" =>', 1)[1].split("}", 1)[0]
    assert "entropy" not in safety_arm, "entropy must NOT be folded into the safety alias"


def test_plane_is_first_class_in_llm_and_gatewayd():
    llm = LLM.read_text(encoding="utf-8")
    assert "pub entropy: Option<sovereign_token_law_entropy::EntropyConstraint>" in llm
    assert "entropy: spec.entropy" in llm, "complete_with_token_law must pass the plane through"
    gw = GW_LIB.read_text(encoding="utf-8")
    assert "pub entropy: Option<sovereign_token_law_fuse::EntropyRequest>" in gw


def test_sdd_513_documents_the_heuristic_honesty_framing():
    assert SDD.is_file(), "SDD-513 must exist"
    text = SDD.read_text(encoding="utf-8")
    assert text.startswith("# SDD-513 —"), "H1 must be the canonical SDD-513 heading"
    low = text.lower()
    assert "heuristic" in low, "the plane's heuristic nature must be documented, not hidden"
    assert "post-hoc" in low and "complement" in low, "it complements, not replaces, the scan"
    assert "shannon" in low or "entropy" in low
    assert "deepen" in low
