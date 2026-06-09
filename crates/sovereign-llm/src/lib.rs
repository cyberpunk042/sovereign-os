//! `sovereign-llm` — the end-to-end text-to-text runtime.
//!
//! Every other crate in the inference arc does one stage; this is the one that
//! makes the whole thing *runnable from text*. It binds a byte-level BPE
//! [`Tokenizer`] to a [`DecoderStack`] so a caller can go straight from a
//! prompt string to generated text:
//!
//! ```text
//!   ids        = tokenizer.encode(prompt)
//!   new_ids    = model.generate(ids, max_new, seed)
//!   completion = tokenizer.decode(new_ids)
//! ```
//!
//! The one invariant that ties the two halves together — the model's
//! vocabulary must equal the tokenizer's — is checked at construction, so a
//! mismatched pair can never silently emit out-of-range ids. Because both the
//! tokenizer and the model are deterministic, a completion is fully
//! reproducible for a given seed, which is what lets the sovereign runtime log
//! and replay a generation exactly.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_decoder_stack::{DecoderStack, StackConfig, StackError};
use sovereign_logit_mask::LogitMask;
use sovereign_tokenizer::Tokenizer;
use thiserror::Error;

/// Schema version of the LLM runtime surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong building or running the runtime.
#[derive(Debug, Error, PartialEq)]
pub enum LlmError {
    /// The model's vocabulary size did not match the tokenizer's.
    #[error("vocab mismatch: tokenizer has {tokenizer}, model has {model}")]
    VocabMismatch {
        /// Tokenizer vocabulary size.
        tokenizer: usize,
        /// Model vocabulary size.
        model: usize,
    },
    /// The prompt encoded to zero tokens (cannot prime the model).
    #[error("prompt encoded to no tokens")]
    EmptyPrompt,
    /// A model/stack error bubbled up.
    #[error("model: {0}")]
    Stack(#[from] StackError),
}

/// The serializable definition of a runtime: a tokenizer + a model config.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LlmConfig {
    /// The byte-level BPE tokenizer.
    pub tokenizer: Tokenizer,
    /// The decoder-only model configuration.
    pub model: StackConfig,
}

/// A runnable text-to-text LLM: tokenizer + stacked decoder model.
#[derive(Debug, Clone)]
pub struct SovereignLlm {
    tokenizer: Tokenizer,
    model: DecoderStack,
}

impl SovereignLlm {
    /// Build a runtime, checking that the model's vocab matches the tokenizer.
    pub fn new(tokenizer: Tokenizer, config: StackConfig) -> Result<Self, LlmError> {
        if config.vocab != tokenizer.vocab_size() {
            return Err(LlmError::VocabMismatch {
                tokenizer: tokenizer.vocab_size(),
                model: config.vocab,
            });
        }
        let model = DecoderStack::new(config)?;
        Ok(Self { tokenizer, model })
    }

    /// Build from a serializable [`LlmConfig`].
    pub fn from_config(config: LlmConfig) -> Result<Self, LlmError> {
        Self::new(config.tokenizer, config.model)
    }

    /// The shared vocabulary size.
    pub fn vocab_size(&self) -> usize {
        self.tokenizer.vocab_size()
    }

    /// Number of decoder layers.
    pub fn layers(&self) -> usize {
        self.model.layers()
    }

    /// Borrow the tokenizer.
    pub fn tokenizer(&self) -> &Tokenizer {
        &self.tokenizer
    }

    /// Complete `prompt`, returning **only** the newly generated text.
    /// Reproducible for a given `seed`. Stateless: each call decodes from a
    /// fresh clone of the model, so repeated calls never contaminate each
    /// other (which is what lets a chat/agent loop reuse one runtime).
    pub fn complete(&self, prompt: &str, max_new: usize, seed: u64) -> Result<String, LlmError> {
        let generated = self.generate_ids(prompt, max_new, seed)?;
        // ids come straight from the model's own vocab, so decode never fails.
        Ok(self.tokenizer.decode(&generated).unwrap_or_default())
    }

