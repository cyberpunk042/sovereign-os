//! `sovereign-degeneration` — catch the loop/repeat collapse in generations.
//!
//! Left unchecked, decoding can fall into *degeneration*: the model stops
//! producing new content and loops — "I think that I think that I think that…",
//! or a whole paragraph copied over and over. This crate is a cheap post-hoc
//! quality gate that quantifies how degenerate a piece of text is along three
//! complementary axes and flags it against configurable thresholds.
//!
//! - **Longest repeated substring.** Using a suffix array
//!   ([`sovereign_suffix_array`]), the length of the longest substring that
//!   occurs at least twice. A long verbatim repeat is the clearest signature of a
//!   copy-loop.
//! - **rep-n (distinct-n-gram ratio).** The fraction of word n-grams that are
//!   *distinct*; healthy text is near 1, a loop drives it toward 0. This is the
//!   standard repetition metric from the neural-text-degeneration literature.
//! - **Repeat coverage.** The fraction of the text occupied by the occurrences
//!   of its longest repeat — high coverage means the repeat dominates the output.
//!
//! [`analyze`] computes all three into a [`DegenerationReport`]; the `is_degenerate`
//! flag fires when the longest repeat is both long enough and frequent enough, or
//! when distinct-n-gram diversity drops below the floor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_suffix_array::SuffixArray;
use std::collections::HashSet;

/// Schema version of the degeneration surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Thresholds controlling when text is judged degenerate.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Config {
    /// n for the rep-n distinct-n-gram metric (words).
    pub ngram: usize,
    /// Minimum acceptable distinct-n-gram ratio; below this is degenerate.
    pub min_distinct_ratio: f64,
    /// A repeated substring at least this many bytes long counts as a strong
    /// signal (when it also recurs `min_repeat_occurrences` times).
    pub min_repeat_len: usize,
    /// How many times the longest repeat must occur to count as degenerate.
    pub min_repeat_occurrences: usize,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            ngram: 3,
            min_distinct_ratio: 0.5,
            min_repeat_len: 20,
            // The *longest* repeat is maximal, so it recurs ~2x; a 20+ byte
            // verbatim span repeated even twice is already a strong signal.
            min_repeat_occurrences: 2,
        }
    }
}

/// The result of analysing a piece of text.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DegenerationReport {
    /// Length in bytes of the longest substring occurring at least twice.
    pub longest_repeat_len: usize,
    /// How many times that longest repeat occurs.
    pub longest_repeat_occurrences: usize,
    /// The longest repeated substring itself (empty if none).
    pub longest_repeat: String,
    /// Fraction of word n-grams that are distinct (1.0 = no repetition).
    pub distinct_ngram_ratio: f64,
    /// Fraction of the text covered by occurrences of the longest repeat.
    pub repeat_coverage: f64,
    /// Whether the text is judged degenerate under the config.
    pub is_degenerate: bool,
}

/// Analyse `text` for degeneration under `config`.
pub fn analyze(text: &str, config: &Config) -> DegenerationReport {
    let sa = SuffixArray::new(text);
    let lrs_bytes = sa.longest_repeated_substring();
    let longest_repeat = String::from_utf8_lossy(lrs_bytes).to_string();
    let longest_repeat_len = lrs_bytes.len();
    let occurrences = if longest_repeat_len == 0 {
        0
    } else {
        sa.count(lrs_bytes)
    };

    let repeat_coverage = if text.is_empty() {
        0.0
    } else {
        (longest_repeat_len * occurrences).min(text.len()) as f64 / text.len() as f64
    };

    let distinct_ngram_ratio = distinct_ngram_ratio(text, config.ngram);

    let strong_repeat =
        longest_repeat_len >= config.min_repeat_len && occurrences >= config.min_repeat_occurrences;
    let low_diversity = distinct_ngram_ratio < config.min_distinct_ratio;
    let is_degenerate = strong_repeat || low_diversity;

    DegenerationReport {
        longest_repeat_len,
        longest_repeat_occurrences: occurrences,
        longest_repeat,
        distinct_ngram_ratio,
        repeat_coverage,
        is_degenerate,
    }
}

