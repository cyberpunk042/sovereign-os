//! Ternary (multiplication-free) **SwiGLU** gated feed-forward network —
//! the BitNet form of the FFN a modern decoder block actually runs.
//!
//! A SwiGLU FFN has three projections and a gate:
//!
//! ```text
//! gate = W_gate · x        up = W_up · x          (both: hidden × dim)
//! h_i  = SiLU(gate_i) · up_i                       (elementwise gate)
//! out  = W_down · h                                (dim × hidden)
//! ```
//!
//! The expensive part — the three matrix products, `O(hidden · dim)` each —
//! is what BitNet makes ternary: [`TernarySwiGlu`] runs all three as
//! [`BitLinearLayer`]s, so every inner-product multiply is eliminated
//! (only the per-output absmean scales remain). The *only* genuine
//! multiplies left are the `hidden` elementwise gate products
//! `SiLU(gate_i) · up_i` — cheap, `O(hidden)`, not `O(hidden · dim)` —
//! which is exactly the BitNet trade: keep the smooth gate in float, make
//! the heavy projections ternary.
//!
//! Because the matmuls are bit-for-bit equal to their dense multiply-based
//! reference (the [`BitLinearLayer`] guarantee) and the SiLU gate is the
//! same function on both sides, [`TernarySwiGlu::forward`] equals a dense
//! SwiGLU on the de-quantized ternary weights — proven by
//! `forward_matches_dense_reference`.
//!
//! Input and output are both `dim`, so the block is always residual-stream
//! compatible ([`TernarySwiGlu::forward_residual`]).
//!
//! Standing rule (workspace doctrine): we do not minimize anything.

use crate::{
    BitLinearError, Packing,
    linear::{BitLinearLayer, OpCount},
};
use serde::{Deserialize, Serialize};

/// The SiLU (a.k.a. swish) activation: `z · σ(z)`, `σ(z) = 1/(1+e^-z)`.
///
/// Smooth and self-gating; this is the nonlinearity SwiGLU applies to the
/// gate projection before the elementwise product with `up`.
pub fn silu(z: f32) -> f32 {
    z / (1.0 + (-z).exp())
}

/// A ternary SwiGLU gated feed-forward network.
///
/// All three projections are multiplication-free [`BitLinearLayer`]s. The
/// `gate` and `up` projections are `hidden × dim`; `down` is `dim ×
/// hidden`, returning to model width.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TernarySwiGlu {
    /// Gate projection (`hidden × dim`), fed through SiLU.
    pub gate: BitLinearLayer,
    /// Up projection (`hidden × dim`), gated elementwise by `SiLU(gate)`.
    pub up: BitLinearLayer,
    /// Down projection (`dim × hidden`), back to model width.
    pub down: BitLinearLayer,
}

impl TernarySwiGlu {
    /// Build from real-valued weight matrices. `w_gate` and `w_up` are
    /// `hidden × dim` (row-major); `w_down` is `dim × hidden`. Each is
    /// absmean-quantized to ternary and packed. Passing the same
    /// `dim`/`hidden` to all three forces their shapes mutually consistent;
    /// a wrongly-sized matrix yields [`BitLinearError::ShapeMismatch`].
    pub fn from_weights(
        w_gate: &[f32],
        w_up: &[f32],
        w_down: &[f32],
        dim: usize,
        hidden: usize,
        packing: Packing,
    ) -> Result<Self, BitLinearError> {
        Ok(Self {
            gate: BitLinearLayer::from_weights(w_gate, hidden, dim, packing)?,
            up: BitLinearLayer::from_weights(w_up, hidden, dim, packing)?,
            down: BitLinearLayer::from_weights(w_down, dim, hidden, packing)?,
        })
    }

    /// Model (residual-stream) width — the in/out dimension.
    pub fn dim(&self) -> usize {
        self.gate.input_dim
    }

    /// Hidden (gated) width.
    pub fn hidden(&self) -> usize {
        self.gate.output_dim
    }

    /// Forward pass. Returns the `dim`-width output and the summed
    /// [`OpCount`] across the three ternary matmuls. The `OpCount` accounts
    /// only the matmul arithmetic; the `hidden` SiLU-gate products are the
    /// separate (intended) float cost of the gate.
    pub fn forward(&self, x: &[f32]) -> Result<(Vec<f32>, OpCount), BitLinearError> {
        let (g, og) = self.gate.forward(x)?;
        let (u, ou) = self.up.forward(x)?;
        // Elementwise gate: h = SiLU(gate) ⊙ up. These are the only genuine
        // multiplies, O(hidden), not O(hidden·dim).
        let h: Vec<f32> = g.iter().zip(&u).map(|(gi, ui)| silu(*gi) * ui).collect();
        let (out, od) = self.down.forward(&h)?;

        let total = OpCount {
            adds: og.adds + ou.adds + od.adds,
            subs: og.subs + ou.subs + od.subs,
            skips: og.skips + ou.skips + od.skips,
            float_muls: og.float_muls + ou.float_muls + od.float_muls,
        };
        Ok((out, total))
    }

    /// Inner-product multiplies a dense GEMM of all three projections would
    /// spend — every one of which this block eliminates.
    pub fn floating_muls_eliminated(&self) -> usize {
        let hd = self.hidden() * self.dim();
        hd + hd + self.dim() * self.hidden()
    }

