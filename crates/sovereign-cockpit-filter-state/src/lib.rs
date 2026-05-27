//! `sovereign-cockpit-filter-state` — pending vs applied filters.
//!
//! Two maps key→value: pending (under edit) and applied (in-
//! effect). set/clear mutate pending; apply() copies pending →
//! applied; discard() copies applied → pending. is_dirty when
//! pending != applied.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FilterState {
    /// Schema version.
    pub schema_version: String,
    /// Pending filters.
    pub pending: BTreeMap<String, String>,
    /// Applied filters.
    pub applied: BTreeMap<String, String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FilterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("key empty")]
    EmptyKey,
    /// Empty.
    #[error("value empty")]
    EmptyValue,
}

impl FilterState {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            pending: BTreeMap::new(),
            applied: BTreeMap::new(),
        }
    }

    /// Set a pending filter.
    pub fn set(&mut self, key: &str, value: &str) -> Result<(), FilterError> {
        if key.is_empty() {
            return Err(FilterError::EmptyKey);
        }
        if value.is_empty() {
            return Err(FilterError::EmptyValue);
        }
        self.pending.insert(key.into(), value.into());
        Ok(())
    }

    /// Clear a pending filter.
    pub fn clear(&mut self, key: &str) -> bool {
        self.pending.remove(key).is_some()
    }

    /// Clear all pending filters.
    pub fn clear_all(&mut self) {
        self.pending.clear();
    }

    /// Apply pending → applied.
    pub fn apply(&mut self) {
        self.applied = self.pending.clone();
    }

    /// Discard pending changes (applied → pending).
    pub fn discard(&mut self) {
        self.pending = self.applied.clone();
    }

    /// Dirty (pending != applied).
    pub fn is_dirty(&self) -> bool {
        self.pending != self.applied
    }

    /// Applied filter count.
    pub fn applied_count(&self) -> usize {
        self.applied.len()
    }

    /// Pending filter count.
    pub fn pending_count(&self) -> usize {
        self.pending.len()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FilterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FilterError::SchemaMismatch);
        }
        for (k, v) in self.pending.iter().chain(self.applied.iter()) {
            if k.is_empty() {
                return Err(FilterError::EmptyKey);
            }
            if v.is_empty() {
                return Err(FilterError::EmptyValue);
            }
        }
        Ok(())
    }
}

impl Default for FilterState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_is_clean() {
        let f = FilterState::new();
        assert!(!f.is_dirty());
    }

    #[test]
    fn set_pending_is_dirty() {
        let mut f = FilterState::new();
        f.set("status", "open").unwrap();
        assert!(f.is_dirty());
    }

    #[test]
    fn apply_clears_dirty() {
        let mut f = FilterState::new();
        f.set("status", "open").unwrap();
        f.apply();
        assert!(!f.is_dirty());
        assert_eq!(f.applied_count(), 1);
    }

    #[test]
    fn discard_reverts_pending() {
        let mut f = FilterState::new();
        f.set("status", "open").unwrap();
        f.apply();
        f.set("status", "closed").unwrap();
        f.discard();
        assert_eq!(f.pending.get("status").unwrap(), "open");
        assert!(!f.is_dirty());
    }

    #[test]
    fn clear_one_pending() {
        let mut f = FilterState::new();
        f.set("a", "x").unwrap();
        f.set("b", "y").unwrap();
        assert!(f.clear("a"));
        assert_eq!(f.pending_count(), 1);
    }

    #[test]
    fn clear_all_pending() {
        let mut f = FilterState::new();
        f.set("a", "x").unwrap();
        f.set("b", "y").unwrap();
        f.clear_all();
        assert_eq!(f.pending_count(), 0);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut f = FilterState::new();
        assert!(matches!(f.set("", "x").unwrap_err(), FilterError::EmptyKey));
        assert!(matches!(
            f.set("k", "").unwrap_err(),
            FilterError::EmptyValue
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = FilterState::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FilterError::SchemaMismatch
        ));
    }

    #[test]
    fn filter_serde_roundtrip() {
        let mut f = FilterState::new();
        f.set("a", "x").unwrap();
        f.apply();
        let j = serde_json::to_string(&f).unwrap();
        let back: FilterState = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
