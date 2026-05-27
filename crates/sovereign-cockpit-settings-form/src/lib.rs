//! `sovereign-cockpit-settings-form` — settings form state.
//!
//! Each field has `committed` (last applied) and optional
//! `pending` (in-flight edit). is_dirty = any field has pending !=
//! committed. apply() commits all pending; discard() drops pending.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One field.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Field {
    /// Committed value.
    pub committed: String,
    /// Pending edit (None = no change).
    pub pending: Option<String>,
}

impl Field {
    /// Effective value (pending if dirty else committed).
    pub fn effective(&self) -> &str {
        self.pending.as_deref().unwrap_or(self.committed.as_str())
    }

    /// Is this field dirty?
    pub fn is_dirty(&self) -> bool {
        match &self.pending {
            None => false,
            Some(p) => p != &self.committed,
        }
    }
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SettingsForm {
    /// Schema version.
    pub schema_version: String,
    /// id → field.
    pub fields: BTreeMap<String, Field>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SettingsError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("field id empty")]
    EmptyId,
    /// Unknown.
    #[error("unknown field: {0}")]
    UnknownField(String),
}

impl SettingsForm {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            fields: BTreeMap::new(),
        }
    }

    /// Register a field with its initial committed value.
    pub fn register(&mut self, id: &str, committed: &str) -> Result<(), SettingsError> {
        if id.is_empty() {
            return Err(SettingsError::EmptyId);
        }
        self.fields.insert(
            id.into(),
            Field {
                committed: committed.into(),
                pending: None,
            },
        );
        Ok(())
    }

    /// Edit pending value (clears pending if equal to committed).
    pub fn edit(&mut self, id: &str, value: &str) -> Result<(), SettingsError> {
        let f = self
            .fields
            .get_mut(id)
            .ok_or_else(|| SettingsError::UnknownField(id.into()))?;
        if value == f.committed {
            f.pending = None;
        } else {
            f.pending = Some(value.into());
        }
        Ok(())
    }

    /// Apply all pending values.
    pub fn apply(&mut self) -> u32 {
        let mut n = 0;
        for f in self.fields.values_mut() {
            if let Some(p) = f.pending.take() {
                if p != f.committed {
                    f.committed = p;
                    n += 1;
                }
            }
        }
        n
    }

    /// Discard all pending edits.
    pub fn discard(&mut self) -> u32 {
        let mut n = 0;
        for f in self.fields.values_mut() {
            if f.pending.take().is_some() {
                n += 1;
            }
        }
        n
    }

    /// Any field dirty.
    pub fn is_dirty(&self) -> bool {
        self.fields.values().any(|f| f.is_dirty())
    }

    /// Effective value (pending or committed).
    pub fn effective(&self, id: &str) -> Option<String> {
        self.fields.get(id).map(|f| f.effective().to_string())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SettingsError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SettingsError::SchemaMismatch);
        }
        for k in self.fields.keys() {
            if k.is_empty() {
                return Err(SettingsError::EmptyId);
            }
        }
        Ok(())
    }
}

impl Default for SettingsForm {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn edit_marks_dirty() {
        let mut s = SettingsForm::new();
        s.register("theme", "light").unwrap();
        assert!(!s.is_dirty());
        s.edit("theme", "dark").unwrap();
        assert!(s.is_dirty());
    }

    #[test]
    fn edit_back_to_committed_clears_dirty() {
        let mut s = SettingsForm::new();
        s.register("theme", "light").unwrap();
        s.edit("theme", "dark").unwrap();
        s.edit("theme", "light").unwrap();
        assert!(!s.is_dirty());
    }

    #[test]
    fn apply_commits() {
        let mut s = SettingsForm::new();
        s.register("theme", "light").unwrap();
        s.edit("theme", "dark").unwrap();
        let n = s.apply();
        assert_eq!(n, 1);
        assert_eq!(s.effective("theme").as_deref(), Some("dark"));
        assert!(!s.is_dirty());
    }

    #[test]
    fn discard_reverts() {
        let mut s = SettingsForm::new();
        s.register("theme", "light").unwrap();
        s.edit("theme", "dark").unwrap();
        let n = s.discard();
        assert_eq!(n, 1);
        assert_eq!(s.effective("theme").as_deref(), Some("light"));
    }

    #[test]
    fn effective_returns_pending() {
        let mut s = SettingsForm::new();
        s.register("theme", "light").unwrap();
        s.edit("theme", "dark").unwrap();
        assert_eq!(s.effective("theme").as_deref(), Some("dark"));
    }

    #[test]
    fn unknown_field_rejected() {
        let mut s = SettingsForm::new();
        assert!(matches!(
            s.edit("nope", "x").unwrap_err(),
            SettingsError::UnknownField(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = SettingsForm::new();
        assert!(matches!(
            s.register("", "x").unwrap_err(),
            SettingsError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SettingsForm::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SettingsError::SchemaMismatch
        ));
    }

    #[test]
    fn settings_serde_roundtrip() {
        let mut s = SettingsForm::new();
        s.register("theme", "light").unwrap();
        s.edit("theme", "dark").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: SettingsForm = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
