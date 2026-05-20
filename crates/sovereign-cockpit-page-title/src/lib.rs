//! `sovereign-cockpit-page-title` — stack-style title manager.
//!
//! `push("Logs")` then `push("Errors")` makes the title path
//! `["Logs", "Errors"]`. `current_title(" — ", Some("Sovereign"))`
//! renders `"Logs — Errors — Sovereign"`. `pop()` removes the top.
//! `clear()` resets.
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
pub struct PageTitle {
    /// Schema version.
    pub schema_version: String,
    /// Stack of labels, outermost first.
    pub stack: Vec<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TitleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
}

impl PageTitle {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            stack: Vec::new(),
        }
    }

    /// Push.
    pub fn push(&mut self, label: &str) -> Result<(), TitleError> {
        if label.is_empty() { return Err(TitleError::EmptyLabel); }
        self.stack.push(label.into());
        Ok(())
    }

    /// Pop. Returns the popped label.
    pub fn pop(&mut self) -> Option<String> {
        self.stack.pop()
    }

    /// Clear.
    pub fn clear(&mut self) {
        self.stack.clear();
    }

    /// Depth.
    pub fn depth(&self) -> usize { self.stack.len() }

    /// Render title.
    pub fn current_title(&self, separator: &str, app_suffix: Option<&str>) -> String {
        let mut parts: Vec<&str> = self.stack.iter().map(|s| s.as_str()).collect();
        if let Some(s) = app_suffix {
            parts.push(s);
        }
        parts.join(separator)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TitleError> {
        if self.schema_version != SCHEMA_VERSION { return Err(TitleError::SchemaMismatch); }
        for s in &self.stack {
            if s.is_empty() { return Err(TitleError::EmptyLabel); }
        }
        Ok(())
    }
}

impl Default for PageTitle {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_render_returns_suffix_only() {
        let t = PageTitle::new();
        assert_eq!(t.current_title(" — ", Some("Sovereign")), "Sovereign");
        assert_eq!(t.current_title(" — ", None), "");
    }

    #[test]
    fn push_and_render() {
        let mut t = PageTitle::new();
        t.push("Logs").unwrap();
        t.push("Errors").unwrap();
        assert_eq!(t.current_title(" — ", Some("Sovereign")), "Logs — Errors — Sovereign");
    }

    #[test]
    fn pop_removes_top() {
        let mut t = PageTitle::new();
        t.push("Logs").unwrap();
        t.push("Errors").unwrap();
        let popped = t.pop();
        assert_eq!(popped.as_deref(), Some("Errors"));
        assert_eq!(t.depth(), 1);
    }

    #[test]
    fn clear_resets() {
        let mut t = PageTitle::new();
        t.push("Logs").unwrap();
        t.push("Errors").unwrap();
        t.clear();
        assert_eq!(t.depth(), 0);
    }

    #[test]
    fn empty_label_rejected() {
        let mut t = PageTitle::new();
        assert!(matches!(t.push("").unwrap_err(), TitleError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = PageTitle::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), TitleError::SchemaMismatch));
    }

    #[test]
    fn title_serde_roundtrip() {
        let mut t = PageTitle::new();
        t.push("Logs").unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: PageTitle = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
