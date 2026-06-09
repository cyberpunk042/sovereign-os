//! `sovereign-dry-sampler` — suppress repetition loops without punishing reuse.
//!
//! Language models fall into loops: having written "the cat sat on the mat, the
//! cat sat on the", the most likely next token is "mat", and the model recites the
//! phrase forever. The blunt fixes have costs — a flat repetition penalty docks
//! every recently-seen token, including ones that *should* recur, and a hard
//! n-gram ban forbids any repeat outright, breaking legitimate structure.
//!
//! **DRY** (Don't Repeat Yourself) is the targeted fix. It looks at the tail of
//! what has been generated and asks, for each candidate next token: *if I pick
//! this, how long a previously-seen sequence would I be extending?* A token that
//! merely continues a two-word echo is barely touched; a token that would extend a
//! long verbatim repeat is penalized exponentially in the match length, so the
//! longer the loop, the harder it is to keep going. Tokens that do not continue any
//! repeat are left alone entirely.
//!
//! Concretely: the last generated token is matched against every earlier
//! occurrence, the match is extended backwards as far as it agrees (the longest
//! common suffix), and the token that *followed* each earlier occurrence is the one
//! that would prolong the repeat — it receives a penalty `multiplier · base^(len −
//! allowed_length)` once `len` reaches `allowed_length`. **Sequence breakers**
//! (newline, punctuation — tokens across which repetition is not meaningful) reset
//! the matching so a repeat is never counted through them.
//!
//! [`DrySampler::penalties`] returns the per-token penalty vector; [`DrySampler::apply`]
//! subtracts it from a logit slice in place. The computation is pure and
//! deterministic.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// Schema version of the DRY sampler surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// DRY sampler configuration.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DrySampler {
    /// Penalty scale (the coefficient on the exponential). `0.0` disables DRY.
    pub multiplier: f32,
    /// Exponential base; the penalty grows by this factor per extra matched token.
    pub base: f32,
    /// Minimum repeated-match length before any penalty applies (typically 2).
    pub allowed_length: usize,
    /// Cap on how far back a match is extended (bounds the work and the penalty).
    pub max_match: usize,
    /// Tokens that reset matching — repetition is not counted across them.
    pub sequence_breakers: Vec<u32>,
}

impl Default for DrySampler {
    fn default() -> Self {
        // values in the range commonly used by llama.cpp / text-generation-webui.
        Self {
            multiplier: 0.8,
            base: 1.75,
            allowed_length: 2,
            max_match: 50,
            sequence_breakers: Vec::new(),
        }
    }
}

impl DrySampler {
    /// A sampler with the core knobs and no sequence breakers.
    pub fn new(multiplier: f32, base: f32, allowed_length: usize) -> Self {
        Self {
            multiplier,
            base,
            allowed_length,
            ..Default::default()
        }
    }

    /// Set the sequence-breaker token set (builder style).
    pub fn with_breakers(mut self, breakers: Vec<u32>) -> Self {
        self.sequence_breakers = breakers;
        self
    }

    /// Whether the sampler is active (a positive multiplier).
    pub fn is_active(&self) -> bool {
        self.multiplier > 0.0
    }

    /// For each token id in `0..vocab_size`, the maximum repeated-match length that
    /// picking it next would extend, given the generated `history`. A length of 0
    /// means the token continues no repeat.
    pub fn match_lengths(&self, history: &[u32], vocab_size: usize) -> Vec<usize> {
        let mut rep = vec![0usize; vocab_size];
        let n = history.len();
        if n == 0 || !self.is_active() {
            return rep;
        }
        let breakers: HashSet<u32> = self.sequence_breakers.iter().copied().collect();
        let last = history[n - 1];
        // a repeat cannot be anchored on a sequence breaker.
        if breakers.contains(&last) {
            return rep;
        }
        let cap = self.max_match.max(1);

        // every earlier occurrence of `last` is a candidate repeat anchor.
        for idx in 0..n - 1 {
            if history[idx] != last {
                continue;
            }
            // extend the match backwards while the tokens agree and we do not
            // cross a sequence breaker or run off either end.
            let mut m = 1usize;
            while m < cap && idx >= m && (n - 1) >= m {
                let a = history[idx - m];
                let b = history[n - 1 - m];
                if a != b || breakers.contains(&a) {
                    break;
                }
                m += 1;
            }
            // the token that followed the earlier occurrence is the one that would
            // prolong the repeat if generated now.
            let next_tok = history[idx + 1] as usize;
            if next_tok < vocab_size && m > rep[next_tok] {
                rep[next_tok] = m;
            }
        }
        rep
    }

