//! `sovereign-cockpit-cell-editor` — inline cell-editor state.
//!
//! Edits a single (row, col). begin() captures original; type_text
//! mutates buffer + dirty; commit() returns Committed{new}; cancel()
//! returns Reverted{original}. set_validation_error blocks commit.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Grid coordinate.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct Coord {
    /// Row.
    pub row: u32,
    /// Column.
    pub col: u32,
}

/// Transaction outcome.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum TransactionOutcome {
    /// Committed; new value supplied.
    Committed {
        /// new.
        new: String,
    },
    /// Reverted to original.
    Reverted {
        /// original.
        original: String,
    },
    /// Commit blocked by validation_error.
    Blocked {
        /// error.
        error: String,
    },
    /// No active edit.
    NoOp,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CellEditor {
    /// Schema version.
    pub schema_version: String,
    /// Active edit (None = nothing being edited).
    pub active: Option<Coord>,
    /// Original value captured on begin.
    pub original: String,
    /// In-progress edit buffer.
    pub buffer: String,
    /// Dirty flag.
    pub dirty: bool,
    /// Validation error (None = ok).
    pub validation_error: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CellEditorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Already editing.
    #[error("already editing {0:?}")]
    AlreadyEditing(Coord),
}

impl CellEditor {
    /// New idle.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            active: None,
            original: String::new(),
            buffer: String::new(),
            dirty: false,
            validation_error: None,
        }
    }

    /// Begin editing at coord.
    pub fn begin(&mut self, coord: Coord, original: &str) -> Result<(), CellEditorError> {
        if let Some(c) = self.active {
            return Err(CellEditorError::AlreadyEditing(c));
        }
        self.active = Some(coord);
        self.original = original.into();
        self.buffer = original.into();
        self.dirty = false;
        self.validation_error = None;
        Ok(())
    }

    /// Replace buffer.
    pub fn set_buffer(&mut self, text: &str) {
        if self.active.is_some() {
            self.buffer = text.into();
            self.dirty = self.buffer != self.original;
        }
    }

    /// Append chars.
    pub fn type_text(&mut self, s: &str) {
        if self.active.is_some() {
            self.buffer.push_str(s);
            self.dirty = self.buffer != self.original;
        }
    }

    /// Set or clear a validation error.
    pub fn set_validation_error(&mut self, err: Option<String>) {
        self.validation_error = err;
    }

    /// Commit.
    pub fn commit(&mut self) -> TransactionOutcome {
        if self.active.is_none() {
            return TransactionOutcome::NoOp;
        }
        if let Some(e) = &self.validation_error {
            return TransactionOutcome::Blocked { error: e.clone() };
        }
        let new = std::mem::take(&mut self.buffer);
        self.original.clear();
        self.active = None;
        self.dirty = false;
        self.validation_error = None;
        TransactionOutcome::Committed { new }
    }

    /// Cancel.
    pub fn cancel(&mut self) -> TransactionOutcome {
        if self.active.is_none() {
            return TransactionOutcome::NoOp;
        }
        let original = std::mem::take(&mut self.original);
        self.buffer.clear();
        self.active = None;
        self.dirty = false;
        self.validation_error = None;
        TransactionOutcome::Reverted { original }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CellEditorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CellEditorError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for CellEditor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn xy(row: u32, col: u32) -> Coord {
        Coord { row, col }
    }

    #[test]
    fn idle_commit_is_noop() {
        let mut e = CellEditor::new();
        assert!(matches!(e.commit(), TransactionOutcome::NoOp));
    }

    #[test]
    fn begin_already_editing_rejected() {
        let mut e = CellEditor::new();
        e.begin(xy(0, 0), "x").unwrap();
        assert!(matches!(
            e.begin(xy(1, 1), "y").unwrap_err(),
            CellEditorError::AlreadyEditing(_)
        ));
    }

    #[test]
    fn type_marks_dirty() {
        let mut e = CellEditor::new();
        e.begin(xy(0, 0), "abc").unwrap();
        e.type_text("d");
        assert!(e.dirty);
    }

    #[test]
    fn type_back_to_original_clears_dirty() {
        let mut e = CellEditor::new();
        e.begin(xy(0, 0), "abc").unwrap();
        e.set_buffer("xyz");
        assert!(e.dirty);
        e.set_buffer("abc");
        assert!(!e.dirty);
    }

    #[test]
    fn commit_returns_new_and_resets() {
        let mut e = CellEditor::new();
        e.begin(xy(0, 0), "abc").unwrap();
        e.set_buffer("xyz");
        match e.commit() {
            TransactionOutcome::Committed { new } => assert_eq!(new, "xyz"),
            _ => panic!(),
        }
        assert!(e.active.is_none());
    }

    #[test]
    fn cancel_returns_original_and_resets() {
        let mut e = CellEditor::new();
        e.begin(xy(0, 0), "abc").unwrap();
        e.set_buffer("xyz");
        match e.cancel() {
            TransactionOutcome::Reverted { original } => assert_eq!(original, "abc"),
            _ => panic!(),
        }
        assert!(e.active.is_none());
    }

    #[test]
    fn validation_error_blocks_commit() {
        let mut e = CellEditor::new();
        e.begin(xy(0, 0), "abc").unwrap();
        e.set_validation_error(Some("bad format".into()));
        match e.commit() {
            TransactionOutcome::Blocked { error } => assert_eq!(error, "bad format"),
            _ => panic!(),
        }
        assert!(e.active.is_some());
    }

    #[test]
    fn clearing_validation_unblocks() {
        let mut e = CellEditor::new();
        e.begin(xy(0, 0), "abc").unwrap();
        e.set_validation_error(Some("bad".into()));
        e.set_validation_error(None);
        assert!(matches!(e.commit(), TransactionOutcome::Committed { .. }));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut e = CellEditor::new();
        e.schema_version = "9.9.9".into();
        assert!(matches!(
            e.validate().unwrap_err(),
            CellEditorError::SchemaMismatch
        ));
    }

    #[test]
    fn outcome_serde_kebab() {
        let o = TransactionOutcome::Reverted {
            original: "x".into(),
        };
        assert!(
            serde_json::to_string(&o)
                .unwrap()
                .contains("\"kind\":\"reverted\"")
        );
    }

    #[test]
    fn editor_serde_roundtrip() {
        let mut e = CellEditor::new();
        e.begin(xy(2, 3), "abc").unwrap();
        e.set_buffer("xyz");
        let j = serde_json::to_string(&e).unwrap();
        let back: CellEditor = serde_json::from_str(&j).unwrap();
        assert_eq!(e, back);
    }
}
