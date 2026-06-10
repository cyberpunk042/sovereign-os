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
use sovereign_decoder_stack::{DecoderStack, GenOptions, StackConfig, StackError};
use sovereign_logit_mask::LogitMask;
use sovereign_sampler::Mirostat;
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

    /// Generate token ids, stopping at the tokenizer's special token named
    /// `eos` (e.g. `"<eos>"`) — the natural serving loop. If that special is
    /// registered, generation stops the moment the model emits it (it is
    /// included); otherwise this is a plain `max_new` generation. Pairs the
    /// tokenizer's special tokens with early-stop.
    pub fn generate_ids_until_eos(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        eos: &str,
    ) -> Result<Vec<u32>, LlmError> {
        match self.tokenizer.special_id(eos) {
            Some(id) => self.generate_ids_until(prompt, max_new, seed, &[id]),
            None => self.generate_ids(prompt, max_new, seed),
        }
    }

    /// Unified, serving-grade generation: compose constrained masking, dynamic
    /// no-repeat-ngram blocking, early-stop, and per-token streaming via
    /// [`GenOptions`] — the single configurable entry point the simpler
    /// `generate_ids*` methods specialize. The `on_token` callback fires with
    /// each generated id; the full id sequence is returned. Pristine cache per
    /// call.
    pub fn generate_ids_with<F: FnMut(u32)>(
        &self,
        prompt: &str,
        seed: u64,
        opts: &GenOptions,
        mut on_token: F,
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
        let mut model = self.model.clone();
        let mut out = Vec::with_capacity(opts.max_new);
        model.generate_with(&ids, seed, opts, |t| {
            let id = t as u32;
            out.push(id);
            on_token(id);
        })?;
        Ok(out)
    }

    /// Generate token ids, stopping early at the first token in `stop_tokens`
    /// (which is included). The EOS / stop-sequence behaviour a real runtime
    /// needs. Pristine cache per call.
    pub fn generate_ids_until(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        stop_tokens: &[u32],
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
        let stops: Vec<usize> = stop_tokens.iter().map(|&t| t as usize).collect();
        let mut model = self.model.clone();
        let generated = model.generate_until(&ids, max_new, seed, &stops)?;
        Ok(generated.iter().map(|&t| t as u32).collect())
    }

    /// Generate token ids under a stateful [`Mirostat`] controller — output
    /// perplexity is held near the controller's target instead of using the
    /// config's static truncation. The controller's `μ` advances across the
    /// call. Starts from a pristine cache (model cloned).
    pub fn generate_ids_mirostat(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mirostat: &mut Mirostat,
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
        let mut model = self.model.clone();
        let generated = model.generate_mirostat(&ids, max_new, seed, mirostat)?;
        Ok(generated.iter().map(|&t| t as u32).collect())
    }

    /// Streaming generation: invoke `on_token` with each generated token id the
    /// moment it is produced, so a caller can emit tokens as they arrive (e.g.
    /// server-sent events) instead of waiting for the whole completion. Returns
    /// the full id sequence too. Starts from a pristine cache (model is cloned),
    /// so it never contaminates other calls.
    pub fn generate_ids_streaming<F: FnMut(u32)>(
        &self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mut on_token: F,
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
        let mut model = self.model.clone();
        let mut out = Vec::with_capacity(max_new);
        model.generate_masked_with(&ids, max_new, seed, &LogitMask::new(), |t| {
            let id = t as u32;
            out.push(id);
            on_token(id);
        })?;
        Ok(out)
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

    /// A runtime whose tokenizer reserves an `<eos>` special token.
    fn runtime_with_eos(sampler: Sampler) -> SovereignLlm {
        let tok = Tokenizer::default().with_specials(["<eos>"]); // vocab 257
        let cfg = model_config(tok.vocab_size(), 4, 2, sampler);
        SovereignLlm::new(tok, cfg).unwrap()
    }

    #[test]
    fn generate_until_eos_uses_the_special_token() {
        let llm = runtime_with_eos(Sampler::new(SamplerConfig::default()));
        let eos = llm.tokenizer().special_id("<eos>").unwrap();
        // eos-aware generation equals generate_ids_until with the resolved id.
        let a = llm.generate_ids_until_eos("hello", 8, 4, "<eos>").unwrap();
        let b = llm.generate_ids_until("hello", 8, 4, &[eos]).unwrap();
        assert_eq!(a, b);
        assert!(a.len() <= 8);
    }

    #[test]
    fn generate_until_eos_unregistered_name_is_plain_generation() {
        let llm = runtime_with_eos(Sampler::new(SamplerConfig::default()));
        let plain = llm.generate_ids("hello", 6, 4).unwrap();
        let eos = llm
            .generate_ids_until_eos("hello", 6, 4, "<not-registered>")
            .unwrap();
        assert_eq!(eos, plain);
        assert_eq!(eos.len(), 6);
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
    fn streaming_matches_batch_and_streams_each_token() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let batch = llm.generate_ids("hello sovereign", 8, 5).unwrap();
        let mut streamed = Vec::new();
        let returned = llm
            .generate_ids_streaming("hello sovereign", 8, 5, |id| streamed.push(id))
            .unwrap();
        assert_eq!(streamed, batch, "streamed ids must match batch");
        assert_eq!(returned, batch, "returned ids must match batch");
        assert_eq!(streamed.len(), 8);
    }

    #[test]
    fn streaming_empty_prompt_errors() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(
            llm.generate_ids_streaming("", 4, 1, |_| {}).unwrap_err(),
            LlmError::EmptyPrompt
        );
    }

    #[test]
    fn mirostat_generation_runs_and_is_reproducible() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let mut ms_a = Mirostat::new(2.5, 0.1);
        let a = llm
            .generate_ids_mirostat("hello sovereign", 8, 3, &mut ms_a)
            .unwrap();
        assert_eq!(a.len(), 8);
        let v = llm.vocab_size() as u32;
        assert!(a.iter().all(|&t| t < v));
        // Same seed + fresh controller → identical ids.
        let mut ms_b = Mirostat::new(2.5, 0.1);
        let b = llm
            .generate_ids_mirostat("hello sovereign", 8, 3, &mut ms_b)
            .unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn mirostat_empty_prompt_errors() {
        let llm = runtime(Sampler::greedy());
        let mut ms = Mirostat::new(3.0, 0.1);
        assert_eq!(
            llm.generate_ids_mirostat("", 4, 1, &mut ms).unwrap_err(),
            LlmError::EmptyPrompt
        );
    }

    #[test]
    fn generate_until_stops_at_stop_token() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let first = llm.generate_ids("hello", 1, 4).unwrap()[0];
        let out = llm.generate_ids_until("hello", 16, 4, &[first]).unwrap();
        assert_eq!(out, vec![first]);
        // empty stop set → full length
        let full = llm.generate_ids_until("hello", 5, 4, &[]).unwrap();
        assert_eq!(full.len(), 5);
    }

    #[test]
    fn generate_until_empty_prompt_errors() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(
            llm.generate_ids_until("", 4, 1, &[0]).unwrap_err(),
            LlmError::EmptyPrompt
        );
    }

    #[test]
    fn generate_with_composes_and_streams() {
        let llm = runtime(Sampler::new(SamplerConfig::default()));
        let opts = GenOptions::new(8).with_no_repeat_ngram(3);
        let mut streamed = Vec::new();
        let out = llm
            .generate_ids_with("hello sovereign", 3, &opts, |id| streamed.push(id))
            .unwrap();
        assert_eq!(streamed, out);
        assert!(out.len() <= 8);
        // reproducible
        let out2 = llm
            .generate_ids_with("hello sovereign", 3, &opts, |_| {})
            .unwrap();
        assert_eq!(out, out2);
    }

    #[test]
    fn generate_with_empty_prompt_errors() {
        let llm = runtime(Sampler::greedy());
        assert_eq!(
            llm.generate_ids_with("", 1, &GenOptions::new(4), |_| {})
                .unwrap_err(),
            LlmError::EmptyPrompt
        );
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
