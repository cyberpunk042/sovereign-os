//! `sovereign-bitlinear-core` — M073 1-bit (ternary) logic + BitLinear core.
//!
//! This is the real compute substrate the dump (`raw/dumps/2026-05-18`
//! lines 777-795) calls for: ternary weights that *eliminate*
//! floating-point multiplication from the linear-projection hot path.
//!
//! ## What is actually implemented here (not a stub)
//!
//! - **Ternary weight set `{-1, 0, +1}`** (F06039) as a 2-bit code, with
//!   the arithmetic-elimination semantics the dump mandates
//!   (F06042-F06045): `+1` adds the activation, `-1` subtracts it, `0`
//!   is a no-op skipped entirely.
//! - **BitNet b1.58 absmean quantization** (F06038, F06051) — per-tensor
//!   scale `γ = mean(|W|)`, then `round(W/γ)` clamped to the ternary set.
//! - **Information-theoretic packing** — base-3 packing of 5 trits per
//!   byte = **1.6 bits/parameter** (F06040, F06054-F06056), satisfying
//!   the `log2(3) ≈ 1.585` lower bound, plus a byte-simple 2-bit packing
//!   (4 trits/byte) for fast unpack.
//! - **Multiplication-free BitLinear GEMM** (F06052, F06059) — the
//!   forward path runs directly on the packed ternary representation
//!   with **no de-quantization back to floating point** at execution;
//!   the only float multiplies are the `output_dim` per-row scale
//!   applications, never the `output_dim × input_dim` inner products.
//! - **Energy / op accounting** (F06046, F06067) — counts add/sub/skip
//!   and the floating-point multiplies eliminated versus a dense GEMM.
//! - **Information-theory validator** (F06074, F06075) — verifies a
//!   packing stores `≈ 1.585` bits/param and *rejects* any encoding that
//!   exceeds 2 bits/param for ternary weights.
//!
//! The numerics are exact: [`BitLinearLayer::forward`] produces bit-for-bit
//! the same result as the multiply-based reference
//! ([`reference::dense_forward`]) on the de-quantized weights — proven by
//! the `forward_matches_dense_reference` test. That equivalence is the
//! whole point: we remove the multiplies *without* changing the answer.
//!
//! Standing rule (workspace doctrine): we do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod linear;
pub mod mlp;
pub mod pack;
pub mod reference;
pub mod ternary;
pub mod validate;

use thiserror::Error;

pub use linear::{BitLinearLayer, OpCount};
pub use mlp::{Activation, BitLinearMlp};
pub use pack::{Packing, bits_per_param};
pub use ternary::{Trit, quantize_absmean};
pub use validate::{InfoTheoryReport, validate_bits_per_param};

/// Schema version of the BitLinear ternary surface (F06079).
pub const SCHEMA_VERSION: &str = "1.0.0";

/// `log2(3)` — the information-theoretic lower bound on bits per ternary
/// parameter (F06040). Any honest ternary encoding stores at least this
/// many bits per weight.
pub const TERNARY_ENTROPY_BITS: f64 = 1.584_962_500_721_156;

/// Hard ceiling for a ternary encoding (F06075). An encoding that spends
/// more than this per parameter is not exploiting ternary structure and
/// is rejected by [`validate::validate_bits_per_param`].
pub const MAX_TERNARY_BITS_PER_PARAM: f64 = 2.0;

/// Errors raised by the BitLinear core.
#[derive(Debug, Error, PartialEq)]
pub enum BitLinearError {
    /// A weight matrix did not contain `output_dim * input_dim` elements.
    #[error("weight count {got} does not match output_dim*input_dim = {expected}")]
    ShapeMismatch {
        /// Number of weights actually supplied.
        got: usize,
        /// Number of weights the declared shape requires.
        expected: usize,
    },
    /// An activation vector length did not match the layer's `input_dim`.
    #[error("activation length {got} does not match input_dim {expected}")]
    InputMismatch {
        /// Length of the activation vector supplied.
        got: usize,
        /// `input_dim` the layer expects.
        expected: usize,
    },
    /// A packed buffer was truncated / not the size the trit count implies.
    #[error("packed buffer of {got} bytes cannot hold {trits} trits under {packing:?}")]
    TruncatedBuffer {
        /// Bytes actually present.
        got: usize,
        /// Trits the buffer is claimed to encode.
        trits: usize,
        /// Packing scheme in use.
        packing: Packing,
    },
    /// An encoding exceeded [`MAX_TERNARY_BITS_PER_PARAM`].
    #[error("encoding spends {bits_per_param:.4} bits/param, exceeding the {ceiling} ceiling")]
    NotTernary {
        /// Measured bits per parameter.
        bits_per_param: f64,
        /// The ceiling that was exceeded.
        ceiling: f64,
    },
    /// A [`mlp::BitLinearMlp`] was built with no layers.
    #[error("a BitLinear MLP must have at least one layer")]
    EmptyStack,
    /// Two consecutive [`mlp::BitLinearMlp`] layers do not chain: layer
    /// `index`'s `output_dim` must equal the next layer's `input_dim`.
    #[error(
        "layer {index} output_dim {output_dim} does not feed layer {next} input_dim {next_input_dim}"
    )]
    StackShapeMismatch {
        /// Index of the producing layer.
        index: usize,
        /// `output_dim` of the producing layer.
        output_dim: usize,
        /// Index of the consuming layer.
        next: usize,
        /// `input_dim` of the consuming layer.
        next_input_dim: usize,
    },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn entropy_bound_is_log2_three() {
        // log2(3) computed independently must match the published constant.
        let log2_3 = 3.0_f64.log2();
        assert!((log2_3 - TERNARY_ENTROPY_BITS).abs() < 1e-12);
    }

    #[test]
    fn schema_version_pinned() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