    /// Residual-wrapped forward — `y = x + swiglu(x)` — the decoder's FFN
    /// sublayer shape. Input and output are both `dim`, so this is always
    /// well-formed (no shape guard needed).
    pub fn forward_residual(&self, x: &[f32]) -> Result<(Vec<f32>, OpCount), BitLinearError> {
        let (mut y, ops) = self.forward(x)?;
        for (yi, &xi) in y.iter_mut().zip(x.iter()) {
            *yi += xi;
        }
        Ok((y, ops))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::reference;

    fn rng(seed: u64) -> impl FnMut() -> f32 {
        let mut state = seed;
        move || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            ((state >> 40) as f32 / 0x10_0000 as f32) * 8.0 - 4.0
        }
    }

    /// Dense multiply-based SwiGLU on the de-quantized ternary weights, with
    /// the identical SiLU gate. The ternary block must match this exactly.
    fn dense_swiglu(g: &TernarySwiGlu, x: &[f32]) -> Vec<f32> {
        let gt = g.gate.trits().unwrap();
        let ut = g.up.trits().unwrap();
        let dt = g.down.trits().unwrap();
        let gate = reference::dense_forward(&gt, g.gate.scale, g.dim(), x);
        let up = reference::dense_forward(&ut, g.up.scale, g.dim(), x);
        let h: Vec<f32> = gate.iter().zip(&up).map(|(a, b)| silu(*a) * b).collect();
        reference::dense_forward(&dt, g.down.scale, g.hidden(), &h)
    }

    #[test]
    fn silu_zero_is_zero() {
        assert_eq!(silu(0.0), 0.0);
    }

    #[test]
    fn forward_matches_dense_reference() {
        let (dim, hidden) = (10, 27);
        let mut next = rng(0xA5A5_1234_DEAD_BEEF);
        let w_gate: Vec<f32> = (0..hidden * dim).map(|_| next()).collect();
        let w_up: Vec<f32> = (0..hidden * dim).map(|_| next()).collect();
        let w_down: Vec<f32> = (0..dim * hidden).map(|_| next()).collect();
        let x: Vec<f32> = (0..dim).map(|_| next()).collect();

        for packing in [Packing::Base3, Packing::TwoBit] {
            let ffn =
                TernarySwiGlu::from_weights(&w_gate, &w_up, &w_down, dim, hidden, packing).unwrap();
            assert_eq!(ffn.dim(), dim);
            assert_eq!(ffn.hidden(), hidden);

            let (y, _ops) = ffn.forward(&x).unwrap();
            let reference = dense_swiglu(&ffn, &x);
            // The matmuls are bit-exact and the SiLU gate is identical, so
            // the whole gated FFN matches the dense version exactly.
            assert_eq!(y, reference, "mismatch under {packing:?}");
            assert_eq!(y.len(), dim);
        }
    }

    #[test]
    fn matmuls_are_multiplication_free() {
        let (dim, hidden) = (6, 16);
        let ffn = TernarySwiGlu::from_weights(
            &vec![0.5f32; hidden * dim],
            &vec![0.5f32; hidden * dim],
            &vec![0.5f32; dim * hidden],
            dim,
            hidden,
            Packing::Base3,
        )
        .unwrap();
        let (_y, ops) = ffn.forward(&vec![1.0f32; dim]).unwrap();
        // The only matmul float multiplies are the per-output scales:
        // gate (hidden) + up (hidden) + down (dim).
        assert_eq!(ops.float_muls, hidden + hidden + dim);
        // Every weight across all three projections is an add/sub/skip.
        let weights = hidden * dim + hidden * dim + dim * hidden;
        assert_eq!(ops.adds + ops.subs + ops.skips, weights);
        assert_eq!(ffn.floating_muls_eliminated(), weights);
    }

    #[test]
    fn zero_weights_make_residual_identity() {
        // All-zero projections: gate=0 → SiLU(0)=0 → h=0 → down(0)=0 → out=0.
        // So the residual sublayer leaves the stream untouched.
        let (dim, hidden) = (8, 20);
        let ffn = TernarySwiGlu::from_weights(
            &vec![0.0f32; hidden * dim],
            &vec![0.0f32; hidden * dim],
            &vec![0.0f32; dim * hidden],
            dim,
            hidden,
            Packing::Base3,
        )
        .unwrap();
        let x: Vec<f32> = (0..dim).map(|i| i as f32 - 3.5).collect();
        let (out, _) = ffn.forward(&x).unwrap();
        assert_eq!(out, vec![0.0f32; dim], "zero block must output zero");
        let (res, _) = ffn.forward_residual(&x).unwrap();
        assert_eq!(res, x, "zero block residual must be the identity");
    }

    #[test]
    fn wrong_weight_length_rejected() {
        // w_gate too short for hidden*dim.
        let err =
            TernarySwiGlu::from_weights(&[0.5; 3], &[0.5; 8], &[0.5; 8], 2, 4, Packing::Base3)
                .unwrap_err();
        assert!(matches!(err, BitLinearError::ShapeMismatch { .. }));
    }

    #[test]
    fn serde_round_trip() {
        let ffn =
            TernarySwiGlu::from_weights(&[0.5; 8], &[0.5; 8], &[0.5; 8], 2, 4, Packing::TwoBit)
                .unwrap();
        let json = serde_json::to_string(&ffn).unwrap();
        let back: TernarySwiGlu = serde_json::from_str(&json).unwrap();
        assert_eq!(ffn, back);
    }
}
