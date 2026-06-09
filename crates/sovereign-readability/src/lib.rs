//! `sovereign-readability` — is this text written for the right audience?
//!
//! A generated answer can be correct yet pitched wrong — a graduate-level wall of
//! clauses where a one-sentence reply was wanted, or baby-talk where precision was
//! needed. Readability formulas turn that intuition into a number from three
//! cheap signals: how long the sentences are, how long the words are, and how many
//! syllables those words carry.
//!
//! - **Flesch Reading Ease** ([`flesch_reading_ease`]): higher is easier
//!   (roughly 90–100 = 5th grade, 60–70 = plain English, 0–30 = academic).
//! - **Flesch-Kincaid Grade Level** ([`flesch_kincaid_grade`]): the US school
//!   grade needed to read the text (8.0 ≈ eighth grade).
//! - **Automated Readability Index** ([`automated_readability_index`]): a
//!   character-based grade estimate that avoids syllable counting.
//!
//! [`analyze`] returns all three plus the underlying counts in a [`Readability`].
//! Sentence segmentation is delegated to [`sovereign_sentence_split`] (so
//! abbreviations and decimals don't inflate the sentence count), and syllables are
//! counted with the standard vowel-group heuristic (adjacent vowels count once, a
//! silent trailing `e` is dropped, every word gets at least one).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the readability surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A full readability analysis.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Readability {
    /// Flesch Reading Ease (higher = easier).
    pub flesch_reading_ease: f64,
    /// Flesch-Kincaid Grade Level (US school grade).
    pub flesch_kincaid_grade: f64,
    /// Automated Readability Index (character-based grade).
    pub automated_readability_index: f64,
    /// Number of sentences.
    pub sentences: usize,
    /// Number of words.
    pub words: usize,
    /// Number of syllables.
    pub syllables: usize,
    /// Number of alphanumeric characters (for ARI).
    pub characters: usize,
}

/// Count the syllables of a single word with the vowel-group heuristic.
pub fn syllables(word: &str) -> usize {
    let w: Vec<char> = word
        .chars()
        .filter(|c| c.is_alphabetic())
        .flat_map(|c| c.to_lowercase())
        .collect();
    if w.is_empty() {
        return 0;
    }
    let is_vowel = |c: char| matches!(c, 'a' | 'e' | 'i' | 'o' | 'u' | 'y');
    let mut count = 0usize;
    let mut prev_vowel = false;
    for &c in &w {
        let v = is_vowel(c);
        if v && !prev_vowel {
            count += 1;
        }
        prev_vowel = v;
    }
    // silent trailing 'e' ("make" → 1), but NOT a consonant + "le" ending, where
    // the "le" forms its own syllable ("apple" → 2, "table" → 2).
    let len = w.len();
    if len > 2 && w[len - 1] == 'e' && !is_vowel(w[len - 2]) {
        let consonant_le = len >= 3 && w[len - 2] == 'l' && !is_vowel(w[len - 3]);
        if !consonant_le {
            count = count.saturating_sub(1);
        }
    }
    count.max(1)
}

/// The text statistics needed by the formulas: `(sentences, words, syllables,
/// characters)`. A text with no sentence terminator still counts as one sentence
/// if it has words.
fn stats(text: &str) -> (usize, usize, usize, usize) {
    let sentence_count = sovereign_sentence_split::split(text).len();
    let words: Vec<&str> = text.split_whitespace().collect();
    let word_count = words.len();
    let sentences = if sentence_count == 0 && word_count > 0 {
        1
    } else {
        sentence_count
    };
    let syllable_count: usize = words.iter().map(|w| syllables(w)).sum();
    let char_count: usize = words
        .iter()
        .map(|w| w.chars().filter(|c| c.is_alphanumeric()).count())
        .sum();
    (sentences, word_count, syllable_count, char_count)
}

/// Flesch Reading Ease of `text` (higher = easier). Returns 0 for empty text.
pub fn flesch_reading_ease(text: &str) -> f64 {
    let (s, w, syl, _) = stats(text);
    if s == 0 || w == 0 {
        return 0.0;
    }
    206.835 - 1.015 * (w as f64 / s as f64) - 84.6 * (syl as f64 / w as f64)
}

/// Flesch-Kincaid Grade Level of `text`. Returns 0 for empty text.
pub fn flesch_kincaid_grade(text: &str) -> f64 {
    let (s, w, syl, _) = stats(text);
    if s == 0 || w == 0 {
        return 0.0;
    }
    0.39 * (w as f64 / s as f64) + 11.8 * (syl as f64 / w as f64) - 15.59
}

