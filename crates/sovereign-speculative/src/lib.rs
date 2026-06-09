//! `sovereign-speculative` — lossless speculative decoding over real models.
//!
//! Autoregressive decoding is serial: one expensive target-model forward per
//! token. Speculative decoding amortizes that — a cheap **draft** model
//! proposes `draft_len` tokens, and the **target** model verifies them; every
//! proposed token that matches what the target would itself have produced is
//! accepted for free, and the first mismatch is corrected by the target. Each
//! round commits the accepted prefix plus one target token, so a good draft
//! yields several tokens per target pass.
//!
//! With **greedy** verification (used here) the scheme is *exactly lossless*:
//! every committed token is the target's own argmax at that position, so the
//! output is identical to decoding the target alone — regardless of how good
//! or bad the draft is. That identity is the headline test. The draft only
//! affects *speed* (the acceptance rate), never the result.
//!
//! Both models are `Clone` ([`sovereign-decoder-stack`]), which is what lets
//! the draft propose on a throwaway fork without committing.
//!
//! [`sovereign-decoder-stack`]: https://docs.rs/sovereign-decoder-stack
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_decoder_stack::{DecoderStack, StackError};
use thiserror::Error;

/// Schema version of the speculative-decoding surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong during speculative decoding.
#[derive(Debug, Error, PartialEq)]
pub enum SpeculativeError {
    /// The draft length was zero.
    #[error("draft_len must be >= 1")]
    ZeroDraftLen,
    /// The prompt was empty.
    #[error("prompt must contain at least one token")]
    EmptyPrompt,
    /// Draft and target disagreed on vocabulary size.
    #[error("vocab mismatch: draft {draft}, target {target}")]
    VocabMismatch {
        /// Draft vocab.
        draft: usize,
        /// Target vocab.
        target: usize,
    },
    /// A model forward error.
    #[error("model: {0}")]
    Model(#[from] StackError),
}

/// The outcome of a speculative decode.
#[derive(Debug, Clone, PartialEq)]
pub struct SpecResult {
    /// The generated tokens (identical to greedy target decoding).
    pub tokens: Vec<usize>,
    /// Total draft tokens proposed across all rounds.
    pub proposed: usize,
    /// Of those, how many were accepted (matched the target).
    pub accepted: usize,
    /// Number of verification rounds run.
    pub rounds: usize,
}

impl SpecResult {
    /// Fraction of proposed tokens that were accepted (`0.0` if none proposed).
    pub fn acceptance_rate(&self) -> f64 {
        if self.proposed == 0 {
            0.0
        } else {
            self.accepted as f64 / self.proposed as f64
        }
    }
}

/// A speculative decoder.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Speculative {
    /// Tokens the draft proposes per round.
    pub draft_len: usize,
    /// Maximum tokens to generate.
    pub max_new: usize,
}

impl Speculative {
    /// A speculative decoder with the given draft length and output budget.
    pub fn new(draft_len: usize, max_new: usize) -> Self {
        Self { draft_len, max_new }
    }

    /// Decode greedily-but-speculatively. The result equals greedy decoding of
    /// `target` alone; `draft` only affects the acceptance rate. Both base
    /// models are cloned and left untouched.
    pub fn decode(
        &self,
        draft: &DecoderStack,
        target: &DecoderStack,
        prompt: &[usize],
    ) -> Result<SpecResult, SpeculativeError> {
        if self.draft_len == 0 {
            return Err(SpeculativeError::ZeroDraftLen);
        }
        if prompt.is_empty() {
            return Err(SpeculativeError::EmptyPrompt);
        }
        if draft.vocab() != target.vocab() {
            return Err(SpeculativeError::VocabMismatch {
                draft: draft.vocab(),
                target: target.vocab(),
            });
        }

        let mut draft = draft.clone();
        let mut target = target.clone();
        let mut draft_logits = prime(&mut draft, prompt)?;
        let mut target_logits = prime(&mut target, prompt)?;

        let mut out = Vec::new();
        let mut proposed = 0usize;
        let mut accepted = 0usize;
        let mut rounds = 0usize;

        while out.len() < self.max_new {
            rounds += 1;

            // 1. draft proposes `draft_len` tokens on a throwaway fork.
            let mut ds = draft.clone();
            let mut dlog = draft_logits.clone();
            let mut proposals = Vec::with_capacity(self.draft_len);
            for _ in 0..self.draft_len {
                let t = argmax(&dlog);
                proposals.push(t);
                dlog = ds.forward(t)?;
            }
            proposed += proposals.len();

            // 2. target verifies; accept while it matches the target's argmax.
            let mut emitted = Vec::new();
            let mut tlog = target_logits;
            let mut all_accepted = true;
            for &q in &proposals {
                let a = argmax(&tlog);
                if a == q {
                    accepted += 1;
                    emitted.push(q);
                    tlog = target.forward(q)?;
                } else {
                    emitted.push(a); // corrected token (still the target's argmax)
                    tlog = target.forward(a)?;
                    all_accepted = false;
                    break;
                }
            }
            // 3. if every proposal matched, the target contributes one bonus token.
            if all_accepted {
                let bonus = argmax(&tlog);
                emitted.push(bonus);
                tlog = target.forward(bonus)?;
            }
            target_logits = tlog;

            // 4. advance the draft over exactly the committed tokens.
            for &e in &emitted {
                draft_logits = draft.forward(e)?;
            }
            out.extend_from_slice(&emitted);
        }

        out.truncate(self.max_new);
        Ok(SpecResult {
            tokens: out,
            proposed,
            accepted,
            rounds,
        })
    }
}

