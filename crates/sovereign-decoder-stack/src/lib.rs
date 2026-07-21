//! `sovereign-decoder-stack` — a complete decoder-only transformer model.
//!
//! This is the top of the decode-engine arc: the per-layer
//! [`sovereign-transformer-block`] stacked into a runnable model with an
//! input embedding, a final norm, an output head, and a sampler. One forward
//! pass is exactly what a decoder-only LLM runs per position:
//!
//! ```text
//!   hidden = embedding[token]
//!   for block in blocks:  hidden = block.step(hidden)   (each keeps its KV cache)
//!   hidden = final_norm(hidden)
//!   logits = head · hidden
//!   next   = sampler(logits, recent, seed)
//! ```
//!
//! [`generate`](DecoderStack::generate) ingests a prompt (advancing every
//! block's cache one position per prompt token) and then decodes
//! autoregressively, feeding each sampled token back in. Because every stage
//! is deterministic under a seed, a whole generation is reproducible and
//! replayable — the property the sovereign runtime's ledger relies on.
//!
//! [`sovereign-transformer-block`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-transformer-block
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_logit_mask::LogitMask;
use sovereign_rmsnorm::RmsNorm;
use sovereign_sampler::{Mirostat, Sampler, SamplerError};
use sovereign_transformer_block::{BlockError, BlockWeights, DecoderBlock};
use thiserror::Error;

