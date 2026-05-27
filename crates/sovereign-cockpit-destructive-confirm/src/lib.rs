//! `sovereign-cockpit-destructive-confirm` — type-to-confirm safety gate.
//!
//! `open(now)` starts a session requiring the operator to type
//! `required_phrase`. `typed(text, now)` updates the buffer.
//! `can_proceed(now)` returns true only when:
//!   * the buffer matches `required_phrase` exactly (case-sensitive)
//!   * AND at least `hold_ms` has elapsed since `open`.
//!
//! `cancel()` resets. `progress_pct()` reports buffer match progress
//! 0..=100 as a chrome hint.
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
pub struct DestructiveConfirm {
    /// Schema version.
    pub schema_version: String,
    /// Phrase the operator must type exactly.
    pub required_phrase: String,
    /// Minimum hold (ms) since open() before can_proceed can return true.
    pub hold_ms: u64,
    /// Current buffer.
    pub buffer: String,
    /// When the gate opened (None means closed).
    pub opened_at_ms: Option<u64>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ConfirmError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty phrase.
    #[error("required_phrase empty")]
    EmptyPhrase,
}

impl DestructiveConfirm {
    /// New.
    pub fn new(required_phrase: &str, hold_ms: u64) -> Result<Self, ConfirmError> {
        if required_phrase.is_empty() {
            return Err(ConfirmError::EmptyPhrase);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            required_phrase: required_phrase.into(),
            hold_ms,
            buffer: String::new(),
            opened_at_ms: None,
        })
    }

    /// Open the gate.
    pub fn open(&mut self, now_ms: u64) {
        self.opened_at_ms = Some(now_ms);
        self.buffer.clear();
    }

    /// Type into the buffer.
    pub fn typed(&mut self, text: &str) {
        self.buffer = text.into();
    }

    /// Cancel.
    pub fn cancel(&mut self) {
        self.opened_at_ms = None;
        self.buffer.clear();
    }

    /// Is the gate open?
    pub fn is_open(&self) -> bool {
        self.opened_at_ms.is_some()
    }

    /// Match progress 0..=100 (count of matching leading chars / total chars).
    pub fn progress_pct(&self) -> u8 {
        let total = self.required_phrase.chars().count();
        if total == 0 {
            return 100;
        }
        let matched = self
            .required_phrase
            .chars()
            .zip(self.buffer.chars())
            .take_while(|(a, b)| a == b)
            .count();
        ((matched * 100) / total) as u8
    }

    /// May the operator proceed?
    pub fn can_proceed(&self, now_ms: u64) -> bool {
        let opened = match self.opened_at_ms {
            Some(t) => t,
            None => return false,
        };
        if now_ms.saturating_sub(opened) < self.hold_ms {
            return false;
        }
        self.buffer == self.required_phrase
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ConfirmError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ConfirmError::SchemaMismatch);
        }
        if self.required_phrase.is_empty() {
            return Err(ConfirmError::EmptyPhrase);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_phrase_rejected() {
        assert!(matches!(
            DestructiveConfirm::new("", 0).unwrap_err(),
            ConfirmError::EmptyPhrase
        ));
    }

    #[test]
    fn closed_cannot_proceed() {
        let c = DestructiveConfirm::new("DELETE", 1000).unwrap();
        assert!(!c.can_proceed(99_999));
    }

    #[test]
    fn must_hold_before_match() {
        let mut c = DestructiveConfirm::new("DELETE", 1000).unwrap();
        c.open(0);
        c.typed("DELETE");
        assert!(!c.can_proceed(500));
        assert!(c.can_proceed(1000));
    }

    #[test]
    fn case_sensitive() {
        let mut c = DestructiveConfirm::new("DELETE", 0).unwrap();
        c.open(0);
        c.typed("delete");
        assert!(!c.can_proceed(0));
    }

    #[test]
    fn partial_progress() {
        let mut c = DestructiveConfirm::new("DELETE", 0).unwrap();
        c.open(0);
        c.typed("DEL");
        assert_eq!(c.progress_pct(), 50);
    }

    #[test]
    fn full_progress() {
        let mut c = DestructiveConfirm::new("DELETE", 0).unwrap();
        c.open(0);
        c.typed("DELETE");
        assert_eq!(c.progress_pct(), 100);
    }

    #[test]
    fn cancel_resets() {
        let mut c = DestructiveConfirm::new("DELETE", 0).unwrap();
        c.open(0);
        c.typed("DEL");
        c.cancel();
        assert!(!c.is_open());
        assert_eq!(c.progress_pct(), 0);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = DestructiveConfirm::new("DELETE", 0).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            ConfirmError::SchemaMismatch
        ));
    }

    #[test]
    fn confirm_serde_roundtrip() {
        let mut c = DestructiveConfirm::new("DELETE", 1000).unwrap();
        c.open(0);
        c.typed("DEL");
        let j = serde_json::to_string(&c).unwrap();
        let back: DestructiveConfirm = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
