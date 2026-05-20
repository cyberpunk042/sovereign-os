//! `sovereign-cockpit-dirty-fields` — form-field dirty tracker.
//!
//! Maintains initial[field] and current[field]. diff()
//! recomputes the dirty set as fields whose current != initial.
//! set_current(field, value) updates the current map and
//! refreshes the dirty membership for that field.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DirtyFields {
    /// Schema version.
    pub schema_version: String,
    /// Initial values.
    pub initial: BTreeMap<String, String>,
    /// Current values.
    pub current: BTreeMap<String, String>,
    /// Dirty fields (cached).
    pub dirty: BTreeSet<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DirtyError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("field empty")]
    EmptyField,
}

impl DirtyFields {
    /// New (empty).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            initial: BTreeMap::new(),
            current: BTreeMap::new(),
            dirty: BTreeSet::new(),
        }
    }

    /// Set initial baseline (replaces).
    pub fn set_initial(&mut self, initial: BTreeMap<String, String>) {
        self.initial = initial.clone();
        self.current = initial;
        self.dirty.clear();
    }

    /// Set current value (and refresh dirty-ness for that field).
    pub fn set_current(&mut self, field: &str, value: &str) -> Result<(), DirtyError> {
        if field.is_empty() { return Err(DirtyError::EmptyField); }
        self.current.insert(field.into(), value.into());
        self.refresh_field(field);
        Ok(())
    }

    fn refresh_field(&mut self, field: &str) {
        let init = self.initial.get(field);
        let cur = self.current.get(field);
        if init == cur {
            self.dirty.remove(field);
        } else {
            self.dirty.insert(field.into());
        }
    }

    /// Recompute the dirty set from scratch.
    pub fn diff(&mut self) {
        self.dirty.clear();
        let mut keys: BTreeSet<&String> = BTreeSet::new();
        keys.extend(self.initial.keys());
        keys.extend(self.current.keys());
        for k in keys {
            if self.initial.get(k) != self.current.get(k) {
                self.dirty.insert(k.clone());
            }
        }
    }

    /// Is field dirty?
    pub fn is_dirty(&self, field: &str) -> bool {
        self.dirty.contains(field)
    }

    /// Any dirty?
    pub fn any_dirty(&self) -> bool {
        !self.dirty.is_empty()
    }

    /// Reset to initial.
    pub fn reset(&mut self) {
        self.current = self.initial.clone();
        self.dirty.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DirtyError> {
        if self.schema_version != SCHEMA_VERSION { return Err(DirtyError::SchemaMismatch); }
        for k in self.initial.keys().chain(self.current.keys()) {
            if k.is_empty() { return Err(DirtyError::EmptyField); }
        }
        Ok(())
    }
}

impl Default for DirtyFields {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn map(items: &[(&str, &str)]) -> BTreeMap<String, String> {
        items.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect()
    }

    #[test]
    fn fresh_not_dirty() {
        let d = DirtyFields::new();
        assert!(!d.any_dirty());
    }

    #[test]
    fn set_current_marks_dirty() {
        let mut d = DirtyFields::new();
        d.set_initial(map(&[("name", "alice")]));
        d.set_current("name", "bob").unwrap();
        assert!(d.is_dirty("name"));
    }

    #[test]
    fn revert_clears_dirty() {
        let mut d = DirtyFields::new();
        d.set_initial(map(&[("name", "alice")]));
        d.set_current("name", "bob").unwrap();
        d.set_current("name", "alice").unwrap();
        assert!(!d.is_dirty("name"));
    }

    #[test]
    fn reset_resets() {
        let mut d = DirtyFields::new();
        d.set_initial(map(&[("name", "alice")]));
        d.set_current("name", "bob").unwrap();
        d.reset();
        assert!(!d.any_dirty());
        assert_eq!(d.current.get("name"), Some(&"alice".into()));
    }

    #[test]
    fn diff_from_scratch() {
        let mut d = DirtyFields::new();
        d.initial = map(&[("a", "1"), ("b", "2")]);
        d.current = map(&[("a", "1"), ("b", "X")]);
        d.diff();
        assert!(d.is_dirty("b"));
        assert!(!d.is_dirty("a"));
    }

    #[test]
    fn empty_field_rejected() {
        let mut d = DirtyFields::new();
        assert!(matches!(d.set_current("", "v").unwrap_err(), DirtyError::EmptyField));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = DirtyFields::new();
        d.schema_version = "9.9.9".into();
        assert!(matches!(d.validate().unwrap_err(), DirtyError::SchemaMismatch));
    }

    #[test]
    fn fields_serde_roundtrip() {
        let mut d = DirtyFields::new();
        d.set_initial(map(&[("a", "1")]));
        d.set_current("a", "2").unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: DirtyFields = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
