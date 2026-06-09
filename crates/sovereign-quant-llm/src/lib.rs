//! `sovereign-quant-llm` — the quantized text-to-text runtime.
//!
//! [`sovereign-llm`] fronts the f32 decoder-stack; this is its low-precision
//! sibling, binding the byte-level BPE [`Tokenizer`] to the mixed-precision
//! [`QuantModel`]. A prompt string is encoded to ids, run through a
//! heterogeneous f32/ternary/NVFP4 multi-head decoder, and decoded back to
//! text — the true end-to-end realization of local *quantized* inference:
//!
//! ```text
//!   ids        = tokenizer.encode(prompt)
//!   new_ids    = quant_model.generate(ids, max_new, seed)   // mixed precision
//!   completion = tokenizer.decode(new_ids)
//! ```
//!
//! As with the f32 runtime, the model's vocabulary must equal the
//! tokenizer's (checked at construction), and decoding is reproducible per
//! seed. Constrained decoding is available via [`complete_constrained`].
//!
//! [`sovereign-llm`]: https://docs.rs/sovereign-llm
//! [`QuantModel`]: sovereign_quant_model::QuantModel
//!
//! Standing rule: We do not minimize anything.
//!
//! [`complete_constrained`]: QuantLlm::complete_constrained

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_logit_mask::LogitMask;
use sovereign_quant_model::{QuantModel, QuantModelError};
use sovereign_stream_decode::Utf8Stream;
use sovereign_tokenizer::Tokenizer;
use thiserror::Error;

