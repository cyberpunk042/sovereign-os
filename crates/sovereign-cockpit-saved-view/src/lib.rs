//! `sovereign-cockpit-saved-view` — operator-saved view registry.
//!
//! Operators capture a list-view's filters + sort + visible columns
//! into a named SavedView. The chrome reapplies all three on
//! activation. Each view is scoped to a `scope_id` so a "logs" saved
//! view is not listed in a "deployments" picker.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One saved view.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SavedView {
    /// Stable id.
    pub id: String,
    /// Scope id (e.g. "logs", "tasks").
    pub scope_id: String,
    /// Display title.
    pub title: String,
    /// Filters blob (caller-chosen schema, captured verbatim).
    pub filters: String,
    /// Sort blob.
    pub sort: String,
    /// Visible columns in order.
    pub columns: Vec<String>,
    /// Creation ts.
    pub created_at_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SavedViewRegistry {
    /// Schema version.
    pub schema_version: String,
    /// id → view.
    pub views: BTreeMap<String, SavedView>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ViewError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("view id empty")]
    EmptyId,
    /// Empty scope.
    #[error("scope id empty")]
    EmptyScope,
    /// Empty title.
    #[error("title empty")]
    EmptyTitle,
    /// Duplicate.
    #[error("duplicate view id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown view id: {0}")]
    UnknownId(String),
}

impl SavedViewRegistry {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            views: BTreeMap::new(),
        }
    }

    /// Create.
    pub fn create(&mut self, v: SavedView) -> Result<(), ViewError> {
        if v.id.is_empty() { return Err(ViewError::EmptyId); }
        if v.scope_id.is_empty() { return Err(ViewError::EmptyScope); }
        if v.title.is_empty() { return Err(ViewError::EmptyTitle); }
        if self.views.contains_key(&v.id) {
            return Err(ViewError::DuplicateId(v.id));
        }
        self.views.insert(v.id.clone(), v);
        Ok(())
    }

    /// Rename.
    pub fn rename(&mut self, id: &str, new_title: &str) -> Result<(), ViewError> {
        if new_title.is_empty() { return Err(ViewError::EmptyTitle); }
        let v = self.views.get_mut(id).ok_or_else(|| ViewError::UnknownId(id.into()))?;
        v.title = new_title.into();
        Ok(())
    }

    /// Delete.
    pub fn delete(&mut self, id: &str) -> Result<(), ViewError> {
        self.views.remove(id).ok_or_else(|| ViewError::UnknownId(id.into()))?;
        Ok(())
    }

    /// All views.
    pub fn list(&self) -> Vec<SavedView> {
        self.views.values().cloned().collect()
    }

    /// Views for a scope.
    pub fn by_scope(&self, scope_id: &str) -> Vec<SavedView> {
        self.views.values().filter(|v| v.scope_id == scope_id).cloned().collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ViewError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ViewError::SchemaMismatch); }
        for (id, v) in &self.views {
            if id.is_empty() { return Err(ViewError::EmptyId); }
            if v.scope_id.is_empty() { return Err(ViewError::EmptyScope); }
            if v.title.is_empty() { return Err(ViewError::EmptyTitle); }
        }
        Ok(())
    }
}

impl Default for SavedViewRegistry {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn v(id: &str, scope: &str, title: &str) -> SavedView {
        SavedView {
            id: id.into(),
            scope_id: scope.into(),
            title: title.into(),
            filters: "{}".into(),
            sort: "{}".into(),
            columns: vec!["ts".into(), "level".into()],
            created_at_ms: 0,
        }
    }

    #[test]
    fn create_and_list() {
        let mut r = SavedViewRegistry::new();
        r.create(v("v1", "logs", "Errors only")).unwrap();
        assert_eq!(r.list().len(), 1);
    }

    #[test]
    fn duplicate_rejected() {
        let mut r = SavedViewRegistry::new();
        r.create(v("v1", "logs", "X")).unwrap();
        assert!(matches!(r.create(v("v1", "logs", "Y")).unwrap_err(), ViewError::DuplicateId(_)));
    }

    #[test]
    fn by_scope_filters() {
        let mut r = SavedViewRegistry::new();
        r.create(v("v1", "logs", "X")).unwrap();
        r.create(v("v2", "tasks", "Y")).unwrap();
        assert_eq!(r.by_scope("logs").len(), 1);
        assert_eq!(r.by_scope("tasks").len(), 1);
        assert_eq!(r.by_scope("other").len(), 0);
    }

    #[test]
    fn rename_changes_title() {
        let mut r = SavedViewRegistry::new();
        r.create(v("v1", "logs", "Old")).unwrap();
        r.rename("v1", "New").unwrap();
        assert_eq!(r.list()[0].title, "New");
    }

    #[test]
    fn rename_empty_title_rejected() {
        let mut r = SavedViewRegistry::new();
        r.create(v("v1", "logs", "X")).unwrap();
        assert!(matches!(r.rename("v1", "").unwrap_err(), ViewError::EmptyTitle));
    }

    #[test]
    fn delete_removes() {
        let mut r = SavedViewRegistry::new();
        r.create(v("v1", "logs", "X")).unwrap();
        r.delete("v1").unwrap();
        assert!(r.list().is_empty());
    }

    #[test]
    fn delete_unknown_rejected() {
        let mut r = SavedViewRegistry::new();
        assert!(matches!(r.delete("nope").unwrap_err(), ViewError::UnknownId(_)));
    }

    #[test]
    fn empty_fields_rejected() {
        let mut r = SavedViewRegistry::new();
        assert!(matches!(r.create(v("", "logs", "X")).unwrap_err(), ViewError::EmptyId));
        assert!(matches!(r.create(v("v1", "", "X")).unwrap_err(), ViewError::EmptyScope));
        assert!(matches!(r.create(v("v1", "logs", "")).unwrap_err(), ViewError::EmptyTitle));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = SavedViewRegistry::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), ViewError::SchemaMismatch));
    }

    #[test]
    fn view_serde_roundtrip() {
        let mut r = SavedViewRegistry::new();
        r.create(v("v1", "logs", "X")).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: SavedViewRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
