//! `sovereign-attention` — the scaled-dot-product attention kernel.
//!
//! Attention is the inner loop of every transformer step, and the dump's
//! AVX++ inference plane needs it in two shapes:
//!
//! * **Prefill** — a query attends to a whole block of keys/values at once.
//! * **Decode** — a single query attends to a KV cache that *grows by one*
//!   token per step (pairs with [`sovereign-kv-cache`]).
//!
//! The naive form materializes the full score row, subtracts its max for
//! stability, softmaxes, and mixes the values. The **online-softmax**
//! (FlashAttention) form computes the *identical* result in a single
//! streaming pass — it never holds the score row, carrying instead a
//! running max `m`, a running denominator `l`, and a running output
//! accumulator, rescaling the accumulator by `exp(m_old - m_new)` whenever a
//! larger score arrives. That recurrence is what makes attention tile-able
//! and memory-bounded, and it is exactly the recurrence [`DecodeStep`] runs
//! when fed a cache one token at a time.
//!
//! The load-bearing invariant — tested here — is that the streaming result
//! equals the naive result to floating-point tolerance, and that both stay
//! finite under scores large enough to overflow a naive `exp`.
//!
//! [`sovereign-kv-cache`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-kv-cache
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the attention surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong assembling an attention call.
#[derive(Debug, Error, PartialEq)]
pub enum AttentionError {
    /// A query/key vector had the wrong length for this head.
    #[error("dimension mismatch: expected {expected}, got {got}")]
    DimMismatch {
        /// Expected length (the head dim).
        expected: usize,
        /// Observed length.
        got: usize,
    },
    /// Number of keys did not equal number of values.
    #[error("key/value count mismatch: {keys} keys vs {values} values")]
    KeyValueCountMismatch {
        /// Number of key vectors.
        keys: usize,
        /// Number of value vectors.
        values: usize,
    },
    /// Value vectors disagreed on their dimension.
    #[error("ragged values: value {index} has dim {got}, expected {expected}")]
    RaggedValues {
        /// Position of the offending value vector.
        index: usize,
        /// Dimension established by the first value.
        expected: usize,
        /// Dimension of this value.
        got: usize,
    },
    /// Attention was asked to read from an empty context.
    #[error("empty context: nothing to attend over")]
    EmptyContext,
    /// More queries than keys in a causal prefill (no causal prefix exists).
    #[error("causal prefill needs queries ({queries}) <= keys ({keys})")]
    TooManyQueries {
        /// Number of query rows.
        queries: usize,
        /// Number of key positions.
        keys: usize,
    },
}

/// A single attention head: a fixed query/key dimension and a softmax scale.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Attention {
    /// Query/key dimension this head operates on.
    pub head_dim: usize,
    /// Multiplier applied to each raw dot product before softmax.
    pub scale: f32,
}

impl Attention {
    /// A head with the canonical `1/sqrt(head_dim)` scale.
    ///
    /// # Panics
    /// Panics if `head_dim == 0` — a zero-width head is never meaningful.
    pub fn new(head_dim: usize) -> Self {
        assert!(head_dim > 0, "head_dim must be > 0");
        Self {
            head_dim,
            scale: 1.0 / (head_dim as f32).sqrt(),
        }
    }

    /// A head with an explicit softmax scale (e.g. for ALiBi-style tweaks).
    ///
    /// # Panics
    /// Panics if `head_dim == 0`.
    pub fn with_scale(head_dim: usize, scale: f32) -> Self {
        assert!(head_dim > 0, "head_dim must be > 0");
        Self { head_dim, scale }
    }

    fn check_vec(&self, v: &[f32]) -> Result<(), AttentionError> {
        if v.len() != self.head_dim {
            return Err(AttentionError::DimMismatch {
                expected: self.head_dim,
                got: v.len(),
            });
        }
        Ok(())
    }

