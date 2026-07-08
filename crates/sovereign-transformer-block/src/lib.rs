//! `sovereign-transformer-block` — a full pre-norm decoder block, assembled.
//!
//! This is the capstone of the decode-engine arc: the four primitive crates
//! wired into the exact structure a modern (Llama-style) decoder layer runs,
//! with residual connections and a stateful KV cache for autoregressive use:
//!
//! ```text
//!   n1  = RMSNorm_attn(hidden)                       (sovereign-rmsnorm)
//!   q   = RoPE(W_q · n1, pos)   k = RoPE(W_k · n1, pos)   v = W_v · n1
//!   cache.push(k, v)                                 (causal self-attention
//!   ctx = Attention(q, cached_keys, cached_values)    includes the new token)
//!   h1  = hidden + W_o · ctx                          (residual 1)
//!   n2  = RMSNorm_ffn(h1)                             (sovereign-rmsnorm)
//!   out = h1 + SwiGLU(n2)                             (sovereign-ffn, residual 2)
//! ```
//!
//! The two residual streams are the load-bearing structural invariant: with
//! the attention and FFN sublayers zeroed, the block is the identity, and
//! stacking blocks composes — both pinned as tests. Each call to
//! [`step`](DecoderBlock::step) consumes one token's hidden state, extends the
//! KV cache, and returns the updated hidden state, exactly as a real decoder
//! advances one position at a time.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_attention::{Attention, AttentionError};
use sovereign_ffn::{FfnError, SwiGlu};
use sovereign_rmsnorm::{RmsNorm, RmsNormError};
use sovereign_rope::{Rope, RopeError};
use thiserror::Error;

