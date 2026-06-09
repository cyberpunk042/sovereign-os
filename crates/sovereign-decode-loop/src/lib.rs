//! `sovereign-decode-loop` — the transformer decode inner loop, assembled.
//!
//! The three primitive engines each do one job; this crate wires them into
//! the loop a real autoregressive decoder runs, one token at a time:
//!
//! ```text
//!   append_token(k, v):   k ← RoPE(k, position);   store (k, v);   position++
//!   decode_next(q, seed): q ← RoPE(q, position)             (sovereign-rope)
//!                         ctx ← Attention(q, keys, values)  (sovereign-attention)
//!                         logits ← head · ctx               (linear projection)
//!                         token ← Sampler(logits, seed)     (sovereign-sampler)
//! ```
//!
//! [`append_token`](DecodeLoop::append_token) grows the KV cache (each key
//! rotated by *its* position), and [`decode_next`](DecodeLoop::decode_next)
//! rotates the query by the *current* position before attending — so the
//! score between a query and a cached key depends only on their relative
//! offset, which is the whole reason RoPE sits in front of attention. The
//! linear head turns the attention context into a vocab-sized logit row, and
//! the sampler turns that into a token. Because every stage is deterministic
//! under a seed, a whole decode is reproducible and replayable.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_attention::{Attention, AttentionError};
use sovereign_rope::{Rope, RopeError};
use sovereign_sampler::{Sampler, SamplerError};
use thiserror::Error;

