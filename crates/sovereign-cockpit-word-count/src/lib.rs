//! `sovereign-cockpit-word-count` — text content counters.
//!
//! count(text, wpm) returns Stats{chars (all chars), chars_no_ws
//! (excluding whitespace), words (Unicode-whitespace-split, non-empty
//! runs), reading_time_ms = words * 60_000 / wpm}.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Stats.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Stats {
    /// All characters.
    pub chars: u64,
    /// Characters excluding whitespace.
    pub chars_no_ws: u64,
    /// Words.
    pub words: u64,
    /// Reading time ms at given WPM.
    pub reading_time_ms: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CountError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero WPM.
    #[error("wpm must be >= 1")]
    ZeroWpm,
}

/// Count.
pub fn count(text: &str, wpm: u32) -> Result<Stats, CountError> {
    if wpm == 0 {
        return Err(CountError::ZeroWpm);
    }
    let chars = text.chars().count() as u64;
    let chars_no_ws = text.chars().filter(|c| !c.is_whitespace()).count() as u64;
    let words = text.split_whitespace().filter(|w| !w.is_empty()).count() as u64;
    let reading_time_ms = words.saturating_mul(60_000) / (wpm as u64);
    Ok(Stats {
        chars,
        chars_no_ws,
        words,
        reading_time_ms,
    })
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), CountError> {
    if s != SCHEMA_VERSION {
        return Err(CountError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_text() {
        let s = count("", 200).unwrap();
        assert_eq!(
            s,
            Stats {
                chars: 0,
                chars_no_ws: 0,
                words: 0,
                reading_time_ms: 0
            }
        );
    }

    #[test]
    fn single_word() {
        let s = count("hello", 200).unwrap();
        assert_eq!(s.chars, 5);
        assert_eq!(s.chars_no_ws, 5);
        assert_eq!(s.words, 1);
    }

    #[test]
    fn multiple_words_and_whitespace() {
        let s = count("hello world friend", 200).unwrap();
        assert_eq!(s.words, 3);
        assert_eq!(s.chars, 18);
        assert_eq!(s.chars_no_ws, 16);
    }

    #[test]
    fn reading_time_scales_with_wpm() {
        // 200 words at 200 wpm = 60_000 ms.
        let text: String = (0..200).map(|_| "x ").collect();
        let s = count(text.trim(), 200).unwrap();
        assert_eq!(s.words, 200);
        assert_eq!(s.reading_time_ms, 60_000);
    }

    #[test]
    fn leading_trailing_whitespace_ignored_for_words() {
        let s = count("   hello   ", 200).unwrap();
        assert_eq!(s.words, 1);
    }

    #[test]
    fn unicode_whitespace_handled() {
        // U+3000 IDEOGRAPHIC SPACE is whitespace under Unicode rules.
        let s = count("a\u{3000}b", 200).unwrap();
        assert_eq!(s.words, 2);
    }

    #[test]
    fn zero_wpm_rejected() {
        assert!(matches!(count("x", 0).unwrap_err(), CountError::ZeroWpm));
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            CountError::SchemaMismatch
        ));
    }

    #[test]
    fn stats_serde_roundtrip() {
        let s = count("hello world", 200).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: Stats = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
