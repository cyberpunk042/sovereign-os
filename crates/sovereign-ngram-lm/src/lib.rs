//! `sovereign-ngram-lm` — a trained statistical n-gram language model.
//!
//! Before reaching for a neural model, a lot of jobs only need a *cheap* sense of
//! "how likely is this token sequence": a draft proposal for speculative
//! decoding, a perplexity baseline, an out-of-distribution flag on a retrieved
//! document. An n-gram model gives exactly that. It counts, over a training
//! corpus of token ids, how often each token follows each context of the previous
//! `order − 1` tokens, then turns those counts into a probability distribution.
//!
//! Two well-known pieces make the raw counts usable. **Add-k (Lidstone)
//! smoothing** adds a pseudo-count `k` to every token so an unseen continuation
//! gets a small non-zero probability instead of zero — without it a single unseen
//! token sends perplexity to infinity. **Backoff** handles a context that was
//! never seen at all: the model drops the oldest context token and tries the
//! shorter context, recursively, down to the context-free unigram distribution.
//! Unknown tokens (ids never seen in training) are folded into a reserved
//! [`UNK`] symbol so the distribution always sums to one over the known
//! vocabulary plus `UNK`.
//!
//! [`NgramModel::prob`] is that distribution; [`NgramModel::log_prob`] its log;
//! [`NgramModel::perplexity`] the geometric-mean branching factor of a sequence
//! (lower = the model finds it more predictable); [`NgramModel::predict_next`]
//! the most likely continuation of a context.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use thiserror::Error;

/// Schema version of the n-gram LM surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Reserved token id standing in for any token never seen in training.
pub const UNK: u32 = u32::MAX;

/// Errors constructing or using the model.
#[derive(Debug, Clone, PartialEq, Error)]
pub enum NgramError {
    /// `order` must be at least 1.
    #[error("order must be >= 1, got {0}")]
    InvalidOrder(usize),
    /// `k` must be finite and strictly positive (add-k needs a real pseudo-count).
    #[error("smoothing k must be finite and > 0, got {0}")]
    InvalidK(f64),
}

/// A trained n-gram model over `u32` token ids.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NgramModel {
    order: usize,
    k: f64,
    /// context key (see [`Self::key`]) → (next token → count).
    ctx_next: HashMap<String, HashMap<u32, u64>>,
    /// context key → total continuations counted (sum of the inner map).
    ctx_total: HashMap<String, u64>,
    /// Distinct training tokens; `UNK` is always a member so OOV has mass.
    vocab: HashSet<u32>,
}

impl NgramModel {
    /// An empty model of the given `order` (e.g. 3 for a trigram model) and
    /// add-k smoothing constant `k` (e.g. `1.0` for Laplace, `0.01` for a lighter
    /// touch).
    pub fn new(order: usize, k: f64) -> Result<Self, NgramError> {
        if order < 1 {
            return Err(NgramError::InvalidOrder(order));
        }
        if !k.is_finite() || k <= 0.0 {
            return Err(NgramError::InvalidK(k));
        }
        let mut vocab = HashSet::new();
        vocab.insert(UNK);
        Ok(Self {
            order,
            k,
            ctx_next: HashMap::new(),
            ctx_total: HashMap::new(),
            vocab,
        })
    }

    /// The model order `n`.
    pub fn order(&self) -> usize {
        self.order
    }

    /// The vocabulary size, including the reserved [`UNK`].
    pub fn vocab_size(&self) -> usize {
        self.vocab.len()
    }

    /// Encode a context slice as a string map key (`,`-joined ids). Distinct
    /// contexts always produce distinct keys; the empty context is `""`.
    fn key(ctx: &[u32]) -> String {
        let mut s = String::new();
        for (i, t) in ctx.iter().enumerate() {
            if i > 0 {
                s.push(',');
            }
            s.push_str(&t.to_string());
        }
        s
    }

    /// Map an arbitrary token id to its in-vocabulary form (`UNK` if unseen).
    fn canon(&self, token: u32) -> u32 {
        if self.vocab.contains(&token) {
            token
        } else {
            UNK
        }
    }

