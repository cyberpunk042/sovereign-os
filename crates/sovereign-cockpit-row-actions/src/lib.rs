//! `sovereign-cockpit-row-actions` — per-row contextual actions.
//!
//! Each row has a `left_actions` set (swipe-right reveals) + a
//! `right_actions` set (swipe-left reveals). Each action carries a
//! `severity` so the chrome can color it (Default / Caution /
//! Destructive) and `requires_confirm` for an extra prompt.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Action severity.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Default.
    Default,
    /// Caution (yellow).
    Caution,
    /// Destructive (red).
    Destructive,
}

/// One action.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Action {
    /// Stable id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Severity.
    pub severity: Severity,
    /// Requires confirm step.
    pub requires_confirm: bool,
}

/// Side.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Side {
    /// Left (swipe right).
    Left,
    /// Right (swipe left).
    Right,
}

/// Per-row set.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct RowSet {
    /// Left swipe (revealed by swipe-right).
    pub left: Vec<Action>,
    /// Right swipe (revealed by swipe-left).
    pub right: Vec<Action>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RowActions {
    /// Schema version.
    pub schema_version: String,
    /// row_id → RowSet.
    pub by_row: BTreeMap<String, RowSet>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RowError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Duplicate action.
    #[error("duplicate action id on side: {0}")]
    DuplicateAction(String),
}

impl RowActions {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            by_row: BTreeMap::new(),
        }
    }

    /// Add an action on a side.
    pub fn add(&mut self, row_id: &str, side: Side, action: Action) -> Result<(), RowError> {
        if row_id.is_empty() || action.id.is_empty() {
            return Err(RowError::EmptyId);
        }
        let set = self.by_row.entry(row_id.into()).or_default();
        let vec = match side {
            Side::Left => &mut set.left,
            Side::Right => &mut set.right,
        };
        if vec.iter().any(|a| a.id == action.id) {
            return Err(RowError::DuplicateAction(action.id));
        }
        vec.push(action);
        Ok(())
    }

    /// Remove an action by (side, id). Returns true if removed.
    pub fn remove(&mut self, row_id: &str, side: Side, action_id: &str) -> bool {
        if let Some(set) = self.by_row.get_mut(row_id) {
            let vec = match side {
                Side::Left => &mut set.left,
                Side::Right => &mut set.right,
            };
            if let Some(pos) = vec.iter().position(|a| a.id == action_id) {
                vec.remove(pos);
                if set.left.is_empty() && set.right.is_empty() {
                    self.by_row.remove(row_id);
                }
                return true;
            }
        }
        false
    }

    /// Actions on a side.
    pub fn actions_on(&self, row_id: &str, side: Side) -> Vec<Action> {
        match self.by_row.get(row_id) {
            Some(set) => match side {
                Side::Left => set.left.clone(),
                Side::Right => set.right.clone(),
            },
            None => Vec::new(),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RowError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RowError::SchemaMismatch);
        }
        for (id, set) in &self.by_row {
            if id.is_empty() {
                return Err(RowError::EmptyId);
            }
            use std::collections::HashSet;
            for v in [&set.left, &set.right] {
                let mut seen: HashSet<&str> = HashSet::new();
                for a in v {
                    if a.id.is_empty() {
                        return Err(RowError::EmptyId);
                    }
                    if !seen.insert(a.id.as_str()) {
                        return Err(RowError::DuplicateAction(a.id.clone()));
                    }
                }
            }
        }
        Ok(())
    }
}

impl Default for RowActions {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a(id: &str, sev: Severity, confirm: bool) -> Action {
        Action {
            id: id.into(),
            label: id.into(),
            severity: sev,
            requires_confirm: confirm,
        }
    }

    #[test]
    fn add_and_query() {
        let mut r = RowActions::new();
        r.add(
            "row-1",
            Side::Right,
            a("delete", Severity::Destructive, true),
        )
        .unwrap();
        r.add("row-1", Side::Left, a("archive", Severity::Default, false))
            .unwrap();
        assert_eq!(r.actions_on("row-1", Side::Right).len(), 1);
        assert_eq!(r.actions_on("row-1", Side::Left).len(), 1);
    }

    #[test]
    fn duplicate_rejected_per_side() {
        let mut r = RowActions::new();
        r.add(
            "row-1",
            Side::Right,
            a("delete", Severity::Destructive, true),
        )
        .unwrap();
        assert!(matches!(
            r.add("row-1", Side::Right, a("delete", Severity::Default, false))
                .unwrap_err(),
            RowError::DuplicateAction(_)
        ));
    }

    #[test]
    fn same_id_allowed_on_different_sides() {
        let mut r = RowActions::new();
        r.add("row-1", Side::Right, a("share", Severity::Default, false))
            .unwrap();
        r.add("row-1", Side::Left, a("share", Severity::Default, false))
            .unwrap();
    }

    #[test]
    fn remove_clears_row_when_empty() {
        let mut r = RowActions::new();
        r.add("row-1", Side::Right, a("x", Severity::Default, false))
            .unwrap();
        assert!(r.remove("row-1", Side::Right, "x"));
        assert!(!r.by_row.contains_key("row-1"));
    }

    #[test]
    fn remove_unknown_returns_false() {
        let mut r = RowActions::new();
        assert!(!r.remove("row-x", Side::Right, "missing"));
    }

    #[test]
    fn empty_id_rejected() {
        let mut r = RowActions::new();
        assert!(matches!(
            r.add("", Side::Right, a("x", Severity::Default, false))
                .unwrap_err(),
            RowError::EmptyId
        ));
        assert!(matches!(
            r.add("row-1", Side::Right, a("", Severity::Default, false))
                .unwrap_err(),
            RowError::EmptyId
        ));
    }

    #[test]
    fn unknown_row_actions_empty() {
        let r = RowActions::new();
        assert!(r.actions_on("row-x", Side::Right).is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = RowActions::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            RowError::SchemaMismatch
        ));
    }

    #[test]
    fn actions_serde_roundtrip() {
        let mut r = RowActions::new();
        r.add(
            "row-1",
            Side::Right,
            a("delete", Severity::Destructive, true),
        )
        .unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: RowActions = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
