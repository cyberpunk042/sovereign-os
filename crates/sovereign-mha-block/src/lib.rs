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
use sovereign_linear::{Linear, LinearError, NvfpRecipe, Precision};
use sovereign_mha::{Mha, MhaError};
use sovereign_nvfp4_runtime::QuantMatrix;
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
    /// Quantizing a KV-cache vector to NVFP4 failed.
    #[error("kv-cache quant: {0}")]
    KvQuant(String),
}

/// The autoregressive KV cache, either dense f32 or NVFP4-compressed. The
/// quantized variant stores each cached key/value vector at ~4.5 bits/param
/// (4-bit elements + per-16-block E4M3 scale) instead of 32, ~7× smaller, at
/// the cost of a bounded reconstruction error and a transient dequantization
/// when attention reads the cache.
#[derive(Debug, Clone)]
enum KvStore {
    Full(Vec<Vec<f32>>),
    Quant(Vec<QuantMatrix>),
}

impl KvStore {
    fn len(&self) -> usize {
        match self {
            KvStore::Full(v) => v.len(),
            KvStore::Quant(v) => v.len(),
        }
    }

    /// Append a vector, quantizing it (as a `1 × dim` matrix) when compressed.
    fn push(&mut self, vec: Vec<f32>) -> Result<(), MhaBlockError> {
        match self {
            KvStore::Full(s) => s.push(vec),
            KvStore::Quant(s) => {
                let dim = vec.len();
                let q = QuantMatrix::from_f32(&vec, 1, dim)
                    .map_err(|e| MhaBlockError::KvQuant(e.to_string()))?;
                s.push(q);
            }
        }
        Ok(())
    }

    /// Materialize the cached vectors as dense f32 (dequantizing if compressed)
    /// so attention can read them.
    fn materialize(&self) -> Vec<Vec<f32>> {
        match self {
            KvStore::Full(s) => s.clone(),
            KvStore::Quant(s) => s.iter().map(|q| q.dequantized_weights()).collect(),
        }
    }
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
    rotated_keys: KvStore,
    values: KvStore,
}

impl MhaDecoderBlock {
    /// Quantize `weights` into a runnable block at `precision`.
    pub fn from_weights(
        weights: &MhaBlockWeights,
        precision: Precision,
    ) -> Result<Self, MhaBlockError> {
        Self::from_weights_selective(weights, precision, &[])
    }

    /// Quantize `weights` at `precision`, but keep the projections named in
    /// `high_precision` (by `"q"/"k"/"v"/"o"/"gate"/"up"/"down"`) in dense
    /// f32. This is how M077 selective-HP is enforced at build time: pass the
    /// names that [`sovereign_linear::recommend_high_precision`] flagged and
    /// those sensitive projections skip quantization while the rest run at the
    /// quantized base precision. With an `f32` base, `high_precision` is a
    /// no-op (everything is already dense).
    pub fn from_weights_selective(
        weights: &MhaBlockWeights,
        precision: Precision,
        high_precision: &[&str],
    ) -> Result<Self, MhaBlockError> {
        let md = weights.model_dim;
        let hd = weights.head_dim;
        let hid = weights.hidden_dim;
        let q_dim = weights.num_q_heads * hd;
        let kv_dim = weights.num_kv_heads * hd;
        let mha = Mha::new(weights.num_q_heads, weights.num_kv_heads, hd)?;
        // A flagged projection builds at dense f32; otherwise NVFP4 auto-selects
        // its M077 recipe (plain / RHT / 2D) and other precisions build their
        // single backend directly.
        let build =
            |name: &str, w: &[f32], out: usize, inp: usize| -> Result<Linear, LinearError> {
                if high_precision.contains(&name) {
                    return Linear::from_f32(w, out, inp, Precision::F32);
                }
                match precision {
                    Precision::Nvfp4 => Linear::from_f32_nvfp4_auto(w, out, inp),
                    _ => Linear::from_f32(w, out, inp, precision),
                }
            };
        Ok(Self {
            model_dim: md,
            head_dim: hd,
            num_q_heads: weights.num_q_heads,
            num_kv_heads: weights.num_kv_heads,
            precision,
            attn_norm: weights.attn_norm.clone(),
            ffn_norm: weights.ffn_norm.clone(),
            q: build("q", &weights.w_q, q_dim, md)?,
            k: build("k", &weights.w_k, kv_dim, md)?,
            v: build("v", &weights.w_v, kv_dim, md)?,
            o: build("o", &weights.w_o, md, q_dim)?,
            gate: build("gate", &weights.w_gate, hid, md)?,
            up: build("up", &weights.w_up, hid, md)?,
            down: build("down", &weights.w_down, md, hid)?,
            rope: Rope::new(hd),
            mha,
            rotated_keys: KvStore::Full(Vec::new()),
            values: KvStore::Full(Vec::new()),
        })
    }

