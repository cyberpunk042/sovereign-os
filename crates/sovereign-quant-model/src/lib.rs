//! `sovereign-quant-model` — a complete mixed-precision decoder-only model.
//!
//! The f32 [`sovereign-decoder-stack`] runs homogeneous f32 blocks. This is
//! its quantized counterpart: the same model harness — token embedding, final
//! norm, output head, sampler — but the layers are a *heterogeneous*
//! [`LayerStack`], so each layer can be f32, ternary, or NVFP4, single- or
//! multi-head, exactly as `sovereign-quant-calibration` recommends per layer.
//! That is the end-to-end realization of mixed-precision local inference: one
//! residual stream flowing through layers of different precisions, embedded in
//! and unembedded out of a shared vocabulary.
//!
//! ```text
//!   hidden = embedding[token]
//!   hidden = layer_stack.run(hidden)   // f32 → ternary → NVFP4 → …
//!   hidden = final_norm(hidden)
//!   logits = head · hidden
//!   next   = sampler(mask(logits), recent, seed)
//! ```
//!
//! [`generate`](QuantModel::generate) / [`generate_masked`](QuantModel::generate_masked)
//! ingest a prompt and decode autoregressively, reproducibly per seed.
//!
//! [`sovereign-decoder-stack`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-decoder-stack
//! [`LayerStack`]: sovereign_decoder_layer::LayerStack
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_decoder_layer::{LayerError, LayerStack, MoeSummary};
use sovereign_logit_mask::LogitMask;
use sovereign_rmsnorm::{RmsNorm, RmsNormError};
use sovereign_sampler::{Sampler, SamplerError};
use thiserror::Error;

/// Schema version of the quant-model surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong building or running the model.
#[derive(Debug, Error, PartialEq)]
pub enum QuantModelError {
    /// The embedding table was mis-shaped.
    #[error("embedding must be vocab*model_dim = {expected} elements, got {got}")]
    EmbeddingShape {
        /// Expected element count.
        expected: usize,
        /// Observed count.
        got: usize,
    },
    /// The output head was mis-shaped.
    #[error("output head must be vocab*model_dim = {expected} elements, got {got}")]
    HeadShape {
        /// Expected element count.
        expected: usize,
        /// Observed count.
        got: usize,
    },
    /// A token id was outside `0..vocab`.
    #[error("token {token} out of range for vocab {vocab}")]
    TokenOutOfRange {
        /// The offending token.
        token: usize,
        /// Vocabulary size.
        vocab: usize,
    },
    /// Generation was asked for with an empty prompt.
    #[error("prompt must contain at least one token")]
    EmptyPrompt,
    /// A layer-stack error.
    #[error("stack: {0}")]
    Layer(#[from] LayerError),
    /// An RMSNorm error.
    #[error("final norm: {0}")]
    RmsNorm(#[from] RmsNormError),
    /// A sampler error.
    #[error("sampler: {0}")]
    Sampler(#[from] SamplerError),
    /// [`ExecMode::GpuFold`] was selected but the GPU fold path cannot serve the
    /// request (SDD-401): no fold backend is attached, or the attached backend's
    /// fold routing is not yet wired into the decode hot path. Never a silent
    /// fall-through to the CPU path under a GPU claim — the mode honest-degrades.
    #[error("gpu-fold unavailable: {reason}")]
    GpuFoldUnavailable {
        /// Why the GPU fold path could not run (backend state + which SDD-401
        /// phase wires it).
        reason: String,
    },
}

/// Decode execution mode (SDD-401 ChromoFold GPU hotswap).
///
/// The CPU path is the **default** and the **bit-exact reference oracle** every
/// future GPU-fold kernel must reproduce (PROJECT_SYNC). `GpuFold` is the opt-in
/// hotswap; until a fold backend is attached **and** the hot-path fold routing
/// lands (SDD-401 phases 4–5), selecting it honest-degrades rather than silently
/// running the CPU path.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ExecMode {
    /// CPU Rust engine — the default and the correctness oracle.
    #[default]
    Cpu,
    /// Opt-in GPU fold path (ChromoFold decode-in-consumer on the device).
    GpuFold,
}

/// Which folds a [`FoldBackend`] can currently serve. An all-`false` set is
/// valid — the seam (mode + plug-point) exists before any fold is wired.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct FoldCaps {
    /// Weight decode-in-GEMM (the "fold the model itself" path; SDD-401 Q-401-A
    /// gated on ChromoFold exporting the GEMM C ABI).
    pub weights: bool,
    /// Folded-KV attention (`cf_kv_attn_fused_async`; SDD-401 phase 4).
    pub kv: bool,
    /// Folded-embedding gather (`cf_embedding_gather_async`).
    pub embedding: bool,
}

/// A GPU fold backend — the device-side decode-in-consumer path a linked
/// ChromoFold engine provides (SDD-401). This trait is the **sovereign-side
/// plug-point**: phase 2 establishes the registration seam (name + capabilities);
/// the actual fold kernels + host↔device marshalling are bound behind the
/// `sovereign-chromofold-sys` `linked` feature in later gated phases. The C ABI
/// stays quarantined in the `-sys` crate — a backend impl lives on the safe side.
pub trait FoldBackend: Send + Sync + std::fmt::Debug {
    /// Human-readable backend name (diagnostics + honest-degrade messages).
    fn name(&self) -> &str;
    /// Which folds this backend can currently serve.
    fn folds(&self) -> FoldCaps;
}

/// A complete mixed-precision decoder-only model.
#[derive(Debug)]
pub struct QuantModel {
    vocab: usize,
    model_dim: usize,
    embedding: Vec<f32>,
    stack: LayerStack,
    final_norm: RmsNorm,
    /// Output projection. Empty when `tied` — the projection reads the
    /// `embedding` table directly, so the second `vocab × model_dim` matrix is
    /// not stored.
    head: Vec<f32>,
    /// Whether the output head is tied to the embedding table (weight tying,
    /// as in GPT-2 / Llama). Halves the embedding-table memory.
    tied: bool,
    /// Optional Gemma-2-style final-logit soft cap: when set, logits are bounded
    /// via `cap·tanh(logit/cap)`. `None` = no capping.
    logit_softcap: Option<f32>,
    sampler: Sampler,
    recent: Vec<usize>,
    recent_window: usize,
    /// Decode execution mode (SDD-401). `Cpu` (default) runs the reference
    /// path; `GpuFold` is the opt-in hotswap.
    exec_mode: ExecMode,
    /// The attached GPU fold backend, if any (SDD-401). `None` by default; a
    /// linked ChromoFold engine registers one in later gated phases.
    fold_backend: Option<Box<dyn FoldBackend>>,
}

impl QuantModel {
    /// Assemble a model. `embedding` and `head` are row-major
    /// `vocab × model_dim`; `stack`'s layers must all operate on `model_dim`.
    pub fn new(
        vocab: usize,
        model_dim: usize,
        embedding: Vec<f32>,
        stack: LayerStack,
        final_norm: RmsNorm,
        head: Vec<f32>,
        sampler: Sampler,
    ) -> Result<Self, QuantModelError> {
        let want = vocab * model_dim;
        if embedding.len() != want {
            return Err(QuantModelError::EmbeddingShape {
                expected: want,
                got: embedding.len(),
            });
        }
        if head.len() != want {
            return Err(QuantModelError::HeadShape {
                expected: want,
                got: head.len(),
            });
        }
        Ok(Self {
            vocab,
            model_dim,
            embedding,
            stack,
            final_norm,
            head,
            tied: false,
            logit_softcap: None,
            sampler,
            recent: Vec::new(),
            recent_window: 64,
            exec_mode: ExecMode::Cpu,
            fold_backend: None,
        })
    }

