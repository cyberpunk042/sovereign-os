//! `sovereign-safetensors-loader` — load a Llama-family model from HuggingFace
//! `safetensors` (+ `config.json`) into the runtime's **existing** multi-head
//! [`QuantModel`].
//!
//! The from-scratch inference stack (`sovereign-serve`) has always emitted
//! gibberish because it hand-builds a model with sine-filler weights and had no
//! way to load a trained one. The transformer math already exists — the repo's
//! `MhaBlockWeights → MhaDecoderBlock → LayerStack → QuantModel → QuantLlm`
//! harness matches real HF Llama tensor shapes at f32. This crate is the missing
//! piece: parse a safetensors file, dequantize `BF16`/`F16` → `f32`, permute the
//! HF rotate-half q/k layout into the runtime's interleaved-RoPE layout, and
//! populate that harness.
//!
//! ## Scope (honest)
//!
//! - **In:** dense-f32 assembly from `F32`/`BF16`/`F16` safetensors; GQA head
//!   counts; weight tying; the HF→interleaved RoPE row-permutation; shape
//!   validation; a synthetic-fixture test proving parse + dequant + shape +
//!   forward + deterministic decode **offline**.
//! - **In (added SDD-950):** `rope_theta` + `rope_scaling` are now parsed from
//!   `config.json` and threaded into each block via
//!   [`MhaDecoderBlock::with_rope`], so Llama-3 (500000) / Qwen2 (1000000) /
//!   Mistral decode at their trained frequency base instead of a hardcoded
//!   10000. Linear / dynamic-NTK / YaRN scaling are applied; llama3 scaling
//!   applies the exact base (short-context coherent; the freq ramp is a noted
//!   follow-up).
//! - **In (MoE Increment 2):** mixture-of-experts models assemble too. When
//!   `config.json` declares `num_experts` (`> 1`; the Mixtral `num_local_experts`
//!   spelling is accepted), every layer's FFN is built as a MoE bank via
//!   [`MhaDecoderBlock::from_weights_moe`] — a router `mlp.gate.weight` plus
//!   per-expert `mlp.experts.{e}.{gate,up,down}_proj.weight` SwiGLUs, top-k'd by
//!   `num_experts_per_tok` at `moe_intermediate_size` width. This is the
//!   Qwen3-30B-A3B / Mixtral class of on-card MoE. **Follow-ups:** GGUF stacked
//!   expert tensors (`ffn_*_exps` + `expert_count` metadata); GPT-OSS fused
//!   `gate_up_proj`; and per-layer dense/MoE interleaving (`mlp_only_layers` /
//!   `decoder_sparse_step`) — this increment builds every layer as MoE, correct
//!   for the fully-sparse A3B/Mixtral families.
//! - **Out (named follow-ups):** GGUF Q4_K/Q8_0 dequant (needs a from-scratch
//!   block-dequant); a real **tokenizer bridge** (the runtime tokenizer is
//!   byte-BPE — a real model's SentencePiece/BPE vocab needs translating);
//!   the llama3 low/high-freq ramp; and **real-model coherence**, which cannot
//!   be verified in this environment (no network to model hosts, no model file
//!   on disk).
//!
//! So: this lands + verifies the *machinery*. Point it at a real Llama-family
//! safetensors with a matching tokenizer and it builds a runnable model; whether
//! that model is *coherent* is the gated follow-up.
//!
//! Standing rule: We do not minimize anything.

#![warn(missing_docs)]

use std::collections::BTreeMap;

use serde::Deserialize;

mod gguf;
pub use gguf::{GgufFile, GgufTokenizer, load_gguf};
use sovereign_decoder_layer::{DecoderLayer, LayerStack};
use sovereign_mha_block::{
    MhaBlockWeights, MhaDecoderBlock, MoeBlockWeights, MoeExpertWeights, RopeScaling,
    RopeScalingKind,
};
use sovereign_quant_llm::QuantLlm;
use sovereign_quant_model::QuantModel;
use sovereign_rmsnorm::RmsNorm;
use sovereign_tokenizer::Tokenizer;

// Re-exported so callers of the precision- / sampler-selectable loaders can name
// the knobs without adding a direct dependency on the underlying crates.
pub use sovereign_linear::Precision;
pub use sovereign_sampler::{Sampler, SamplerConfig};

/// Schema version of the loader surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Everything that can go wrong loading a model.
#[derive(Debug, thiserror::Error)]
pub enum LoaderError {
    /// The safetensors byte stream was too short for its declared header.
    #[error("safetensors truncated: {0}")]
    Truncated(String),
    /// The JSON header (safetensors or config.json) did not parse.
    #[error("json parse: {0}")]
    Json(String),
    /// A tensor the architecture requires was absent.
    #[error("missing tensor `{0}`")]
    MissingTensor(String),
    /// A tensor used a dtype this loader does not (yet) decode.
    #[error(
        "unsupported dtype `{dtype}` for tensor `{name}` (F32/F16/BF16 only; GGUF-Q is a follow-up)"
    )]
    UnsupportedDtype {
        /// Tensor name.
        name: String,
        /// The offending dtype string.
        dtype: String,
    },
    /// A tensor's element count did not match the shape the config implies.
    #[error("shape mismatch for `{name}`: expected {expected} elems, tensor holds {got}")]
    ShapeMismatch {
        /// Tensor name.
        name: String,
        /// Element count the config implies.
        expected: usize,
        /// Element count the tensor actually holds.
        got: usize,
    },
    /// `head_dim` was odd — RoPE pairs require an even head dimension.
    #[error("head_dim must be even for RoPE, got {0}")]
    OddHeadDim(usize),
    /// A `config.json` field was structurally invalid (a zero dimension that
    /// divides or indexes — e.g. `num_attention_heads: 0` divides by zero in
    /// `head_dim`). Rejected up front so a malformed model dir can't panic the
    /// loader thread on `/v1/models/load`.
    #[error("invalid config: {0}")]
    InvalidConfig(String),
    /// The runtime harness rejected the assembled weights.
    #[error("model assembly failed: {0}")]
    Build(String),
}

fn default_eps() -> f32 {
    1e-6
}

