//! `sovereign-cockpit-reply-form` — inline reply form state.
//!
//! State{parent_id, draft, saved_at_ms, autosave_every_ms}.
//! type(s) sets draft. tick(now) autosaves if elapsed >=
//! autosave_every_ms. submit(now) validates non-empty + returns
//! the body and resets. cancel clears.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplyForm {
    /// Schema version.
    pub schema_version: String,
    /// Parent thread id this reply belongs to.
    pub parent_id: String,
    /// Current draft body.
    pub draft: String,
    /// Last autosave ts ms.
    pub saved_at_ms: u64,
    /// Autosave interval ms (>= 1).
    pub autosave_every_ms: u64,
    /// Snapshot of last persisted draft (for dirty detection).
    pub persisted_draft: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ReplyError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty parent.
    #[error("parent_id empty")]
    EmptyParent,
    /// Zero autosave.
    #[error("autosave_every_ms must be >= 1")]
    ZeroAutosave,
    /// Empty.
    #[error("draft empty")]
    EmptyDraft,
}

impl ReplyForm {
    /// New.
    pub fn new(parent_id: &str, autosave_every_ms: u64) -> Result<Self, ReplyError> {
        if parent_id.is_empty() { return Err(ReplyError::EmptyParent); }
        if autosave_every_ms == 0 { return Err(ReplyError::ZeroAutosave); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            parent_id: parent_id.into(),
            draft: String::new(),
            saved_at_ms: 0,
            autosave_every_ms,
            persisted_draft: String::new(),
        })
    }

    /// Type into draft.
    pub fn r#type(&mut self, body: &str) { self.draft = body.into(); }

    /// Has the draft diverged from the last persisted snapshot?
    pub fn dirty(&self) -> bool { self.draft != self.persisted_draft }

    /// Tick — autosaves if interval elapsed and dirty.
    pub fn tick(&mut self, now_ms: u64) -> bool {
        if !self.dirty() { return false; }
        let elapsed = now_ms.saturating_sub(self.saved_at_ms);
        if elapsed < self.autosave_every_ms { return false; }
        self.persisted_draft = self.draft.clone();
        self.saved_at_ms = now_ms;
        true
    }

    /// Submit — returns the body and resets the form.
    pub fn submit(&mut self) -> Result<String, ReplyError> {
        if self.draft.trim().is_empty() { return Err(ReplyError::EmptyDraft); }
        let body = std::mem::take(&mut self.draft);
        self.persisted_draft.clear();
        self.saved_at_ms = 0;
        Ok(body)
    }

    /// Cancel — clears.
    pub fn cancel(&mut self) {
        self.draft.clear();
        self.persisted_draft.clear();
        self.saved_at_ms = 0;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ReplyError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ReplyError::SchemaMismatch); }
        if self.parent_id.is_empty() { return Err(ReplyError::EmptyParent); }
        if self.autosave_every_ms == 0 { return Err(ReplyError::ZeroAutosave); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn type_marks_dirty() {
        let mut f = ReplyForm::new("p1", 1000).unwrap();
        assert!(!f.dirty());
        f.r#type("hello");
        assert!(f.dirty());
    }

    #[test]
    fn tick_no_autosave_within_window() {
        let mut f = ReplyForm::new("p1", 1000).unwrap();
        f.r#type("hello");
        assert!(!f.tick(500));
        assert!(f.dirty());
    }

    #[test]
    fn tick_autosaves_after_window() {
        let mut f = ReplyForm::new("p1", 1000).unwrap();
        f.r#type("hello");
        assert!(f.tick(1500));
        assert!(!f.dirty());
        assert_eq!(f.persisted_draft, "hello");
    }

    #[test]
    fn submit_returns_body_and_resets() {
        let mut f = ReplyForm::new("p1", 1000).unwrap();
        f.r#type("done");
        let body = f.submit().unwrap();
        assert_eq!(body, "done");
        assert!(f.draft.is_empty());
        assert!(!f.dirty());
    }

    #[test]
    fn submit_empty_rejected() {
        let mut f = ReplyForm::new("p1", 1000).unwrap();
        f.r#type("   ");
        assert!(matches!(f.submit().unwrap_err(), ReplyError::EmptyDraft));
    }

    #[test]
    fn cancel_clears() {
        let mut f = ReplyForm::new("p1", 1000).unwrap();
        f.r#type("typing");
        f.cancel();
        assert!(f.draft.is_empty());
    }

    #[test]
    fn empty_parent_rejected() {
        assert!(matches!(ReplyForm::new("", 1000).unwrap_err(), ReplyError::EmptyParent));
    }

    #[test]
    fn zero_autosave_rejected() {
        assert!(matches!(ReplyForm::new("p", 0).unwrap_err(), ReplyError::ZeroAutosave));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = ReplyForm::new("p", 1000).unwrap();
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), ReplyError::SchemaMismatch));
    }

    #[test]
    fn reply_serde_roundtrip() {
        let mut f = ReplyForm::new("p", 500).unwrap();
        f.r#type("hi");
        let j = serde_json::to_string(&f).unwrap();
        let back: ReplyForm = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
