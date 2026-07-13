//! `sovereign-bounded-block` — a decoder block that runs forever in O(1) memory.
//!
//! Every other decoder block grows its KV cache by one entry per step, so a
//! long enough generation eventually exhausts memory. This block swaps that
//! unbounded cache for a [`WindowedKv`] — first `sinks` tokens plus the most
//! recent `window` — so its memory and per-step attention cost are *capped*
//! no matter how many tokens pass through it. That is what makes the
//! operator's endless operation actually endless.
//!
//! The structure is otherwise identical to [`sovereign-quant-block`]:
//! pre-norm RMSNorm → precision-generic Q/K/V projection → per-head RoPE →
//! causal self-attention over the retained window → output projection →
//! residual → RMSNorm → SwiGLU → residual. Because keys are stored already
//! rotated by their absolute position, eviction is sound: each retained key
//! keeps its position phase, and the relative-position property holds over the
//! window. While the total tokens seen stays within `sinks + window`, nothing
//! is evicted and the block reproduces the unbounded quant-block exactly —
//! pinned as a cross-crate test.
//!
//! [`sovereign-quant-block`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-quant-block
//! [`WindowedKv`]: sovereign_kv_window::WindowedKv
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_attention::{Attention, AttentionError};
use sovereign_ffn::silu;
use sovereign_kv_window::{WindowError, WindowedKv};
use sovereign_linear::{Linear, LinearError, Precision};
use sovereign_rmsnorm::{RmsNorm, RmsNormError};
use sovereign_rope::{Rope, RopeError};
use thiserror::Error;

