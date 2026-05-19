//! `sovereign-cockpit-multi-line-input` — auto-growing textarea.
//!
//! Soft-wrap at `soft_wrap_cols` (char-level, not grapheme-aware
//! here — the cockpit layer can pre-process if needed). Reports
//! `visible_rows` = min(actual line count, max_rows).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MultiLineInput {
    /// Schema version.
    pub schema_version: String,
    /// Buffer.
    pub buffer: String,
    /// Soft wrap col count.
    pub soft_wrap_cols: u32,
    /// Min rows shown.
    pub min_rows: u32,
    /// Max rows before scroll appears.
    pub max_rows: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum InputError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad wrap.
    #[error("soft_wrap_cols is zero")]
    WrapZero,
    /// Bad min/max.
    #[error("min_rows {0} > max_rows {1}")]
    BadRows(u32, u32),
}

impl MultiLineInput {
    /// New.
    pub fn new(soft_wrap_cols: u32, min_rows: u32, max_rows: u32) -> Result<Self, InputError> {
        if soft_wrap_cols == 0 { return Err(InputError::WrapZero); }
        if min_rows > max_rows { return Err(InputError::BadRows(min_rows, max_rows)); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            buffer: String::new(),
            soft_wrap_cols, min_rows, max_rows,
        })
    }

    /// Type text.
    pub fn type_text(&mut self, s: &str) {
        self.buffer.push_str(s);
    }

    /// Insert newline.
    pub fn newline(&mut self) {
        self.buffer.push('\n');
    }

    /// Backspace.
    pub fn backspace(&mut self) -> bool {
        self.buffer.pop().is_some()
    }

    /// Logical line count (including wraps).
    pub fn line_count(&self) -> u32 {
        if self.buffer.is_empty() { return 1; }
        let mut count: u32 = 0;
        for line in self.buffer.split('\n') {
            let chars = line.chars().count();
            if chars == 0 {
                count = count.saturating_add(1);
            } else {
                let wraps = (chars as u32 + self.soft_wrap_cols - 1) / self.soft_wrap_cols;
                count = count.saturating_add(wraps.max(1));
            }
        }
        count.max(1)
    }

    /// Rendered visible row count.
    pub fn visible_rows(&self) -> u32 {
        let lc = self.line_count();
        lc.clamp(self.min_rows.max(1), self.max_rows)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), InputError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(InputError::SchemaMismatch);
        }
        if self.soft_wrap_cols == 0 { return Err(InputError::WrapZero); }
        if self.min_rows > self.max_rows { return Err(InputError::BadRows(self.min_rows, self.max_rows)); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wrap_zero_rejected() {
        assert!(matches!(MultiLineInput::new(0, 1, 5).unwrap_err(), InputError::WrapZero));
    }

    #[test]
    fn min_over_max_rejected() {
        assert!(matches!(MultiLineInput::new(80, 10, 5).unwrap_err(), InputError::BadRows(10, 5)));
    }

    #[test]
    fn empty_one_line() {
        let m = MultiLineInput::new(80, 1, 10).unwrap();
        assert_eq!(m.line_count(), 1);
    }

    #[test]
    fn explicit_newlines() {
        let mut m = MultiLineInput::new(80, 1, 10).unwrap();
        m.type_text("a\nb\nc");
        assert_eq!(m.line_count(), 3);
    }

    #[test]
    fn soft_wrap_counted() {
        let mut m = MultiLineInput::new(10, 1, 100).unwrap();
        m.type_text(&"x".repeat(25));
        // 25 chars / 10 col wrap = 3 lines.
        assert_eq!(m.line_count(), 3);
    }

    #[test]
    fn visible_rows_clamped_min() {
        let m = MultiLineInput::new(80, 3, 10).unwrap();
        assert_eq!(m.visible_rows(), 3);
    }

    #[test]
    fn visible_rows_clamped_max() {
        let mut m = MultiLineInput::new(10, 1, 5).unwrap();
        m.type_text(&"x".repeat(100));
        assert_eq!(m.visible_rows(), 5);
    }

    #[test]
    fn backspace_works() {
        let mut m = MultiLineInput::new(80, 1, 10).unwrap();
        m.type_text("ab");
        m.backspace();
        assert_eq!(m.buffer, "a");
    }

    #[test]
    fn newline_inserts() {
        let mut m = MultiLineInput::new(80, 1, 10).unwrap();
        m.type_text("a");
        m.newline();
        m.type_text("b");
        assert_eq!(m.line_count(), 2);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = MultiLineInput::new(80, 1, 10).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), InputError::SchemaMismatch));
    }

    #[test]
    fn input_serde_roundtrip() {
        let mut m = MultiLineInput::new(80, 1, 10).unwrap();
        m.type_text("hello world\nsecond line");
        let j = serde_json::to_string(&m).unwrap();
        let back: MultiLineInput = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
