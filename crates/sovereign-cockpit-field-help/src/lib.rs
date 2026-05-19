//! `sovereign-cockpit-field-help` — per-field help/error display.
//!
//! Per-field state: help_text + optional error_text + dismissed.
//! resolve(id) returns Render::None / Help / Error. Error wins;
//! dismissed hides both Help and Error until cleared.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One field.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Field {
    /// Stable id.
    pub id: String,
    /// Help text (≤ 200 chars).
    pub help_text: String,
    /// Error text (None = no error).
    pub error_text: Option<String>,
    /// Operator dismissed the help/error?
    pub dismissed: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FieldHelp {
    /// Schema version.
    pub schema_version: String,
    /// Fields.
    pub fields: Vec<Field>,
}

/// Render output.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Render {
    /// Nothing to show.
    None,
    /// Help text.
    Help {
        /// text.
        text: String,
    },
    /// Error text (overrides help).
    Error {
        /// text.
        text: String,
    },
}

/// Errors.
#[derive(Debug, Error)]
pub enum FieldHelpError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("field id empty")]
    EmptyId,
    /// Help too long.
    #[error("field {0} help_text length {1} > 200")]
    HelpTooLong(String, usize),
    /// Error too long.
    #[error("field {0} error_text length {1} > 200")]
    ErrorTooLong(String, usize),
    /// Duplicate id.
    #[error("duplicate field id: {0}")]
    DuplicateId(String),
    /// Unknown id.
    #[error("unknown field id: {0}")]
    Unknown(String),
}

impl FieldHelp {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            fields: Vec::new(),
        }
    }

    /// Add a field.
    pub fn add(&mut self, f: Field) -> Result<(), FieldHelpError> {
        check_field(&f)?;
        if self.fields.iter().any(|x| x.id == f.id) {
            return Err(FieldHelpError::DuplicateId(f.id));
        }
        self.fields.push(f);
        Ok(())
    }

    /// Set error on a field.
    pub fn set_error(&mut self, id: &str, err: Option<String>) -> Result<(), FieldHelpError> {
        let f = self.fields.iter_mut().find(|f| f.id == id)
            .ok_or_else(|| FieldHelpError::Unknown(id.into()))?;
        if let Some(e) = &err {
            let n = e.chars().count();
            if n > 200 {
                return Err(FieldHelpError::ErrorTooLong(id.into(), n));
            }
        }
        f.error_text = err;
        // Surface error: undismiss.
        if f.error_text.is_some() {
            f.dismissed = false;
        }
        Ok(())
    }

    /// Mark a field dismissed.
    pub fn dismiss(&mut self, id: &str) -> Result<(), FieldHelpError> {
        let f = self.fields.iter_mut().find(|f| f.id == id)
            .ok_or_else(|| FieldHelpError::Unknown(id.into()))?;
        f.dismissed = true;
        Ok(())
    }

    /// Resolve render for a field.
    pub fn resolve(&self, id: &str) -> Render {
        let f = match self.fields.iter().find(|f| f.id == id) {
            Some(f) => f,
            None => return Render::None,
        };
        if let Some(err) = &f.error_text {
            return Render::Error { text: err.clone() };
        }
        if f.dismissed { return Render::None; }
        if f.help_text.is_empty() { return Render::None; }
        Render::Help { text: f.help_text.clone() }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FieldHelpError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FieldHelpError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for f in &self.fields {
            check_field(f)?;
            if !seen.insert(f.id.as_str()) {
                return Err(FieldHelpError::DuplicateId(f.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_field(f: &Field) -> Result<(), FieldHelpError> {
    if f.id.is_empty() { return Err(FieldHelpError::EmptyId); }
    let n = f.help_text.chars().count();
    if n > 200 { return Err(FieldHelpError::HelpTooLong(f.id.clone(), n)); }
    if let Some(e) = &f.error_text {
        let n = e.chars().count();
        if n > 200 { return Err(FieldHelpError::ErrorTooLong(f.id.clone(), n)); }
    }
    Ok(())
}

impl Default for FieldHelp {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn f(id: &str, help: &str) -> Field {
        Field { id: id.into(), help_text: help.into(), error_text: None, dismissed: false }
    }

    #[test]
    fn help_renders() {
        let mut h = FieldHelp::new();
        h.add(f("a", "type your name")).unwrap();
        assert!(matches!(h.resolve("a"), Render::Help { .. }));
    }

    #[test]
    fn error_overrides_help() {
        let mut h = FieldHelp::new();
        h.add(f("a", "type your name")).unwrap();
        h.set_error("a", Some("required".into())).unwrap();
        let r = h.resolve("a");
        match r {
            Render::Error { text } => assert_eq!(text, "required"),
            _ => panic!(),
        }
    }

    #[test]
    fn dismissed_hides_help() {
        let mut h = FieldHelp::new();
        h.add(f("a", "type your name")).unwrap();
        h.dismiss("a").unwrap();
        assert!(matches!(h.resolve("a"), Render::None));
    }

    #[test]
    fn dismiss_does_not_hide_error() {
        let mut h = FieldHelp::new();
        h.add(f("a", "help")).unwrap();
        h.dismiss("a").unwrap();
        h.set_error("a", Some("err".into())).unwrap();
        assert!(matches!(h.resolve("a"), Render::Error { .. }));
    }

    #[test]
    fn error_undismisses() {
        let mut h = FieldHelp::new();
        h.add(f("a", "help")).unwrap();
        h.dismiss("a").unwrap();
        h.set_error("a", Some("err".into())).unwrap();
        // Cleared error → dismissed is now false, help shows.
        h.set_error("a", None).unwrap();
        assert!(matches!(h.resolve("a"), Render::Help { .. }));
    }

    #[test]
    fn unknown_resolves_to_none() {
        let h = FieldHelp::new();
        assert!(matches!(h.resolve("ghost"), Render::None));
    }

    #[test]
    fn duplicate_rejected() {
        let mut h = FieldHelp::new();
        h.add(f("a", "x")).unwrap();
        assert!(matches!(h.add(f("a", "y")).unwrap_err(), FieldHelpError::DuplicateId(_)));
    }

    #[test]
    fn help_too_long_rejected() {
        let mut h = FieldHelp::new();
        let mut field = f("a", "");
        field.help_text = "x".repeat(201);
        assert!(matches!(h.add(field).unwrap_err(), FieldHelpError::HelpTooLong(_, 201)));
    }

    #[test]
    fn error_too_long_rejected() {
        let mut h = FieldHelp::new();
        h.add(f("a", "help")).unwrap();
        let e = "x".repeat(201);
        assert!(matches!(h.set_error("a", Some(e)).unwrap_err(), FieldHelpError::ErrorTooLong(_, 201)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = FieldHelp::new();
        h.schema_version = "9.9.9".into();
        assert!(matches!(h.validate().unwrap_err(), FieldHelpError::SchemaMismatch));
    }

    #[test]
    fn render_serde_kebab() {
        let r = Render::Help { text: "x".into() };
        assert!(serde_json::to_string(&r).unwrap().contains("\"kind\":\"help\""));
    }

    #[test]
    fn help_serde_roundtrip() {
        let mut h = FieldHelp::new();
        h.add(f("a", "help")).unwrap();
        let j = serde_json::to_string(&h).unwrap();
        let back: FieldHelp = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
