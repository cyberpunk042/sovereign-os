//! `sovereign-cockpit-stepper` — multi-step wizard state.
//!
//! Ordered steps with per-step status. Forward navigation requires
//! the active step's status to be Done (or Skipped). Backward
//! navigation is always permitted. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-step status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum StepStatus {
    /// Not started.
    NotStarted,
    /// Currently active.
    Active,
    /// Successfully completed.
    Done,
    /// Failed.
    Error,
    /// Skipped by operator.
    Skipped,
}

/// One step.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Step {
    /// Stable id.
    pub id: String,
    /// Display label.
    pub label: String,
    /// May this step be skipped?
    pub skippable: bool,
    /// Status.
    pub status: StepStatus,
}

/// Stepper state envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Stepper {
    /// Schema version.
    pub schema_version: String,
    /// Steps (≥ 1).
    pub steps: Vec<Step>,
    /// Active step index.
    pub active: usize,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StepperError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// No steps.
    #[error("stepper has no steps")]
    Empty,
    /// Empty id.
    #[error("step id empty")]
    EmptyId,
    /// Empty label.
    #[error("step {0} label empty")]
    EmptyLabel(String),
    /// Duplicate id.
    #[error("duplicate step id: {0}")]
    DuplicateId(String),
    /// Active index out of range.
    #[error("active {active} out of range (len {len})")]
    ActiveOutOfRange {
        /// active.
        active: usize,
        /// len.
        len: usize,
    },
    /// Tried to advance from an incomplete step.
    #[error("cannot advance: step {0} not Done or Skipped")]
    StepIncomplete(String),
    /// Already at last step.
    #[error("already at last step")]
    AtEnd,
    /// Already at first step.
    #[error("already at first step")]
    AtStart,
    /// Tried to skip a non-skippable step.
    #[error("step {0} is not skippable")]
    NotSkippable(String),
}

impl Stepper {
    /// New stepper. First step becomes Active.
    pub fn new(mut steps: Vec<Step>) -> Result<Self, StepperError> {
        if steps.is_empty() {
            return Err(StepperError::Empty);
        }
        check_steps(&steps)?;
        steps[0].status = StepStatus::Active;
        for s in steps.iter_mut().skip(1) {
            if s.status == StepStatus::Active {
                s.status = StepStatus::NotStarted;
            }
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            steps,
            active: 0,
        })
    }

    /// Mark the current step done.
    pub fn complete_current(&mut self) {
        self.steps[self.active].status = StepStatus::Done;
    }

    /// Mark the current step failed.
    pub fn fail_current(&mut self) {
        self.steps[self.active].status = StepStatus::Error;
    }

    /// Skip current step (must be skippable).
    pub fn skip_current(&mut self) -> Result<(), StepperError> {
        let s = &mut self.steps[self.active];
        if !s.skippable {
            return Err(StepperError::NotSkippable(s.id.clone()));
        }
        s.status = StepStatus::Skipped;
        Ok(())
    }

    /// Advance to next step. Requires current to be Done or Skipped.
    pub fn next(&mut self) -> Result<(), StepperError> {
        let cur = &self.steps[self.active];
        match cur.status {
            StepStatus::Done | StepStatus::Skipped => {}
            _ => return Err(StepperError::StepIncomplete(cur.id.clone())),
        }
        if self.active + 1 >= self.steps.len() {
            return Err(StepperError::AtEnd);
        }
        self.active += 1;
        self.steps[self.active].status = StepStatus::Active;
        Ok(())
    }

    /// Go back one step.
    pub fn back(&mut self) -> Result<(), StepperError> {
        if self.active == 0 {
            return Err(StepperError::AtStart);
        }
        // The current step's status reverts to NotStarted unless Done/Skipped/Error preserved.
        if self.steps[self.active].status == StepStatus::Active {
            self.steps[self.active].status = StepStatus::NotStarted;
        }
        self.active -= 1;
        self.steps[self.active].status = StepStatus::Active;
        Ok(())
    }

    /// Has every step finished (Done or Skipped)?
    pub fn is_complete(&self) -> bool {
        self.steps
            .iter()
            .all(|s| matches!(s.status, StepStatus::Done | StepStatus::Skipped))
    }

    /// Currently active step.
    pub fn active_step(&self) -> &Step {
        &self.steps[self.active]
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StepperError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(StepperError::SchemaMismatch);
        }
        if self.steps.is_empty() {
            return Err(StepperError::Empty);
        }
        check_steps(&self.steps)?;
        if self.active >= self.steps.len() {
            return Err(StepperError::ActiveOutOfRange {
                active: self.active,
                len: self.steps.len(),
            });
        }
        Ok(())
    }
}