/// The fraction of word `n`-grams in `text` that are distinct (rep-n). Returns
/// `1.0` when there are too few words to form an n-gram (nothing to repeat).
pub fn distinct_ngram_ratio(text: &str, n: usize) -> f64 {
    let words: Vec<&str> = text.split_whitespace().collect();
    if n == 0 || words.len() < n {
        return 1.0;
    }
    let total = words.len() - n + 1;
    let mut seen = HashSet::new();
    for w in words.windows(n) {
        seen.insert(w.join(" "));
    }
    seen.len() as f64 / total as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn healthy_text_is_not_degenerate() {
        let text = "The quick brown fox jumps over the lazy dog while a curious cat \
                    watches from the warm windowsill above the quiet garden path.";
        let r = analyze(text, &Config::default());
        assert!(!r.is_degenerate, "healthy text flagged: {r:?}");
        assert!(
            r.distinct_ngram_ratio > 0.9,
            "ratio {}",
            r.distinct_ngram_ratio
        );
    }

    #[test]
    fn looping_text_is_degenerate() {
        // a classic decoding loop
        let text = "I really think that I really think that I really think that \
                    I really think that I really think that I really think that.";
        let r = analyze(text, &Config::default());
        assert!(r.is_degenerate, "loop not flagged: {r:?}");
        assert!(r.longest_repeat.contains("really think that"));
        // the longest repeat is maximal, so it occurs at least twice
        assert!(r.longest_repeat_occurrences >= 2);
    }

    #[test]
    fn copied_paragraph_is_degenerate() {
        let para = "the system processes each request and returns a structured response ";
        let text = format!("{para}{para}{para}{para}");
        let r = analyze(&text, &Config::default());
        assert!(r.is_degenerate);
        assert!(r.repeat_coverage > 0.5, "coverage {}", r.repeat_coverage);
    }

    #[test]
    fn distinct_ratio_detects_repetition() {
        // every trigram distinct → ratio 1.0
        assert_eq!(distinct_ngram_ratio("a b c d e f g", 3), 1.0);
        // pure repetition → low ratio
        let loopy = "x y z x y z x y z x y z";
        assert!(
            distinct_ngram_ratio(loopy, 3) < 0.5,
            "{}",
            distinct_ngram_ratio(loopy, 3)
        );
    }

    #[test]
    fn distinct_ratio_handles_short_text() {
        assert_eq!(distinct_ngram_ratio("only two", 3), 1.0); // fewer words than n
        assert_eq!(distinct_ngram_ratio("", 3), 1.0);
        assert_eq!(distinct_ngram_ratio("a b c", 0), 1.0);
    }

    #[test]
    fn empty_text_is_clean() {
        let r = analyze("", &Config::default());
        assert_eq!(r.longest_repeat_len, 0);
        assert_eq!(r.longest_repeat_occurrences, 0);
        assert_eq!(r.repeat_coverage, 0.0);
        assert!(!r.is_degenerate);
    }

    #[test]
    fn config_thresholds_are_respected() {
        let text = "ab ab ab ab ab ab ab ab";
        // strict config flags it; lenient config does not
        let strict = Config {
            ngram: 2,
            min_distinct_ratio: 0.9,
            min_repeat_len: 2,
            min_repeat_occurrences: 2,
        };
        assert!(analyze(text, &strict).is_degenerate);

        let lenient = Config {
            ngram: 2,
            min_distinct_ratio: 0.01,
            min_repeat_len: 1000,
            min_repeat_occurrences: 1000,
        };
        assert!(!analyze(text, &lenient).is_degenerate);
    }

    #[test]
    fn report_serde_round_trip() {
        let r = analyze("a b a b a b a b", &Config::default());
        let j = serde_json::to_string(&r).unwrap();
        let back: DegenerationReport = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
