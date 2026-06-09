//! `sovereign-mha-block` — the production multi-head GQA decoder block.
//!
//! The earlier blocks are single-head; a real decoder runs *many* query heads
//! and (for GQA) *fewer* key/value heads to shrink the KV cache, with each
//! head carrying its own RoPE phase, and the weights kept in low precision.
//! This block is all of that at once:
//!
//! ```text
//!   n1   = RMSNorm_attn(hidden)
//!   q    = Linear_q(n1)   [num_q_heads·head_dim],  RoPE each head by pos
//!   k    = Linear_k(n1)   [num_kv_heads·head_dim], RoPE each head by pos
//!   v    = Linear_v(n1)   [num_kv_heads·head_dim]
//!   cache.push(k, v)
//!   ctx  = MHA(q, cached_keys, cached_values)   [GQA head grouping]
//!   h1   = hidden + Linear_o(ctx)
//!   n2   = RMSNorm_ffn(h1)
//!   out  = h1 + Linear_down( SiLU(Linear_gate(n2)) ⊙ Linear_up(n2) )
//! ```
//!
//! Projections run through the precision-generic [`Linear`], so the whole
//! block executes in f32, ternary, or NVFP4. The pinned properties: with one
//! query head and one KV head at f32 it reproduces the single-head
//! [`sovereign-quant-block`] (a cross-crate equivalence test), GQA/MQA head
//! grouping runs, and the zeroed-sublayer block is the identity.
//!
//! [`Linear`]: sovereign_linear::Linear
//! [`sovereign-quant-block`]: https://docs.rs/sovereign-quant-block
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_ffn::silu;
use sovereign_linear::{Linear, LinearError, Precision};
use sovereign_mha::{Mha, MhaError};
use sovereign_rmsnorm::{RmsNorm, RmsNormError};
use sovereign_rope::{Rope, RopeError};
use thiserror::Error;

