//! `sovereign-cockpit-quick-action` — one-tap action registry.
//!
//! Each QuickAction has (id, label, icon, hotkey, enabled). The
//! registry tracks usage counts and ordered_for_display() returns
//! the actions sorted by descending use_count (ties by insertion
//! order). Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One quick action.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct QuickAction {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Icon hint (engine-supplied id; cockpit resolves to glyph).
    pub icon: String,
    /// Hotkey chord (optional, "" means none).
    pub hotkey: String,
    /// Enabled?
    pub enabled: bool,
    /// Use count (bumps via record_use).
    pub use_count: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct QuickActions {
    /// Schema version.
    pub schema_version: String,
    /// Actions in insertion order.
    pub actions: Vec<QuickAction>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum QuickActionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("action id empty")]
    EmptyId,
    /// Empty label.
    #[error("action {0} label empty")]
    EmptyLabel(String),
    /// Empty icon.
    #[error("action {0} icon empty")]
    EmptyIcon(String),
    /// Duplicate id.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Unknown id.
    #[error("unknown id: {0}")]
    Unknown(String),
}

impl QuickActions {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            actions: Vec::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, a: QuickAction) -> Result<(), QuickActionError> {
        check_action(&a)?;
        if self.actions.iter().any(|x| x.id == a.id) {
            return Err(QuickActionError::DuplicateId(a.id));
        }
        self.actions.push(a);
        Ok(())
    }

    /// Record usage.
    pub fn record_use(&mut self, id: &str) -> Result<(), QuickActionError> {
        let a = self
            .actions
            .iter_mut()
            .find(|a| a.id == id)
            .ok_or_else(|| QuickActionError::Unknown(id.into()))?;
        a.use_count = a.use_count.saturating_add(1);
        Ok(())
    }

    /// Sorted view by descending use_count (insertion order for ties).
    pub fn ordered_for_display(&self) -> Vec<&QuickAction> {
        let mut indexed: Vec<(usize, &QuickAction)> = self.actions.iter().enumerate().collect();
        indexed.sort_by(|(ia, a), (ib, b)| b.use_count.cmp(&a.use_count).then(ia.cmp(ib)));
        indexed.into_iter().map(|(_, a)| a).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), QuickActionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(QuickActionError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for a in &self.actions {
            check_action(a)?;
            if !seen.insert(a.id.as_str()) {
                return Err(QuickActionError::DuplicateId(a.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_action(a: &QuickAction) -> Result<(), QuickActionError> {
    if a.id.is_empty() {
        return Err(QuickActionError::EmptyId);
    }
    if a.label.is_empty() {
        return Err(QuickActionError::EmptyLabel(a.id.clone()));
    }
    if a.icon.is_empty() {
        return Err(QuickActionError::EmptyIcon(a.id.clone()));
    }
    Ok(())
}

impl Default for QuickActions {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn act(id: &str) -> QuickAction {
        QuickAction {
            id: id.into(),
            label: format!("L-{id}"),
            icon: format!("icon-{id}"),
            hotkey: String::new(),
            enabled: true,
            use_count: 0,
        }
    }

    #[test]
    fn register_and_record() {
        let mut q = QuickActions::new();
        q.register(act("save")).unwrap();
        q.record_use("save").unwrap();
        assert_eq!(q.actions[0].use_count, 1);
    }

    #[test]
    fn record_unknown_rejected() {
        let mut q = QuickActions::new();
        assert!(matches!(
            q.record_use("none").unwrap_err(),
            QuickActionError::Unknown(_)
        ));
    }

    #[test]
    fn duplicate_rejected() {
        let mut q = QuickActions::new();
        q.register(act("a")).unwrap();
        assert!(matches!(
            q.register(act("a")).unwrap_err(),
            QuickActionError::DuplicateId(_)
        ));
    }

    #[test]
    fn ordered_by_use_count_desc() {
        let mut q = QuickActions::new();
        q.register(act("a")).unwrap();
        q.register(act("b")).unwrap();
        q.register(act("c")).unwrap();
        q.record_use("b").unwrap();
        q.record_use("b").unwrap();
        q.record_use("c").unwrap();
        let order: Vec<&str> = q
            .ordered_for_display()
            .iter()
            .map(|a| a.id.as_str())
            .collect();
        assert_eq!(order, vec!["b", "c", "a"]);
    }

    #[test]
    fn order_stable_on_tie() {
        let mut q = QuickActions::new();
        q.register(act("a")).unwrap();
        q.register(act("b")).unwrap();
        q.register(act("c")).unwrap();
        let order: Vec<&str> = q
            .ordered_for_display()
            .iter()
            .map(|a| a.id.as_str())
            .collect();
        assert_eq!(order, vec!["a", "b", "c"]);
    }

    #[test]
    fn empty_id_rejected() {
        let mut q = QuickActions::new();
        let mut a = act("a");
        a.id = String::new();
        assert!(matches!(
            q.register(a).unwrap_err(),
            QuickActionError::EmptyId
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let mut q = QuickActions::new();
        let mut a = act("a");
        a.label = String::new();
        assert!(matches!(
            q.register(a).unwrap_err(),
            QuickActionError::EmptyLabel(_)
        ));
    }

    #[test]
    fn empty_icon_rejected() {
        let mut q = QuickActions::new();
        let mut a = act("a");
        a.icon = String::new();
        assert!(matches!(
            q.register(a).unwrap_err(),
            QuickActionError::EmptyIcon(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut q = QuickActions::new();
        q.schema_version = "9.9.9".into();
        assert!(matches!(
            q.validate().unwrap_err(),
            QuickActionError::SchemaMismatch
        ));
    }

    #[test]
    fn actions_serde_roundtrip() {
        let mut q = QuickActions::new();
        q.register(act("a")).unwrap();
        q.record_use("a").unwrap();
        let j = serde_json::to_string(&q).unwrap();
        let back: QuickActions = serde_json::from_str(&j).unwrap();
        assert_eq!(q, back);
    }
}