    /// Switch this block to an **NVFP4-compressed KV cache** (default is dense
    /// f32). Each cached key/value vector is stored at ~4.5 bits/param instead
    /// of 32 — about 7× smaller — trading a bounded reconstruction error and a
    /// transient dequantization at attention time for the memory saving. Must
    /// be called before any `step` (the cache must be empty).
    pub fn with_quantized_kv(mut self) -> Self {
        self.rotated_keys = KvStore::Quant(Vec::new());
        self.values = KvStore::Quant(Vec::new());
        self
    }

    /// Whether this block stores its KV cache NVFP4-compressed.
    pub fn kv_quantized(&self) -> bool {
        matches!(self.values, KvStore::Quant(_))
    }

    /// Extend this block's usable context from `train_ctx` to `target_ctx` by
    /// RoPE linear position interpolation — positions are compressed back into
    /// the trained rotation range so longer sequences stay in-distribution
    /// (default is no scaling). Must be called before any `step`.
    pub fn with_context_extension(mut self, train_ctx: usize, target_ctx: usize) -> Self {
        self.rope = Rope::for_context_extension(self.head_dim, train_ctx, target_ctx);
        self
    }

    /// The RoPE position-interpolation scale in effect (`1.0` = no extension).
    pub fn rope_position_scale(&self) -> f32 {
        self.rope.position_scale
    }

    /// The execution precision.
    pub fn precision(&self) -> Precision {
        self.precision
    }

