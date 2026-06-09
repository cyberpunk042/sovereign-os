//! `sovereign-logit-mask` — constrained-decoding logit processing.
//!
//! Sampling decides *how* to draw from a distribution; this crate decides
//! *which tokens are even eligible*, by transforming the raw logit row before
//! it reaches the sampler. It is the hook for two real needs:
//!
//! * **Structured output** — confine generation to a permitted token set (an
//!   allow-list), e.g. only digits, only valid JSON continuations, only the
//!   tokens a grammar permits at this step.
//! * **Safety / steering** — push the model away from forbidden tokens (a
//!   ban-list) or nudge it with a per-token logit bias.
//!
//! Applied in order: an allow-list (everything *not* allowed → `−∞`), then
//! bans (`−∞`), then additive biases. A banned or disallowed token gets
//! `−∞`, so after softmax its probability is exactly zero and the sampler can
//! never select it — pinned as an integration test against the real sampler.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

/// Schema version of the logit-mask surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A constrained-decoding logit processor.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct LogitMask {
    /// If non-empty, ONLY these token ids may survive (others → `−∞`).
    allow: HashSet<usize>,
    /// These token ids are forced to `−∞`.
    ban: HashSet<usize>,
    /// Additive per-token logit biases.
    bias: HashMap<usize, f32>,
}

impl LogitMask {
    /// An empty mask (identity transform).
    pub fn new() -> Self {
        Self::default()
    }

    /// Restrict eligibility to `tokens` (allow-list). Repeated calls union.
    pub fn allow_only<I: IntoIterator<Item = usize>>(mut self, tokens: I) -> Self {
        self.allow.extend(tokens);
        self
    }

    /// Forbid a single token.
    pub fn ban(mut self, token: usize) -> Self {
        self.ban.insert(token);
        self
    }

    /// Forbid several tokens.
    pub fn ban_all<I: IntoIterator<Item = usize>>(mut self, tokens: I) -> Self {
        self.ban.extend(tokens);
        self
    }

    /// Add a logit bias for a token (positive encourages, negative discourages).
    pub fn bias(mut self, token: usize, delta: f32) -> Self {
        *self.bias.entry(token).or_insert(0.0) += delta;
        self
    }

    /// Whether the mask is empty (a no-op).
    pub fn is_identity(&self) -> bool {
        self.allow.is_empty() && self.ban.is_empty() && self.bias.is_empty()
    }

    /// Whether token `id` is eligible (not disallowed and not banned). Indices
    /// beyond the eventual logit row are reported as eligible (no constraint).
    pub fn is_eligible(&self, id: usize) -> bool {
        let allowed = self.allow.is_empty() || self.allow.contains(&id);
        allowed && !self.ban.contains(&id)
    }

    /// Apply the mask in place: allow-list → bans → biases. Out-of-range token
    /// specifications are ignored. Disallowed/banned positions become `−∞`.
    pub fn apply(&self, logits: &mut [f32]) {
        // allow-list: mask everything not allowed
        if !self.allow.is_empty() {
            for (i, l) in logits.iter_mut().enumerate() {
                if !self.allow.contains(&i) {
                    *l = f32::NEG_INFINITY;
                }
            }
        }
        // bans
        for &b in &self.ban {
            if let Some(l) = logits.get_mut(b) {
                *l = f32::NEG_INFINITY;
            }
        }
        // biases (applied to whatever survives; -inf + finite stays -inf)
        for (&t, &delta) in &self.bias {
            if let Some(l) = logits.get_mut(t) {
                *l += delta;
            }
        }
    }

