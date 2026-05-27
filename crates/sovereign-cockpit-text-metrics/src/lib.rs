//! `sovereign-cockpit-text-metrics` — text metrics for the cockpit.
//!
//! `measure(text)` returns:
//!   * `bytes` — len() in bytes.
//!   * `chars` — `text.chars().count()` (UTF-8 codepoints).
//!   * `graphemes` — best-effort grapheme count without `unicode-
//!     segmentation`: count codepoints whose category is not a
//!     combining mark, ZWJ, or variation selector.
//!   * `words` — `split_whitespace().count()`.
//!   * `lines` — `split('\n').count()` (matches `wc -l + 1` style).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Measured metrics.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct TextMetrics {
    /// Bytes.
    pub bytes: usize,
    /// Codepoints.
    pub chars: usize,
    /// Graphemes (best-effort).
    pub graphemes: usize,
    /// Words.
    pub words: usize,
    /// Lines.
    pub lines: usize,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CockpitTextMetrics {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MetricsError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl CockpitTextMetrics {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    /// Measure.
    pub fn measure(&self, text: &str) -> TextMetrics {
        let bytes = text.len();
        let chars = text.chars().count();
        let mut graphemes = 0usize;
        for ch in text.chars() {
            if !is_combining_or_joiner(ch) {
                graphemes += 1;
            }
        }
        let words = text.split_whitespace().count();
        let lines = if text.is_empty() {
            0
        } else {
            text.split('\n').count()
        };
        TextMetrics {
            bytes,
            chars,
            graphemes,
            words,
            lines,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MetricsError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MetricsError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for CockpitTextMetrics {
    fn default() -> Self {
        Self::new()
    }
}

fn is_combining_or_joiner(c: char) -> bool {
    match c as u32 {
        0x0300..=0x036F => true,   // combining diacritical
        0x1AB0..=0x1AFF => true,   // combining diacritical extended
        0x1DC0..=0x1DFF => true,   // combining diacritical supplement
        0x20D0..=0x20FF => true,   // combining for symbols
        0xFE00..=0xFE0F => true,   // variation selectors
        0xE0100..=0xE01EF => true, // variation selectors supplement
        0x200C | 0x200D => true,   // ZWNJ / ZWJ
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_text() {
        let m = CockpitTextMetrics::new().measure("");
        assert_eq!(
            m,
            TextMetrics {
                bytes: 0,
                chars: 0,
                graphemes: 0,
                words: 0,
                lines: 0
            }
        );
    }

    #[test]
    fn ascii_simple() {
        let m = CockpitTextMetrics::new().measure("hello world");
        assert_eq!(m.bytes, 11);
        assert_eq!(m.chars, 11);
        assert_eq!(m.graphemes, 11);
        assert_eq!(m.words, 2);
        assert_eq!(m.lines, 1);
    }

    #[test]
    fn multi_line() {
        let m = CockpitTextMetrics::new().measure("a\nb\nc");
        assert_eq!(m.lines, 3);
    }

    #[test]
    fn utf8_chars_vs_bytes() {
        // 3 codepoints, 7 bytes (é=2, ñ=2, c=1) plus literal differences.
        let m = CockpitTextMetrics::new().measure("éñc");
        assert_eq!(m.chars, 3);
        assert!(m.bytes > 3);
    }

    #[test]
    fn combining_marks_drop_grapheme_count() {
        // "e" + combining acute (U+0301) → 2 chars but 1 grapheme.
        let s = "e\u{0301}";
        let m = CockpitTextMetrics::new().measure(s);
        assert_eq!(m.chars, 2);
        assert_eq!(m.graphemes, 1);
    }

    #[test]
    fn zwj_emoji_sequence() {
        // Family emoji 👨‍👩‍👧 = man + ZWJ + woman + ZWJ + girl → 5 cps, 3 graphemes (best-effort).
        let s = "\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}";
        let m = CockpitTextMetrics::new().measure(s);
        assert_eq!(m.chars, 5);
        assert_eq!(m.graphemes, 3);
    }

    #[test]
    fn words_split_on_whitespace() {
        let m = CockpitTextMetrics::new().measure("  foo  bar\tbaz\nqux  ");
        assert_eq!(m.words, 4);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = CockpitTextMetrics::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            MetricsError::SchemaMismatch
        ));
    }

    #[test]
    fn metrics_serde_roundtrip() {
        let c = CockpitTextMetrics::new();
        let j = serde_json::to_string(&c).unwrap();
        let back: CockpitTextMetrics = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