/// Schema version of the transformer-block surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong constructing or running a decoder block.
#[derive(Debug, Error, PartialEq)]
pub enum BlockError {
    /// A projection matrix had the wrong element count for its shape.
    #[error("projection '{which}' must be {expected} elements ({rows}x{cols}), got {got}")]
    WeightShape {
        /// Which projection (`q`, `k`, `v`, `o`).
        which: &'static str,
        /// Expected element count.
        expected: usize,
        /// Rows.
        rows: usize,
        /// Columns.
        cols: usize,
        /// Observed element count.
        got: usize,
    },
    /// The input hidden state had the wrong length.
    #[error("hidden dim mismatch: expected {expected}, got {got}")]
    HiddenDim {
        /// Configured model dimension.
        expected: usize,
        /// Observed length.
        got: usize,
    },
    /// An RMSNorm sub-error.
    #[error("rmsnorm: {0}")]
    RmsNorm(#[from] RmsNormError),
    /// A RoPE sub-error.
    #[error("rope: {0}")]
    Rope(#[from] RopeError),
    /// An attention sub-error.
    #[error("attention: {0}")]
    Attention(#[from] AttentionError),
    /// An FFN sub-error.
    #[error("ffn: {0}")]
    Ffn(#[from] FfnError),
}

/// The immutable weights of a decoder block.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BlockWeights {
    /// Model (residual-stream) dimension.
    pub model_dim: usize,
    /// Per-head attention dimension (even; RoPE rotates pairs).
    pub head_dim: usize,
    /// Pre-attention RMSNorm.
    pub attn_norm: RmsNorm,
    /// Pre-FFN RMSNorm.
    pub ffn_norm: RmsNorm,
    /// Query projection, row-major `head_dim × model_dim`.
    pub w_q: Vec<f32>,
    /// Key projection, row-major `head_dim × model_dim`.
    pub w_k: Vec<f32>,
    /// Value projection, row-major `head_dim × model_dim`.
    pub w_v: Vec<f32>,
    /// Output projection, row-major `model_dim × head_dim`.
    pub w_o: Vec<f32>,
    /// The SwiGLU feed-forward network (model_dim → model_dim).
    pub ffn: SwiGlu,
}

impl BlockWeights {
    /// Validate the projection shapes against `model_dim`/`head_dim`.
    fn validate(&self) -> Result<(), BlockError> {
        check("q", &self.w_q, self.head_dim, self.model_dim)?;
        check("k", &self.w_k, self.head_dim, self.model_dim)?;
        check("v", &self.w_v, self.head_dim, self.model_dim)?;
        check("o", &self.w_o, self.model_dim, self.head_dim)?;
        Ok(())
    }
}

fn check(which: &'static str, w: &[f32], rows: usize, cols: usize) -> Result<(), BlockError> {
    let expected = rows * cols;
    if w.len() != expected {
        return Err(BlockError::WeightShape {
            which,
            expected,
            rows,
            cols,
            got: w.len(),
        });
    }
    Ok(())
}

/// Row-major `rows × cols` matrix times a `cols`-vector → `rows`-vector.
fn matvec(w: &[f32], x: &[f32], rows: usize, cols: usize) -> Vec<f32> {
    let mut out = vec![0.0f32; rows];
    for (r, o) in out.iter_mut().enumerate() {
        let row = &w[r * cols..(r + 1) * cols];
        *o = row.iter().zip(x).map(|(a, b)| a * b).sum();
    }
    out
}

/// A decoder block plus its autoregressive KV cache.
#[derive(Debug, Clone)]
pub struct DecoderBlock {
    weights: BlockWeights,
    rope: Rope,
    attention: Attention,
    rotated_keys: Vec<Vec<f32>>,
    values: Vec<Vec<f32>>,
}

impl DecoderBlock {
    /// Assemble a decoder block from validated weights.
    pub fn new(weights: BlockWeights) -> Result<Self, BlockError> {
        weights.validate()?;
        let rope = Rope::new(weights.head_dim);
        let attention = Attention::new(weights.head_dim);
        Ok(Self {
            weights,
            rope,
            attention,
            rotated_keys: Vec::new(),
            values: Vec::new(),
        })
    }

    /// Number of positions in the KV cache.
    pub fn len(&self) -> usize {
        self.values.len()
    }

    /// Whether the cache is empty.
    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }

    /// Advance one position: consume a token's `hidden` state, extend the KV
    /// cache with this token's key/value (causal self-attention therefore
    /// includes the new token), and return the updated hidden state.
    pub fn step(&mut self, hidden: &[f32]) -> Result<Vec<f32>, BlockError> {
        let w = &self.weights;
        if hidden.len() != w.model_dim {
            return Err(BlockError::HiddenDim {
                expected: w.model_dim,
                got: hidden.len(),
            });
        }
        let pos = self.values.len();

        // --- attention sublayer (pre-norm) ---
        let n1 = w.attn_norm.normalize(hidden)?;
        let q = self
            .rope
            .rotate(&matvec(&w.w_q, &n1, w.head_dim, w.model_dim), pos)?;
        let k = self
            .rope
            .rotate(&matvec(&w.w_k, &n1, w.head_dim, w.model_dim), pos)?;
        let v = matvec(&w.w_v, &n1, w.head_dim, w.model_dim);
        self.rotated_keys.push(k);
        self.values.push(v);

        let ctx = self
            .attention
            .attend(&q, &self.rotated_keys, &self.values)?;
        let attn_out = matvec(&w.w_o, &ctx, w.model_dim, w.head_dim);
        // residual 1
        let h1: Vec<f32> = hidden.iter().zip(&attn_out).map(|(a, b)| a + b).collect();

        // --- feed-forward sublayer (pre-norm) ---
        let n2 = w.ffn_norm.normalize(&h1)?;
        let ffn_out = w.ffn.forward(&n2)?;
        // residual 2
        Ok(h1.iter().zip(&ffn_out).map(|(a, b)| a + b).collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A block whose attention + FFN sublayers are all-zero → identity block.
    fn zero_block(model_dim: usize, head_dim: usize) -> BlockWeights {
        BlockWeights {
            model_dim,
            head_dim,
            attn_norm: RmsNorm::new(model_dim),
            ffn_norm: RmsNorm::new(model_dim),
            w_q: vec![0.0; head_dim * model_dim],
            w_k: vec![0.0; head_dim * model_dim],
            w_v: vec![0.0; head_dim * model_dim],
            w_o: vec![0.0; model_dim * head_dim],
            ffn: SwiGlu::new(
                model_dim,
                model_dim,
                vec![0.0; model_dim * model_dim],
                vec![0.0; model_dim * model_dim],
                vec![0.0; model_dim * model_dim],
            )
            .unwrap(),
        }
    }

    /// A block with small non-trivial weights.
    fn small_block(model_dim: usize, head_dim: usize) -> BlockWeights {
        let qkv = |seed: f32| {
            (0..head_dim * model_dim)
                .map(|i| ((i as f32 + seed) * 0.01).sin())
                .collect::<Vec<_>>()
        };
        BlockWeights {
            model_dim,
            head_dim,
            attn_norm: RmsNorm::new(model_dim),
            ffn_norm: RmsNorm::new(model_dim),
            w_q: qkv(1.0),
            w_k: qkv(2.0),
            w_v: qkv(3.0),
            w_o: (0..model_dim * head_dim)
                .map(|i| ((i as f32) * 0.02).cos())
                .collect(),
            ffn: SwiGlu::new(
                model_dim,
                model_dim,
                (0..model_dim * model_dim)
                    .map(|i| (i as f32) * 0.01)
                    .collect(),
                (0..model_dim * model_dim)
                    .map(|i| (i as f32) * 0.02)
                    .collect(),
                (0..model_dim * model_dim)
                    .map(|i| (i as f32) * 0.015)
                    .collect(),
            )
            .unwrap(),
        }
    }

    #[test]
    fn output_keeps_model_dimension() {
        let mut block = DecoderBlock::new(small_block(4, 4)).unwrap();
        let out = block.step(&[0.1, 0.2, -0.3, 0.4]).unwrap();
        assert_eq!(out.len(), 4);
    }

    #[test]
    fn zeroed_sublayers_make_an_identity_block() {
        // Both residual paths add zero → output == input, every step.
        let mut block = DecoderBlock::new(zero_block(4, 4)).unwrap();
        for step in 0..5 {
            let x = vec![1.0 + step as f32, -2.0, 0.5, 3.0];
            let out = block.step(&x).unwrap();
            assert_eq!(out, x, "step {step} should be identity");
        }
    }

    #[test]
    fn cache_grows_one_per_step() {
        let mut block = DecoderBlock::new(small_block(4, 4)).unwrap();
        assert!(block.is_empty());
        block.step(&[0.1, 0.2, 0.3, 0.4]).unwrap();
        block.step(&[0.5, 0.6, 0.7, 0.8]).unwrap();
        assert_eq!(block.len(), 2);
    }

    #[test]
    fn stepping_is_deterministic() {
        let mut a = DecoderBlock::new(small_block(4, 4)).unwrap();
        let mut b = DecoderBlock::new(small_block(4, 4)).unwrap();
        let x = [0.3, -0.1, 0.7, 0.2];
        assert_eq!(a.step(&x).unwrap(), b.step(&x).unwrap());
    }

    #[test]
    fn output_is_finite_across_a_run() {
        let mut block = DecoderBlock::new(small_block(8, 8)).unwrap();
        for step in 0..16 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.3).sin()).collect();
            let out = block.step(&x).unwrap();
            assert!(out.iter().all(|v| v.is_finite()), "step {step}");
        }
    }

    #[test]
    fn blocks_stack() {
        // Output of block 1 feeds block 2 — a 2-layer stack runs end to end.
        let mut b1 = DecoderBlock::new(small_block(4, 4)).unwrap();
        let mut b2 = DecoderBlock::new(small_block(4, 4)).unwrap();
        let mut hidden = vec![0.2, 0.4, -0.1, 0.3];
        for _ in 0..4 {
            let h = b1.step(&hidden).unwrap();
            hidden = b2.step(&h).unwrap();
            assert_eq!(hidden.len(), 4);
            assert!(hidden.iter().all(|v| v.is_finite()));
        }
        assert_eq!(b1.len(), 4);
        assert_eq!(b2.len(), 4);
    }

    #[test]
    fn hidden_dim_mismatch_is_caught() {
        let mut block = DecoderBlock::new(small_block(4, 4)).unwrap();
        assert_eq!(
            block.step(&[1.0, 2.0]).unwrap_err(),
            BlockError::HiddenDim {
                expected: 4,
                got: 2
            }
        );
    }

    #[test]
    fn bad_projection_shape_is_caught() {
        let mut w = zero_block(4, 4);
        w.w_q = vec![0.0; 3]; // wrong
        assert_eq!(
            DecoderBlock::new(w).unwrap_err(),
            BlockError::WeightShape {
                which: "q",
                expected: 16,
                rows: 4,
                cols: 4,
                got: 3
            }
        );
    }

    #[test]
    fn weights_serde_round_trip() {
        let w = small_block(4, 4);
        let j = serde_json::to_string(&w).unwrap();
        let back: BlockWeights = serde_json::from_str(&j).unwrap();
        assert_eq!(w, back);
    }
}
