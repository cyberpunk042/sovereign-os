//! `sovereign-cockpit-step-indicator` — visual step renderer.
//!
//! Pure projection: given ordered steps with status, emit per-step
//! Visual rendering tokens. Connector between step i and i+1 is
//! filled when step i is Done or Skipped.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Step status (mirror of cockpit-stepper).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum StepStatus {
    /// Not started.
    NotStarted,
    /// Active.
    Active,
    /// Done.
    Done,
    /// Error.
    Error,
    /// Skipped.
    Skipped,
}

/// One step.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Step {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// Status.
    pub status: StepStatus,
}

/// One rendered visual token.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StepVisual {
    /// 1-based number.
    pub number: u32,
    /// Label.
    pub label: String,
    /// Status.
    pub status: StepStatus,
    /// Connector from this step to the next is filled?
    pub connector_filled: bool,
    /// Is this the last step (no connector after)?
    pub is_last: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StepIndicator {
    /// Schema version.
    pub schema_version: String,
    /// Steps in order.
    pub steps: Vec<Step>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum IndicatorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty steps.
    #[error("steps empty")]
    EmptySteps,
    /// Empty id.
    #[error("step id empty")]
    EmptyId,
    /// Empty label.
    #[error("step {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate step id: {0}")]
    DuplicateId(String),
}

impl StepIndicator {
    /// New.
    pub fn new(steps: Vec<Step>) -> Result<Self, IndicatorError> {
        check_steps(&steps)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            steps,
        })
    }

    /// Render.
    pub fn render(&self) -> Vec<StepVisual> {
        let n = self.steps.len();
        self.steps
            .iter()
            .enumerate()
            .map(|(i, s)| StepVisual {
                number: (i + 1) as u32,
                label: s.label.clone(),
                status: s.status,
                connector_filled: matches!(s.status, StepStatus::Done | StepStatus::Skipped),
                is_last: i + 1 == n,
            })
            .collect()
    }

    /// Percent completion (Done + Skipped count / total).
    pub fn percent_complete(&self) -> u8 {
        let n = self.steps.len();
        if n == 0 {
            return 0;
        }
        let done = self
            .steps
            .iter()
            .filter(|s| matches!(s.status, StepStatus::Done | StepStatus::Skipped))
            .count();
        ((done * 100) / n) as u8
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), IndicatorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(IndicatorError::SchemaMismatch);
        }
        check_steps(&self.steps)
    }
}

fn check_steps(s: &[Step]) -> Result<(), IndicatorError> {
    if s.is_empty() {
        return Err(IndicatorError::EmptySteps);
    }
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for step in s {
        if step.id.is_empty() {
            return Err(IndicatorError::EmptyId);
        }
        if step.label.is_empty() {
            return Err(IndicatorError::EmptyLabel(step.id.clone()));
        }
        if !seen.insert(step.id.as_str()) {
            return Err(IndicatorError::DuplicateId(step.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn step(id: &str, status: StepStatus) -> Step {
        Step {
            id: id.into(),
            label: format!("L-{id}"),
            status,
        }
    }

    #[test]
    fn empty_steps_rejected() {
        assert!(matches!(
            StepIndicator::new(vec![]).unwrap_err(),
            IndicatorError::EmptySteps
        ));
    }

    #[test]
    fn render_numbers_1_based() {
        let i = StepIndicator::new(vec![
            step("a", StepStatus::Done),
            step("b", StepStatus::Active),
            step("c", StepStatus::NotStarted),
        ])
        .unwrap();
        let r = i.render();
        assert_eq!(r[0].number, 1);
        assert_eq!(r[2].number, 3);
    }

    #[test]
    fn connector_filled_when_done() {
        let i = StepIndicator::new(vec![
            step("a", StepStatus::Done),
            step("b", StepStatus::NotStarted),
        ])
        .unwrap();
        let r = i.render();
        assert!(r[0].connector_filled);
        // last step's connector_filled is meaningless but we still report.
        assert!(r[1].is_last);
    }

    #[test]
    fn connector_filled_when_skipped() {
        let i = StepIndicator::new(vec![
            step("a", StepStatus::Skipped),
            step("b", StepStatus::NotStarted),
        ])
        .unwrap();
        let r = i.render();
        assert!(r[0].connector_filled);
    }

    #[test]
    fn connector_empty_when_active() {
        let i = StepIndicator::new(vec![
            step("a", StepStatus::Active),
            step("b", StepStatus::NotStarted),
        ])
        .unwrap();
        let r = i.render();
        assert!(!r[0].connector_filled);
    }

    #[test]
    fn percent_complete() {
        let i = StepIndicator::new(vec![
            step("a", StepStatus::Done),
            step("b", StepStatus::Done),
            step("c", StepStatus::Active),
            step("d", StepStatus::NotStarted),
        ])
        .unwrap();
        assert_eq!(i.percent_complete(), 50);
    }

    #[test]
    fn percent_all_done() {
        let i = StepIndicator::new(vec![step("a", StepStatus::Done)]).unwrap();
        assert_eq!(i.percent_complete(), 100);
    }

    #[test]
    fn duplicate_rejected() {
        assert!(matches!(
            StepIndicator::new(vec![
                step("a", StepStatus::Done),
                step("a", StepStatus::Done)
            ])
            .unwrap_err(),
            IndicatorError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut s = step("a", StepStatus::Done);
        s.id = String::new();
        assert!(matches!(
            StepIndicator::new(vec![s]).unwrap_err(),
            IndicatorError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut i = StepIndicator::new(vec![step("a", StepStatus::Done)]).unwrap();
        i.schema_version = "9.9.9".into();
        assert!(matches!(
            i.validate().unwrap_err(),
            IndicatorError::SchemaMismatch
        ));
    }

    #[test]
    fn status_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&StepStatus::NotStarted).unwrap(),
            "\"not-started\""
        );
    }

    #[test]
    fn indicator_serde_roundtrip() {
        let i = StepIndicator::new(vec![
            step("a", StepStatus::Done),
            step("b", StepStatus::Active),
        ])
        .unwrap();
        let j = serde_json::to_string(&i).unwrap();
        let back: StepIndicator = serde_json::from_str(&j).unwrap();
        assert_eq!(i, back);
    }
}
