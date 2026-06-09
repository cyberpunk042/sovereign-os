//! `sovereign-perplexity` — language-model evaluation by perplexity.
//!
//! Generation shows what a model *says*; perplexity measures how well it
//! *predicts*. Given a reference token sequence, this crate runs the model
//! teacher-forced — at each position it reads the model's distribution for the
//! next token and records the log-probability the model assigned to the token
//! that actually came next — then reports:
//!
//! * **cross-entropy** = mean negative log-probability per predicted token, and
//! * **perplexity** = `exp(cross_entropy)`, the effective branching factor.
//!
//! Perplexity is the standard intrinsic LM metric: lower is better, and it is
//! bounded below by 1.0. It is what you use to compare two models, or to check
//! how much a quantization level costs in predictive quality. The model is
//! scored on a clone, so the caller's model state is untouched. A model that
//! is perfectly uniform over a vocabulary of size `V` scores exactly `V` —
//! pinned as a test.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_decoder_stack::{DecoderStack, StackError};
use sovereign_quant_model::QuantModel;
use thiserror::Error;

/// Schema version of the perplexity surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong evaluating perplexity.
#[derive(Debug, Error, PartialEq)]
pub enum PerplexityError {
    /// Fewer than two tokens — nothing can be predicted.
    #[error("need at least 2 tokens to score (got {got})")]
    TooShort {
        /// Number of tokens supplied.
        got: usize,
    },
    /// A model forward error.
    #[error("model: {0}")]
    Model(#[from] StackError),
    /// A quantized-model error (it has no Clone, so it is scored in place and
    /// must be fresh).
    #[error("quant model: {0}")]
    QuantModel(String),
    /// A quantized model was not fresh (already had cached positions), so an
    /// in-place teacher-forced evaluation would be contaminated.
    #[error("quant model must be fresh (position 0), had {position}")]
    NotFresh {
        /// The model's current decode position.
        position: usize,
    },
}

/// The result of a perplexity evaluation.
#[derive(Debug, Clone, PartialEq)]
pub struct Eval {
    /// Number of tokens whose probability was scored (`tokens.len() - 1`).
    pub predicted: usize,
    /// Sum of log-probabilities the model assigned to the true next tokens.
    pub total_logprob: f64,
    /// Mean negative log-probability per predicted token (cross-entropy, nats).
    pub cross_entropy: f64,
    /// `exp(cross_entropy)` — the perplexity (≥ 1.0).
    pub perplexity: f64,
}

/// Score `model`'s perplexity on `tokens` (teacher-forced). The model is
/// cloned, so the caller's instance is not advanced.
pub fn evaluate(model: &DecoderStack, tokens: &[usize]) -> Result<Eval, PerplexityError> {
    if tokens.len() < 2 {
        return Err(PerplexityError::TooShort { got: tokens.len() });
    }
    let mut m = model.clone();
    let mut total_logprob = 0.0f64;

    // Feed token 0, then for each subsequent token read its assigned log-prob.
    let mut logits = m.forward(tokens[0])?;
    for &next in &tokens[1..] {
        let lp = log_softmax(&logits);
        total_logprob += lp[next] as f64;
        logits = m.forward(next)?;
    }

    let predicted = tokens.len() - 1;
    let cross_entropy = -total_logprob / predicted as f64;
    Ok(Eval {
        predicted,
        total_logprob,
        cross_entropy,
        perplexity: cross_entropy.exp(),
    })
}

/// Score a mixed-precision [`QuantModel`]'s perplexity on `tokens`. The model
/// has no `Clone`, so it is scored *in place* and must be **fresh** (decode
/// position 0); it is left advanced afterward. Build a new model to re-score.
///
/// This is what lets a runtime measure the predictive cost of quantization:
/// score an f32 model and its ternary/NVFP4 counterpart on the same text and
/// compare perplexities.
pub fn evaluate_quant(model: &mut QuantModel, tokens: &[usize]) -> Result<Eval, PerplexityError> {
    if tokens.len() < 2 {
        return Err(PerplexityError::TooShort { got: tokens.len() });
    }
    if model.position() != 0 {
        return Err(PerplexityError::NotFresh {
            position: model.position(),
        });
    }
    let mut total_logprob = 0.0f64;
    let mut logits = model
        .forward(tokens[0])
        .map_err(|e| PerplexityError::QuantModel(e.to_string()))?;
    for &next in &tokens[1..] {
        let lp = log_softmax(&logits);
        total_logprob += lp[next] as f64;
        logits = model
            .forward(next)
            .map_err(|e| PerplexityError::QuantModel(e.to_string()))?;
    }
    let predicted = tokens.len() - 1;
    let cross_entropy = -total_logprob / predicted as f64;
    Ok(Eval {
        predicted,
        total_logprob,
        cross_entropy,
        perplexity: cross_entropy.exp(),
    })
}

/// Numerically-stable log-softmax.
fn log_softmax(logits: &[f32]) -> Vec<f32> {
    let max = logits.iter().copied().fold(f32::NEG_INFINITY, f32::max);
    let sum_exp: f32 = logits.iter().map(|l| (l - max).exp()).sum();
    let log_sum = max + sum_exp.ln();
    logits.iter().map(|l| l - log_sum).collect()
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
        (0..n).map(|i| ((i as f32 + s) * 0.019).sin()).collect()
    }

