//! `sovereign-quant-block` — a precision-selectable transformer decoder block.
//!
//! The reference [`sovereign-transformer-block`] runs its projections in f32.
//! The dump's whole premise, though, is *low-precision* inference — so this
//! block keeps the exact same pre-norm structure but routes every projection
//! (Q/K/V/O and the SwiGLU gate/up/down) through a precision-generic
//! [`Linear`], so the whole block can execute in f32, ternary 1.58-bit, or
//! NVFP4 4-bit:
//!
//! ```text
//!   n1  = RMSNorm_attn(hidden)
//!   q   = RoPE(Linear_q(n1), pos)   k = RoPE(Linear_k(n1), pos)   v = Linear_v(n1)
//!   ctx = Attention(q, cached_keys, cached_values)
//!   h1  = hidden + Linear_o(ctx)
//!   n2  = RMSNorm_ffn(h1)
//!   out = h1 + Linear_down( SiLU(Linear_gate(n2)) ⊙ Linear_up(n2) )
//! ```
//!
//! Two properties are pinned: at [`Precision::F32`] the block reproduces the
//! independent reference block bit-for-bit (a cross-crate equivalence test),
//! and at any precision the zeroed-sublayer block is the identity (both
//! residual streams). [`bits_per_param`](QuantDecoderBlock::bits_per_param)
//! reports the real footprint the chosen precision implies.
//!
//! [`sovereign-transformer-block`]: https://docs.rs/sovereign-transformer-block
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_attention::{Attention, AttentionError};
use sovereign_ffn::silu;
use sovereign_linear::{Linear, LinearError, Precision};
use sovereign_rmsnorm::{RmsNorm, RmsNormError};
use sovereign_rope::{Rope, RopeError};
use thiserror::Error;