/// The subset of an HF `config.json` the loader needs. safetensors carries only
/// tensors, not hyperparameters, so these come alongside.
#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    /// Residual-stream dimension (`hidden_size`).
    #[serde(rename = "hidden_size")]
    pub model_dim: usize,
    /// Number of decoder layers (`num_hidden_layers`).
    #[serde(rename = "num_hidden_layers")]
    pub n_layers: usize,
    /// Number of query heads (`num_attention_heads`).
    #[serde(rename = "num_attention_heads")]
    pub n_heads: usize,
    /// Number of key/value heads (`num_key_value_heads`); defaults to `n_heads`
    /// (i.e. plain MHA) when absent.
    #[serde(rename = "num_key_value_heads", default)]
    pub n_kv_heads: Option<usize>,
    /// Vocabulary size (`vocab_size`).
    #[serde(rename = "vocab_size")]
    pub vocab: usize,
    /// FFN hidden dimension (`intermediate_size`).
    #[serde(rename = "intermediate_size")]
    pub hidden: usize,
    /// RMSNorm epsilon (`rms_norm_eps`).
    #[serde(rename = "rms_norm_eps", default = "default_eps")]
    pub eps: f32,
    /// Whether `lm_head` ties to `embed_tokens` (`tie_word_embeddings`).
    #[serde(rename = "tie_word_embeddings", default)]
    pub tied: bool,
    /// Explicit per-head dimension (`head_dim`); defaults to `model_dim / n_heads`.
    #[serde(rename = "head_dim", default)]
    pub head_dim: Option<usize>,
    /// RoPE frequency base (`rope_theta`). Defaults to 10000 (the pre-Llama-3
    /// convention); modern models train with 500000 (Llama-3) / 1000000 (Qwen2)
    /// and decode incoherently at 10000 — this is THE field that unblocks them.
    #[serde(rename = "rope_theta", default = "default_rope_theta")]
    pub rope_theta: f32,
    /// Optional RoPE position scaling (`rope_scaling`), for long-context models.
    #[serde(rename = "rope_scaling", default)]
    pub rope_scaling: Option<RopeScalingCfg>,
    /// Number of experts for a mixture-of-experts FFN (`num_experts`, or the
    /// Mixtral spelling `num_local_experts`). `None` / `0` = a dense model.
    /// Present ⇒ every decoder layer's FFN is built as a MoE bank instead of a
    /// single SwiGLU (the Qwen3-30B-A3B / Mixtral class of on-card models).
    #[serde(rename = "num_experts", alias = "num_local_experts", default)]
    pub num_experts: Option<usize>,
    /// Experts activated per token (`num_experts_per_tok`), the MoE top-`k`.
    /// Required when `num_experts` is set.
    #[serde(rename = "num_experts_per_tok", default)]
    pub num_experts_per_tok: Option<usize>,
    /// Per-expert FFN hidden dimension (`moe_intermediate_size`). Falls back to
    /// the dense `intermediate_size` when absent (Mixtral reuses the dense
    /// width; Qwen3-MoE gives experts a distinct, smaller width).
    #[serde(rename = "moe_intermediate_size", default)]
    pub moe_intermediate_size: Option<usize>,
}

/// Default frequency base when `config.json` omits `rope_theta`.
fn default_rope_theta() -> f32 {
    10000.0
}

fn default_scaling_factor() -> f32 {
    1.0
}
fn default_beta_fast() -> f32 {
    32.0
}
fn default_beta_slow() -> f32 {
    1.0
}

/// The `rope_scaling` block of an HF `config.json`. Accepts both the newer
/// `rope_type` and the older `type` key. Translated to a runtime
/// [`RopeScaling`] by [`Config::rope_scaling_resolved`].
#[derive(Debug, Clone, serde::Deserialize)]
pub struct RopeScalingCfg {
    /// Scaling family: `linear` / `dynamic` / `yarn` / `llama3` (case-insensitive).
    #[serde(rename = "rope_type", alias = "type", default)]
    pub rope_type: String,
    /// Scaling factor (`factor`).
    #[serde(default = "default_scaling_factor")]
    pub factor: f32,
    /// Trained context (`original_max_position_embeddings`), needed by YaRN.
    #[serde(rename = "original_max_position_embeddings", default)]
    pub original_ctx: Option<usize>,
    /// YaRN high-frequency ramp threshold (`beta_fast`).
    #[serde(default = "default_beta_fast")]
    pub beta_fast: f32,
    /// YaRN low-frequency ramp threshold (`beta_slow`).
    #[serde(default = "default_beta_slow")]
    pub beta_slow: f32,
}

impl Config {
    /// Parse an HF `config.json`, then structurally validate it — so a
    /// malformed model dir fails with a clean [`LoaderError::InvalidConfig`]
    /// instead of panicking the loader thread deeper in (div-by-zero in
    /// `head_dim`, zero-length allocations, etc.).
    pub fn from_json(bytes: &[u8]) -> Result<Self, LoaderError> {
        let cfg: Self =
            serde_json::from_slice(bytes).map_err(|e| LoaderError::Json(e.to_string()))?;
        cfg.validate()?;
        Ok(cfg)
    }

    /// Reject structurally-invalid dimensions: every field below either DIVIDES
    /// (`head_dim = model_dim / n_heads`) or sizes a required tensor, so a zero
    /// is a panic or a nonsensical model — surface it as an error at the door.
    pub fn validate(&self) -> Result<(), LoaderError> {
        let zero = |name: &str| Err(LoaderError::InvalidConfig(format!("{name} must be > 0")));
        if self.n_heads == 0 {
            return zero("num_attention_heads");
        }
        if self.model_dim == 0 {
            return zero("hidden_size");
        }
        if self.n_layers == 0 {
            return zero("num_hidden_layers");
        }
        if self.vocab == 0 {
            return zero("vocab_size");
        }
        if self.hidden == 0 {
            return zero("intermediate_size");
        }
        if self.n_kv_heads == Some(0) {
            return zero("num_key_value_heads");
        }
        if self.head_dim == Some(0) {
            return zero("head_dim");
        }
        // MoE fields: if the model declares experts, the count and the per-token
        // activation must be sane, and `experts_per_tok` cannot exceed the bank.
        if let Some(n) = self.num_experts {
            if n > 1 {
                if self.moe_intermediate_size == Some(0) {
                    return zero("moe_intermediate_size");
                }
                if let Some(k) = self.num_experts_per_tok {
                    if k == 0 {
                        return zero("num_experts_per_tok");
                    }
                    if k > n {
                        return Err(LoaderError::InvalidConfig(format!(
                            "num_experts_per_tok ({k}) exceeds num_experts ({n})"
                        )));
                    }
                }
            }
        }
        Ok(())
    }

    /// Resolve `rope_scaling` into the runtime [`RopeScaling`] the block builder
    /// takes, or `None` when absent / an unrecognized `rope_type` (in which case
    /// the base `rope_theta` alone applies — never a fabricated scaling).
    #[must_use]
    pub fn rope_scaling_resolved(&self) -> Option<RopeScaling> {
        let cfg = self.rope_scaling.as_ref()?;
        let kind = match cfg.rope_type.to_ascii_lowercase().as_str() {
            "linear" => RopeScalingKind::Linear,
            "dynamic" | "dynamic-ntk" | "ntk" => RopeScalingKind::Dynamic,
            "yarn" => RopeScalingKind::Yarn,
            "llama3" => RopeScalingKind::Llama3,
            _ => return None,
        };
        Some(RopeScaling {
            kind,
            factor: cfg.factor,
            original_ctx: cfg.original_ctx,
            beta_fast: cfg.beta_fast,
            beta_slow: cfg.beta_slow,
        })
    }
    /// Effective key/value head count.
    #[must_use]
    pub fn kv_heads(&self) -> usize {
        self.n_kv_heads.unwrap_or(self.n_heads)
    }
    /// Effective per-head dimension. `n_heads` is validated `> 0` by
    /// [`Config::validate`]; `.max(1)` keeps this panic-free even if a caller
    /// constructs a `Config` directly and skips validation.
    #[must_use]
    pub fn head_dim(&self) -> usize {
        self.head_dim
            .unwrap_or(self.model_dim / self.n_heads.max(1))
    }

    /// Whether this model's FFN is a mixture of experts (`num_experts` present
    /// and `> 1`). A `num_experts` of `0` or `1` is treated as dense — a
    /// 1-expert "MoE" is just a dense SwiGLU with a redundant router.
    #[must_use]
    pub fn is_moe(&self) -> bool {
        self.num_experts.is_some_and(|n| n > 1)
    }

    /// Number of experts (`0` when dense).
    #[must_use]
    pub fn experts(&self) -> usize {
        self.num_experts.unwrap_or(0)
    }

    /// Experts activated per token (top-`k`); defaults to `2` (the Mixtral /
    /// Qwen3-MoE convention) when a MoE config omits it. `0` for a dense model.
    #[must_use]
    pub fn experts_per_tok(&self) -> usize {
        if self.is_moe() {
            self.num_experts_per_tok.unwrap_or(2)
        } else {
            0
        }
    }

