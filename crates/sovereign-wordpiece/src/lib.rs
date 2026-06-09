//! `sovereign-wordpiece` — greedy subword tokenization, the BERT scheme.
//!
//! WordPiece sits between character and word tokenization: a fixed vocabulary
//! holds whole words *and* word-pieces, and any word is split into the longest
//! vocabulary pieces that cover it. Pieces that continue a word (i.e. don't start
//! it) are written with a `##` prefix, so `playing` becomes `play ##ing` and the
//! `##` lets detokenization glue the pieces back without a space. A word the
//! vocabulary cannot cover at all becomes a single `[UNK]`.
//!
//! Tokenization is **greedy longest-match-first from the left**: at each position
//! take the longest piece in the vocabulary that matches there (with the `##`
//! prefix once past the first piece); if no piece matches at some position, the
//! *whole word* is unknown — that is the defining rule of WordPiece, and it is
//! why a vocabulary normally includes every single character so coverage is
//! guaranteed. A configurable `max_input_chars_per_word` caps pathological long
//! tokens straight to `[UNK]`.
//!
//! Tokenization runs over Unicode scalar values (`char`s), so the `##` boundaries
//! never split a multi-byte character.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// Schema version of the WordPiece surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The continuation prefix marking a non-initial word-piece.
pub const CONTINUATION: &str = "##";

/// A WordPiece tokenizer over a fixed vocabulary.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WordPiece {
    vocab: HashSet<String>,
    unk: String,
    max_input_chars_per_word: usize,
}