    fn block(zero: bool) -> BlockWeights {
        let m = |s: f32, n: usize| if zero { vec![0.0; n] } else { mat(s, n) };
        BlockWeights {
            model_dim: MD,
            head_dim: MD,
            attn_norm: RmsNorm::new(MD),
            ffn_norm: RmsNorm::new(MD),
            w_q: m(1.0, MD * MD),
            w_k: m(2.0, MD * MD),
            w_v: m(3.0, MD * MD),
            w_o: m(4.0, MD * MD),
            ffn: SwiGlu::new(MD, MD, m(5.0, MD * MD), m(6.0, MD * MD), m(7.0, MD * MD)).unwrap(),
        }
    }

    fn model(vocab: usize, uniform: bool) -> DecoderStack {
        // uniform: zero embedding + zero head → all logits 0 → uniform softmax.
        let cfg = StackConfig {
            vocab,
            model_dim: MD,
            embedding: if uniform {
                vec![0.0; vocab * MD]
            } else {
                mat(0.5, vocab * MD)
            },
            blocks: vec![block(uniform)],
            final_norm: RmsNorm::new(MD),
            head: if uniform {
                vec![0.0; vocab * MD]
            } else {
                mat(0.9, vocab * MD)
            },
            sampler: Sampler::greedy(),
            recent_window: 64,
        };
        DecoderStack::new(cfg).unwrap()
    }

    #[test]
    fn uniform_model_perplexity_equals_vocab() {
        let vocab = 7;
        let m = model(vocab, true);
        let ev = evaluate(&m, &[0, 1, 2, 3, 0, 1]).unwrap();
        // every distribution is uniform over `vocab` → perplexity == vocab
        assert!(
            (ev.perplexity - vocab as f64).abs() < 1e-4,
            "{}",
            ev.perplexity
        );
        // cross-entropy == ln(vocab)
        assert!((ev.cross_entropy - (vocab as f64).ln()).abs() < 1e-5);
    }

    #[test]
    fn perplexity_is_at_least_one() {
        let m = model(8, false);
        let ev = evaluate(&m, &[1, 2, 3, 4, 5]).unwrap();
        assert!(ev.perplexity >= 1.0 - 1e-9, "{}", ev.perplexity);
    }

    #[test]
    fn predicted_count_is_len_minus_one() {
        let m = model(8, false);
        let ev = evaluate(&m, &[1, 2, 3, 4]).unwrap();
        assert_eq!(ev.predicted, 3);
    }

