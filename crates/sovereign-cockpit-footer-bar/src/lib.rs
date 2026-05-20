//! `sovereign-cockpit-footer-bar` — fixed action footer.
//!
//! primary_action (optional) — the visually-emphasized button.
//! secondary_actions — additional buttons. status_text shown
//! left/center. set_primary/clear_primary/add_secondary/
//! remove_secondary mutators. invokes counted per id.
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
pub struct FooterBar {
    /// Schema version.
    pub schema_version: String,
    /// Primary action.
    pub primary: Option<Action>,
    /// Secondary actions.
    pub secondary: Vec<Action>,
    /// Status text shown on the bar.
    pub status_text: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FooterError {
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

impl FooterBar {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            primary: None,
            secondary: Vec::new(),
            status_text: String::new(),
        }
    }

    /// Set primary action.
    pub fn set_primary(&mut self, id: &str, label: &str) -> Result<(), FooterError> {
        if id.is_empty() { return Err(FooterError::EmptyId); }
        if label.is_empty() { return Err(FooterError::EmptyLabel); }
        self.primary = Some(Action { id: id.into(), label: label.into(), invokes: 0 });
        Ok(())
    }

    /// Clear primary.
    pub fn clear_primary(&mut self) {
        self.primary = None;
    }

    /// Add secondary action.
    pub fn add_secondary(&mut self, id: &str, label: &str) -> Result<(), FooterError> {
        if id.is_empty() { return Err(FooterError::EmptyId); }
        if label.is_empty() { return Err(FooterError::EmptyLabel); }
        if self.secondary.iter().any(|a| a.id == id) {
            return Err(FooterError::DuplicateId(id.into()));
        }
        if self.primary.as_ref().map(|p| p.id == id).unwrap_or(false) {
            return Err(FooterError::DuplicateId(id.into()));
        }
        self.secondary.push(Action { id: id.into(), label: label.into(), invokes: 0 });
        Ok(())
    }

    /// Remove secondary.
    pub fn remove_secondary(&mut self, id: &str) -> bool {
        if let Some(pos) = self.secondary.iter().position(|a| a.id == id) {
            self.secondary.remove(pos);
            true
        } else {
            false
        }
    }

    /// Set status text (can be empty).
    pub fn set_status_text(&mut self, s: &str) {
        self.status_text = s.into();
    }

    /// Invoke an action by id.
    pub fn invoke(&mut self, id: &str) -> Result<(), FooterError> {
        if let Some(p) = self.primary.as_mut() {
            if p.id == id { p.invokes = p.invokes.saturating_add(1); return Ok(()); }
        }
        if let Some(a) = self.secondary.iter_mut().find(|a| a.id == id) {
            a.invokes = a.invokes.saturating_add(1);
            return Ok(());
        }
        Err(FooterError::UnknownId(id.into()))
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FooterError> {
        if self.schema_version != SCHEMA_VERSION { return Err(FooterError::SchemaMismatch); }
        for a in self.primary.iter().chain(self.secondary.iter()) {
            if a.id.is_empty() { return Err(FooterError::EmptyId); }
            if a.label.is_empty() { return Err(FooterError::EmptyLabel); }
        }
        Ok(())
    }
}

impl Default for FooterBar {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn set_primary_and_invoke() {
        let mut b = FooterBar::new();
        b.set_primary("save", "Save").unwrap();
        b.invoke("save").unwrap();
        assert_eq!(b.primary.unwrap().invokes, 1);
    }

    #[test]
    fn add_secondary_and_invoke() {
        let mut b = FooterBar::new();
        b.add_secondary("cancel", "Cancel").unwrap();
        b.invoke("cancel").unwrap();
        assert_eq!(b.secondary[0].invokes, 1);
    }

    #[test]
    fn duplicate_secondary_rejected() {
        let mut b = FooterBar::new();
        b.add_secondary("x", "X").unwrap();
        assert!(matches!(b.add_secondary("x", "Y").unwrap_err(), FooterError::DuplicateId(_)));
    }

    #[test]
    fn secondary_cannot_clash_with_primary() {
        let mut b = FooterBar::new();
        b.set_primary("save", "Save").unwrap();
        assert!(matches!(b.add_secondary("save", "Save2").unwrap_err(), FooterError::DuplicateId(_)));
    }

    #[test]
    fn remove_secondary() {
        let mut b = FooterBar::new();
        b.add_secondary("x", "X").unwrap();
        assert!(b.remove_secondary("x"));
        assert!(!b.remove_secondary("x"));
    }

    #[test]
    fn unknown_invoke_rejected() {
        let mut b = FooterBar::new();
        assert!(matches!(b.invoke("nope").unwrap_err(), FooterError::UnknownId(_)));
    }

    #[test]
    fn set_status_text() {
        let mut b = FooterBar::new();
        b.set_status_text("draft saved");
        assert_eq!(b.status_text, "draft saved");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = FooterBar::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(b.validate().unwrap_err(), FooterError::SchemaMismatch));
    }

    #[test]
    fn footer_serde_roundtrip() {
        let mut b = FooterBar::new();
        b.set_primary("save", "Save").unwrap();
        b.add_secondary("cancel", "Cancel").unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: FooterBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
