//! `sovereign-cockpit-validation-summary` — per-field roll-up.
//!
//! record(field, ErrorLevel, message) appends to that field's
//! error list. clear(field) drops one field; clear_all drops
//! all. status() returns Pass when no Error-level entries
//! exist; Failed otherwise. error_fields() lists distinct
//! field ids with at least one Error-level entry.
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
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum ErrorLevel {
    /// Info (notice only).
    Info,
    /// Warning (does not block).
    Warning,
    /// Error (blocks submit).
    Error,
}

/// Entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Level.
    pub level: ErrorLevel,
    /// Message.
    pub message: String,
}

/// Status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Pass.
    Pass,
    /// Failed.
    Failed,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ValidationSummary {
    /// Schema version.
    pub schema_version: String,
    /// field → entries.
    pub by_field: BTreeMap<String, Vec<Entry>>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ValidationError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("field empty")]
    EmptyField,
    /// Empty.
    #[error("message empty")]
    EmptyMessage,
}

impl ValidationSummary {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            by_field: BTreeMap::new(),
        }
    }

    /// Record an entry on a field.
    pub fn record(
        &mut self,
        field: &str,
        level: ErrorLevel,
        message: &str,
    ) -> Result<(), ValidationError> {
        if field.is_empty() {
            return Err(ValidationError::EmptyField);
        }
        if message.is_empty() {
            return Err(ValidationError::EmptyMessage);
        }
        self.by_field.entry(field.into()).or_default().push(Entry {
            level,
            message: message.into(),
        });
        Ok(())
    }

    /// Clear one field.
    pub fn clear(&mut self, field: &str) -> bool {
        self.by_field.remove(field).is_some()
    }

    /// Clear all.
    pub fn clear_all(&mut self) {
        self.by_field.clear();
    }

    /// Field ids with at least one Error-level entry.
    pub fn error_fields(&self) -> Vec<&str> {
        self.by_field
            .iter()
            .filter(|(_, es)| es.iter().any(|e| e.level == ErrorLevel::Error))
            .map(|(k, _)| k.as_str())
            .collect()
    }

    /// Overall status.
    pub fn status(&self) -> Status {
        if self.error_fields().is_empty() {
            Status::Pass
        } else {
            Status::Failed
        }
    }

    /// Entry count.
    pub fn entry_count(&self) -> usize {
        self.by_field.values().map(|v| v.len()).sum()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ValidationError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ValidationError::SchemaMismatch);
        }
        for (k, es) in &self.by_field {
            if k.is_empty() {
                return Err(ValidationError::EmptyField);
            }
            for e in es {
                if e.message.is_empty() {
                    return Err(ValidationError::EmptyMessage);
                }
            }
        }
        Ok(())
    }
}

impl Default for ValidationSummary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_is_pass() {
        let s = ValidationSummary::new();
        assert_eq!(s.status(), Status::Pass);
    }

    #[test]
    fn info_only_is_pass() {
        let mut s = ValidationSummary::new();
        s.record("email", ErrorLevel::Info, "consider verifying")
            .unwrap();
        s.record("email", ErrorLevel::Warning, "double-check")
            .unwrap();
        assert_eq!(s.status(), Status::Pass);
        assert_eq!(s.entry_count(), 2);
    }

    #[test]
    fn error_makes_failed() {
        let mut s = ValidationSummary::new();
        s.record("email", ErrorLevel::Error, "invalid format")
            .unwrap();
        assert_eq!(s.status(), Status::Failed);
        assert_eq!(s.error_fields(), vec!["email"]);
    }

    #[test]
    fn clear_field_removes_errors() {
        let mut s = ValidationSummary::new();
        s.record("email", ErrorLevel::Error, "invalid").unwrap();
        s.clear("email");
        assert_eq!(s.status(), Status::Pass);
    }

    #[test]
    fn clear_all_resets() {
        let mut s = ValidationSummary::new();
        s.record("a", ErrorLevel::Error, "x").unwrap();
        s.record("b", ErrorLevel::Warning, "y").unwrap();
        s.clear_all();
        assert_eq!(s.entry_count(), 0);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = ValidationSummary::new();
        assert!(matches!(
            s.record("", ErrorLevel::Error, "x").unwrap_err(),
            ValidationError::EmptyField
        ));
        assert!(matches!(
            s.record("f", ErrorLevel::Error, "").unwrap_err(),
            ValidationError::EmptyMessage
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ValidationSummary::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            ValidationError::SchemaMismatch
        ));
    }

    #[test]
    fn summary_serde_roundtrip() {
        let mut s = ValidationSummary::new();
        s.record("email", ErrorLevel::Error, "invalid").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ValidationSummary = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