/// Schema version of the MHA-block surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong building or running a multi-head decoder block.
#[derive(Debug, Error, PartialEq)]
pub enum MhaBlockError {
    /// The input hidden state had the wrong length.
    #[error("hidden dim mismatch: expected {expected}, got {got}")]
    HiddenDim {
        /// Configured model dimension.
        expected: usize,
        /// Observed length.
        got: usize,
    },
    /// A multi-head-attention config/run error.
    #[error("mha: {0}")]
    Mha(#[from] MhaError),
    /// A linear-layer error.
    #[error("linear: {0}")]
    Linear(#[from] LinearError),
    /// An RMSNorm sub-error.
    #[error("rmsnorm: {0}")]
    RmsNorm(#[from] RmsNormError),
    /// A RoPE sub-error.
    #[error("rope: {0}")]
    Rope(#[from] RopeError),
}

/// f32 weights for a multi-head decoder block (row-major).
#[derive(Debug, Clone)]
pub struct MhaBlockWeights {
    /// Model (residual-stream) dimension.
    pub model_dim: usize,
    /// Per-head dimension (even).
    pub head_dim: usize,
    /// Number of query heads.
    pub num_q_heads: usize,
    /// Number of key/value heads (divides `num_q_heads`).
    pub num_kv_heads: usize,
    /// FFN hidden dimension.
    pub hidden_dim: usize,
    /// Pre-attention RMSNorm.
    pub attn_norm: RmsNorm,
    /// Pre-FFN RMSNorm.
    pub ffn_norm: RmsNorm,
    /// Q projection, `(num_q_heads·head_dim) × model_dim`.
    pub w_q: Vec<f32>,
    /// K projection, `(num_kv_heads·head_dim) × model_dim`.
    pub w_k: Vec<f32>,
    /// V projection, `(num_kv_heads·head_dim) × model_dim`.
    pub w_v: Vec<f32>,
    /// Output projection, `model_dim × (num_q_heads·head_dim)`.
    pub w_o: Vec<f32>,
    /// FFN gate, `hidden_dim × model_dim`.
    pub w_gate: Vec<f32>,
    /// FFN up, `hidden_dim × model_dim`.
    pub w_up: Vec<f32>,
    /// FFN down, `model_dim × hidden_dim`.
    pub w_down: Vec<f32>,
}

/// A multi-head GQA decoder block + its autoregressive KV cache.
#[derive(Debug, Clone)]
pub struct MhaDecoderBlock {
    model_dim: usize,
    head_dim: usize,
    num_q_heads: usize,
    num_kv_heads: usize,
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
    mha: Mha,
    rotated_keys: Vec<Vec<f32>>,
    values: Vec<Vec<f32>>,
}

impl MhaDecoderBlock {
    /// Quantize `weights` into a runnable block at `precision`.
    pub fn from_weights(
        weights: &MhaBlockWeights,
        precision: Precision,
    ) -> Result<Self, MhaBlockError> {
        let md = weights.model_dim;
        let hd = weights.head_dim;
        let hid = weights.hidden_dim;
        let q_dim = weights.num_q_heads * hd;
        let kv_dim = weights.num_kv_heads * hd;
        let mha = Mha::new(weights.num_q_heads, weights.num_kv_heads, hd)?;
        Ok(Self {
            model_dim: md,
            head_dim: hd,
            num_q_heads: weights.num_q_heads,
            num_kv_heads: weights.num_kv_heads,
            precision,
            attn_norm: weights.attn_norm.clone(),
            ffn_norm: weights.ffn_norm.clone(),
            q: Linear::from_f32(&weights.w_q, q_dim, md, precision)?,
            k: Linear::from_f32(&weights.w_k, kv_dim, md, precision)?,
            v: Linear::from_f32(&weights.w_v, kv_dim, md, precision)?,
            o: Linear::from_f32(&weights.w_o, md, q_dim, precision)?,
            gate: Linear::from_f32(&weights.w_gate, hid, md, precision)?,
            up: Linear::from_f32(&weights.w_up, hid, md, precision)?,
            down: Linear::from_f32(&weights.w_down, md, hid, precision)?,
            rope: Rope::new(hd),
            mha,
            rotated_keys: Vec::new(),
            values: Vec::new(),
        })
    }

    /// The execution precision.
    pub fn precision(&self) -> Precision {
        self.precision
    }

    /// Number of query heads.
    pub fn num_q_heads(&self) -> usize {
        self.num_q_heads
    }

    /// Number of key/value heads.
    pub fn num_kv_heads(&self) -> usize {
        self.num_kv_heads
    }

    /// Number of cached positions.
    pub fn len(&self) -> usize {
        self.values.len()
    }

    /// Whether the cache is empty.
    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }

    /// Rotate each `head_dim`-wide head slice of `v` by `pos`.
    fn rope_heads(&self, v: &mut [f32], heads: usize, pos: usize) -> Result<(), MhaBlockError> {
        let hd = self.head_dim;
        for h in 0..heads {
            self.rope
                .rotate_in_place(&mut v[h * hd..(h + 1) * hd], pos)?;
        }
        Ok(())
    }

    /// Advance one position and return the updated hidden state.
    pub fn step(&mut self, hidden: &[f32]) -> Result<Vec<f32>, MhaBlockError> {
        if hidden.len() != self.model_dim {
            return Err(MhaBlockError::HiddenDim {
                expected: self.model_dim,
                got: hidden.len(),
            });
        }
        let pos = self.values.len();

        // attention sublayer (pre-norm)
        let n1 = self.attn_norm.normalize(hidden)?;
        let mut q = self.q.forward(&n1)?;
        let mut k = self.k.forward(&n1)?;
        let v = self.v.forward(&n1)?;
        self.rope_heads(&mut q, self.num_q_heads, pos)?;
        self.rope_heads(&mut k, self.num_kv_heads, pos)?;
        self.rotated_keys.push(k);
        self.values.push(v);

        let ctx = self.mha.attend(&q, &self.rotated_keys, &self.values)?;
        let attn_out = self.o.forward(&ctx)?;
        let h1: Vec<f32> = hidden.iter().zip(&attn_out).map(|(a, b)| a + b).collect();

        // feed-forward sublayer (pre-norm) — SwiGLU via Linear
        let n2 = self.ffn_norm.normalize(&h1)?;
        let gate = self.gate.forward(&n2)?;
        let up = self.up.forward(&n2)?;
        let act: Vec<f32> = gate.iter().zip(&up).map(|(g, u)| silu(*g) * u).collect();
        let ffn_out = self.down.forward(&act)?;

        Ok(h1.iter().zip(&ffn_out).map(|(a, b)| a + b).collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mat(s: f32, n: usize) -> Vec<f32> {
        (0..n).map(|i| ((i as f32 + s) * 0.017).sin()).collect()
    }

    fn weights(
        model_dim: usize,
        head_dim: usize,
        num_q: usize,
        num_kv: usize,
        hidden_dim: usize,
    ) -> MhaBlockWeights {
        let q_dim = num_q * head_dim;
        let kv_dim = num_kv * head_dim;
        MhaBlockWeights {
            model_dim,
            head_dim,
            num_q_heads: num_q,
            num_kv_heads: num_kv,
            hidden_dim,
            attn_norm: RmsNorm::new(model_dim),
            ffn_norm: RmsNorm::new(model_dim),
            w_q: mat(1.0, q_dim * model_dim),
            w_k: mat(2.0, kv_dim * model_dim),
            w_v: mat(3.0, kv_dim * model_dim),
            w_o: mat(4.0, model_dim * q_dim),
            w_gate: mat(5.0, hidden_dim * model_dim),
            w_up: mat(6.0, hidden_dim * model_dim),
            w_down: mat(7.0, model_dim * hidden_dim),
        }
    }

    #[test]
    fn single_head_f32_matches_quant_block() {
        // num_q = num_kv = 1, f32 → must equal the single-head quant-block.
        use sovereign_quant_block::{QuantBlockWeights, QuantDecoderBlock};
        let md = 4;
        let hd = 4;
        let hid = 4;
        let w = weights(md, hd, 1, 1, hid);

        let mut mha_block = MhaDecoderBlock::from_weights(&w, Precision::F32).unwrap();
        let qw = QuantBlockWeights {
            model_dim: md,
            head_dim: hd,
            hidden_dim: hid,
            attn_norm: w.attn_norm.clone(),
            ffn_norm: w.ffn_norm.clone(),
            w_q: w.w_q.clone(),
            w_k: w.w_k.clone(),
            w_v: w.w_v.clone(),
            w_o: w.w_o.clone(),
            w_gate: w.w_gate.clone(),
            w_up: w.w_up.clone(),
            w_down: w.w_down.clone(),
        };
        let mut quant = QuantDecoderBlock::from_weights(&qw, Precision::F32).unwrap();

        for step in 0..6 {
            let x: Vec<f32> = (0..md).map(|i| ((i + step) as f32 * 0.3).sin()).collect();
            let ya = mha_block.step(&x).unwrap();
            let yb = quant.step(&x).unwrap();
            for (a, b) in ya.iter().zip(&yb) {
                assert!((a - b).abs() < 1e-5, "step {step}: {ya:?} vs {yb:?}");
            }
        }
    }

    #[test]
    fn gqa_block_runs_finite() {
        // 4 query heads, 2 kv heads → GQA. model_dim = num_q*head_dim = 8.
        let w = weights(8, 2, 4, 2, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::F32).unwrap();
        assert_eq!(block.num_q_heads(), 4);
        assert_eq!(block.num_kv_heads(), 2);
        for step in 0..5 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            let y = block.step(&x).unwrap();
            assert_eq!(y.len(), 8);
            assert!(y.iter().all(|v| v.is_finite()));
        }
        assert_eq!(block.len(), 5);
    }

    #[test]
    fn mqa_block_runs_finite() {
        // 4 query heads share 1 kv head (MQA). model_dim = 8.
        let w = weights(8, 2, 4, 1, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::F32).unwrap();
        assert_eq!(block.num_kv_heads(), 1);
        let x: Vec<f32> = (0..8).map(|i| (i as f32 * 0.2).sin()).collect();
        assert!(block.step(&x).unwrap().iter().all(|v| v.is_finite()));
    }

    #[test]
    fn ternary_multihead_block_runs() {
        let w = weights(8, 2, 4, 2, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::Ternary).unwrap();
        assert_eq!(block.precision(), Precision::Ternary);
        let x: Vec<f32> = (0..8).map(|i| (i as f32 * 0.3).cos()).collect();
        assert!(block.step(&x).unwrap().iter().all(|v| v.is_finite()));
    }

    #[test]
    fn zeroed_block_is_identity() {
        let md = 8;
        let hd = 2;
        let (nq, nkv, hid) = (4, 2, 8);
        let zw = MhaBlockWeights {
            model_dim: md,
            head_dim: hd,
            num_q_heads: nq,
            num_kv_heads: nkv,
            hidden_dim: hid,
            attn_norm: RmsNorm::new(md),
            ffn_norm: RmsNorm::new(md),
            w_q: vec![0.0; nq * hd * md],
            w_k: vec![0.0; nkv * hd * md],
            w_v: vec![0.0; nkv * hd * md],
            w_o: vec![0.0; md * nq * hd],
            w_gate: vec![0.0; hid * md],
            w_up: vec![0.0; hid * md],
            w_down: vec![0.0; md * hid],
        };
        let mut block = MhaDecoderBlock::from_weights(&zw, Precision::F32).unwrap();
        let x = vec![1.0, -2.0, 0.5, 3.0, -1.0, 0.25, 2.0, -0.5];
        assert_eq!(block.step(&x).unwrap(), x);
    }

    #[test]
    fn bad_head_grouping_is_caught() {
        let w = weights(6, 2, 3, 2, 8); // 3 not divisible by 2
        assert!(matches!(
            MhaDecoderBlock::from_weights(&w, Precision::F32),
            Err(MhaBlockError::Mha(_))
        ));
    }

    #[test]
    fn hidden_dim_mismatch_is_caught() {
        let w = weights(8, 2, 4, 2, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::F32).unwrap();
        assert_eq!(
            block.step(&[1.0, 2.0]).unwrap_err(),
            MhaBlockError::HiddenDim {
                expected: 8,
                got: 2
            }
        );
    }
}
