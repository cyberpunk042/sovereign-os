//! `sovereign-cockpit-field-error` — per-field error/warning/hint registry.
//!
//! Each field carries a list of `Entry { severity, message }`. The
//! registry is unique per (field_id, message); duplicate inserts are
//! no-ops. `worst_for_field` returns the highest-severity entry for a
//! field (or None). `visible_for_field` filters entries at or above
//! a severity threshold.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Ord, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Hint.
    Hint,
    /// Info.
    Info,
    /// Warn.
    Warn,
    /// Error.
    Error,
}

/// One entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// severity.
    pub severity: Severity,
    /// message.
    pub message: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FieldError {
    /// Schema version.
    pub schema_version: String,
    /// field_id → entries.
    pub entries: BTreeMap<String, Vec<Entry>>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FieldErrorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty field id.
    #[error("field id empty")]
    EmptyId,
    /// Empty message.
    #[error("empty message")]
    EmptyMessage,
}

impl FieldError {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: BTreeMap::new(),
        }
    }

    /// Insert. Dedups on (field_id, message).
    pub fn insert(
        &mut self,
        field_id: &str,
        severity: Severity,
        message: &str,
    ) -> Result<bool, FieldErrorError> {
        if field_id.is_empty() {
            return Err(FieldErrorError::EmptyId);
        }
        if message.is_empty() {
            return Err(FieldErrorError::EmptyMessage);
        }
        let v = self.entries.entry(field_id.into()).or_default();
        if v.iter().any(|e| e.message == message) {
            return Ok(false);
        }
        v.push(Entry {
            severity,
            message: message.into(),
        });
        Ok(true)
    }

    /// Remove a specific message; returns true if removed.
    pub fn remove(&mut self, field_id: &str, message: &str) -> bool {
        if let Some(v) = self.entries.get_mut(field_id) {
            if let Some(pos) = v.iter().position(|e| e.message == message) {
                v.remove(pos);
                if v.is_empty() {
                    self.entries.remove(field_id);
                }
                return true;
            }
        }
        false
    }

    /// Clear all entries for a field.
    pub fn clear_field(&mut self, field_id: &str) -> usize {
        self.entries.remove(field_id).map(|v| v.len()).unwrap_or(0)
    }

    /// Worst entry for a field.
    pub fn worst_for_field(&self, field_id: &str) -> Option<&Entry> {
        self.entries
            .get(field_id)
            .and_then(|v| v.iter().max_by_key(|e| e.severity))
    }

    /// All entries for a field at or above a threshold.
    pub fn visible_for_field(&self, field_id: &str, min_sev: Severity) -> Vec<Entry> {
        self.entries
            .get(field_id)
            .map(|v| {
                v.iter()
                    .filter(|e| e.severity >= min_sev)
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FieldErrorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FieldErrorError::SchemaMismatch);
        }
        for (k, v) in &self.entries {
            if k.is_empty() {
                return Err(FieldErrorError::EmptyId);
            }
            for e in v {
                if e.message.is_empty() {
                    return Err(FieldErrorError::EmptyMessage);
                }
            }
        }
        Ok(())
    }
}

impl Default for FieldError {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ordering_error_worst() {
        assert!(Severity::Error > Severity::Warn);
        assert!(Severity::Warn > Severity::Info);
        assert!(Severity::Info > Severity::Hint);
    }

    #[test]
    fn insert_and_worst() {
        let mut f = FieldError::new();
        f.insert("email", Severity::Warn, "missing @").unwrap();
        f.insert("email", Severity::Error, "too long").unwrap();
        let w = f.worst_for_field("email").unwrap();
        assert_eq!(w.severity, Severity::Error);
    }

    #[test]
    fn insert_dedups_by_message() {
        let mut f = FieldError::new();
        assert!(f.insert("email", Severity::Warn, "missing @").unwrap());
        assert!(!f.insert("email", Severity::Error, "missing @").unwrap());
    }

    #[test]
    fn remove_clears_when_empty() {
        let mut f = FieldError::new();
        f.insert("email", Severity::Warn, "x").unwrap();
        assert!(f.remove("email", "x"));
        assert!(f.entries.get("email").is_none());
    }

    #[test]
    fn clear_field_count() {
        let mut f = FieldError::new();
        f.insert("email", Severity::Warn, "x").unwrap();
        f.insert("email", Severity::Info, "y").unwrap();
        assert_eq!(f.clear_field("email"), 2);
        assert_eq!(f.clear_field("email"), 0);
    }

    #[test]
    fn visible_at_threshold() {
        let mut f = FieldError::new();
        f.insert("email", Severity::Hint, "hint!").unwrap();
        f.insert("email", Severity::Error, "boom").unwrap();
        let warn_and_above = f.visible_for_field("email", Severity::Warn);
        assert_eq!(warn_and_above.len(), 1);
        assert_eq!(warn_and_above[0].severity, Severity::Error);
    }

    #[test]
    fn empty_id_rejected() {
        let mut f = FieldError::new();
        assert!(matches!(
            f.insert("", Severity::Warn, "x").unwrap_err(),
            FieldErrorError::EmptyId
        ));
    }

    #[test]
    fn empty_message_rejected() {
        let mut f = FieldError::new();
        assert!(matches!(
            f.insert("a", Severity::Warn, "").unwrap_err(),
            FieldErrorError::EmptyMessage
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = FieldError::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FieldErrorError::SchemaMismatch
        ));
    }

    #[test]
    fn errors_serde_roundtrip() {
        let mut f = FieldError::new();
        f.insert("email", Severity::Error, "boom").unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: FieldError = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
