//! `sovereign-cockpit-split-button` — primary action + alts menu.
//!
//! Action{id, label}. add_action appends; primary is at index 0
//! (or None when empty). swap_primary(id) promotes the action
//! with that id to index 0 (last-used-first pattern).
//! invoke(id) records a click and (when last_used_first=true)
//! promotes the action. menu() returns non-primary actions.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Action.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Action {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Invocations.
    pub invokes: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SplitButton {
    /// Schema version.
    pub schema_version: String,
    /// Actions; index 0 is primary.
    pub actions: Vec<Action>,
    /// When true, invoke(id) promotes to primary.
    pub last_used_first: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ButtonError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown id: {0}")]
    UnknownId(String),
}

impl SplitButton {
    /// New.
    pub fn new(last_used_first: bool) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            actions: Vec::new(),
            last_used_first,
        }
    }

    /// Add action.
    pub fn add_action(&mut self, id: &str, label: &str) -> Result<(), ButtonError> {
        if id.is_empty() { return Err(ButtonError::EmptyId); }
        if label.is_empty() { return Err(ButtonError::EmptyLabel); }
        if self.actions.iter().any(|a| a.id == id) {
            return Err(ButtonError::DuplicateId(id.into()));
        }
        self.actions.push(Action { id: id.into(), label: label.into(), invokes: 0 });
        Ok(())
    }

    /// Primary action.
    pub fn primary(&self) -> Option<&Action> { self.actions.first() }

    /// Menu actions (non-primary).
    pub fn menu(&self) -> &[Action] {
        if self.actions.is_empty() { &[] } else { &self.actions[1..] }
    }

    /// Promote action to primary by id.
    pub fn swap_primary(&mut self, id: &str) -> Result<(), ButtonError> {
        let pos = self.actions.iter().position(|a| a.id == id)
            .ok_or_else(|| ButtonError::UnknownId(id.into()))?;
        if pos != 0 {
            let item = self.actions.remove(pos);
            self.actions.insert(0, item);
        }
        Ok(())
    }

    /// Invoke an action by id; bumps counter; promotes if configured.
    pub fn invoke(&mut self, id: &str) -> Result<(), ButtonError> {
        let pos = self.actions.iter().position(|a| a.id == id)
            .ok_or_else(|| ButtonError::UnknownId(id.into()))?;
        self.actions[pos].invokes = self.actions[pos].invokes.saturating_add(1);
        if self.last_used_first && pos != 0 {
            let item = self.actions.remove(pos);
            self.actions.insert(0, item);
        }
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ButtonError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ButtonError::SchemaMismatch); }
        for a in &self.actions {
            if a.id.is_empty() { return Err(ButtonError::EmptyId); }
            if a.label.is_empty() { return Err(ButtonError::EmptyLabel); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn first_added_is_primary() {
        let mut b = SplitButton::new(false);
        b.add_action("save", "Save").unwrap();
        b.add_action("save_as", "Save As").unwrap();
        assert_eq!(b.primary().unwrap().id, "save");
        assert_eq!(b.menu().len(), 1);
    }

    #[test]
    fn swap_primary_promotes() {
        let mut b = SplitButton::new(false);
        b.add_action("save", "Save").unwrap();
        b.add_action("save_as", "Save As").unwrap();
        b.swap_primary("save_as").unwrap();
        assert_eq!(b.primary().unwrap().id, "save_as");
    }

    #[test]
    fn invoke_increments_counter() {
        let mut b = SplitButton::new(false);
        b.add_action("save", "Save").unwrap();
        b.invoke("save").unwrap();
        b.invoke("save").unwrap();
        assert_eq!(b.primary().unwrap().invokes, 2);
    }

    #[test]
    fn last_used_first_promotes_on_invoke() {
        let mut b = SplitButton::new(true);
        b.add_action("a", "A").unwrap();
        b.add_action("b", "B").unwrap();
        b.invoke("b").unwrap();
        assert_eq!(b.primary().unwrap().id, "b");
    }

    #[test]
    fn swap_self_is_noop() {
        let mut b = SplitButton::new(false);
        b.add_action("a", "A").unwrap();
        b.swap_primary("a").unwrap();
        assert_eq!(b.primary().unwrap().id, "a");
    }

    #[test]
    fn empty_has_no_primary() {
        let b = SplitButton::new(false);
        assert!(b.primary().is_none());
        assert!(b.menu().is_empty());
    }

    #[test]
    fn duplicate_rejected() {
        let mut b = SplitButton::new(false);
        b.add_action("a", "A").unwrap();
        assert!(matches!(b.add_action("a", "A2").unwrap_err(), ButtonError::DuplicateId(_)));
    }

    #[test]
    fn unknown_invoke_rejected() {
        let mut b = SplitButton::new(false);
        assert!(matches!(b.invoke("nope").unwrap_err(), ButtonError::UnknownId(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = SplitButton::new(false);
        b.schema_version = "9.9.9".into();
        assert!(matches!(b.validate().unwrap_err(), ButtonError::SchemaMismatch));
    }

    #[test]
    fn button_serde_roundtrip() {
        let mut b = SplitButton::new(true);
        b.add_action("a", "A").unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: SplitButton = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
