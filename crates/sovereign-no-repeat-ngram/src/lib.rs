//! `sovereign-no-repeat-ngram` — block exact n-gram repetition in decoding.
//!
//! The sampler's repetition penalty discourages individual *tokens* that have
//! appeared recently; this is the *sequence*-level control. Given the tokens
//! generated so far and a size `n`, it finds every token that would make the
//! last `n` tokens an n-gram that already occurred earlier — and reports them
//! so a caller can ban them (e.g. via the logit mask). The effect: the model
//! can never emit the same `n`-token phrase twice, which kills the verbatim
//! loops that token penalties alone don't stop.
//!
//! Concretely, the "prefix" is the last `n − 1` generated tokens; a candidate
//! next token is banned if the sequence `prefix ++ [token]` appears anywhere
//! earlier in the history. `n = 1` degenerates to "never repeat any token".
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

/// Schema version of the no-repeat-ngram surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A no-repeat-n-gram constraint of size `n`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct NoRepeatNgram {
    /// The n-gram size. `0` disables the constraint.
    pub n: usize,
}

impl NoRepeatNgram {
    /// A constraint of size `n`.
    pub fn new(n: usize) -> Self {
        Self { n }
    }

    /// Whether the constraint is active.
    pub fn is_active(&self) -> bool {
        self.n > 0
    }

    /// The tokens that, appended to `history`, would repeat a previously-seen
    /// `n`-gram — i.e. the tokens to ban for the next step. Sorted, deduped.
    pub fn banned_next(&self, history: &[usize]) -> Vec<usize> {
        if self.n == 0 {
            return Vec::new();
        }
        let prefix_len = self.n - 1;
        if history.len() < prefix_len {
            return Vec::new();
        }
        let prefix = &history[history.len() - prefix_len..];

        let mut banned = BTreeSet::new();
        if history.len() >= self.n {
            for w in history.windows(self.n) {
                if &w[..prefix_len] == prefix {
                    banned.insert(w[self.n - 1]);
                }
            }
        }
        banned.into_iter().collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inactive_when_zero() {
        let g = NoRepeatNgram::new(0);
        assert!(!g.is_active());
        assert!(g.banned_next(&[1, 2, 3]).is_empty());
    }

    #[test]
    fn bigram_blocks_the_loop_continuation() {
        // history a b a b a (0 1 0 1 0); last token is `a` → `b` would repeat "a b"
        let g = NoRepeatNgram::new(2);
        assert_eq!(g.banned_next(&[0, 1, 0, 1, 0]), vec![1]);
    }

    #[test]
    fn bigram_no_ban_when_prefix_is_new() {
        // last token 2 never appeared as a bigram prefix before
        let g = NoRepeatNgram::new(2);
        assert!(g.banned_next(&[0, 1, 0, 1, 2]).is_empty());
    }

    #[test]
    fn trigram_blocks_only_the_full_match() {
        // "x y z ... x y" → next `z` would repeat the trigram "x y z"
        // tokens: x=0 y=1 z=2 q=3 ; history: 0 1 2 3 0 1
        let g = NoRepeatNgram::new(3);
        assert_eq!(g.banned_next(&[0, 1, 2, 3, 0, 1]), vec![2]);
        // but if the prefix "3 0" never preceded anything, no ban
        assert!(g.banned_next(&[0, 1, 2, 3, 0]).is_empty());
    }

    #[test]
    fn collects_all_distinct_continuations() {
        // prefix `0` was followed by 1 and by 2 earlier → both banned
        let g = NoRepeatNgram::new(2);
        assert_eq!(g.banned_next(&[0, 1, 0, 2, 0]), vec![1, 2]);
    }

    #[test]
    fn unigram_bans_every_seen_token() {
        let g = NoRepeatNgram::new(1);
        assert_eq!(g.banned_next(&[3, 1, 3, 2]), vec![1, 2, 3]);
    }

    #[test]
    fn history_too_short_yields_no_bans() {
        let g = NoRepeatNgram::new(3);
        assert!(g.banned_next(&[5]).is_empty()); // need a 2-token prefix
    }

    #[test]
    fn serde_round_trip() {
        let g = NoRepeatNgram::new(4);
        let j = serde_json::to_string(&g).unwrap();
        let back: NoRepeatNgram = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }

    // Integration: feed the bans into the logit mask → the sampler never picks
    // a token that would repeat an n-gram.
    #[test]
    fn banned_tokens_are_never_sampled() {
        use sovereign_logit_mask::LogitMask;
        use sovereign_sampler::{Sampler, SamplerConfig};

        let g = NoRepeatNgram::new(2);
        let history = [0usize, 1, 0, 1, 0]; // `b` (=1) would repeat "a b"
        let banned = g.banned_next(&history);
        assert_eq!(banned, vec![1]);

        // token 1 has the highest raw logit, but it's banned
        let raw = [0.5, 10.0, 0.3, 0.2];
        let mask = LogitMask::new().ban_all(banned);
        let masked = mask.masked(&raw);
        let sampler = Sampler::new(SamplerConfig::default());
        for seed in 0..300u64 {
            let t = sampler.sample_seeded(&masked, &[], seed).unwrap();
            assert_ne!(t, 1, "banned n-gram continuation sampled at seed {seed}");
        }
    }
}
