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
//! [`sovereign-quant-block`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-quant-block
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_ffn::silu;
use sovereign_linear::{Linear, LinearError, NvfpRecipe, Precision};
use sovereign_mha::{Mha, MhaError};
use sovereign_moe_gate::top_k_gate;
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
    /// The MoE FFN was built with a malformed expert bank.
    #[error("moe config: {0}")]
    MoeConfig(String),
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

    /// Drop the cached vector at `idx` (for sliding-window / attention-sink
    /// eviction). No-op if `idx` is out of range.
    fn remove_at(&mut self, idx: usize) {
        match self {
            KvStore::Full(s) => {
                if idx < s.len() {
                    s.remove(idx);
                }
            }
            KvStore::Quant(s) => {
                if idx < s.len() {
                    s.remove(idx);
                }
            }
        }
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

/// A SwiGLU feed-forward network: `down( SiLU(gate(x)) ⊙ up(x) )`, run over an
/// already-normalized input. This is the single dense expert; a MoE block holds
/// a bank of these ([`MoeFfn`]).
#[derive(Debug, Clone)]
struct SwiGlu {
    gate: Linear,
    up: Linear,
    down: Linear,
}

impl SwiGlu {
    /// Run the SwiGLU on a pre-normalized vector.
    fn forward(&self, x: &[f32]) -> Result<Vec<f32>, MhaBlockError> {
        let gate = self.gate.forward(x)?;
        let up = self.up.forward(x)?;
        let act: Vec<f32> = gate.iter().zip(&up).map(|(g, u)| silu(*g) * u).collect();
        Ok(self.down.forward(&act)?)
    }
}

/// Logistic sigmoid, `1 / (1 + e^-x)`.
fn sigmoid(x: f32) -> f32 {
    1.0 / (1.0 + (-x).exp())
}

/// Add a bias vector to `v` in place when present (a no-op for `None`).
fn add_bias(v: &mut [f32], bias: &Option<Vec<f32>>) {
    if let Some(b) = bias {
        for (x, bb) in v.iter_mut().zip(b) {
            *x += bb;
        }
    }
}

/// The gated-activation an expert applies to `(gate, up)`.
#[derive(Debug, Clone, Copy, PartialEq)]
enum MoeActivation {
    /// Standard SwiGLU: `SiLU(gate) · up` (Mixtral / Qwen3-MoE).
    SwiGlu,
    /// GPT-OSS's clamped variant: `gate` capped at `limit`, `up` clamped to
    /// `±limit`, then `out = (up + 1) · (gate · σ(α·gate))`.
    GptOssClamped {
        /// GLU gate scale α (GPT-OSS uses `1.702`, the sigmoid-GELU approximation).
        alpha: f32,
        /// Clamp bound (`swiglu_limit`, GPT-OSS uses `7.0`).
        limit: f32,
    },
}

/// One MoE expert: a SwiGLU with optional per-projection biases (GPT-OSS has
/// them; Mixtral / Qwen3-MoE do not). The activation is chosen at the bank level.
#[derive(Debug, Clone)]
struct MoeExpert {
    gate: Linear,
    up: Linear,
    down: Linear,
    gate_bias: Option<Vec<f32>>,
    up_bias: Option<Vec<f32>>,
    down_bias: Option<Vec<f32>>,
}

impl MoeExpert {
    fn forward(&self, x: &[f32], act: MoeActivation) -> Result<Vec<f32>, MhaBlockError> {
        let mut gate = self.gate.forward(x)?;
        let mut up = self.up.forward(x)?;
        add_bias(&mut gate, &self.gate_bias);
        add_bias(&mut up, &self.up_bias);
        let activated: Vec<f32> = match act {
            MoeActivation::SwiGlu => gate.iter().zip(&up).map(|(g, u)| silu(*g) * u).collect(),
            MoeActivation::GptOssClamped { alpha, limit } => gate
                .iter()
                .zip(&up)
                .map(|(g, u)| {
                    let g = g.min(limit);
                    let u = u.clamp(-limit, limit);
                    (u + 1.0) * (g * sigmoid(alpha * g))
                })
                .collect(),
        };
        let mut out = self.down.forward(&activated)?;
        add_bias(&mut out, &self.down_bias);
        Ok(out)
    }
}

/// A mixture-of-experts feed-forward network: a router scores every expert, the
/// top-`experts_per_tok` are selected and softmax-weighted (via
/// [`sovereign_moe_gate::top_k_gate`]), and their expert outputs are blended by
/// weight into the residual-width output. Only the routed experts run per token
/// — the active-vs-total-parameter split that makes MoE memory-bound rather than
/// compute-bound, and thus a good local-inference fit. Carries an optional router
/// bias and a per-bank activation so both the standard (SwiGLU) and the GPT-OSS
/// (biased, clamped-α) FFN math run through one path.
#[derive(Debug, Clone)]
struct MoeFfn {
    /// Router projection, `num_experts × model_dim`, producing per-expert logits.
    router: Linear,
    /// Optional router bias, `[num_experts]` (GPT-OSS has one).
    router_bias: Option<Vec<f32>>,
    /// Expert banks, one per expert.
    experts: Vec<MoeExpert>,
    /// Number of experts activated per token (top-`k`).
    experts_per_tok: usize,
    /// Residual-stream dimension (each expert's output width).
    model_dim: usize,
    /// The gated activation the experts apply.
    activation: MoeActivation,
}

impl MoeFfn {
    /// Route a pre-normalized vector to its top-`k` experts and blend their
    /// outputs by softmax weight.
    fn forward(&self, x: &[f32]) -> Result<Vec<f32>, MhaBlockError> {
        let mut logits = self.router.forward(x)?;
        add_bias(&mut logits, &self.router_bias);
        let routing = top_k_gate(&logits, self.experts_per_tok);
        let mut out = vec![0.0f32; self.model_dim];
        for r in &routing {
            let expert = self.experts.get(r.expert).ok_or_else(|| {
                MhaBlockError::MoeConfig(format!(
                    "router selected expert {} but only {} experts exist",
                    r.expert,
                    self.experts.len()
                ))
            })?;
            let ey = expert.forward(x, self.activation)?;
            for (o, y) in out.iter_mut().zip(&ey) {
                *o += r.weight * y;
            }
        }
        Ok(out)
    }
}

/// The feed-forward sublayer of a decoder block: either a single dense SwiGLU
/// (the standard decoder) or a mixture-of-experts bank (the MoE decoder). Both
/// consume the FFN-normalized hidden state and return the residual-width FFN
/// output; the block adds it back into the residual stream identically either
/// way, so a MoE block drops into a [`LayerStack`] exactly as a dense one does.
///
/// [`LayerStack`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-decoder-layer
#[derive(Debug, Clone)]
enum Ffn {
    Dense(SwiGlu),
    Moe(MoeFfn),
}

impl Ffn {
    /// Run the FFN on a pre-normalized vector.
    fn forward(&self, x: &[f32]) -> Result<Vec<f32>, MhaBlockError> {
        match self {
            Ffn::Dense(swiglu) => swiglu.forward(x),
            Ffn::Moe(moe) => moe.forward(x),
        }
    }

    /// The NVFP4 recipe each FFN projection auto-selected, `(name, recipe)`, or
    /// empty when not NVFP4. Dense yields `gate/up/down`; MoE yields `router`
    /// plus each expert's `expert-{gate,up,down}`.
    fn nvfp4_recipes(&self) -> Vec<(&'static str, NvfpRecipe)> {
        match self {
            Ffn::Dense(s) => [("gate", &s.gate), ("up", &s.up), ("down", &s.down)]
                .into_iter()
                .filter_map(|(name, lin)| lin.nvfp4_recipe().map(|r| (name, r)))
                .collect(),
            Ffn::Moe(m) => {
                let mut out = Vec::new();
                if let Some(r) = m.router.nvfp4_recipe() {
                    out.push(("router", r));
                }
                for e in &m.experts {
                    for (name, lin) in [
                        ("expert-gate", &e.gate),
                        ("expert-up", &e.up),
                        ("expert-down", &e.down),
                    ] {
                        if let Some(r) = lin.nvfp4_recipe() {
                            out.push((name, r));
                        }
                    }
                }
                out
            }
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

/// f32 weights for a single MoE expert's SwiGLU FFN (row-major).
#[derive(Debug, Clone)]
pub struct MoeExpertWeights {
    /// Expert gate, `hidden_dim × model_dim`.
    pub w_gate: Vec<f32>,
    /// Expert up, `hidden_dim × model_dim`.
    pub w_up: Vec<f32>,
    /// Expert down, `model_dim × hidden_dim`.
    pub w_down: Vec<f32>,
}

/// f32 weights for a decoder block whose FFN is a mixture of experts
/// (row-major). The attention half is identical to [`MhaBlockWeights`]; the FFN
/// half is a router (scoring every expert) plus a bank of per-expert SwiGLUs, of
/// which only `experts_per_tok` run per token.
#[derive(Debug, Clone)]
pub struct MoeBlockWeights {
    /// Model (residual-stream) dimension.
    pub model_dim: usize,
    /// Per-head dimension (even).
    pub head_dim: usize,
    /// Number of query heads.
    pub num_q_heads: usize,
    /// Number of key/value heads (divides `num_q_heads`).
    pub num_kv_heads: usize,
    /// Per-expert FFN hidden dimension.
    pub hidden_dim: usize,
    /// Experts activated per token (top-`k`); clamped to the expert count.
    pub experts_per_tok: usize,
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
    /// Router projection, `num_experts × model_dim`, producing per-expert logits.
    pub w_router: Vec<f32>,
    /// Per-expert SwiGLU weights; `len()` is the number of experts.
    pub experts: Vec<MoeExpertWeights>,
}

/// Per-expert biases for a GPT-OSS MoE block (GPT-OSS biases every expert
/// projection; Mixtral / Qwen3-MoE do not). Row lengths: `gate`/`up` are the
/// per-expert hidden width, `down` is the model dimension.
#[derive(Debug, Clone)]
pub struct GptOssExpertBias {
    /// Gate bias, `[hidden_dim]`.
    pub gate: Vec<f32>,
    /// Up bias, `[hidden_dim]`.
    pub up: Vec<f32>,
    /// Down bias, `[model_dim]`.
    pub down: Vec<f32>,
}

/// GPT-OSS mixture-of-experts weights: the same attention + router + expert
/// weight matrices as [`MoeBlockWeights`], plus GPT-OSS's extras — a router
/// bias, per-expert projection biases, and the clamped-α SwiGLU activation
/// parameters. Build a block from this via
/// [`MhaDecoderBlock::from_weights_moe_gpt_oss`].
///
/// The activation GPT-OSS runs is `out = (up + 1) · (gate · σ(α·gate))` with
/// `gate` capped at `limit` and `up` clamped to `±limit` — distinct from the
/// standard `SiLU(gate)·up`. `alpha` is `1.702`, `limit` (`swiglu_limit`) is
/// `7.0` in the released checkpoints.
#[derive(Debug, Clone)]
pub struct GptOssMoeWeights {
    /// Attention + router + expert weight matrices (the router and experts here
    /// are the de-interleaved gate/up/down, exactly as [`from_weights_moe`] takes).
    ///
    /// [`from_weights_moe`]: MhaDecoderBlock::from_weights_moe
    pub base: MoeBlockWeights,
    /// Router bias, `[num_experts]`.
    pub router_bias: Vec<f32>,
    /// Per-expert projection biases; `len()` must equal `base.experts.len()`.
    pub expert_biases: Vec<GptOssExpertBias>,
    /// GLU gate scale α (GPT-OSS: `1.702`).
    pub alpha: f32,
    /// Clamp bound `swiglu_limit` (GPT-OSS: `7.0`).
    pub limit: f32,
    /// Attention Q-projection bias, `[num_q_heads·head_dim]` (GPT-OSS). `None`
    /// leaves attention unbiased.
    pub attn_q_bias: Option<Vec<f32>>,
    /// Attention K-projection bias, `[num_kv_heads·head_dim]`.
    pub attn_k_bias: Option<Vec<f32>>,
    /// Attention V-projection bias, `[num_kv_heads·head_dim]`.
    pub attn_v_bias: Option<Vec<f32>>,
    /// Attention output-projection bias, `[model_dim]`.
    pub attn_o_bias: Option<Vec<f32>>,
    /// Per-query-head learned attention-sink logits, `[num_q_heads]`. `None`
    /// leaves the softmax standard.
    pub attn_sinks: Option<Vec<f32>>,
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
    /// Optional attention-projection biases (GPT-OSS biases q/k/v/o; Llama/Qwen
    /// do not). Applied right after each projection — q/k/v before RoPE, o after.
    q_bias: Option<Vec<f32>>,
    k_bias: Option<Vec<f32>>,
    v_bias: Option<Vec<f32>>,
    o_bias: Option<Vec<f32>>,
    /// Optional per-query-head learned **attention sink** logits (GPT-OSS): each
    /// head's softmax denominator gains its sink term, letting it attend to
    /// "nothing". `None` = standard softmax.
    attn_sinks: Option<Vec<f32>>,
    ffn: Ffn,
    rope: Rope,
    mha: Mha,
    rotated_keys: KvStore,
    values: KvStore,
    /// Sliding-window attention span: when set, each step attends to (and
    /// retains) only the most recent `window` positions. `None` = full causal.
    window: Option<usize>,
    /// Number of initial "attention-sink" positions always kept in the cache
    /// (StreamingLLM): eviction never drops the first `sink_count` entries, so
    /// the window holds `sink_count` sinks + the most recent positions.
    sink_count: usize,
    /// Absolute positions processed so far (the RoPE position counter), which
    /// keeps advancing even as the windowed cache drops old entries.
    position: usize,
}

/// The RoPE position-scaling family a model config asks for (HuggingFace
/// `rope_scaling.rope_type`). Applied on top of the frequency base
/// (`rope_theta`) by [`MhaDecoderBlock::with_rope`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RopeScalingKind {
    /// Linear position interpolation (`type: "linear"`): divide every position
    /// by `factor` so an extended context compresses into the trained range.
    Linear,
    /// Dynamic NTK (`type: "dynamic"`): raise the frequency base by `factor`.
    Dynamic,
    /// YaRN (`type: "yarn"`): NTK-by-parts per-frequency interpolation.
    Yarn,
    /// Llama-3 frequency smoothing (`type: "llama3"`). The base theta is applied
    /// exactly; the low/high-frequency ramp is not yet modeled by
    /// [`sovereign_rope`], so extension beyond the trained context is
    /// approximate (honest partial support — short-context is exact).
    Llama3,
}

/// A resolved RoPE scaling request. Built by the model loader from the config's
/// `rope_scaling` block and handed to [`MhaDecoderBlock::with_rope`]. Plain data
/// (no serde) — the config-parsing layer owns deserialization.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RopeScaling {
    /// Which scaling family to apply.
    pub kind: RopeScalingKind,
    /// The scaling factor (`rope_scaling.factor`, e.g. 8.0 for Llama-3.1).
    pub factor: f32,
    /// The model's trained context (`original_max_position_embeddings`), needed
    /// by YaRN; `None` when the config omits it.
    pub original_ctx: Option<usize>,
    /// YaRN high-frequency ramp threshold (`beta_fast`, default 32).
    pub beta_fast: f32,
    /// YaRN low-frequency ramp threshold (`beta_slow`, default 1).
    pub beta_slow: f32,
}

impl RopeScaling {
    /// A scaling request with the canonical YaRN ramp defaults (`beta_fast = 32`,
    /// `beta_slow = 1`).
    pub fn new(kind: RopeScalingKind, factor: f32, original_ctx: Option<usize>) -> Self {
        Self {
            kind,
            factor,
            original_ctx,
            beta_fast: 32.0,
            beta_slow: 1.0,
        }
    }
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
            q_bias: None,
            k_bias: None,
            v_bias: None,
            o_bias: None,
            attn_sinks: None,
            ffn: Ffn::Dense(SwiGlu {
                gate: build("gate", &weights.w_gate, hid, md)?,
                up: build("up", &weights.w_up, hid, md)?,
                down: build("down", &weights.w_down, md, hid)?,
            }),
            rope: Rope::new(hd),
            mha,
            rotated_keys: KvStore::Full(Vec::new()),
            values: KvStore::Full(Vec::new()),
            window: None,
            sink_count: 0,
            position: 0,
        })
    }

    /// Quantize a **mixture-of-experts** decoder block at `precision`. The
    /// attention half is built exactly as [`from_weights`](Self::from_weights);
    /// the FFN half is a router plus a bank of per-expert SwiGLUs. At `step`
    /// time the router scores every expert, the top-`experts_per_tok` are
    /// selected and softmax-weighted, and only those experts run — the
    /// active-vs-total-parameter split that makes MoE the memory-bound,
    /// local-inference-friendly architecture. The block still implements the
    /// same [`DecoderLayer`] contract, so a MoE block composes into a
    /// [`LayerStack`] beside dense ones with no wiring change.
    ///
    /// Errors if the expert bank is empty or `experts_per_tok` is zero.
    ///
    /// [`DecoderLayer`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-decoder-layer
    /// [`LayerStack`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-decoder-layer
    pub fn from_weights_moe(
        weights: &MoeBlockWeights,
        precision: Precision,
    ) -> Result<Self, MhaBlockError> {
        let md = weights.model_dim;
        let hd = weights.head_dim;
        let hid = weights.hidden_dim;
        let q_dim = weights.num_q_heads * hd;
        let kv_dim = weights.num_kv_heads * hd;
        let num_experts = weights.experts.len();
        if num_experts == 0 {
            return Err(MhaBlockError::MoeConfig(
                "MoE block needs at least one expert".to_string(),
            ));
        }
        if weights.experts_per_tok == 0 {
            return Err(MhaBlockError::MoeConfig(
                "experts_per_tok must be at least 1".to_string(),
            ));
        }
        let mha = Mha::new(weights.num_q_heads, weights.num_kv_heads, hd)?;
        // MoE weights build at the base precision (no selective-HP list — that
        // is a dense-path concern for now).
        let build = |w: &[f32], out: usize, inp: usize| -> Result<Linear, LinearError> {
            match precision {
                Precision::Nvfp4 => Linear::from_f32_nvfp4_auto(w, out, inp),
                _ => Linear::from_f32(w, out, inp, precision),
            }
        };
        let router = build(&weights.w_router, num_experts, md)?;
        let mut experts = Vec::with_capacity(num_experts);
        for e in &weights.experts {
            experts.push(MoeExpert {
                gate: build(&e.w_gate, hid, md)?,
                up: build(&e.w_up, hid, md)?,
                down: build(&e.w_down, md, hid)?,
                gate_bias: None,
                up_bias: None,
                down_bias: None,
            });
        }
        Ok(Self {
            model_dim: md,
            head_dim: hd,
            num_q_heads: weights.num_q_heads,
            num_kv_heads: weights.num_kv_heads,
            precision,
            attn_norm: weights.attn_norm.clone(),
            ffn_norm: weights.ffn_norm.clone(),
            q: build(&weights.w_q, q_dim, md)?,
            k: build(&weights.w_k, kv_dim, md)?,
            v: build(&weights.w_v, kv_dim, md)?,
            o: build(&weights.w_o, md, q_dim)?,
            q_bias: None,
            k_bias: None,
            v_bias: None,
            o_bias: None,
            attn_sinks: None,
            ffn: Ffn::Moe(MoeFfn {
                router,
                router_bias: None,
                experts,
                experts_per_tok: weights.experts_per_tok.min(num_experts),
                model_dim: md,
                activation: MoeActivation::SwiGlu,
            }),
            rope: Rope::new(hd),
            mha,
            rotated_keys: KvStore::Full(Vec::new()),
            values: KvStore::Full(Vec::new()),
            window: None,
            sink_count: 0,
            position: 0,
        })
    }

    /// Quantize a **GPT-OSS** mixture-of-experts block. Like
    /// [`from_weights_moe`](Self::from_weights_moe) but with GPT-OSS's FFN math:
    /// a router bias, per-expert projection biases, and the clamped-α SwiGLU
    /// activation (`out = (up+1)·(gate·σ(α·gate))`, gate capped at `limit`, up
    /// clamped to `±limit`). The attention half additionally applies GPT-OSS's
    /// optional q/k/v/o projection biases and per-query-head learned attention
    /// sinks when supplied (`None` leaves attention standard).
    ///
    /// Errors if the expert bank is empty, `experts_per_tok` is zero, or the
    /// per-expert bias count does not match the expert count.
    pub fn from_weights_moe_gpt_oss(
        weights: &GptOssMoeWeights,
        precision: Precision,
    ) -> Result<Self, MhaBlockError> {
        let base = &weights.base;
        let md = base.model_dim;
        let hd = base.head_dim;
        let hid = base.hidden_dim;
        let q_dim = base.num_q_heads * hd;
        let kv_dim = base.num_kv_heads * hd;
        let num_experts = base.experts.len();
        if num_experts == 0 {
            return Err(MhaBlockError::MoeConfig(
                "MoE block needs at least one expert".to_string(),
            ));
        }
        if base.experts_per_tok == 0 {
            return Err(MhaBlockError::MoeConfig(
                "experts_per_tok must be at least 1".to_string(),
            ));
        }
        if weights.expert_biases.len() != num_experts {
            return Err(MhaBlockError::MoeConfig(format!(
                "expert_biases ({}) must match experts ({num_experts})",
                weights.expert_biases.len()
            )));
        }
        let mha = Mha::new(base.num_q_heads, base.num_kv_heads, hd)?;
        let build = |w: &[f32], out: usize, inp: usize| -> Result<Linear, LinearError> {
            match precision {
                Precision::Nvfp4 => Linear::from_f32_nvfp4_auto(w, out, inp),
                _ => Linear::from_f32(w, out, inp, precision),
            }
        };
        let router = build(&base.w_router, num_experts, md)?;
        let mut experts = Vec::with_capacity(num_experts);
        for (e, b) in base.experts.iter().zip(&weights.expert_biases) {
            experts.push(MoeExpert {
                gate: build(&e.w_gate, hid, md)?,
                up: build(&e.w_up, hid, md)?,
                down: build(&e.w_down, md, hid)?,
                gate_bias: Some(b.gate.clone()),
                up_bias: Some(b.up.clone()),
                down_bias: Some(b.down.clone()),
            });
        }
        Ok(Self {
            model_dim: md,
            head_dim: hd,
            num_q_heads: base.num_q_heads,
            num_kv_heads: base.num_kv_heads,
            precision,
            attn_norm: base.attn_norm.clone(),
            ffn_norm: base.ffn_norm.clone(),
            q: build(&base.w_q, q_dim, md)?,
            k: build(&base.w_k, kv_dim, md)?,
            v: build(&base.w_v, kv_dim, md)?,
            o: build(&base.w_o, md, q_dim)?,
            q_bias: weights.attn_q_bias.clone(),
            k_bias: weights.attn_k_bias.clone(),
            v_bias: weights.attn_v_bias.clone(),
            o_bias: weights.attn_o_bias.clone(),
            attn_sinks: weights.attn_sinks.clone(),
            ffn: Ffn::Moe(MoeFfn {
                router,
                router_bias: Some(weights.router_bias.clone()),
                experts,
                experts_per_tok: base.experts_per_tok.min(num_experts),
                model_dim: md,
                activation: MoeActivation::GptOssClamped {
                    alpha: weights.alpha,
                    limit: weights.limit,
                },
            }),
            rope: Rope::new(hd),
            mha,
            rotated_keys: KvStore::Full(Vec::new()),
            values: KvStore::Full(Vec::new()),
            window: None,
            sink_count: 0,
            position: 0,
        })
    }

    /// Whether this block's FFN is a mixture of experts (vs a single dense
    /// SwiGLU).
    pub fn is_moe(&self) -> bool {
        matches!(self.ffn, Ffn::Moe(_))
    }

    /// Number of experts in this block's MoE FFN, or `0` if it is dense.
    pub fn num_experts(&self) -> usize {
        match &self.ffn {
            Ffn::Moe(m) => m.experts.len(),
            Ffn::Dense(_) => 0,
        }
    }

    /// Experts activated per token (top-`k`), or `0` if this block is dense.
    pub fn experts_per_tok(&self) -> usize {
        match &self.ffn {
            Ffn::Moe(m) => m.experts_per_tok,
            Ffn::Dense(_) => 0,
        }
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

    /// Extend this block's usable context from `train_ctx` to `target_ctx` with
    /// **YaRN** (NTK-by-parts) RoPE scaling — per-frequency interpolation that
    /// preserves high-frequency (local) resolution while extending range,
    /// outperforming the uniform [`with_context_extension`](Self::with_context_extension)
    /// (position interpolation). Uses the canonical ramp thresholds `α=1, β=32`.
    /// Must be called before any `step`.
    pub fn with_yarn_context(mut self, train_ctx: usize, target_ctx: usize) -> Self {
        self.rope = Rope::with_yarn(
            self.head_dim,
            sovereign_rope::DEFAULT_THETA_BASE,
            train_ctx,
            target_ctx,
            1.0,
            32.0,
        );
        self
    }

    /// Whether this block uses YaRN RoPE scaling.
    pub fn rope_is_yarn(&self) -> bool {
        self.rope.yarn_train > 0
    }

    /// Set the RoPE frequency base (`rope_theta`) and, optionally, a scaling
    /// family — the config-driven replacement for the hardcoded base-10000
    /// [`Rope::new`] the block defaults to. This is THE fix for running modern
    /// models: Llama-3 (500000), Qwen2 (1000000), Mistral, etc. all train with a
    /// non-default base, and decoding them at 10000 produces incoherent output.
    /// Must be called before any `step` (it rebuilds the RoPE head).
    ///
    /// Scaling is applied on top of the base per [`RopeScalingKind`]. `None`
    /// (the common case — most base models ship no `rope_scaling`) uses the base
    /// alone.
    pub fn with_rope(mut self, theta_base: f32, scaling: Option<&RopeScaling>) -> Self {
        let hd = self.head_dim;
        self.rope = match scaling {
            None => Rope::with_base(hd, theta_base),
            Some(s) => match s.kind {
                RopeScalingKind::Linear => {
                    // Position interpolation: compress positions by `factor`.
                    let mut r = Rope::with_base(hd, theta_base);
                    if s.factor > 0.0 {
                        r.position_scale = 1.0 / s.factor;
                    }
                    r
                }
                RopeScalingKind::Dynamic => {
                    // Dynamic NTK: stretch the base so low-frequency pairs cover
                    // the extended context.
                    let base = sovereign_rope::ntk_aware_base(hd, theta_base, s.factor.max(1.0));
                    Rope::with_base(hd, base)
                }
                RopeScalingKind::Yarn => {
                    let train = s.original_ctx.unwrap_or(0);
                    let target = ((train as f32) * s.factor.max(1.0)) as usize;
                    if train > 0 && target > train && s.beta_fast > s.beta_slow {
                        // with_yarn(head_dim, theta, train, target, alpha, beta):
                        // alpha is the low-freq threshold (beta_slow), beta the
                        // high-freq threshold (beta_fast).
                        Rope::with_yarn(hd, theta_base, train, target, s.beta_slow, s.beta_fast)
                    } else {
                        // Not enough info to model YaRN — the correct base is
                        // still the dominant win (honest partial support).
                        Rope::with_base(hd, theta_base)
                    }
                }
                RopeScalingKind::Llama3 => {
                    // The base theta is exact; the llama3 low/high-freq ramp is
                    // not yet modeled (short-context generation is coherent).
                    Rope::with_base(hd, theta_base)
                }
            },
        };
        self
    }

    /// The RoPE frequency base (`theta_base`) in effect (10000 by default).
    pub fn rope_theta_base(&self) -> f32 {
        self.rope.theta_base
    }

    /// Enable **sliding-window attention** with span `window`: each step
    /// attends to (and the cache retains) only the most recent `window`
    /// positions, bounding both attention cost and KV-cache memory at long
    /// context (Mistral-style local attention). Default is full causal
    /// attention. Must be called before any `step`.
    ///
    /// # Panics
    /// Panics if `window` is zero.
    pub fn with_sliding_window(mut self, window: usize) -> Self {
        assert!(window > 0, "sliding window must be > 0");
        self.window = Some(window);
        self
    }

    /// The sliding-window span, or `None` for full causal attention.
    pub fn sliding_window(&self) -> Option<usize> {
        self.window
    }

    /// Keep the first `sinks` positions permanently cached as **attention
    /// sinks** (StreamingLLM): under a sliding window, eviction preserves these
    /// initial tokens (which absorb a large share of attention mass) instead of
    /// dropping them, fixing the quality collapse of naive window eviction.
    /// Only meaningful with a sliding window; `sinks` is capped at the window.
    /// Must be called before any `step`.
    pub fn with_attention_sinks(mut self, sinks: usize) -> Self {
        self.sink_count = sinks;
        self
    }

    /// Number of attention-sink positions kept (`0` = none).
    pub fn attention_sinks(&self) -> usize {
        self.sink_count
    }

    /// Number of key/value vectors currently held in the cache (bounded by the
    /// sliding window when one is set; equals [`len`](Self::len) otherwise).
    pub fn cache_len(&self) -> usize {
        self.values.len()
    }

    /// The execution precision.
    pub fn precision(&self) -> Precision {
        self.precision
    }

    /// The M077 NVFP4 recipe each projection auto-selected, as
    /// `(name, recipe)` pairs, or empty when the block is not NVFP4. Lets the
    /// engine report which projections needed RHT / 2D over plain microscaling.
    pub fn nvfp4_recipes(&self) -> Vec<(&'static str, NvfpRecipe)> {
        let mut out: Vec<(&'static str, NvfpRecipe)> = [
            ("q", &self.q),
            ("k", &self.k),
            ("v", &self.v),
            ("o", &self.o),
        ]
        .into_iter()
        .filter_map(|(name, lin)| lin.nvfp4_recipe().map(|r| (name, r)))
        .collect();
        out.extend(self.ffn.nvfp4_recipes());
        out
    }

    /// Number of query heads.
    pub fn num_q_heads(&self) -> usize {
        self.num_q_heads
    }

    /// Number of key/value heads.
    pub fn num_kv_heads(&self) -> usize {
        self.num_kv_heads
    }

    /// Number of positions processed (advances even when the sliding window
    /// evicts old cache entries; see [`cache_len`](Self::cache_len) for the
    /// number actually held).
    pub fn len(&self) -> usize {
        self.position
    }

    /// Whether any position has been processed.
    pub fn is_empty(&self) -> bool {
        self.position == 0
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
        let pos = self.position;

        // attention sublayer (pre-norm)
        let n1 = self.attn_norm.normalize(hidden)?;
        let mut q = self.q.forward(&n1)?;
        let mut k = self.k.forward(&n1)?;
        let mut v = self.v.forward(&n1)?;
        // GPT-OSS attention biases (q/k/v before RoPE); no-op when unset.
        add_bias(&mut q, &self.q_bias);
        add_bias(&mut k, &self.k_bias);
        add_bias(&mut v, &self.v_bias);
        self.rope_heads(&mut q, self.num_q_heads, pos)?;
        self.rope_heads(&mut k, self.num_kv_heads, pos)?;
        self.rotated_keys.push(k)?;
        self.values.push(v)?;

        // Sliding-window eviction: keep only `window` entries. With attention
        // sinks, evict the oldest *non-sink* entry (index = sink_count) so the
        // first `sink_count` positions stay cached.
        if let Some(w) = self.window {
            let evict_idx = self.sink_count.min(w.saturating_sub(1));
            while self.values.len() > w {
                self.rotated_keys.remove_at(evict_idx);
                self.values.remove_at(evict_idx);
            }
        }
        self.position += 1;

        let keys = self.rotated_keys.materialize();
        let vals = self.values.materialize();
        // GPT-OSS per-head attention sinks when present, else standard softmax.
        let ctx = match &self.attn_sinks {
            Some(sinks) => self.mha.attend_with_sinks(&q, &keys, &vals, sinks)?,
            None => self.mha.attend(&q, &keys, &vals)?,
        };
        let mut attn_out = self.o.forward(&ctx)?;
        add_bias(&mut attn_out, &self.o_bias);
        let h1: Vec<f32> = hidden.iter().zip(&attn_out).map(|(a, b)| a + b).collect();

        // feed-forward sublayer (pre-norm) — dense SwiGLU or routed MoE bank.
        // Both consume the normalized state and return the residual-width FFN
        // output, added back into the residual stream identically.
        let n2 = self.ffn_norm.normalize(&h1)?;
        let ffn_out = self.ffn.forward(&n2)?;

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
    fn int8_block_runs_end_to_end_and_tracks_f32() {
        // The Zen-5 T1 tier: an INT8 (VNNI) block builds through the same
        // from_weights path, steps a sequence with finite outputs, and stays
        // close to the f32 reference block on the same inputs.
        let w = weights(8, 2, 4, 2, 16);
        let mut int8 = MhaDecoderBlock::from_weights(&w, Precision::Int8).unwrap();
        let mut dense = MhaDecoderBlock::from_weights(&w, Precision::F32).unwrap();
        assert_eq!(int8.precision(), Precision::Int8);
        assert!(int8.nvfp4_recipes().is_empty()); // not an NVFP4 block
        for step in 0..4 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            let yq = int8.step(&x).unwrap();
            let yf = dense.step(&x).unwrap();
            assert_eq!(yq.len(), 8);
            assert!(yq.iter().all(|v| v.is_finite()));
            // INT8 tracks f32 closely on this small well-conditioned block.
            let norm: f32 = yf.iter().map(|v| v * v).sum::<f32>().sqrt();
            for (a, b) in yf.iter().zip(&yq) {
                assert!(
                    (a - b).abs() < 0.05 * norm.max(1.0),
                    "step {step}: f32 {yf:?} vs int8 {yq:?}"
                );
            }
        }
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
    fn sliding_window_bounds_cache_and_tracks_position() {
        let w = weights(8, 2, 4, 2, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_sliding_window(2);
        assert_eq!(block.sliding_window(), Some(2));
        for step in 0..6 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            assert!(block.step(&x).unwrap().iter().all(|v| v.is_finite()));
            assert!(block.cache_len() <= 2, "cache must stay within the window");
        }
        assert_eq!(block.len(), 6); // positions keep advancing
        assert_eq!(block.cache_len(), 2); // but the cache is bounded
    }

    #[test]
    fn sliding_window_output_depends_only_on_the_window() {
        // Defining locality property: with window 2, the output after feeding a
        // shared last-2 suffix is identical regardless of earlier inputs.
        let w = weights(8, 2, 4, 2, 16);
        let shared = [
            vec![0.3f32, -0.2, 0.1, 0.4, -0.5, 0.2, 0.0, -0.1],
            vec![-0.1f32, 0.5, -0.3, 0.2, 0.1, -0.4, 0.3, 0.0],
        ];
        let run = |prefix: &[Vec<f32>]| -> Vec<f32> {
            let mut b = MhaDecoderBlock::from_weights(&w, Precision::F32)
                .unwrap()
                .with_sliding_window(2);
            let mut last = Vec::new();
            for x in prefix.iter().chain(shared.iter()) {
                last = b.step(x).unwrap();
            }
            last
        };
        let a = run(&[vec![1.0f32; 8], vec![-1.0f32; 8]]);
        let c = run(&[vec![0.2f32; 8], vec![0.7f32; 8], vec![-0.9f32; 8]]);
        assert_eq!(a.len(), c.len());
        for (x, y) in a.iter().zip(&c) {
            // RoPE makes attention depend only on relative offset, so the two
            // runs agree up to f32 rounding through different absolute angles.
            let tol = 1e-5 * x.abs().max(1.0);
            assert!(
                (x - y).abs() <= tol,
                "windowed output must depend only on the window: {x} vs {y}"
            );
        }
    }

    #[test]
    fn attention_sinks_retain_the_initial_token() {
        // window 3, 1 sink. Feed a distinguishing first token, then 5 identical
        // tokens. With a sink the first token stays cached, so its identity
        // still affects the output; pure SWA (no sink) would have evicted it and
        // the outputs would be identical.
        let w = weights(8, 2, 4, 2, 16);
        let tail: Vec<Vec<f32>> = (0..5)
            .map(|s| (0..8).map(|i| ((i + s) as f32 * 0.2).sin()).collect())
            .collect();
        let run = |first: &[f32], sinks: usize| -> Vec<f32> {
            let mut b = MhaDecoderBlock::from_weights(&w, Precision::F32)
                .unwrap()
                .with_sliding_window(3)
                .with_attention_sinks(sinks);
            let mut last = b.step(first).unwrap();
            for x in &tail {
                last = b.step(x).unwrap();
            }
            last
        };
        let first_a = vec![1.0f32; 8];
        let first_b = vec![-1.0f32; 8];

        // With a sink, the differing first token still moves the output.
        let with_sink_a = run(&first_a, 1);
        let with_sink_b = run(&first_b, 1);
        let sink_diff: f32 = with_sink_a
            .iter()
            .zip(&with_sink_b)
            .map(|(x, y)| (x - y).abs())
            .sum();
        assert!(
            sink_diff > 1e-3,
            "sink must keep the first token influential"
        );

        // Without a sink (pure SWA), the first token is evicted → outputs equal.
        let no_sink_a = run(&first_a, 0);
        let no_sink_b = run(&first_b, 0);
        for (x, y) in no_sink_a.iter().zip(&no_sink_b) {
            let tol = 1e-5 * x.abs().max(1.0);
            assert!((x - y).abs() <= tol, "pure SWA must have evicted token 0");
        }
    }

    #[test]
    fn all_long_context_optimizations_compose() {
        // The full streaming stack at once: NVFP4-compressed KV cache + sliding
        // window + attention sinks + RoPE context extension. They must compose
        // and decode finite with a bounded cache.
        let w = weights(16, 4, 4, 4, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::Nvfp4)
            .unwrap()
            .with_quantized_kv()
            .with_sliding_window(4)
            .with_attention_sinks(1)
            .with_context_extension(2048, 8192);
        assert!(block.kv_quantized());
        assert_eq!(block.sliding_window(), Some(4));
        assert_eq!(block.attention_sinks(), 1);
        assert!((block.rope_position_scale() - 0.25).abs() < 1e-6);
        for step in 0..12 {
            let x: Vec<f32> = (0..16).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            let y = block.step(&x).unwrap();
            assert_eq!(y.len(), 16);
            assert!(y.iter().all(|v| v.is_finite()));
            assert!(block.cache_len() <= 4);
        }
        assert_eq!(block.len(), 12);
    }

    #[test]
    fn attention_sinks_stay_within_window() {
        let w = weights(8, 2, 4, 2, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_sliding_window(3)
            .with_attention_sinks(1);
        assert_eq!(block.attention_sinks(), 1);
        for step in 0..8 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            assert!(block.step(&x).unwrap().iter().all(|v| v.is_finite()));
            assert!(block.cache_len() <= 3);
        }
        assert_eq!(block.len(), 8);
    }

    #[test]
    fn yarn_context_block_runs_finite() {
        // YaRN RoPE scaling 2048 → 8192; block decodes finite at extended
        // positions, and reports YaRN active (plain block does not).
        let w = weights(8, 2, 4, 2, 16);
        let mut block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_yarn_context(2048, 8192);
        assert!(block.rope_is_yarn());
        for step in 0..5 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            assert!(block.step(&x).unwrap().iter().all(|v| v.is_finite()));
        }
        assert!(
            !MhaDecoderBlock::from_weights(&w, Precision::F32)
                .unwrap()
                .rope_is_yarn()
        );
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

    #[test]
    fn default_rope_base_is_10000() {
        let w = weights(4, 4, 1, 1, 4);
        let block = MhaDecoderBlock::from_weights(&w, Precision::F32).unwrap();
        assert_eq!(block.rope_theta_base(), sovereign_rope::DEFAULT_THETA_BASE);
    }

    #[test]
    fn with_rope_sets_the_base_theta() {
        // The core fix: a Llama-3-style base must actually reach the RoPE head.
        let w = weights(4, 4, 1, 1, 4);
        let block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_rope(500000.0, None);
        assert_eq!(block.rope_theta_base(), 500000.0);
        assert_eq!(
            block.rope_position_scale(),
            1.0,
            "no scaling ⇒ unit position scale"
        );
        assert!(!block.rope_is_yarn());
    }

    #[test]
    fn with_rope_linear_scaling_sets_position_scale() {
        let w = weights(4, 4, 1, 1, 4);
        let s = RopeScaling::new(RopeScalingKind::Linear, 4.0, None);
        let block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_rope(10000.0, Some(&s));
        assert_eq!(block.rope_theta_base(), 10000.0, "linear keeps the base");
        assert_eq!(
            block.rope_position_scale(),
            0.25,
            "position_scale = 1/factor"
        );
    }

    #[test]
    fn with_rope_dynamic_ntk_raises_the_base() {
        let w = weights(4, 4, 1, 1, 4);
        let s = RopeScaling::new(RopeScalingKind::Dynamic, 8.0, None);
        let block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_rope(10000.0, Some(&s));
        assert!(
            block.rope_theta_base() > 10000.0,
            "dynamic-NTK stretches the base above the trained theta, got {}",
            block.rope_theta_base()
        );
        assert_eq!(block.rope_position_scale(), 1.0);
    }

    #[test]
    fn with_rope_yarn_engages_when_context_is_known() {
        let w = weights(4, 4, 1, 1, 4);
        let s = RopeScaling::new(RopeScalingKind::Yarn, 4.0, Some(2048));
        let block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_rope(10000.0, Some(&s));
        assert!(
            block.rope_is_yarn(),
            "YaRN should engage with a known original context"
        );
        assert_eq!(block.rope_theta_base(), 10000.0);
    }

    #[test]
    fn with_rope_yarn_falls_back_to_base_without_context() {
        let w = weights(4, 4, 1, 1, 4);
        let s = RopeScaling::new(RopeScalingKind::Yarn, 4.0, None); // no original_ctx
        let block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_rope(500000.0, Some(&s));
        assert!(
            !block.rope_is_yarn(),
            "no context ⇒ honest fallback, not fabricated YaRN"
        );
        assert_eq!(
            block.rope_theta_base(),
            500000.0,
            "the correct base still applies"
        );
    }

    #[test]
    fn with_rope_llama3_applies_base_only() {
        let w = weights(4, 4, 1, 1, 4);
        let s = RopeScaling::new(RopeScalingKind::Llama3, 8.0, Some(8192));
        let block = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_rope(500000.0, Some(&s));
        assert_eq!(block.rope_theta_base(), 500000.0);
        assert_eq!(
            block.rope_position_scale(),
            1.0,
            "base-only (honest partial support)"
        );
    }

    #[test]
    fn changing_the_base_changes_the_output() {
        // A different base must actually alter decode — proves the RoPE head is
        // wired, not a no-op field.
        let w = weights(8, 8, 2, 2, 8);
        let mut a = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_rope(10000.0, None);
        let mut b = MhaDecoderBlock::from_weights(&w, Precision::F32)
            .unwrap()
            .with_rope(500000.0, None);
        let h = mat(0.5, 8);
        // Prime a couple of positions so RoPE at pos>0 differentiates the bases.
        let _ = a.step(&h).unwrap();
        let _ = b.step(&h).unwrap();
        let oa = a.step(&h).unwrap();
        let ob = b.step(&h).unwrap();
        assert_ne!(
            oa, ob,
            "distinct RoPE bases must yield distinct decode output"
        );
    }

    // ---- Mixture-of-experts FFN --------------------------------------------

    /// A single-expert `MoeBlockWeights` whose expert SwiGLU mirrors the dense
    /// FFN in `dense`, with matching attention weights. Its top-1 gate softmaxes
    /// over one logit → weight `1.0`, so it must decode identically to the dense
    /// block built from `dense`.
    fn moe_mirror_of(dense: &MhaBlockWeights) -> MoeBlockWeights {
        MoeBlockWeights {
            model_dim: dense.model_dim,
            head_dim: dense.head_dim,
            num_q_heads: dense.num_q_heads,
            num_kv_heads: dense.num_kv_heads,
            hidden_dim: dense.hidden_dim,
            experts_per_tok: 1,
            attn_norm: dense.attn_norm.clone(),
            ffn_norm: dense.ffn_norm.clone(),
            w_q: dense.w_q.clone(),
            w_k: dense.w_k.clone(),
            w_v: dense.w_v.clone(),
            w_o: dense.w_o.clone(),
            w_router: mat(8.0, dense.model_dim), // 1 expert × model_dim
            experts: vec![MoeExpertWeights {
                w_gate: dense.w_gate.clone(),
                w_up: dense.w_up.clone(),
                w_down: dense.w_down.clone(),
            }],
        }
    }

    /// A multi-expert MoE block sharing the dense-helper attention weights, with
    /// `num_experts` distinct expert SwiGLUs and a per-expert router.
    fn moe_weights(
        model_dim: usize,
        head_dim: usize,
        num_q: usize,
        num_kv: usize,
        hidden_dim: usize,
        num_experts: usize,
        experts_per_tok: usize,
    ) -> MoeBlockWeights {
        let q_dim = num_q * head_dim;
        let kv_dim = num_kv * head_dim;
        let experts = (0..num_experts)
            .map(|e| {
                let base = 10.0 + e as f32 * 3.0;
                MoeExpertWeights {
                    w_gate: mat(base, hidden_dim * model_dim),
                    w_up: mat(base + 1.0, hidden_dim * model_dim),
                    w_down: mat(base + 2.0, model_dim * hidden_dim),
                }
            })
            .collect();
        MoeBlockWeights {
            model_dim,
            head_dim,
            num_q_heads: num_q,
            num_kv_heads: num_kv,
            hidden_dim,
            experts_per_tok,
            attn_norm: RmsNorm::new(model_dim),
            ffn_norm: RmsNorm::new(model_dim),
            w_q: mat(1.0, q_dim * model_dim),
            w_k: mat(2.0, kv_dim * model_dim),
            w_v: mat(3.0, kv_dim * model_dim),
            w_o: mat(4.0, model_dim * q_dim),
            w_router: mat(8.0, num_experts * model_dim),
            experts,
        }
    }

    #[test]
    fn moe_block_runs_and_reports_its_shape() {
        // An 8-expert, top-2 MoE block steps a sequence with finite output and
        // reports its MoE shape.
        let w = moe_weights(8, 2, 4, 2, 16, 8, 2);
        let mut block = MhaDecoderBlock::from_weights_moe(&w, Precision::F32).unwrap();
        assert!(block.is_moe());
        assert_eq!(block.num_experts(), 8);
        assert_eq!(block.experts_per_tok(), 2);
        for step in 0..6 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            let y = block.step(&x).unwrap();
            assert_eq!(y.len(), 8);
            assert!(y.iter().all(|v| v.is_finite()), "step {step}");
        }
        assert_eq!(block.len(), 6);
    }

    #[test]
    fn dense_block_reports_not_moe() {
        let w = weights(8, 2, 4, 2, 16);
        let block = MhaDecoderBlock::from_weights(&w, Precision::F32).unwrap();
        assert!(!block.is_moe());
        assert_eq!(block.num_experts(), 0);
        assert_eq!(block.experts_per_tok(), 0);
    }

    #[test]
    fn single_expert_moe_matches_the_dense_block() {
        // The pinned equivalence: a 1-expert top-1 MoE (softmax over one logit =
        // weight 1.0) decodes bit-for-bit like the dense block with the same
        // attention + FFN weights. This is the "MoE reduces to dense" invariant.
        let dense_w = weights(8, 2, 4, 2, 16);
        let moe_w = moe_mirror_of(&dense_w);
        let mut dense = MhaDecoderBlock::from_weights(&dense_w, Precision::F32).unwrap();
        let mut moe = MhaDecoderBlock::from_weights_moe(&moe_w, Precision::F32).unwrap();
        assert!(moe.is_moe() && !dense.is_moe());
        for step in 0..6 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.3).sin()).collect();
            let yd = dense.step(&x).unwrap();
            let ym = moe.step(&x).unwrap();
            assert_eq!(
                yd, ym,
                "step {step}: single-expert MoE must equal the dense block"
            );
        }
    }

    #[test]
    fn top1_moe_equals_its_selected_single_expert_and_uses_both() {
        // With top-1 over 2 distinct experts, each step's output must equal one
        // of the two single-expert reference blocks (weight 1.0, no blending) —
        // and across a varied sequence, the router must select *both* experts,
        // proving the gate genuinely routes.
        let mut w = moe_weights(8, 2, 4, 2, 16, 2, 1);
        // Router that selects on the sign of the first normalized component:
        // expert 0 wins when n2[0] > 0, expert 1 when n2[0] < 0. The sign of
        // n2[0] flips across the varied input sequence, so both get used.
        let md = w.model_dim;
        w.w_router = vec![0.0f32; 2 * md];
        w.w_router[0] = 1.0; // expert 0 logit = n2[0]
        w.w_router[md] = -1.0; // expert 1 logit = -n2[0]
        let mut moe = MhaDecoderBlock::from_weights_moe(&w, Precision::F32).unwrap();

        // Two single-expert references sharing the same attention + router, each
        // holding one of the experts. Attention (and thus the KV trajectory) is
        // independent of the FFN branch, so these stay in lockstep with `moe`.
        let single = |expert: MoeExpertWeights| MoeBlockWeights {
            experts_per_tok: 1,
            w_router: mat(8.0, w.model_dim), // 1 expert × model_dim
            experts: vec![expert],
            attn_norm: w.attn_norm.clone(),
            ffn_norm: w.ffn_norm.clone(),
            w_q: w.w_q.clone(),
            w_k: w.w_k.clone(),
            w_v: w.w_v.clone(),
            w_o: w.w_o.clone(),
            ..w.clone()
        };
        let mut ref0 =
            MhaDecoderBlock::from_weights_moe(&single(w.experts[0].clone()), Precision::F32)
                .unwrap();
        let mut ref1 =
            MhaDecoderBlock::from_weights_moe(&single(w.experts[1].clone()), Precision::F32)
                .unwrap();

        let (mut used0, mut used1) = (false, false);
        for step in 0..12 {
            let x: Vec<f32> = (0..8)
                .map(|i| ((i * 2 + step) as f32 * 0.37).sin())
                .collect();
            let ym = moe.step(&x).unwrap();
            let y0 = ref0.step(&x).unwrap();
            let y1 = ref1.step(&x).unwrap();
            if ym == y0 {
                used0 = true;
            } else if ym == y1 {
                used1 = true;
            } else {
                panic!("step {step}: top-1 MoE output matched neither single expert");
            }
        }
        assert!(
            used0 && used1,
            "router must select both experts across the sequence (used0={used0}, used1={used1})"
        );
    }

    #[test]
    fn moe_router_weights_change_the_output() {
        // Same experts, different router → different routing → different decode.
        // Proves the router logits actually drive selection.
        let a_w = moe_weights(8, 2, 4, 2, 16, 4, 1);
        let mut b_w = a_w.clone();
        // Reverse the router rows so a different expert tends to win.
        b_w.w_router = a_w.w_router.iter().rev().copied().collect();
        let mut a = MhaDecoderBlock::from_weights_moe(&a_w, Precision::F32).unwrap();
        let mut b = MhaDecoderBlock::from_weights_moe(&b_w, Precision::F32).unwrap();
        let mut differed = false;
        for step in 0..8 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.29).cos()).collect();
            if a.step(&x).unwrap() != b.step(&x).unwrap() {
                differed = true;
            }
        }
        assert!(
            differed,
            "distinct routers must yield distinct decode output"
        );
    }

    #[test]
    fn moe_rejects_empty_expert_bank() {
        let mut w = moe_weights(8, 2, 4, 2, 16, 1, 1);
        w.experts.clear();
        let err = MhaDecoderBlock::from_weights_moe(&w, Precision::F32).unwrap_err();
        assert!(matches!(err, MhaBlockError::MoeConfig(_)), "got {err:?}");
    }

    #[test]
    fn moe_rejects_zero_experts_per_tok() {
        let mut w = moe_weights(8, 2, 4, 2, 16, 4, 1);
        w.experts_per_tok = 0;
        let err = MhaDecoderBlock::from_weights_moe(&w, Precision::F32).unwrap_err();
        assert!(matches!(err, MhaBlockError::MoeConfig(_)), "got {err:?}");
    }

    #[test]
    fn nvfp4_moe_reports_router_and_expert_recipes() {
        // An NVFP4 MoE block auto-selects a recipe for every projection: 4
        // attention + 1 router + 3 per expert. With 2 experts that is 4+1+6 = 11.
        let w = moe_weights(8, 2, 4, 2, 16, 2, 1);
        let block = MhaDecoderBlock::from_weights_moe(&w, Precision::Nvfp4).unwrap();
        let recipes = block.nvfp4_recipes();
        assert_eq!(recipes.len(), 4 + 1 + 2 * 3, "recipes: {recipes:?}");
        assert!(recipes.iter().any(|(n, _)| *n == "router"));
        assert!(recipes.iter().any(|(n, _)| *n == "expert-gate"));
        // An f32 MoE block reports none.
        let f32_block = MhaDecoderBlock::from_weights_moe(&w, Precision::F32).unwrap();
        assert!(f32_block.nvfp4_recipes().is_empty());
    }

    // ---- GPT-OSS FFN math (biases + clamped-α activation) -------------------

    fn lin1(w: f32) -> Linear {
        Linear::from_f32(&[w], 1, 1, Precision::F32).unwrap()
    }

    #[test]
    fn gpt_oss_activation_matches_the_reference_formula() {
        // A 1-in / 1-hidden / 1-out expert with identity weights: gate = up = x,
        // so the output is directly checkable against the written-out formula
        // `(up + 1) · (gate · σ(α·gate))`.
        let expert = MoeExpert {
            gate: lin1(1.0),
            up: lin1(1.0),
            down: lin1(1.0),
            gate_bias: Some(vec![0.0]),
            up_bias: Some(vec![0.0]),
            down_bias: Some(vec![0.0]),
        };
        let (alpha, limit) = (1.702f32, 7.0f32);
        let g = 0.5f32; // gate = up = 0.5, both inside ±limit (no clamp)
        let expected = (g + 1.0) * (g * (1.0 / (1.0 + (-(alpha * g)).exp())));
        let y = expert
            .forward(&[0.5], MoeActivation::GptOssClamped { alpha, limit })
            .unwrap();
        assert!(
            (y[0] - expected).abs() < 1e-6,
            "got {}, want {expected}",
            y[0]
        );
    }

    #[test]
    fn gpt_oss_activation_clamps_gate_and_up() {
        // With a tight limit, gate is capped at `limit` and up clamped to
        // `±limit` before the GLU.
        let expert = MoeExpert {
            gate: lin1(1.0),
            up: lin1(1.0),
            down: lin1(1.0),
            gate_bias: Some(vec![0.0]),
            up_bias: Some(vec![0.0]),
            down_bias: Some(vec![0.0]),
        };
        let (alpha, limit) = (1.702f32, 0.3f32);
        let g = 0.5f32.min(limit); // 0.3
        let u = 0.5f32.clamp(-limit, limit); // 0.3
        let expected = (u + 1.0) * (g * (1.0 / (1.0 + (-(alpha * g)).exp())));
        let y = expert
            .forward(&[0.5], MoeActivation::GptOssClamped { alpha, limit })
            .unwrap();
        assert!(
            (y[0] - expected).abs() < 1e-6,
            "got {}, want {expected}",
            y[0]
        );
    }

    #[test]
    fn gpt_oss_down_bias_is_added() {
        // A nonzero down bias shifts the output by exactly that bias.
        let base = MoeExpert {
            gate: lin1(1.0),
            up: lin1(1.0),
            down: lin1(1.0),
            gate_bias: Some(vec![0.0]),
            up_bias: Some(vec![0.0]),
            down_bias: Some(vec![0.0]),
        };
        let biased = MoeExpert {
            down_bias: Some(vec![2.5]),
            ..base.clone()
        };
        let act = MoeActivation::GptOssClamped {
            alpha: 1.702,
            limit: 7.0,
        };
        let a = base.forward(&[0.5], act).unwrap()[0];
        let b = biased.forward(&[0.5], act).unwrap()[0];
        assert!((b - a - 2.5).abs() < 1e-6, "down bias must add 2.5");
    }

    // GPT-OSS MoE weights: 4 experts, per-expert hidden 16, model_dim 8.
    const GO_EXPERTS: usize = 4;
    const GO_HID: usize = 16;

    fn gpt_oss_weights(experts_per_tok: usize, zero_bias: bool) -> GptOssMoeWeights {
        let base = moe_weights(8, 2, 4, 2, GO_HID, GO_EXPERTS, experts_per_tok);
        let bias = |seed: f32, n: usize| {
            if zero_bias {
                vec![0.0; n]
            } else {
                mat(seed, n)
            }
        };
        let expert_biases = (0..GO_EXPERTS)
            .map(|e| GptOssExpertBias {
                gate: bias(e as f32, GO_HID),
                up: bias(e as f32 + 0.5, GO_HID),
                down: bias(e as f32 + 1.0, 8),
            })
            .collect();
        // Attention biases + sinks only in the non-zero case, so the zero-bias
        // fixture isolates the FFN activation. q_dim=4·2=8, kv_dim=2·2=4,
        // model_dim=8, num_q_heads=4.
        let attn = |seed: f32, n: usize| (!zero_bias).then(|| mat(seed, n));
        GptOssMoeWeights {
            base,
            router_bias: bias(9.0, GO_EXPERTS),
            expert_biases,
            alpha: 1.702,
            limit: 7.0,
            attn_q_bias: attn(20.0, 8),
            attn_k_bias: attn(21.0, 4),
            attn_v_bias: attn(22.0, 4),
            attn_o_bias: attn(23.0, 8),
            attn_sinks: attn(24.0, 4),
        }
    }

    #[test]
    fn gpt_oss_moe_block_runs_and_reports_shape() {
        let w = gpt_oss_weights(2, false);
        let mut block = MhaDecoderBlock::from_weights_moe_gpt_oss(&w, Precision::F32).unwrap();
        assert!(block.is_moe());
        assert_eq!(block.num_experts(), GO_EXPERTS);
        assert_eq!(block.experts_per_tok(), 2);
        for step in 0..6 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.2).sin()).collect();
            let y = block.step(&x).unwrap();
            assert_eq!(y.len(), 8);
            assert!(y.iter().all(|v| v.is_finite()), "step {step}");
        }
    }

    #[test]
    fn gpt_oss_differs_from_standard_moe() {
        // Same weights + zero biases, but the GPT-OSS clamped-α activation is a
        // different function than SwiGLU, so decode differs.
        let w = gpt_oss_weights(2, true); // zero biases → only the activation differs
        let mut gpt = MhaDecoderBlock::from_weights_moe_gpt_oss(&w, Precision::F32).unwrap();
        let mut std = MhaDecoderBlock::from_weights_moe(&w.base, Precision::F32).unwrap();
        let mut differed = false;
        for step in 0..6 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.3).sin()).collect();
            if gpt.step(&x).unwrap() != std.step(&x).unwrap() {
                differed = true;
            }
        }
        assert!(
            differed,
            "the GPT-OSS activation must decode differently from SwiGLU"
        );
    }

    #[test]
    fn gpt_oss_rejects_mismatched_bias_count() {
        let mut w = gpt_oss_weights(2, false);
        w.expert_biases.pop(); // now len != num_experts
        let err = MhaDecoderBlock::from_weights_moe_gpt_oss(&w, Precision::F32).unwrap_err();
        assert!(matches!(err, MhaBlockError::MoeConfig(_)), "got {err:?}");
    }

    #[test]
    fn gpt_oss_attention_biases_and_sinks_change_decode() {
        // Identical FFN (GPT-OSS biases + activation), but one block has the
        // attention q/k/v/o biases + per-head sinks and the other does not — so
        // decode must differ, proving the attention path is wired.
        let with_attn = gpt_oss_weights(2, false);
        let mut no_attn_w = gpt_oss_weights(2, false);
        no_attn_w.attn_q_bias = None;
        no_attn_w.attn_k_bias = None;
        no_attn_w.attn_v_bias = None;
        no_attn_w.attn_o_bias = None;
        no_attn_w.attn_sinks = None;
        let mut a = MhaDecoderBlock::from_weights_moe_gpt_oss(&with_attn, Precision::F32).unwrap();
        let mut b = MhaDecoderBlock::from_weights_moe_gpt_oss(&no_attn_w, Precision::F32).unwrap();
        let mut differed = false;
        for step in 0..5 {
            let x: Vec<f32> = (0..8).map(|i| ((i + step) as f32 * 0.25).sin()).collect();
            let ya = a.step(&x).unwrap();
            let yb = b.step(&x).unwrap();
            assert!(ya.iter().all(|v| v.is_finite()));
            if ya != yb {
                differed = true;
            }
        }
        assert!(
            differed,
            "attention biases + sinks must change the decode output"
        );
    }
}
