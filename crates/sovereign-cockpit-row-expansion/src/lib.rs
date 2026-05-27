//! `sovereign-cockpit-row-expansion` — row expansion state.
//!
//! Per-row `Expansion { expanded, loaded }`. Rows start collapsed
//! and unloaded. `expand(id)` marks expanded; `mark_loaded(id)`
//! signals subrows have arrived. UI typically renders a spinner
//! when expanded && !loaded. `collapse(id)` un-expands but keeps
//! the loaded flag so re-expand is instant. `forget(id)` drops
//! both flags.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-row state.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Expansion {
    /// Expanded.
    pub expanded: bool,
    /// Loaded (subrows known).
    pub loaded: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RowExpansion {
    /// Schema version.
    pub schema_version: String,
    /// id → expansion.
    pub rows: BTreeMap<String, Expansion>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RowError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("row id empty")]
    EmptyId,
}

impl RowExpansion {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            rows: BTreeMap::new(),
        }
    }

    /// Expand.
    pub fn expand(&mut self, id: &str) -> Result<(), RowError> {
        if id.is_empty() {
            return Err(RowError::EmptyId);
        }
        let r = self.rows.entry(id.into()).or_default();
        r.expanded = true;
        Ok(())
    }

    /// Collapse (keep loaded).
    pub fn collapse(&mut self, id: &str) -> Result<(), RowError> {
        if id.is_empty() {
            return Err(RowError::EmptyId);
        }
        let r = self.rows.entry(id.into()).or_default();
        r.expanded = false;
        Ok(())
    }

    /// Toggle expanded.
    pub fn toggle(&mut self, id: &str) -> Result<bool, RowError> {
        if id.is_empty() {
            return Err(RowError::EmptyId);
        }
        let r = self.rows.entry(id.into()).or_default();
        r.expanded = !r.expanded;
        Ok(r.expanded)
    }

    /// Mark loaded.
    pub fn mark_loaded(&mut self, id: &str) -> Result<(), RowError> {
        if id.is_empty() {
            return Err(RowError::EmptyId);
        }
        let r = self.rows.entry(id.into()).or_default();
        r.loaded = true;
        Ok(())
    }

    /// Is expanded.
    pub fn is_expanded(&self, id: &str) -> bool {
        self.rows.get(id).map(|r| r.expanded).unwrap_or(false)
    }

    /// Is loaded.
    pub fn is_loaded(&self, id: &str) -> bool {
        self.rows.get(id).map(|r| r.loaded).unwrap_or(false)
    }

    /// Pending load: expanded but not loaded.
    pub fn pending_load(&self) -> Vec<String> {
        self.rows
            .iter()
            .filter(|(_, r)| r.expanded && !r.loaded)
            .map(|(k, _)| k.clone())
            .collect()
    }

    /// Forget a row.
    pub fn forget(&mut self, id: &str) -> bool {
        self.rows.remove(id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RowError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RowError::SchemaMismatch);
        }
        for k in self.rows.keys() {
            if k.is_empty() {
                return Err(RowError::EmptyId);
            }
        }
        Ok(())
    }
}

impl Default for RowExpansion {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn expand_collapse() {
        let mut r = RowExpansion::new();
        r.expand("a").unwrap();
        assert!(r.is_expanded("a"));
        r.collapse("a").unwrap();
        assert!(!r.is_expanded("a"));
    }

    #[test]
    fn toggle_flips() {
        let mut r = RowExpansion::new();
        assert!(r.toggle("a").unwrap());
        assert!(!r.toggle("a").unwrap());
    }

    #[test]
    fn collapse_keeps_loaded() {
        let mut r = RowExpansion::new();
        r.expand("a").unwrap();
        r.mark_loaded("a").unwrap();
        r.collapse("a").unwrap();
        assert!(r.is_loaded("a"));
    }

    #[test]
    fn pending_load_filters() {
        let mut r = RowExpansion::new();
        r.expand("a").unwrap();
        r.expand("b").unwrap();
        r.mark_loaded("b").unwrap();
        let p = r.pending_load();
        assert_eq!(p, vec!["a"]);
    }

    #[test]
    fn forget_drops_row() {
        let mut r = RowExpansion::new();
        r.expand("a").unwrap();
        assert!(r.forget("a"));
        assert!(!r.is_expanded("a"));
    }

    #[test]
    fn unknown_row_is_collapsed_unloaded() {
        let r = RowExpansion::new();
        assert!(!r.is_expanded("nope"));
        assert!(!r.is_loaded("nope"));
    }

    #[test]
    fn empty_id_rejected() {
        let mut r = RowExpansion::new();
        assert!(matches!(r.expand("").unwrap_err(), RowError::EmptyId));
        assert!(matches!(r.collapse("").unwrap_err(), RowError::EmptyId));
        assert!(matches!(r.toggle("").unwrap_err(), RowError::EmptyId));
        assert!(matches!(r.mark_loaded("").unwrap_err(), RowError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = RowExpansion::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            RowError::SchemaMismatch
        ));
    }

    #[test]
    fn row_serde_roundtrip() {
        let mut r = RowExpansion::new();
        r.expand("a").unwrap();
        r.mark_loaded("a").unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: RowExpansion = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