    /// Validate that `keys`/`values` form a usable context and return the
    /// common value dimension.
    fn check_context(
        &self,
        q: &[f32],
        keys: &[Vec<f32>],
        values: &[Vec<f32>],
    ) -> Result<usize, AttentionError> {
        self.check_vec(q)?;
        if keys.len() != values.len() {
            return Err(AttentionError::KeyValueCountMismatch {
                keys: keys.len(),
                values: values.len(),
            });
        }
        if keys.is_empty() {
            return Err(AttentionError::EmptyContext);
        }
        for k in keys {
            self.check_vec(k)?;
        }
        let value_dim = values[0].len();
        for (index, v) in values.iter().enumerate() {
            if v.len() != value_dim {
                return Err(AttentionError::RaggedValues {
                    index,
                    expected: value_dim,
                    got: v.len(),
                });
            }
        }
        Ok(value_dim)
    }

    /// The softmax attention weights for one query over `keys`
    /// (max-subtracted for numerical stability). Sums to 1.
    pub fn weights(&self, q: &[f32], keys: &[Vec<f32>]) -> Result<Vec<f32>, AttentionError> {
        self.check_vec(q)?;
        if keys.is_empty() {
            return Err(AttentionError::EmptyContext);
        }
        for k in keys {
            self.check_vec(k)?;
        }
        let scores: Vec<f32> = keys.iter().map(|k| self.scale * dot(q, k)).collect();
        Ok(softmax(&scores))
    }

    /// The softmax attention weights with a learned **attention sink** — a
    /// virtual logit that joins the softmax denominator but has no value vector,
    /// so it absorbs probability mass the query would rather send "nowhere".
    /// The returned weights are the real-position weights and therefore sum to
    /// `1 − sink_share ≤ 1` (the deficit is the mass the sink took). This is the
    /// GPT-OSS / StreamingLLM per-head sink. `sink = f32::NEG_INFINITY` recovers
    /// the plain [`weights`](Self::weights) exactly.
    pub fn weights_with_sink(
        &self,
        q: &[f32],
        keys: &[Vec<f32>],
        sink: f32,
    ) -> Result<Vec<f32>, AttentionError> {
        self.check_vec(q)?;
        if keys.is_empty() {
            return Err(AttentionError::EmptyContext);
        }
        for k in keys {
            self.check_vec(k)?;
        }
        let scores: Vec<f32> = keys.iter().map(|k| self.scale * dot(q, k)).collect();
        // max over the scores AND the sink logit, for numerical stability.
        let max = scores
            .iter()
            .copied()
            .fold(f32::NEG_INFINITY, f32::max)
            .max(sink);
        let exps: Vec<f32> = scores.iter().map(|s| (s - max).exp()).collect();
        let denom: f32 = exps.iter().sum::<f32>() + (sink - max).exp();
        Ok(exps.iter().map(|e| e / denom).collect())
    }

    /// Naive full attention: `softmax(scale · q·Kᵀ) · V`.
    ///
    /// Materializes the score row, subtracts its max, softmaxes, then mixes
    /// the values. Returns a vector of length `value_dim`.
    pub fn attend(
        &self,
        q: &[f32],
        keys: &[Vec<f32>],
        values: &[Vec<f32>],
    ) -> Result<Vec<f32>, AttentionError> {
        let value_dim = self.check_context(q, keys, values)?;
        let w = self.weights(q, keys)?;
        let mut out = vec![0.0f32; value_dim];
        for (wi, v) in w.iter().zip(values) {
            for (o, vi) in out.iter_mut().zip(v) {
                *o += wi * vi;
            }
        }
        Ok(out)
    }

    /// Full attention with a per-head learned **attention sink** (GPT-OSS): like
    /// [`attend`](Self::attend) but the softmax denominator includes the sink
    /// logit, so the output is scaled down by the mass the sink absorbed.
    /// `sink = f32::NEG_INFINITY` reduces to [`attend`](Self::attend) exactly.
    pub fn attend_with_sink(
        &self,
        q: &[f32],
        keys: &[Vec<f32>],
        values: &[Vec<f32>],
        sink: f32,
    ) -> Result<Vec<f32>, AttentionError> {
        let value_dim = self.check_context(q, keys, values)?;
        let w = self.weights_with_sink(q, keys, sink)?;
        let mut out = vec![0.0f32; value_dim];
        for (wi, v) in w.iter().zip(values) {
            for (o, vi) in out.iter_mut().zip(v) {
                *o += wi * vi;
            }
        }
        Ok(out)
    }

