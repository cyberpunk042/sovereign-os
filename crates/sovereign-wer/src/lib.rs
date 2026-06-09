//! `sovereign-wer` — how wrong is a transcription, word by word.
//!
//! Word Error Rate is the standard way to score a hypothesis transcription
//! against a reference: align the two word sequences, count the **substitutions**,
//! **insertions**, and **deletions** needed to turn the reference into the
//! hypothesis, and divide by the number of reference words —
//! `WER = (S + I + D) / N`. Unlike a bag-of-words overlap it respects order, and
//! unlike BLEU/ROUGE it is an *error* rate (lower is better, `0` is perfect, and
//! it can exceed `1` when the hypothesis is much longer than the reference).
//!
//! This crate computes WER and its **Character Error Rate** sibling (the same
//! over characters, useful for languages without clear word boundaries or for
//! fine-grained scoring), and returns the full [`ErrorBreakdown`] — the S/I/D
//! counts that say *how* the transcription went wrong, not just *how much*.
//! Alignment is delegated to [`sovereign_edit_align`].
//!
//! Tokenization for [`word_error_rate`] is lowercase whitespace splitting; pass
//! pre-tokenized words to [`wer_tokens`] for full control.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_edit_align::{align, summary};

/// Schema version of the wer surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A full error breakdown.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct ErrorBreakdown {
    /// The error rate `(S + I + D) / N`.
    pub error_rate: f64,
    /// Substitution count.
    pub substitutions: usize,
    /// Insertion count.
    pub insertions: usize,
    /// Deletion count.
    pub deletions: usize,
    /// Number of reference units (the denominator `N`).
    pub reference_len: usize,
}

impl ErrorBreakdown {
    /// The total number of errors (`S + I + D`).
    pub fn total_errors(&self) -> usize {
        self.substitutions + self.insertions + self.deletions
    }
}

/// Error breakdown between pre-tokenized `reference` and `hypothesis` unit slices.
/// With an empty reference, the rate is 0 if the hypothesis is also empty, else
/// the insertion count itself (every hypothesis unit is an error).
pub fn breakdown<T: PartialEq>(reference: &[T], hypothesis: &[T]) -> ErrorBreakdown {
    let ops = align(reference, hypothesis);
    let s = summary(&ops);
    let n = reference.len();
    let total = s.substitutions + s.insertions + s.deletions;
    let error_rate = if n == 0 {
        if total == 0 { 0.0 } else { total as f64 }
    } else {
        total as f64 / n as f64
    };
    ErrorBreakdown {
        error_rate,
        substitutions: s.substitutions,
        insertions: s.insertions,
        deletions: s.deletions,
        reference_len: n,
    }
}

/// Word Error Rate between two pre-tokenized word slices.
pub fn wer_tokens(reference: &[&str], hypothesis: &[&str]) -> ErrorBreakdown {
    breakdown(reference, hypothesis)
}

/// Word Error Rate between `reference` and `hypothesis` strings (lowercase
/// whitespace tokenization).
pub fn word_error_rate(reference: &str, hypothesis: &str) -> ErrorBreakdown {
    let r: Vec<String> = reference
        .split_whitespace()
        .map(|w| w.to_lowercase())
        .collect();
    let h: Vec<String> = hypothesis
        .split_whitespace()
        .map(|w| w.to_lowercase())
        .collect();
    breakdown(&r, &h)
}

/// Character Error Rate between `reference` and `hypothesis` strings (over chars,
/// whitespace included as written).
pub fn character_error_rate(reference: &str, hypothesis: &str) -> ErrorBreakdown {
    let r: Vec<char> = reference.chars().collect();
    let h: Vec<char> = hypothesis.chars().collect();
    breakdown(&r, &h)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn perfect_transcription_is_zero() {
        let b = word_error_rate("the quick brown fox", "the quick brown fox");
        assert!(approx(b.error_rate, 0.0));
        assert_eq!(b.total_errors(), 0);
    }

    #[test]
    fn one_substitution() {
        // 4 reference words, one wrong → WER 1/4
        let b = word_error_rate("the quick brown fox", "the quick green fox");
        assert!(approx(b.error_rate, 0.25), "{}", b.error_rate);
        assert_eq!(b.substitutions, 1);
        assert_eq!(b.insertions, 0);
        assert_eq!(b.deletions, 0);
        assert_eq!(b.reference_len, 4);
    }

    #[test]
    fn insertion_and_deletion() {
        // reference 3 words; hypothesis adds one and drops one
        let ins = word_error_rate("a b c", "a b c d");
        assert_eq!(ins.insertions, 1);
        assert!(approx(ins.error_rate, 1.0 / 3.0));

        let del = word_error_rate("a b c d", "a b c");
        assert_eq!(del.deletions, 1);
        assert!(approx(del.error_rate, 0.25));
    }

    #[test]
    fn mixed_errors_textbook() {
        // ref: "the cat sat on the mat" (6 words)
        // hyp: "the cat sit on mat"  → sub(sat→sit), del(the), ... let's just
        // check the rate equals (S+I+D)/6 from the breakdown.
        let b = word_error_rate("the cat sat on the mat", "the cat sit on mat");
        assert_eq!(b.reference_len, 6);
        let expected = b.total_errors() as f64 / 6.0;
        assert!(approx(b.error_rate, expected));
        assert!(b.total_errors() >= 2); // at least a sub and a deletion
    }

    #[test]
    fn case_insensitive_word_matching() {
        let b = word_error_rate("The Quick Fox", "the quick fox");
        assert!(approx(b.error_rate, 0.0));
    }

    #[test]
    fn character_error_rate_basic() {
        // "kitten" -> "sitting": 3 edits over 6 chars → CER 0.5
        let b = character_error_rate("kitten", "sitting");
        assert!(approx(b.error_rate, 0.5), "{}", b.error_rate);
        assert_eq!(b.total_errors(), 3);
    }

    #[test]
    fn wer_can_exceed_one() {
        // hypothesis much longer than reference → many insertions
        let b = word_error_rate("hello", "hello there how are you today friend");
        assert!(b.error_rate > 1.0, "{}", b.error_rate);
    }

    #[test]
    fn empty_reference_cases() {
        assert!(approx(word_error_rate("", "").error_rate, 0.0));
        // empty reference, non-empty hypothesis → error rate = insertion count
        let b = word_error_rate("", "two words");
        assert!(approx(b.error_rate, 2.0));
    }

    #[test]
    fn pre_tokenized_interface() {
        let r = ["the", "cat", "sat"];
        let h = ["the", "dog", "sat"];
        let b = wer_tokens(&r, &h);
        assert!(approx(b.error_rate, 1.0 / 3.0));
        assert_eq!(b.substitutions, 1);
    }

    #[test]
    fn serde_round_trip() {
        let b = word_error_rate("a b c", "a x c");
        let j = serde_json::to_string(&b).unwrap();
        let back: ErrorBreakdown = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