/// Feed a prompt into `model`, returning the logits for the next token.
fn prime(model: &mut DecoderStack, prompt: &[usize]) -> Result<Vec<f32>, SpeculativeError> {
    let mut logits = Vec::new();
    for &t in prompt {
        logits = model.forward(t)?;
    }
    Ok(logits)
}

/// Index of the largest logit (ties → lower index).
fn argmax(logits: &[f32]) -> usize {
    let mut best = 0;
    for i in 1..logits.len() {
        if logits[i] > logits[best] {
            best = i;
        }
    }
    best
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_decoder_stack::StackConfig;
    use sovereign_ffn::SwiGlu;
    use sovereign_rmsnorm::RmsNorm;
    use sovereign_sampler::Sampler;
    use sovereign_transformer_block::BlockWeights;

    const MD: usize = 4;

    fn mat(s: f32, n: usize) -> Vec<f32> {
        (0..n).map(|i| ((i as f32 + s) * 0.023).sin()).collect()
    }

    fn model(vocab: usize, seed: f32) -> DecoderStack {
        let block = BlockWeights {
            model_dim: MD,
            head_dim: MD,
            attn_norm: RmsNorm::new(MD),
            ffn_norm: RmsNorm::new(MD),
            w_q: mat(seed + 1.0, MD * MD),
            w_k: mat(seed + 2.0, MD * MD),
            w_v: mat(seed + 3.0, MD * MD),
            w_o: mat(seed + 4.0, MD * MD),
            ffn: SwiGlu::new(
                MD,
                MD,
                mat(seed + 5.0, MD * MD),
                mat(seed + 6.0, MD * MD),
                mat(seed + 7.0, MD * MD),
            )
            .unwrap(),
        };
        let cfg = StackConfig {
            vocab,
            model_dim: MD,
            embedding: mat(seed + 0.5, vocab * MD),
            blocks: vec![block],
            final_norm: RmsNorm::new(MD),
            head: mat(seed + 0.9, vocab * MD),
            sampler: Sampler::greedy(),
            recent_window: 64,
        };
        DecoderStack::new(cfg).unwrap()
    }

    /// Pure greedy decode of the target, for the lossless comparison.
    fn greedy(mut m: DecoderStack, prompt: &[usize], steps: usize) -> Vec<usize> {
        let mut logits = Vec::new();
        for &t in prompt {
            logits = m.forward(t).unwrap();
        }
        let mut out = Vec::new();
        for _ in 0..steps {
            let t = argmax(&logits);
            out.push(t);
            logits = m.forward(t).unwrap();
        }
        out
    }

    #[test]
    fn output_is_lossless_vs_greedy_target_with_a_different_draft() {
        let target = model(8, 0.0);
        let draft = model(8, 50.0); // a *different* (worse) draft
        let spec = Speculative::new(4, 10)
            .decode(&draft, &target, &[1, 2])
            .unwrap();
        let g = greedy(target.clone(), &[1, 2], 10);
        assert_eq!(spec.tokens, g, "speculative must equal greedy target");
    }

    #[test]
    fn lossless_even_for_several_draft_lengths() {
        let target = model(10, 0.0);
        let draft = model(10, 13.0);
        let g = greedy(target.clone(), &[3, 1, 4], 12);
        for k in [1usize, 2, 3, 5, 8] {
            let spec = Speculative::new(k, 12)
                .decode(&draft, &target, &[3, 1, 4])
                .unwrap();
            assert_eq!(spec.tokens, g, "draft_len {k}");
        }
    }

    #[test]
    fn identical_draft_accepts_everything() {
        // draft == target → every proposal matches → 100% acceptance.
        let target = model(8, 0.0);
        let draft = model(8, 0.0);
        let spec = Speculative::new(4, 12)
            .decode(&draft, &target, &[1, 2])
            .unwrap();
        assert_eq!(spec.accepted, spec.proposed);
        assert!((spec.acceptance_rate() - 1.0).abs() < 1e-9);
    }

    #[test]
    fn returns_exactly_max_new_tokens() {
        let target = model(8, 0.0);
        let draft = model(8, 7.0);
        let spec = Speculative::new(3, 9)
            .decode(&draft, &target, &[1])
            .unwrap();
        assert_eq!(spec.tokens.len(), 9);
        assert!(spec.rounds >= 1);
        assert!(spec.accepted <= spec.proposed);
    }

    #[test]
    fn base_models_are_untouched() {
        let target = model(8, 0.0);
        let draft = model(8, 7.0);
        let _ = Speculative::new(3, 6)
            .decode(&draft, &target, &[1])
            .unwrap();
        assert_eq!(target.position(), 0);
        assert_eq!(draft.position(), 0);
    }

    #[test]
    fn vocab_mismatch_zero_draft_empty_prompt_are_errors() {
        let target = model(8, 0.0);
        let draft = model(8, 7.0);
        assert_eq!(
            Speculative::new(0, 4)
                .decode(&draft, &target, &[1])
                .unwrap_err(),
            SpeculativeError::ZeroDraftLen
        );
        assert_eq!(
            Speculative::new(2, 4)
                .decode(&draft, &target, &[])
                .unwrap_err(),
            SpeculativeError::EmptyPrompt
        );
        let small = model(5, 0.0);
        assert_eq!(
            Speculative::new(2, 4)
                .decode(&small, &target, &[1])
                .unwrap_err(),
            SpeculativeError::VocabMismatch {
                draft: 5,
                target: 8
            }
        );
    }
}
