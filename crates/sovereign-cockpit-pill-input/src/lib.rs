//! `sovereign-cockpit-pill-input` — multi-value pill/tag field.
//!
//! commit(buffer) splits by `separator`, trims, drops empties,
//! dedups against existing, and appends up to max_pills cap.
//! remove(pill) removes by exact match. clear empties.
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
pub struct PillInput {
    /// Schema version.
    pub schema_version: String,
    /// Pills (insertion order).
    pub pills: Vec<String>,
    /// Separator (e.g., ',').
    pub separator: char,
    /// Max pills.
    pub max_pills: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PillError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero max.
    #[error("max_pills must be >= 1")]
    ZeroMax,
}

impl PillInput {
    /// New.
    pub fn new(separator: char, max_pills: u32) -> Result<Self, PillError> {
        if max_pills == 0 {
            return Err(PillError::ZeroMax);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            pills: Vec::new(),
            separator,
            max_pills,
        })
    }

    /// Commit buffer; returns count added.
    pub fn commit(&mut self, buffer: &str) -> u32 {
        let mut added = 0u32;
        for part in buffer.split(self.separator) {
            let trimmed = part.trim();
            if trimmed.is_empty() {
                continue;
            }
            if (self.pills.len() as u32) >= self.max_pills {
                break;
            }
            if self.pills.iter().any(|p| p == trimmed) {
                continue;
            }
            self.pills.push(trimmed.into());
            added = added.saturating_add(1);
        }
        added
    }

    /// Remove by exact match.
    pub fn remove(&mut self, pill: &str) -> bool {
        if let Some(pos) = self.pills.iter().position(|p| p == pill) {
            self.pills.remove(pos);
            true
        } else {
            false
        }
    }

    /// Clear all.
    pub fn clear(&mut self) {
        self.pills.clear();
    }

    /// Count.
    pub fn len(&self) -> usize {
        self.pills.len()
    }

    /// Empty?
    pub fn is_empty(&self) -> bool {
        self.pills.is_empty()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PillError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PillError::SchemaMismatch);
        }
        if self.max_pills == 0 {
            return Err(PillError::ZeroMax);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn commit_splits_and_trims() {
        let mut p = PillInput::new(',', 10).unwrap();
        let n = p.commit("alice, bob,charlie");
        assert_eq!(n, 3);
        assert_eq!(p.pills, vec!["alice", "bob", "charlie"]);
    }

    #[test]
    fn commit_dedups() {
        let mut p = PillInput::new(',', 10).unwrap();
        p.commit("alice,bob");
        let n = p.commit("alice,carol");
        assert_eq!(n, 1);
        assert_eq!(p.pills, vec!["alice", "bob", "carol"]);
    }

    #[test]
    fn commit_skips_empty() {
        let mut p = PillInput::new(',', 10).unwrap();
        let n = p.commit(", ,alice,, ,bob,");
        assert_eq!(n, 2);
    }

    #[test]
    fn max_cap_enforced() {
        let mut p = PillInput::new(',', 2).unwrap();
        let n = p.commit("a,b,c,d");
        assert_eq!(n, 2);
        assert_eq!(p.pills, vec!["a", "b"]);
    }

    #[test]
    fn remove_by_exact() {
        let mut p = PillInput::new(',', 10).unwrap();
        p.commit("a,b,c");
        assert!(p.remove("b"));
        assert!(!p.remove("nope"));
        assert_eq!(p.pills, vec!["a", "c"]);
    }

    #[test]
    fn clear_resets() {
        let mut p = PillInput::new(',', 10).unwrap();
        p.commit("a,b");
        p.clear();
        assert!(p.is_empty());
    }

    #[test]
    fn zero_max_rejected() {
        assert!(matches!(
            PillInput::new(',', 0).unwrap_err(),
            PillError::ZeroMax
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = PillInput::new(',', 10).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PillError::SchemaMismatch
        ));
    }

    #[test]
    fn input_serde_roundtrip() {
        let mut p = PillInput::new(',', 10).unwrap();
        p.commit("a,b");
        let j = serde_json::to_string(&p).unwrap();
        let back: PillInput = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
