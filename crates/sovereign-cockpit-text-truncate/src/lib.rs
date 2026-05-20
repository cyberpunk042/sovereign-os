//! `sovereign-cockpit-text-truncate` — string truncation.
//!
//! Mode{Start/Middle/End} + max_chars (>= ellipsis.chars().count()
//! + 1). Operates on Unicode scalar chars (not bytes). Strings
//! shorter than max_chars pass through unchanged.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Mode.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Truncate from the start ("...lorem").
    Start,
    /// Truncate the middle ("lor...rem").
    Middle,
    /// Truncate from the end ("lorem...").
    End,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TextTruncate {
    /// Schema version.
    pub schema_version: String,
    /// Mode.
    pub mode: Mode,
    /// Max char length (>= ellipsis.chars().count() + 1).
    pub max_chars: u32,
    /// Ellipsis string.
    pub ellipsis: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TruncateError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad max_chars.
    #[error("max_chars must be >= ellipsis length + 1")]
    BadMaxChars,
    /// Empty ellipsis.
    #[error("ellipsis empty")]
    EmptyEllipsis,
}

impl TextTruncate {
    /// New.
    pub fn new(mode: Mode, max_chars: u32, ellipsis: &str) -> Result<Self, TruncateError> {
        if ellipsis.is_empty() { return Err(TruncateError::EmptyEllipsis); }
        let ell_n = ellipsis.chars().count() as u32;
        if max_chars < ell_n + 1 { return Err(TruncateError::BadMaxChars); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            mode,
            max_chars,
            ellipsis: ellipsis.into(),
        })
    }

    /// Truncate.
    pub fn apply(&self, input: &str) -> String {
        let chars: Vec<char> = input.chars().collect();
        let n = chars.len();
        let max = self.max_chars as usize;
        if n <= max { return input.into(); }
        let ell_n = self.ellipsis.chars().count();
        let keep = max - ell_n;
        match self.mode {
            Mode::End => {
                let head: String = chars[..keep].iter().collect();
                format!("{}{}", head, self.ellipsis)
            }
            Mode::Start => {
                let tail: String = chars[n - keep..].iter().collect();
                format!("{}{}", self.ellipsis, tail)
            }
            Mode::Middle => {
                let left = keep / 2;
                let right = keep - left;
                let head: String = chars[..left].iter().collect();
                let tail: String = chars[n - right..].iter().collect();
                format!("{}{}{}", head, self.ellipsis, tail)
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TruncateError> {
        if self.schema_version != SCHEMA_VERSION { return Err(TruncateError::SchemaMismatch); }
        if self.ellipsis.is_empty() { return Err(TruncateError::EmptyEllipsis); }
        let ell_n = self.ellipsis.chars().count() as u32;
        if self.max_chars < ell_n + 1 { return Err(TruncateError::BadMaxChars); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn short_string_pass_through() {
        let t = TextTruncate::new(Mode::End, 10, "…").unwrap();
        assert_eq!(t.apply("hello"), "hello");
    }

    #[test]
    fn end_truncate() {
        let t = TextTruncate::new(Mode::End, 8, "…").unwrap();
        // keep = 7 chars + 1 ellipsis = 8.
        assert_eq!(t.apply("abcdefghijkl"), "abcdefg…");
    }

    #[test]
    fn start_truncate() {
        let t = TextTruncate::new(Mode::Start, 8, "…").unwrap();
        assert_eq!(t.apply("abcdefghijkl"), "…fghijkl");
    }

    #[test]
    fn middle_truncate() {
        let t = TextTruncate::new(Mode::Middle, 9, "…").unwrap();
        // keep = 8; left=4, right=4. "abcdefghijkl" → "abcd…ijkl"
        assert_eq!(t.apply("abcdefghijkl"), "abcd…ijkl");
    }

    #[test]
    fn multibyte_chars_counted_correctly() {
        let t = TextTruncate::new(Mode::End, 5, "…").unwrap();
        // 4 chars then ellipsis.
        assert_eq!(t.apply("αβγδεζη"), "αβγδ…");
    }

    #[test]
    fn multichar_ellipsis() {
        let t = TextTruncate::new(Mode::End, 10, "...").unwrap();
        // keep = 7.
        assert_eq!(t.apply("abcdefghijkl"), "abcdefg...");
    }

    #[test]
    fn bad_max_chars_rejected() {
        assert!(matches!(
            TextTruncate::new(Mode::End, 1, "..").unwrap_err(),
            TruncateError::BadMaxChars
        ));
    }

    #[test]
    fn empty_ellipsis_rejected() {
        assert!(matches!(
            TextTruncate::new(Mode::End, 10, "").unwrap_err(),
            TruncateError::EmptyEllipsis
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TextTruncate::new(Mode::End, 10, "…").unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), TruncateError::SchemaMismatch));
    }

    #[test]
    fn trunc_serde_roundtrip() {
        let t = TextTruncate::new(Mode::Middle, 10, "…").unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: TextTruncate = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