/// Schema version of the decode-loop surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong running a decode step.
#[derive(Debug, Error, PartialEq)]
pub enum DecodeError {
    /// A positional-rotation error from the RoPE stage.
    #[error("rope: {0}")]
    Rope(#[from] RopeError),
    /// An attention error (dim/context mismatch).
    #[error("attention: {0}")]
    Attention(#[from] AttentionError),
    /// A sampling error (empty/over-filtered logits).
    #[error("sampler: {0}")]
    Sampler(#[from] SamplerError),
    /// The output head's input width did not match the attention value dim.
    #[error("projection input width {expected} != context dim {got}")]
    ProjectionWidth {
        /// Width the head expects (its `dim`).
        expected: usize,
        /// Width the attention context actually has.
        got: usize,
    },
    /// Decoding was requested with an empty KV cache.
    #[error("empty kv cache: append at least one token before decoding")]
    EmptyCache,
}

/// A dense linear output head: `logits = W · context`, with `W` stored
/// row-major as `vocab` rows of `dim` columns.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OutputHead {
    /// Vocabulary size (number of logits produced).
    pub vocab: usize,
    /// Input width (must equal the attention value dimension).
    pub dim: usize,
    /// Row-major `vocab × dim` weights.
    pub weights: Vec<f32>,
}

impl OutputHead {
    /// Build a head from `vocab × dim` row-major weights.
    ///
    /// # Panics
    /// Panics if `weights.len() != vocab * dim`.
    pub fn new(vocab: usize, dim: usize, weights: Vec<f32>) -> Self {
        assert_eq!(weights.len(), vocab * dim, "weights must be vocab*dim");
        Self {
            vocab,
            dim,
            weights,
        }
    }

    /// Project an attention context vector into a `vocab`-length logit row.
    pub fn project(&self, context: &[f32]) -> Result<Vec<f32>, DecodeError> {
        if context.len() != self.dim {
            return Err(DecodeError::ProjectionWidth {
                expected: self.dim,
                got: context.len(),
            });
        }
        let mut logits = vec![0.0f32; self.vocab];
        for (v, logit) in logits.iter_mut().enumerate() {
            let row = &self.weights[v * self.dim..(v + 1) * self.dim];
            *logit = row.iter().zip(context).map(|(w, c)| w * c).sum();
        }
        Ok(logits)
    }
}

/// One decoder layer's autoregressive state: the configured engines plus the
/// growing KV cache and the recent-token window.
#[derive(Debug, Clone)]
pub struct DecodeLoop {
    rope: Rope,
    attention: Attention,
    sampler: Sampler,
    head: OutputHead,
    rotated_keys: Vec<Vec<f32>>,
    values: Vec<Vec<f32>>,
    recent: Vec<usize>,
    /// How many recent tokens feed the repetition penalty.
    recent_window: usize,
}

impl DecodeLoop {
    /// Assemble a decode loop. `rope` and `attention` must share a head dim;
    /// `head.dim` must equal the attention value dimension fed at runtime.
    pub fn new(rope: Rope, attention: Attention, sampler: Sampler, head: OutputHead) -> Self {
        Self {
            rope,
            attention,
            sampler,
            head,
            rotated_keys: Vec::new(),
            values: Vec::new(),
            recent: Vec::new(),
            recent_window: 64,
        }
    }

    /// Set how many recent tokens feed the repetition penalty (default 64).
    pub fn with_recent_window(mut self, window: usize) -> Self {
        self.recent_window = window;
        self
    }

    /// Number of cached positions.
    pub fn len(&self) -> usize {
        self.values.len()
    }

    /// Whether the KV cache is empty.
    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }

    /// The tokens emitted so far (most recent last).
    pub fn emitted(&self) -> &[usize] {
        &self.recent
    }

    /// Append a `(key, value)` to the KV cache. The key is RoPE-rotated by its
    /// own position (the current cache length) before being stored.
    pub fn append_token(&mut self, key: &[f32], value: Vec<f32>) -> Result<(), DecodeError> {
        let pos = self.values.len();
        let rotated = self.rope.rotate(key, pos)?;
        self.rotated_keys.push(rotated);
        self.values.push(value);
        Ok(())
    }

    /// Run one decode step: rotate `query` by the current position, attend
    /// over the cache, project to logits, and sample the next token (seeded
    /// for reproducibility). The sampled token is recorded for the repetition
    /// penalty but does *not* itself extend the cache — call
    /// [`append_token`](Self::append_token) with that token's K/V to advance.
    pub fn decode_next(&mut self, query: &[f32], seed: u64) -> Result<usize, DecodeError> {
        if self.values.is_empty() {
            return Err(DecodeError::EmptyCache);
        }
        let pos = self.values.len();
        let q = self.rope.rotate(query, pos)?;
        let context = self
            .attention
            .attend(&q, &self.rotated_keys, &self.values)?;
        let logits = self.head.project(&context)?;
        let recent_start = self.recent.len().saturating_sub(self.recent_window);
        let token = self
            .sampler
            .sample_seeded(&logits, &self.recent[recent_start..], seed)?;
        self.recent.push(token);
        Ok(token)
    }

    /// The attention context (pre-projection) for `query` at the current
    /// position — useful for inspection/tests without sampling.
    pub fn context_for(&self, query: &[f32]) -> Result<Vec<f32>, DecodeError> {
        if self.values.is_empty() {
            return Err(DecodeError::EmptyCache);
        }
        let pos = self.values.len();
        let q = self.rope.rotate(query, pos)?;
        Ok(self
            .attention
            .attend(&q, &self.rotated_keys, &self.values)?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_sampler::SamplerConfig;

    // Head dim 4, value dim 2, vocab 3.
    fn loop_fixture() -> DecodeLoop {
        let rope = Rope::new(4);
        let attention = Attention::new(4);
        let sampler = Sampler::new(SamplerConfig::default());
        // 3 vocab rows × 2 dims, row-major.
        let head = OutputHead::new(3, 2, vec![1.0, 0.0, 0.0, 1.0, -1.0, -1.0]);
        DecodeLoop::new(rope, attention, sampler, head)
    }

    fn seed_cache(dl: &mut DecodeLoop) {
        dl.append_token(&[1.0, 0.0, 0.0, 0.0], vec![1.0, 0.0])
            .unwrap();
        dl.append_token(&[0.0, 1.0, 0.0, 0.0], vec![0.0, 1.0])
            .unwrap();
        dl.append_token(&[0.0, 0.0, 1.0, 0.0], vec![1.0, 1.0])
            .unwrap();
    }

    #[test]
    fn decoding_empty_cache_errors() {
        let mut dl = loop_fixture();
        assert_eq!(
            dl.decode_next(&[1.0, 0.0, 0.0, 0.0], 1).unwrap_err(),
            DecodeError::EmptyCache
        );
    }

    #[test]
    fn cache_grows_with_appended_tokens() {
        let mut dl = loop_fixture();
        assert!(dl.is_empty());
        seed_cache(&mut dl);
        assert_eq!(dl.len(), 3);
        assert!(!dl.is_empty());
    }

    #[test]
    fn output_head_projects_correctly() {
        let head = OutputHead::new(3, 2, vec![1.0, 0.0, 0.0, 1.0, -1.0, -1.0]);
        // context [2,3]: logits = [1*2+0*3, 0*2+1*3, -1*2-1*3] = [2, 3, -5]
        let logits = head.project(&[2.0, 3.0]).unwrap();
        assert_eq!(logits, vec![2.0, 3.0, -5.0]);
    }

    #[test]
    fn projection_width_mismatch_is_caught() {
        let head = OutputHead::new(3, 2, vec![0.0; 6]);
        assert_eq!(
            head.project(&[1.0, 2.0, 3.0]).unwrap_err(),
            DecodeError::ProjectionWidth {
                expected: 2,
                got: 3
            }
        );
    }

    #[test]
    fn full_step_emits_in_range_token() {
        let mut dl = loop_fixture();
        seed_cache(&mut dl);
        let t = dl.decode_next(&[0.5, 0.5, 0.5, 0.5], 42).unwrap();
        assert!(t < 3);
        assert_eq!(dl.emitted(), &[t]);
    }

    #[test]
    fn decode_is_reproducible_per_seed() {
        let mut a = loop_fixture();
        let mut b = loop_fixture();
        seed_cache(&mut a);
        seed_cache(&mut b);
        let ta = a.decode_next(&[0.3, -0.2, 0.7, 0.1], 7).unwrap();
        let tb = b.decode_next(&[0.3, -0.2, 0.7, 0.1], 7).unwrap();
        assert_eq!(ta, tb);
    }

    #[test]
    fn greedy_head_selects_the_dominant_logit() {
        // A head whose row 2 dwarfs the others → greedy always picks token 2.
        let rope = Rope::new(4);
        let attention = Attention::new(4);
        let sampler = Sampler::greedy();
        let head = OutputHead::new(3, 2, vec![0.0, 0.0, 0.0, 0.0, 10.0, 10.0]);
        let mut dl = DecodeLoop::new(rope, attention, sampler, head);
        seed_cache(&mut dl);
        for seed in 0..20u64 {
            // fresh loop each time so `recent` doesn't accumulate
            let mut d = dl.clone();
            assert_eq!(d.decode_next(&[1.0, 1.0, 1.0, 1.0], seed).unwrap(), 2);
        }
    }

    #[test]
    fn position_changes_the_attention_context() {
        // The same query attends differently as the cache (and thus the
        // query's RoPE position) grows — proving RoPE+attention are wired in.
        let mut dl = loop_fixture();
        dl.append_token(&[1.0, 0.0, 0.0, 0.0], vec![1.0, 0.0])
            .unwrap();
        let ctx1 = dl.context_for(&[0.5, 0.5, 0.5, 0.5]).unwrap();
        dl.append_token(&[0.0, 1.0, 0.0, 0.0], vec![0.0, 1.0])
            .unwrap();
        let ctx2 = dl.context_for(&[0.5, 0.5, 0.5, 0.5]).unwrap();
        // different cache contents ⇒ different context
        assert!(ctx1 != ctx2);
    }

    #[test]
    fn autoregressive_run_records_every_token() {
        let mut dl = loop_fixture();
        seed_cache(&mut dl);
        // emit 5 tokens, feeding a trivial K/V back each step
        for step in 0..5u64 {
            let t = dl.decode_next(&[0.2, 0.4, -0.1, 0.3], step).unwrap();
            // advance the cache with the emitted token's (toy) K/V
            dl.append_token(&[0.1, 0.1, 0.1, 0.1], vec![t as f32, 1.0])
                .unwrap();
        }
        assert_eq!(dl.emitted().len(), 5);
        assert_eq!(dl.len(), 8); // 3 seeded + 5 appended
    }

    #[test]
    fn head_serde_round_trip() {
        let head = OutputHead::new(2, 3, vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0]);
        let j = serde_json::to_string(&head).unwrap();
        let back: OutputHead = serde_json::from_str(&j).unwrap();
        assert_eq!(head, back);
    }
}
