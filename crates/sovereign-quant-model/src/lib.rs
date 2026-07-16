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

use sovereign_decoder_layer::{LayerError, LayerStack};
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
        let hidden = self.embed(token);
        let hidden = self.stack.run(&hidden)?;
        let normed = self.final_norm.normalize(&hidden)?;
        let mut logits = self.project_head(&normed);
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
        mut on_token: F,
    ) -> Result<Vec<usize>, QuantModelError> {
        if prompt.is_empty() {
            return Err(QuantModelError::EmptyPrompt);
        }
        let mut logits = Vec::new();
        for &t in prompt {
            logits = self.forward(t)?;
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
            self.recent.push(token);
            generated.push(token);
            on_token(token);
            logits = self.forward(token)?;
        }
        Ok(generated)
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