    /// Per-expert FFN hidden width — `moe_intermediate_size` when present, else
    /// the dense `intermediate_size`.
    #[must_use]
    pub fn moe_hidden(&self) -> usize {
        self.moe_intermediate_size.unwrap_or(self.hidden)
    }
}

// ── safetensors container ────────────────────────────────────────────────────

#[derive(Debug, Clone, Deserialize)]
struct TensorInfo {
    dtype: String,
    #[allow(dead_code)]
    shape: Vec<usize>,
    data_offsets: [usize; 2],
}

/// A parsed safetensors file: `u64 LE header length` + JSON header + data buffer.
/// Holds a borrow of the input bytes; tensor accessors decode on demand.
pub struct SafeTensors<'a> {
    data: &'a [u8],
    data_start: usize,
    infos: BTreeMap<String, TensorInfo>,
}

impl<'a> SafeTensors<'a> {
    /// Parse the header of a safetensors byte stream.
    pub fn parse(bytes: &'a [u8]) -> Result<Self, LoaderError> {
        if bytes.len() < 8 {
            return Err(LoaderError::Truncated(
                "fewer than 8 header-length bytes".into(),
            ));
        }
        let header_len = u64::from_le_bytes(bytes[0..8].try_into().unwrap()) as usize;
        let json_end = 8usize
            .checked_add(header_len)
            .ok_or_else(|| LoaderError::Truncated("header length overflows".into()))?;
        if bytes.len() < json_end {
            return Err(LoaderError::Truncated(format!(
                "header declares {header_len} bytes; only {} present",
                bytes.len().saturating_sub(8)
            )));
        }
        let raw: BTreeMap<String, serde_json::Value> = serde_json::from_slice(&bytes[8..json_end])
            .map_err(|e| LoaderError::Json(e.to_string()))?;
        let mut infos = BTreeMap::new();
        for (name, value) in raw {
            if name == "__metadata__" {
                continue;
            }
            let info: TensorInfo =
                serde_json::from_value(value).map_err(|e| LoaderError::Json(e.to_string()))?;
            infos.insert(name, info);
        }
        Ok(Self {
            data: bytes,
            data_start: json_end,
            infos,
        })
    }

    /// The tensor names present (sorted).
    #[must_use]
    pub fn names(&self) -> Vec<&str> {
        self.infos.keys().map(String::as_str).collect()
    }

    /// Decode a tensor to `f32`, dequantizing `BF16`/`F16` on the way. Returns
    /// the flat row-major elements.
    pub fn tensor_f32(&self, name: &str) -> Result<Vec<f32>, LoaderError> {
        let info = self
            .infos
            .get(name)
            .ok_or_else(|| LoaderError::MissingTensor(name.to_string()))?;
        let [start, end] = info.data_offsets;
        // `checked_add`: the offsets come from the untrusted JSON header, so a
        // hostile `data_offsets: [usize::MAX, …]` would wrap `data_start + start`
        // and could slip past the range check below — decode the wrong bytes as
        // weights (release) or panic (debug). Overflow → out-of-range error.
        let (Some(a), Some(b)) = (
            self.data_start.checked_add(start),
            self.data_start.checked_add(end),
        ) else {
            return Err(LoaderError::Truncated(format!(
                "tensor `{name}` data_offsets [{start},{end}] overflow the data buffer"
            )));
        };
        if b > self.data.len() || a > b {
            return Err(LoaderError::Truncated(format!(
                "tensor `{name}` data_offsets [{start},{end}] out of range"
            )));
        }
        let raw = &self.data[a..b];
        match info.dtype.as_str() {
            "F32" => {
                if raw.len() % 4 != 0 {
                    return Err(LoaderError::Truncated(format!(
                        "`{name}` F32 not 4-aligned"
                    )));
                }
                Ok(raw
                    .chunks_exact(4)
                    .map(|c| f32::from_le_bytes(c.try_into().unwrap()))
                    .collect())
            }
            "BF16" => {
                if raw.len() % 2 != 0 {
                    return Err(LoaderError::Truncated(format!(
                        "`{name}` BF16 not 2-aligned"
                    )));
                }
                Ok(raw
                    .chunks_exact(2)
                    .map(|c| sovereign_vnni::bf16_to_f32(u16::from_le_bytes(c.try_into().unwrap())))
                    .collect())
            }
            "F16" => {
                if raw.len() % 2 != 0 {
                    return Err(LoaderError::Truncated(format!(
                        "`{name}` F16 not 2-aligned"
                    )));
                }
                Ok(raw
                    .chunks_exact(2)
                    .map(|c| {
                        half::f16::from_bits(u16::from_le_bytes(c.try_into().unwrap())).to_f32()
                    })
                    .collect())
            }
            other => Err(LoaderError::UnsupportedDtype {
                name: name.to_string(),
                dtype: other.to_string(),
            }),
        }
    }

    /// Decode a tensor and check it holds exactly `expected` elements.
    fn tensor_exact(&self, name: &str, expected: usize) -> Result<Vec<f32>, LoaderError> {
        let v = self.tensor_f32(name)?;
        if v.len() != expected {
            return Err(LoaderError::ShapeMismatch {
                name: name.to_string(),
                expected,
                got: v.len(),
            });
        }
        Ok(v)
    }
}

// ── HF rotate-half → interleaved RoPE permutation ────────────────────────────

/// HF stores q/k projections so that RoPE is applied as `rotate_half` — the head
/// vector is split `[first_half | second_half]` and rotated as pairs `(i, i+d/2)`.
/// The runtime's `sovereign-rope` uses the **interleaved** convention, pairs
/// `(2i, 2i+1)` (GGUF/GPT-J "NORM" style). To make an HF-trained q/k weight
/// produce the right rotation here, reorder the per-head output rows so row `2i`
/// takes HF row `i` and row `2i+1` takes HF row `i + d/2`.
///
/// `w` is `(num_heads · head_dim) × in_dim` row-major. Returns the permuted copy.
/// This is a pure row-permutation (bijective) — it changes no values.
///
/// # Errors
/// [`LoaderError::OddHeadDim`] if `head_dim` is odd.
pub fn permute_qk_hf_to_interleaved(
    w: &[f32],
    num_heads: usize,
    head_dim: usize,
    in_dim: usize,
) -> Result<Vec<f32>, LoaderError> {
    if head_dim % 2 != 0 {
        return Err(LoaderError::OddHeadDim(head_dim));
    }
    let half = head_dim / 2;
    let mut out = vec![0.0f32; w.len()];
    for h in 0..num_heads {
        let head = h * head_dim * in_dim;
        for i in 0..half {
            let src_even = head + i * in_dim;
            let src_odd = head + (i + half) * in_dim;
            let dst_even = head + (2 * i) * in_dim;
            let dst_odd = head + (2 * i + 1) * in_dim;
            out[dst_even..dst_even + in_dim].copy_from_slice(&w[src_even..src_even + in_dim]);
            out[dst_odd..dst_odd + in_dim].copy_from_slice(&w[src_odd..src_odd + in_dim]);
        }
    }
    Ok(out)
}

// ── assembly ─────────────────────────────────────────────────────────────────

/// Load a model's tensors (safetensors bytes) + `Config` into a runnable
/// [`QuantModel`] at dense f32 with greedy sampling — the defaults.
///
/// Applies the HF→interleaved RoPE permutation to q/k and honors
/// `tie_word_embeddings`. For a non-f32 runtime precision or a non-greedy
/// sampler, use [`load_at_precision`], [`load_with_sampler`], or
/// [`load_configured`] — this is `load_configured(.., F32, greedy())`.
pub fn load(model_bytes: &[u8], config: &Config) -> Result<QuantModel, LoaderError> {
    load_configured(model_bytes, config, Precision::F32, Sampler::greedy())
}

