//! `sovereign-cockpit-undo-redo-stack` — undo/redo with branching.
//!
//! `push(command)` appends a new command and clears any redo
//! history. `undo()` pops from the undo stack onto the redo stack
//! and returns the command (caller does the actual reversal). `redo()`
//! re-pushes from redo onto undo. Bounded by `capacity` — overflow
//! drops oldest undo.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One command (operator-defined string + payload).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Command {
    /// Command kind / id.
    pub kind: String,
    /// Display label.
    pub label: String,
    /// Forward payload (what to do).
    pub forward_payload: String,
    /// Inverse payload (what undo should do).
    pub inverse_payload: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct UndoRedoStack {
    /// Schema version.
    pub schema_version: String,
    /// Max items kept in undo stack.
    pub capacity: usize,
    /// Done commands (most-recent at back).
    pub undo: VecDeque<Command>,
    /// Undone commands (most-recently-undone at back).
    pub redo: Vec<Command>,
    /// Total drops (overflow).
    pub dropped_oldest: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StackError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("kind empty")]
    EmptyKind,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Zero capacity.
    #[error("capacity must be > 0")]
    ZeroCapacity,
    /// Nothing to undo.
    #[error("undo stack empty")]
    NothingToUndo,
    /// Nothing to redo.
    #[error("redo stack empty")]
    NothingToRedo,
}

impl UndoRedoStack {
    /// New.
    pub fn new(capacity: usize) -> Result<Self, StackError> {
        if capacity == 0 { return Err(StackError::ZeroCapacity); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            undo: VecDeque::with_capacity(capacity),
            redo: Vec::new(),
            dropped_oldest: 0,
        })
    }

    /// Push a new command (clears redo).
    pub fn push(&mut self, command: Command) -> Result<(), StackError> {
        if command.kind.is_empty() { return Err(StackError::EmptyKind); }
        if command.label.is_empty() { return Err(StackError::EmptyLabel); }
        // New work invalidates any redo branch.
        self.redo.clear();
        if self.undo.len() == self.capacity {
            self.undo.pop_front();
            self.dropped_oldest = self.dropped_oldest.saturating_add(1);
        }
        self.undo.push_back(command);
        Ok(())
    }

    /// Undo — returns command to be reversed by caller.
    pub fn undo(&mut self) -> Result<Command, StackError> {
        let c = self.undo.pop_back().ok_or(StackError::NothingToUndo)?;
        self.redo.push(c.clone());
        Ok(c)
    }

    /// Redo — returns command to be re-applied by caller.
    pub fn redo(&mut self) -> Result<Command, StackError> {
        let c = self.redo.pop().ok_or(StackError::NothingToRedo)?;
        // Putting it back into undo without overflow (capacity already accounted).
        if self.undo.len() == self.capacity {
            self.undo.pop_front();
            self.dropped_oldest = self.dropped_oldest.saturating_add(1);
        }
        self.undo.push_back(c.clone());
        Ok(c)
    }

    /// Can undo?
    pub fn can_undo(&self) -> bool { !self.undo.is_empty() }

    /// Can redo?
    pub fn can_redo(&self) -> bool { !self.redo.is_empty() }

    /// Clear all.
    pub fn clear(&mut self) {
        self.undo.clear();
        self.redo.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StackError> {
        if self.schema_version != SCHEMA_VERSION { return Err(StackError::SchemaMismatch); }
        if self.capacity == 0 { return Err(StackError::ZeroCapacity); }
        for c in self.undo.iter().chain(self.redo.iter()) {
            if c.kind.is_empty() { return Err(StackError::EmptyKind); }
            if c.label.is_empty() { return Err(StackError::EmptyLabel); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cmd(label: &str) -> Command {
        Command {
            kind: "edit".into(),
            label: label.into(),
            forward_payload: "+".into(),
            inverse_payload: "-".into(),
        }
    }

    #[test]
    fn push_and_undo() {
        let mut s = UndoRedoStack::new(10).unwrap();
        s.push(cmd("a")).unwrap();
        let c = s.undo().unwrap();
        assert_eq!(c.label, "a");
        assert!(!s.can_undo());
        assert!(s.can_redo());
    }

    #[test]
    fn undo_then_redo() {
        let mut s = UndoRedoStack::new(10).unwrap();
        s.push(cmd("a")).unwrap();
        s.undo().unwrap();
        let c = s.redo().unwrap();
        assert_eq!(c.label, "a");
        assert!(s.can_undo());
        assert!(!s.can_redo());
    }

    #[test]
    fn push_after_undo_clears_redo() {
        let mut s = UndoRedoStack::new(10).unwrap();
        s.push(cmd("a")).unwrap();
        s.undo().unwrap();
        s.push(cmd("b")).unwrap();
        // Redo stack should be empty.
        assert!(matches!(s.redo().unwrap_err(), StackError::NothingToRedo));
    }

    #[test]
    fn capacity_drops_oldest() {
        let mut s = UndoRedoStack::new(2).unwrap();
        s.push(cmd("a")).unwrap();
        s.push(cmd("b")).unwrap();
        s.push(cmd("c")).unwrap();
        assert_eq!(s.dropped_oldest, 1);
        // "a" dropped; undo returns "c".
        assert_eq!(s.undo().unwrap().label, "c");
        assert_eq!(s.undo().unwrap().label, "b");
        assert!(!s.can_undo());
    }

    #[test]
    fn empty_undo_rejected() {
        let mut s = UndoRedoStack::new(10).unwrap();
        assert!(matches!(s.undo().unwrap_err(), StackError::NothingToUndo));
    }

    #[test]
    fn empty_redo_rejected() {
        let mut s = UndoRedoStack::new(10).unwrap();
        assert!(matches!(s.redo().unwrap_err(), StackError::NothingToRedo));
    }

    #[test]
    fn clear_zeros() {
        let mut s = UndoRedoStack::new(10).unwrap();
        s.push(cmd("a")).unwrap();
        s.clear();
        assert!(!s.can_undo());
    }

    #[test]
    fn zero_capacity_rejected() {
        assert!(matches!(UndoRedoStack::new(0).unwrap_err(), StackError::ZeroCapacity));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = UndoRedoStack::new(10).unwrap();
        assert!(matches!(s.push(Command { kind: "".into(), label: "x".into(), forward_payload: "".into(), inverse_payload: "".into() }).unwrap_err(), StackError::EmptyKind));
        assert!(matches!(s.push(Command { kind: "k".into(), label: "".into(), forward_payload: "".into(), inverse_payload: "".into() }).unwrap_err(), StackError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = UndoRedoStack::new(10).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), StackError::SchemaMismatch));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = UndoRedoStack::new(5).unwrap();
        s.push(cmd("a")).unwrap();
        s.push(cmd("b")).unwrap();
        s.undo().unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: UndoRedoStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