/// Schema version of the bounded-block surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong building or running a bounded decoder block.
#[derive(Debug, Error, PartialEq)]
pub enum BoundedBlockError {
    /// The input hidden state had the wrong length.
    #[error("hidden dim mismatch: expected {expected}, got {got}")]
    HiddenDim {
        /// Configured model dimension.
        expected: usize,
        /// Observed length.
        got: usize,
    },
    /// A linear-layer error.
    #[error("linear: {0}")]
    Linear(#[from] LinearError),
    /// An RMSNorm error.
    #[error("rmsnorm: {0}")]
    RmsNorm(#[from] RmsNormError),
    /// A RoPE error.
    #[error("rope: {0}")]
    Rope(#[from] RopeError),
    /// An attention error.
    #[error("attention: {0}")]
    Attention(#[from] AttentionError),
    /// A windowed-cache error.
    #[error("kv window: {0}")]
    Window(#[from] WindowError),
}

/// f32 weights for a bounded block (row-major, single head: head_dim wide).
#[derive(Debug, Clone)]
pub struct BoundedBlockWeights {
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
    /// FFN gate, `hidden_dim × model_dim`.
    pub w_gate: Vec<f32>,
    /// FFN up, `hidden_dim × model_dim`.
    pub w_up: Vec<f32>,
    /// FFN down, `model_dim × hidden_dim`.
    pub w_down: Vec<f32>,
}

/// A bounded-memory decoder block: a sliding-window KV cache + the usual
/// pre-norm sublayers.
#[derive(Debug, Clone)]
pub struct BoundedDecoderBlock {
    model_dim: usize,
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
    cache: WindowedKv,
}

impl BoundedDecoderBlock {
    /// Quantize `weights` into a bounded block at `precision`, keeping `sinks`
    /// leading tokens and the most recent `window` tokens.
    pub fn from_weights(
        weights: &BoundedBlockWeights,
        precision: Precision,
        sinks: usize,
        window: usize,
    ) -> Result<Self, BoundedBlockError> {
        let md = weights.model_dim;
        let hd = weights.head_dim;
        let hid = weights.hidden_dim;
        Ok(Self {
            model_dim: md,
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
            cache: WindowedKv::new(sinks, window)?,
        })
    }

    /// The execution precision.
    pub fn precision(&self) -> Precision {
        self.precision
    }

    /// Maximum KV entries retained (`sinks + window`).
    pub fn capacity(&self) -> usize {
        self.cache.capacity()
    }

    /// Currently retained KV entries.
    pub fn retained(&self) -> usize {
        self.cache.retained()
    }

    /// Total tokens ever processed (including evicted positions).
    pub fn seen(&self) -> usize {
        self.cache.seen()
    }

    /// Advance one position and return the updated hidden state. Memory stays
    /// bounded by `capacity()` regardless of how many times this is called.
    pub fn step(&mut self, hidden: &[f32]) -> Result<Vec<f32>, BoundedBlockError> {
        if hidden.len() != self.model_dim {
            return Err(BoundedBlockError::HiddenDim {
                expected: self.model_dim,
                got: hidden.len(),
            });
        }
        // absolute position = tokens seen so far (matches the unbounded block)
        let pos = self.cache.seen();

        let n1 = self.attn_norm.normalize(hidden)?;
        let q = self.rope.rotate(&self.q.forward(&n1)?, pos)?;
        let k = self.rope.rotate(&self.k.forward(&n1)?, pos)?;
        let v = self.v.forward(&n1)?;
        // store the position-rotated key/value, then evict the middle if needed
        self.cache.push(k, v)?;

        let ctx = self
            .attention
            .attend(&q, self.cache.keys(), self.cache.values())?;
        let attn_out = self.o.forward(&ctx)?;
        let h1: Vec<f32> = hidden.iter().zip(&attn_out).map(|(a, b)| a + b).collect();

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

    const MD: usize = 4;

    fn mat(s: f32, n: usize) -> Vec<f32> {
        (0..n).map(|i| ((i as f32 + s) * 0.017).sin()).collect()
    }

    fn weights() -> BoundedBlockWeights {
        BoundedBlockWeights {
            model_dim: MD,
            head_dim: MD,
            hidden_dim: MD,
            attn_norm: RmsNorm::new(MD),
            ffn_norm: RmsNorm::new(MD),
            w_q: mat(1.0, MD * MD),
            w_k: mat(2.0, MD * MD),
            w_v: mat(3.0, MD * MD),
            w_o: mat(4.0, MD * MD),
            w_gate: mat(5.0, MD * MD),
            w_up: mat(6.0, MD * MD),
            w_down: mat(7.0, MD * MD),
        }
    }

    #[test]
    fn memory_stays_bounded_over_a_long_run() {
        let mut block =
            BoundedDecoderBlock::from_weights(&weights(), Precision::F32, 2, 8).unwrap();
        assert_eq!(block.capacity(), 10);
        for step in 0..5000 {
            let x: Vec<f32> = (0..MD).map(|i| ((i + step) as f32 * 0.21).sin()).collect();
            let y = block.step(&x).unwrap();
            assert!(y.iter().all(|v| v.is_finite()));
            assert!(
                block.retained() <= 10,
                "retained {} at step {step}",
                block.retained()
            );
        }
        assert_eq!(block.seen(), 5000);
        assert_eq!(block.retained(), 10);
    }

    #[test]
    fn within_window_matches_unbounded_quant_block() {
        use sovereign_quant_block::{QuantBlockWeights, QuantDecoderBlock};
        let w = weights();
        // window large enough that nothing is evicted over the test
        let mut bounded = BoundedDecoderBlock::from_weights(&w, Precision::F32, 0, 64).unwrap();
        let qw = QuantBlockWeights {
            model_dim: w.model_dim,
            head_dim: w.head_dim,
            hidden_dim: w.hidden_dim,
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
        let mut unbounded = QuantDecoderBlock::from_weights(&qw, Precision::F32).unwrap();

        for step in 0..16 {
            let x: Vec<f32> = (0..MD).map(|i| ((i + step) as f32 * 0.3).sin()).collect();
            let yb = bounded.step(&x).unwrap();
            let yu = unbounded.step(&x).unwrap();
            for (a, b) in yb.iter().zip(&yu) {
                assert!((a - b).abs() < 1e-5, "step {step}: {yb:?} vs {yu:?}");
            }
        }
    }

    #[test]
    fn ternary_bounded_block_runs() {
        let mut block =
            BoundedDecoderBlock::from_weights(&weights(), Precision::Ternary, 1, 4).unwrap();
        assert_eq!(block.precision(), Precision::Ternary);
        for step in 0..100 {
            let x: Vec<f32> = (0..MD).map(|i| ((i + step) as f32 * 0.2).cos()).collect();
            assert!(block.step(&x).unwrap().iter().all(|v| v.is_finite()));
        }
        assert!(block.retained() <= block.capacity());
    }

    #[test]
    fn hidden_dim_mismatch_is_caught() {
        let mut block =
            BoundedDecoderBlock::from_weights(&weights(), Precision::F32, 1, 4).unwrap();
        assert_eq!(
            block.step(&[1.0, 2.0]).unwrap_err(),
            BoundedBlockError::HiddenDim {
                expected: 4,
                got: 2
            }
        );
    }

    #[test]
    fn zero_window_is_rejected() {
        assert!(matches!(
            BoundedDecoderBlock::from_weights(&weights(), Precision::F32, 1, 0),
            Err(BoundedBlockError::Window(_))
        ));
    }
}
