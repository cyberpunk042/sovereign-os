//! `sovereign-cockpit-edit-mode` — per-document edit lifecycle.
//!
//! `Mode::Read` ←→ `Edit{dirty}` → `ReviewPending` →
//! (`Read` on approve, `Edit{dirty:false}` on reject).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Mode {
    /// Read-only.
    Read,
    /// Editing.
    Edit {
        /// dirty flag.
        dirty: bool,
    },
    /// Submitted for review.
    ReviewPending,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EditMode {
    /// Schema version.
    pub schema_version: String,
    /// doc_id → mode.
    pub modes: BTreeMap<String, Mode>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum EditError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty doc id.
    #[error("doc id empty")]
    EmptyId,
    /// Bad transition.
    #[error("bad transition from {0:?}")]
    BadTransition(Mode),
}

impl EditMode {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            modes: BTreeMap::new(),
        }
    }

    fn current(&self, doc_id: &str) -> Mode {
        self.modes.get(doc_id).copied().unwrap_or(Mode::Read)
    }

    /// Read → Edit{dirty:false}.
    pub fn request_edit(&mut self, doc_id: &str) -> Result<(), EditError> {
        if doc_id.is_empty() { return Err(EditError::EmptyId); }
        match self.current(doc_id) {
            Mode::Read => { self.modes.insert(doc_id.into(), Mode::Edit { dirty: false }); Ok(()) }
            other => Err(EditError::BadTransition(other)),
        }
    }

    /// Edit → Edit{dirty:true} (caller hit any key).
    pub fn dirty(&mut self, doc_id: &str) -> Result<(), EditError> {
        match self.current(doc_id) {
            Mode::Edit { .. } => { self.modes.insert(doc_id.into(), Mode::Edit { dirty: true }); Ok(()) }
            other => Err(EditError::BadTransition(other)),
        }
    }

    /// Save draft: Edit{dirty} → Edit{dirty:false} (no submission).
    pub fn save_draft(&mut self, doc_id: &str) -> Result<(), EditError> {
        match self.current(doc_id) {
            Mode::Edit { .. } => { self.modes.insert(doc_id.into(), Mode::Edit { dirty: false }); Ok(()) }
            other => Err(EditError::BadTransition(other)),
        }
    }

    /// Submit: Edit → ReviewPending.
    pub fn submit_for_review(&mut self, doc_id: &str) -> Result<(), EditError> {
        match self.current(doc_id) {
            Mode::Edit { .. } => { self.modes.insert(doc_id.into(), Mode::ReviewPending); Ok(()) }
            other => Err(EditError::BadTransition(other)),
        }
    }

    /// Approve: ReviewPending → Read.
    pub fn approve(&mut self, doc_id: &str) -> Result<(), EditError> {
        match self.current(doc_id) {
            Mode::ReviewPending => { self.modes.insert(doc_id.into(), Mode::Read); Ok(()) }
            other => Err(EditError::BadTransition(other)),
        }
    }

    /// Reject: ReviewPending → Edit{dirty:false}.
    pub fn reject(&mut self, doc_id: &str) -> Result<(), EditError> {
        match self.current(doc_id) {
            Mode::ReviewPending => { self.modes.insert(doc_id.into(), Mode::Edit { dirty: false }); Ok(()) }
            other => Err(EditError::BadTransition(other)),
        }
    }

    /// Mode for a doc.
    pub fn mode_of(&self, doc_id: &str) -> Mode { self.current(doc_id) }

    /// Dirty?
    pub fn is_dirty(&self, doc_id: &str) -> bool {
        matches!(self.current(doc_id), Mode::Edit { dirty: true })
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), EditError> {
        if self.schema_version != SCHEMA_VERSION { return Err(EditError::SchemaMismatch); }
        for k in self.modes.keys() {
            if k.is_empty() { return Err(EditError::EmptyId); }
        }
        Ok(())
    }
}

impl Default for EditMode {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_read() {
        let m = EditMode::new();
        assert_eq!(m.mode_of("d"), Mode::Read);
    }

    #[test]
    fn read_to_edit() {
        let mut m = EditMode::new();
        m.request_edit("d").unwrap();
        assert_eq!(m.mode_of("d"), Mode::Edit { dirty: false });
    }

    #[test]
    fn dirty_then_save() {
        let mut m = EditMode::new();
        m.request_edit("d").unwrap();
        m.dirty("d").unwrap();
        assert!(m.is_dirty("d"));
        m.save_draft("d").unwrap();
        assert!(!m.is_dirty("d"));
        assert_eq!(m.mode_of("d"), Mode::Edit { dirty: false });
    }

    #[test]
    fn submit_then_approve() {
        let mut m = EditMode::new();
        m.request_edit("d").unwrap();
        m.submit_for_review("d").unwrap();
        assert_eq!(m.mode_of("d"), Mode::ReviewPending);
        m.approve("d").unwrap();
        assert_eq!(m.mode_of("d"), Mode::Read);
    }

    #[test]
    fn submit_then_reject() {
        let mut m = EditMode::new();
        m.request_edit("d").unwrap();
        m.submit_for_review("d").unwrap();
        m.reject("d").unwrap();
        assert_eq!(m.mode_of("d"), Mode::Edit { dirty: false });
    }

    #[test]
    fn bad_transitions_rejected() {
        let mut m = EditMode::new();
        // approve from Read.
        assert!(matches!(m.approve("d").unwrap_err(), EditError::BadTransition(_)));
        // request_edit twice.
        m.request_edit("d").unwrap();
        assert!(matches!(m.request_edit("d").unwrap_err(), EditError::BadTransition(_)));
    }

    #[test]
    fn empty_id_rejected() {
        let mut m = EditMode::new();
        assert!(matches!(m.request_edit("").unwrap_err(), EditError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = EditMode::new();
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), EditError::SchemaMismatch));
    }

    #[test]
    fn edit_serde_roundtrip() {
        let mut m = EditMode::new();
        m.request_edit("d").unwrap();
        m.dirty("d").unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: EditMode = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
