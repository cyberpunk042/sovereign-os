//! `sovereign-cockpit-form-validity` — form aggregate validity.
//!
//! Per-field record: required + touched + value-empty + custom
//! error string. is_valid() rolls them up; visible_errors() returns
//! only errors for touched fields (so Required errors don't render
//! before interaction). Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One field's validity.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Field {
    /// Stable id.
    pub id: String,
    /// Display label (for error attribution).
    pub label: String,
    /// Required?
    pub required: bool,
    /// Has the operator interacted with this field yet?
    pub touched: bool,
    /// Is the current value empty?
    pub empty: bool,
    /// Custom validation error (None = ok). Set by upstream rules.
    pub custom_error: Option<String>,
}

/// Form envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FormValidity {
    /// Schema version.
    pub schema_version: String,
    /// Fields.
    pub fields: Vec<Field>,
}

/// Per-error report.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FormError {
    /// Field id.
    pub id: String,
    /// Field label.
    pub label: String,
    /// Error message.
    pub message: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FormError_ {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("field id empty")]
    EmptyId,
    /// Empty label.
    #[error("field {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate field id: {0}")]
    DuplicateId(String),
    /// Unknown id.
    #[error("unknown field id: {0}")]
    Unknown(String),
}

impl FormValidity {
    /// New empty.
    pub fn new(fields: Vec<Field>) -> Result<Self, FormError_> {
        check_fields(&fields)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            fields,
        })
    }

    /// Mark a field touched.
    pub fn touch(&mut self, id: &str) -> Result<(), FormError_> {
        let f = self.fields.iter_mut().find(|f| f.id == id)
            .ok_or_else(|| FormError_::Unknown(id.into()))?;
        f.touched = true;
        Ok(())
    }

    /// Update emptiness of a field (cheap call from the input event).
    pub fn set_empty(&mut self, id: &str, empty: bool) -> Result<(), FormError_> {
        let f = self.fields.iter_mut().find(|f| f.id == id)
            .ok_or_else(|| FormError_::Unknown(id.into()))?;
        f.empty = empty;
        Ok(())
    }

    /// Set a custom error for a field (None to clear).
    pub fn set_custom_error(&mut self, id: &str, err: Option<String>) -> Result<(), FormError_> {
        let f = self.fields.iter_mut().find(|f| f.id == id)
            .ok_or_else(|| FormError_::Unknown(id.into()))?;
        f.custom_error = err;
        Ok(())
    }

    /// Compute submit-valid: every required+empty rejected; every custom_error rejected.
    pub fn is_valid(&self) -> bool {
        for f in &self.fields {
            if f.required && f.empty { return false; }
            if f.custom_error.is_some() { return false; }
        }
        true
    }

    /// Visible errors (only for touched fields). Required-empty &
    /// custom_error both surface. Stable order = field order.
    pub fn visible_errors(&self) -> Vec<FormError> {
        let mut out: Vec<FormError> = Vec::new();
        for f in &self.fields {
            if !f.touched { continue; }
            if f.required && f.empty {
                out.push(FormError {
                    id: f.id.clone(),
                    label: f.label.clone(),
                    message: format!("{} is required", f.label),
                });
            }
            if let Some(e) = &f.custom_error {
                out.push(FormError {
                    id: f.id.clone(),
                    label: f.label.clone(),
                    message: e.clone(),
                });
            }
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FormError_> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FormError_::SchemaMismatch);
        }
        check_fields(&self.fields)
    }
}

fn check_fields(fields: &[Field]) -> Result<(), FormError_> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for f in fields {
        if f.id.is_empty() { return Err(FormError_::EmptyId); }
        if f.label.is_empty() { return Err(FormError_::EmptyLabel(f.id.clone())); }
        if !seen.insert(f.id.as_str()) {
            return Err(FormError_::DuplicateId(f.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn f(id: &str, required: bool, empty: bool) -> Field {
        Field {
            id: id.into(),
            label: format!("L-{id}"),
            required,
            touched: false,
            empty,
            custom_error: None,
        }
    }

    #[test]
    fn empty_form_valid() {
        let f = FormValidity::new(vec![]).unwrap();
        assert!(f.is_valid());
        assert!(f.visible_errors().is_empty());
    }

    #[test]
    fn required_empty_blocks_submit() {
        let f = FormValidity::new(vec![f("a", true, true)]).unwrap();
        assert!(!f.is_valid());
    }

    #[test]
    fn required_filled_passes() {
        let f = FormValidity::new(vec![f("a", true, false)]).unwrap();
        assert!(f.is_valid());
    }

    #[test]
    fn required_empty_untouched_no_visible_error() {
        let f = FormValidity::new(vec![f("a", true, true)]).unwrap();
        assert!(f.visible_errors().is_empty());
    }

    #[test]
    fn required_empty_touched_shows_error() {
        let mut f = FormValidity::new(vec![f("a", true, true)]).unwrap();
        f.touch("a").unwrap();
        let errs = f.visible_errors();
        assert_eq!(errs.len(), 1);
        assert!(errs[0].message.contains("required"));
    }

    #[test]
    fn custom_error_blocks_submit_regardless_of_touch() {
        let mut form = FormValidity::new(vec![f("a", false, false)]).unwrap();
        form.set_custom_error("a", Some("invalid format".into())).unwrap();
        assert!(!form.is_valid());
        // Touched -> visible.
        form.touch("a").unwrap();
        let errs = form.visible_errors();
        assert_eq!(errs.len(), 1);
        assert_eq!(errs[0].message, "invalid format");
    }

    #[test]
    fn set_empty_changes_validity() {
        let mut form = FormValidity::new(vec![f("a", true, true)]).unwrap();
        assert!(!form.is_valid());
        form.set_empty("a", false).unwrap();
        assert!(form.is_valid());
    }

    #[test]
    fn set_custom_error_none_clears() {
        let mut form = FormValidity::new(vec![f("a", false, false)]).unwrap();
        form.set_custom_error("a", Some("bad".into())).unwrap();
        assert!(!form.is_valid());
        form.set_custom_error("a", None).unwrap();
        assert!(form.is_valid());
    }

    #[test]
    fn unknown_field_rejected() {
        let mut form = FormValidity::new(vec![f("a", false, false)]).unwrap();
        assert!(matches!(form.touch("z").unwrap_err(), FormError_::Unknown(_)));
        assert!(matches!(form.set_empty("z", true).unwrap_err(), FormError_::Unknown(_)));
        assert!(matches!(form.set_custom_error("z", None).unwrap_err(), FormError_::Unknown(_)));
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            FormValidity::new(vec![f("a", false, false), f("a", false, false)]).unwrap_err(),
            FormError_::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = f("a", false, false);
        x.id = String::new();
        assert!(matches!(FormValidity::new(vec![x]).unwrap_err(), FormError_::EmptyId));
    }

    #[test]
    fn empty_label_rejected() {
        let mut x = f("a", false, false);
        x.label = String::new();
        assert!(matches!(FormValidity::new(vec![x]).unwrap_err(), FormError_::EmptyLabel(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut form = FormValidity::new(vec![f("a", false, false)]).unwrap();
        form.schema_version = "9.9.9".into();
        assert!(matches!(form.validate().unwrap_err(), FormError_::SchemaMismatch));
    }

    #[test]
    fn form_serde_roundtrip() {
        let mut form = FormValidity::new(vec![f("a", true, true), f("b", false, false)]).unwrap();
        form.touch("a").unwrap();
        let j = serde_json::to_string(&form).unwrap();
        let back: FormValidity = serde_json::from_str(&j).unwrap();
        assert_eq!(form, back);
    }
}