    /// Online-softmax (FlashAttention) attention: one streaming pass that
    /// never materializes the score row, yet returns the *same* result as
    /// [`attend`](Self::attend) to floating-point tolerance.
    pub fn attend_streaming(
        &self,
        q: &[f32],
        keys: &[Vec<f32>],
        values: &[Vec<f32>],
    ) -> Result<Vec<f32>, AttentionError> {
        let value_dim = self.check_context(q, keys, values)?;
        let mut step = DecodeStep::with_value_dim(*self, value_dim);
        for (k, v) in keys.iter().zip(values) {
            step.push(q, k, v)?;
        }
        step.output()
    }

    /// Causal prefill: row `i` attends only to keys/values `0..=i`.
    ///
    /// `queries[i]` is the query at position `i`; it must see no future
    /// token. Requires `queries.len() <= keys.len()`. Returns one output
    /// row per query.
    pub fn attend_causal(
        &self,
        queries: &[Vec<f32>],
        keys: &[Vec<f32>],
        values: &[Vec<f32>],
    ) -> Result<Vec<Vec<f32>>, AttentionError> {
        if keys.len() != values.len() {
            return Err(AttentionError::KeyValueCountMismatch {
                keys: keys.len(),
                values: values.len(),
            });
        }
        if queries.len() > keys.len() {
            return Err(AttentionError::TooManyQueries {
                queries: queries.len(),
                keys: keys.len(),
            });
        }
        let mut rows = Vec::with_capacity(queries.len());
        for (i, q) in queries.iter().enumerate() {
            // causal prefix: positions 0..=i
            rows.push(self.attend(q, &keys[..=i], &values[..=i])?);
        }
        Ok(rows)
    }
}

/// Stateful decode-time attention: a fixed query whose context grows one
/// token at a time. This is the online-softmax recurrence exposed as an
/// accumulator, so it slots directly behind a growing KV cache — `push` per
/// decoded position, [`output`](Self::output) when you need the result.
#[derive(Debug, Clone, PartialEq)]
pub struct DecodeStep {
    head: Attention,
    /// Running max of the scaled scores seen so far.
    running_max: f32,
    /// Running softmax denominator (sum of rescaled exponentials).
    denom: f32,
    /// Running, unnormalized output accumulator.
    acc: Vec<f32>,
    /// Whether `acc`/`value_dim` is fixed yet.
    value_dim: Option<usize>,
    /// Number of tokens folded in so far.
    tokens: usize,
}

impl DecodeStep {
    /// Start an empty accumulator for `head`; the value dimension is fixed by
    /// the first [`push`](Self::push).
    pub fn new(head: Attention) -> Self {
        Self {
            head,
            running_max: f32::NEG_INFINITY,
            denom: 0.0,
            acc: Vec::new(),
            value_dim: None,
            tokens: 0,
        }
    }

    /// Start an accumulator with the value dimension already known.
    pub fn with_value_dim(head: Attention, value_dim: usize) -> Self {
        Self {
            head,
            running_max: f32::NEG_INFINITY,
            denom: 0.0,
            acc: vec![0.0; value_dim],
            value_dim: Some(value_dim),
            tokens: 0,
        }
    }

    /// Number of tokens folded in.
    pub fn tokens(&self) -> usize {
        self.tokens
    }

    /// Fold one `(key, value)` pair into the running softmax, scoring it
    /// against `query`. The first push fixes the value dimension.
    pub fn push(
        &mut self,
        query: &[f32],
        key: &[f32],
        value: &[f32],
    ) -> Result<(), AttentionError> {
        self.head.check_vec(query)?;
        self.head.check_vec(key)?;
        match self.value_dim {
            None => {
                self.value_dim = Some(value.len());
                self.acc = vec![0.0; value.len()];
            }
            Some(d) if d != value.len() => {
                return Err(AttentionError::RaggedValues {
                    index: self.tokens,
                    expected: d,
                    got: value.len(),
                });
            }
            Some(_) => {}
        }

        let score = self.head.scale * dot(query, key);
        let new_max = self.running_max.max(score);
        // exp(old_max - new_max) rescales everything accumulated so far.
        let rescale = if self.running_max.is_finite() {
            (self.running_max - new_max).exp()
        } else {
            0.0
        };
        let p = (score - new_max).exp();
        self.denom = self.denom * rescale + p;
        for (a, vi) in self.acc.iter_mut().zip(value) {
            *a = *a * rescale + p * vi;
        }
        self.running_max = new_max;
        self.tokens += 1;
        Ok(())
    }