    #[test]
    fn cross_entropy_and_perplexity_are_consistent() {
        let m = model(8, false);
        let ev = evaluate(&m, &[2, 4, 6, 1, 3]).unwrap();
        assert!((ev.perplexity - ev.cross_entropy.exp()).abs() < 1e-9);
        // total_logprob = -cross_entropy * predicted
        assert!((ev.total_logprob + ev.cross_entropy * ev.predicted as f64).abs() < 1e-6);
    }

    #[test]
    fn base_model_is_left_untouched() {
        let m = model(8, false);
        let _ = evaluate(&m, &[1, 2, 3]).unwrap();
        assert_eq!(m.position(), 0);
    }

    #[test]
    fn determinism() {
        let m = model(8, false);
        assert_eq!(
            evaluate(&m, &[1, 2, 3, 4]).unwrap(),
            evaluate(&m, &[1, 2, 3, 4]).unwrap()
        );
    }

    #[test]
    fn too_short_is_an_error() {
        let m = model(8, false);
        assert_eq!(
            evaluate(&m, &[1]).unwrap_err(),
            PerplexityError::TooShort { got: 1 }
        );
    }

    // --- quantized-model evaluation ---

    fn quant_model(vocab: usize, precision: sovereign_linear::Precision) -> QuantModel {
        use sovereign_decoder_layer::{DecoderLayer, LayerStack};
        use sovereign_quant_block::{QuantBlockWeights, QuantDecoderBlock};
        let qb = QuantDecoderBlock::from_weights(
            &QuantBlockWeights {
                model_dim: MD,
                head_dim: MD,
                hidden_dim: MD,
                attn_norm: RmsNorm::new(MD),
                ffn_norm: RmsNorm::new(MD),
                w_q: mat(1.0, MD * MD),
                w_k: mat(2.0, MD * MD),
                w_v: mat(3.0, MD * MD),
                w_o: mat(4.0, MD * MD),
                w_gate: mat(5.0, MD * MD),
                w_up: mat(6.0, MD * MD),
                w_down: mat(7.0, MD * MD),
            },
            precision,
        )
        .unwrap();
        let stack = LayerStack::new(vec![Box::new(qb) as Box<dyn DecoderLayer>]).unwrap();
        QuantModel::new(
            vocab,
            MD,
            mat(0.5, vocab * MD),
            stack,
            RmsNorm::new(MD),
            mat(0.9, vocab * MD),
            Sampler::greedy(),
        )
        .unwrap()
    }

    #[test]
    fn quant_model_perplexity_is_finite_and_at_least_one() {
        use sovereign_linear::Precision;
        let mut m = quant_model(8, Precision::Ternary);
        let ev = evaluate_quant(&mut m, &[1, 2, 3, 4, 5]).unwrap();
        assert!(ev.perplexity.is_finite() && ev.perplexity >= 1.0 - 1e-9);
        assert_eq!(ev.predicted, 4);
    }

    #[test]
    fn quant_eval_requires_a_fresh_model() {
        use sovereign_linear::Precision;
        let mut m = quant_model(8, Precision::F32);
        m.forward(0).unwrap(); // advance it
        assert_eq!(
            evaluate_quant(&mut m, &[1, 2, 3]).unwrap_err(),
            PerplexityError::NotFresh { position: 1 }
        );
    }

    #[test]
    fn measures_quantization_cost_f32_vs_ternary() {
        use sovereign_linear::Precision;
        // Same weights, two precisions → both score finite perplexities that a
        // runtime can compare to decide whether ternary is acceptable here.
        let seq = [1usize, 3, 5, 2, 4, 6, 1];
        let mut f = quant_model(8, Precision::F32);
        let mut t = quant_model(8, Precision::Ternary);
        let ef = evaluate_quant(&mut f, &seq).unwrap();
        let et = evaluate_quant(&mut t, &seq).unwrap();
        assert!(ef.perplexity >= 1.0 && et.perplexity >= 1.0);
        assert!(ef.perplexity.is_finite() && et.perplexity.is_finite());
    }
}