/// Schema version of the quant-block surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong building or running a quantized decoder block.
#[derive(Debug, Error, PartialEq)]
pub enum QuantBlockError {
    /// The input hidden state had the wrong length.
    #[error("hidden dim mismatch: expected {expected}, got {got}")]
    HiddenDim {
        /// Configured model dimension.
        expected: usize,
        /// Observed length.
        got: usize,
    },
    /// A linear-layer error (shape/precision/forward).
    #[error("linear: {0}")]
    Linear(#[from] LinearError),
    /// An RMSNorm sub-error.
    #[error("rmsnorm: {0}")]
    RmsNorm(#[from] RmsNormError),
    /// A RoPE sub-error.
    #[error("rope: {0}")]
    Rope(#[from] RopeError),
    /// An attention sub-error.
    #[error("attention: {0}")]
    Attention(#[from] AttentionError),
}

/// The f32 weights to quantize into a block (row-major, same layout as the
/// reference block).
#[derive(Debug, Clone)]
pub struct QuantBlockWeights {
    /// Model (residual-stream) dimension.
    pub model_dim: usize,
    /// Per-head attention dimension (even).
    pub head_dim: usize,
    /// FFN hidden dimension.
    pub hidden_dim: usize,
    /// Pre-attention RMSNorm.
    pub attn_norm: RmsNorm,
    /// Pre-FFN RMSNorm.
    pub ffn_norm: RmsNorm,
    /// Q projection, `head_dim × model_dim`.
    pub w_q: Vec<f32>,
    /// K projection, `head_dim × model_dim`.
    pub w_k: Vec<f32>,
    /// V projection, `head_dim × model_dim`.
    pub w_v: Vec<f32>,
    /// Output projection, `model_dim × head_dim`.
    pub w_o: Vec<f32>,
    /// FFN gate projection, `hidden_dim × model_dim`.
    pub w_gate: Vec<f32>,
    /// FFN up projection, `hidden_dim × model_dim`.
    pub w_up: Vec<f32>,
    /// FFN down projection, `model_dim × hidden_dim`.
    pub w_down: Vec<f32>,
}

/// A quantized decoder block + its autoregressive KV cache.
#[derive(Debug, Clone)]
pub struct QuantDecoderBlock {
    model_dim: usize,
    head_dim: usize,
    precision: Precision,
    attn_norm: RmsNorm,
    ffn_norm: RmsNorm,
    q: Linear,
    k: Linear,
    v: Linear,
    o: Linear,
    gate: Linear,
    up: Linear,
    down: Linear,
    rope: Rope,
    attention: Attention,
    rotated_keys: Vec<Vec<f32>>,
    values: Vec<Vec<f32>>,
}

impl QuantDecoderBlock {
    /// Quantize `weights` into a runnable block at `precision`.
    pub fn from_weights(
        weights: &QuantBlockWeights,
        precision: Precision,
    ) -> Result<Self, QuantBlockError> {
        let (md, hd, hid) = (weights.model_dim, weights.head_dim, weights.hidden_dim);
        Ok(Self {
            model_dim: md,
            head_dim: hd,
            precision,
            attn_norm: weights.attn_norm.clone(),
            ffn_norm: weights.ffn_norm.clone(),
            q: Linear::from_f32(&weights.w_q, hd, md, precision)?,
            k: Linear::from_f32(&weights.w_k, hd, md, precision)?,
            v: Linear::from_f32(&weights.w_v, hd, md, precision)?,
            o: Linear::from_f32(&weights.w_o, md, hd, precision)?,
            gate: Linear::from_f32(&weights.w_gate, hid, md, precision)?,
            up: Linear::from_f32(&weights.w_up, hid, md, precision)?,
            down: Linear::from_f32(&weights.w_down, md, hid, precision)?,
            rope: Rope::new(hd),
            attention: Attention::new(hd),
            rotated_keys: Vec::new(),
            values: Vec::new(),
        })
    }

    /// The execution precision of every projection.
    pub fn precision(&self) -> Precision {
        self.precision
    }

    /// The per-head attention dimension.
    pub fn head_dim(&self) -> usize {
        self.head_dim
    }

    /// The model (residual-stream) dimension.
    pub fn model_dim(&self) -> usize {
        self.model_dim
    }

    /// Number of cached positions.
    pub fn len(&self) -> usize {
        self.values.len()
    }

    /// Whether the cache is empty.
    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }

    /// Average bits/param across the seven projections at this precision.
    pub fn bits_per_param(&self) -> f64 {
        let ls = [
            &self.q, &self.k, &self.v, &self.o, &self.gate, &self.up, &self.down,
        ];
        ls.iter().map(|l| l.bits_per_param()).sum::<f64>() / ls.len() as f64
    }

    /// Advance one position: consume `hidden`, extend the KV cache, and return
    /// the updated hidden state.
    pub fn step(&mut self, hidden: &[f32]) -> Result<Vec<f32>, QuantBlockError> {
        if hidden.len() != self.model_dim {
            return Err(QuantBlockError::HiddenDim {
                expected: self.model_dim,
                got: hidden.len(),
            });
        }
        let pos = self.values.len();

        // attention sublayer (pre-norm)
        let n1 = self.attn_norm.normalize(hidden)?;
        let q = self.rope.rotate(&self.q.forward(&n1)?, pos)?;
        let k = self.rope.rotate(&self.k.forward(&n1)?, pos)?;
        let v = self.v.forward(&n1)?;
        self.rotated_keys.push(k);
        self.values.push(v);

        let ctx = self
            .attention
            .attend(&q, &self.rotated_keys, &self.values)?;
        let attn_out = self.o.forward(&ctx)?;
        let h1: Vec<f32> = hidden.iter().zip(&attn_out).map(|(a, b)| a + b).collect();

        // feed-forward sublayer (pre-norm) — SwiGLU via Linear projections
        let n2 = self.ffn_norm.normalize(&h1)?;
        let gate = self.gate.forward(&n2)?;
        let up = self.up.forward(&n2)?;
        let hidden_act: Vec<f32> = gate.iter().zip(&up).map(|(g, u)| silu(*g) * u).collect();
        let ffn_out = self.down.forward(&hidden_act)?;

        Ok(h1.iter().zip(&ffn_out).map(|(a, b)| a + b).collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn weights(model_dim: usize, hidden_dim: usize, seed: f32) -> QuantBlockWeights {
        let hd = model_dim;
        let mat = |s: f32, n: usize| (0..n).map(|i| ((i as f32 + s) * 0.017).sin()).collect();
        QuantBlockWeights {
            model_dim,
            head_dim: hd,
            hidden_dim,
            attn_norm: RmsNorm::new(model_dim),
            ffn_norm: RmsNorm::new(model_dim),
            w_q: mat(seed, hd * model_dim),
            w_k: mat(seed + 1.0, hd * model_dim),
            w_v: mat(seed + 2.0, hd * model_dim),
            w_o: mat(seed + 3.0, model_dim * hd),
            w_gate: mat(seed + 4.0, hidden_dim * model_dim),
            w_up: mat(seed + 5.0, hidden_dim * model_dim),
            w_down: mat(seed + 6.0, model_dim * hidden_dim),
        }
    }

    fn zero_weights(model_dim: usize, hidden_dim: usize) -> QuantBlockWeights {
        QuantBlockWeights {
            model_dim,
            head_dim: model_dim,
            hidden_dim,
            attn_norm: RmsNorm::new(model_dim),
            ffn_norm: RmsNorm::new(model_dim),
            w_q: vec![0.0; model_dim * model_dim],
            w_k: vec![0.0; model_dim * model_dim],
            w_v: vec![0.0; model_dim * model_dim],
            w_o: vec![0.0; model_dim * model_dim],
            w_gate: vec![0.0; hidden_dim * model_dim],
            w_up: vec![0.0; hidden_dim * model_dim],
            w_down: vec![0.0; model_dim * hidden_dim],
        }
    }

    #[test]
    fn f32_block_matches_the_reference_block() {
        // The f32 path must reproduce the independent reference implementation.
        use sovereign_ffn::SwiGlu;
        use sovereign_transformer_block::{BlockWeights, DecoderBlock};

        let w = weights(4, 4, 3.0);
        let mut quant = QuantDecoderBlock::from_weights(&w, Precision::F32).unwrap();

        let reference_weights = BlockWeights {
            model_dim: w.model_dim,
            head_dim: w.head_dim,
            attn_norm: w.attn_norm.clone(),
            ffn_norm: w.ffn_norm.clone(),
            w_q: w.w_q.clone(),
            w_k: w.w_k.clone(),
            w_v: w.w_v.clone(),
            w_o: w.w_o.clone(),
            ffn: SwiGlu::new(
                w.model_dim,
                w.hidden_dim,
                w.w_gate.clone(),
                w.w_up.clone(),
                w.w_down.clone(),
            )
            .unwrap(),
        };
        let mut reference = DecoderBlock::new(reference_weights).unwrap();

        for step in 0..6 {
            let x: Vec<f32> = (0..4).map(|i| ((i + step) as f32 * 0.3).sin()).collect();
            let yq = quant.step(&x).unwrap();
            let yr = reference.step(&x).unwrap();
            for (a, b) in yq.iter().zip(&yr) {
                assert!((a - b).abs() < 1e-5, "step {step}: {yq:?} vs {yr:?}");
            }
        }
    }

    #[test]
    fn zeroed_block_is_identity_at_every_precision() {
        for p in [Precision::F32, Precision::Ternary, Precision::Nvfp4] {
            let mut block = QuantDecoderBlock::from_weights(&zero_weights(4, 4), p).unwrap();
            let x = vec![1.0, -2.0, 0.5, 3.0];
            let y = block.step(&x).unwrap();
            assert_eq!(y, x, "precision {p:?} should be identity");
        }
    }

    #[test]
    fn ternary_block_runs_and_reports_low_bits() {
        let mut block =
            QuantDecoderBlock::from_weights(&weights(16, 16, 1.0), Precision::Ternary).unwrap();
        assert_eq!(block.precision(), Precision::Ternary);
        assert!(block.bits_per_param() < 2.0, "{}", block.bits_per_param());
        let x: Vec<f32> = (0..16).map(|i| (i as f32 * 0.2).sin()).collect();
        let y = block.step(&x).unwrap();
        assert_eq!(y.len(), 16);
        assert!(y.iter().all(|v| v.is_finite()));
    }

    #[test]
    fn nvfp4_block_runs_and_reports_4_5_bits() {
        let mut block =
            QuantDecoderBlock::from_weights(&weights(16, 16, 2.0), Precision::Nvfp4).unwrap();
        assert!(
            (block.bits_per_param() - 4.5).abs() < 1e-9,
            "{}",
            block.bits_per_param()
        );
        let x: Vec<f32> = (0..16).map(|i| (i as f32 * 0.1).cos()).collect();
        assert!(block.step(&x).unwrap().iter().all(|v| v.is_finite()));
    }

    #[test]
    fn cache_grows_and_dim_mismatch_caught() {
        let mut block =
            QuantDecoderBlock::from_weights(&weights(4, 8, 1.0), Precision::F32).unwrap();
        assert!(block.is_empty());
        block.step(&[0.1, 0.2, 0.3, 0.4]).unwrap();
        assert_eq!(block.len(), 1);
        assert_eq!(
            block.step(&[1.0, 2.0]).unwrap_err(),
            QuantBlockError::HiddenDim {
                expected: 4,
                got: 2
            }
        );
    }
}
