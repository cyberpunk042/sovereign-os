//! `sovereign-beam-search` — deterministic search-based decoding.
//!
//! The sampler draws stochastically; beam search instead *searches* for the
//! highest-probability continuation. It keeps the `beam_width` best partial
//! hypotheses ranked by cumulative log-probability, and at each step expands
//! every beam by its most likely next tokens, keeping the global top
//! `beam_width` survivors — then returns the best complete sequence.
//!
//! Extending a beam means advancing *that beam's* KV cache by one token, so
//! each beam needs its own decoder state. This is exactly why it composes with
//! [`sovereign-decoder-stack`]: its model is `Clone`, so a beam forks by
//! cloning the model. Two properties are pinned: with `beam_width == 1` the
//! result is greedy (argmax each step), and with a wider beam the returned
//! sequence's cumulative log-prob is never worse than greedy's.
//!
//! [`sovereign-decoder-stack`]: https://docs.rs/sovereign-decoder-stack
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_decoder_stack::{DecoderStack, StackError};
use thiserror::Error;

/// Schema version of the beam-search surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong during a beam search.
#[derive(Debug, Error, PartialEq)]
pub enum BeamError {
    /// The beam width was zero.
    #[error("beam_width must be >= 1")]
    ZeroBeam,
    /// The prompt was empty.
    #[error("prompt must contain at least one token")]
    EmptyPrompt,
    /// A model forward error.
    #[error("model: {0}")]
    Model(#[from] StackError),
}

/// The result of a beam search.
#[derive(Debug, Clone, PartialEq)]
pub struct BeamResult {
    /// The highest-scoring generated token sequence (excludes the prompt).
    pub tokens: Vec<usize>,
    /// Its cumulative log-probability (sum of per-step log-probs).
    pub score: f64,
}

/// A beam-search decoder configuration.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct BeamSearch {
    /// Number of hypotheses kept at each step.
    pub beam_width: usize,
    /// Maximum tokens to generate.
    pub max_new: usize,
}

struct Beam {
    model: DecoderStack,
    tokens: Vec<usize>,
    score: f64,
    logits: Vec<f32>,
}

impl BeamSearch {
    /// A beam search with the given width and generation length.
    pub fn new(beam_width: usize, max_new: usize) -> Self {
        Self {
            beam_width,
            max_new,
        }
    }

    /// Search from `base` (the model is cloned; `base` is left untouched) over
    /// `prompt`, returning the best generated sequence.
    pub fn search(&self, base: &DecoderStack, prompt: &[usize]) -> Result<BeamResult, BeamError> {
        if self.beam_width == 0 {
            return Err(BeamError::ZeroBeam);
        }
        if prompt.is_empty() {
            return Err(BeamError::EmptyPrompt);
        }

        // Prime a fresh model on the prompt; its last logits seed all beams.
        let mut primed = base.clone();
        let mut logits = Vec::new();
        for &t in prompt {
            logits = primed.forward(t)?;
        }

        let mut beams = vec![Beam {
            model: primed,
            tokens: Vec::new(),
            score: 0.0,
            logits,
        }];

        for _ in 0..self.max_new {
            // (beam index, token, extended score), gathered across all beams.
            let mut candidates: Vec<(usize, usize, f64)> = Vec::new();
            for (bi, beam) in beams.iter().enumerate() {
                let logprobs = log_softmax(&beam.logits);
                for &t in &top_indices(&logprobs, self.beam_width) {
                    candidates.push((bi, t, beam.score + logprobs[t] as f64));
                }
            }
            // keep the global top `beam_width` by score
            candidates.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal));
            candidates.truncate(self.beam_width);

            // materialize the surviving beams (fork each parent's KV state)
            let mut next = Vec::with_capacity(candidates.len());
            for (bi, t, score) in candidates {
                let mut model = beams[bi].model.clone();
                let new_logits = model.forward(t)?;
                let mut tokens = beams[bi].tokens.clone();
                tokens.push(t);
                next.push(Beam {
                    model,
                    tokens,
                    score,
                    logits: new_logits,
                });
            }
            beams = next;
        }

        // beams are score-sorted (candidates were); the best is first.
        let best = beams
            .into_iter()
            .max_by(|a, b| {
                a.score
                    .partial_cmp(&b.score)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .expect("at least one beam");
        Ok(BeamResult {
            tokens: best.tokens,
            score: best.score,
        })
    }
}

