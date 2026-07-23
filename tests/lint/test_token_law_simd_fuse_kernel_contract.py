"""SDD-515 — the SIMD fused-mask AND-kernel contract (M00155 DEEPEN).

`token_law_combine` fuses each token-law plane's per-step allow-bitset into one
mask (`And` = a token survives only if every plane allows it). SDD-513/514 both
deferred it as "the SIMD-of-the-AND"; SDD-514 removed the O(n²) whole-prefix
re-walk, leaving the per-step fusion itself. This lint pins the real AVX-512F
kernel (`_mm512_and_si512` / `_mm512_or_si512`, 8×u64 = 512 allow-bits per
instruction), non-breaking, behind the crate's standard parity discipline:

  * a runtime `has_avx512f()` dispatch (identical to the crate's other kernels);
  * `token_law_combine_scalar` extracted as the bit-for-bit source of truth;
  * `token_law_combine_avx512` (`#[target_feature(enable = "avx512f")]`);
  * a parity test proving avx == scalar across widths / ragged tails / ragged
    law widths, for And and Or.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHEATS = REPO / "crates" / "sovereign-simd" / "src" / "cheats.rs"
SDD = REPO / "docs" / "sdd" / "515-token-law-simd-fuse-kernel.md"


def test_token_law_combine_dispatches_to_avx512_behind_the_runtime_gate():
    src = CHEATS.read_text(encoding="utf-8")
    # The public entry keeps its signature and dispatches only behind the gate.
    assert "pub fn token_law_combine(laws: &[&[u64]], combine: LawCombine) -> Vec<u64>" in src
    assert "if crate::has_avx512f()" in src
    assert "return unsafe { token_law_combine_avx512(laws, combine, width) };" in src
    # Scalar reference is the source of truth the AVX path falls back to.
    assert "token_law_combine_scalar(laws, combine, width)" in src


def test_scalar_reference_and_avx512_kernel_both_exist():
    src = CHEATS.read_text(encoding="utf-8")
    assert "fn token_law_combine_scalar(laws: &[&[u64]], combine: LawCombine, width: usize) -> Vec<u64>" in src
    assert 'unsafe fn token_law_combine_avx512(' in src
    # The real AVX-512F kernel: target_feature + the 512-bit and/or intrinsics.
    kernel = src.split("unsafe fn token_law_combine_avx512(", 1)[1]
    assert '#[target_feature(enable = "avx512f")]' in src
    assert "_mm512_and_si512" in kernel
    assert "_mm512_or_si512" in kernel
    assert "_mm512_loadu_si512" in kernel and "_mm512_storeu_si512" in kernel


def test_parity_and_correctness_tests_travel_with_the_kernel():
    src = CHEATS.read_text(encoding="utf-8")
    # The load-bearing parity test + a host-agnostic wide/ragged correctness test.
    assert "fn token_law_combine_avx_matches_scalar" in src
    assert "fn token_law_combine_handles_wide_and_ragged_masks" in src


def test_sdd_515_documents_the_parity_invariant_and_kernel():
    assert SDD.is_file(), "SDD-515 must exist"
    text = SDD.read_text(encoding="utf-8")
    assert text.startswith("# SDD-515 —"), "H1 must be the canonical SDD-515 heading"
    low = text.lower()
    assert "parity" in low, "the parity invariant must be documented"
    assert "bit-for-bit" in low or "bit-identical" in low
    assert "avx-512" in low or "avx512" in low
    assert "deepen" in low
