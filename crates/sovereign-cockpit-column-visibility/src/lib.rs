//! `sovereign-cockpit-column-visibility` — per-column show/hide.
//!
//! Column{id, label, required, visible}. register adds; toggle/
//! show/hide flip visible. Required columns cannot be hidden
//! (rejected). visible_columns returns visible ids in
//! registration order.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Column.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Column {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Required (cannot hide).
    pub required: bool,
    /// Currently visible.
    pub visible: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColumnVisibility {
    /// Schema version.
    pub schema_version: String,
    /// Columns in registration order.
    pub columns: Vec<Column>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ColError {
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
    /// Required.
    #[error("required column cannot be hidden: {0}")]
    RequiredCannotHide(String),
}

impl ColumnVisibility {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            columns: Vec::new(),
        }
    }

    /// Register a column.
    pub fn register(&mut self, id: &str, label: &str, required: bool) -> Result<(), ColError> {
        if id.is_empty() {
            return Err(ColError::EmptyId);
        }
        if label.is_empty() {
            return Err(ColError::EmptyLabel);
        }
        if self.columns.iter().any(|c| c.id == id) {
            return Err(ColError::DuplicateId(id.into()));
        }
        self.columns.push(Column {
            id: id.into(),
            label: label.into(),
            required,
            visible: true,
        });
        Ok(())
    }

    /// Show.
    pub fn show(&mut self, id: &str) -> Result<(), ColError> {
        let c = self
            .columns
            .iter_mut()
            .find(|c| c.id == id)
            .ok_or_else(|| ColError::UnknownId(id.into()))?;
        c.visible = true;
        Ok(())
    }

    /// Hide (rejects required).
    pub fn hide(&mut self, id: &str) -> Result<(), ColError> {
        let c = self
            .columns
            .iter_mut()
            .find(|c| c.id == id)
            .ok_or_else(|| ColError::UnknownId(id.into()))?;
        if c.required {
            return Err(ColError::RequiredCannotHide(id.into()));
        }
        c.visible = false;
        Ok(())
    }

    /// Toggle (rejects hiding a required column).
    pub fn toggle(&mut self, id: &str) -> Result<bool, ColError> {
        let c = self
            .columns
            .iter_mut()
            .find(|c| c.id == id)
            .ok_or_else(|| ColError::UnknownId(id.into()))?;
        if c.visible {
            if c.required {
                return Err(ColError::RequiredCannotHide(id.into()));
            }
            c.visible = false;
        } else {
            c.visible = true;
        }
        Ok(c.visible)
    }

    /// Visible columns in registration order.
    pub fn visible_columns(&self) -> Vec<&str> {
        self.columns
            .iter()
            .filter(|c| c.visible)
            .map(|c| c.id.as_str())
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ColError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ColError::SchemaMismatch);
        }
        for c in &self.columns {
            if c.id.is_empty() {
                return Err(ColError::EmptyId);
            }
            if c.label.is_empty() {
                return Err(ColError::EmptyLabel);
            }
            if c.required && !c.visible {
                return Err(ColError::RequiredCannotHide(c.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for ColumnVisibility {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_visible_default() {
        let mut v = ColumnVisibility::new();
        v.register("a", "A", false).unwrap();
        assert_eq!(v.visible_columns(), vec!["a"]);
    }

    #[test]
    fn hide_and_show() {
        let mut v = ColumnVisibility::new();
        v.register("a", "A", false).unwrap();
        v.hide("a").unwrap();
        assert!(v.visible_columns().is_empty());
        v.show("a").unwrap();
        assert_eq!(v.visible_columns(), vec!["a"]);
    }

    #[test]
    fn required_cannot_hide() {
        let mut v = ColumnVisibility::new();
        v.register("a", "A", true).unwrap();
        assert!(matches!(
            v.hide("a").unwrap_err(),
            ColError::RequiredCannotHide(_)
        ));
    }

    #[test]
    fn toggle_required_visible_rejected() {
        let mut v = ColumnVisibility::new();
        v.register("a", "A", true).unwrap();
        // Toggle from visible → hidden rejected.
        assert!(matches!(
            v.toggle("a").unwrap_err(),
            ColError::RequiredCannotHide(_)
        ));
    }

    #[test]
    fn unknown_id_rejected() {
        let mut v = ColumnVisibility::new();
        assert!(matches!(
            v.hide("nope").unwrap_err(),
            ColError::UnknownId(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut v = ColumnVisibility::new();
        assert!(matches!(
            v.register("", "A", false).unwrap_err(),
            ColError::EmptyId
        ));
        assert!(matches!(
            v.register("a", "", false).unwrap_err(),
            ColError::EmptyLabel
        ));
    }

    #[test]
    fn duplicate_rejected() {
        let mut v = ColumnVisibility::new();
        v.register("a", "A", false).unwrap();
        assert!(matches!(
            v.register("a", "B", false).unwrap_err(),
            ColError::DuplicateId(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut v = ColumnVisibility::new();
        v.schema_version = "9.9.9".into();
        assert!(matches!(
            v.validate().unwrap_err(),
            ColError::SchemaMismatch
        ));
    }

    #[test]
    fn vis_serde_roundtrip() {
        let mut v = ColumnVisibility::new();
        v.register("a", "A", true).unwrap();
        let j = serde_json::to_string(&v).unwrap();
        let back: ColumnVisibility = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }
}