/// Numerically-stable log-softmax.
fn log_softmax(logits: &[f32]) -> Vec<f32> {
    let max = logits.iter().copied().fold(f32::NEG_INFINITY, f32::max);
    let sum_exp: f32 = logits.iter().map(|l| (l - max).exp()).sum();
    let log_sum = max + sum_exp.ln();
    logits.iter().map(|l| l - log_sum).collect()
}

/// Indices of the `k` largest values, highest first (ties by lower index).
fn top_indices(values: &[f32], k: usize) -> Vec<usize> {
    let mut idx: Vec<usize> = (0..values.len()).collect();
    idx.sort_by(|&a, &b| {
        values[b]
            .partial_cmp(&values[a])
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    idx.truncate(k.min(values.len()));
    idx
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
        (0..n).map(|i| ((i as f32 + s) * 0.021).sin()).collect()
    }

    fn model(vocab: usize) -> DecoderStack {
        let block = BlockWeights {
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
        };
        let cfg = StackConfig {
            vocab,
            model_dim: MD,
            embedding: mat(0.5, vocab * MD),
            blocks: vec![block],
            final_norm: RmsNorm::new(MD),
            head: mat(0.9, vocab * MD),
            sampler: Sampler::greedy(), // unused by beam search
            recent_window: 64,
        };
        DecoderStack::new(cfg).unwrap()
    }

    /// Greedy reference: argmax each step, advancing one model.
    fn greedy(mut m: DecoderStack, prompt: &[usize], steps: usize) -> (Vec<usize>, f64) {
        let mut logits = Vec::new();
        for &t in prompt {
            logits = m.forward(t).unwrap();
        }
        let mut toks = Vec::new();
        let mut score = 0.0f64;
        for _ in 0..steps {
            let lp = log_softmax(&logits);
            let t = top_indices(&lp, 1)[0];
            score += lp[t] as f64;
            toks.push(t);
            logits = m.forward(t).unwrap();
        }
        (toks, score)
    }

    #[test]
    fn beam_width_one_equals_greedy() {
        let m = model(8);
        let bs = BeamSearch::new(1, 6);
        let res = bs.search(&m, &[1, 2]).unwrap();
        let (gtoks, gscore) = greedy(m.clone(), &[1, 2], 6);
        assert_eq!(res.tokens, gtoks);
        assert!((res.score - gscore).abs() < 1e-5);
    }

    #[test]
    fn wider_beam_is_never_worse_than_greedy() {
        let m = model(10);
        let (_g, gscore) = greedy(m.clone(), &[3, 1], 8);
        let res = BeamSearch::new(4, 8).search(&m, &[3, 1]).unwrap();
        // beam search maximizes cumulative log-prob → >= greedy
        assert!(
            res.score >= gscore - 1e-6,
            "beam {} < greedy {}",
            res.score,
            gscore
        );
    }

    #[test]
    fn returns_requested_length_in_range() {
        let m = model(8);
        let res = BeamSearch::new(3, 5).search(&m, &[1]).unwrap();
        assert_eq!(res.tokens.len(), 5);
        assert!(res.tokens.iter().all(|&t| t < 8));
    }

    #[test]
    fn is_deterministic() {
        let m = model(8);
        let a = BeamSearch::new(3, 6).search(&m, &[2, 4]).unwrap();
        let b = BeamSearch::new(3, 6).search(&m, &[2, 4]).unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn base_model_is_left_untouched() {
        let m = model(8);
        let _ = BeamSearch::new(2, 4).search(&m, &[1]).unwrap();
        // base never advanced (search clones it)
        assert_eq!(m.position(), 0);
    }

    #[test]
    fn zero_beam_and_empty_prompt_are_errors() {
        let m = model(8);
        assert_eq!(
            BeamSearch::new(0, 4).search(&m, &[1]).unwrap_err(),
            BeamError::ZeroBeam
        );
        assert_eq!(
            BeamSearch::new(2, 4).search(&m, &[]).unwrap_err(),
            BeamError::EmptyPrompt
        );
    }
}
