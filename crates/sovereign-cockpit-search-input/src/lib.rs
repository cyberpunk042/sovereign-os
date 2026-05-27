//! `sovereign-cockpit-search-input` — search-input widget state.
//!
//! Buffer + debounce window + last submitted snapshot. type_text /
//! clear / submit mutators. should_emit(now_ms) tells the caller
//! when the debounce window has elapsed since the last keystroke.
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
pub struct SearchInput {
    /// Schema version.
    pub schema_version: String,
    /// Current buffer.
    pub buffer: String,
    /// Debounce window in ms.
    pub debounce_ms: u32,
    /// Wall-clock ms of last keystroke (0 = none yet).
    pub last_keystroke_ms: u64,
    /// Last submitted query value (after debounce or explicit submit).
    pub last_submitted: String,
    /// Has the buffer been emitted since the last keystroke?
    pub emitted: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SearchInputError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// debounce_ms too large to be reasonable.
    #[error("debounce_ms {0} > 60000 (1 min cap)")]
    DebounceTooLarge(u32),
}

impl SearchInput {
    /// New with given debounce (≤ 60_000).
    pub fn new(debounce_ms: u32) -> Result<Self, SearchInputError> {
        if debounce_ms > 60_000 {
            return Err(SearchInputError::DebounceTooLarge(debounce_ms));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            buffer: String::new(),
            debounce_ms,
            last_keystroke_ms: 0,
            last_submitted: String::new(),
            emitted: true,
        })
    }

    /// Append text (operator typed). Marks dirty + records keystroke time.
    pub fn type_text(&mut self, s: &str, now_ms: u64) {
        self.buffer.push_str(s);
        self.last_keystroke_ms = now_ms;
        self.emitted = false;
    }

    /// Replace buffer (e.g., paste).
    pub fn set_buffer(&mut self, text: &str, now_ms: u64) {
        self.buffer = text.into();
        self.last_keystroke_ms = now_ms;
        self.emitted = false;
    }

    /// Clear buffer (X click).
    pub fn clear(&mut self, now_ms: u64) {
        self.buffer.clear();
        self.last_keystroke_ms = now_ms;
        self.emitted = false;
    }

    /// Is the clear button visible?
    pub fn show_clear(&self) -> bool {
        !self.buffer.is_empty()
    }

    /// Should the operator caller emit a search now? Returns true once
    /// per quiet window. set the `emit_done()` after consuming.
    pub fn should_emit(&self, now_ms: u64) -> bool {
        if self.emitted {
            return false;
        }
        now_ms.saturating_sub(self.last_keystroke_ms) >= self.debounce_ms as u64
    }

    /// Mark emitted + record the submitted value (idempotent until next type).
    pub fn emit_done(&mut self) {
        self.last_submitted = self.buffer.clone();
        self.emitted = true;
    }

    /// Explicit submit (Enter key) — emits regardless of debounce.
    pub fn submit(&mut self) -> String {
        self.last_submitted = self.buffer.clone();
        self.emitted = true;
        self.last_submitted.clone()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SearchInputError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SearchInputError::SchemaMismatch);
        }
        if self.debounce_ms > 60_000 {
            return Err(SearchInputError::DebounceTooLarge(self.debounce_ms));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn debounce_too_large_rejected() {
        assert!(matches!(
            SearchInput::new(60_001).unwrap_err(),
            SearchInputError::DebounceTooLarge(_)
        ));
    }

    #[test]
    fn type_marks_emitted_false() {
        let mut s = SearchInput::new(200).unwrap();
        s.type_text("abc", 100);
        assert!(!s.emitted);
        assert_eq!(s.buffer, "abc");
    }

    #[test]
    fn should_emit_after_debounce() {
        let mut s = SearchInput::new(200).unwrap();
        s.type_text("abc", 100);
        assert!(!s.should_emit(150));
        assert!(s.should_emit(300));
    }

    #[test]
    fn emit_done_freezes_until_next_type() {
        let mut s = SearchInput::new(200).unwrap();
        s.type_text("abc", 100);
        assert!(s.should_emit(400));
        s.emit_done();
        assert!(!s.should_emit(500));
        assert_eq!(s.last_submitted, "abc");
        s.type_text("d", 600);
        assert!(s.should_emit(900));
    }

    #[test]
    fn submit_bypasses_debounce() {
        let mut s = SearchInput::new(2_000).unwrap();
        s.type_text("abc", 100);
        assert!(!s.should_emit(200));
        let v = s.submit();
        assert_eq!(v, "abc");
        assert!(!s.should_emit(200));
    }

    #[test]
    fn show_clear_when_buffer_nonempty() {
        let mut s = SearchInput::new(200).unwrap();
        assert!(!s.show_clear());
        s.type_text("a", 0);
        assert!(s.show_clear());
    }

    #[test]
    fn clear_empties() {
        let mut s = SearchInput::new(200).unwrap();
        s.type_text("abc", 0);
        s.clear(1);
        assert!(s.buffer.is_empty());
    }

    #[test]
    fn set_buffer_replaces() {
        let mut s = SearchInput::new(200).unwrap();
        s.type_text("abc", 0);
        s.set_buffer("xyz", 1);
        assert_eq!(s.buffer, "xyz");
        assert!(!s.emitted);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SearchInput::new(200).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SearchInputError::SchemaMismatch
        ));
    }

    #[test]
    fn input_serde_roundtrip() {
        let mut s = SearchInput::new(200).unwrap();
        s.type_text("hi", 100);
        let j = serde_json::to_string(&s).unwrap();
        let back: SearchInput = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