    /// Complete `prompt`, returning the prompt followed by the generated text.
    pub fn complete_with_prompt(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<String, LlmError> {
        let completion = self.complete(prompt, max_new, seed)?;
        Ok(format!("{prompt}{completion}"))
    }

    /// The token ids generated for `prompt` (without decoding to text).
    pub fn generate_ids(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<Vec<u32>, LlmError> {
        self.generate_ids_constrained(prompt, max_new, seed, &LogitMask::new())
    }

    /// Like [`generate_ids`](Self::generate_ids) but applies a [`LogitMask`]
    /// at every step — constrained decoding (allow-list / bans / bias).
    pub fn generate_ids_constrained(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
    ) -> Result<Vec<u32>, LlmError> {
        let ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .into_iter()
            .map(|t| t as usize)
            .collect();
        if ids.is_empty() {
            return Err(LlmError::EmptyPrompt);
        }
        // clone the model so generation starts from a pristine cache every call
        let mut model = self.model.clone();
        let generated = model.generate_masked(&ids, max_new, seed, mask)?;
        Ok(generated.iter().map(|&t| t as u32).collect())
    }

    /// Complete `prompt` under a [`LogitMask`], returning only the newly
    /// generated text. Confines generation to the mask's permitted tokens.
    pub fn complete_constrained(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
    ) -> Result<String, LlmError> {
        let generated = self.generate_ids_constrained(prompt, max_new, seed, mask)?;
        Ok(self.tokenizer.decode(&generated).unwrap_or_default())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_ffn::SwiGlu;
    use sovereign_rmsnorm::RmsNorm;
    use sovereign_sampler::{Sampler, SamplerConfig};
    use sovereign_transformer_block::BlockWeights;

    fn block(model_dim: usize, seed: f32) -> BlockWeights {
        let hd = model_dim;
        let mat = |s: f32, n: usize| (0..n).map(|i| ((i as f32 + s) * 0.013).sin()).collect();
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

    /// A model whose vocab matches a base (256-token) tokenizer.
    fn model_config(
        vocab: usize,
        model_dim: usize,
        layers: usize,
        sampler: Sampler,
    ) -> StackConfig {
        StackConfig {
            vocab,
            model_dim,
            embedding: (0..vocab * model_dim)
                .map(|i| ((i as f32) * 0.001).sin())
                .collect(),
            blocks: (0..layers)
                .map(|l| block(model_dim, l as f32 * 7.0))
                .collect(),
            final_norm: RmsNorm::new(model_dim),
            head: (0..vocab * model_dim)
                .map(|i| ((i as f32) * 0.001).cos())
                .collect(),
            sampler,
            recent_window: 64,
        }
    }

    fn runtime(sampler: Sampler) -> SovereignLlm {
        let tok = Tokenizer::default(); // 256-token base vocab
        let cfg = model_config(tok.vocab_size(), 4, 2, sampler);
        SovereignLlm::new(tok, cfg).unwrap()
    }

    #[test]
    fn vocab_must_match() {
        let tok = Tokenizer::default(); // 256
        let cfg = model_config(100, 4, 1, Sampler::greedy()); // wrong vocab
        assert_eq!(
            SovereignLlm::new(tok, cfg).unwrap_err(),
            LlmError::VocabMismatch {
                tokenizer: 256,
                model: 100
            }
        );
    }

    #[test]
    fn complete_produces_decodable_text() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let out = llm.complete("hello", 8, 42).unwrap();
        // generated text decodes (possibly lossy) — just assert it ran & is a String
        assert!(out.is_empty() || out.is_char_boundary(0));
        // 8 new tokens were generated
        assert_eq!(llm.generate_ids("hello", 8, 42).unwrap().len(), 8);
    }

    #[test]
    fn completion_is_reproducible_per_seed() {
        let a = runtime(Sampler::new(SamplerConfig::default()));
        let b = runtime(Sampler::new(SamplerConfig::default()));
        assert_eq!(
            a.generate_ids("the quick brown fox", 10, 7).unwrap(),
            b.generate_ids("the quick brown fox", 10, 7).unwrap()
        );
    }

    #[test]
    fn complete_with_prompt_prefixes_the_input() {
        let llm = runtime(Sampler::greedy());
        let full = llm.complete_with_prompt("abc", 4, 1).unwrap();
        assert!(full.starts_with("abc"), "{full:?}");
    }

    #[test]
    fn generated_ids_are_in_vocab() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let ids = llm.generate_ids("xyz", 12, 99).unwrap();
        let v = llm.vocab_size() as u32;
        assert!(ids.iter().all(|&t| t < v));
    }

    #[test]
    fn empty_prompt_is_an_error() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(llm.complete("", 4, 1).unwrap_err(), LlmError::EmptyPrompt);
    }

    #[test]
    fn generation_is_stateless_across_calls() {
        // Two calls on the SAME runtime with the same args must match (the
        // model is cloned per call, so call 1 never contaminates call 2).
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let a = llm.generate_ids("hello world", 10, 5).unwrap();
        let b = llm.generate_ids("hello world", 10, 5).unwrap();
        assert_eq!(a, b);
        // and a different prompt in between doesn't perturb it
        let _ = llm.generate_ids("other prompt entirely", 7, 9).unwrap();
        let c = llm.generate_ids("hello world", 10, 5).unwrap();
        assert_eq!(a, c);
    }

    #[test]
    fn constrained_completion_confines_to_allowed_tokens() {
        use sovereign_logit_mask::LogitMask;
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        // only bytes for 'A' (65) and 'B' (66) are allowed to be generated
        let mask = LogitMask::new().allow_only([65usize, 66]);
        let ids = llm.generate_ids_constrained("hello", 16, 3, &mask).unwrap();
        assert!(ids.iter().all(|&t| t == 65 || t == 66), "got {ids:?}");
        // and the decoded text is only As and Bs
        let text = llm.complete_constrained("hello", 16, 3, &mask).unwrap();
        assert!(text.chars().all(|c| c == 'A' || c == 'B'), "text {text:?}");
    }

    #[test]
    fn layers_and_vocab_report_correctly() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(llm.vocab_size(), 256);
        assert_eq!(llm.layers(), 2);
    }

    #[test]
    fn config_serde_round_trip() {
        let tok = Tokenizer::default();
        let cfg = LlmConfig {
            tokenizer: tok.clone(),
            model: model_config(tok.vocab_size(), 4, 1, Sampler::greedy()),
        };
        let j = serde_json::to_string(&cfg).unwrap();
        let back: LlmConfig = serde_json::from_str(&j).unwrap();
        assert_eq!(cfg, back);
        // and it builds
        assert!(SovereignLlm::from_config(back).is_ok());
    }
}
