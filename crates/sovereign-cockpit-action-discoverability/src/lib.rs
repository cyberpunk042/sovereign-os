//! `sovereign-cockpit-action-discoverability` — usage telemetry.
//!
//! `register(action_id, label, category)` enumerates a discoverable
//! action. `record_use(action_id, ts_ms)` marks usage. `undiscovered(
//! min_age_ms, now_ms)` lists actions that have never been used and
//! have existed at least `min_age_ms` (we record `created_at_ms`
//! when registered). `most_used(n)` and `least_used(n)` return
//! top/bottom by use_count.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One action's usage record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionUsage {
    /// Action id.
    pub action_id: String,
    /// Label.
    pub label: String,
    /// Category.
    pub category: String,
    /// Created ts (when registered).
    pub created_at_ms: u64,
    /// Use count.
    pub use_count: u64,
    /// Last used (0 if never).
    pub last_used_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionDiscoverability {
    /// Schema version.
    pub schema_version: String,
    /// id → action.
    pub actions: BTreeMap<String, ActionUsage>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DiscoverabilityError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Empty.
    #[error("category empty")]
    EmptyCategory,
    /// Unknown.
    #[error("unknown action: {0}")]
    UnknownAction(String),
}

impl ActionDiscoverability {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            actions: BTreeMap::new(),
        }
    }

    /// Register (idempotent — preserves use_count on re-registration).
    pub fn register(&mut self, action_id: &str, label: &str, category: &str, ts_ms: u64) -> Result<(), DiscoverabilityError> {
        if action_id.is_empty() { return Err(DiscoverabilityError::EmptyId); }
        if label.is_empty() { return Err(DiscoverabilityError::EmptyLabel); }
        if category.is_empty() { return Err(DiscoverabilityError::EmptyCategory); }
        let entry = self.actions.entry(action_id.into()).or_insert(ActionUsage {
            action_id: action_id.into(),
            label: label.into(),
            category: category.into(),
            created_at_ms: ts_ms,
            use_count: 0,
            last_used_ms: 0,
        });
        // Update label/category on re-register.
        entry.label = label.into();
        entry.category = category.into();
        Ok(())
    }

    /// Record use.
    pub fn record_use(&mut self, action_id: &str, ts_ms: u64) -> Result<(), DiscoverabilityError> {
        let a = self.actions.get_mut(action_id).ok_or_else(|| DiscoverabilityError::UnknownAction(action_id.into()))?;
        a.use_count = a.use_count.saturating_add(1);
        a.last_used_ms = ts_ms;
        Ok(())
    }

    /// Undiscovered (never used, existed at least min_age).
    pub fn undiscovered(&self, min_age_ms: u64, now_ms: u64) -> Vec<ActionUsage> {
        let mut v: Vec<ActionUsage> = self.actions.values()
            .filter(|a| a.use_count == 0 && now_ms.saturating_sub(a.created_at_ms) >= min_age_ms)
            .cloned()
            .collect();
        v.sort_by(|a, b| a.created_at_ms.cmp(&b.created_at_ms).then(a.action_id.cmp(&b.action_id)));
        v
    }

    /// Most used.
    pub fn most_used(&self, n: usize) -> Vec<ActionUsage> {
        let mut v: Vec<ActionUsage> = self.actions.values().cloned().collect();
        v.sort_by(|a, b| b.use_count.cmp(&a.use_count).then(a.label.cmp(&b.label)));
        v.truncate(n);
        v
    }

    /// Least used.
    pub fn least_used(&self, n: usize) -> Vec<ActionUsage> {
        let mut v: Vec<ActionUsage> = self.actions.values().cloned().collect();
        v.sort_by(|a, b| a.use_count.cmp(&b.use_count).then(a.label.cmp(&b.label)));
        v.truncate(n);
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DiscoverabilityError> {
        if self.schema_version != SCHEMA_VERSION { return Err(DiscoverabilityError::SchemaMismatch); }
        for (id, a) in &self.actions {
            if id.is_empty() { return Err(DiscoverabilityError::EmptyId); }
            if a.label.is_empty() { return Err(DiscoverabilityError::EmptyLabel); }
            if a.category.is_empty() { return Err(DiscoverabilityError::EmptyCategory); }
        }
        Ok(())
    }
}

impl Default for ActionDiscoverability {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_and_record() {
        let mut d = ActionDiscoverability::new();
        d.register("save", "Save", "file", 0).unwrap();
        d.record_use("save", 100).unwrap();
        assert_eq!(d.actions["save"].use_count, 1);
    }

    #[test]
    fn undiscovered_filters_used_and_too_new() {
        let mut d = ActionDiscoverability::new();
        d.register("old-unused", "X", "c", 0).unwrap();
        d.register("new-unused", "Y", "c", 9_000).unwrap();
        d.register("used", "Z", "c", 0).unwrap();
        d.record_use("used", 5_000).unwrap();
        // now = 10_000, min_age = 5000.
        let u = d.undiscovered(5_000, 10_000);
        assert_eq!(u.len(), 1);
        assert_eq!(u[0].action_id, "old-unused");
    }

    #[test]
    fn most_used_sorted() {
        let mut d = ActionDiscoverability::new();
        d.register("a", "A", "c", 0).unwrap();
        d.register("b", "B", "c", 0).unwrap();
        for _ in 0..5 { d.record_use("a", 0).unwrap(); }
        d.record_use("b", 0).unwrap();
        let top = d.most_used(2);
        assert_eq!(top[0].action_id, "a");
        assert_eq!(top[1].action_id, "b");
    }

    #[test]
    fn least_used_sorted() {
        let mut d = ActionDiscoverability::new();
        d.register("a", "A", "c", 0).unwrap();
        d.register("b", "B", "c", 0).unwrap();
        d.record_use("b", 0).unwrap();
        let bot = d.least_used(1);
        assert_eq!(bot[0].action_id, "a");
    }

    #[test]
    fn register_idempotent_preserves_count() {
        let mut d = ActionDiscoverability::new();
        d.register("a", "Old", "x", 0).unwrap();
        d.record_use("a", 0).unwrap();
        d.register("a", "New", "y", 100).unwrap();
        // Label/category updated, but use_count preserved.
        assert_eq!(d.actions["a"].label, "New");
        assert_eq!(d.actions["a"].use_count, 1);
    }

    #[test]
    fn unknown_record_use_rejected() {
        let mut d = ActionDiscoverability::new();
        assert!(matches!(d.record_use("nope", 0).unwrap_err(), DiscoverabilityError::UnknownAction(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut d = ActionDiscoverability::new();
        assert!(matches!(d.register("", "x", "c", 0).unwrap_err(), DiscoverabilityError::EmptyId));
        assert!(matches!(d.register("a", "", "c", 0).unwrap_err(), DiscoverabilityError::EmptyLabel));
        assert!(matches!(d.register("a", "x", "", 0).unwrap_err(), DiscoverabilityError::EmptyCategory));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = ActionDiscoverability::new();
        d.schema_version = "9.9.9".into();
        assert!(matches!(d.validate().unwrap_err(), DiscoverabilityError::SchemaMismatch));
    }

    #[test]
    fn discoverability_serde_roundtrip() {
        let mut d = ActionDiscoverability::new();
        d.register("save", "Save", "file", 0).unwrap();
        d.record_use("save", 100).unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: ActionDiscoverability = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