/// Load at a caller-chosen runtime `precision` (greedy sampling).
///
/// The decoder blocks are built at `precision` instead of the f32 default, so a
/// real checkpoint can run as Ternary / NVFP4 / INT8 / BF16 in-memory — a 7B
/// model at ~7GB (INT8) / ~14GB (BF16) instead of ~28GB f32, the local-sovereign
/// premise. Weights are still parsed from f32/f16/bf16 tensors and quantized
/// down at load; loading an *already*-quantized checkpoint (GGUF Q4_K/Q8_0,
/// GPTQ, AWQ) is a separate, larger follow-up (no dequant-from-disk path exists
/// yet — see [`LoaderError::UnsupportedDtype`]).
pub fn load_at_precision(
    model_bytes: &[u8],
    config: &Config,
    precision: Precision,
) -> Result<QuantModel, LoaderError> {
    load_configured(model_bytes, config, precision, Sampler::greedy())
}

/// Load with a caller-supplied `sampler` (dense f32).
///
/// The default loaders hardwire `Sampler::greedy()`, so temperature / top-p /
/// top-k are unreachable even when a request asks for them; this threads a
/// chosen sampler into the assembled model. (Wiring per-request HTTP sampling
/// parameters into the daemon is a separate, gateway-side follow-up.)
pub fn load_with_sampler(
    model_bytes: &[u8],
    config: &Config,
    sampler: Sampler,
) -> Result<QuantModel, LoaderError> {
    load_configured(model_bytes, config, Precision::F32, sampler)
}

/// Load with both a caller-chosen runtime `precision` and `sampler` — the full
/// configurable entry point the convenience loaders delegate to.
///
/// Checked product of tensor dimensions → element count. A crafted config with
/// huge-but-nonzero dims must not wrap `usize` into a small `expected` that a
/// malicious tensor could then match (silently loading the wrong shape); an
/// overflow is an [`LoaderError::InvalidConfig`] instead.
fn elems(dims: &[usize]) -> Result<usize, LoaderError> {
    dims.iter()
        .copied()
        .try_fold(1usize, |acc, d| acc.checked_mul(d))
        .ok_or_else(|| LoaderError::InvalidConfig("tensor element count overflows usize".into()))
}

/// Applies the HF→interleaved RoPE permutation to q/k, threads the model's real
/// `rope_theta` + `rope_scaling` into every block, and honors
/// `tie_word_embeddings`.
pub fn load_configured(
    model_bytes: &[u8],
    config: &Config,
    precision: Precision,
    sampler: Sampler,
) -> Result<QuantModel, LoaderError> {
    // Defense if a caller built `Config` directly (not via `from_json`): the
    // multiplies + `head_dim` division below assume non-zero dimensions.
    config.validate()?;
    let st = SafeTensors::parse(model_bytes)?;
    let md = config.model_dim;
    let hd = config.head_dim();
    if hd % 2 != 0 {
        return Err(LoaderError::OddHeadDim(hd));
    }
    let nq = config.n_heads;
    let nkv = config.kv_heads();
    let hidden = config.hidden;
    let vocab = config.vocab;
    let q_dim = elems(&[nq, hd])?;
    let kv_dim = elems(&[nkv, hd])?;

    let mut layers: Vec<Box<dyn DecoderLayer>> = Vec::with_capacity(config.n_layers);
    for i in 0..config.n_layers {
        let p = |suffix: &str| format!("model.layers.{i}.{suffix}");
        // Attention half — identical for dense and MoE layers.
        let w_q = permute_qk_hf_to_interleaved(
            &st.tensor_exact(&p("self_attn.q_proj.weight"), elems(&[q_dim, md])?)?,
            nq,
            hd,
            md,
        )?;
        let w_k = permute_qk_hf_to_interleaved(
            &st.tensor_exact(&p("self_attn.k_proj.weight"), elems(&[kv_dim, md])?)?,
            nkv,
            hd,
            md,
        )?;
        let w_v = st.tensor_exact(&p("self_attn.v_proj.weight"), elems(&[kv_dim, md])?)?;
        let w_o = st.tensor_exact(&p("self_attn.o_proj.weight"), elems(&[md, q_dim])?)?;
        let attn_norm = RmsNorm::with_gain(
            st.tensor_exact(&p("input_layernorm.weight"), md)?,
            config.eps,
        );
        let ffn_norm = RmsNorm::with_gain(
            st.tensor_exact(&p("post_attention_layernorm.weight"), md)?,
            config.eps,
        );

        // FFN half — a mixture-of-experts bank when the model declares experts,
        // otherwise the dense SwiGLU. The MoE layout is the Qwen3-MoE / Mixtral
        // one: a router `mlp.gate.weight` scoring every expert, plus per-expert
        // `mlp.experts.{e}.{gate,up,down}_proj.weight` SwiGLUs.
        let block = if config.is_moe() {
            let n_exp = config.experts();
            let moe_hid = config.moe_hidden();
            let mut experts = Vec::with_capacity(n_exp);
            for e in 0..n_exp {
                let ep = |s: &str| format!("model.layers.{i}.mlp.experts.{e}.{s}");
                experts.push(MoeExpertWeights {
                    w_gate: st.tensor_exact(&ep("gate_proj.weight"), elems(&[moe_hid, md])?)?,
                    w_up: st.tensor_exact(&ep("up_proj.weight"), elems(&[moe_hid, md])?)?,
                    w_down: st.tensor_exact(&ep("down_proj.weight"), elems(&[md, moe_hid])?)?,
                });
            }
            let weights = MoeBlockWeights {
                model_dim: md,
                head_dim: hd,
                num_q_heads: nq,
                num_kv_heads: nkv,
                hidden_dim: moe_hid,
                experts_per_tok: config.experts_per_tok(),
                attn_norm,
                ffn_norm,
                w_q,
                w_k,
                w_v,
                w_o,
                w_router: st.tensor_exact(&p("mlp.gate.weight"), elems(&[n_exp, md])?)?,
                experts,
            };
            MhaDecoderBlock::from_weights_moe(&weights, precision)
                .map_err(|e| LoaderError::Build(format!("layer {i}: {e}")))?
        } else {
            let weights = MhaBlockWeights {
                model_dim: md,
                head_dim: hd,
                num_q_heads: nq,
                num_kv_heads: nkv,
                hidden_dim: hidden,
                attn_norm,
                ffn_norm,
                w_q,
                w_k,
                w_v,
                w_o,
                w_gate: st.tensor_exact(&p("mlp.gate_proj.weight"), elems(&[hidden, md])?)?,
                w_up: st.tensor_exact(&p("mlp.up_proj.weight"), elems(&[hidden, md])?)?,
                w_down: st.tensor_exact(&p("mlp.down_proj.weight"), elems(&[md, hidden])?)?,
            };
            MhaDecoderBlock::from_weights(&weights, precision)
                .map_err(|e| LoaderError::Build(format!("layer {i}: {e}")))?
        };
        // Thread the model's real RoPE base + scaling into every block (the fix
        // for modern models — default 10000 decodes them as garbage).
        let block = block.with_rope(config.rope_theta, config.rope_scaling_resolved().as_ref());
        layers.push(Box::new(block));
    }

    let stack = LayerStack::new(layers).map_err(|e| LoaderError::Build(e.to_string()))?;
    let embedding = st.tensor_exact("model.embed_tokens.weight", elems(&[vocab, md])?)?;
    let final_norm = RmsNorm::with_gain(st.tensor_exact("model.norm.weight", md)?, config.eps);

    if config.tied {
        QuantModel::new_tied(vocab, md, embedding, stack, final_norm, sampler)
            .map_err(|e| LoaderError::Build(e.to_string()))
    } else {
        let head = st.tensor_exact("lm_head.weight", elems(&[vocab, md])?)?;
        QuantModel::new(vocab, md, embedding, stack, final_norm, head, sampler)
            .map_err(|e| LoaderError::Build(e.to_string()))
    }
}

