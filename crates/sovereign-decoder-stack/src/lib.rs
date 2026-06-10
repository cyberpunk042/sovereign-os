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
//! [`sovereign-transformer-block`]: https://docs.rs/sovereign-transformer-block
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_logit_mask::LogitMask;
use sovereign_rmsnorm::RmsNorm;
use sovereign_sampler::{Sampler, SamplerError};
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
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_ffn::SwiGlu;
    use sovereign_sampler::SamplerConfig;

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