    /// Train on one token sequence. Every n-gram of order `1..=order` is counted,
    /// so all backoff levels are populated from the same pass. Call repeatedly to
    /// accumulate over a corpus.
    pub fn train(&mut self, tokens: &[u32]) {
        for &t in tokens {
            self.vocab.insert(t);
        }
        for (i, &next) in tokens.iter().enumerate() {
            // For position i, count this token under every context length
            // 0..=order-1 that fits before it.
            let max_ctx = (self.order - 1).min(i);
            for clen in 0..=max_ctx {
                let key = Self::key(&tokens[i - clen..i]);
                *self
                    .ctx_next
                    .entry(key.clone())
                    .or_default()
                    .entry(next)
                    .or_insert(0) += 1;
                *self.ctx_total.entry(key).or_insert(0) += 1;
            }
        }
    }

    /// The add-k probability of `token` directly under exactly `ctx` (no
    /// backoff). Returns `None` if `ctx` was never seen. `token` and `ctx` are
    /// assumed already canonicalised.
    fn prob_at(&self, ctx: &[u32], token: u32) -> Option<f64> {
        let key = Self::key(ctx);
        let total = *self.ctx_total.get(&key)?;
        let count = self
            .ctx_next
            .get(&key)
            .and_then(|m| m.get(&token))
            .copied()
            .unwrap_or(0);
        let v = self.vocab.len() as f64;
        Some((count as f64 + self.k) / (total as f64 + self.k * v))
    }

    /// Probability of `token` given the preceding `context`, with add-k smoothing
    /// and backoff to shorter contexts when the full context was never seen.
    ///
    /// Only the last `order − 1` tokens of `context` are used. The result is a
    /// valid probability in `(0, 1]` and, summed over the known vocabulary plus
    /// [`UNK`], totals 1 for any fixed backed-off context.
    pub fn prob(&self, context: &[u32], token: u32) -> f64 {
        let token = self.canon(token);
        // Use at most order-1 trailing context tokens, canonicalised.
        let take = (self.order - 1).min(context.len());
        let mut ctx: Vec<u32> = context[context.len() - take..]
            .iter()
            .map(|&t| self.canon(t))
            .collect();
        loop {
            if let Some(p) = self.prob_at(&ctx, token) {
                return p;
            }
            if ctx.is_empty() {
                // No data at all (untrained model): uniform over {UNK}.
                let v = self.vocab.len() as f64;
                return 1.0 / v;
            }
            ctx.remove(0); // drop oldest context token and back off
        }
    }

    /// Natural log of [`prob`](Self::prob).
    pub fn log_prob(&self, context: &[u32], token: u32) -> f64 {
        self.prob(context, token).ln()
    }

    /// The full next-token distribution over the known vocabulary (including
    /// [`UNK`]) given `context`, as `(token, probability)` pairs sorted by
    /// descending probability then ascending token id. The probabilities sum to
    /// ~1.
    pub fn distribution(&self, context: &[u32]) -> Vec<(u32, f64)> {
        let mut dist: Vec<(u32, f64)> = self
            .vocab
            .iter()
            .map(|&t| (t, self.prob(context, t)))
            .collect();
        dist.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
        dist
    }

    /// The most probable next token given `context` (ties broken by smaller id),
    /// or `None` if the model is untrained.
    pub fn predict_next(&self, context: &[u32]) -> Option<u32> {
        if self.ctx_total.is_empty() {
            return None;
        }
        self.distribution(context).first().map(|&(t, _)| t)
    }