/// Load into a [`QuantLlm`], pairing the model with a caller-supplied tokenizer.
///
/// The tokenizer's `vocab_size()` MUST equal the model's `vocab` (the runtime
/// enforces this). A real model needs a real vocab bridge (a named follow-up);
/// for the synthetic fixture the byte-level [`Tokenizer::default`] (vocab 256)
/// pairs with a vocab-256 fixture.
pub fn load_llm(
    model_bytes: &[u8],
    config: &Config,
    tokenizer: Tokenizer,
) -> Result<QuantLlm, LoaderError> {
    let model = load(model_bytes, config)?;
    QuantLlm::new(tokenizer, model).map_err(|e| LoaderError::Build(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── a minimal safetensors writer, used only to build offline test fixtures ──

    fn f32_to_bf16_bits(x: f32) -> u16 {
        // round-to-nearest-even truncation of the low 16 bits
        let bits = x.to_bits();
        let round = ((bits >> 16) & 1) + 0x7fff;
        ((bits.wrapping_add(round)) >> 16) as u16
    }

    #[derive(Clone, Copy)]
    enum Dt {
        F32,
        Bf16,
    }

    fn write_safetensors(tensors: &[(String, Dt, Vec<usize>, Vec<f32>)]) -> Vec<u8> {
        let mut data = Vec::new();
        let mut entries = Vec::new();
        for (name, dt, shape, vals) in tensors {
            let start = data.len();
            for v in vals {
                match dt {
                    Dt::F32 => data.extend_from_slice(&v.to_le_bytes()),
                    Dt::Bf16 => data.extend_from_slice(&f32_to_bf16_bits(*v).to_le_bytes()),
                }
            }
            let end = data.len();
            let dtype = match dt {
                Dt::F32 => "F32",
                Dt::Bf16 => "BF16",
            };
            let shape_json = shape
                .iter()
                .map(|d| d.to_string())
                .collect::<Vec<_>>()
                .join(",");
            entries.push(format!(
                "\"{name}\":{{\"dtype\":\"{dtype}\",\"shape\":[{shape_json}],\"data_offsets\":[{start},{end}]}}"
            ));
        }
        let header = format!("{{{}}}", entries.join(","));
        let mut out = (header.len() as u64).to_le_bytes().to_vec();
        out.extend_from_slice(header.as_bytes());
        out.extend_from_slice(&data);
        out
    }

    // deterministic pseudo-weights so the fixture is reproducible without rand
    fn seq(seed: f32, n: usize) -> Vec<f32> {
        (0..n)
            .map(|i| (((i as f32) + seed) * 0.017).sin() * 0.1)
            .collect()
    }

    // a tiny 2-layer Llama-shaped model: vocab 256 (pairs with Tokenizer::default),
    // model_dim 8, 2 q-heads / 1 kv-head (GQA), head_dim 4, ffn 16.
    const MD: usize = 8;
    const NL: usize = 2;
    const NQ: usize = 2;
    const NKV: usize = 1;
    const HD: usize = 4;
    const HID: usize = 16;
    const V: usize = 256;

    // `qk_dt` = the dtype used for the q/k projections (exercises dequant); the
    // rest are f32.
    fn fixture(qk_dt: Dt) -> (Vec<u8>, Config) {
        let qd = NQ * HD;
        let kvd = NKV * HD;
        let mut t: Vec<(String, Dt, Vec<usize>, Vec<f32>)> = vec![
            (
                "model.embed_tokens.weight".into(),
                Dt::F32,
                vec![V, MD],
                seq(0.5, V * MD),
            ),
            ("model.norm.weight".into(), Dt::F32, vec![MD], vec![1.0; MD]),
            (
                "lm_head.weight".into(),
                Dt::F32,
                vec![V, MD],
                seq(0.9, V * MD),
            ),
        ];
        for i in 0..NL {
            let base = 10.0 + i as f32 * 7.0;
            let p = |s: &str| format!("model.layers.{i}.{s}");
            t.push((
                p("self_attn.q_proj.weight"),
                qk_dt,
                vec![qd, MD],
                seq(base, qd * MD),
            ));
            t.push((
                p("self_attn.k_proj.weight"),
                qk_dt,
                vec![kvd, MD],
                seq(base + 1.0, kvd * MD),
            ));
            t.push((
                p("self_attn.v_proj.weight"),
                Dt::F32,
                vec![kvd, MD],
                seq(base + 2.0, kvd * MD),
            ));
            t.push((
                p("self_attn.o_proj.weight"),
                Dt::F32,
                vec![MD, qd],
                seq(base + 3.0, MD * qd),
            ));
            t.push((
                p("mlp.gate_proj.weight"),
                Dt::F32,
                vec![HID, MD],
                seq(base + 4.0, HID * MD),
            ));
            t.push((
                p("mlp.up_proj.weight"),
                Dt::F32,
                vec![HID, MD],
                seq(base + 5.0, HID * MD),
            ));
            t.push((
                p("mlp.down_proj.weight"),
                Dt::F32,
                vec![MD, HID],
                seq(base + 6.0, MD * HID),
            ));
            t.push((
                p("input_layernorm.weight"),
                Dt::F32,
                vec![MD],
                vec![1.0; MD],
            ));
            t.push((
                p("post_attention_layernorm.weight"),
                Dt::F32,
                vec![MD],
                vec![1.0; MD],
            ));
        }
        let bytes = write_safetensors(&t);
        let cfg = Config {
            model_dim: MD,
            n_layers: NL,
            n_heads: NQ,
            n_kv_heads: Some(NKV),
            vocab: V,
            hidden: HID,
            eps: 1e-6,
            tied: false,
            head_dim: Some(HD),
            rope_theta: 10000.0,
            rope_scaling: None,
            num_experts: None,
            num_experts_per_tok: None,
            moe_intermediate_size: None,
        };
        (bytes, cfg)
    }

    #[test]
    fn permutation_is_bijective_and_correct() {
        // head_dim 4, 1 head, in_dim 1 → rows [a,b,c,d] → [a,c,b,d]
        let w = vec![10.0, 20.0, 30.0, 40.0];
        let p = permute_qk_hf_to_interleaved(&w, 1, 4, 1).unwrap();
        assert_eq!(p, vec![10.0, 30.0, 20.0, 40.0]);
        // applying twice returns to identity (this permutation is its own inverse
        // for head_dim 4); generally check it's a permutation of the multiset
        let mut sorted = p.clone();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
        assert_eq!(sorted, vec![10.0, 20.0, 30.0, 40.0]);
        // odd head_dim rejected
        assert!(permute_qk_hf_to_interleaved(&[1.0, 2.0, 3.0], 1, 3, 1).is_err());
    }

    #[test]
    fn parses_header_and_offsets() {
        let (bytes, _cfg) = fixture(Dt::F32);
        let st = SafeTensors::parse(&bytes).unwrap();
        assert!(st.names().contains(&"model.embed_tokens.weight"));
        let emb = st.tensor_f32("model.embed_tokens.weight").unwrap();
        assert_eq!(emb.len(), V * MD);
        // missing + truncated error paths
        assert!(matches!(
            st.tensor_f32("nope"),
            Err(LoaderError::MissingTensor(_))
        ));
        assert!(SafeTensors::parse(&[0u8; 4]).is_err());
    }

    #[test]
    fn bf16_dequant_within_tolerance() {
        // a BF16 q_proj round-trips to within bf16 precision of the f32 source
        let (bytes, cfg) = fixture(Dt::Bf16);
        let st = SafeTensors::parse(&bytes).unwrap();
        let q = st
            .tensor_f32("model.layers.0.self_attn.q_proj.weight")
            .unwrap();
        let want = seq(10.0, cfg.n_heads * cfg.head_dim() * cfg.model_dim);
        assert_eq!(q.len(), want.len());
        for (a, b) in q.iter().zip(&want) {
            // bf16 keeps 8 bits of mantissa → ~2^-8 relative
            assert!((a - b).abs() <= 1e-2 * (b.abs() + 1.0), "{a} vs {b}");
        }
    }

    #[test]
    fn unsupported_dtype_errors() {
        // hand-write a header with an unsupported dtype
        let header = "{\"t\":{\"dtype\":\"I8\",\"shape\":[1],\"data_offsets\":[0,1]}}";
        let mut bytes = (header.len() as u64).to_le_bytes().to_vec();
        bytes.extend_from_slice(header.as_bytes());
        bytes.push(0);
        let st = SafeTensors::parse(&bytes).unwrap();
        assert!(matches!(
            st.tensor_f32("t"),
            Err(LoaderError::UnsupportedDtype { .. })
        ));
    }

    #[test]
    fn assembles_a_runnable_model_f32() {
        let (bytes, cfg) = fixture(Dt::F32);
        let mut model = load(&bytes, &cfg).expect("f32 fixture loads");
        // forward a single token → logits of length vocab
        let logits = model.forward(1).expect("forward");
        assert_eq!(logits.len(), V);
        assert!(logits.iter().all(|v: &f32| v.is_finite()));
    }

    #[test]
    fn assembles_a_runnable_model_bf16() {
        let (bytes, cfg) = fixture(Dt::Bf16);
        let mut model = load(&bytes, &cfg).expect("bf16 fixture loads");
        let logits = model.forward(1).expect("forward");
        assert_eq!(logits.len(), V);
    }

    #[test]
    fn deterministic_decode_through_quantllm() {
        let (bytes, cfg) = fixture(Dt::F32);
        let mut llm = load_llm(&bytes, &cfg, Tokenizer::default()).expect("llm builds (vocab 256)");
        let a = llm.generate_ids("hello", 6, 42).expect("gen a");
        let b = llm.generate_ids("hello", 6, 42).expect("gen b");
        assert_eq!(a, b, "greedy decode must be reproducible per seed");
        assert_eq!(a.len(), 6);
        // NOT asserted: semantic coherence — the fixture weights are synthetic;
        // real-model coherence is the gated follow-up.
    }

    // ---- Configurable load: precision + sampler (SDD-953) ----

    #[test]
    fn load_at_precision_builds_non_f32_runtime() {
        // Real weights (parsed f32) quantized DOWN into the runtime block at a
        // caller-chosen precision — the 7B-≠-28GB path. Each variant must still
        // produce finite logits from the synthetic fixture.
        let (bytes, cfg) = fixture(Dt::F32);
        for p in [
            Precision::Bf16,
            Precision::Int8,
            Precision::Nvfp4,
            Precision::Ternary,
        ] {
            let mut model = load_at_precision(&bytes, &cfg, p)
                .unwrap_or_else(|e| panic!("load at {p:?} failed: {e:?}"));
            let logits = model.forward(1).expect("forward");
            assert_eq!(logits.len(), V, "{p:?} vocab width");
            assert!(
                logits.iter().all(|v: &f32| v.is_finite()),
                "{p:?} logits finite"
            );
        }
    }

    #[test]
    fn load_defaults_to_f32_greedy() {
        // The default loader is exactly load_configured(.., F32, greedy()).
        let (bytes, cfg) = fixture(Dt::F32);
        let model = load(&bytes, &cfg).expect("load");
        assert_eq!(
            model.sampler().config.temperature,
            0.0,
            "default sampler is greedy"
        );
    }

    #[test]
    fn load_with_sampler_threads_temperature() {
        // The loader hardwires greedy; load_with_sampler lets a caller pick the
        // temperature so it is honored at decode time.
        let (bytes, cfg) = fixture(Dt::F32);
        let sampler = Sampler::new(sovereign_sampler::SamplerConfig {
            temperature: 0.7,
            ..Default::default()
        });
        let model = load_with_sampler(&bytes, &cfg, sampler).expect("load with sampler");
        assert_eq!(model.sampler().config.temperature, 0.7);
    }

    #[test]
    fn load_configured_sets_both_axes() {
        // Both knobs at once: a non-f32 runtime precision AND a non-greedy sampler.
        let (bytes, cfg) = fixture(Dt::F32);
        let sampler = Sampler::new(sovereign_sampler::SamplerConfig {
            temperature: 0.5,
            top_k: Some(20),
            ..Default::default()
        });
        let mut model =
            load_configured(&bytes, &cfg, Precision::Int8, sampler).expect("configured load");
        assert_eq!(model.sampler().config.temperature, 0.5);
        assert_eq!(model.sampler().config.top_k, Some(20));
        let logits = model.forward(1).expect("forward");
        assert_eq!(logits.len(), V);
    }

    // ---- RoPE config parsing (SDD-950) ----

    #[test]
    fn rope_theta_defaults_to_10000_when_absent() {
        let cfg = Config::from_json(
            br#"{"hidden_size":8,"num_hidden_layers":1,"num_attention_heads":2,
                 "vocab_size":16,"intermediate_size":16}"#,
        )
        .unwrap();
        assert_eq!(cfg.rope_theta, 10000.0);
        assert!(cfg.rope_scaling.is_none());
        assert!(cfg.rope_scaling_resolved().is_none());
    }

    #[test]
    fn rope_theta_parsed_from_config() {
        // A Llama-3-shaped base must survive the round trip.
        let cfg = Config::from_json(
            br#"{"hidden_size":8,"num_hidden_layers":1,"num_attention_heads":2,
                 "vocab_size":16,"intermediate_size":16,"rope_theta":500000.0}"#,
        )
        .unwrap();
        assert_eq!(cfg.rope_theta, 500000.0);
    }

    #[test]
    fn rope_scaling_linear_resolves() {
        // Older "type" key.
        let cfg = Config::from_json(
            br#"{"hidden_size":8,"num_hidden_layers":1,"num_attention_heads":2,
                 "vocab_size":16,"intermediate_size":16,
                 "rope_scaling":{"type":"linear","factor":4.0}}"#,
        )
        .unwrap();
        let s = cfg.rope_scaling_resolved().expect("resolves");
        assert_eq!(s.kind, RopeScalingKind::Linear);
        assert_eq!(s.factor, 4.0);
    }

    #[test]
    fn rope_scaling_llama3_resolves_with_original_ctx() {
        // Newer "rope_type" key + the Llama-3.1 shape.
        let cfg = Config::from_json(
            br#"{"hidden_size":8,"num_hidden_layers":1,"num_attention_heads":2,
                 "vocab_size":16,"intermediate_size":16,"rope_theta":500000.0,
                 "rope_scaling":{"rope_type":"llama3","factor":8.0,
                   "original_max_position_embeddings":8192,
                   "low_freq_factor":1.0,"high_freq_factor":4.0}}"#,
        )
        .unwrap();
        assert_eq!(cfg.rope_theta, 500000.0);
        let s = cfg.rope_scaling_resolved().expect("resolves");
        assert_eq!(s.kind, RopeScalingKind::Llama3);
        assert_eq!(s.factor, 8.0);
        assert_eq!(s.original_ctx, Some(8192));
    }

    #[test]
    fn rope_scaling_yarn_carries_betas() {
        let cfg = Config::from_json(
            br#"{"hidden_size":8,"num_hidden_layers":1,"num_attention_heads":2,
                 "vocab_size":16,"intermediate_size":16,
                 "rope_scaling":{"rope_type":"yarn","factor":4.0,
                   "original_max_position_embeddings":4096,
                   "beta_fast":32.0,"beta_slow":1.0}}"#,
        )
        .unwrap();
        let s = cfg.rope_scaling_resolved().expect("resolves");
        assert_eq!(s.kind, RopeScalingKind::Yarn);
        assert_eq!(s.original_ctx, Some(4096));
        assert_eq!((s.beta_fast, s.beta_slow), (32.0, 1.0));
    }

    #[test]
    fn unknown_rope_type_yields_no_scaling_not_an_error() {
        // Honest: an unrecognized type falls back to base-theta only, never a
        // fabricated scaling and never a parse failure.
        let cfg = Config::from_json(
            br#"{"hidden_size":8,"num_hidden_layers":1,"num_attention_heads":2,
                 "vocab_size":16,"intermediate_size":16,
                 "rope_scaling":{"rope_type":"someNewMethod","factor":2.0}}"#,
        )
        .unwrap();
        assert!(cfg.rope_scaling.is_some(), "the block is parsed");
        assert!(
            cfg.rope_scaling_resolved().is_none(),
            "but resolves to no scaling"
        );
    }

    // ── malformed / adversarial input hardening (2026-07-17) ─────────────────
    // Everything below is reachable via `/v1/models/load` (a crafted model dir
    // or a corrupt download). None may panic — each returns a clean error.

    #[test]
    fn config_rejects_zero_num_attention_heads() {
        // the div-by-zero: head_dim = model_dim / n_heads.
        let r = Config::from_json(
            br#"{"hidden_size":8,"num_hidden_layers":1,"num_attention_heads":0,
                 "vocab_size":16,"intermediate_size":16}"#,
        );
        assert!(matches!(r, Err(LoaderError::InvalidConfig(_))));
    }

    #[test]
    fn config_rejects_every_zero_dimension() {
        let base = |field: &str| {
            let mut m = std::collections::BTreeMap::from([
                ("hidden_size", 8),
                ("num_hidden_layers", 1),
                ("num_attention_heads", 2),
                ("vocab_size", 16),
                ("intermediate_size", 16),
            ]);
            m.insert(field, 0);
            let body = m
                .iter()
                .map(|(k, v)| format!("\"{k}\":{v}"))
                .collect::<Vec<_>>()
                .join(",");
            Config::from_json(format!("{{{body}}}").as_bytes())
        };
        for field in [
            "hidden_size",
            "num_hidden_layers",
            "num_attention_heads",
            "vocab_size",
            "intermediate_size",
        ] {
            assert!(
                matches!(base(field), Err(LoaderError::InvalidConfig(_))),
                "zero {field} must be rejected"
            );
        }
    }

    #[test]
    fn head_dim_never_divides_by_zero() {
        // even a directly-constructed (validation-skipping) Config must not panic.
        let cfg = Config {
            model_dim: 8,
            n_layers: 1,
            n_heads: 0,
            n_kv_heads: None,
            vocab: 16,
            hidden: 16,
            eps: 1e-6,
            tied: false,
            head_dim: None,
            rope_theta: 10000.0,
            rope_scaling: None,
            num_experts: None,
            num_experts_per_tok: None,
            moe_intermediate_size: None,
        };
        let _ = cfg.head_dim(); // must not panic
    }

    #[test]
    fn overflowing_data_offsets_are_out_of_range_not_a_panic() {
        // a header whose data_offsets wrap `data_start + offset` in usize must be
        // rejected, never wrap-around into a valid-looking slice.
        let header = format!(
            "{{\"t\":{{\"dtype\":\"F32\",\"shape\":[1],\"data_offsets\":[{},{}]}}}}",
            usize::MAX,
            usize::MAX
        );
        let mut bytes = (header.len() as u64).to_le_bytes().to_vec();
        bytes.extend_from_slice(header.as_bytes());
        bytes.extend_from_slice(&[0u8; 4]);
        let st = SafeTensors::parse(&bytes).expect("header parses");
        assert!(matches!(st.tensor_f32("t"), Err(LoaderError::Truncated(_))));
    }

    #[test]
    fn giant_but_non_overflowing_offsets_are_out_of_range() {
        let header =
            "{\"t\":{\"dtype\":\"F32\",\"shape\":[1],\"data_offsets\":[0,1000000000]}}".to_string();
        let mut bytes = (header.len() as u64).to_le_bytes().to_vec();
        bytes.extend_from_slice(header.as_bytes());
        bytes.extend_from_slice(&[0u8; 4]);
        let st = SafeTensors::parse(&bytes).expect("header parses");
        assert!(matches!(st.tensor_f32("t"), Err(LoaderError::Truncated(_))));
    }

    #[test]
    fn elems_rejects_overflowing_product() {
        // a small product is fine…
        assert_eq!(elems(&[3, 4, 5]).unwrap(), 60);
        // …but a product that overflows usize is an error, never a wrap.
        assert!(matches!(
            elems(&[usize::MAX, 2]),
            Err(LoaderError::InvalidConfig(_))
        ));
    }

    #[test]
    fn load_rejects_zero_head_config_without_panicking() {
        // end-to-end: a real fixture body but a config with n_heads=0 → the
        // assembly path's validate() gate catches it before head_dim divides.
        let (bytes, mut cfg) = fixture(Dt::F32);
        cfg.n_heads = 0;
        assert!(matches!(
            load(&bytes, &cfg),
            Err(LoaderError::InvalidConfig(_))
        ));
    }

    // ---- Mixture-of-experts assembly (MoE Increment 2) ---------------------

    // A MoE variant of `fixture`: identical attention half, but each layer's
    // FFN is a router (`mlp.gate.weight`, `[N_EXP, MD]`) plus `N_EXP` expert
    // SwiGLUs (`mlp.experts.{e}.{gate,up,down}_proj.weight`) at width `MOE_HID`.
    // It deliberately writes NO `mlp.gate_proj/up_proj/down_proj`, so a load
    // that succeeds proves the MoE branch (not the dense one) was taken.
    const N_EXP: usize = 4;
    const MOE_HID: usize = 12;

    fn moe_fixture(experts_per_tok: usize) -> (Vec<u8>, Config) {
        let qd = NQ * HD;
        let kvd = NKV * HD;
        let mut t: Vec<(String, Dt, Vec<usize>, Vec<f32>)> = vec![
            (
                "model.embed_tokens.weight".into(),
                Dt::F32,
                vec![V, MD],
                seq(0.5, V * MD),
            ),
            ("model.norm.weight".into(), Dt::F32, vec![MD], vec![1.0; MD]),
            (
                "lm_head.weight".into(),
                Dt::F32,
                vec![V, MD],
                seq(0.9, V * MD),
            ),
        ];
        for i in 0..NL {
            let base = 10.0 + i as f32 * 7.0;
            let p = |s: &str| format!("model.layers.{i}.{s}");
            t.push((
                p("self_attn.q_proj.weight"),
                Dt::F32,
                vec![qd, MD],
                seq(base, qd * MD),
            ));
            t.push((
                p("self_attn.k_proj.weight"),
                Dt::F32,
                vec![kvd, MD],
                seq(base + 1.0, kvd * MD),
            ));
            t.push((
                p("self_attn.v_proj.weight"),
                Dt::F32,
                vec![kvd, MD],
                seq(base + 2.0, kvd * MD),
            ));
            t.push((
                p("self_attn.o_proj.weight"),
                Dt::F32,
                vec![MD, qd],
                seq(base + 3.0, MD * qd),
            ));
            t.push((
                p("input_layernorm.weight"),
                Dt::F32,
                vec![MD],
                vec![1.0; MD],
            ));
            t.push((
                p("post_attention_layernorm.weight"),
                Dt::F32,
                vec![MD],
                vec![1.0; MD],
            ));
            // MoE FFN: router + per-expert SwiGLU bank.
            t.push((
                p("mlp.gate.weight"),
                Dt::F32,
                vec![N_EXP, MD],
                seq(base + 4.0, N_EXP * MD),
            ));
            for e in 0..N_EXP {
                let ep = |s: &str| format!("model.layers.{i}.mlp.experts.{e}.{s}");
                let eb = base + 5.0 + e as f32 * 3.0;
                t.push((
                    ep("gate_proj.weight"),
                    Dt::F32,
                    vec![MOE_HID, MD],
                    seq(eb, MOE_HID * MD),
                ));
                t.push((
                    ep("up_proj.weight"),
                    Dt::F32,
                    vec![MOE_HID, MD],
                    seq(eb + 1.0, MOE_HID * MD),
                ));
                t.push((
                    ep("down_proj.weight"),
                    Dt::F32,
                    vec![MD, MOE_HID],
                    seq(eb + 2.0, MD * MOE_HID),
                ));
            }
        }
        let bytes = write_safetensors(&t);
        let cfg = Config {
            model_dim: MD,
            n_layers: NL,
            n_heads: NQ,
            n_kv_heads: Some(NKV),
            vocab: V,
            hidden: HID,
            eps: 1e-6,
            tied: false,
            head_dim: Some(HD),
            rope_theta: 10000.0,
            rope_scaling: None,
            num_experts: Some(N_EXP),
            num_experts_per_tok: Some(experts_per_tok),
            moe_intermediate_size: Some(MOE_HID),
        };
        (bytes, cfg)
    }

    #[test]
    fn assembles_a_runnable_moe_model() {
        // Loads a model whose ONLY FFN tensors are the MoE router + experts —
        // success means the loader built MoE blocks (a dense build would fail on
        // the absent `mlp.gate_proj.weight`).
        let (bytes, cfg) = moe_fixture(2);
        assert!(cfg.is_moe());
        assert_eq!(cfg.experts(), N_EXP);
        assert_eq!(cfg.experts_per_tok(), 2);
        assert_eq!(cfg.moe_hidden(), MOE_HID);
        let mut model = load(&bytes, &cfg).expect("MoE fixture loads");
        assert_eq!(model.layers(), NL);
        let logits = model.forward(1).expect("forward");
        assert_eq!(logits.len(), V);
        assert!(logits.iter().all(|v: &f32| v.is_finite()));
    }

    #[test]
    fn moe_deterministic_decode_through_quantllm() {
        let (bytes, cfg) = moe_fixture(2);
        let mut llm =
            load_llm(&bytes, &cfg, Tokenizer::default()).expect("MoE llm builds (vocab 256)");
        let a = llm.generate_ids("hello", 6, 42).expect("gen a");
        let b = llm.generate_ids("hello", 6, 42).expect("gen b");
        assert_eq!(a, b, "greedy MoE decode must be reproducible per seed");
        assert_eq!(a.len(), 6);
    }

    #[test]
    fn moe_top1_and_full_topk_both_run() {
        // top-1 (one expert per token) and top-N (all experts blended) are both
        // valid activation counts and both produce finite logits.
        for k in [1, N_EXP] {
            let (bytes, cfg) = moe_fixture(k);
            let mut model = load(&bytes, &cfg).unwrap_or_else(|e| panic!("top-{k} load: {e:?}"));
            let logits = model.forward(2).expect("forward");
            assert_eq!(logits.len(), V);
            assert!(logits.iter().all(|v: &f32| v.is_finite()), "top-{k} finite");
        }
    }

    #[test]
    fn moe_load_at_precision_quantizes_experts() {
        // The expert bank + router quantize DOWN into the runtime block at a
        // caller-chosen precision, exactly like the dense path.
        let (bytes, cfg) = moe_fixture(2);
        for p in [Precision::Int8, Precision::Nvfp4, Precision::Ternary] {
            let mut model = load_at_precision(&bytes, &cfg, p)
                .unwrap_or_else(|e| panic!("MoE load at {p:?} failed: {e:?}"));
            let logits = model.forward(1).expect("forward");
            assert_eq!(logits.len(), V, "{p:?} vocab width");
            assert!(logits.iter().all(|v: &f32| v.is_finite()), "{p:?} finite");
        }
    }

    #[test]
    fn moe_config_missing_router_tensor_errors() {
        // A MoE config pointed at a DENSE fixture body must fail on the absent
        // router tensor — proving the loader switched to the MoE tensor names.
        let (bytes, dense_cfg) = fixture(Dt::F32);
        let mut moe_cfg = dense_cfg;
        moe_cfg.num_experts = Some(N_EXP);
        moe_cfg.num_experts_per_tok = Some(2);
        moe_cfg.moe_intermediate_size = Some(HID);
        assert!(matches!(
            load(&bytes, &moe_cfg),
            Err(LoaderError::MissingTensor(_))
        ));
    }

    #[test]
    fn moe_config_rejects_bad_topk() {
        // top-k over the expert count, or zero, is rejected at validate().
        let (_, mut cfg) = moe_fixture(2);
        cfg.num_experts_per_tok = Some(N_EXP + 1);
        assert!(matches!(cfg.validate(), Err(LoaderError::InvalidConfig(_))));
        cfg.num_experts_per_tok = Some(0);
        assert!(matches!(cfg.validate(), Err(LoaderError::InvalidConfig(_))));
    }

    #[test]
    fn moe_config_parses_both_expert_spellings() {
        // `num_experts` (Qwen3-MoE) and `num_local_experts` (Mixtral) both map to
        // the same field; `num_experts_per_tok` and `moe_intermediate_size` too.
        let qwen = br#"{"hidden_size":8,"num_hidden_layers":2,"num_attention_heads":2,
             "num_key_value_heads":1,"vocab_size":256,"intermediate_size":16,
             "num_experts":4,"num_experts_per_tok":2,"moe_intermediate_size":12}"#;
        let c = Config::from_json(qwen).expect("qwen moe config");
        assert!(c.is_moe());
        assert_eq!(c.experts(), 4);
        assert_eq!(c.experts_per_tok(), 2);
        assert_eq!(c.moe_hidden(), 12);

        let mixtral = br#"{"hidden_size":8,"num_hidden_layers":2,"num_attention_heads":2,
             "num_key_value_heads":1,"vocab_size":256,"intermediate_size":16,
             "num_local_experts":8,"num_experts_per_tok":2}"#;
        let m = Config::from_json(mixtral).expect("mixtral moe config");
        assert!(m.is_moe());
        assert_eq!(m.experts(), 8);
        // moe_intermediate_size absent → falls back to the dense intermediate.
        assert_eq!(m.moe_hidden(), 16);
    }

    #[test]
    fn dense_config_is_not_moe() {
        // No experts, or a degenerate single expert, is a dense model.
        let (_, dense) = fixture(Dt::F32);
        assert!(!dense.is_moe());
        assert_eq!(dense.experts_per_tok(), 0);
        let (_, mut one) = moe_fixture(1);
        one.num_experts = Some(1); // a 1-expert "MoE" is just dense
        assert!(!one.is_moe());
    }
}
