//! `sovereign-cockpit-quick-notes` — quick notes list.
//!
//! Note{id, text, pinned, done, ts_ms}. add appends; capacity
//! drops oldest non-pinned (then oldest if all pinned). pin/
//! unpin toggle. mark_done sets done=true. visible() returns
//! pinned-first then by insertion order; optional include_done
//! flag.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Note.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Note {
    /// Id.
    pub id: String,
    /// Text.
    pub text: String,
    /// Pinned.
    pub pinned: bool,
    /// Done.
    pub done: bool,
    /// Created ts ms.
    pub ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct QuickNotes {
    /// Schema version.
    pub schema_version: String,
    /// Capacity.
    pub capacity: u32,
    /// Notes.
    pub notes: Vec<Note>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum NoteError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("text empty")]
    EmptyText,
    /// Zero capacity.
    #[error("capacity must be >= 1")]
    ZeroCapacity,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown id: {0}")]
    UnknownId(String),
}

impl QuickNotes {
    /// New.
    pub fn new(capacity: u32) -> Result<Self, NoteError> {
        if capacity == 0 { return Err(NoteError::ZeroCapacity); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            notes: Vec::new(),
        })
    }

    /// Add.
    pub fn add(&mut self, id: &str, text: &str, ts_ms: u64) -> Result<(), NoteError> {
        if id.is_empty() { return Err(NoteError::EmptyId); }
        if text.is_empty() { return Err(NoteError::EmptyText); }
        if self.notes.iter().any(|n| n.id == id) {
            return Err(NoteError::DuplicateId(id.into()));
        }
        if (self.notes.len() as u32) >= self.capacity {
            // Drop oldest non-pinned, or oldest if all pinned.
            let drop_idx = self.notes.iter().position(|n| !n.pinned)
                .unwrap_or(0);
            self.notes.remove(drop_idx);
        }
        self.notes.push(Note {
            id: id.into(),
            text: text.into(),
            pinned: false,
            done: false,
            ts_ms,
        });
        Ok(())
    }

    /// Pin/unpin.
    pub fn pin(&mut self, id: &str, pinned: bool) -> Result<(), NoteError> {
        let n = self.notes.iter_mut().find(|n| n.id == id)
            .ok_or_else(|| NoteError::UnknownId(id.into()))?;
        n.pinned = pinned;
        Ok(())
    }

    /// Mark done.
    pub fn mark_done(&mut self, id: &str, done: bool) -> Result<(), NoteError> {
        let n = self.notes.iter_mut().find(|n| n.id == id)
            .ok_or_else(|| NoteError::UnknownId(id.into()))?;
        n.done = done;
        Ok(())
    }

    /// Visible: pinned first (insertion order within), then unpinned.
    pub fn visible(&self, include_done: bool) -> Vec<&Note> {
        let filter = |n: &&Note| include_done || !n.done;
        let pinned: Vec<&Note> = self.notes.iter().filter(|n| n.pinned).filter(filter).collect();
        let unpinned: Vec<&Note> = self.notes.iter().filter(|n| !n.pinned).filter(filter).collect();
        let mut out = pinned;
        out.extend(unpinned);
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), NoteError> {
        if self.schema_version != SCHEMA_VERSION { return Err(NoteError::SchemaMismatch); }
        if self.capacity == 0 { return Err(NoteError::ZeroCapacity); }
        for n in &self.notes {
            if n.id.is_empty() { return Err(NoteError::EmptyId); }
            if n.text.is_empty() { return Err(NoteError::EmptyText); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_visible_order() {
        let mut q = QuickNotes::new(5).unwrap();
        q.add("a", "first", 0).unwrap();
        q.add("b", "second", 1).unwrap();
        q.pin("b", true).unwrap();
        let v: Vec<&str> = q.visible(false).iter().map(|n| n.id.as_str()).collect();
        assert_eq!(v, vec!["b", "a"]); // pinned first
    }

    #[test]
    fn mark_done_filters() {
        let mut q = QuickNotes::new(5).unwrap();
        q.add("a", "x", 0).unwrap();
        q.mark_done("a", true).unwrap();
        assert!(q.visible(false).is_empty());
        assert_eq!(q.visible(true).len(), 1);
    }

    #[test]
    fn capacity_drops_oldest_non_pinned() {
        let mut q = QuickNotes::new(2).unwrap();
        q.add("a", "x", 0).unwrap();
        q.add("b", "y", 1).unwrap();
        q.pin("a", true).unwrap();
        q.add("c", "z", 2).unwrap();
        // "b" (non-pinned, older) dropped; "a" + "c" remain.
        let ids: Vec<&str> = q.notes.iter().map(|n| n.id.as_str()).collect();
        assert_eq!(ids, vec!["a", "c"]);
    }

    #[test]
    fn capacity_drops_oldest_if_all_pinned() {
        let mut q = QuickNotes::new(2).unwrap();
        q.add("a", "x", 0).unwrap();
        q.add("b", "y", 1).unwrap();
        q.pin("a", true).unwrap();
        q.pin("b", true).unwrap();
        q.add("c", "z", 2).unwrap();
        let ids: Vec<&str> = q.notes.iter().map(|n| n.id.as_str()).collect();
        // "a" was first → dropped.
        assert_eq!(ids, vec!["b", "c"]);
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut q = QuickNotes::new(5).unwrap();
        q.add("a", "x", 0).unwrap();
        assert!(matches!(q.add("a", "y", 1).unwrap_err(), NoteError::DuplicateId(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut q = QuickNotes::new(5).unwrap();
        assert!(matches!(q.add("", "x", 0).unwrap_err(), NoteError::EmptyId));
        assert!(matches!(q.add("i", "", 0).unwrap_err(), NoteError::EmptyText));
        assert!(matches!(QuickNotes::new(0).unwrap_err(), NoteError::ZeroCapacity));
    }

    #[test]
    fn unknown_pin_rejected() {
        let mut q = QuickNotes::new(5).unwrap();
        assert!(matches!(q.pin("nope", true).unwrap_err(), NoteError::UnknownId(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut q = QuickNotes::new(5).unwrap();
        q.schema_version = "9.9.9".into();
        assert!(matches!(q.validate().unwrap_err(), NoteError::SchemaMismatch));
    }

    #[test]
    fn notes_serde_roundtrip() {
        let mut q = QuickNotes::new(5).unwrap();
        q.add("a", "x", 0).unwrap();
        let j = serde_json::to_string(&q).unwrap();
        let back: QuickNotes = serde_json::from_str(&j).unwrap();
        assert_eq!(q, back);
    }
}
