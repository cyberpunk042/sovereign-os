//! `sovereign-cockpit-wizard-flow` — wizard flow control.
//!
//! Steps form a directed graph: each step lists allowed `next`
//! step ids. The wizard has a current step + a `valid` flag per
//! step. `advance(target)` succeeds only if target is in current's
//! next list AND current.valid; otherwise rejects.
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
    /// Id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Allowed next step ids.
    pub next: BTreeSet<String>,
    /// Valid (caller-asserted).
    pub valid: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WizardFlow {
    /// Schema version.
    pub schema_version: String,
    /// id → step.
    pub steps: BTreeMap<String, Step>,
    /// Current step id.
    pub current: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum WizardError {
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
    #[error("duplicate step: {0}")]
    DuplicateStep(String),
    /// Unknown.
    #[error("unknown step: {0}")]
    UnknownStep(String),
    /// No current.
    #[error("no current step set")]
    NoCurrent,
    /// Not in next set.
    #[error("step {target} not in {current}.next")]
    NotReachable {
        /// current.
        current: String,
        /// target.
        target: String,
    },
    /// Current invalid.
    #[error("current step {0} not valid")]
    Invalid(String),
}

impl WizardFlow {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            steps: BTreeMap::new(),
            current: None,
        }
    }

    /// Add step.
    pub fn add_step(&mut self, id: &str, label: &str, next: &[&str]) -> Result<(), WizardError> {
        if id.is_empty() {
            return Err(WizardError::EmptyId);
        }
        if label.is_empty() {
            return Err(WizardError::EmptyLabel);
        }
        if self.steps.contains_key(id) {
            return Err(WizardError::DuplicateStep(id.into()));
        }
        let mut next_set = BTreeSet::new();
        for n in next {
            if n.is_empty() {
                return Err(WizardError::EmptyId);
            }
            next_set.insert((*n).into());
        }
        self.steps.insert(
            id.into(),
            Step {
                id: id.into(),
                label: label.into(),
                next: next_set,
                valid: false,
            },
        );
        Ok(())
    }

    /// Start.
    pub fn start(&mut self, id: &str) -> Result<(), WizardError> {
        if !self.steps.contains_key(id) {
            return Err(WizardError::UnknownStep(id.into()));
        }
        self.current = Some(id.into());
        Ok(())
    }

    /// Mark step valid/invalid.
    pub fn set_valid(&mut self, id: &str, valid: bool) -> Result<(), WizardError> {
        let s = self
            .steps
            .get_mut(id)
            .ok_or_else(|| WizardError::UnknownStep(id.into()))?;
        s.valid = valid;
        Ok(())
    }

    /// Advance.
    pub fn advance(&mut self, target: &str) -> Result<(), WizardError> {
        let current_id = self.current.clone().ok_or(WizardError::NoCurrent)?;
        let current = self
            .steps
            .get(&current_id)
            .ok_or_else(|| WizardError::UnknownStep(current_id.clone()))?;
        if !current.valid {
            return Err(WizardError::Invalid(current_id));
        }
        if !current.next.contains(target) {
            return Err(WizardError::NotReachable {
                current: current_id,
                target: target.into(),
            });
        }
        if !self.steps.contains_key(target) {
            return Err(WizardError::UnknownStep(target.into()));
        }
        self.current = Some(target.into());
        Ok(())
    }

    /// At an end (current has no next)?
    pub fn is_terminal(&self) -> bool {
        if let Some(id) = &self.current {
            if let Some(s) = self.steps.get(id) {
                return s.next.is_empty();
            }
        }
        false
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), WizardError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(WizardError::SchemaMismatch);
        }
        for (id, s) in &self.steps {
            if id.is_empty() {
                return Err(WizardError::EmptyId);
            }
            if s.label.is_empty() {
                return Err(WizardError::EmptyLabel);
            }
            for n in &s.next {
                if !self.steps.contains_key(n) {
                    return Err(WizardError::UnknownStep(n.clone()));
                }
            }
        }
        Ok(())
    }
}

impl Default for WizardFlow {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn flow() -> WizardFlow {
        let mut w = WizardFlow::new();
        w.add_step("welcome", "Welcome", &["details"]).unwrap();
        w.add_step("details", "Details", &["confirm"]).unwrap();
        w.add_step("confirm", "Confirm", &[]).unwrap();
        w
    }

    #[test]
    fn happy_path_advance() {
        let mut w = flow();
        w.start("welcome").unwrap();
        w.set_valid("welcome", true).unwrap();
        w.advance("details").unwrap();
        assert_eq!(w.current.as_deref(), Some("details"));
    }

    #[test]
    fn cant_advance_when_invalid() {
        let mut w = flow();
        w.start("welcome").unwrap();
        assert!(matches!(
            w.advance("details").unwrap_err(),
            WizardError::Invalid(_)
        ));
    }

    #[test]
    fn cant_advance_to_non_neighbor() {
        let mut w = flow();
        w.start("welcome").unwrap();
        w.set_valid("welcome", true).unwrap();
        assert!(matches!(
            w.advance("confirm").unwrap_err(),
            WizardError::NotReachable { .. }
        ));
    }

    #[test]
    fn terminal_step_detected() {
        let mut w = flow();
        w.start("confirm").unwrap();
        assert!(w.is_terminal());
    }

    #[test]
    fn duplicate_rejected() {
        let mut w = WizardFlow::new();
        w.add_step("a", "A", &[]).unwrap();
        assert!(matches!(
            w.add_step("a", "A", &[]).unwrap_err(),
            WizardError::DuplicateStep(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut w = WizardFlow::new();
        assert!(matches!(
            w.add_step("", "x", &[]).unwrap_err(),
            WizardError::EmptyId
        ));
        assert!(matches!(
            w.add_step("a", "", &[]).unwrap_err(),
            WizardError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut w = flow();
        w.schema_version = "9.9.9".into();
        assert!(matches!(
            w.validate().unwrap_err(),
            WizardError::SchemaMismatch
        ));
    }

    #[test]
    fn wizard_serde_roundtrip() {
        let mut w = flow();
        w.start("welcome").unwrap();
        w.set_valid("welcome", true).unwrap();
        let j = serde_json::to_string(&w).unwrap();
        let back: WizardFlow = serde_json::from_str(&j).unwrap();
        assert_eq!(w, back);
    }
}
