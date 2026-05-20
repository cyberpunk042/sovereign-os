//! `sovereign-cockpit-combobox-state` — combobox UI state.
//!
//! Holds the option list, search filter, open/closed state,
//! highlighted index, and the accepted value. Filtering is
//! case-insensitive substring on each option's label.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One option.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Option_ {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ComboboxState {
    /// Schema version.
    pub schema_version: String,
    /// Option list.
    pub options: Vec<Option_>,
    /// Current search filter.
    pub filter: String,
    /// Open?
    pub open: bool,
    /// Highlighted index into the *filtered* list (None = nothing highlighted).
    pub highlight: Option<usize>,
    /// Accepted value (id).
    pub value: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ComboboxError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Unknown.
    #[error("option not in list: {0}")]
    UnknownOption(String),
}

impl ComboboxState {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            options: Vec::new(),
            filter: String::new(),
            open: false,
            highlight: None,
            value: None,
        }
    }

    /// Set option list (clears highlight + filter).
    pub fn set_options(&mut self, options: Vec<Option_>) -> Result<(), ComboboxError> {
        for o in &options {
            if o.id.is_empty() { return Err(ComboboxError::EmptyId); }
            if o.label.is_empty() { return Err(ComboboxError::EmptyLabel); }
        }
        self.options = options;
        self.filter.clear();
        self.highlight = None;
        Ok(())
    }

    /// Update filter (highlight clamps to filtered range).
    pub fn set_filter(&mut self, filter: &str) {
        self.filter = filter.into();
        let count = self.filtered_count();
        match (self.highlight, count) {
            (Some(_), 0) => self.highlight = None,
            (Some(i), n) if i >= n => self.highlight = Some(n - 1),
            _ => {}
        }
    }

    /// Open dropdown.
    pub fn open(&mut self) {
        self.open = true;
        if self.highlight.is_none() && self.filtered_count() > 0 {
            self.highlight = Some(0);
        }
    }

    /// Close dropdown (does not clear filter or highlight).
    pub fn close(&mut self) {
        self.open = false;
    }

    /// Move highlight down.
    pub fn move_down(&mut self) {
        let n = self.filtered_count();
        if n == 0 { self.highlight = None; return; }
        let next = match self.highlight {
            None => 0,
            Some(i) => (i + 1) % n,
        };
        self.highlight = Some(next);
    }

    /// Move highlight up.
    pub fn move_up(&mut self) {
        let n = self.filtered_count();
        if n == 0 { self.highlight = None; return; }
        let next = match self.highlight {
            None => n - 1,
            Some(0) => n - 1,
            Some(i) => i - 1,
        };
        self.highlight = Some(next);
    }

    /// Accept the currently-highlighted option.
    pub fn accept_highlight(&mut self) -> Option<String> {
        let v = self.filtered_visible();
        let i = self.highlight?;
        let id = v.get(i)?.id.clone();
        self.value = Some(id.clone());
        self.open = false;
        Some(id)
    }

    /// Set value by id.
    pub fn set_value(&mut self, id: &str) -> Result<(), ComboboxError> {
        if !self.options.iter().any(|o| o.id == id) {
            return Err(ComboboxError::UnknownOption(id.into()));
        }
        self.value = Some(id.into());
        Ok(())
    }

    /// Clear value.
    pub fn clear_value(&mut self) {
        self.value = None;
    }

    /// Filtered visible list.
    pub fn filtered_visible(&self) -> Vec<Option_> {
        if self.filter.is_empty() {
            return self.options.clone();
        }
        let needle = self.filter.to_lowercase();
        self.options.iter()
            .filter(|o| o.label.to_lowercase().contains(&needle))
            .cloned()
            .collect()
    }

    /// Number of filtered options.
    pub fn filtered_count(&self) -> usize {
        if self.filter.is_empty() {
            return self.options.len();
        }
        let needle = self.filter.to_lowercase();
        self.options.iter().filter(|o| o.label.to_lowercase().contains(&needle)).count()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ComboboxError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ComboboxError::SchemaMismatch); }
        for o in &self.options {
            if o.id.is_empty() { return Err(ComboboxError::EmptyId); }
            if o.label.is_empty() { return Err(ComboboxError::EmptyLabel); }
        }
        if let Some(v) = &self.value {
            if !self.options.iter().any(|o| &o.id == v) {
                return Err(ComboboxError::UnknownOption(v.clone()));
            }
        }
        Ok(())
    }
}

impl Default for ComboboxState {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn opts() -> Vec<Option_> {
        vec![
            Option_ { id: "apple".into(), label: "Apple".into() },
            Option_ { id: "banana".into(), label: "Banana".into() },
            Option_ { id: "cherry".into(), label: "Cherry".into() },
        ]
    }

    #[test]
    fn open_highlights_first() {
        let mut c = ComboboxState::new();
        c.set_options(opts()).unwrap();
        c.open();
        assert_eq!(c.highlight, Some(0));
    }

    #[test]
    fn filter_narrows_list() {
        let mut c = ComboboxState::new();
        c.set_options(opts()).unwrap();
        c.set_filter("an");
        let v = c.filtered_visible();
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].id, "banana");
    }

    #[test]
    fn highlight_wraps() {
        let mut c = ComboboxState::new();
        c.set_options(opts()).unwrap();
        c.open();
        c.move_down();
        c.move_down();
        assert_eq!(c.highlight, Some(2));
        c.move_down();
        assert_eq!(c.highlight, Some(0));
        c.move_up();
        assert_eq!(c.highlight, Some(2));
    }

    #[test]
    fn accept_sets_value() {
        let mut c = ComboboxState::new();
        c.set_options(opts()).unwrap();
        c.open();
        c.move_down(); // highlight banana
        let id = c.accept_highlight().unwrap();
        assert_eq!(id, "banana");
        assert_eq!(c.value.as_deref(), Some("banana"));
        assert!(!c.open);
    }

    #[test]
    fn filter_clamps_highlight() {
        let mut c = ComboboxState::new();
        c.set_options(opts()).unwrap();
        c.open();
        c.highlight = Some(2);
        // Filter narrows to 1 item.
        c.set_filter("apple");
        // Should clamp to 0.
        assert_eq!(c.highlight, Some(0));
    }

    #[test]
    fn set_value_unknown_rejected() {
        let mut c = ComboboxState::new();
        c.set_options(opts()).unwrap();
        assert!(matches!(c.set_value("nope").unwrap_err(), ComboboxError::UnknownOption(_)));
    }

    #[test]
    fn empty_options_rejected() {
        let mut c = ComboboxState::new();
        assert!(matches!(c.set_options(vec![Option_ { id: "".into(), label: "x".into() }]).unwrap_err(), ComboboxError::EmptyId));
        assert!(matches!(c.set_options(vec![Option_ { id: "i".into(), label: "".into() }]).unwrap_err(), ComboboxError::EmptyLabel));
    }

    #[test]
    fn empty_filter_match_all() {
        let mut c = ComboboxState::new();
        c.set_options(opts()).unwrap();
        c.set_filter("");
        assert_eq!(c.filtered_count(), 3);
    }

    #[test]
    fn case_insensitive_filter() {
        let mut c = ComboboxState::new();
        c.set_options(opts()).unwrap();
        c.set_filter("APP");
        let v = c.filtered_visible();
        assert_eq!(v.len(), 1);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ComboboxState::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), ComboboxError::SchemaMismatch));
    }

    #[test]
    fn combobox_serde_roundtrip() {
        let mut c = ComboboxState::new();
        c.set_options(opts()).unwrap();
        c.set_value("banana").unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: ComboboxState = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