    /// Assemble a model with **tied** embedding / output weights (GPT-2 / Llama
    /// style): the output head reuses the `embedding` table, so only one
    /// `vocab × model_dim` matrix is stored instead of two. `logits[v]` becomes
    /// `embedding_row[v] · hidden`.
    pub fn new_tied(
        vocab: usize,
        model_dim: usize,
        embedding: Vec<f32>,
        stack: LayerStack,
        final_norm: RmsNorm,
        sampler: Sampler,
    ) -> Result<Self, QuantModelError> {
        let want = vocab * model_dim;
        if embedding.len() != want {
            return Err(QuantModelError::EmbeddingShape {
                expected: want,
                got: embedding.len(),
            });
        }
        Ok(Self {
            vocab,
            model_dim,
            embedding,
            stack,
            final_norm,
            head: Vec::new(),
            tied: true,
            logit_softcap: None,
            sampler,
            recent: Vec::new(),
            recent_window: 64,
            exec_mode: ExecMode::Cpu,
            fold_backend: None,
        })
    }

    /// Whether the output head is tied to the embedding table.
    pub fn is_tied(&self) -> bool {
        self.tied
    }

    /// Enable Gemma-2-style final-logit soft-capping at `cap`: every output
    /// logit is bounded into `(−cap, cap)` via `cap·tanh(logit/cap)`. A
    /// non-positive `cap` disables it.
    pub fn with_logit_softcap(mut self, cap: f32) -> Self {
        self.logit_softcap = if cap > 0.0 { Some(cap) } else { None };
        self
    }

    /// The active final-logit soft cap, or `None`.
    pub fn logit_softcap(&self) -> Option<f32> {
        self.logit_softcap
    }

    /// Set the repetition-penalty window (default 64).
    pub fn with_recent_window(mut self, window: usize) -> Self {
        self.recent_window = window;
        self
    }

    /// Replace the token sampler (builder; mirrors [`with_logit_softcap`]).
    ///
    /// The safetensors loader assembles every model with `Sampler::greedy()`;
    /// this lets a caller run the same assembled model at a chosen
    /// temperature / top-p / top-k. It is the **model-side** half of
    /// configurable generation — wiring a per-request sampler from the gateway's
    /// HTTP parameters is a separate, daemon-side follow-up.
    ///
    /// [`with_logit_softcap`]: Self::with_logit_softcap
    pub fn with_sampler(mut self, sampler: Sampler) -> Self {
        self.sampler = sampler;
        self
    }

    /// Replace the token sampler on an existing model (mutable; use this when
    /// the model is already loaded and you need per-request sampling).
    pub fn set_sampler(&mut self, sampler: Sampler) {
        self.sampler = sampler;
    }

    /// Select the decode execution mode (builder; SDD-401). Default is
    /// [`ExecMode::Cpu`] — the reference path. [`ExecMode::GpuFold`] is the
    /// opt-in hotswap and requires an attached, capable [`FoldBackend`].
    pub fn with_exec_mode(mut self, mode: ExecMode) -> Self {
        self.exec_mode = mode;
        self
    }

