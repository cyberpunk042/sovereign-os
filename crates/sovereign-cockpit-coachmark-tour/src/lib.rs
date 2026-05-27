//! `sovereign-cockpit-coachmark-tour` — guided UI tour.
//!
//! Step{anchor, title, body}. start() begins at step 0 if any;
//! next() advances; prev() goes back. dismiss() ends tour as
//! completed=false; finish() marks completed=true after last
//! step. current() returns active step or None when tour is
//! over.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Step.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Step {
    /// Anchor widget id.
    pub anchor: String,
    /// Title.
    pub title: String,
    /// Body text.
    pub body: String,
}

/// Status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Idle (not started).
    Idle,
    /// Running.
    Running,
    /// Completed.
    Completed,
    /// Dismissed.
    Dismissed,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CoachmarkTour {
    /// Schema version.
    pub schema_version: String,
    /// Steps.
    pub steps: Vec<Step>,
    /// Current index (only meaningful when status=Running).
    pub current_index: usize,
    /// Status.
    pub status: Status,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TourError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("anchor empty")]
    EmptyAnchor,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Empty.
    #[error("body empty")]
    EmptyBody,
    /// No steps.
    #[error("no steps")]
    NoSteps,
    /// Not running.
    #[error("not running")]
    NotRunning,
}

impl CoachmarkTour {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            steps: Vec::new(),
            current_index: 0,
            status: Status::Idle,
        }
    }

    /// Append step.
    pub fn add_step(&mut self, anchor: &str, title: &str, body: &str) -> Result<(), TourError> {
        if anchor.is_empty() {
            return Err(TourError::EmptyAnchor);
        }
        if title.is_empty() {
            return Err(TourError::EmptyTitle);
        }
        if body.is_empty() {
            return Err(TourError::EmptyBody);
        }
        self.steps.push(Step {
            anchor: anchor.into(),
            title: title.into(),
            body: body.into(),
        });
        Ok(())
    }

    /// Start tour.
    pub fn start(&mut self) -> Result<(), TourError> {
        if self.steps.is_empty() {
            return Err(TourError::NoSteps);
        }
        self.current_index = 0;
        self.status = Status::Running;
        Ok(())
    }

    /// Advance.
    pub fn next(&mut self) -> Result<(), TourError> {
        if self.status != Status::Running {
            return Err(TourError::NotRunning);
        }
        if self.current_index + 1 >= self.steps.len() {
            self.status = Status::Completed;
        } else {
            self.current_index += 1;
        }
        Ok(())
    }

    /// Go back.
    pub fn prev(&mut self) -> Result<(), TourError> {
        if self.status != Status::Running {
            return Err(TourError::NotRunning);
        }
        if self.current_index > 0 {
            self.current_index -= 1;
        }
        Ok(())
    }

    /// Dismiss.
    pub fn dismiss(&mut self) -> Result<(), TourError> {
        if self.status != Status::Running {
            return Err(TourError::NotRunning);
        }
        self.status = Status::Dismissed;
        Ok(())
    }

    /// Current step when Running.
    pub fn current(&self) -> Option<&Step> {
        if self.status == Status::Running {
            self.steps.get(self.current_index)
        } else {
            None
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TourError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TourError::SchemaMismatch);
        }
        for s in &self.steps {
            if s.anchor.is_empty() {
                return Err(TourError::EmptyAnchor);
            }
            if s.title.is_empty() {
                return Err(TourError::EmptyTitle);
            }
            if s.body.is_empty() {
                return Err(TourError::EmptyBody);
            }
        }
        Ok(())
    }
}

impl Default for CoachmarkTour {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tour() -> CoachmarkTour {
        let mut t = CoachmarkTour::new();
        t.add_step("w1", "Welcome", "Hello!").unwrap();
        t.add_step("w2", "Tools", "Use the toolbar").unwrap();
        t.add_step("w3", "Done", "You're set.").unwrap();
        t
    }

    #[test]
    fn fresh_is_idle() {
        let t = tour();
        assert_eq!(t.status, Status::Idle);
        assert!(t.current().is_none());
    }

    #[test]
    fn start_runs() {
        let mut t = tour();
        t.start().unwrap();
        assert_eq!(t.status, Status::Running);
        assert_eq!(t.current().unwrap().anchor, "w1");
    }

    #[test]
    fn next_advances_and_completes() {
        let mut t = tour();
        t.start().unwrap();
        t.next().unwrap();
        assert_eq!(t.current().unwrap().anchor, "w2");
        t.next().unwrap();
        assert_eq!(t.current().unwrap().anchor, "w3");
        t.next().unwrap();
        assert_eq!(t.status, Status::Completed);
    }

    #[test]
    fn prev_goes_back() {
        let mut t = tour();
        t.start().unwrap();
        t.next().unwrap();
        t.prev().unwrap();
        assert_eq!(t.current_index, 0);
    }

    #[test]
    fn prev_at_first_noop() {
        let mut t = tour();
        t.start().unwrap();
        t.prev().unwrap();
        assert_eq!(t.current_index, 0);
    }

    #[test]
    fn dismiss_ends() {
        let mut t = tour();
        t.start().unwrap();
        t.dismiss().unwrap();
        assert_eq!(t.status, Status::Dismissed);
    }

    #[test]
    fn cannot_next_when_not_running() {
        let mut t = tour();
        assert!(matches!(t.next().unwrap_err(), TourError::NotRunning));
    }

    #[test]
    fn no_steps_cannot_start() {
        let mut t = CoachmarkTour::new();
        assert!(matches!(t.start().unwrap_err(), TourError::NoSteps));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut t = CoachmarkTour::new();
        assert!(matches!(
            t.add_step("", "t", "b").unwrap_err(),
            TourError::EmptyAnchor
        ));
        assert!(matches!(
            t.add_step("a", "", "b").unwrap_err(),
            TourError::EmptyTitle
        ));
        assert!(matches!(
            t.add_step("a", "t", "").unwrap_err(),
            TourError::EmptyBody
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = tour();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            TourError::SchemaMismatch
        ));
    }

    #[test]
    fn tour_serde_roundtrip() {
        let mut t = tour();
        t.start().unwrap();
        t.next().unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: CoachmarkTour = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
