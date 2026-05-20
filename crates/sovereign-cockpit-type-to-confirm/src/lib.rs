//! `sovereign-cockpit-type-to-confirm` — type-to-confirm gate.
//!
//! Operator must type a confirmation phrase exactly (e.g.
//! "DELETE prod-db") to enable the destructive action. update(s)
//! sets current_input; matches() true iff current_input ==
//! required exactly (or case-insensitively per config).
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
pub struct TypeToConfirm {
    /// Schema version.
    pub schema_version: String,
    /// Required phrase.
    pub required: String,
    /// Whether comparison ignores ASCII case.
    pub case_insensitive: bool,
    /// Current input.
    pub current_input: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ConfirmError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty required phrase.
    #[error("required phrase empty")]
    EmptyRequired,
}

impl TypeToConfirm {
    /// New.
    pub fn new(required: &str, case_insensitive: bool) -> Result<Self, ConfirmError> {
        if required.is_empty() { return Err(ConfirmError::EmptyRequired); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            required: required.into(),
            case_insensitive,
            current_input: String::new(),
        })
    }

    /// Update current input.
    pub fn update(&mut self, s: &str) { self.current_input = s.into(); }

    /// Reset.
    pub fn reset(&mut self) { self.current_input.clear(); }

    /// True iff input matches required.
    pub fn matches(&self) -> bool {
        if self.case_insensitive {
            self.current_input.eq_ignore_ascii_case(&self.required)
        } else {
            self.current_input == self.required
        }
    }

    /// Diff progress: how many leading bytes of input match the
    /// required prefix (capped at required.len()).
    pub fn prefix_len(&self) -> usize {
        let req = if self.case_insensitive { self.required.to_ascii_lowercase() } else { self.required.clone() };
        let inp = if self.case_insensitive { self.current_input.to_ascii_lowercase() } else { self.current_input.clone() };
        let mut n = 0;
        for (a, b) in inp.bytes().zip(req.bytes()) {
            if a == b { n += 1; } else { break; }
        }
        n
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ConfirmError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ConfirmError::SchemaMismatch); }
        if self.required.is_empty() { return Err(ConfirmError::EmptyRequired); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exact_match_strict() {
        let mut c = TypeToConfirm::new("DELETE prod", false).unwrap();
        c.update("DELETE prod");
        assert!(c.matches());
    }

    #[test]
    fn case_mismatch_strict() {
        let mut c = TypeToConfirm::new("DELETE prod", false).unwrap();
        c.update("delete prod");
        assert!(!c.matches());
    }

    #[test]
    fn case_insensitive() {
        let mut c = TypeToConfirm::new("DELETE prod", true).unwrap();
        c.update("delete prod");
        assert!(c.matches());
    }

    #[test]
    fn partial_does_not_match() {
        let mut c = TypeToConfirm::new("DELETE prod", false).unwrap();
        c.update("DELETE pro");
        assert!(!c.matches());
        assert_eq!(c.prefix_len(), 10);
    }

    #[test]
    fn diverging_input_prefix() {
        let mut c = TypeToConfirm::new("DELETE prod", false).unwrap();
        c.update("DELETzz");
        assert!(!c.matches());
        assert_eq!(c.prefix_len(), 5);
    }

    #[test]
    fn reset_clears_input() {
        let mut c = TypeToConfirm::new("DELETE prod", false).unwrap();
        c.update("DELETE prod");
        c.reset();
        assert!(!c.matches());
        assert_eq!(c.prefix_len(), 0);
    }

    #[test]
    fn empty_required_rejected() {
        assert!(matches!(TypeToConfirm::new("", false).unwrap_err(), ConfirmError::EmptyRequired));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = TypeToConfirm::new("X", false).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), ConfirmError::SchemaMismatch));
    }

    #[test]
    fn confirm_serde_roundtrip() {
        let mut c = TypeToConfirm::new("DELETE prod", true).unwrap();
        c.update("delete pr");
        let j = serde_json::to_string(&c).unwrap();
        let back: TypeToConfirm = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