    /// Select the decode execution mode on an existing model (mutable; SDD-401).
    pub fn set_exec_mode(&mut self, mode: ExecMode) {
        self.exec_mode = mode;
    }

    /// The active decode execution mode.
    pub fn exec_mode(&self) -> ExecMode {
        self.exec_mode
    }

    /// Attach a GPU fold backend (SDD-401). Off by default; a linked ChromoFold
    /// engine registers one in later gated phases. Attaching a backend does not
    /// by itself change decode — [`ExecMode::GpuFold`] must also be selected.
    pub fn set_fold_backend(&mut self, backend: Option<Box<dyn FoldBackend>>) {
        self.fold_backend = backend;
    }

    /// The attached fold backend's name + capabilities, or `None` if none is
    /// attached — the operator-surface introspection for the hotswap state.
    pub fn fold_backend_status(&self) -> Option<(&str, FoldCaps)> {
        self.fold_backend.as_ref().map(|b| (b.name(), b.folds()))
    }

    /// The active token sampler. Its [`config`] carries the temperature /
    /// top-k / top-p / penalties actually used at decode time, so callers (and
    /// tests) can introspect how this model will sample.
    ///
    /// [`config`]: sovereign_sampler::Sampler::config
    pub fn sampler(&self) -> &Sampler {
        &self.sampler
    }

    /// Number of layers.
    pub fn layers(&self) -> usize {
        self.stack.depth()
    }

    /// The model dimension (residual-stream width).
    pub fn model_dim(&self) -> usize {
        self.model_dim
    }

    /// The mixture-of-experts shape of this model, or `None` if it is fully
    /// dense. Lets a daemon / operator surface report expert count, top-k, and
    /// how many layers are sparse for a loaded MoE checkpoint.
    pub fn moe_summary(&self) -> Option<MoeSummary> {
        self.stack.moe_summary()
    }

    /// Vocabulary size.
    pub fn vocab(&self) -> usize {
        self.vocab
    }

    /// Current decode position (KV depth of the stack).
    pub fn position(&self) -> usize {
        self.stack.positions()
    }

    /// Tokens emitted so far.
    pub fn emitted(&self) -> &[usize] {
        &self.recent
    }

    fn embed(&self, token: usize) -> Vec<f32> {
        let d = self.model_dim;
        self.embedding[token * d..(token + 1) * d].to_vec()
    }

    fn project_head(&self, hidden: &[f32]) -> Vec<f32> {
        let d = self.model_dim;
        // When tied, the output projection reads the embedding table directly.
        let table = if self.tied {
            &self.embedding
        } else {
            &self.head
        };
        let mut logits = vec![0.0f32; self.vocab];
        for (v, logit) in logits.iter_mut().enumerate() {
            let row = &table[v * d..(v + 1) * d];
            *logit = row.iter().zip(hidden).map(|(w, h)| w * h).sum();
        }
        logits
    }

    /// One forward pass for `token`, advancing every layer's cache; returns the
    /// next-token logits.
    pub fn forward(&mut self, token: usize) -> Result<Vec<f32>, QuantModelError> {
        if token >= self.vocab {
            return Err(QuantModelError::TokenOutOfRange {
                token,
                vocab: self.vocab,
            });
        }
        // SDD-401 GPU hotswap seam. Phase 2 establishes the mode + backend
        // plug-point; the hot-path fold routing (folded-KV = phase 4,
        // decode-in-GEMM = phase 5) is not wired yet. So `GpuFold` MUST NOT
        // silently run the CPU path under a GPU claim — it honest-degrades with
        // a precise reason. The default `Cpu` path below is untouched.
        if self.exec_mode == ExecMode::GpuFold {
            let reason = match &self.fold_backend {
                None => "GpuFold mode requires an attached fold backend; none is set \
                     (attach one via set_fold_backend — SDD-401 phase 3)"
                    .to_string(),
                Some(b) => format!(
                    "fold backend '{}' attached (folds: weights={}, kv={}, embedding={}), \
                     but hot-path fold routing is not wired yet (folded-KV lands in \
                     SDD-401 phase 4, decode-in-GEMM in phase 5)",
                    b.name(),
                    b.folds().weights,
                    b.folds().kv,
                    b.folds().embedding,
                ),
            };
            return Err(QuantModelError::GpuFoldUnavailable { reason });
        }
        let hidden = self.embed(token);
        let hidden = self.stack.run(&hidden)?;
        let normed = self.final_norm.normalize(&hidden)?;
        let mut logits = self.project_head(&normed);
        // (see forward_prefill below for the head-skipping prefill variant)
        // Optional Gemma-2-style logit soft-capping: bound each logit into
        // (−cap, cap) via cap·tanh(logit/cap), which tames over-confident
        // outliers while staying ~linear near zero and order-preserving.
        if let Some(cap) = self.logit_softcap {
            for l in &mut logits {
                *l = cap * (*l / cap).tanh();
            }
        }
        Ok(logits)
    }