fn check_steps(steps: &[Step]) -> Result<(), StepperError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for s in steps {
        if s.id.is_empty() {
            return Err(StepperError::EmptyId);
        }
        if s.label.is_empty() {
            return Err(StepperError::EmptyLabel(s.id.clone()));
        }
        if !seen.insert(s.id.as_str()) {
            return Err(StepperError::DuplicateId(s.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn step(id: &str, skippable: bool) -> Step {
        Step {
            id: id.into(),
            label: format!("L-{id}"),
            skippable,
            status: StepStatus::NotStarted,
        }
    }

    #[test]
    fn empty_rejected() {
        assert!(matches!(
            Stepper::new(vec![]).unwrap_err(),
            StepperError::Empty
        ));
    }

    #[test]
    fn first_step_active_on_new() {
        let s = Stepper::new(vec![step("a", false), step("b", false)]).unwrap();
        assert_eq!(s.active_step().id, "a");
        assert_eq!(s.steps[0].status, StepStatus::Active);
        assert_eq!(s.steps[1].status, StepStatus::NotStarted);
    }

    #[test]
    fn cannot_next_without_complete() {
        let mut s = Stepper::new(vec![step("a", false), step("b", false)]).unwrap();
        assert!(matches!(
            s.next().unwrap_err(),
            StepperError::StepIncomplete(_)
        ));
    }

    #[test]
    fn complete_then_next() {
        let mut s = Stepper::new(vec![step("a", false), step("b", false)]).unwrap();
        s.complete_current();
        s.next().unwrap();
        assert_eq!(s.active_step().id, "b");
        assert_eq!(s.steps[0].status, StepStatus::Done);
        assert_eq!(s.steps[1].status, StepStatus::Active);
    }

    #[test]
    fn skip_skippable_then_next() {
        let mut s = Stepper::new(vec![step("a", true), step("b", false)]).unwrap();
        s.skip_current().unwrap();
        s.next().unwrap();
        assert_eq!(s.active_step().id, "b");
    }

    #[test]
    fn skip_nonskippable_rejected() {
        let mut s = Stepper::new(vec![step("a", false), step("b", false)]).unwrap();
        assert!(matches!(
            s.skip_current().unwrap_err(),
            StepperError::NotSkippable(_)
        ));
    }

    #[test]
    fn back_at_start_rejected() {
        let mut s = Stepper::new(vec![step("a", false), step("b", false)]).unwrap();
        assert!(matches!(s.back().unwrap_err(), StepperError::AtStart));
    }

    #[test]
    fn next_at_end_rejected() {
        let mut s = Stepper::new(vec![step("a", false)]).unwrap();
        s.complete_current();
        assert!(matches!(s.next().unwrap_err(), StepperError::AtEnd));
    }

    #[test]
    fn back_resumes_previous() {
        let mut s = Stepper::new(vec![step("a", false), step("b", false)]).unwrap();
        s.complete_current();
        s.next().unwrap();
        s.back().unwrap();
        assert_eq!(s.active, 0);
        assert_eq!(s.steps[0].status, StepStatus::Active);
        assert_eq!(s.steps[1].status, StepStatus::NotStarted);
    }

    #[test]
    fn is_complete_true_when_all_done_or_skipped() {
        let mut s = Stepper::new(vec![step("a", true), step("b", false)]).unwrap();
        s.skip_current().unwrap();
        s.next().unwrap();
        s.complete_current();
        assert!(s.is_complete());
    }

    #[test]
    fn fail_current_records_error() {
        let mut s = Stepper::new(vec![step("a", false)]).unwrap();
        s.fail_current();
        assert_eq!(s.steps[0].status, StepStatus::Error);
        assert!(!s.is_complete());
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            Stepper::new(vec![step("a", false), step("a", false)]).unwrap_err(),
            StepperError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut x = step("a", false);
        x.id = String::new();
        assert!(matches!(
            Stepper::new(vec![x]).unwrap_err(),
            StepperError::EmptyId
        ));
    }

    #[test]
    fn empty_label_rejected() {
        let mut x = step("a", false);
        x.label = String::new();
        assert!(matches!(
            Stepper::new(vec![x]).unwrap_err(),
            StepperError::EmptyLabel(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = Stepper::new(vec![step("a", false)]).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            StepperError::SchemaMismatch
        ));
    }

    #[test]
    fn status_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&StepStatus::NotStarted).unwrap(),
            "\"not-started\""
        );
        assert_eq!(
            serde_json::to_string(&StepStatus::Skipped).unwrap(),
            "\"skipped\""
        );
    }

    #[test]
    fn stepper_serde_roundtrip() {
        let s = Stepper::new(vec![step("a", false), step("b", false)]).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: Stepper = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