/// Automated Readability Index of `text`. Returns 0 for empty text.
pub fn automated_readability_index(text: &str) -> f64 {
    let (s, w, _, chars) = stats(text);
    if s == 0 || w == 0 {
        return 0.0;
    }
    4.71 * (chars as f64 / w as f64) + 0.5 * (w as f64 / s as f64) - 21.43
}

/// Compute all readability metrics and the underlying counts.
pub fn analyze(text: &str) -> Readability {
    let (s, w, syl, chars) = stats(text);
    let (fre, fk, ari) = if s == 0 || w == 0 {
        (0.0, 0.0, 0.0)
    } else {
        (
            206.835 - 1.015 * (w as f64 / s as f64) - 84.6 * (syl as f64 / w as f64),
            0.39 * (w as f64 / s as f64) + 11.8 * (syl as f64 / w as f64) - 15.59,
            4.71 * (chars as f64 / w as f64) + 0.5 * (w as f64 / s as f64) - 21.43,
        )
    };
    Readability {
        flesch_reading_ease: fre,
        flesch_kincaid_grade: fk,
        automated_readability_index: ari,
        sentences: s,
        words: w,
        syllables: syl,
        characters: chars,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn syllable_counts() {
        assert_eq!(syllables("cat"), 1);
        assert_eq!(syllables("apple"), 2);
        assert_eq!(syllables("readability"), 5); // rea-da-bil-i-ty (heuristic)
        assert_eq!(syllables("the"), 1);
        assert_eq!(syllables("make"), 1); // silent e
        assert_eq!(syllables("queue"), 1); // adjacent vowels count once-ish
        assert_eq!(syllables(""), 0);
        assert_eq!(syllables("rhythm"), 1); // at least one
    }

    #[test]
    fn simple_text_is_easy() {
        // short words, short sentences → high reading ease, low grade.
        let text = "The cat sat. The dog ran. We had fun.";
        let r = analyze(text);
        assert!(
            r.flesch_reading_ease > 80.0,
            "FRE {}",
            r.flesch_reading_ease
        );
        assert!(
            r.flesch_kincaid_grade < 4.0,
            "FK {}",
            r.flesch_kincaid_grade
        );
        assert_eq!(r.sentences, 3);
    }

    #[test]
    fn complex_text_is_harder() {
        let simple = "I like dogs. They are fun. We play a lot.";
        let complex = "The implementation demonstrates considerable architectural \
                       sophistication, necessitating comprehensive familiarity with \
                       numerous interdependent subsystems and their configurations.";
        let s = analyze(simple);
        let c = analyze(complex);
        assert!(c.flesch_reading_ease < s.flesch_reading_ease);
        assert!(c.flesch_kincaid_grade > s.flesch_kincaid_grade);
    }

    #[test]
    fn grade_levels_are_ordered_by_difficulty() {
        let easy = "See the cat. The cat is big.";
        let hard = "Notwithstanding the aforementioned considerations, the committee \
                    deliberated extensively regarding the multifaceted implications.";
        assert!(flesch_kincaid_grade(hard) > flesch_kincaid_grade(easy));
        assert!(automated_readability_index(hard) > automated_readability_index(easy));
    }

    #[test]
    fn single_sentence_no_terminator() {
        let r = analyze("just a few simple words here");
        assert_eq!(r.sentences, 1);
        assert_eq!(r.words, 6);
        assert!(r.flesch_reading_ease > 0.0);
    }

    #[test]
    fn empty_text() {
        let r = analyze("");
        assert_eq!(r.words, 0);
        assert_eq!(r.flesch_reading_ease, 0.0);
        assert_eq!(flesch_kincaid_grade(""), 0.0);
        assert_eq!(automated_readability_index("   "), 0.0);
    }

    #[test]
    fn counts_are_consistent() {
        let r = analyze("The quick brown fox jumps.");
        assert_eq!(r.words, 5);
        assert_eq!(r.sentences, 1);
        assert!(r.syllables >= 5); // at least one each
        assert!(r.characters > 0);
    }

    #[test]
    fn serde_round_trip() {
        let r = analyze("Some example text for serialization testing here today.");
        let j = serde_json::to_string(&r).unwrap();
        let back: Readability = serde_json::from_str(&j).unwrap();
        // integer counts round-trip exactly; floats may shift a ULP through JSON
        assert_eq!(r.words, back.words);
        assert_eq!(r.sentences, back.sentences);
        assert_eq!(r.syllables, back.syllables);
        assert!((r.flesch_reading_ease - back.flesch_reading_ease).abs() < 1e-9);
        assert!((r.flesch_kincaid_grade - back.flesch_kincaid_grade).abs() < 1e-9);
    }
}
