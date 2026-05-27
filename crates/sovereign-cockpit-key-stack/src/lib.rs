//! `sovereign-cockpit-key-stack` — multi-keystroke chord recorder.
//!
//! Records keystrokes with timestamps. record_at() ages out keys
//! older than `timeout_ms`. matches(prefix) returns true if the
//! current tail equals the prefix.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One recorded keystroke.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Keystroke {
    /// Chord text (e.g., "ctrl+x", "g").
    pub chord: String,
    /// Wall-clock ms.
    pub at_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeyStack {
    /// Schema version.
    pub schema_version: String,
    /// Recent keystrokes (FIFO).
    pub recent: Vec<Keystroke>,
    /// Max stack length.
    pub max_len: u32,
    /// Stroke expiry ms.
    pub timeout_ms: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum KeyStackError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// max_len zero.
    #[error("max_len is zero")]
    MaxLenZero,
    /// timeout_ms zero.
    #[error("timeout_ms is zero")]
    TimeoutZero,
    /// Empty chord.
    #[error("chord empty")]
    EmptyChord,
}

impl KeyStack {
    /// New.
    pub fn new(max_len: u32, timeout_ms: u32) -> Result<Self, KeyStackError> {
        if max_len == 0 {
            return Err(KeyStackError::MaxLenZero);
        }
        if timeout_ms == 0 {
            return Err(KeyStackError::TimeoutZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            recent: Vec::new(),
            max_len,
            timeout_ms,
        })
    }

    /// Record + age out.
    pub fn record_at(&mut self, chord: &str, at_ms: u64) -> Result<(), KeyStackError> {
        if chord.is_empty() {
            return Err(KeyStackError::EmptyChord);
        }
        // Age out.
        self.recent
            .retain(|k| at_ms.saturating_sub(k.at_ms) < self.timeout_ms as u64);
        self.recent.push(Keystroke {
            chord: chord.into(),
            at_ms,
        });
        while (self.recent.len() as u32) > self.max_len {
            self.recent.remove(0);
        }
        Ok(())
    }

    /// Does the current tail equal prefix?
    pub fn matches(&self, prefix: &[&str]) -> bool {
        if prefix.len() > self.recent.len() {
            return false;
        }
        let tail = &self.recent[self.recent.len() - prefix.len()..];
        for (i, expected) in prefix.iter().enumerate() {
            if tail[i].chord != *expected {
                return false;
            }
        }
        true
    }

    /// Clear.
    pub fn clear(&mut self) {
        self.recent.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), KeyStackError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(KeyStackError::SchemaMismatch);
        }
        if self.max_len == 0 {
            return Err(KeyStackError::MaxLenZero);
        }
        if self.timeout_ms == 0 {
            return Err(KeyStackError::TimeoutZero);
        }
        for k in &self.recent {
            if k.chord.is_empty() {
                return Err(KeyStackError::EmptyChord);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn max_len_zero_rejected() {
        assert!(matches!(
            KeyStack::new(0, 1000).unwrap_err(),
            KeyStackError::MaxLenZero
        ));
    }

    #[test]
    fn timeout_zero_rejected() {
        assert!(matches!(
            KeyStack::new(10, 0).unwrap_err(),
            KeyStackError::TimeoutZero
        ));
    }

    #[test]
    fn record_appends() {
        let mut s = KeyStack::new(5, 1000).unwrap();
        s.record_at("g", 100).unwrap();
        s.record_at("g", 200).unwrap();
        assert_eq!(s.recent.len(), 2);
    }

    #[test]
    fn matches_double_gg() {
        let mut s = KeyStack::new(5, 1000).unwrap();
        s.record_at("g", 100).unwrap();
        s.record_at("g", 200).unwrap();
        assert!(s.matches(&["g", "g"]));
    }

    #[test]
    fn no_match_when_different() {
        let mut s = KeyStack::new(5, 1000).unwrap();
        s.record_at("g", 100).unwrap();
        s.record_at("d", 200).unwrap();
        assert!(!s.matches(&["g", "g"]));
    }

    #[test]
    fn matches_emacs_chord() {
        let mut s = KeyStack::new(5, 1000).unwrap();
        s.record_at("ctrl+x", 100).unwrap();
        s.record_at("ctrl+f", 200).unwrap();
        assert!(s.matches(&["ctrl+x", "ctrl+f"]));
    }

    #[test]
    fn timeout_ages_out() {
        let mut s = KeyStack::new(5, 500).unwrap();
        s.record_at("g", 100).unwrap();
        s.record_at("g", 700).unwrap();
        // First g (at 100) aged out by timeout 500 (700-100=600>500).
        assert_eq!(s.recent.len(), 1);
        assert!(!s.matches(&["g", "g"]));
    }

    #[test]
    fn max_len_evicts() {
        let mut s = KeyStack::new(2, 10_000).unwrap();
        s.record_at("a", 100).unwrap();
        s.record_at("b", 200).unwrap();
        s.record_at("c", 300).unwrap();
        assert_eq!(s.recent.len(), 2);
        assert!(s.matches(&["b", "c"]));
    }

    #[test]
    fn empty_chord_rejected() {
        let mut s = KeyStack::new(5, 1000).unwrap();
        assert!(matches!(
            s.record_at("", 100).unwrap_err(),
            KeyStackError::EmptyChord
        ));
    }

    #[test]
    fn clear() {
        let mut s = KeyStack::new(5, 1000).unwrap();
        s.record_at("a", 100).unwrap();
        s.clear();
        assert!(s.recent.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = KeyStack::new(5, 1000).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            KeyStackError::SchemaMismatch
        ));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = KeyStack::new(5, 1000).unwrap();
        s.record_at("g", 100).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: KeyStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