    /// The per-token penalty vector (length `vocab_size`). A token whose match
    /// length reaches `allowed_length` gets `multiplier · base^(len − allowed_length)`;
    /// all others get `0`.
    pub fn penalties(&self, history: &[u32], vocab_size: usize) -> Vec<f32> {
        let rep = self.match_lengths(history, vocab_size);
        rep.into_iter()
            .map(|len| {
                if len >= self.allowed_length && self.is_active() {
                    let exp = (len - self.allowed_length) as i32;
                    self.multiplier * self.base.powi(exp)
                } else {
                    0.0
                }
            })
            .collect()
    }

    /// Subtract the DRY penalties from `logits` in place. The slice length is the
    /// vocabulary size.
    pub fn apply(&self, logits: &mut [f32], history: &[u32]) {
        if !self.is_active() {
            return;
        }
        let pen = self.penalties(history, logits.len());
        for (l, p) in logits.iter_mut().zip(pen) {
            *l -= p;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f32, b: f32) -> bool {
        (a - b).abs() < 1e-5
    }

    #[test]
    fn no_history_no_penalty() {
        let dry = DrySampler::default();
        let p = dry.penalties(&[], 10);
        assert!(p.iter().all(|&x| x == 0.0));
    }

    #[test]
    fn penalizes_token_that_continues_a_repeat() {
        // history: a(0) b(1) c(2) a(0) b(1) ; about to pick token 6.
        // picking c(2) would re-create the trigram "a b c" → penalize token 2.
        let dry = DrySampler::new(0.8, 1.75, 2);
        let hist = [0u32, 1, 2, 0, 1];
        let p = dry.penalties(&hist, 5);
        assert!(p[2] > 0.0, "token 2 should be penalized: {p:?}");
        // tokens that don't continue the repeat are untouched.
        assert!(approx(p[0], 0.0));
        assert!(approx(p[1], 0.0));
        assert!(approx(p[3], 0.0));
        assert!(approx(p[4], 0.0));
    }

    #[test]
    fn longer_repeat_penalized_more() {
        // a longer verbatim match should yield a bigger penalty (exponential).
        let dry = DrySampler::new(1.0, 2.0, 1);
        // short match: x y x → picking y extends match length 1.
        let short = [9u32, 5, 9];
        let ps = dry.penalties(&short, 10);
        // long match: a b c d a b c → picking d extends match length 3.
        let long = [0u32, 1, 2, 3, 0, 1, 2];
        let pl = dry.penalties(&long, 10);
        assert!(ps[5] > 0.0 && pl[3] > 0.0);
        assert!(
            pl[3] > ps[5],
            "long {} should exceed short {}",
            pl[3],
            ps[5]
        );
    }

    #[test]
    fn allowed_length_gates_short_matches() {
        // allowed_length 3: a match of only length 2 must NOT be penalized.
        let dry = DrySampler::new(0.8, 1.75, 3);
        let hist = [0u32, 1, 2, 0, 1]; // continuing token 2 has match length 2
        let p = dry.penalties(&hist, 5);
        assert!(approx(p[2], 0.0), "match len 2 < allowed 3 should be free");
        // with allowed_length 2 the same case IS penalized.
        let dry2 = DrySampler::new(0.8, 1.75, 2);
        assert!(dry2.penalties(&hist, 5)[2] > 0.0);
    }

    #[test]
    fn exact_penalty_value() {
        // match length 2, allowed 2 → exponent 0 → penalty == multiplier.
        let dry = DrySampler::new(0.8, 1.75, 2);
        let hist = [0u32, 1, 2, 0, 1];
        let p = dry.penalties(&hist, 5);
        assert!(approx(p[2], 0.8), "got {}", p[2]);
        // match length 3, allowed 2 → exponent 1 → penalty == multiplier*base.
        let dry3 = DrySampler::new(0.8, 1.75, 2);
        let hist3 = [0u32, 1, 2, 3, 0, 1, 2]; // continuing token 3, match len 3
        let p3 = dry3.penalties(&hist3, 5);
        assert!(approx(p3[3], 0.8 * 1.75), "got {}", p3[3]);
    }

    #[test]
    fn sequence_breaker_resets_matching() {
        // token 7 is a breaker between the two occurrences of the pattern.
        // history: a b | a b  with a breaker (7) — the match cannot cross it.
        let dry = DrySampler::new(0.8, 1.75, 1).with_breakers(vec![7]);
        // a(0) b(1) BRK(7) a(0) b(1): last is b(1); earlier b at idx1.
        // extending back: history[0]=a==history[3]=a (m=2)? idx-2 = -1 stops; but
        // the anchor chain doesn't cross the breaker here, so token 7 is the next.
        let hist = [0u32, 1, 7, 0, 1];
        let p = dry.penalties(&hist, 8);
        // continuing token after earlier b(idx1) is the breaker 7 itself — picking
        // a breaker is still "allowed"; what matters is breakers stop back-extension.
        // Construct a case where back-extension would cross a breaker:
        let dry2 = DrySampler::new(1.0, 2.0, 1).with_breakers(vec![7]);
        // a 7 b a' ... : x(0) BRK(7) y(1) z(2) x(0) BRK(7) y(1) ; last=y(1) earlier y at idx2
        let hist2 = [0u32, 7, 1, 2, 0, 7, 1];
        let p2 = dry2.penalties(&hist2, 8);
        // continuing token z(2) extends match y back to... 7 is a breaker so back
        // extension from idx2 hits history[1]=7 → stops at m=1. penalty exists but
        // is small; without the breaker it would extend further.
        let dry3 = DrySampler::new(1.0, 2.0, 1); // no breakers
        let p3 = dry3.penalties(&hist2, 8);
        assert!(
            p3[2] >= p2[2],
            "breaker should not increase penalty: with {} without {}",
            p2[2],
            p3[2]
        );
        // sanity: the first scenario produced a finite vector.
        assert_eq!(p.len(), 8);
    }

    #[test]
    fn max_match_caps_penalty() {
        // a very long repeat capped at max_match=2 should not penalize beyond it.
        let dry = DrySampler::new(1.0, 2.0, 1);
        let capped = DrySampler {
            max_match: 2,
            ..DrySampler::new(1.0, 2.0, 1)
        };
        let hist = [0u32, 1, 2, 3, 4, 0, 1, 2, 3]; // continuing token 4, long match
        let uncapped_p = dry.penalties(&hist, 6);
        let capped_p = capped.penalties(&hist, 6);
        assert!(
            capped_p[4] < uncapped_p[4],
            "cap should reduce: capped {} uncapped {}",
            capped_p[4],
            uncapped_p[4]
        );
    }

    #[test]
    fn apply_subtracts_in_place() {
        let dry = DrySampler::new(0.8, 1.75, 2);
        let hist = [0u32, 1, 2, 0, 1];
        let mut logits = vec![1.0f32; 5];
        dry.apply(&mut logits, &hist);
        // token 2 was penalized; the rest unchanged.
        assert!(approx(logits[2], 1.0 - 0.8));
        assert!(approx(logits[0], 1.0));
        assert!(approx(logits[3], 1.0));
    }

    #[test]
    fn inactive_when_multiplier_zero() {
        let dry = DrySampler::new(0.0, 1.75, 2);
        assert!(!dry.is_active());
        let hist = [0u32, 1, 2, 0, 1];
        let mut logits = vec![1.0f32; 5];
        dry.apply(&mut logits, &hist);
        assert!(logits.iter().all(|&x| approx(x, 1.0)));
    }

    #[test]
    fn deterministic() {
        let dry = DrySampler::default();
        let dry = DrySampler {
            multiplier: 0.8,
            ..dry
        };
        let hist = [3u32, 1, 4, 1, 5, 3, 1, 4, 1];
        assert_eq!(dry.penalties(&hist, 8), dry.penalties(&hist, 8));
    }

    #[test]
    fn serde_round_trip() {
        let dry = DrySampler::new(0.7, 1.5, 3).with_breakers(vec![10, 13]);
        let j = serde_json::to_string(&dry).unwrap();
        let back: DrySampler = serde_json::from_str(&j).unwrap();
        assert_eq!(dry, back);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
