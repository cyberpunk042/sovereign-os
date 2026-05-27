//! `sovereign-cockpit-reading-progress` — reading tracker.
//!
//! Total word count + words_per_minute. update(offset_words)
//! sets current; progress_bp 0..=10000; remaining_seconds based
//! on (total - offset) / wpm * 60. completed when offset >=
//! total.
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
pub struct ReadingProgress {
    /// Schema version.
    pub schema_version: String,
    /// Total word count.
    pub total_words: u32,
    /// Current offset (clamped 0..=total).
    pub offset_words: u32,
    /// Reading speed words per minute.
    pub wpm: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ProgressError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero total.
    #[error("total_words must be >= 1")]
    ZeroTotal,
    /// Zero wpm.
    #[error("wpm must be >= 1")]
    ZeroWpm,
}

impl ReadingProgress {
    /// New.
    pub fn new(total_words: u32, wpm: u32) -> Result<Self, ProgressError> {
        if total_words == 0 {
            return Err(ProgressError::ZeroTotal);
        }
        if wpm == 0 {
            return Err(ProgressError::ZeroWpm);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            total_words,
            offset_words: 0,
            wpm,
        })
    }

    /// Update offset (clamped to total).
    pub fn update(&mut self, offset_words: u32) {
        self.offset_words = offset_words.min(self.total_words);
    }

    /// Progress in basis points.
    pub fn progress_bp(&self) -> u32 {
        ((self.offset_words as u64 * 10_000) / self.total_words as u64) as u32
    }

    /// Remaining seconds at current wpm.
    pub fn remaining_seconds(&self) -> u32 {
        let remaining_words = self.total_words.saturating_sub(self.offset_words);
        ((remaining_words as u64 * 60) / self.wpm as u64) as u32
    }

    /// Completed?
    pub fn is_complete(&self) -> bool {
        self.offset_words >= self.total_words
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ProgressError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ProgressError::SchemaMismatch);
        }
        if self.total_words == 0 {
            return Err(ProgressError::ZeroTotal);
        }
        if self.wpm == 0 {
            return Err(ProgressError::ZeroWpm);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_is_zero() {
        let p = ReadingProgress::new(1000, 200).unwrap();
        assert_eq!(p.progress_bp(), 0);
        assert!(!p.is_complete());
    }

    #[test]
    fn half_done() {
        let mut p = ReadingProgress::new(1000, 200).unwrap();
        p.update(500);
        assert_eq!(p.progress_bp(), 5000);
        // 500 words at 200 wpm = 2.5 min = 150 s.
        assert_eq!(p.remaining_seconds(), 150);
    }

    #[test]
    fn complete_at_total() {
        let mut p = ReadingProgress::new(1000, 200).unwrap();
        p.update(1000);
        assert_eq!(p.progress_bp(), 10000);
        assert!(p.is_complete());
        assert_eq!(p.remaining_seconds(), 0);
    }

    #[test]
    fn over_offset_clamps() {
        let mut p = ReadingProgress::new(1000, 200).unwrap();
        p.update(9999);
        assert_eq!(p.offset_words, 1000);
    }

    #[test]
    fn bad_inputs_rejected() {
        assert!(matches!(
            ReadingProgress::new(0, 200).unwrap_err(),
            ProgressError::ZeroTotal
        ));
        assert!(matches!(
            ReadingProgress::new(100, 0).unwrap_err(),
            ProgressError::ZeroWpm
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ReadingProgress::new(100, 200).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            ProgressError::SchemaMismatch
        ));
    }

    #[test]
    fn progress_serde_roundtrip() {
        let mut p = ReadingProgress::new(100, 200).unwrap();
        p.update(50);
        let j = serde_json::to_string(&p).unwrap();
        let back: ReadingProgress = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
