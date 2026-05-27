//! `sovereign-cockpit-onboarding-flow` — first-run guided tour.
//!
//! 8 steps with linear forward/back navigation + skip-to-end.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 8 canonical onboarding steps.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Step {
    /// Welcome screen.
    Welcome,
    /// Pick theme.
    Theme,
    /// Pick locale.
    Locale,
    /// Pick profile.
    Profile,
    /// First conversation tutorial.
    FirstConversation,
    /// Dashboard tour.
    DashboardTour,
    /// Replay tour.
    ReplayTour,
    /// Done.
    Done,
}

/// Flow state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct OnboardingFlow {
    /// Schema version.
    pub schema_version: String,
    /// Current step.
    pub current: Step,
    /// Completed (i.e. operator reached Done or skipped).
    pub completed: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FlowError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Already at first step.
    #[error("at first step (Welcome)")]
    AtFirst,
    /// Already at last step.
    #[error("at last step (Done)")]
    AtLast,
}

const ORDER: [Step; 8] = [
    Step::Welcome,
    Step::Theme,
    Step::Locale,
    Step::Profile,
    Step::FirstConversation,
    Step::DashboardTour,
    Step::ReplayTour,
    Step::Done,
];

fn step_index(s: Step) -> usize {
    ORDER.iter().position(|x| *x == s).unwrap_or(0)
}

impl OnboardingFlow {
    /// New flow starting at Welcome.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            current: Step::Welcome,
            completed: false,
        }
    }

    /// Advance to next step.
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> Result<Step, FlowError> {
        if self.current == Step::Done {
            return Err(FlowError::AtLast);
        }
        let idx = step_index(self.current);
        self.current = ORDER[idx + 1];
        if self.current == Step::Done {
            self.completed = true;
        }
        Ok(self.current)
    }

    /// Go back.
    pub fn back(&mut self) -> Result<Step, FlowError> {
        if self.current == Step::Welcome {
            return Err(FlowError::AtFirst);
        }
        let idx = step_index(self.current);
        self.current = ORDER[idx - 1];
        // Going back un-completes.
        self.completed = false;
        Ok(self.current)
    }

    /// Skip to end.
    pub fn skip(&mut self) {
        self.current = Step::Done;
        self.completed = true;
    }

    /// Reset to start.
    pub fn reset(&mut self) {
        self.current = Step::Welcome;
        self.completed = false;
    }

    /// Progress percent (0..=100).
    pub fn progress_pct(&self) -> u8 {
        let idx = step_index(self.current);
        ((idx * 100) / (ORDER.len() - 1)) as u8
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FlowError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FlowError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for OnboardingFlow {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_starts_at_welcome() {
        let f = OnboardingFlow::new();
        assert_eq!(f.current, Step::Welcome);
        assert!(!f.completed);
        assert_eq!(f.progress_pct(), 0);
        f.validate().unwrap();
    }

    #[test]
    fn next_advances() {
        let mut f = OnboardingFlow::new();
        assert_eq!(f.next().unwrap(), Step::Theme);
        assert_eq!(f.next().unwrap(), Step::Locale);
    }

    #[test]
    fn reach_done_marks_completed() {
        let mut f = OnboardingFlow::new();
        for _ in 0..7 {
            f.next().unwrap();
        }
        assert_eq!(f.current, Step::Done);
        assert!(f.completed);
        assert_eq!(f.progress_pct(), 100);
    }

    #[test]
    fn next_on_done_rejected() {
        let mut f = OnboardingFlow::new();
        f.skip();
        assert!(matches!(f.next().unwrap_err(), FlowError::AtLast));
    }

    #[test]
    fn back_walks_back() {
        let mut f = OnboardingFlow::new();
        f.next().unwrap();
        f.next().unwrap();
        assert_eq!(f.back().unwrap(), Step::Theme);
    }

    #[test]
    fn back_at_welcome_rejected() {
        let mut f = OnboardingFlow::new();
        assert!(matches!(f.back().unwrap_err(), FlowError::AtFirst));
    }

    #[test]
    fn back_uncompletes() {
        let mut f = OnboardingFlow::new();
        f.skip();
        assert!(f.completed);
        f.back().unwrap();
        assert!(!f.completed);
    }

    #[test]
    fn skip_jumps_to_done() {
        let mut f = OnboardingFlow::new();
        f.skip();
        assert_eq!(f.current, Step::Done);
        assert!(f.completed);
    }

    #[test]
    fn reset_restores() {
        let mut f = OnboardingFlow::new();
        f.skip();
        f.reset();
        assert_eq!(f.current, Step::Welcome);
        assert!(!f.completed);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = OnboardingFlow::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FlowError::SchemaMismatch
        ));
    }

    #[test]
    fn step_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Step::FirstConversation).unwrap(),
            "\"first-conversation\""
        );
        assert_eq!(
            serde_json::to_string(&Step::DashboardTour).unwrap(),
            "\"dashboard-tour\""
        );
    }

    #[test]
    fn flow_serde_roundtrip() {
        let mut f = OnboardingFlow::new();
        f.next().unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: OnboardingFlow = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
