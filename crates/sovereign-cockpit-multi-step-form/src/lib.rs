//! `sovereign-cockpit-multi-step-form` — multi-step form navigator.
//!
//! Each step declares its required field ids. The operator
//! `complete_field(step, field)` as they fill the form;
//! `next_allowed_from(step)` returns true only when every required
//! field of that step has been completed. `percent_complete` sums
//! across all steps.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One step.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Step {
    /// Stable id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Required field ids.
    pub required_fields: BTreeSet<String>,
    /// Completed field ids.
    pub completed_fields: BTreeSet<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MultiStepForm {
    /// Schema version.
    pub schema_version: String,
    /// Steps in order.
    pub steps: Vec<Step>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FormError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty step id.
    #[error("step id empty")]
    EmptyStepId,
    /// Empty field id.
    #[error("field id empty")]
    EmptyFieldId,
    /// Unknown step.
    #[error("unknown step: {0}")]
    UnknownStep(String),
}

impl MultiStepForm {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            steps: Vec::new(),
        }
    }

    /// Push step.
    pub fn push(&mut self, step: Step) -> Result<(), FormError> {
        if step.id.is_empty() {
            return Err(FormError::EmptyStepId);
        }
        for f in &step.required_fields {
            if f.is_empty() {
                return Err(FormError::EmptyFieldId);
            }
        }
        self.steps.push(step);
        Ok(())
    }

    /// Mark a field completed.
    pub fn complete_field(&mut self, step_id: &str, field_id: &str) -> Result<(), FormError> {
        if field_id.is_empty() {
            return Err(FormError::EmptyFieldId);
        }
        let s = self
            .steps
            .iter_mut()
            .find(|s| s.id == step_id)
            .ok_or_else(|| FormError::UnknownStep(step_id.into()))?;
        s.completed_fields.insert(field_id.into());
        Ok(())
    }

    /// Uncomplete (e.g. operator cleared the field).
    pub fn uncomplete_field(&mut self, step_id: &str, field_id: &str) -> Result<(), FormError> {
        let s = self
            .steps
            .iter_mut()
            .find(|s| s.id == step_id)
            .ok_or_else(|| FormError::UnknownStep(step_id.into()))?;
        s.completed_fields.remove(field_id);
        Ok(())
    }

    /// Is the step complete?
    pub fn step_complete(&self, step_id: &str) -> bool {
        if let Some(s) = self.steps.iter().find(|s| s.id == step_id) {
            return s.required_fields.is_subset(&s.completed_fields);
        }
        false
    }

    /// Next allowed?
    pub fn next_allowed_from(&self, step_id: &str) -> bool {
        self.step_complete(step_id)
    }

    /// Percent complete across all steps (by required-field count).
    pub fn percent_complete(&self) -> u8 {
        let mut total = 0usize;
        let mut done = 0usize;
        for s in &self.steps {
            total += s.required_fields.len();
            done += s.required_fields.intersection(&s.completed_fields).count();
        }
        if total == 0 {
            0
        } else {
            ((done * 100) / total) as u8
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FormError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FormError::SchemaMismatch);
        }
        for s in &self.steps {
            if s.id.is_empty() {
                return Err(FormError::EmptyStepId);
            }
            for f in s.required_fields.iter().chain(s.completed_fields.iter()) {
                if f.is_empty() {
                    return Err(FormError::EmptyFieldId);
                }
            }
        }
        Ok(())
    }
}

impl Default for MultiStepForm {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn step(id: &str, required: &[&str]) -> Step {
        Step {
            id: id.into(),
            label: format!("Step {id}"),
            required_fields: required.iter().map(|s| (*s).into()).collect(),
            completed_fields: BTreeSet::new(),
        }
    }

    #[test]
    fn step_complete_when_all_required_done() {
        let mut f = MultiStepForm::new();
        f.push(step("s1", &["name", "email"])).unwrap();
        assert!(!f.step_complete("s1"));
        f.complete_field("s1", "name").unwrap();
        assert!(!f.step_complete("s1"));
        f.complete_field("s1", "email").unwrap();
        assert!(f.step_complete("s1"));
    }

    #[test]
    fn next_allowed_from_complete_step() {
        let mut f = MultiStepForm::new();
        f.push(step("s1", &["x"])).unwrap();
        assert!(!f.next_allowed_from("s1"));
        f.complete_field("s1", "x").unwrap();
        assert!(f.next_allowed_from("s1"));
    }

    #[test]
    fn percent_complete_aggregates() {
        let mut f = MultiStepForm::new();
        f.push(step("s1", &["a", "b"])).unwrap();
        f.push(step("s2", &["c", "d"])).unwrap();
        f.complete_field("s1", "a").unwrap();
        assert_eq!(f.percent_complete(), 25);
        f.complete_field("s1", "b").unwrap();
        f.complete_field("s2", "c").unwrap();
        assert_eq!(f.percent_complete(), 75);
    }

    #[test]
    fn percent_empty_form_zero() {
        let f = MultiStepForm::new();
        assert_eq!(f.percent_complete(), 0);
    }

    #[test]
    fn uncomplete_removes() {
        let mut f = MultiStepForm::new();
        f.push(step("s1", &["x"])).unwrap();
        f.complete_field("s1", "x").unwrap();
        f.uncomplete_field("s1", "x").unwrap();
        assert!(!f.step_complete("s1"));
    }

    #[test]
    fn unknown_step_rejected() {
        let mut f = MultiStepForm::new();
        assert!(matches!(
            f.complete_field("nope", "x").unwrap_err(),
            FormError::UnknownStep(_)
        ));
    }

    #[test]
    fn empty_fields_rejected() {
        let mut f = MultiStepForm::new();
        f.push(step("s1", &["x"])).unwrap();
        assert!(matches!(
            f.complete_field("s1", "").unwrap_err(),
            FormError::EmptyFieldId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = MultiStepForm::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FormError::SchemaMismatch
        ));
    }

    #[test]
    fn form_serde_roundtrip() {
        let mut f = MultiStepForm::new();
        f.push(step("s1", &["x"])).unwrap();
        f.complete_field("s1", "x").unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: MultiStepForm = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