/// Schema version of the quantized-runtime surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong building or running the quantized runtime.
#[derive(Debug, Error, PartialEq)]
pub enum QuantLlmError {
    /// The model's vocabulary size did not match the tokenizer's.
    #[error("vocab mismatch: tokenizer has {tokenizer}, model has {model}")]
    VocabMismatch {
        /// Tokenizer vocabulary size.
        tokenizer: usize,
        /// Model vocabulary size.
        model: usize,
    },
    /// The prompt encoded to zero tokens.
    #[error("prompt encoded to no tokens")]
    EmptyPrompt,
    /// A model error bubbled up.
    #[error("model: {0}")]
    Model(#[from] QuantModelError),
}

/// A quantized text-to-text runtime: tokenizer + mixed-precision model.
#[derive(Debug)]
pub struct QuantLlm {
    tokenizer: Tokenizer,
    model: QuantModel,
}

impl QuantLlm {
    /// Build a runtime, checking the model's vocab matches the tokenizer's.
    pub fn new(tokenizer: Tokenizer, model: QuantModel) -> Result<Self, QuantLlmError> {
        if model.vocab() != tokenizer.vocab_size() {
            return Err(QuantLlmError::VocabMismatch {
                tokenizer: tokenizer.vocab_size(),
                model: model.vocab(),
            });
        }
        Ok(Self { tokenizer, model })
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

    fn encode_prompt(&self, prompt: &str) -> Result<Vec<usize>, QuantLlmError> {
        let ids: Vec<usize> = self
            .tokenizer
            .encode(prompt)
            .into_iter()
            .map(|t| t as usize)
            .collect();
        if ids.is_empty() {
            return Err(QuantLlmError::EmptyPrompt);
        }
        Ok(ids)
    }

    /// Generate token ids for `prompt` (no decoding). Reproducible per seed.
    pub fn generate_ids(
        &mut self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<Vec<u32>, QuantLlmError> {
        self.generate_ids_constrained(prompt, max_new, seed, &LogitMask::new())
    }

    /// Generate token ids under a [`LogitMask`] (constrained decoding).
    pub fn generate_ids_constrained(
        &mut self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
    ) -> Result<Vec<u32>, QuantLlmError> {
        let ids = self.encode_prompt(prompt)?;
        let generated = self.model.generate_masked(&ids, max_new, seed, mask)?;
        Ok(generated.iter().map(|&t| t as u32).collect())
    }

    /// Complete `prompt`, returning only the newly generated text.
    pub fn complete(
        &mut self,
        prompt: &str,
        max_new: usize,
        seed: u64,
    ) -> Result<String, QuantLlmError> {
        self.complete_constrained(prompt, max_new, seed, &LogitMask::new())
    }

    /// Complete `prompt` under a [`LogitMask`], returning the generated text.
    pub fn complete_constrained(
        &mut self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
    ) -> Result<String, QuantLlmError> {
        let ids = self.generate_ids_constrained(prompt, max_new, seed, mask)?;
        Ok(self.tokenizer.decode(&ids).unwrap_or_default())
    }

    /// Stream a completion: `on_text` is called with each incremental text
    /// chunk as tokens are generated, with multi-byte UTF-8 characters held
    /// across token boundaries (never split). Returns the full completion.
    pub fn stream<F: FnMut(&str)>(
        &mut self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        on_text: F,
    ) -> Result<String, QuantLlmError> {
        self.stream_constrained(prompt, max_new, seed, &LogitMask::new(), on_text)
    }

    /// Streaming completion under a [`LogitMask`]. Decodes token-by-token
    /// through a [`Utf8Stream`] so each `on_text` chunk is always valid UTF-8.
    pub fn stream_constrained<F: FnMut(&str)>(
        &mut self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        mask: &LogitMask,
        mut on_text: F,
    ) -> Result<String, QuantLlmError> {
        let ids = self.encode_prompt(prompt)?;
        let tokenizer = &self.tokenizer;
        let mut stream = Utf8Stream::new();
        let mut full = String::new();
        self.model
            .generate_masked_with(&ids, max_new, seed, mask, |tok| {
                if let Some(bytes) = tokenizer.token_bytes(tok as u32) {
                    let chunk = stream.push(bytes);
                    if !chunk.is_empty() {
                        full.push_str(&chunk);
                        on_text(&chunk);
                    }
                }
            })?;
        let tail = stream.finish();
        if !tail.is_empty() {
            full.push_str(&tail);
            on_text(&tail);
        }
        Ok(full)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_decoder_layer::{DecoderLayer, LayerStack};
    use sovereign_ffn::SwiGlu;
    use sovereign_linear::Precision;
    use sovereign_mha_block::{MhaBlockWeights, MhaDecoderBlock};
    use sovereign_quant_block::{QuantBlockWeights, QuantDecoderBlock};
    use sovereign_quant_model::QuantModel;
    use sovereign_rmsnorm::RmsNorm;
    use sovereign_sampler::{Sampler, SamplerConfig};
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

    fn quant_runtime(sampler: Sampler) -> QuantLlm {
        let tok = Tokenizer::default(); // 256-token base vocab
        let vocab = tok.vocab_size();
        let layers: Vec<Box<dyn DecoderLayer>> = vec![
            Box::new(transformer_layer()),
            Box::new(quant_layer(Precision::Ternary)),
            Box::new(mha_layer(Precision::Nvfp4)),
        ];
        let stack = LayerStack::new(layers).unwrap();
        let model = QuantModel::new(
            vocab,
            MD,
            mat(0.5, vocab * MD),
            stack,
            RmsNorm::new(MD),
            mat(0.9, vocab * MD),
            sampler,
        )
        .unwrap();
        QuantLlm::new(tok, model).unwrap()
    }

    #[test]
    fn vocab_must_match() {
        let tok = Tokenizer::default(); // 256
        let layers: Vec<Box<dyn DecoderLayer>> = vec![Box::new(transformer_layer())];
        let stack = LayerStack::new(layers).unwrap();
        let model = QuantModel::new(
            100, // wrong vocab
            MD,
            mat(0.5, 100 * MD),
            stack,
            RmsNorm::new(MD),
            mat(0.9, 100 * MD),
            Sampler::greedy(),
        )
        .unwrap();
        assert_eq!(
            QuantLlm::new(tok, model).unwrap_err(),
            QuantLlmError::VocabMismatch {
                tokenizer: 256,
                model: 100
            }
        );
    }

    #[test]
    fn quantized_completion_decodes_and_is_in_range() {
        let mut llm = quant_runtime(Sampler::new(SamplerConfig::default()));
        assert_eq!(llm.vocab_size(), 256);
        assert_eq!(llm.layers(), 3);
        let ids = llm.generate_ids("hello", 10, 42).unwrap();
        assert_eq!(ids.len(), 10);
        assert!(ids.iter().all(|&t| t < 256));
        // it decodes to a string (the full quantized text->text path runs)
        let _text = llm.complete("hello", 10, 42).unwrap();
    }

    #[test]
    fn quantized_generation_is_reproducible_per_seed() {
        let mut a = quant_runtime(Sampler::new(SamplerConfig::default()));
        let mut b = quant_runtime(Sampler::new(SamplerConfig::default()));
        assert_eq!(
            a.generate_ids("the quick brown fox", 12, 7).unwrap(),
            b.generate_ids("the quick brown fox", 12, 7).unwrap()
        );
    }

    #[test]
    fn quantized_constrained_completion_confines_output() {
        let mut llm = quant_runtime(Sampler::new(SamplerConfig::default()));
        let mask = LogitMask::new().allow_only([65usize, 66]); // 'A','B'
        let ids = llm.generate_ids_constrained("hello", 16, 3, &mask).unwrap();
        assert!(ids.iter().all(|&t| t == 65 || t == 66), "got {ids:?}");
        let text = llm.complete_constrained("hello", 16, 3, &mask).unwrap();
        assert!(text.chars().all(|c| c == 'A' || c == 'B'), "text {text:?}");
    }

    #[test]
    fn empty_prompt_is_an_error() {
        let mut llm = quant_runtime(Sampler::greedy());
        assert_eq!(
            llm.complete("", 4, 1).unwrap_err(),
            QuantLlmError::EmptyPrompt
        );
    }

    #[test]
    fn streaming_chunks_concatenate_to_the_full_completion() {
        let mut llm = quant_runtime(Sampler::new(SamplerConfig::default()));
        let mut streamed = String::new();
        let mut chunks = 0;
        let full = llm
            .stream("hello", 16, 9, |chunk| {
                streamed.push_str(chunk);
                chunks += 1;
            })
            .unwrap();
        assert_eq!(streamed, full);
        assert!(chunks >= 1);
    }

    #[test]
    fn streaming_matches_batch_completion_same_seed() {
        let mut a = quant_runtime(Sampler::new(SamplerConfig::default()));
        let mut b = quant_runtime(Sampler::new(SamplerConfig::default()));
        let batch = a.complete("the quick brown", 12, 21).unwrap();
        let streamed = b.stream("the quick brown", 12, 21, |_| {}).unwrap();
        assert_eq!(batch, streamed);
    }
}