/// Schema version of the decoder-stack surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong building or running the model.
#[derive(Debug, Error, PartialEq)]
pub enum StackError {
    /// No decoder blocks were supplied.
    #[error("a decoder stack needs at least one block")]
    NoBlocks,
    /// A block's model dimension disagreed with the stack's.
    #[error("block {index} has model_dim {got}, expected {expected}")]
    BlockDim {
        /// Which block.
        index: usize,
        /// Stack model dimension.
        expected: usize,
        /// Block model dimension.
        got: usize,
    },
    /// The embedding table was mis-shaped.
    #[error("embedding must be vocab*model_dim = {expected} elements, got {got}")]
    EmbeddingShape {
        /// Expected element count.
        expected: usize,
        /// Observed element count.
        got: usize,
    },
    /// The output head was mis-shaped.
    #[error("output head must be vocab*model_dim = {expected} elements, got {got}")]
    HeadShape {
        /// Expected element count.
        expected: usize,
        /// Observed element count.
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
    /// An error from a decoder block.
    #[error("block: {0}")]
    Block(#[from] BlockError),
    /// An error from the sampler stage.
    #[error("sampler: {0}")]
    Sampler(#[from] SamplerError),
}

/// The immutable configuration + weights of a decoder-only model.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StackConfig {
    /// Vocabulary size.
    pub vocab: usize,
    /// Model (residual-stream) dimension.
    pub model_dim: usize,
    /// Token embedding table, row-major `vocab × model_dim`.
    pub embedding: Vec<f32>,
    /// Per-layer block weights.
    pub blocks: Vec<BlockWeights>,
    /// Final pre-head RMSNorm.
    pub final_norm: RmsNorm,
    /// Output (unembedding) head, row-major `vocab × model_dim`.
    pub head: Vec<f32>,
    /// Sampler controls.
    pub sampler: Sampler,
    /// How many recent tokens feed the repetition penalty.
    pub recent_window: usize,
}

/// Composable decode controls for [`DecoderStack::generate_with`]. Defaults to
/// plain generation (no mask, no n-gram blocking, no stop tokens); set only the
/// fields you need.
#[derive(Debug, Clone, Default)]
pub struct GenOptions {
    /// Maximum tokens to generate.
    pub max_new: usize,
    /// A base logit mask applied every step (constrained / allow-list / bias).
    pub mask: LogitMask,
    /// If set, block any token completing an already-seen `n`-gram each step.
    pub no_repeat_ngram: Option<usize>,
    /// Stop generation the moment one of these tokens is produced (it is
    /// included in the output).
    pub stop_tokens: Vec<usize>,
    /// Minimum tokens to generate before a `stop_tokens` token may be emitted:
    /// the stop tokens are masked out for the first `min_new` steps, forcing a
    /// minimum response length (a common serving constraint). `0` = no minimum.
    pub min_new: usize,
    /// The M002 token-law allow-mask (SDD-500): a per-vocabulary bitset packed
    /// 64 tokens per `u64` word (bit `t` set = token `t` allowed), the combined
    /// output of `sovereign_simd::cheats::token_law_combine` over the active
    /// laws. When `Some`, every disallowed token is set to `-inf` each step, so
    /// the model **cannot** emit outside the allow set — the first real
    /// per-token call site of the M002 bit-machine. Correctness (not
    /// acceleration): it applies whenever present, regardless of `avx-mode`.
    /// `None` = unconstrained (identity).
    pub token_law: Option<Vec<u64>>,
}

impl GenOptions {
    /// Options that just generate `max_new` tokens with no extra controls.
    pub fn new(max_new: usize) -> Self {
        Self {
            max_new,
            ..Self::default()
        }
    }

    /// Set the base logit mask.
    pub fn with_mask(mut self, mask: LogitMask) -> Self {
        self.mask = mask;
        self
    }

    /// Enable dynamic no-repeat-ngram blocking of size `n`.
    pub fn with_no_repeat_ngram(mut self, n: usize) -> Self {
        self.no_repeat_ngram = Some(n);
        self
    }

    /// Set the stop tokens for early termination.
    pub fn with_stop_tokens(mut self, stops: impl IntoIterator<Item = usize>) -> Self {
        self.stop_tokens = stops.into_iter().collect();
        self
    }

    /// Force at least `min_new` tokens before any stop token may be emitted.
    pub fn with_min_new(mut self, min_new: usize) -> Self {
        self.min_new = min_new;
        self
    }

    /// Constrain generation to a M002 token-law allow-mask (SDD-500): a
    /// per-vocabulary bitset (bit `t` = token `t` allowed), typically the output
    /// of `sovereign_simd::cheats::token_law_combine` over the active laws.
    /// Disallowed tokens are `-inf`-masked every step; the model cannot emit
    /// outside the set.
    pub fn with_token_law(mut self, allow: Vec<u64>) -> Self {
        self.token_law = Some(allow);
        self
    }
}

/// A runnable decoder-only model with each layer's autoregressive KV cache.
#[derive(Debug, Clone)]
pub struct DecoderStack {
    config: StackConfig,
    blocks: Vec<DecoderBlock>,
    recent: Vec<usize>,
}

impl DecoderStack {
    /// Build a model from its config, validating all shapes.
    pub fn new(config: StackConfig) -> Result<Self, StackError> {
        if config.blocks.is_empty() {
            return Err(StackError::NoBlocks);
        }
        let want_embed = config.vocab * config.model_dim;
        if config.embedding.len() != want_embed {
            return Err(StackError::EmbeddingShape {
                expected: want_embed,
                got: config.embedding.len(),
            });
        }
        if config.head.len() != want_embed {
            return Err(StackError::HeadShape {
                expected: want_embed,
                got: config.head.len(),
            });
        }
        let mut blocks = Vec::with_capacity(config.blocks.len());
        for (index, bw) in config.blocks.iter().enumerate() {
            if bw.model_dim != config.model_dim {
                return Err(StackError::BlockDim {
                    index,
                    expected: config.model_dim,
                    got: bw.model_dim,
                });
            }
            blocks.push(DecoderBlock::new(bw.clone())?);
        }
        Ok(Self {
            config,
            blocks,
            recent: Vec::new(),
        })
    }

    /// Number of layers.
    pub fn layers(&self) -> usize {
        self.blocks.len()
    }

    /// Vocabulary size.
    pub fn vocab(&self) -> usize {
        self.config.vocab
    }

    /// Current decode position (KV cache depth of every layer).
    pub fn position(&self) -> usize {
        self.blocks.first().map(|b| b.len()).unwrap_or(0)
    }

    /// The tokens sampled so far.
    pub fn emitted(&self) -> &[usize] {
        &self.recent
    }

    fn embed(&self, token: usize) -> Vec<f32> {
        let d = self.config.model_dim;
        self.config.embedding[token * d..(token + 1) * d].to_vec()
    }

    fn project_head(&self, hidden: &[f32]) -> Vec<f32> {
        let d = self.config.model_dim;
        let mut logits = vec![0.0f32; self.config.vocab];
        for (v, logit) in logits.iter_mut().enumerate() {
            let row = &self.config.head[v * d..(v + 1) * d];
            *logit = row.iter().zip(hidden).map(|(w, h)| w * h).sum();
        }
        logits
    }

    /// Run one forward pass for `token`, advancing every block's cache, and
    /// return the logit row for the next token.
    pub fn forward(&mut self, token: usize) -> Result<Vec<f32>, StackError> {
        if token >= self.config.vocab {
            return Err(StackError::TokenOutOfRange {
                token,
                vocab: self.config.vocab,
            });
        }
        let mut hidden = self.embed(token);
        for block in &mut self.blocks {
            hidden = block.step(&hidden)?;
        }
        let normed = self
            .config
            .final_norm
            .normalize(&hidden)
            .map_err(BlockError::from)?;
        Ok(self.project_head(&normed))
    }

    /// Ingest `prefix` into the KV cache **without generating**, advancing every
    /// layer's cache by `prefix.len()` positions. This is the prefix-KV-reuse
    /// primitive: prime a shared prefix (e.g. a system prompt) once, then
    /// [`clone`](Clone::clone) this primed stack per request and generate only
    /// the per-request suffix — amortizing the prefix's forward passes across
    /// many requests. Reuse is **transparent**: priming `prefix` then generating
    /// `suffix` yields the same tokens as generating `prefix ++ suffix` in one
    /// call (pinned as a test). No-op for an empty prefix.
    pub fn prime(&mut self, prefix: &[usize]) -> Result<(), StackError> {
        for &t in prefix {
            self.forward(t)?;
        }
        Ok(())
    }

    /// Ingest a prompt and autoregressively generate up to `max_new` tokens.
    /// Returns the generated tokens (excluding the prompt). Reproducible for a
    /// given `seed`.
    pub fn generate(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
    ) -> Result<Vec<usize>, StackError> {
        self.generate_masked(prompt, max_new, seed, &LogitMask::new())
    }

    /// Like [`generate`](Self::generate) but applies `mask` to every step's
    /// logits before sampling — constrained decoding (allow-list / bans /
    /// bias). With an empty mask this is identical to `generate`.
    pub fn generate_masked(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
    ) -> Result<Vec<usize>, StackError> {
        let mut generated = Vec::with_capacity(max_new);
        self.generate_masked_with(prompt, max_new, seed, mask, |t| generated.push(t))?;
        Ok(generated)
    }

    /// Generate with **dynamic no-repeat-ngram blocking**: at every step the
    /// blocklist is rebuilt from the full generated-so-far history (prompt +
    /// emitted), so the model can never complete an `n`-gram it has already
    /// produced — preventing verbatim loops that a static mask can't catch as
    /// the sequence grows. Reproducible per `seed`.
    pub fn generate_no_repeat_ngram(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        n: usize,
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut history: Vec<usize> = prompt.to_vec();
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            // Rebuild the blocklist from the live history and apply it.
            let mut masked = logits.clone();
            LogitMask::new()
                .no_repeat_ngram(&history, n)
                .apply(&mut masked);
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &masked,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            history.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Generate with a stateful [`Mirostat`] controller instead of the config's
    /// static truncation: each step shapes the logits through the sampler's
    /// distribution (temperature / penalties), then lets `mirostat` pick the
    /// token and update its running `μ` so output perplexity stays near the
    /// controller's target. Reproducible per `seed`; `mirostat`'s state advances
    /// across the call (and persists for the caller to inspect).
    pub fn generate_mirostat(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mirostat: &mut Mirostat,
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let probs = self
                .config
                .sampler
                .distribution(&logits, &self.recent[recent_start..])?;
            // One deterministic uniform from seed+pos (splitmix64), so the run
            // is reproducible like the static path.
            let u = splitmix_uniform(seed.wrapping_add(pos)) as f32;
            let token = mirostat
                .sample(&probs, u)
                .ok_or(SamplerError::AllFiltered)?;
            self.recent.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Unified, serving-grade generation that **composes** the decode controls
    /// that the single-purpose methods can only apply one at a time: a base
    /// [`LogitMask`] (constrained decoding), dynamic no-repeat-ngram blocking,
    /// early stop on a stop token, and a per-token streaming callback — all in
    /// one loop. Reproducible per `seed`. See [`GenOptions`].
    pub fn generate_with<F: FnMut(usize)>(
        &mut self,
        prompt: &[usize],
        seed: u64,
        opts: &GenOptions,
        mut on_token: F,
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut history: Vec<usize> = prompt.to_vec();
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(opts.max_new);
        for _ in 0..opts.max_new {
            let mut l = logits.clone();
            opts.mask.apply(&mut l);
            // M002 token-law bitset (SDD-500) — the first real per-token call
            // site of the bit-machine: disallowed tokens go to -inf so the
            // model cannot emit outside the allow set. Correctness, not
            // acceleration: applied whenever present, regardless of avx-mode.
            if let Some(ref allow) = opts.token_law {
                sovereign_token_law_mask::mask_logits(allow, &mut l);
            }
            if let Some(n) = opts.no_repeat_ngram {
                LogitMask::new().no_repeat_ngram(&history, n).apply(&mut l);
            }
            // Min-length: forbid stop tokens until `min_new` tokens are out.
            if generated.len() < opts.min_new && !opts.stop_tokens.is_empty() {
                LogitMask::new()
                    .ban_all(opts.stop_tokens.iter().copied())
                    .apply(&mut l);
            }
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &l,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            history.push(token);
            generated.push(token);
            on_token(token);
            if opts.stop_tokens.contains(&token) {
                break;
            }
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Generate up to `max_new` tokens, stopping early the moment a token in
    /// `stop_tokens` is produced (the stop token **is** included in the result).
    /// This is the EOS / stop-sequence behaviour a real runtime needs — most
    /// completions end well before the length cap. With an empty `stop_tokens`
    /// this is identical to [`generate`](Self::generate). Reproducible per seed.
    pub fn generate_until(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        stop_tokens: &[usize],
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            generated.push(token);
            if stop_tokens.contains(&token) {
                break;
            }
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Streaming generation: identical to [`generate_masked`](Self::generate_masked)
    /// but invokes `on_token` with each sampled token id the instant it is
    /// produced (before the next forward pass), so a server can emit tokens as
    /// they arrive instead of waiting for the whole completion. The collected
    /// sequence is exactly what `generate_masked` would return.
    pub fn generate_masked_with<F: FnMut(usize)>(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
        mut on_token: F,
    ) -> Result<(), StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        // Ingest the prompt; the logits after the last prompt token predict
        // the first generated token.
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }

        for _ in 0..max_new {
            mask.apply(&mut logits);
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            on_token(token);
            logits = self.forward(token)?;
        }
        Ok(())
    }

    /// Generate up to `max_new` tokens, recomputing the logit mask **each step**
    /// from the tokens generated so far. `mask_fn(&generated)` returns the
    /// [`LogitMask`] to apply before sampling the next token — the hook that lets
    /// a stateful constraint (a regex/grammar automaton) forbid every token that
    /// would leave the constraint unsatisfiable, so the model can only ever emit
    /// strings the constraint accepts. Returns the generated token ids.
    /// Reproducible per `seed`.
    pub fn generate_dynamic_mask<M>(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mut mask_fn: M,
    ) -> Result<Vec<usize>, StackError>
    where
        M: FnMut(&[usize]) -> LogitMask,
    {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            let mask = mask_fn(&generated);
            mask.apply(&mut logits);
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Generate up to `max_new` tokens applying **XTC** (Exclude Top Choices)
    /// to the logits each step before sampling: when several tokens clear the
    /// confidence threshold, the most-probable ones are dropped (with the
    /// configured per-step probability) so a lower-but-plausible token can win —
    /// more creative output without the word-salad of hot temperature, and a
    /// no-op when only one token is confident (it stays on track). The XTC roll
    /// uses a seed stream distinct from the sampler's, so both are reproducible
    /// per `seed`. Returns the generated ids.
    pub fn generate_xtc(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        xtc: &sovereign_xtc_sampler::XtcSampler,
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            let pos = self.position() as u64;
            // distinct seed stream for the XTC roll (offset from the sampler's).
            xtc.apply_seeded(
                &mut logits,
                seed.wrapping_add(pos).wrapping_add(0x5743_4358),
            );
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Generate up to `max_new` tokens applying **repetition / frequency /
    /// presence penalties** to the logits each step before sampling. The penalty
    /// history is the prompt plus everything generated so far: repetition scales
    /// down the logit of any already-seen token (CTRL-style), frequency subtracts
    /// proportionally to how often it appeared, and presence subtracts a flat
    /// amount for any prior appearance — the classic trio that discourages loops
    /// and over-used tokens. Identity `penalties` leave the logits untouched, so
    /// this reduces to the base sampler. Reproducible per `seed`.
    pub fn generate_penalized(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        penalties: &sovereign_repetition_penalty::Penalties,
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        // penalty history: the prompt plus everything generated in this call.
        let mut history: Vec<usize> = prompt.to_vec();
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            penalties.apply(&mut logits, &history);
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            generated.push(token);
            history.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Generate up to `max_new` tokens using **locally-typical sampling** at
    /// cumulative `mass`: each step keeps only the tokens whose surprisal is
    /// closest to the distribution's entropy (the "typical set") and masks the
    /// rest before sampling — suppressing both the bland high-probability tokens
    /// and the incoherent tail, which reads as more human than plain top-p. A
    /// `mass` of `1.0` keeps everything (reduces to the base sampler).
    /// Reproducible per `seed`.
    pub fn generate_typical(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mass: f64,
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            sovereign_typical_sampling::typical_mask_logits(&mut logits, mass);
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Generate up to `max_new` tokens driving each step's logits through a
    /// **[`LogitPipeline`](sovereign_logit_pipeline::LogitPipeline)** — an ordered
    /// list of logit processors (allow/ban masks, no-repeat-n-gram blocking, or
    /// any caller-supplied [`LogitProcessor`](sovereign_logit_pipeline::LogitProcessor))
    /// applied in one defined order over the prompt+generated history before
    /// sampling. This is the composable generalization of the single-control
    /// methods (`generate_masked`, `generate_no_repeat_ngram`): every control is
    /// one entry in the pipeline, so their order is explicit and they can't be
    /// forgotten. An empty pipeline is identical to [`generate`](Self::generate).
    /// Reproducible per `seed`.
    pub fn generate_piped(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        pipeline: &sovereign_logit_pipeline::LogitPipeline,
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut history: Vec<usize> = prompt.to_vec();
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            pipeline.apply(&history, &mut logits);
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            history.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Generate up to `max_new` tokens by the **Gumbel-max trick**
    /// (`sovereign-gumbel`): each step adds one i.i.d. Gumbel sample to every
    /// logit and takes the `argmax`, which is distributed *exactly* as
    /// `softmax(logits)` — a branch-free way to draw from the raw logits with no
    /// explicit normalization (equivalent to multinomial sampling at temperature
    /// 1). It bypasses the config sampler's truncation entirely; forbidden
    /// (`-inf`) logits stay forbidden. Reproducible per `seed` (one seeded Gumbel
    /// stream drives the whole call).
    pub fn generate_gumbel(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut gumbel = sovereign_gumbel::GumbelSampler::new(seed);
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            let logits_f64: Vec<f64> = logits.iter().map(|&l| l as f64).collect();
            // vocab is always non-empty, so `sample` yields a token.
            let token = gumbel.sample(&logits_f64).unwrap_or(0);
            self.recent.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Generate up to `max_new` tokens applying **DRY** (Don't Repeat Yourself)
    /// to the logits each step before sampling: each candidate is penalized by how
    /// long a previously-generated sequence picking it would extend (exponential
    /// in the match length), so a long verbatim loop becomes exponentially hard to
    /// continue while ordinary reuse is barely touched — targeted loop suppression
    /// without the collateral damage of a flat repetition penalty or a hard n-gram
    /// ban. The penalty is computed over the tokens generated in this call.
    /// Reproducible per `seed`.
    pub fn generate_dry(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        dry: &sovereign_dry_sampler::DrySampler,
    ) -> Result<Vec<usize>, StackError> {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated: Vec<usize> = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            let history: Vec<u32> = generated.iter().map(|&i| i as u32).collect();
            dry.apply(&mut logits, &history);
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// Like [`generate_dynamic_mask`](Self::generate_dynamic_mask) but the mask
    /// hook may **stop** generation: `mask_fn(&generated)` returns `None` to end
    /// (e.g. a grammar constraint signalling the output is a complete sentence, or
    /// that no token can keep the parse valid) or `Some(mask)` to apply and
    /// continue. Generates at most `max_new` tokens. Returns the generated ids.
    pub fn generate_dynamic_mask_until<M>(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mut mask_fn: M,
    ) -> Result<Vec<usize>, StackError>
    where
        M: FnMut(&[usize]) -> Option<LogitMask>,
    {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
        }
        let mut generated = Vec::with_capacity(max_new);
        for _ in 0..max_new {
            let Some(mask) = mask_fn(&generated) else {
                break;
            };
            mask.apply(&mut logits);
            let pos = self.position() as u64;
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }

    /// The M002-native dynamic constraint loop (SDD-501): like
    /// [`generate_dynamic_mask_until`](Self::generate_dynamic_mask_until) but the
    /// per-step hook returns a **token-law allow-mask** (a packed `Vec<u64>`,
    /// typically `sovereign_token_law_mask::TokenLawPlanes::combine_with(...)`
    /// intersecting a grammar plane with static policy planes) rather than a
    /// `LogitMask`. `law_fn(&generated)` returns `None` to stop (the grammar is
    /// complete, or no token keeps every plane satisfiable — never sample from
    /// an all-masked row) or `Some(allow)` to `-inf`-mask every disallowed token
    /// and continue. This is the multi-plane realization of M00117: one running
    /// model confined by grammar **and** policy at once, composed by the real
    /// `token_law_combine` kernel. Generates at most `max_new` tokens.
    pub fn generate_dynamic_token_law_until<M>(
        &mut self,
        prompt: &[usize],
        max_new: usize,
        seed: u64,
        mut law_fn: M,
    ) -> Result<Vec<usize>, StackError>
    where
        M: FnMut(&[usize]) -> Option<Vec<u64>>,
    {
        if prompt.is_empty() {
            return Err(StackError::EmptyPrompt);
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
            let recent_start = self.recent.len().saturating_sub(self.config.recent_window);
            let token = self.config.sampler.sample_seeded(
                &logits,
                &self.recent[recent_start..],
                seed.wrapping_add(pos),
            )?;
            self.recent.push(token);
            generated.push(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
    }
}

/// Deterministic splitmix64 → uniform `[0, 1)` from one seed, so the Mirostat
/// path is reproducible without threading an RNG type through the stack.
fn splitmix_uniform(seed: u64) -> f64 {
    let mut z = seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^= z >> 31;
    (z >> 11) as f64 / (1u64 << 53) as f64
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_ffn::SwiGlu;
    use sovereign_sampler::{Mirostat, SamplerConfig};

    fn block(model_dim: usize, seed: f32) -> BlockWeights {
        let hd = model_dim;
        let mat = |s: f32, n: usize| (0..n).map(|i| ((i as f32 + s) * 0.01).sin()).collect();
        BlockWeights {
            model_dim,
            head_dim: hd,
            attn_norm: RmsNorm::new(model_dim),
            ffn_norm: RmsNorm::new(model_dim),
            w_q: mat(seed, hd * model_dim),
            w_k: mat(seed + 1.0, hd * model_dim),
            w_v: mat(seed + 2.0, hd * model_dim),
            w_o: mat(seed + 3.0, model_dim * hd),
            ffn: SwiGlu::new(
                model_dim,
                model_dim,
                mat(seed + 4.0, model_dim * model_dim),
                mat(seed + 5.0, model_dim * model_dim),
                mat(seed + 6.0, model_dim * model_dim),
            )
            .unwrap(),
        }
    }

    fn config(vocab: usize, model_dim: usize, layers: usize, sampler: Sampler) -> StackConfig {
        StackConfig {
            vocab,
            model_dim,
            embedding: (0..vocab * model_dim)
                .map(|i| ((i as f32) * 0.05).sin())
                .collect(),
            blocks: (0..layers)
                .map(|l| block(model_dim, l as f32 * 10.0))
                .collect(),
            final_norm: RmsNorm::new(model_dim),
            head: (0..vocab * model_dim)
                .map(|i| ((i as f32) * 0.03).cos())
                .collect(),
            sampler,
            recent_window: 64,
        }
    }

    #[test]
    fn generates_requested_number_of_in_range_tokens() {
        let mut m =
            DecoderStack::new(config(6, 4, 2, Sampler::new(SamplerConfig::default()))).unwrap();
        let out = m.generate(&[1, 2, 3], 5, 42).unwrap();
        assert_eq!(out.len(), 5);
        assert!(out.iter().all(|&t| t < 6));
    }

    #[test]
    fn dynamic_mask_confines_every_token_to_the_allowed_set() {
        // A mask_fn that always allows only tokens 1..=2 — the dynamic loop must
        // apply it each step, so every generated token is in the set.
        let mut m = DecoderStack::new(config(8, 4, 2, Sampler::greedy())).unwrap();
        let out = m
            .generate_dynamic_mask(&[3, 4], 6, 7, |_generated| {
                LogitMask::new().allow_only(1..=2)
            })
            .unwrap();
        assert_eq!(out.len(), 6);
        assert!(out.iter().all(|&t| (1..=2).contains(&t)), "{out:?}");
    }

    #[test]
    fn piped_empty_pipeline_equals_plain_generate() {
        use sovereign_logit_pipeline::LogitPipeline;
        let cfg = config(8, 4, 2, Sampler::greedy());
        let plain = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate(&[1, 2], 6, 9)
            .unwrap();
        let piped = DecoderStack::new(cfg)
            .unwrap()
            .generate_piped(&[1, 2], 6, 9, &LogitPipeline::new())
            .unwrap();
        assert_eq!(piped, plain);
    }

    #[test]
    fn piped_composes_multiple_ban_processors() {
        use sovereign_logit_pipeline::{LogitPipeline, MaskProcessor};
        // two mask processors, each banning a different token — the pipeline must
        // apply BOTH each step, so neither banned token can ever be emitted.
        let mut m = DecoderStack::new(config(8, 4, 2, Sampler::greedy())).unwrap();
        let pipeline = LogitPipeline::new()
            .with(Box::new(MaskProcessor(LogitMask::new().ban_all([5, 6, 7]))))
            .with(Box::new(MaskProcessor(LogitMask::new().ban_all([0, 1]))));
        let out = m.generate_piped(&[2, 3], 8, 7, &pipeline).unwrap();
        assert_eq!(out.len(), 8);
        assert!(
            out.iter().all(|&t| ![0, 1, 5, 6, 7].contains(&t)),
            "banned token leaked: {out:?}"
        );
    }

    #[test]
    fn gumbel_generates_in_range_and_is_reproducible() {
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let a = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate_gumbel(&[1, 2, 3], 6, 42)
            .unwrap();
        let b = DecoderStack::new(cfg)
            .unwrap()
            .generate_gumbel(&[1, 2, 3], 6, 42)
            .unwrap();
        assert_eq!(a.len(), 6);
        assert!(a.iter().all(|&t| t < 8), "{a:?}");
        assert_eq!(a, b, "same seed must reproduce the Gumbel draw");
    }

    #[test]
    fn gumbel_sample_matches_softmax_on_a_peaked_distribution() {
        // Gumbel-max draws exactly softmax(logits); a dominant logit should win a
        // large majority of single-step draws.
        let mut wins = 0;
        for s in 0..400u64 {
            let mut g = sovereign_gumbel::GumbelSampler::new(s);
            // token 3 is far above the rest → softmax mass ~concentrated there
            if g.sample(&[0.0, 0.0, 0.0, 6.0, 0.0, 0.0]) == Some(3) {
                wins += 1;
            }
        }
        assert!(wins > 360, "peaked logit won only {wins}/400");
    }

    #[test]
    fn dry_inactive_equals_plain_generate() {
        use sovereign_dry_sampler::DrySampler;
        // multiplier 0 → DRY inactive → identical to plain generation.
        let cfg = config(8, 4, 2, Sampler::greedy());
        let plain = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate(&[1, 2], 6, 9)
            .unwrap();
        let dry = DrySampler::new(0.0, 1.75, 2);
        let with_dry = DecoderStack::new(cfg)
            .unwrap()
            .generate_dry(&[1, 2], 6, 9, &dry)
            .unwrap();
        assert_eq!(plain, with_dry);
    }

    #[test]
    fn dry_active_is_reproducible() {
        use sovereign_dry_sampler::DrySampler;
        let cfg = config(8, 4, 2, Sampler::greedy());
        let dry = DrySampler::new(2.0, 1.75, 1);
        let a = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate_dry(&[1, 2], 8, 4, &dry)
            .unwrap();
        let b = DecoderStack::new(cfg)
            .unwrap()
            .generate_dry(&[1, 2], 8, 4, &dry)
            .unwrap();
        assert_eq!(a, b);
        assert_eq!(a.len(), 8);
    }

    #[test]
    fn xtc_inactive_equals_plain_generate() {
        use sovereign_xtc_sampler::XtcSampler;
        // probability 0 → XTC never fires → identical to plain generation.
        let cfg = config(8, 4, 2, Sampler::greedy());
        let plain = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate(&[1, 2], 6, 9)
            .unwrap();
        let xtc = XtcSampler::new(0.1, 0.0);
        let with_xtc = DecoderStack::new(cfg)
            .unwrap()
            .generate_xtc(&[1, 2], 6, 9, &xtc)
            .unwrap();
        assert_eq!(plain, with_xtc);
    }

    #[test]
    fn xtc_active_can_change_the_output_and_is_reproducible() {
        use sovereign_xtc_sampler::XtcSampler;
        // an always-firing, low-threshold XTC excludes top choices, so the output
        // can differ from greedy; and it is reproducible for a fixed seed.
        let cfg = config(8, 4, 2, Sampler::greedy());
        let xtc = XtcSampler::new(0.01, 1.0);
        let a = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate_xtc(&[1, 2], 8, 4, &xtc)
            .unwrap();
        let b = DecoderStack::new(cfg)
            .unwrap()
            .generate_xtc(&[1, 2], 8, 4, &xtc)
            .unwrap();
        assert_eq!(a, b, "reproducible for a fixed seed");
        assert_eq!(a.len(), 8);
    }

    #[test]
    fn dynamic_mask_until_stops_when_hook_returns_none() {
        // Allow token 2 for the first 3 steps, then stop — so exactly [2,2,2] is
        // generated even though max_new is larger.
        let mut m = DecoderStack::new(config(8, 4, 2, Sampler::greedy())).unwrap();
        let out = m
            .generate_dynamic_mask_until(&[1], 10, 5, |generated| {
                if generated.len() < 3 {
                    Some(LogitMask::new().allow_only(2..=2))
                } else {
                    None
                }
            })
            .unwrap();
        assert_eq!(out, vec![2, 2, 2]);
    }

    #[test]
    fn dynamic_mask_can_tighten_as_generation_proceeds() {
        // The mask depends on how many tokens have been generated: first step
        // allows token 5, afterwards only token 2 — proving the hook sees state.
        let mut m = DecoderStack::new(config(8, 4, 2, Sampler::greedy())).unwrap();
        let out = m
            .generate_dynamic_mask(&[1], 4, 1, |generated| {
                if generated.is_empty() {
                    LogitMask::new().allow_only(5..=5)
                } else {
                    LogitMask::new().allow_only(2..=2)
                }
            })
            .unwrap();
        assert_eq!(out, vec![5, 2, 2, 2]);
    }

    #[test]
    fn streaming_matches_batch_and_fires_per_token() {
        // The streamed token sequence equals what generate_masked returns, and
        // on_token fires exactly max_new times, in order.
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let batch = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate(&[1, 2], 6, 99)
            .unwrap();
        let mut streamed = Vec::new();
        let mut m = DecoderStack::new(cfg).unwrap();
        m.generate_masked_with(&[1, 2], 6, 99, &LogitMask::new(), |t| streamed.push(t))
            .unwrap();
        assert_eq!(streamed, batch);
        assert_eq!(streamed.len(), 6);
    }

    #[test]
    fn mirostat_generation_runs_reproducibly_and_advances_mu() {
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let mut m1 = DecoderStack::new(cfg.clone()).unwrap();
        let mut ms1 = Mirostat::new(2.0, 0.1);
        let a = m1.generate_mirostat(&[1, 2], 6, 7, &mut ms1).unwrap();
        assert_eq!(a.len(), 6);
        assert!(a.iter().all(|&t| t < 8));
        // μ moved from its 2τ start as the controller adapted.
        assert!((ms1.mu() - 4.0).abs() > 1e-6, "μ should have adapted");

        // Same seed + fresh controller → identical sequence (reproducible).
        let mut m2 = DecoderStack::new(cfg).unwrap();
        let mut ms2 = Mirostat::new(2.0, 0.1);
        let b = m2.generate_mirostat(&[1, 2], 6, 7, &mut ms2).unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn no_repeat_ngram_generation_has_no_repeated_ngram() {
        // With dynamic n=3 blocking, the full sequence (prompt + generated) must
        // contain no repeated 3-gram, and the run is reproducible.
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let mut m = DecoderStack::new(cfg.clone()).unwrap();
        let prompt = [1usize, 2, 3];
        let out = m.generate_no_repeat_ngram(&prompt, 12, 7, 3).unwrap();
        let mut full = prompt.to_vec();
        full.extend(&out);
        let mut seen = std::collections::HashSet::new();
        for w in full.windows(3) {
            assert!(seen.insert(w.to_vec()), "3-gram {w:?} repeated");
        }
        // reproducible
        let mut m2 = DecoderStack::new(cfg).unwrap();
        assert_eq!(out, m2.generate_no_repeat_ngram(&prompt, 12, 7, 3).unwrap());
    }

    #[test]
    fn generate_until_stops_at_a_stop_token() {
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let prompt = [1usize, 2];
        // Discover the first greedy/sampled token, then make it a stop token →
        // generation must end after exactly one token (the stop token).
        let first = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate(&prompt, 1, 9)
            .unwrap()[0];
        let mut m = DecoderStack::new(cfg.clone()).unwrap();
        let out = m.generate_until(&prompt, 10, 9, &[first]).unwrap();
        assert_eq!(out, vec![first]);

        // Empty stop set → identical to generate (full length).
        let mut a = DecoderStack::new(cfg.clone()).unwrap();
        let mut b = DecoderStack::new(cfg).unwrap();
        assert_eq!(
            a.generate_until(&prompt, 6, 9, &[]).unwrap(),
            b.generate(&prompt, 6, 9).unwrap()
        );
    }

    #[test]
    fn dynamic_token_law_composes_grammar_and_policy() {
        // SDD-501: multi-plane composition gates the decoder. A static safety
        // plane bans token 5; a per-step "grammar" plane allows {2,5,6}; the AND
        // confines generation to {2,6}, and the loop stops when law_fn says None.
        use sovereign_token_law_mask::TokenLawPlanes;
        let cfg = config(8, 4, 2, Sampler::greedy());
        let planes = TokenLawPlanes::new(8).with_allow_ids(&[0, 1, 2, 3, 4, 6, 7]); // ban 5
        let prompt = [1usize, 3];
        let mut m = DecoderStack::new(cfg).unwrap();
        let out = m
            .generate_dynamic_token_law_until(&prompt, 12, 7, |generated| {
                if generated.len() >= 5 {
                    None // stop after five tokens
                } else {
                    // "grammar" this step allows {2,5,6}; AND static-ban(5) → {2,6}
                    Some(planes.combine_with(&[2, 5, 6]))
                }
            })
            .unwrap();
        assert_eq!(out.len(), 5);
        for t in &out {
            assert!(
                *t == 2 || *t == 6,
                "emitted a token outside grammar∧policy: {t}"
            );
        }
    }

    #[test]
    fn token_law_mask_constrains_generation_to_the_allow_set() {
        // SDD-500: the M002 token-law bitset actually gates generation.
        // vocab 8, greedy for determinism. Allow ONLY tokens {2, 5}.
        let cfg = config(8, 4, 2, Sampler::greedy());
        let allow = vec![(1u64 << 2) | (1u64 << 5)]; // bits 2 and 5 set
        let prompt = [1usize, 3];

        let mut m = DecoderStack::new(cfg.clone()).unwrap();
        let out = m
            .generate_with(
                &prompt,
                7,
                &GenOptions::new(12).with_token_law(allow),
                |_| {},
            )
            .unwrap();
        assert!(!out.is_empty());
        for t in &out {
            assert!(*t == 2 || *t == 5, "emitted disallowed token {t}");
        }

        // Proof the MASK is what constrained it: a full-allow mask (every bit
        // set) must be an exact no-op vs unconstrained generation.
        let mut unc = DecoderStack::new(cfg.clone()).unwrap();
        let unconstrained = unc
            .generate_with(&prompt, 7, &GenOptions::new(12), |_| {})
            .unwrap();
        let mut full = DecoderStack::new(cfg).unwrap();
        let full_allow = full
            .generate_with(
                &prompt,
                7,
                &GenOptions::new(12).with_token_law(vec![u64::MAX]),
                |_| {},
            )
            .unwrap();
        assert_eq!(
            unconstrained, full_allow,
            "a full-allow mask must be a no-op"
        );
    }

    #[test]
    fn generate_with_composes_all_controls() {
        // No-repeat-3gram + early-stop + streaming, all at once.
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let prompt = [1usize, 2, 3];
        // Discover a token to use as a stop, then compose everything.
        let probe = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate(&prompt, 1, 5)
            .unwrap()[0];
        let opts = GenOptions::new(12)
            .with_no_repeat_ngram(3)
            .with_stop_tokens([probe]);
        let mut streamed = Vec::new();
        let mut m = DecoderStack::new(cfg.clone()).unwrap();
        let out = m
            .generate_with(&prompt, 5, &opts, |t| streamed.push(t))
            .unwrap();
        // streaming fired for every produced token
        assert_eq!(streamed, out);
        // ended at the stop token (or hit the cap)
        assert!(out.len() <= 12);
        if out.len() < 12 {
            assert_eq!(*out.last().unwrap(), probe);
        }
        // no 3-gram repeats across prompt + output
        let mut full = prompt.to_vec();
        full.extend(&out);
        let mut seen = std::collections::HashSet::new();
        assert!(full.windows(3).all(|w| seen.insert(w.to_vec())));

        // reproducible
        let mut m2 = DecoderStack::new(cfg).unwrap();
        assert_eq!(out, m2.generate_with(&prompt, 5, &opts, |_| {}).unwrap());
    }

    #[test]
    fn prefix_reuse_is_transparent_and_amortizes() {
        // Priming a prefix then generating a suffix must equal generating the
        // concatenation in one call — so a primed clone can be reused per
        // request without changing the output.
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let prefix = [1usize, 2, 3];
        let suffix = [4usize, 5];

        let mut whole = DecoderStack::new(cfg.clone()).unwrap();
        let mut full = prefix.to_vec();
        full.extend(&suffix);
        let mono = whole.generate(&full, 6, 7).unwrap();

        // Prime once, then reuse the primed state for the (here single) request.
        let mut base = DecoderStack::new(cfg).unwrap();
        base.prime(&prefix).unwrap();
        assert_eq!(base.position(), 3); // cache advanced over the prefix
        let mut reused = base.clone(); // a clone per request would share the prefix
        let out = reused.generate(&suffix, 6, 7).unwrap();
        assert_eq!(out, mono, "prefix reuse must be output-identical");
        // The primed base is untouched and reusable for the next request.
        assert_eq!(base.position(), 3);
    }

    #[test]
    fn generate_with_min_new_defers_the_stop_token() {
        // Make the first sampled token a stop token; with min_new it cannot be
        // emitted until at least min_new tokens are out, so the output is longer.
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let prompt = [1usize, 2];
        let first = DecoderStack::new(cfg.clone())
            .unwrap()
            .generate(&prompt, 1, 9)
            .unwrap()[0];

        // Without min_new: stops immediately at the stop token.
        let opts_stop = GenOptions::new(10).with_stop_tokens([first]);
        let mut a = DecoderStack::new(cfg.clone()).unwrap();
        let stopped = a.generate_with(&prompt, 9, &opts_stop, |_| {}).unwrap();
        assert_eq!(stopped, vec![first]);

        // With min_new = 4: the stop token is masked for the first 4 tokens.
        let opts_min = GenOptions::new(10)
            .with_stop_tokens([first])
            .with_min_new(4);
        let mut b = DecoderStack::new(cfg).unwrap();
        let out = b.generate_with(&prompt, 9, &opts_min, |_| {}).unwrap();
        assert!(out.len() >= 4, "min_new must force ≥4 tokens: {out:?}");
        // None of the first 4 emitted tokens is the (banned) stop token.
        assert!(out[..4].iter().all(|&t| t != first));
    }

    #[test]
    fn generate_with_plain_equals_generate() {
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let prompt = [1usize, 2];
        let mut a = DecoderStack::new(cfg.clone()).unwrap();
        let mut b = DecoderStack::new(cfg).unwrap();
        let plain = a
            .generate_with(&prompt, 9, &GenOptions::new(6), |_| {})
            .unwrap();
        assert_eq!(plain, b.generate(&prompt, 6, 9).unwrap());
    }

    #[test]
    fn generate_until_empty_prompt_errors() {
        let mut m =
            DecoderStack::new(config(6, 4, 1, Sampler::new(SamplerConfig::default()))).unwrap();
        assert_eq!(
            m.generate_until(&[], 3, 1, &[0]).unwrap_err(),
            StackError::EmptyPrompt
        );
    }

    #[test]
    fn no_repeat_ngram_empty_prompt_errors() {
        let mut m =
            DecoderStack::new(config(6, 4, 1, Sampler::new(SamplerConfig::default()))).unwrap();
        assert_eq!(
            m.generate_no_repeat_ngram(&[], 3, 1, 2).unwrap_err(),
            StackError::EmptyPrompt
        );
    }

    #[test]
    fn mirostat_empty_prompt_errors() {
        let mut m =
            DecoderStack::new(config(6, 4, 1, Sampler::new(SamplerConfig::default()))).unwrap();
        let mut ms = Mirostat::new(3.0, 0.1);
        assert_eq!(
            m.generate_mirostat(&[], 3, 1, &mut ms).unwrap_err(),
            StackError::EmptyPrompt
        );
    }

    #[test]
    fn streaming_empty_prompt_errors() {
        let mut m =
            DecoderStack::new(config(6, 4, 1, Sampler::new(SamplerConfig::default()))).unwrap();
        let err = m
            .generate_masked_with(&[], 3, 1, &LogitMask::new(), |_| {})
            .unwrap_err();
        assert_eq!(err, StackError::EmptyPrompt);
    }

    #[test]
    fn position_tracks_prompt_plus_generated() {
        let mut m =
            DecoderStack::new(config(6, 4, 3, Sampler::new(SamplerConfig::default()))).unwrap();
        m.generate(&[0, 1], 4, 7).unwrap();
        // 2 prompt + 4 generated forward passes = 6 positions in every layer
        assert_eq!(m.position(), 6);
        assert_eq!(m.layers(), 3);
    }

    #[test]
    fn generation_is_reproducible_per_seed() {
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let mut a = DecoderStack::new(cfg.clone()).unwrap();
        let mut b = DecoderStack::new(cfg).unwrap();
        assert_eq!(
            a.generate(&[1, 2], 6, 999).unwrap(),
            b.generate(&[1, 2], 6, 999).unwrap()
        );
    }

    #[test]
    fn greedy_head_forces_the_dominant_token() {
        // A head whose row 3 dominates → greedy sampling always emits token 3.
        let mut cfg = config(5, 4, 1, Sampler::greedy());
        // zero the head, then make row 3 large and positive
        cfg.head = vec![0.0; 5 * 4];
        for c in 0..4 {
            cfg.head[3 * 4 + c] = 100.0;
        }
        // also make the embedding+final norm produce a positive hidden so row 3
        // wins; with a positive constant hidden, row 3's dot is large positive.
        cfg.embedding = vec![1.0; 5 * 4];
        let mut m = DecoderStack::new(cfg).unwrap();
        let out = m.generate(&[0], 4, 1).unwrap();
        assert!(out.iter().all(|&t| t == 3), "got {out:?}");
    }

    #[test]
    fn emitted_matches_generated() {
        let mut m =
            DecoderStack::new(config(6, 4, 2, Sampler::new(SamplerConfig::default()))).unwrap();
        let out = m.generate(&[2], 3, 5).unwrap();
        assert_eq!(m.emitted(), out.as_slice());
    }

    #[test]
    fn empty_prompt_is_an_error() {
        let mut m = DecoderStack::new(config(6, 4, 1, Sampler::greedy())).unwrap();
        assert_eq!(m.generate(&[], 3, 1).unwrap_err(), StackError::EmptyPrompt);
    }

    #[test]
    fn masked_generation_stays_in_the_allow_list() {
        let mut m =
            DecoderStack::new(config(8, 4, 2, Sampler::new(SamplerConfig::default()))).unwrap();
        let mask = LogitMask::new().allow_only([2usize, 5]);
        let out = m.generate_masked(&[1, 3], 12, 7, &mask).unwrap();
        assert!(out.iter().all(|&t| t == 2 || t == 5), "got {out:?}");
    }

    #[test]
    fn empty_mask_matches_plain_generate() {
        let cfg = config(8, 4, 2, Sampler::new(SamplerConfig::default()));
        let mut a = DecoderStack::new(cfg.clone()).unwrap();
        let mut b = DecoderStack::new(cfg).unwrap();
        assert_eq!(
            a.generate(&[1, 2], 6, 5).unwrap(),
            b.generate_masked(&[1, 2], 6, 5, &LogitMask::new()).unwrap()
        );
    }

    #[test]
    fn token_out_of_range_is_caught() {
        let mut m = DecoderStack::new(config(4, 4, 1, Sampler::greedy())).unwrap();
        assert_eq!(
            m.forward(9).unwrap_err(),
            StackError::TokenOutOfRange { token: 9, vocab: 4 }
        );
    }

    #[test]
    fn no_blocks_is_rejected() {
        let mut cfg = config(4, 4, 1, Sampler::greedy());
        cfg.blocks.clear();
        assert_eq!(DecoderStack::new(cfg).unwrap_err(), StackError::NoBlocks);
    }

    #[test]
    fn embedding_shape_is_validated() {
        let mut cfg = config(4, 4, 1, Sampler::greedy());
        cfg.embedding.pop();
        assert!(matches!(
            DecoderStack::new(cfg).unwrap_err(),
            StackError::EmbeddingShape { .. }
        ));
    }

    #[test]
    fn config_serde_round_trip() {
        let cfg = config(4, 4, 2, Sampler::new(SamplerConfig::default()));
        let j = serde_json::to_string(&cfg).unwrap();
        let back: StackConfig = serde_json::from_str(&j).unwrap();
        assert_eq!(cfg, back);
    }
}
