//! `sovereign-unigram-tokenizer` — maximum-likelihood subword segmentation.
//!
//! The Unigram language-model tokenizer (the scheme behind SentencePiece) treats
//! a vocabulary as a set of pieces, each with a probability, and assumes a
//! tokenization's probability is the product of its pieces' probabilities
//! (a *unigram* model — pieces are independent). Tokenizing a string then means
//! finding the segmentation into vocabulary pieces with the highest total
//! probability. Working in log space turns that product into a sum, and the best
//! segmentation is found by a Viterbi-style dynamic program over the lattice of
//! pieces: `best[i] = max over pieces p ending at position i of
//! best[start(p)] + logprob(p)`, with a backpointer at each position to
//! reconstruct the winning split.
//!
//! Unlike greedy WordPiece, this is *globally* optimal for the model — it will
//! reject a long early piece if two shorter ones score better overall. A
//! single-character fallback with a fixed penalty guarantees every input is
//! segmentable even when a character is missing from the vocabulary, so it never
//! gets stuck.
//!
//! The DP runs over Unicode scalar values, so multi-byte text segments
//! correctly, and the candidate pieces at each position are bounded by the
//! longest vocabulary piece for efficiency.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema version of the unigram-tokenizer surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A Unigram-LM tokenizer over a fixed piece vocabulary.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct UnigramTokenizer {
    /// piece → log-probability (typically ≤ 0).
    vocab: HashMap<String, f64>,
    /// longest piece length in characters (bounds the DP lookback).
    max_piece_chars: usize,
    /// log-probability charged to an out-of-vocabulary single character.
    unk_penalty: f64,
}

/// A tokenization result: the pieces and the total log-probability.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Segmentation {
    /// The chosen pieces, in order.
    pub pieces: Vec<String>,
    /// The total log-probability of the segmentation under the model.
    pub log_prob: f64,
}

impl UnigramTokenizer {
    /// Build from `(piece, log_probability)` entries. `unk_penalty` is the score
    /// charged when a single character has to be emitted that is not in the
    /// vocabulary (a large negative number, e.g. `-20.0`, discourages it).
    ///
    /// Empty pieces are ignored.
    pub fn new<I, S>(pieces: I, unk_penalty: f64) -> Self
    where
        I: IntoIterator<Item = (S, f64)>,
        S: Into<String>,
    {
        let mut vocab = HashMap::new();
        let mut max_piece_chars = 1; // at least 1 for the single-char fallback
        for (p, lp) in pieces {
            let p = p.into();
            if p.is_empty() {
                continue;
            }
            let len = p.chars().count();
            if len > max_piece_chars {
                max_piece_chars = len;
            }
            vocab.insert(p, lp);
        }
        Self {
            vocab,
            max_piece_chars,
            unk_penalty,
        }
    }

    /// Build from raw piece *counts*, converting to log-probabilities
    /// (`ln(count / total)`). Convenient when a vocabulary is given as frequencies.
    pub fn from_counts<I, S>(counts: I, unk_penalty: f64) -> Self
    where
        I: IntoIterator<Item = (S, u64)>,
        S: Into<String>,
    {
        let entries: Vec<(String, u64)> = counts.into_iter().map(|(s, c)| (s.into(), c)).collect();
        let total: u64 = entries.iter().map(|(_, c)| *c).sum();
        let total = total.max(1) as f64;
        let logged = entries
            .into_iter()
            .filter(|(_, c)| *c > 0)
            .map(|(s, c)| (s, (c as f64 / total).ln()));
        Self::new(logged, unk_penalty)
    }

    /// The vocabulary size.
    pub fn vocab_size(&self) -> usize {
        self.vocab.len()
    }

    /// The log-probability of `piece`, if it is in the vocabulary.
    pub fn piece_log_prob(&self, piece: &str) -> Option<f64> {
        self.vocab.get(piece).copied()
    }

    /// Segment `text` into the maximum-likelihood sequence of pieces.
    pub fn segment(&self, text: &str) -> Segmentation {
        let chars: Vec<char> = text.chars().collect();
        let n = chars.len();
        if n == 0 {
            return Segmentation {
                pieces: Vec::new(),
                log_prob: 0.0,
            };
        }

        // best[i] = best log-prob to segment the first i characters.
        let mut best = vec![f64::NEG_INFINITY; n + 1];
        // back[i] = (start index of the piece ending at i, the piece string).
        let mut back: Vec<(usize, String)> = vec![(0, String::new()); n + 1];
        best[0] = 0.0;

        for i in 1..=n {
            let lo = i.saturating_sub(self.max_piece_chars);
            for j in lo..i {
                if best[j] == f64::NEG_INFINITY {
                    continue;
                }
                let piece: String = chars[j..i].iter().collect();
                let score = match self.vocab.get(&piece) {
                    Some(&lp) => lp,
                    None => {
                        // only allow the fallback for a single character.
                        if i - j == 1 {
                            self.unk_penalty
                        } else {
                            continue;
                        }
                    }
                };
                let cand = best[j] + score;
                if cand > best[i] {
                    best[i] = cand;
                    back[i] = (j, piece);
                }
            }
        }

        // reconstruct
        let mut pieces = Vec::new();
        let mut i = n;
        while i > 0 {
            let (j, piece) = back[i].clone();
            pieces.push(piece);
            i = j;
        }
        pieces.reverse();
        Segmentation {
            pieces,
            log_prob: best[n],
        }
    }