impl WordPiece {
    /// Build from a vocabulary and an unknown-token string.
    ///
    /// The vocabulary should contain the continuation pieces *with* their `##`
    /// prefix exactly as they will be emitted (e.g. `"##ing"`), and word-initial
    /// pieces without it. `max_input_chars_per_word` defaults to 100 here.
    pub fn new<I, S>(vocab: I, unk: impl Into<String>) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        Self {
            vocab: vocab.into_iter().map(Into::into).collect(),
            unk: unk.into(),
            max_input_chars_per_word: 100,
        }
    }

    /// Override the per-word character cap (words longer than this become
    /// `[UNK]` without any matching attempt).
    pub fn with_max_input_chars(mut self, max: usize) -> Self {
        self.max_input_chars_per_word = max;
        self
    }

    /// The unknown token.
    pub fn unk(&self) -> &str {
        &self.unk
    }

    /// The vocabulary size.
    pub fn vocab_size(&self) -> usize {
        self.vocab.len()
    }

    /// Whether `piece` (written exactly as it would be emitted, with any `##`
    /// prefix) is in the vocabulary.
    pub fn contains(&self, piece: &str) -> bool {
        self.vocab.contains(piece)
    }

    /// Tokenize a single whitespace-free word into vocabulary pieces. Returns the
    /// `[UNK]` token (as a one-element vector) if the word is too long or cannot
    /// be fully covered.
    pub fn tokenize_word(&self, word: &str) -> Vec<String> {
        let chars: Vec<char> = word.chars().collect();
        if chars.is_empty() {
            return Vec::new();
        }
        if chars.len() > self.max_input_chars_per_word {
            return vec![self.unk.clone()];
        }

        let mut pieces = Vec::new();
        let mut start = 0usize;
        while start < chars.len() {
            // longest match starting at `start`
            let mut end = chars.len();
            let mut found: Option<String> = None;
            while start < end {
                let mut candidate: String = if start > 0 {
                    CONTINUATION.to_string()
                } else {
                    String::new()
                };
                candidate.extend(&chars[start..end]);
                if self.vocab.contains(&candidate) {
                    found = Some(candidate);
                    break;
                }
                end -= 1;
            }
            match found {
                Some(piece) => {
                    pieces.push(piece);
                    start = end;
                }
                None => {
                    // No piece matches here → the whole word is unknown.
                    return vec![self.unk.clone()];
                }
            }
        }
        pieces
    }

    /// Tokenize text: split on whitespace, then tokenize each word, concatenating
    /// the pieces.
    pub fn tokenize(&self, text: &str) -> Vec<String> {
        text.split_whitespace()
            .flat_map(|w| self.tokenize_word(w))
            .collect()
    }

    /// Reassemble pieces back into text: a `##` piece glues onto the previous
    /// token, every other piece starts a new whitespace-separated word. `[UNK]`
    /// tokens are emitted literally (the original surface form is unrecoverable).
    pub fn detokenize(&self, pieces: &[String]) -> String {
        let mut out = String::new();
        for piece in pieces {
            if let Some(rest) = piece.strip_prefix(CONTINUATION) {
                out.push_str(rest);
            } else {
                if !out.is_empty() {
                    out.push(' ');
                }
                out.push_str(piece);
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tokenizer() -> WordPiece {
        // classic WordPiece example vocabulary
        WordPiece::new(
            [
                "un", "##aff", "##able", "play", "##ing", "##ed", "word", "##s", "a", "b", "c",
            ],
            "[UNK]",
        )
    }

    #[test]
    fn splits_into_longest_pieces() {
        let t = tokenizer();
        assert_eq!(t.tokenize_word("unaffable"), vec!["un", "##aff", "##able"]);
        assert_eq!(t.tokenize_word("playing"), vec!["play", "##ing"]);
        assert_eq!(t.tokenize_word("played"), vec!["play", "##ed"]);
        assert_eq!(t.tokenize_word("words"), vec!["word", "##s"]);
    }

    #[test]
    fn whole_word_unknown_when_uncoverable() {
        let t = tokenizer();
        // 'x' is not in the vocab at any position → whole word is [UNK]
        assert_eq!(t.tokenize_word("xyz"), vec!["[UNK]"]);
        // even a word that starts coverable but can't finish is fully [UNK]
        assert_eq!(t.tokenize_word("playzz"), vec!["[UNK]"]);
    }

    #[test]
    fn greedy_prefers_the_longest_initial_match() {
        // "word" should win over a hypothetical shorter "wo" because we match
        // longest-first; here only "word" exists so it's unambiguous, but verify
        // the boundary: "word" + "##s"
        let t = tokenizer();
        assert_eq!(t.tokenize_word("words"), vec!["word", "##s"]);
    }

    #[test]
    fn tokenize_handles_multiple_words() {
        let t = tokenizer();
        let toks = t.tokenize("playing words");
        assert_eq!(toks, vec!["play", "##ing", "word", "##s"]);
    }

    #[test]
    fn empty_and_whitespace() {
        let t = tokenizer();
        assert!(t.tokenize_word("").is_empty());
        assert!(t.tokenize("   ").is_empty());
        assert!(t.tokenize("").is_empty());
    }

    #[test]
    fn max_chars_forces_unk() {
        let t = tokenizer().with_max_input_chars(3);
        // "playing" is 7 chars > 3 → straight to [UNK]
        assert_eq!(t.tokenize_word("playing"), vec!["[UNK]"]);
        // a short coverable word still works
        assert_eq!(t.tokenize_word("un"), vec!["un"]);
    }

    #[test]
    fn detokenize_inverts_known_tokenization() {
        let t = tokenizer();
        let toks = t.tokenize("playing words");
        // "play##ing" -> "playing", "word##s" -> "words"
        assert_eq!(t.detokenize(&toks), "playing words");
    }

    #[test]
    fn detokenize_continuation_gluing() {
        let t = tokenizer();
        let pieces: Vec<String> = ["un", "##aff", "##able"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        assert_eq!(t.detokenize(&pieces), "unaffable");
    }

    #[test]
    fn multibyte_characters_are_not_split() {
        // vocabulary with a multi-byte initial and continuation
        let t = WordPiece::new(["café", "##é", "ca", "##fé"], "[UNK]");
        // "café" matches whole
        assert_eq!(t.tokenize_word("café"), vec!["café"]);
        // "café" also coverable as "ca" + "##fé"
        let t2 = WordPiece::new(["ca", "##fé"], "[UNK]");
        assert_eq!(t2.tokenize_word("café"), vec!["ca", "##fé"]);
    }

    #[test]
    fn serde_round_trip() {
        let t = tokenizer();
        let j = serde_json::to_string(&t).unwrap();
        let back: WordPiece = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
        assert_eq!(back.tokenize_word("playing"), vec!["play", "##ing"]);
    }
}