    /// Apply to a copy and return it.
    pub fn masked(&self, logits: &[f32]) -> Vec<f32> {
        let mut out = logits.to_vec();
        self.apply(&mut out);
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_mask_is_identity() {
        let m = LogitMask::new();
        assert!(m.is_identity());
        let logits = vec![1.0, 2.0, 3.0];
        assert_eq!(m.masked(&logits), logits);
    }

    #[test]
    fn ban_sets_neg_infinity() {
        let m = LogitMask::new().ban(1);
        let out = m.masked(&[1.0, 2.0, 3.0]);
        assert_eq!(out[0], 1.0);
        assert_eq!(out[1], f32::NEG_INFINITY);
        assert_eq!(out[2], 3.0);
        assert!(!m.is_eligible(1));
        assert!(m.is_eligible(0));
    }

    #[test]
    fn bias_is_additive() {
        let m = LogitMask::new().bias(0, 5.0).bias(2, -1.0);
        let out = m.masked(&[1.0, 2.0, 3.0]);
        assert_eq!(out, vec![6.0, 2.0, 2.0]);
    }

    #[test]
    fn allow_only_masks_the_rest() {
        let m = LogitMask::new().allow_only([0, 2]);
        let out = m.masked(&[1.0, 2.0, 3.0, 4.0]);
        assert_eq!(out[0], 1.0);
        assert_eq!(out[1], f32::NEG_INFINITY);
        assert_eq!(out[2], 3.0);
        assert_eq!(out[3], f32::NEG_INFINITY);
        assert!(m.is_eligible(0) && !m.is_eligible(1) && m.is_eligible(2));
    }

    #[test]
    fn ban_overrides_allow() {
        // token in allow-list but also banned → banned wins (−∞).
        let m = LogitMask::new().allow_only([0, 1, 2]).ban(1);
        let out = m.masked(&[1.0, 2.0, 3.0]);
        assert_eq!(out[1], f32::NEG_INFINITY);
        assert!(!m.is_eligible(1));
    }

    #[test]
    fn bias_on_banned_token_stays_neg_inf() {
        let m = LogitMask::new().ban(0).bias(0, 100.0);
        let out = m.masked(&[1.0, 2.0]);
        assert_eq!(out[0], f32::NEG_INFINITY);
    }

    #[test]
    fn out_of_range_specs_are_ignored() {
        let m = LogitMask::new().ban(99).bias(50, 1.0);
        let logits = vec![1.0, 2.0];
        assert_eq!(m.masked(&logits), logits); // unchanged, no panic
    }

    #[test]
    fn repeated_bias_accumulates() {
        let m = LogitMask::new().bias(0, 1.0).bias(0, 2.0);
        assert_eq!(m.masked(&[0.0])[0], 3.0);
    }

    #[test]
    fn serde_round_trip() {
        let m = LogitMask::new().allow_only([1, 2, 3]).ban(2).bias(1, 0.5);
        let j = serde_json::to_string(&m).unwrap();
        let back: LogitMask = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }

    // Integration with the real sampler: a masked token is never sampled.
    #[test]
    fn sampler_never_picks_a_banned_token() {
        use sovereign_sampler::{Sampler, SamplerConfig};
        let sampler = Sampler::new(SamplerConfig::default());
        // token 1 has by far the highest raw logit, but we ban it.
        let raw = [0.0, 10.0, 0.1, 0.2];
        let mask = LogitMask::new().ban(1);
        let masked = mask.masked(&raw);
        for seed in 0..300u64 {
            let t = sampler.sample_seeded(&masked, &[], seed).unwrap();
            assert_ne!(t, 1, "banned token 1 was sampled at seed {seed}");
        }
    }

    #[test]
    fn sampler_confined_to_allow_list() {
        use sovereign_sampler::{Sampler, SamplerConfig};
        let sampler = Sampler::new(SamplerConfig::default());
        let raw = [5.0, 1.0, 4.0, 3.0, 2.0];
        let mask = LogitMask::new().allow_only([1, 3]);
        let masked = mask.masked(&raw);
        for seed in 0..300u64 {
            let t = sampler.sample_seeded(&masked, &[], seed).unwrap();
            assert!(
                t == 1 || t == 3,
                "sampled {t} outside allow-list at seed {seed}"
            );
        }
    }
}
