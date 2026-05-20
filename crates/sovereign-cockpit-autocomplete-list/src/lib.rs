//! `sovereign-cockpit-autocomplete-list` — list + highlight cursor.
//!
//! State holds `suggestions: Vec<Suggestion>` and `highlight: Option<usize>`.
//! `update(query, suggestions)` replaces the list and resets the highlight
//! to `Some(0)` if non-empty, else `None`. `arrow_down`/`arrow_up` wrap
//! the highlight. `accept()` returns the highlighted suggestion.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One suggestion.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Suggestion {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Optional secondary label.
    pub secondary: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AutocompleteList {
    /// Schema version.
    pub schema_version: String,
    /// Current query.
    pub query: String,
    /// Ranked suggestions.
    pub suggestions: Vec<Suggestion>,
    /// Currently highlighted index.
    pub highlight: Option<usize>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ListError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id in supplied suggestions.
    #[error("suggestion id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate suggestion id: {0}")]
    DuplicateId(String),
}

impl AutocompleteList {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            query: String::new(),
            suggestions: Vec::new(),
            highlight: None,
        }
    }

    /// Replace suggestions.
    pub fn update(&mut self, query: &str, suggestions: Vec<Suggestion>) -> Result<(), ListError> {
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for s in &suggestions {
            if s.id.is_empty() { return Err(ListError::EmptyId); }
            if !seen.insert(s.id.as_str()) {
                return Err(ListError::DuplicateId(s.id.clone()));
            }
        }
        self.query = query.into();
        let n = suggestions.len();
        self.suggestions = suggestions;
        self.highlight = if n == 0 { None } else { Some(0) };
        Ok(())
    }

    /// Move highlight down.
    pub fn arrow_down(&mut self) {
        let n = self.suggestions.len();
        if n == 0 { self.highlight = None; return; }
        self.highlight = Some(match self.highlight {
            None => 0,
            Some(i) => (i + 1) % n,
        });
    }

    /// Move highlight up.
    pub fn arrow_up(&mut self) {
        let n = self.suggestions.len();
        if n == 0 { self.highlight = None; return; }
        self.highlight = Some(match self.highlight {
            None => n - 1,
            Some(0) => n - 1,
            Some(i) => i - 1,
        });
    }

    /// Accept the highlighted entry.
    pub fn accept(&self) -> Option<&Suggestion> {
        self.highlight.and_then(|i| self.suggestions.get(i))
    }

    /// Clear.
    pub fn clear(&mut self) {
        self.query.clear();
        self.suggestions.clear();
        self.highlight = None;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ListError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ListError::SchemaMismatch); }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for s in &self.suggestions {
            if s.id.is_empty() { return Err(ListError::EmptyId); }
            if !seen.insert(s.id.as_str()) {
                return Err(ListError::DuplicateId(s.id.clone()));
            }
        }
        if let Some(i) = self.highlight {
            if i >= self.suggestions.len() {
                return Err(ListError::DuplicateId("highlight oob".into()));
            }
        }
        Ok(())
    }
}

impl Default for AutocompleteList {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(id: &str) -> Suggestion {
        Suggestion { id: id.into(), label: id.into(), secondary: String::new() }
    }

    #[test]
    fn update_resets_highlight_to_zero() {
        let mut l = AutocompleteList::new();
        l.update("q", vec![s("a"), s("b")]).unwrap();
        assert_eq!(l.highlight, Some(0));
    }

    #[test]
    fn empty_update_clears_highlight() {
        let mut l = AutocompleteList::new();
        l.update("q", vec![]).unwrap();
        assert_eq!(l.highlight, None);
    }

    #[test]
    fn arrow_down_wraps() {
        let mut l = AutocompleteList::new();
        l.update("q", vec![s("a"), s("b")]).unwrap();
        l.arrow_down();
        assert_eq!(l.highlight, Some(1));
        l.arrow_down();
        assert_eq!(l.highlight, Some(0));
    }

    #[test]
    fn arrow_up_wraps() {
        let mut l = AutocompleteList::new();
        l.update("q", vec![s("a"), s("b")]).unwrap();
        l.arrow_up();
        assert_eq!(l.highlight, Some(1));
    }

    #[test]
    fn accept_returns_highlighted() {
        let mut l = AutocompleteList::new();
        l.update("q", vec![s("a"), s("b")]).unwrap();
        l.arrow_down();
        assert_eq!(l.accept().unwrap().id, "b");
    }

    #[test]
    fn empty_id_rejected() {
        let mut l = AutocompleteList::new();
        assert!(matches!(l.update("q", vec![s("")]).unwrap_err(), ListError::EmptyId));
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut l = AutocompleteList::new();
        assert!(matches!(l.update("q", vec![s("a"), s("a")]).unwrap_err(), ListError::DuplicateId(_)));
    }

    #[test]
    fn clear_resets_all() {
        let mut l = AutocompleteList::new();
        l.update("q", vec![s("a")]).unwrap();
        l.clear();
        assert!(l.suggestions.is_empty());
        assert!(l.query.is_empty());
        assert!(l.highlight.is_none());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = AutocompleteList::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), ListError::SchemaMismatch));
    }

    #[test]
    fn list_serde_roundtrip() {
        let mut l = AutocompleteList::new();
        l.update("q", vec![s("a"), s("b")]).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: AutocompleteList = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