    /// Just the pieces of the best segmentation.
    pub fn tokenize(&self, text: &str) -> Vec<String> {
        self.segment(text).pieces
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // log-prob helper: use natural log of a "probability"
    fn lp(p: f64) -> f64 {
        p.ln()
    }

    #[test]
    fn picks_globally_best_segmentation() {
        // "hello": piece "hello" is more probable than "he"+"llo"
        let t = UnigramTokenizer::new(
            [
                ("hello", lp(0.6)),
                ("he", lp(0.4)),
                ("llo", lp(0.4)),
                ("l", lp(0.1)),
                ("o", lp(0.1)),
                ("h", lp(0.1)),
                ("e", lp(0.1)),
            ],
            -20.0,
        );
        assert_eq!(t.tokenize("hello"), vec!["hello"]);
    }

    #[test]
    fn prefers_two_good_pieces_over_one_weak_long_piece() {
        // "ab": "a"+"b" (each prob .5 → logsum ln.25) beats "ab" (prob .1 → ln.1)
        let t = UnigramTokenizer::new([("ab", lp(0.1)), ("a", lp(0.5)), ("b", lp(0.5))], -20.0);
        assert_eq!(t.tokenize("ab"), vec!["a", "b"]);
    }

    #[test]
    fn higher_prob_long_piece_wins_when_it_should() {
        // make "ab" very likely → it should beat "a"+"b"
        let t = UnigramTokenizer::new([("ab", lp(0.9)), ("a", lp(0.2)), ("b", lp(0.2))], -20.0);
        assert_eq!(t.tokenize("ab"), vec!["ab"]);
    }

    #[test]
    fn single_char_fallback_covers_unknown() {
        // 'z' not in vocab → emitted as a fallback single char with penalty
        let t = UnigramTokenizer::new([("a", lp(0.5)), ("b", lp(0.5))], -20.0);
        let seg = t.segment("azb");
        assert_eq!(seg.pieces, vec!["a", "z", "b"]);
        // the penalty shows up in the score
        assert!(seg.log_prob < lp(0.5) * 2.0);
    }

    #[test]
    fn empty_text_is_empty_segmentation() {
        let t = UnigramTokenizer::new([("a", lp(1.0))], -20.0);
        let seg = t.segment("");
        assert!(seg.pieces.is_empty());
        assert_eq!(seg.log_prob, 0.0);
    }

    #[test]
    fn from_counts_builds_log_probs() {
        // counts 3 and 1 → probs .75 and .25
        let t = UnigramTokenizer::from_counts([("x", 3u64), ("y", 1u64)], -20.0);
        assert!((t.piece_log_prob("x").unwrap() - 0.75f64.ln()).abs() < 1e-12);
        assert!((t.piece_log_prob("y").unwrap() - 0.25f64.ln()).abs() < 1e-12);
    }

    #[test]
    fn reconstruction_concatenates_to_input() {
        let t = UnigramTokenizer::new(
            [
                ("th", lp(0.3)),
                ("e", lp(0.3)),
                ("the", lp(0.3)),
                ("re", lp(0.2)),
                ("t", lp(0.1)),
                ("h", lp(0.1)),
                ("r", lp(0.1)),
            ],
            -20.0,
        );
        for input in ["there", "the", "三", "thethe"] {
            let pieces = t.tokenize(input);
            assert_eq!(pieces.concat(), input, "pieces {pieces:?} != {input}");
        }
    }

    #[test]
    fn handles_multibyte_text() {
        // pieces over CJK characters
        let t = UnigramTokenizer::new(
            [
                ("日本", lp(0.6)),
                ("日", lp(0.2)),
                ("本", lp(0.2)),
                ("語", lp(0.5)),
            ],
            -20.0,
        );
        assert_eq!(t.tokenize("日本語"), vec!["日本", "語"]);
    }

    #[test]
    fn serde_round_trip() {
        let t = UnigramTokenizer::new([("a", lp(0.5)), ("b", lp(0.5))], -10.0);
        let j = serde_json::to_string(&t).unwrap();
        let back: UnigramTokenizer = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
        assert_eq!(back.tokenize("ab"), t.tokenize("ab"));
    }
}
