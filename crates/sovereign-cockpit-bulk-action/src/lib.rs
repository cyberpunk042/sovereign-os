//! `sovereign-cockpit-bulk-action` — bulk-action enablement.
//!
//! Each Action declares min/max selection bounds + a flag asserting
//! it requires at least one unlocked item. enabled(selected, locked)
//! returns the actions currently runnable.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One action.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Action {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Minimum selection count (≥ 1).
    pub min_count: u32,
    /// Maximum selection count (0 = unbounded).
    pub max_count: u32,
    /// Requires at least one non-locked item in selection?
    pub requires_unlocked: bool,
}

/// Registry envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BulkActionRegistry {
    /// Schema version.
    pub schema_version: String,
    /// Actions.
    pub actions: Vec<Action>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BulkActionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("action id empty")]
    EmptyId,
    /// Empty label.
    #[error("action {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate action id: {0}")]
    DuplicateId(String),
    /// min_count zero.
    #[error("action {0} min_count zero")]
    MinZero(String),
    /// max_count < min_count (when max > 0).
    #[error("action {id} max {max} < min {min}")]
    BadRange {
        /// id.
        id: String,
        /// min.
        min: u32,
        /// max.
        max: u32,
    },
}

impl BulkActionRegistry {
    /// New.
    pub fn new(actions: Vec<Action>) -> Result<Self, BulkActionError> {
        check_actions(&actions)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            actions,
        })
    }

    /// Compute enabled action ids for given selection + locked sets.
    pub fn enabled(&self, selected: &BTreeSet<String>, locked: &BTreeSet<String>) -> Vec<String> {
        let n = selected.len() as u32;
        let unlocked_count = selected.iter().filter(|s| !locked.contains(*s)).count();
        let mut out: Vec<String> = Vec::new();
        for a in &self.actions {
            if n < a.min_count { continue; }
            if a.max_count > 0 && n > a.max_count { continue; }
            if a.requires_unlocked && unlocked_count == 0 { continue; }
            out.push(a.id.clone());
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BulkActionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BulkActionError::SchemaMismatch);
        }
        check_actions(&self.actions)
    }
}

fn check_actions(a: &[Action]) -> Result<(), BulkActionError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for x in a {
        if x.id.is_empty() { return Err(BulkActionError::EmptyId); }
        if x.label.is_empty() { return Err(BulkActionError::EmptyLabel(x.id.clone())); }
        if x.min_count == 0 { return Err(BulkActionError::MinZero(x.id.clone())); }
        if x.max_count > 0 && x.max_count < x.min_count {
            return Err(BulkActionError::BadRange { id: x.id.clone(), min: x.min_count, max: x.max_count });
        }
        if !seen.insert(x.id.as_str()) {
            return Err(BulkActionError::DuplicateId(x.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a(id: &str, min: u32, max: u32, ru: bool) -> Action {
        Action {
            id: id.into(),
            label: format!("L-{id}"),
            min_count: min,
            max_count: max,
            requires_unlocked: ru,
        }
    }

    fn sel(items: &[&str]) -> BTreeSet<String> {
        items.iter().map(|s| (*s).to_string()).collect()
    }

    #[test]
    fn min_count_blocks_when_under() {
        let r = BulkActionRegistry::new(vec![a("delete", 1, 0, false)]).unwrap();
        assert!(r.enabled(&sel(&[]), &sel(&[])).is_empty());
        assert_eq!(r.enabled(&sel(&["x"]), &sel(&[])), vec!["delete"]);
    }

    #[test]
    fn max_count_blocks_when_over() {
        let r = BulkActionRegistry::new(vec![a("rename", 1, 1, false)]).unwrap();
        assert!(r.enabled(&sel(&["x", "y"]), &sel(&[])).is_empty());
        assert_eq!(r.enabled(&sel(&["x"]), &sel(&[])), vec!["rename"]);
    }

    #[test]
    fn unbounded_max_zero() {
        let r = BulkActionRegistry::new(vec![a("delete", 1, 0, false)]).unwrap();
        assert_eq!(r.enabled(&sel(&["a", "b", "c", "d", "e"]), &sel(&[])), vec!["delete"]);
    }

    #[test]
    fn requires_unlocked_filters_when_all_locked() {
        let r = BulkActionRegistry::new(vec![a("delete", 1, 0, true)]).unwrap();
        assert!(r.enabled(&sel(&["a", "b"]), &sel(&["a", "b"])).is_empty());
        assert_eq!(r.enabled(&sel(&["a", "b"]), &sel(&["a"])), vec!["delete"]);
    }

    #[test]
    fn multiple_actions_filtered_independently() {
        let r = BulkActionRegistry::new(vec![
            a("rename", 1, 1, false),
            a("delete", 1, 0, true),
        ]).unwrap();
        let e = r.enabled(&sel(&["a", "b"]), &sel(&[]));
        assert!(!e.contains(&"rename".to_string()));
        assert!(e.contains(&"delete".to_string()));
    }

    #[test]
    fn duplicate_rejected() {
        assert!(matches!(
            BulkActionRegistry::new(vec![a("d", 1, 0, false), a("d", 1, 0, false)]).unwrap_err(),
            BulkActionError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = a("a", 1, 0, false);
        x.id = String::new();
        assert!(matches!(BulkActionRegistry::new(vec![x]).unwrap_err(), BulkActionError::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut x = a("a", 1, 0, false);
        x.label = String::new();
        assert!(matches!(BulkActionRegistry::new(vec![x]).unwrap_err(), BulkActionError::EmptyLabel(_)));
    }

    #[test]
    fn min_zero_rejected() {
        assert!(matches!(
            BulkActionRegistry::new(vec![a("a", 0, 0, false)]).unwrap_err(),
            BulkActionError::MinZero(_)
        ));
    }

    #[test]
    fn max_below_min_rejected() {
        assert!(matches!(
            BulkActionRegistry::new(vec![a("a", 5, 3, false)]).unwrap_err(),
            BulkActionError::BadRange { .. }
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = BulkActionRegistry::new(vec![a("a", 1, 0, false)]).unwrap();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), BulkActionError::SchemaMismatch));
    }

    #[test]
    fn registry_serde_roundtrip() {
        let r = BulkActionRegistry::new(vec![a("rename", 1, 1, false), a("delete", 1, 0, true)]).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: BulkActionRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