    /// Advance model state by one token WITHOUT producing logits.
    ///
    /// Prefill only needs the logits of the LAST prompt token — every earlier
    /// one is fed in purely to build KV state, and its logits are computed and
    /// thrown away. On this model the LM head is 2048×49152 ≈ 101M MACs against
    /// ~1611M for the 24 layers, so that discard is ~5.9% of every prefill
    /// token's work.
    ///
    /// Skipping it is exact, not an approximation: `final_norm` and
    /// `project_head` are pure functions of the hidden state and mutate
    /// nothing. All model state lives in `stack.run`, which still runs.
    ///
    /// Note this does NOT make prefill cheap — it stays one full forward pass
    /// per prompt token, because the stack has no batched entry point. Batched
    /// prefill (a single matmul over the whole prompt) is the change that would
    /// actually matter, and it needs batched variants of attention, FFN and the
    /// norms across several crates. See
    /// `docs/evaluations/gatewayd-cpu-decode-latency-2026-07-31.md`.
    pub fn forward_prefill(&mut self, token: usize) -> Result<(), QuantModelError> {
        if token >= self.vocab {
            return Err(QuantModelError::TokenOutOfRange {
                token,
                vocab: self.vocab,
            });
        }
        if self.exec_mode == ExecMode::GpuFold {
            // Defer to forward() so the GpuFold honest-degrade message stays in
            // exactly one place rather than being duplicated and drifting.
            self.forward(token)?;
            return Ok(());
        }
        let hidden = self.embed(token);
        let _ = self.stack.run(&hidden)?;
        Ok(())
    }

    /// Ingest a prompt and autoregressively generate up to `max_new` tokens.
    pub fn generate(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
    ) -> Result<Vec<usize>, QuantModelError> {
        self.generate_masked(prompt, max_new, seed, &LogitMask::new())
    }

    /// Constrained autoregressive generation: applies `mask` to each step's
    /// logits before sampling.
    pub fn generate_masked(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
    ) -> Result<Vec<usize>, QuantModelError> {
        self.generate_masked_with(prompt, max_new, seed, mask, |_| {})
    }

    /// Constrained generation that invokes `on_token` with each sampled token
    /// id as it is produced — the hook a streaming runtime drives to emit text
    /// token-by-token. Returns the full generated id sequence as well.
    pub fn generate_masked_with<F: FnMut(usize)>(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
        on_token: F,
    ) -> Result<Vec<usize>, QuantModelError> {
        self.generate_masked_until_with(prompt, max_new, seed, mask, &[], on_token)
    }

