//! `sovereign-cockpit-unsaved-guard` — unsaved-changes navigation gate.
//!
//! Operators mark scopes dirty when an edit happens, clean on save.
//! `navigate(scope_id)` returns `BlockConfirm{scope_id}` when the
//! scope is still dirty, else `Allow`. `force_navigate(scope_id)`
//! clears + allows (operator explicitly chose to discard).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct UnsavedGuard {
    /// Schema version.
    pub schema_version: String,
    /// Dirty scope ids.
    pub dirty: BTreeSet<String>,
}

/// Verdict.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum NavVerdict {
    /// Navigation allowed.
    Allow,
    /// Block + prompt operator to confirm discard.
    BlockConfirm {
        /// the scope that's dirty.
        scope_id: String,
    },
}

/// Errors.
#[derive(Debug, Error)]
pub enum GuardError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty scope.
    #[error("scope id empty")]
    EmptyScope,
}

impl UnsavedGuard {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            dirty: BTreeSet::new(),
        }
    }

    /// Mark dirty.
    pub fn mark_dirty(&mut self, scope_id: &str) -> Result<(), GuardError> {
        if scope_id.is_empty() {
            return Err(GuardError::EmptyScope);
        }
        self.dirty.insert(scope_id.into());
        Ok(())
    }

    /// Mark clean.
    pub fn mark_clean(&mut self, scope_id: &str) -> Result<(), GuardError> {
        if scope_id.is_empty() {
            return Err(GuardError::EmptyScope);
        }
        self.dirty.remove(scope_id);
        Ok(())
    }

    /// Is the scope dirty?
    pub fn is_dirty(&self, scope_id: &str) -> bool {
        self.dirty.contains(scope_id)
    }

    /// Navigate attempt.
    pub fn navigate(&self, scope_id: &str) -> NavVerdict {
        if self.dirty.contains(scope_id) {
            NavVerdict::BlockConfirm {
                scope_id: scope_id.into(),
            }
        } else {
            NavVerdict::Allow
        }
    }

    /// Force-discard navigation.
    pub fn force_navigate(&mut self, scope_id: &str) -> bool {
        self.dirty.remove(scope_id)
    }

    /// Are any scopes dirty?
    pub fn any_dirty(&self) -> bool {
        !self.dirty.is_empty()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GuardError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(GuardError::SchemaMismatch);
        }
        for s in &self.dirty {
            if s.is_empty() {
                return Err(GuardError::EmptyScope);
            }
        }
        Ok(())
    }
}

impl Default for UnsavedGuard {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clean_allows() {
        let g = UnsavedGuard::new();
        assert_eq!(g.navigate("doc-1"), NavVerdict::Allow);
    }

    #[test]
    fn dirty_blocks() {
        let mut g = UnsavedGuard::new();
        g.mark_dirty("doc-1").unwrap();
        match g.navigate("doc-1") {
            NavVerdict::BlockConfirm { scope_id } => assert_eq!(scope_id, "doc-1"),
            _ => panic!(),
        }
    }

    #[test]
    fn mark_clean_unblocks() {
        let mut g = UnsavedGuard::new();
        g.mark_dirty("doc-1").unwrap();
        g.mark_clean("doc-1").unwrap();
        assert_eq!(g.navigate("doc-1"), NavVerdict::Allow);
    }

    #[test]
    fn force_navigate_discards() {
        let mut g = UnsavedGuard::new();
        g.mark_dirty("doc-1").unwrap();
        assert!(g.force_navigate("doc-1"));
        assert_eq!(g.navigate("doc-1"), NavVerdict::Allow);
    }

    #[test]
    fn force_navigate_clean_false() {
        let mut g = UnsavedGuard::new();
        assert!(!g.force_navigate("doc-1"));
    }

    #[test]
    fn any_dirty() {
        let mut g = UnsavedGuard::new();
        assert!(!g.any_dirty());
        g.mark_dirty("doc-1").unwrap();
        assert!(g.any_dirty());
    }

    #[test]
    fn empty_scope_rejected() {
        let mut g = UnsavedGuard::new();
        assert!(matches!(
            g.mark_dirty("").unwrap_err(),
            GuardError::EmptyScope
        ));
        assert!(matches!(
            g.mark_clean("").unwrap_err(),
            GuardError::EmptyScope
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = UnsavedGuard::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(
            g.validate().unwrap_err(),
            GuardError::SchemaMismatch
        ));
    }

    #[test]
    fn guard_serde_roundtrip() {
        let mut g = UnsavedGuard::new();
        g.mark_dirty("doc-1").unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: UnsavedGuard = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
