"""SDD-500 — token-law-mask contract: the M002 bit-machine's first real
per-token call site, and its honest scope boundary.

The `sovereign-token-law-mask` crate turns the M00117 `token_law_combine`
allow-mask into a decode-time logit mask, wired into `sovereign-decoder-stack`
so a packed token-law bitset actually constrains generation. This lint pins:

  * the crate exists, is a LogitProcessor, and ties to the real simd kernel;
  * decoder-stack carries + applies the token-law mask per token;
  * the HONEST SCOPE is documented in the crate itself — it constrains the
    in-repo decode stack, NOT the external-proxy /v1/messages path (which
    exposes no logits) — so no future reader over-claims coverage (the
    SDD-500 §Non-goals contract).
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRATE = REPO / "crates" / "sovereign-token-law-mask"
LIB = CRATE / "src" / "lib.rs"
CARGO = CRATE / "Cargo.toml"
STACK = REPO / "crates" / "sovereign-decoder-stack" / "src" / "lib.rs"
STACK_CARGO = REPO / "crates" / "sovereign-decoder-stack" / "Cargo.toml"
SDD = REPO / "docs" / "sdd" / "500-per-token-token-law-bitset.md"


def test_crate_exists_and_ties_to_the_real_kernel():
    assert LIB.is_file(), f"missing {LIB}"
    src = LIB.read_text(encoding="utf-8")
    # the real M00117 kernel + the pipeline trait — not a reimplementation
    assert "token_law_combine" in src, "must use the real simd token_law_combine kernel"
    assert "impl LogitProcessor for TokenLawMask" in src
    assert "pub fn mask_logits" in src and "NEG_INFINITY" in src
    assert "#![forbid(unsafe_code)]" in src


def test_decoder_stack_applies_the_token_law_per_token():
    stack = STACK.read_text(encoding="utf-8")
    assert "pub token_law: Option<Vec<u64>>" in stack, "GenOptions must carry the token-law mask"
    assert "sovereign_token_law_mask::mask_logits(allow, &mut l)" in stack, (
        "generate_with must apply the token-law mask each step"
    )
    assert "with_token_law" in stack
    assert "sovereign-token-law-mask" in STACK_CARGO.read_text(encoding="utf-8")


def test_honest_scope_is_documented_in_the_crate():
    """The external-proxy path is out of scope (no logit access) — this MUST be
    stated in the crate doc so the coverage claim can never be over-read."""
    src = LIB.read_text(encoding="utf-8").lower()
    assert "honest scope" in src
    assert "external-proxy" in src or "external proxy" in src
    assert "in-repo" in src
    # names the reason it can't cover the proxy path
    assert "no logits" in src or "exposes no logits" in src or "out-of-process" in src


def test_sdd_500_reference_present():
    src = LIB.read_text(encoding="utf-8")
    assert "SDD-500" in src, "the crate should cite its design (SDD-500)"
    assert SDD.is_file(), "SDD-500 must exist"
