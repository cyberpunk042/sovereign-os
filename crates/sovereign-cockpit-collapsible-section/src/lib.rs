//! `sovereign-cockpit-collapsible-section` — per-section collapsed/expanded state.
//!
//! Operator clicks a section header; collapsed/expanded toggles. The
//! cockpit persists per-section preference and restores on reload.
//! Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CollapsibleState {
    /// Schema version.
    pub schema_version: String,
    /// Default state when section_id unknown.
    pub default_collapsed: bool,
    /// section_id → collapsed flag.
    pub states: HashMap<String, bool>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CollapsibleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty section_id.
    #[error("section_id empty")]
    EmptySectionId,
}

impl CollapsibleState {
    /// New, defaulting unknown sections to `default_collapsed`.
    pub fn new(default_collapsed: bool) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            default_collapsed,
            states: HashMap::new(),
        }
    }

    /// Set state.
    pub fn set(&mut self, section_id: &str, collapsed: bool) -> Result<(), CollapsibleError> {
        if section_id.is_empty() {
            return Err(CollapsibleError::EmptySectionId);
        }
        self.states.insert(section_id.into(), collapsed);
        Ok(())
    }

    /// Toggle state.
    pub fn toggle(&mut self, section_id: &str) -> Result<bool, CollapsibleError> {
        if section_id.is_empty() {
            return Err(CollapsibleError::EmptySectionId);
        }
        let current = self.is_collapsed(section_id);
        self.states.insert(section_id.into(), !current);
        Ok(!current)
    }

    /// Get state. Returns `default_collapsed` if section_id unknown.
    pub fn is_collapsed(&self, section_id: &str) -> bool {
        self.states
            .get(section_id)
            .copied()
            .unwrap_or(self.default_collapsed)
    }

    /// Reset all sections to default.
    pub fn reset_all(&mut self) {
        self.states.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CollapsibleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CollapsibleError::SchemaMismatch);
        }
        for k in self.states.keys() {
            if k.is_empty() {
                return Err(CollapsibleError::EmptySectionId);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_collapsed_used_for_unknown() {
        let s = CollapsibleState::new(true);
        assert!(s.is_collapsed("any"));
        let s = CollapsibleState::new(false);
        assert!(!s.is_collapsed("any"));
    }

    #[test]
    fn set_overrides_default() {
        let mut s = CollapsibleState::new(true);
        s.set("section-a", false).unwrap();
        assert!(!s.is_collapsed("section-a"));
        assert!(s.is_collapsed("section-b")); // unknown
    }

    #[test]
    fn toggle_flips() {
        let mut s = CollapsibleState::new(false);
        let v = s.toggle("a").unwrap();
        assert!(v);
        let v = s.toggle("a").unwrap();
        assert!(!v);
    }

    #[test]
    fn reset_all_clears() {
        let mut s = CollapsibleState::new(false);
        s.set("a", true).unwrap();
        s.reset_all();
        assert!(s.states.is_empty());
        assert!(!s.is_collapsed("a")); // reverts to default
    }

    #[test]
    fn empty_section_id_rejected() {
        let mut s = CollapsibleState::new(false);
        assert!(matches!(
            s.set("", true).unwrap_err(),
            CollapsibleError::EmptySectionId
        ));
        assert!(matches!(
            s.toggle("").unwrap_err(),
            CollapsibleError::EmptySectionId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = CollapsibleState::new(false);
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            CollapsibleError::SchemaMismatch
        ));
    }

    #[test]
    fn state_serde_roundtrip() {
        let mut s = CollapsibleState::new(false);
        s.set("a", true).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: CollapsibleState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
