//! `sovereign-cockpit-modal-stack` — Z-ordered modal stack.
//!
//! Stack of currently-open modal dialogs. Top draws above bottom; only
//! the top accepts keyboard focus. Closing a modal pops it.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Maximum modal depth.
pub const MAX_DEPTH: usize = 8;

/// One modal entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModalEntry {
    /// Modal id.
    pub id: String,
    /// Modal kind name (e.g. "confirmation", "settings", "command-palette").
    pub kind: String,
    /// Payload (serialized JSON, opaque to this crate).
    pub payload: String,
}

/// Modal stack.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModalStack {
    /// Schema version.
    pub schema_version: String,
    /// Stack (top = last element).
    pub stack: Vec<ModalEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ModalError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("modal id empty")]
    EmptyId,
    /// Empty kind.
    #[error("modal {0} kind empty")]
    EmptyKind(String),
    /// Duplicate id.
    #[error("duplicate modal id: {0}")]
    DuplicateId(String),
    /// Stack full.
    #[error("stack full (depth {MAX_DEPTH})")]
    Full,
    /// Nothing to pop.
    #[error("stack empty")]
    Empty,
    /// Unknown id.
    #[error("unknown modal id: {0}")]
    Unknown(String),
}

impl ModalStack {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            stack: Vec::new(),
        }
    }

    /// Push a modal.
    pub fn push(&mut self, m: ModalEntry) -> Result<(), ModalError> {
        if m.id.is_empty() {
            return Err(ModalError::EmptyId);
        }
        if m.kind.is_empty() {
            return Err(ModalError::EmptyKind(m.id));
        }
        if self.stack.iter().any(|e| e.id == m.id) {
            return Err(ModalError::DuplicateId(m.id));
        }
        if self.stack.len() >= MAX_DEPTH {
            return Err(ModalError::Full);
        }
        self.stack.push(m);
        Ok(())
    }

    /// Pop top modal.
    pub fn pop(&mut self) -> Result<ModalEntry, ModalError> {
        self.stack.pop().ok_or(ModalError::Empty)
    }

    /// Close a specific modal by id (collapses stack).
    pub fn close(&mut self, id: &str) -> Result<(), ModalError> {
        let pos = self
            .stack
            .iter()
            .position(|e| e.id == id)
            .ok_or_else(|| ModalError::Unknown(id.into()))?;
        self.stack.remove(pos);
        Ok(())
    }

    /// Currently-focused modal (top of stack).
    pub fn focused(&self) -> Option<&ModalEntry> {
        self.stack.last()
    }

    /// Depth.
    pub fn depth(&self) -> usize {
        self.stack.len()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ModalError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ModalError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for e in &self.stack {
            if e.id.is_empty() {
                return Err(ModalError::EmptyId);
            }
            if e.kind.is_empty() {
                return Err(ModalError::EmptyKind(e.id.clone()));
            }
            if !seen.insert(e.id.as_str()) {
                return Err(ModalError::DuplicateId(e.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for ModalStack {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn m(id: &str, kind: &str) -> ModalEntry {
        ModalEntry {
            id: id.into(),
            kind: kind.into(),
            payload: "{}".into(),
        }
    }

    #[test]
    fn empty_stack_validates() {
        ModalStack::new().validate().unwrap();
    }

    #[test]
    fn push_and_focus() {
        let mut s = ModalStack::new();
        s.push(m("a", "confirmation")).unwrap();
        s.push(m("b", "settings")).unwrap();
        assert_eq!(s.focused().unwrap().id, "b");
    }

    #[test]
    fn pop_collapses() {
        let mut s = ModalStack::new();
        s.push(m("a", "x")).unwrap();
        s.push(m("b", "x")).unwrap();
        let popped = s.pop().unwrap();
        assert_eq!(popped.id, "b");
        assert_eq!(s.focused().unwrap().id, "a");
    }

    #[test]
    fn close_specific() {
        let mut s = ModalStack::new();
        s.push(m("a", "x")).unwrap();
        s.push(m("b", "x")).unwrap();
        s.push(m("c", "x")).unwrap();
        s.close("b").unwrap();
        assert_eq!(s.depth(), 2);
        assert_eq!(s.focused().unwrap().id, "c");
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = ModalStack::new();
        s.push(m("a", "x")).unwrap();
        assert!(matches!(
            s.push(m("a", "y")).unwrap_err(),
            ModalError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = ModalStack::new();
        assert!(matches!(
            s.push(m("", "x")).unwrap_err(),
            ModalError::EmptyId
        ));
    }

    #[test]
    fn empty_kind_rejected() {
        let mut s = ModalStack::new();
        assert!(matches!(
            s.push(m("a", "")).unwrap_err(),
            ModalError::EmptyKind(_)
        ));
    }

    #[test]
    fn full_rejected() {
        let mut s = ModalStack::new();
        for i in 0..MAX_DEPTH {
            s.push(m(&format!("m{i}"), "x")).unwrap();
        }
        assert!(matches!(
            s.push(m("over", "x")).unwrap_err(),
            ModalError::Full
        ));
    }

    #[test]
    fn pop_empty_rejected() {
        let mut s = ModalStack::new();
        assert!(matches!(s.pop().unwrap_err(), ModalError::Empty));
    }

    #[test]
    fn close_unknown_rejected() {
        let mut s = ModalStack::new();
        assert!(matches!(
            s.close("none").unwrap_err(),
            ModalError::Unknown(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ModalStack::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            ModalError::SchemaMismatch
        ));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = ModalStack::new();
        s.push(m("a", "x")).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ModalStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