    /// The normalized attention output over everything pushed so far.
    pub fn output(&self) -> Result<Vec<f32>, AttentionError> {
        if self.tokens == 0 || self.denom == 0.0 {
            return Err(AttentionError::EmptyContext);
        }
        Ok(self.acc.iter().map(|a| a / self.denom).collect())
    }
}

/// Dot product of two equal-length slices.
fn dot(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

/// Numerically-stable softmax (subtracts the max before exponentiating).
fn softmax(scores: &[f32]) -> Vec<f32> {
    let max = scores.iter().copied().fold(f32::NEG_INFINITY, f32::max);
    let exps: Vec<f32> = scores.iter().map(|s| (s - max).exp()).collect();
    let sum: f32 = exps.iter().sum();
    exps.iter().map(|e| e / sum).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: &[f32], b: &[f32], eps: f32) -> bool {
        a.len() == b.len() && a.iter().zip(b).all(|(x, y)| (x - y).abs() <= eps)
    }

    #[test]
    fn scale_defaults_to_inv_sqrt_dim() {
        let h = Attention::new(4);
        assert!((h.scale - 0.5).abs() < 1e-6); // 1/sqrt(4) = 0.5
    }

    #[test]
    fn weights_form_a_distribution() {
        let h = Attention::new(2);
        let q = vec![1.0, 0.0];
        let keys = vec![vec![1.0, 0.0], vec![0.0, 1.0], vec![1.0, 0.0]];
        let w = h.weights(&q, &keys).unwrap();
        let sum: f32 = w.iter().sum();
        assert!((sum - 1.0).abs() < 1e-6);
        // the two keys aligned with q get equal, larger weight than the orthogonal one
        assert!(w[0] > w[1]);
        assert!((w[0] - w[2]).abs() < 1e-6);
    }

    #[test]
    fn sink_neg_infinity_recovers_plain_attention() {
        // An infinitely-negative sink contributes nothing, so the sink variants
        // must equal the plain ones exactly.
        let h = Attention::with_scale(2, 1.0);
        let q = vec![0.7, -0.3];
        let keys = vec![vec![1.0, 0.0], vec![0.0, 1.0], vec![0.5, 0.5]];
        let values = vec![vec![1.0, 2.0], vec![3.0, 4.0], vec![5.0, 6.0]];
        let w = h.weights(&q, &keys).unwrap();
        let ws = h.weights_with_sink(&q, &keys, f32::NEG_INFINITY).unwrap();
        assert!(approx(&w, &ws, 1e-6));
        let a = h.attend(&q, &keys, &values).unwrap();
        let asink = h
            .attend_with_sink(&q, &keys, &values, f32::NEG_INFINITY)
            .unwrap();
        assert!(approx(&a, &asink, 1e-6));
    }

    #[test]
    fn sink_absorbs_mass_and_matches_the_formula() {
        // Single key: score = scale·q·k. With a sink logit `s`, the real weight
        // is exp(score) / (exp(score) + exp(s)); the remainder is the sink share.
        let h = Attention::with_scale(2, 1.0);
        let q = vec![1.0, 0.0];
        let keys = vec![vec![2.0, 0.0]]; // score = 1.0·(1·2) = 2.0
        let sink = 1.0f32;
        let w = h.weights_with_sink(&q, &keys, sink).unwrap();
        let expected = 2.0f32.exp() / (2.0f32.exp() + 1.0f32.exp());
        assert!(
            (w[0] - expected).abs() < 1e-6,
            "got {}, want {expected}",
            w[0]
        );
        assert!(w[0] < 1.0, "the sink must absorb some mass");
        // A larger sink absorbs more mass → smaller real weight.
        let w_big = h.weights_with_sink(&q, &keys, 5.0).unwrap();
        assert!(w_big[0] < w[0], "a bigger sink logit takes more mass");
    }

    #[test]
    fn attend_mixes_values_by_weight() {
        let h = Attention::with_scale(2, 1.0);
        let q = vec![10.0, 0.0]; // strongly selects key 0
        let keys = vec![vec![1.0, 0.0], vec![0.0, 1.0]];
        let values = vec![vec![1.0, 2.0, 3.0], vec![-9.0, -9.0, -9.0]];
        let out = h.attend(&q, &keys, &values).unwrap();
        // weight on key 0 ≈ 1, so output ≈ value 0
        assert!(approx(&out, &[1.0, 2.0, 3.0], 1e-3));
    }

    #[test]
    fn streaming_equals_naive() {
        let h = Attention::new(3);
        let q = vec![0.3, -1.1, 2.0];
        let keys = vec![
            vec![1.0, 0.0, -1.0],
            vec![0.5, 0.5, 0.5],
            vec![-2.0, 1.0, 0.3],
            vec![0.1, 0.2, 0.4],
        ];
        let values = vec![
            vec![1.0, 0.0],
            vec![0.0, 1.0],
            vec![2.0, -1.0],
            vec![-1.0, 3.0],
        ];
        let naive = h.attend(&q, &keys, &values).unwrap();
        let stream = h.attend_streaming(&q, &keys, &values).unwrap();
        assert!(approx(&naive, &stream, 1e-5), "{naive:?} vs {stream:?}");
    }

    #[test]
    fn streaming_is_order_dependent_in_max_but_not_result() {
        // Reordering keys/values together must not change the result.
        let h = Attention::new(2);
        let q = vec![1.0, 1.0];
        let keys = vec![vec![3.0, 0.0], vec![0.0, 3.0], vec![1.0, 1.0]];
        let values = vec![vec![1.0], vec![2.0], vec![3.0]];
        let a = h.attend_streaming(&q, &keys, &values).unwrap();

        let keys_r = vec![vec![1.0, 1.0], vec![3.0, 0.0], vec![0.0, 3.0]];
        let values_r = vec![vec![3.0], vec![1.0], vec![2.0]];
        let b = h.attend_streaming(&q, &keys_r, &values_r).unwrap();
        assert!(approx(&a, &b, 1e-5));
    }

    #[test]
    fn stable_under_overflowing_scores() {
        // Scores ~1000: a naive exp() would be +inf. Both paths must stay
        // finite and agree, selecting the max-scoring key.
        let h = Attention::with_scale(1, 1.0);
        let q = vec![1.0];
        let keys = vec![vec![1000.0], vec![999.0], vec![-1000.0]];
        let values = vec![vec![5.0], vec![6.0], vec![7.0]];
        let naive = h.attend(&q, &keys, &values).unwrap();
        let stream = h.attend_streaming(&q, &keys, &values).unwrap();
        assert!(naive[0].is_finite() && stream[0].is_finite());
        assert!(approx(&naive, &stream, 1e-4));
        // key 2 is annihilated; keys 0,1 differ by 1 → weights ≈0.731/0.269,
        // so output ≈ 0.731·5 + 0.269·6 ≈ 5.269 (finite, between the two).
        assert!((naive[0] - 5.269).abs() < 1e-2);
    }

    #[test]
    fn decode_step_matches_full_attention() {
        // Feeding a growing cache one token at a time == one-shot attend.
        let h = Attention::new(3);
        let q = vec![0.7, -0.2, 1.3];
        let keys = vec![
            vec![1.0, 2.0, 0.0],
            vec![0.0, -1.0, 1.0],
            vec![0.5, 0.5, -0.5],
        ];
        let values = vec![vec![1.0, 1.0], vec![2.0, 0.0], vec![0.0, 3.0]];

        let mut step = DecodeStep::new(h);
        for (k, v) in keys.iter().zip(&values) {
            step.push(&q, k, v).unwrap();
        }
        assert_eq!(step.tokens(), 3);
        let incremental = step.output().unwrap();
        let full = h.attend(&q, &keys, &values).unwrap();
        assert!(approx(&incremental, &full, 1e-5));
    }

    #[test]
    fn decode_step_grows_monotonically() {
        // After each push, output() should be valid and equal attending over
        // the prefix seen so far.
        let h = Attention::with_scale(1, 1.0);
        let q = vec![1.0];
        let ks = [vec![0.0], vec![2.0], vec![1.0]];
        let vs = [vec![10.0], vec![20.0], vec![30.0]];
        let mut step = DecodeStep::new(h);
        for i in 0..ks.len() {
            step.push(&q, &ks[i], &vs[i]).unwrap();
            let prefix = h.attend(&q, &ks[..=i], &vs[..=i]).unwrap();
            assert!(approx(&step.output().unwrap(), &prefix, 1e-5));
        }
    }

    #[test]
    fn causal_prefill_rows_attend_only_to_the_past() {
        let h = Attention::with_scale(1, 1.0);
        let queries = vec![vec![1.0], vec![1.0], vec![1.0]];
        let keys = vec![vec![0.0], vec![5.0], vec![-5.0]];
        let values = vec![vec![1.0], vec![2.0], vec![3.0]];
        let rows = h.attend_causal(&queries, &keys, &values).unwrap();
        assert_eq!(rows.len(), 3);
        // row 0 sees only token 0 → output exactly value 0
        assert!((rows[0][0] - 1.0).abs() < 1e-6);
        // row 1 sees tokens 0,1 and key 1 has score 5 → close to value 1
        assert!(rows[1][0] > 1.9);
        // each causal row equals streaming over its prefix
        for (i, row) in rows.iter().enumerate() {
            let s = h
                .attend_streaming(&queries[i], &keys[..=i], &values[..=i])
                .unwrap();
            assert!(approx(row, &s, 1e-5));
        }
    }

    #[test]
    fn empty_context_is_an_error() {
        let h = Attention::new(2);
        assert_eq!(
            h.attend(&[1.0, 0.0], &[], &[]).unwrap_err(),
            AttentionError::EmptyContext
        );
        assert_eq!(
            DecodeStep::new(h).output().unwrap_err(),
            AttentionError::EmptyContext
        );
    }

    #[test]
    fn dimension_mismatch_is_caught() {
        let h = Attention::new(3);
        let err = h
            .attend(&[1.0, 0.0], &[vec![1.0, 0.0, 0.0]], &[vec![1.0]])
            .unwrap_err();
        assert_eq!(
            err,
            AttentionError::DimMismatch {
                expected: 3,
                got: 2
            }
        );
    }

    #[test]
    fn kv_count_mismatch_is_caught() {
        let h = Attention::new(1);
        let err = h
            .attend(&[1.0], &[vec![1.0], vec![2.0]], &[vec![1.0]])
            .unwrap_err();
        assert_eq!(
            err,
            AttentionError::KeyValueCountMismatch { keys: 2, values: 1 }
        );
    }

    #[test]
    fn ragged_values_are_caught() {
        let h = Attention::new(1);
        let err = h
            .attend(
                &[1.0],
                &[vec![1.0], vec![2.0]],
                &[vec![1.0], vec![1.0, 2.0]],
            )
            .unwrap_err();
        assert_eq!(
            err,
            AttentionError::RaggedValues {
                index: 1,
                expected: 1,
                got: 2
            }
        );
    }

    #[test]
    fn too_many_queries_for_causal_is_caught() {
        let h = Attention::new(1);
        let err = h
            .attend_causal(&[vec![1.0], vec![1.0]], &[vec![1.0]], &[vec![1.0]])
            .unwrap_err();
        assert_eq!(
            err,
            AttentionError::TooManyQueries {
                queries: 2,
                keys: 1
            }
        );
    }

    #[test]
    fn head_serde_round_trip() {
        let h = Attention::new(8);
        let j = serde_json::to_string(&h).unwrap();
        let back: Attention = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