    /// Perplexity of `tokens`: `exp(-1/N · Σ log p(t_i | preceding))`, the
    /// geometric-mean branching factor. Lower means the model finds the sequence
    /// more predictable. Returns `None` for an empty sequence.
    pub fn perplexity(&self, tokens: &[u32]) -> Option<f64> {
        if tokens.is_empty() {
            return None;
        }
        let mut sum_log = 0.0;
        for i in 0..tokens.len() {
            let ctx = &tokens[..i];
            sum_log += self.log_prob(ctx, tokens[i]);
        }
        Some((-sum_log / tokens.len() as f64).exp())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_bad_parameters() {
        assert_eq!(NgramModel::new(0, 1.0), Err(NgramError::InvalidOrder(0)));
        assert!(matches!(
            NgramModel::new(2, 0.0),
            Err(NgramError::InvalidK(_))
        ));
        assert!(matches!(
            NgramModel::new(2, f64::NAN),
            Err(NgramError::InvalidK(_))
        ));
    }

    #[test]
    fn distribution_sums_to_one() {
        let mut m = NgramModel::new(3, 0.5).unwrap();
        m.train(&[1, 2, 3, 1, 2, 4, 1, 2, 3]);
        let total: f64 = m.distribution(&[1, 2]).iter().map(|&(_, p)| p).sum();
        assert!((total - 1.0).abs() < 1e-9, "sum was {total}");
        // also after backoff to a context that was never seen
        let total2: f64 = m.distribution(&[99, 98]).iter().map(|&(_, p)| p).sum();
        assert!((total2 - 1.0).abs() < 1e-9, "backoff sum was {total2}");
    }

    #[test]
    fn learns_a_deterministic_continuation() {
        // "1 2" is always followed by 3 in training → 3 should be most likely
        let mut m = NgramModel::new(3, 0.01).unwrap();
        m.train(&[1, 2, 3, 5, 1, 2, 3, 6, 1, 2, 3]);
        assert_eq!(m.predict_next(&[1, 2]), Some(3));
        assert!(m.prob(&[1, 2], 3) > m.prob(&[1, 2], 6));
    }

    #[test]
    fn backoff_uses_shorter_context_when_unseen() {
        let mut m = NgramModel::new(3, 0.1).unwrap();
        // bigram "2 -> 3" is frequent; trigram context "7 2" never seen
        m.train(&[2, 3, 2, 3, 2, 3, 4, 5]);
        // predicting after [7, 2]: full context "7 2" unseen → back off to "2"
        // where 3 dominates.
        assert_eq!(m.predict_next(&[7, 2]), Some(3));
    }

    #[test]
    fn unknown_tokens_fold_into_unk() {
        let mut m = NgramModel::new(2, 1.0).unwrap();
        m.train(&[1, 2, 3]);
        // token 999 was never seen → treated as UNK, still gets positive prob
        assert!(m.prob(&[1], 999) > 0.0);
        // and prob(.,999) equals prob(.,UNK) since 999 canonicalises to UNK
        assert_eq!(m.prob(&[1], 999), m.prob(&[1], UNK));
    }

    #[test]
    fn perplexity_is_lower_on_trained_than_random_text() {
        // train on a repetitive pattern, then compare perplexity of an in-pattern
        // sequence vs a scrambled one.
        let mut m = NgramModel::new(3, 0.05).unwrap();
        let pattern: Vec<u32> = (0..60).map(|i| (i % 4) as u32).collect(); // 0 1 2 3 0 1 2 3...
        m.train(&pattern);
        let in_pattern = m.perplexity(&[0, 1, 2, 3, 0, 1, 2, 3]).unwrap();
        let scrambled = m.perplexity(&[3, 1, 3, 0, 2, 2, 1, 0]).unwrap();
        assert!(
            in_pattern < scrambled,
            "in-pattern {in_pattern} should beat scrambled {scrambled}"
        );
        // a perfectly predictable continuation should have low perplexity
        assert!(in_pattern < 2.0, "in-pattern perplexity {in_pattern}");
    }

    #[test]
    fn perplexity_of_empty_is_none() {
        let m = NgramModel::new(2, 1.0).unwrap();
        assert_eq!(m.perplexity(&[]), None);
    }

    #[test]
    fn untrained_model_is_uniform_and_unpredictable() {
        let m = NgramModel::new(2, 1.0).unwrap();
        // only UNK in vocab → prob 1 over {UNK}
        assert_eq!(m.predict_next(&[1, 2]), None);
        assert!((m.prob(&[1], 5) - 1.0).abs() < 1e-9); // 1/|{UNK}|
    }

    #[test]
    fn log_prob_matches_prob() {
        let mut m = NgramModel::new(2, 0.3).unwrap();
        m.train(&[1, 2, 1, 3, 1, 2]);
        let p = m.prob(&[1], 2);
        assert!((m.log_prob(&[1], 2) - p.ln()).abs() < 1e-12);
    }

    #[test]
    fn serde_round_trip() {
        let mut m = NgramModel::new(3, 0.5).unwrap();
        m.train(&[1, 2, 3, 4, 1, 2, 3]);
        let j = serde_json::to_string(&m).unwrap();
        let back: NgramModel = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
        assert_eq!(back.predict_next(&[1, 2]), m.predict_next(&[1, 2]));
    }

    #[test]
    fn higher_order_captures_longer_dependencies() {
        // sequence where the token depends on TWO back, not one
        // pattern: a X b  a Y b  ... bigram of "a" is ambiguous, but unigram-free
        // here we just confirm a trigram model trains without panic and predicts.
        let mut m = NgramModel::new(3, 0.01).unwrap();
        m.train(&[10, 11, 12, 10, 11, 12, 10, 11, 12]);
        assert_eq!(m.predict_next(&[10, 11]), Some(12));
        assert_eq!(m.order(), 3);
    }
}