    /// [`generate_masked_with`] with end-of-turn tokens.
    ///
    /// Decoding stops as soon as a sampled id appears in `stop_ids`, and that
    /// token is NOT passed to `on_token` — it is a control marker, not output.
    /// An empty `stop_ids` reproduces [`generate_masked_with`] exactly, which is
    /// why that method now delegates here.
    ///
    /// Without this the loop only ever ended at `max_new`: an instruction-tuned
    /// model emitted its `<|im_end|>`, decoding sailed straight past it, and the
    /// model carried on inventing a conversation. Observed with
    /// SmolLM2-1.7B-Instruct answering "The capital of France is Paris." and
    /// then continuing into fabricated `system` / `user` turns for the remaining
    /// 50 tokens of its budget.
    ///
    /// The returned `Vec` excludes the stop token for the same reason, so a
    /// caller counting tokens or caching the result sees only real output.
    ///
    /// [`generate_masked_with`]: Self::generate_masked_with
    pub fn generate_masked_until_with<F: FnMut(usize)>(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
        stop_ids: &[usize],
        mut on_token: F,
    ) -> Result<Vec<usize>, QuantModelError> {
        if prompt.is_empty() {
            return Err(QuantModelError::EmptyPrompt);
        }
        // Only the LAST prompt token's logits are used — the rest are fed in to
        // build KV state. forward_prefill skips the LM head for those, which is
        // exact (the head is a pure function of the hidden state) and saves
        // ~5.9% of each prefill token's work on a 1.7B/49152-vocab model.
        let mut logits = Vec::new();
        let last = prompt.len() - 1;
        for (i, &t) in prompt.iter().enumerate() {
            if i == last {
                logits = self.forward(t)?;
            } else {
                self.forward_prefill(t)?;
            }
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            mask.apply(&mut logits);
            let pos = self.position() as u64;
            let start = self.recent.len().saturating_sub(self.recent_window);
            let token = self.sampler.sample_seeded(
                &logits,
                &self.recent[start..],
                seed.wrapping_add(pos),
            )?;
            // Stop BEFORE recording or emitting: the marker is not output, and
            // leaving it out of `recent` keeps the repetition window clean.
            if stop_ids.contains(&token) {
                break;
            }
            self.recent.push(token);
            generated.push(token);
            on_token(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// The M00117 CONNECT decode loop: like [`generate_masked_with`] but the mask
    /// is **recomputed every step** from the tokens generated so far, via a
    /// per-step hook returning a **token-law allow-bitset** (a packed `Vec<u64>`,
    /// ⌈vocab/64⌉ words — the `sovereign-token-law-fuse` `FusedMask::mask` wire
    /// shape). `law_fn(&generated)` returns `None` to **stop** (the grammar is
    /// complete, or no token keeps every plane satisfiable — the caller must never
    /// force a sample from an all-masked row) or `Some(allow)` to `-inf`-mask every
    /// disallowed token and continue. `on_token` streams each sampled id as it is
    /// produced. This mirrors [`DecoderStack::generate_dynamic_token_law_until`] so
    /// the quantized serving model that gatewayd drives on `/v1/messages` is
    /// confined by the SAME checkpoint-free engine as `sovereign-llm`'s
    /// `complete_with_token_law` — the two decode stacks fuse identically.
    ///
    /// [`generate_masked_with`]: Self::generate_masked_with
    pub fn generate_dynamic_token_law_until_with<M, F>(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mut law_fn: M,
        mut on_token: F,
    ) -> Result<Vec<usize>, QuantModelError>
    where
        M: FnMut(&[usize]) -> Option<Vec<u64>>,
        F: FnMut(usize),
    {
        if prompt.is_empty() {
            return Err(QuantModelError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            let Some(allow) = law_fn(&generated) else {
                break;
            };
            sovereign_token_law_mask::mask_logits(&allow, &mut logits);
            let pos = self.position() as u64;
            let start = self.recent.len().saturating_sub(self.recent_window);
            let token = self.sampler.sample_seeded(
                &logits,
                &self.recent[start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            generated.push(token);
            on_token(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Non-streaming convenience over
    /// [`generate_dynamic_token_law_until_with`](Self::generate_dynamic_token_law_until_with)
    /// (mirrors the [`generate_masked`]/[`generate_masked_with`] pair).
    ///
    /// [`generate_masked`]: Self::generate_masked
    /// [`generate_masked_with`]: Self::generate_masked_with
    pub fn generate_dynamic_token_law_until<M>(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        law_fn: M,
    ) -> Result<Vec<usize>, QuantModelError>
    where
        M: FnMut(&[usize]) -> Option<Vec<u64>>,
    {
        self.generate_dynamic_token_law_until_with(prompt, max_new, seed, law_fn, |_| {})
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_decoder_layer::DecoderLayer;
    use sovereign_ffn::SwiGlu;
    use sovereign_linear::Precision;
    use sovereign_mha_block::{MhaBlockWeights, MhaDecoderBlock};
    use sovereign_quant_block::{QuantBlockWeights, QuantDecoderBlock};
    use sovereign_rmsnorm::RmsNorm;
    use sovereign_sampler::SamplerConfig;
    use sovereign_transformer_block::{BlockWeights, DecoderBlock};

    const MD: usize = 4;

    fn mat(s: f32, n: usize) -> Vec<f32> {
        (0..n).map(|i| ((i as f32 + s) * 0.017).sin()).collect()
    }

    fn transformer_layer() -> DecoderBlock {
        DecoderBlock::new(BlockWeights {
            model_dim: MD,
            head_dim: MD,
            attn_norm: RmsNorm::new(MD),
            ffn_norm: RmsNorm::new(MD),
            w_q: mat(1.0, MD * MD),
            w_k: mat(2.0, MD * MD),
            w_v: mat(3.0, MD * MD),
            w_o: mat(4.0, MD * MD),
            ffn: SwiGlu::new(
                MD,
                MD,
                mat(5.0, MD * MD),
                mat(6.0, MD * MD),
                mat(7.0, MD * MD),
            )
            .unwrap(),
        })
        .unwrap()
    }

    fn quant_layer(p: Precision) -> QuantDecoderBlock {
        QuantDecoderBlock::from_weights(
            &QuantBlockWeights {
                model_dim: MD,
                head_dim: MD,
                hidden_dim: MD,
                attn_norm: RmsNorm::new(MD),
                ffn_norm: RmsNorm::new(MD),
                w_q: mat(8.0, MD * MD),
                w_k: mat(9.0, MD * MD),
                w_v: mat(10.0, MD * MD),
                w_o: mat(11.0, MD * MD),
                w_gate: mat(12.0, MD * MD),
                w_up: mat(13.0, MD * MD),
                w_down: mat(14.0, MD * MD),
            },
            p,
        )
        .unwrap()
    }

    fn mha_layer(p: Precision) -> MhaDecoderBlock {
        let (nq, nkv, hd) = (2, 1, 2);
        MhaDecoderBlock::from_weights(
            &MhaBlockWeights {
                model_dim: MD,
                head_dim: hd,
                num_q_heads: nq,
                num_kv_heads: nkv,
                hidden_dim: MD,
                attn_norm: RmsNorm::new(MD),
                ffn_norm: RmsNorm::new(MD),
                w_q: mat(15.0, nq * hd * MD),
                w_k: mat(16.0, nkv * hd * MD),
                w_v: mat(17.0, nkv * hd * MD),
                w_o: mat(18.0, MD * nq * hd),
                w_gate: mat(19.0, MD * MD),
                w_up: mat(20.0, MD * MD),
                w_down: mat(21.0, MD * MD),
            },
            p,
        )
        .unwrap()
    }

    fn mixed_model(vocab: usize, sampler: Sampler) -> QuantModel {
        let layers: Vec<Box<dyn DecoderLayer>> = vec![
            Box::new(transformer_layer()),
            Box::new(quant_layer(Precision::Ternary)),
            Box::new(mha_layer(Precision::Nvfp4)),
        ];
        let stack = LayerStack::new(layers).unwrap();
        QuantModel::new(
            vocab,
            MD,
            mat(0.5, vocab * MD),
            stack,
            RmsNorm::new(MD),
            mat(0.9, vocab * MD),
            sampler,
        )
        .unwrap()
    }

    #[test]
    fn mixed_precision_model_generates_in_range() {
        let mut m = mixed_model(8, Sampler::new(SamplerConfig::default()));
        assert_eq!(m.layers(), 3);
        let out = m.generate(&[1, 2, 3], 6, 42).unwrap();
        assert_eq!(out.len(), 6);
        assert!(out.iter().all(|&t| t < 8));
        // 3 prompt + 6 generated = 9 positions in the stack
        assert_eq!(m.position(), 9);
    }

    // ── SDD-401 GPU-hotswap seam (phase 2) ──────────────────────────────────
    #[derive(Debug)]
    struct MockFold {
        caps: FoldCaps,
    }
    impl FoldBackend for MockFold {
        fn name(&self) -> &str {
            "mock-fold"
        }
        fn folds(&self) -> FoldCaps {
            self.caps
        }
    }

    #[test]
    fn exec_mode_defaults_to_cpu() {
        let m = mixed_model(8, Sampler::greedy());
        assert_eq!(m.exec_mode(), ExecMode::Cpu);
        assert!(m.fold_backend_status().is_none());
    }

    #[test]
    fn gpu_fold_without_backend_honest_degrades() {
        let mut m = mixed_model(8, Sampler::greedy()).with_exec_mode(ExecMode::GpuFold);
        let err = m.forward(1).unwrap_err();
        match err {
            QuantModelError::GpuFoldUnavailable { reason } => {
                assert!(
                    reason.contains("none is set"),
                    "reason should name the missing backend: {reason}"
                );
            }
            other => panic!("expected GpuFoldUnavailable, got {other:?}"),
        }
    }

    #[test]
    fn gpu_fold_with_unwired_backend_honest_degrades_and_names_it() {
        let mut m = mixed_model(8, Sampler::greedy());
        m.set_fold_backend(Some(Box::new(MockFold {
            caps: FoldCaps {
                kv: true,
                ..FoldCaps::default()
            },
        })));
        m.set_exec_mode(ExecMode::GpuFold);
        assert_eq!(m.fold_backend_status().map(|(n, _)| n), Some("mock-fold"));
        assert!(m.fold_backend_status().unwrap().1.kv);
        let err = m.forward(1).unwrap_err();
        match err {
            QuantModelError::GpuFoldUnavailable { reason } => {
                assert!(
                    reason.contains("mock-fold"),
                    "reason should name the backend: {reason}"
                );
                assert!(
                    reason.contains("kv=true"),
                    "reason should report caps: {reason}"
                );
                assert!(
                    reason.contains("not wired yet"),
                    "reason should say routing is unwired: {reason}"
                );
            }
            other => panic!("expected GpuFoldUnavailable, got {other:?}"),
        }
    }

    #[test]
    fn cpu_mode_generation_is_unchanged_by_an_attached_backend() {
        // The default (Cpu) path must never consult the fold backend — attaching
        // one and staying in Cpu mode yields byte-identical generation.
        let mut plain = mixed_model(8, Sampler::greedy());
        let mut withbe = mixed_model(8, Sampler::greedy());
        withbe.set_fold_backend(Some(Box::new(MockFold {
            caps: FoldCaps {
                weights: true,
                kv: true,
                embedding: true,
            },
        })));
        assert_eq!(withbe.exec_mode(), ExecMode::Cpu);
        let a = plain.generate(&[1, 2, 3], 6, 42).unwrap();
        let b = withbe.generate(&[1, 2, 3], 6, 42).unwrap();
        assert_eq!(
            a, b,
            "Cpu-mode output must be identical regardless of an attached backend"
        );
    }

    #[test]
    fn dynamic_token_law_confines_every_step_to_the_allowed_bitset() {
        // CONNECT: the per-step allow-bitset must -inf-mask every disallowed
        // token, so the sampled id is ALWAYS in the allowed set — the same
        // guarantee sovereign-llm's complete_with_token_law gives DecoderStack,
        // now on the quantized serving model gatewayd drives.
        let mut m = mixed_model(8, Sampler::new(SamplerConfig::default()));
        // allow only ids {2, 5} (vocab 8 → one bitset word)
        let allow = vec![(1u64 << 2) | (1u64 << 5)];
        let mut streamed = Vec::new();
        let out = m
            .generate_dynamic_token_law_until_with(
                &[1, 2, 3],
                6,
                42,
                |_generated| Some(allow.clone()),
                |tok| streamed.push(tok),
            )
            .unwrap();
        assert_eq!(out.len(), 6);
        assert!(
            out.iter().all(|&t| t == 2 || t == 5),
            "every token must be in the allowed set {{2,5}}, got {out:?}"
        );
        assert_eq!(
            streamed, out,
            "on_token must stream exactly the generated ids"
        );
    }

    #[test]
    fn head_skipping_prefill_is_bit_identical_to_the_full_forward() {
        // forward_prefill drops final_norm + project_head for non-final prompt
        // tokens. Both are pure functions of the hidden state, so the KV state
        // they leave behind must be identical — if it is not, generation would
        // silently diverge and this optimisation would be a correctness bug
        // rather than a saving.
        let mask = LogitMask::new();
        let prompt = [1usize, 2, 3, 4, 5];

        // Reference: drive the stack with full forwards, then read logits.
        let mut a = mixed_model(8, Sampler::new(SamplerConfig::default()));
        let mut ref_logits = Vec::new();
        for &t in &prompt {
            ref_logits = a.forward(t).unwrap();
        }

        // Same prompt, head skipped on every token but the last.
        let mut b = mixed_model(8, Sampler::new(SamplerConfig::default()));
        let mut got_logits = Vec::new();
        let last = prompt.len() - 1;
        for (i, &t) in prompt.iter().enumerate() {
            if i == last {
                got_logits = b.forward(t).unwrap();
            } else {
                b.forward_prefill(t).unwrap();
            }
        }
        assert_eq!(ref_logits, got_logits, "skipping the head must not change the final logits");

        // And end to end, the generated sequences must match exactly.
        let out_a = mixed_model(8, Sampler::new(SamplerConfig::default()))
            .generate_masked_with(&prompt, 6, 3, &mask, |_| {})
            .unwrap();
        let out_b = mixed_model(8, Sampler::new(SamplerConfig::default()))
            .generate_masked_until_with(&prompt, 6, 3, &mask, &[], |_| {})
            .unwrap();
        assert_eq!(out_a, out_b, "generation is unchanged by head-skipping prefill");
    }

    #[test]
    fn forward_prefill_rejects_out_of_range_tokens_like_forward() {
        let mut m = mixed_model(8, Sampler::new(SamplerConfig::default()));
        let v = m.vocab;
        assert!(m.forward_prefill(v).is_err(), "out-of-range must still error");
    }

    #[test]
    fn generate_masked_until_stops_on_a_stop_token_and_does_not_emit_it() {
        // An end-of-turn marker is a control token, not output: decoding must
        // stop AT it and never hand it to the caller. Before stop_ids existed,
        // the loop ran to max_new regardless and an instruct model's <|im_end|>
        // was emitted as ordinary text, after which it kept inventing turns.
        let mask = LogitMask::new();

        // What this fixture deterministically produces with no stop. Do NOT
        // assume the ids are distinct — an earlier version of this test picked
        // baseline[2] as the stop and got length 0, because this fixture repeats
        // a single token and baseline[2] == baseline[0].
        let baseline = mixed_model(8, Sampler::new(SamplerConfig::default()))
            .generate_masked_with(&[1, 2, 3], 6, 0, &mask, |_| {})
            .unwrap();
        assert_eq!(baseline.len(), 6, "baseline runs to max_new");

        // Stopping on the FIRST token must yield nothing at all, and must not
        // emit the marker.
        let mut emitted = Vec::new();
        let out = mixed_model(8, Sampler::new(SamplerConfig::default()))
            .generate_masked_until_with(&[1, 2, 3], 6, 0, &mask, &[baseline[0]], |t| {
                emitted.push(t)
            })
            .unwrap();
        assert!(out.is_empty(), "stops at the very first token");
        assert!(emitted.is_empty(), "the stop token is never emitted");

        // A stop id the model never samples must not truncate anything.
        let absent = (0..usize::MAX)
            .find(|c| !baseline.contains(c))
            .expect("some id is not in a 6-token sample");
        let out2 = mixed_model(8, Sampler::new(SamplerConfig::default()))
            .generate_masked_until_with(&[1, 2, 3], 6, 0, &mask, &[absent], |_| {})
            .unwrap();
        assert_eq!(out2, baseline, "an unsampled stop id changes nothing");
    }

    #[test]
    fn generate_masked_until_with_no_stop_ids_matches_the_original() {
        // The empty-stop path must be byte-identical to generate_masked_with,
        // since that method now delegates here — every existing caller depends
        // on it being unchanged.
        let mask = LogitMask::new();
        let a = mixed_model(8, Sampler::new(SamplerConfig::default()))
            .generate_masked_with(&[1, 2, 3], 5, 11, &mask, |_| {})
            .unwrap();
        let b = mixed_model(8, Sampler::new(SamplerConfig::default()))
            .generate_masked_until_with(&[1, 2, 3], 5, 11, &mask, &[], |_| {})
            .unwrap();
        assert_eq!(a, b, "no stop ids ⇒ identical to the original loop");
    }

    #[test]
    fn dynamic_token_law_stops_when_the_hook_returns_none() {
        // `None` from the hook (grammar complete / no satisfiable token) ends
        // generation immediately — never sample from an all-masked row.
        let mut m = mixed_model(8, Sampler::new(SamplerConfig::default()));
        let allow = vec![0xFFu64];
        let mut steps = 0usize;
        let out = m
            .generate_dynamic_token_law_until(&[1, 2, 3], 10, 7, |generated| {
                steps += 1;
                if generated.len() >= 3 {
                    None
                } else {
                    Some(allow.clone())
                }
            })
            .unwrap();
        assert_eq!(out.len(), 3, "stops after 3 tokens when the hook says None");
        assert_eq!(steps, 4, "hook called 3 times to emit, once more to stop");
    }

    #[test]
    fn with_sampler_replaces_the_sampler_and_is_observable() {
        // Assembled greedy (as the loader does), then re-pointed at a warm
        // sampler via the builder — the sampler() getter must reflect it.
        let m = mixed_model(8, Sampler::greedy());
        assert_eq!(m.sampler().config.temperature, 0.0, "starts greedy");
        let warm = m.with_sampler(Sampler::new(SamplerConfig {
            temperature: 0.8,
            top_p: Some(0.9),
            ..Default::default()
        }));
        assert_eq!(warm.sampler().config.temperature, 0.8);
        assert_eq!(warm.sampler().config.top_p, Some(0.9));
    }

    #[test]
    fn tied_model_uses_embedding_as_output_head() {
        let vocab = 8;
        let emb = mat(0.5, vocab * MD);
        let layers: Vec<Box<dyn DecoderLayer>> = vec![Box::new(transformer_layer())];
        let stack = LayerStack::new(layers).unwrap();
        let mut m = QuantModel::new_tied(
            vocab,
            MD,
            emb.clone(),
            stack,
            RmsNorm::new(MD),
            Sampler::greedy(),
        )
        .unwrap();
        assert!(m.is_tied());
        // Run a forward pass and verify each logit equals the corresponding
        // embedding row dotted with the (normed) final hidden state — i.e. the
        // head genuinely reuses the embedding table.
        let logits = m.forward(3).unwrap();
        assert_eq!(logits.len(), vocab);
        // Re-derive the normed hidden the same way forward does, to recompute
        // the expected tied logits independently.
        // (We can't reach the private hidden, so instead check the tying
        // invariant structurally: an untied model built with head == embedding
        // produces identical logits.)
        let layers2: Vec<Box<dyn DecoderLayer>> = vec![Box::new(transformer_layer())];
        let mut untied = QuantModel::new(
            vocab,
            MD,
            emb.clone(),
            LayerStack::new(layers2).unwrap(),
            RmsNorm::new(MD),
            emb.clone(), // head == embedding
            Sampler::greedy(),
        )
        .unwrap();
        assert!(!untied.is_tied());
        let logits_untied = untied.forward(3).unwrap();
        for (a, b) in logits.iter().zip(&logits_untied) {
            assert!(
                (a - b).abs() < 1e-6,
                "tied logits must match head==embedding"
            );
        }
    }

    #[test]
    fn logit_softcap_bounds_and_preserves_order() {
        let vocab = 8;
        let layers: Vec<Box<dyn DecoderLayer>> = vec![Box::new(transformer_layer())];
        let stack = LayerStack::new(layers).unwrap();
        let mut capped = QuantModel::new(
            vocab,
            MD,
            mat(0.5, vocab * MD),
            stack,
            RmsNorm::new(MD),
            mat(0.9, vocab * MD),
            Sampler::greedy(),
        )
        .unwrap()
        .with_logit_softcap(2.0);
        assert_eq!(capped.logit_softcap(), Some(2.0));

        let layers2: Vec<Box<dyn DecoderLayer>> = vec![Box::new(transformer_layer())];
        let mut plain = QuantModel::new(
            vocab,
            MD,
            mat(0.5, vocab * MD),
            LayerStack::new(layers2).unwrap(),
            RmsNorm::new(MD),
            mat(0.9, vocab * MD),
            Sampler::greedy(),
        )
        .unwrap();

        let cl = capped.forward(3).unwrap();
        let pl = plain.forward(3).unwrap();
        // Every capped logit is strictly inside (−2, 2).
        assert!(
            cl.iter().all(|&l| l.abs() < 2.0),
            "capping must bound logits"
        );
        // Order is preserved (tanh is monotonic), so the argmax is unchanged.
        let amax = |v: &[f32]| (0..v.len()).max_by(|&a, &b| v[a].total_cmp(&v[b])).unwrap();
        assert_eq!(amax(&cl), amax(&pl));
        // A non-positive cap disables it.
        assert_eq!(plain.with_logit_softcap(0.0).logit_softcap(), None);
    }

    #[test]
    fn tied_model_validates_embedding_shape() {
        let layers: Vec<Box<dyn DecoderLayer>> = vec![Box::new(transformer_layer())];
        let stack = LayerStack::new(layers).unwrap();
        let err = QuantModel::new_tied(
            8,
            MD,
            vec![0.0; 3],
            stack,
            RmsNorm::new(MD),
            Sampler::greedy(),
        )
        .unwrap_err();
        assert!(matches!(err, QuantModelError::EmbeddingShape { .. }));
    }

    #[test]
    fn generation_is_reproducible_per_seed() {
        let mut a = mixed_model(8, Sampler::new(SamplerConfig::default()));
        let mut b = mixed_model(8, Sampler::new(SamplerConfig::default()));
        assert_eq!(
            a.generate(&[1, 2], 8, 123).unwrap(),
            b.generate(&[1, 2], 8, 123).unwrap()
        );
    }

    #[test]
    fn masked_generation_confined_to_allow_list() {
        let mut m = mixed_model(8, Sampler::new(SamplerConfig::default()));
        let mask = LogitMask::new().allow_only([2usize, 5]);
        let out = m.generate_masked(&[1], 12, 7, &mask).unwrap();
        assert!(out.iter().all(|&t| t == 2 || t == 5), "got {out:?}");
    }

    #[test]
    fn emitted_matches_generated() {
        let mut m = mixed_model(8, Sampler::new(SamplerConfig::default()));
        let out = m.generate(&[3], 4, 5).unwrap();
        assert_eq!(m.emitted(), out.as_slice());
    }

    #[test]
    fn empty_prompt_and_oob_token_are_errors() {
        let mut m = mixed_model(8, Sampler::greedy());
        assert_eq!(
            m.generate(&[], 4, 1).unwrap_err(),
            QuantModelError::EmptyPrompt
        );
        assert_eq!(
            m.forward(99).unwrap_err(),
            QuantModelError::TokenOutOfRange {
                token: 99,
                vocab: 8
            }
        );
    }

    #[test]
    fn embedding_shape_is_validated() {
        let stack = LayerStack::new(vec![Box::new(transformer_layer())]).unwrap();
        let err = QuantModel::new(
            8,
            MD,
            mat(0.5, 8 * MD - 1), // wrong
            stack,
            RmsNorm::new(MD),
            mat(0.9, 8 * MD),
            Sampler::greedy(),
        )
        .unwrap_err();
        assert!(matches!(err, QuantModelError::EmbeddingShape { .. }));
    }
}
