//! `sovereign-cockpit-undo-stack` — operator action undo history.
//!
//! Each `UndoEntry` records (kind, label, reverse_payload, performed_at,
//! performed_by). Stack is LIFO with a fixed capacity of 100.
//! `redo_stack` mirrors after `undo()`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Maximum stack depth.
pub const MAX_DEPTH: usize = 100;

/// Kind of reversible action.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ActionKind {
    /// Dashboard toggle.
    ToggleFlip,
    /// Execution mode switch.
    ModeSwitch,
    /// Bookmark add.
    BookmarkAdd,
    /// Bookmark remove.
    BookmarkRemove,
    /// Prompt-template add.
    TemplateAdd,
    /// Prompt-template remove.
    TemplateRemove,
    /// Workspace folder add.
    WorkspaceAdd,
    /// Workspace folder remove.
    WorkspaceRemove,
}

/// One undo entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct UndoEntry {
    /// Action kind.
    pub kind: ActionKind,
    /// Operator-readable label.
    pub label: String,
    /// Opaque payload describing how to reverse (JSON string).
    pub reverse_payload: String,
    /// ISO-8601 UTC.
    pub performed_at: String,
    /// Operator MS003 fingerprint.
    pub performed_by: String,
}

/// Stack envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct UndoStack {
    /// Schema version.
    pub schema_version: String,
    /// Past actions (newest at end).
    pub undo: Vec<UndoEntry>,
    /// Actions popped by `undo()` that can be `redo()`-ed.
    pub redo: Vec<UndoEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum UndoError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty label.
    #[error("undo entry label empty")]
    EmptyLabel,
    /// Empty performed_at.
    #[error("undo entry {0} missing performed_at")]
    MissingTimestamp(String),
    /// Empty performed_by.
    #[error("undo entry {0} missing performed_by")]
    MissingActor(String),
    /// undo() called on empty stack.
    #[error("undo stack empty")]
    NothingToUndo,
    /// redo() called on empty stack.
    #[error("redo stack empty")]
    NothingToRedo,
}

impl UndoStack {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            undo: Vec::new(),
            redo: Vec::new(),
        }
    }

    /// Record an action (clears redo stack).
    pub fn record(&mut self, entry: UndoEntry) -> Result<(), UndoError> {
        if entry.label.is_empty() { return Err(UndoError::EmptyLabel); }
        if entry.performed_at.is_empty() { return Err(UndoError::MissingTimestamp(entry.label)); }
        if entry.performed_by.is_empty() { return Err(UndoError::MissingActor(entry.label)); }
        self.undo.push(entry);
        while self.undo.len() > MAX_DEPTH {
            self.undo.remove(0);
        }
        self.redo.clear();
        Ok(())
    }

    /// Pop one action onto the redo stack.
    pub fn undo(&mut self) -> Result<UndoEntry, UndoError> {
        let e = self.undo.pop().ok_or(UndoError::NothingToUndo)?;
        self.redo.push(e.clone());
        Ok(e)
    }

    /// Pop one redo back onto the undo stack.
    pub fn redo(&mut self) -> Result<UndoEntry, UndoError> {
        let e = self.redo.pop().ok_or(UndoError::NothingToRedo)?;
        self.undo.push(e.clone());
        Ok(e)
    }

    /// Depth of the undo stack.
    pub fn depth(&self) -> usize { self.undo.len() }

    /// Depth of the redo stack.
    pub fn redo_depth(&self) -> usize { self.redo.len() }

    /// Validate.
    pub fn validate(&self) -> Result<(), UndoError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(UndoError::SchemaMismatch);
        }
        for e in self.undo.iter().chain(self.redo.iter()) {
            if e.label.is_empty() { return Err(UndoError::EmptyLabel); }
            if e.performed_at.is_empty() { return Err(UndoError::MissingTimestamp(e.label.clone())); }
            if e.performed_by.is_empty() { return Err(UndoError::MissingActor(e.label.clone())); }
        }
        Ok(())
    }
}

impl Default for UndoStack {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn e(label: &str, kind: ActionKind) -> UndoEntry {
        UndoEntry {
            kind,
            label: label.into(),
            reverse_payload: "{}".into(),
            performed_at: "2026-05-19T03:00:00Z".into(),
            performed_by: "op".into(),
        }
    }

    #[test]
    fn empty_stack_validates() {
        UndoStack::new().validate().unwrap();
    }

    #[test]
    fn record_undo_redo_cycle() {
        let mut s = UndoStack::new();
        s.record(e("toggle X", ActionKind::ToggleFlip)).unwrap();
        s.record(e("mode->Execute", ActionKind::ModeSwitch)).unwrap();
        assert_eq!(s.depth(), 2);
        let popped = s.undo().unwrap();
        assert_eq!(popped.label, "mode->Execute");
        assert_eq!(s.depth(), 1);
        assert_eq!(s.redo_depth(), 1);
        let redone = s.redo().unwrap();
        assert_eq!(redone.label, "mode->Execute");
        assert_eq!(s.depth(), 2);
        assert_eq!(s.redo_depth(), 0);
    }

    #[test]
    fn record_clears_redo_stack() {
        let mut s = UndoStack::new();
        s.record(e("a", ActionKind::ToggleFlip)).unwrap();
        s.undo().unwrap();
        assert_eq!(s.redo_depth(), 1);
        s.record(e("b", ActionKind::ToggleFlip)).unwrap();
        assert_eq!(s.redo_depth(), 0);
    }

    #[test]
    fn undo_on_empty_rejected() {
        let mut s = UndoStack::new();
        assert!(matches!(s.undo().unwrap_err(), UndoError::NothingToUndo));
    }

    #[test]
    fn redo_on_empty_rejected() {
        let mut s = UndoStack::new();
        assert!(matches!(s.redo().unwrap_err(), UndoError::NothingToRedo));
    }

    #[test]
    fn empty_label_rejected() {
        let mut s = UndoStack::new();
        let err = s.record(e("", ActionKind::ToggleFlip)).unwrap_err();
        assert!(matches!(err, UndoError::EmptyLabel));
    }

    #[test]
    fn missing_timestamp_rejected() {
        let mut s = UndoStack::new();
        let mut entry = e("x", ActionKind::ToggleFlip);
        entry.performed_at = String::new();
        let err = s.record(entry).unwrap_err();
        assert!(matches!(err, UndoError::MissingTimestamp(_)));
    }

    #[test]
    fn overflow_drops_oldest() {
        let mut s = UndoStack::new();
        for i in 0..(MAX_DEPTH + 5) {
            s.record(e(&format!("a{i}"), ActionKind::ToggleFlip)).unwrap();
        }
        assert_eq!(s.depth(), MAX_DEPTH);
        // Oldest 5 dropped → first remaining is "a5"
        assert_eq!(s.undo[0].label, "a5");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = UndoStack::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), UndoError::SchemaMismatch));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(serde_json::to_string(&ActionKind::ToggleFlip).unwrap(), "\"toggle-flip\"");
        assert_eq!(serde_json::to_string(&ActionKind::ModeSwitch).unwrap(), "\"mode-switch\"");
        assert_eq!(serde_json::to_string(&ActionKind::BookmarkAdd).unwrap(), "\"bookmark-add\"");
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = UndoStack::new();
        s.record(e("a", ActionKind::ToggleFlip)).unwrap();
        s.undo().unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: UndoStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
