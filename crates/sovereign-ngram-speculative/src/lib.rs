//! `sovereign-ngram-speculative` — a free draft, straight from the context.
//!
//! Speculative decoding speeds up generation by having a cheap *draft* propose
//! several tokens that the expensive model then verifies in one pass. The usual
//! draft is a small model — but for repetitive text you don't need one.
//! **Prompt-lookup decoding** observes that what the model is about to say has
//! often been said before in the same context: a repeated phrase, a copied table
//! row, an echoed instruction. So the draft is simply *the continuation that
//! followed the last time these tokens appeared*.
//!
//! [`NgramSpeculator::propose`] does exactly that: it looks at the last `n` tokens
//! of the context (largest `n` first, so the most specific match wins), finds the
//! most recent earlier occurrence of that `n`-gram, and returns up to `max_draft`
//! of the tokens that followed it. If nothing matches, the draft is empty and the
//! model decodes normally. Because the draft costs only a search of the context,
//! every accepted token is pure speedup, and it is *exact* — a wrong guess is
//! simply rejected by verification, never emitted.
//!
//! [`accepted_prefix`] is the verification helper: how many leading draft tokens
//! match what the model actually produced. It pairs with any verifier (e.g.
//! `sovereign-spec-decode`).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the ngram-speculative surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A prompt-lookup speculative drafter.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct NgramSpeculator {
    /// Largest suffix length to match (tries this down to `min_ngram`).
    pub max_ngram: usize,
    /// Smallest suffix length to match.
    pub min_ngram: usize,
    /// Maximum number of draft tokens to propose.
    pub max_draft: usize,
}

impl Default for NgramSpeculator {
    fn default() -> Self {
        Self {
            max_ngram: 3,
            min_ngram: 1,
            max_draft: 10,
        }
    }
}

impl NgramSpeculator {
    /// A drafter with explicit parameters.
    pub fn new(max_ngram: usize, min_ngram: usize, max_draft: usize) -> Self {
        Self {
            max_ngram: max_ngram.max(1),
            min_ngram: min_ngram.max(1),
            max_draft,
        }
    }

    /// Propose draft tokens for `context` via prompt lookup. Tries to match the
    /// last `n` tokens (for `n` from `max_ngram` down to `min_ngram`) against an
    /// earlier occurrence, returning up to `max_draft` tokens that followed the
    /// most recent such occurrence. Empty if nothing matches.
    pub fn propose(&self, context: &[u32]) -> Vec<u32> {
        let len = context.len();
        let hi = self.max_ngram.min(len.saturating_sub(1)); // need room before the suffix
        for n in (self.min_ngram..=hi).rev() {
            let suffix = &context[len - n..];
            // search backwards for the most recent earlier occurrence of `suffix`
            // (ending before the current suffix start).
            // candidate end positions: a match starting at i means context[i..i+n]
            // == suffix, with i + n <= len - n... actually we want i + n <= len - 1
            // wait: the occurrence must be *earlier* than the current suffix, i.e.
            // start i < len - n.
            let mut best_start: Option<usize> = None;
            // iterate possible start positions from latest to earliest.
            let last_possible = (len - n).saturating_sub(1);
            for i in (0..=last_possible).rev() {
                if &context[i..i + n] == suffix {
                    best_start = Some(i);
                    break;
                }
            }
            if let Some(start) = best_start {
                // the tokens that followed this occurrence are the draft.
                let after = start + n;
                let take = self.max_draft.min(len - after);
                if take > 0 {
                    return context[after..after + take].to_vec();
                }
            }
        }
        Vec::new()
    }
}

/// The number of leading tokens of `draft` that match `actual` — the accepted
/// prefix length after verification. (Speculative decoding always also emits one
/// more correct token from the model itself; this counts only the reused draft.)
pub fn accepted_prefix(draft: &[u32], actual: &[u32]) -> usize {
    draft
        .iter()
        .zip(actual.iter())
        .take_while(|(d, a)| d == a)
        .count()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn proposes_continuation_of_repeated_ngram() {
        // context: "a b c d ... a b" — the last "a b" occurred earlier followed by
        // "c d", so the draft should be [c, d, ...].
        let ctx = [1, 2, 3, 4, 5, 1, 2];
        let spec = NgramSpeculator::new(3, 1, 3); // cap the draft at 3 tokens
        let draft = spec.propose(&ctx);
        // suffix [1,2] matched at index 0, followed by 3,4,5
        assert_eq!(draft, vec![3, 4, 5]);
    }

    #[test]
    fn prefers_longer_ngram_match() {
        // both "2" and "1 2" occur earlier, but the longer match is more specific.
        // context: 9 1 2 3 ... 8 1 2
        let ctx = [9, 1, 2, 3, 7, 8, 1, 2];
        let spec = NgramSpeculator::new(3, 1, 5);
        let draft = spec.propose(&ctx);
        // last two tokens [1,2] matched at index 1 → followed by 3
        assert_eq!(draft[0], 3);
    }

    #[test]
    fn respects_max_draft() {
        let ctx = [1, 2, 3, 4, 5, 6, 7, 1, 2];
        let spec = NgramSpeculator::new(2, 1, 2);
        let draft = spec.propose(&ctx);
        // [1,2] at index 0 followed by 3,4,5,6,7 but capped to 2 → [3,4]
        assert_eq!(draft, vec![3, 4]);
    }

    #[test]
    fn no_match_yields_empty_draft() {
        let ctx = [1, 2, 3, 4, 5];
        let spec = NgramSpeculator::default();
        // the suffix [3,4,5]/[4,5]/[5] never occurred earlier → empty
        assert!(spec.propose(&ctx).is_empty());
    }

    #[test]
    fn uses_most_recent_occurrence() {
        // "1 2" occurs at index 0 (→3) and index 4 (→9); use the most recent (→9).
        let ctx = [1, 2, 3, 0, 1, 2, 9, 0, 1, 2];
        let spec = NgramSpeculator::new(2, 1, 1);
        let draft = spec.propose(&ctx);
        assert_eq!(draft, vec![9]);
    }

    #[test]
    fn accepted_prefix_counts_matching_run() {
        assert_eq!(accepted_prefix(&[1, 2, 3], &[1, 2, 9]), 2);
        assert_eq!(accepted_prefix(&[1, 2, 3], &[1, 2, 3, 4]), 3);
        assert_eq!(accepted_prefix(&[9], &[1]), 0);
        assert_eq!(accepted_prefix(&[], &[1, 2]), 0);
    }

    #[test]
    fn short_context_is_safe() {
        let spec = NgramSpeculator::default();
        assert!(spec.propose(&[]).is_empty());
        assert!(spec.propose(&[1]).is_empty());
    }

    #[test]
    fn realistic_repetition_speedup() {
        // a repeated phrase: drafting should propose the rest of the phrase.
        // "the system is ready . the system is" → draft "ready ."
        let ctx = [10, 20, 30, 40, 50, 10, 20, 30];
        let spec = NgramSpeculator::new(3, 1, 2); // propose at most 2 draft tokens
        let draft = spec.propose(&ctx);
        // last [10,20,30] matched at index 0 → followed by 40,50
        assert_eq!(draft, vec![40, 50]);
        // verification accepts the whole draft if the model agrees
        let actual = [40, 50];
        assert_eq!(accepted_prefix(&draft, &actual), 2);
    }

    #[test]
    fn serde_round_trip() {
        let spec = NgramSpeculator::new(4, 2, 8);
        let j = serde_json::to_string(&spec).unwrap();
        assert_eq!(serde_json::from_str::<NgramSpeculator>(&j).unwrap(), spec);
    }
}