    /// The M077 NVFP4 recipe each projection auto-selected, as
    /// `(name, recipe)` pairs, or empty when the block is not NVFP4. Lets the
    /// engine report which projections needed RHT / 2D over plain microscaling.
    pub fn nvfp4_recipes(&self) -> Vec<(&'static str, NvfpRecipe)> {
        [
            ("q", &self.q),
            ("k", &self.k),
            ("v", &self.v),
            ("o", &self.o),
            ("gate", &self.gate),
            ("up", &self.up),
            ("down", &self.down),
        ]
        .into_iter()
        .filter_map(|(name, lin)| lin.nvfp4_recipe().map(|r| (name, r)))
        .collect()
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
        self.values.len() == 0
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
        self.rotated_keys.push(k)?;
        self.values.push(v)?;

        let keys = self.rotated_keys.materialize();
        let vals = self.values.materialize();
        let ctx = self.mha.attend(&q, &keys, &vals)?;
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
    fn nvfp4_block_reports_a_recipe_per_projection() {
        // An NVFP4 block auto-selects a recipe for all 7 projections; an F32
        // block reports none.
        let w = weights(8, 2, 4, 2, 16);
        let block = MhaDecoderBlock::from_weights(&w, Precision::Nvfp4).unwrap();
        let recipes = block.nvfp4_recipes();
        assert_eq!(recipes.len(), 7);
        assert!(
            recipes.iter().all(|(_, r)| matches!(
                r,
                NvfpRecipe::Plain | NvfpRecipe::Rht(_) | NvfpRecipe::TwoD
            ))
        );
        let f32_block = MhaDecoderBlock::from_weights(&w, Precision::F32).unwrap();
        assert!(f32_block.nvfp4_recipes().is_empty());
    }

    #[test]
    fn selective_hp_keeps_flagged_projection_dense() {
        // An NVFP4 block with "gate" flagged high-precision builds 6 NVFP4
        // projections + a dense f32 gate; the flagged one has no NVFP4 recipe.
        let w = weights(8, 2, 4, 2, 16);
        let block =
            MhaDecoderBlock::from_weights_selective(&w, Precision::Nvfp4, &["gate"]).unwrap();
        let recipes = block.nvfp4_recipes();
        assert_eq!(recipes.len(), 6, "gate should be dense: {recipes:?}");
        assert!(
            !recipes.iter().any(|(n, _)| *n == "gate"),
            "gate must not have an NVFP4 recipe: {recipes:?}"
        );
        assert!(recipes.iter().any(|(n, _)| *n == "up"));
        // Still runs end-to-end with mixed precision inside one block.
        let mut block = block;
        let x: Vec<f32> = (0..8).map(|i| (i as f32 * 0.2).sin()).collect();
        assert!(block.step(&x).unwrap().iter().all(|v| v.is_finite()));
    }

    #[test]
    fn selective_hp_empty_matches_plain_nvfp4() {
        // An empty HP set is identical to a plain NVFP4 block: all 7 quantized.
        let w = weights(8, 2, 4, 2, 16);
        let a = MhaDecoderBlock::from_weights(&w, Precision::Nvfp4).unwrap();
        let b = MhaDecoderBlock::from_weights_selective(&w, Precision::Nvfp4, &[]).unwrap();
        assert_eq!(a.nvfp4_recipes(), b.nvfp4_recipes());
        assert_eq!(b.nvfp4_recipes().len(), 7);
    }

    #[test]
    fn quantized_kv_cache_runs_and_tracks_length() {
        let w = weights(8, 2, 4, 2, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_quantized_kv();
        assert!(block.kv_quantized());
        assert!(block.is_empty());
        for step in 0..6 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            let y = block.step(&x).unwrap();
            assert_eq!(y.len(), 8);
            assert!(y.iter().all(|v| v.is_finite()));
        }
        assert_eq!(block.len(), 6);
    }

    #[test]
    fn quantized_kv_stays_close_to_full_cache() {
        // model_dim 16, num_kv 4 × head_dim 4 → 16-wide KV vectors that fill one
        // NVFP4 block exactly (the realistic case). The compressed cache should
        // track the dense-f32 cache: small relative deviation, never diverging.
        let w = weights(16, 4, 4, 4, 16);
        let mut full = MhaDecoderBlock::from_weights(&w, Precision::F32).unwrap();
        let mut quant = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_quantized_kv();
        let (mut max_dev, mut max_mag) = (0.0f32, 1e-6f32);
        for step in 0..5 {
            let x: Vec<f32> = (0..16).map(|i| ((i + step) as f32 * 0.3).sin()).collect();
            let a = full.step(&x).unwrap();
            let b = quant.step(&x).unwrap();
            for (p, q) in a.iter().zip(&b) {
                max_dev = max_dev.max((p - q).abs());
                max_mag = max_mag.max(p.abs());
            }
        }
        // Relative deviation stays modest with a full-block NVFP4 cache.
        let rel = max_dev / max_mag;
        assert!(
            rel < 0.15,
            "quantized-KV relative deviation {rel} too large"
        );
        assert!(!full.kv_quantized() && quant.kv_quantized());
    }

    #[test]
    fn context_extended_block_runs_finite() {
        // RoPE position interpolation: 1024 → 4096 → scale 0.25, block decodes
        // finite at extended positions.
        let w = weights(8, 2, 4, 2, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_context_extension(1024, 4096);
        assert!((block.rope_position_scale() - 0.25).abs() < 1e-6);
        for step in 0..5 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            assert!(block.step(&x).unwrap().iter().all(|v| v.is_finite()));
        }
        // A plain block has no scaling.
        assert_eq!(
            MhaDecoderBlock::from_weights(&w, Precision::F32)
                .unwrap()
                .rope_position_scale(),
            1.0
        );
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
