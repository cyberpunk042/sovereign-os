//! `sovereign-cockpit-feature-tour` — on-demand guided tour state.
//!
//! Tours are registered with an ordered list of `Step`. `start(tour)`
//! activates a tour at step 0; `next` / `prev` move the cursor;
//! `dismiss(reason)` records the dismissal and stops without
//! marking completed; `complete()` is fired automatically on
//! `next()` past the last step (or manually).
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
    /// DOM anchor id.
    pub anchor_id: String,
    /// Title.
    pub title: String,
    /// Body.
    pub body: String,
    /// May the operator dismiss this step early?
    pub dismissable: bool,
}

/// One tour.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tour {
    /// Stable id.
    pub id: String,
    /// Display title.
    pub title: String,
    /// Steps.
    pub steps: Vec<Step>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FeatureTour {
    /// Schema version.
    pub schema_version: String,
    /// Registered tours.
    pub tours: BTreeMap<String, Tour>,
    /// Currently active (tour_id, step_index).
    pub active: Option<(String, usize)>,
    /// Tours the operator has fully completed.
    pub completed: BTreeSet<String>,
    /// Tours dismissed (skipped) with reason.
    pub dismissed: BTreeMap<String, String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TourError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Unknown tour.
    #[error("unknown tour id: {0}")]
    UnknownTour(String),
    /// Empty steps.
    #[error("tour {0} has no steps")]
    NoSteps(String),
    /// No active tour.
    #[error("no active tour")]
    NoActiveTour,
}

impl FeatureTour {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            tours: BTreeMap::new(),
            active: None,
            completed: BTreeSet::new(),
            dismissed: BTreeMap::new(),
        }
    }

    /// Register a tour.
    pub fn register(&mut self, tour: Tour) -> Result<(), TourError> {
        if tour.id.is_empty() {
            return Err(TourError::EmptyId);
        }
        if tour.steps.is_empty() {
            return Err(TourError::NoSteps(tour.id.clone()));
        }
        for s in &tour.steps {
            if s.id.is_empty() || s.anchor_id.is_empty() {
                return Err(TourError::EmptyId);
            }
        }
        self.tours.insert(tour.id.clone(), tour);
        Ok(())
    }

    /// Start a tour.
    pub fn start(&mut self, tour_id: &str) -> Result<(), TourError> {
        if !self.tours.contains_key(tour_id) {
            return Err(TourError::UnknownTour(tour_id.into()));
        }
        self.active = Some((tour_id.into(), 0));
        Ok(())
    }

    /// Current step pointer.
    pub fn current_step(&self) -> Option<(&Tour, &Step)> {
        let (tour_id, idx) = self.active.as_ref()?;
        let t = self.tours.get(tour_id)?;
        let s = t.steps.get(*idx)?;
        Some((t, s))
    }

    /// Next step. If past the last step, marks completed and clears active.
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> Result<(), TourError> {
        let (tour_id, idx) = self.active.clone().ok_or(TourError::NoActiveTour)?;
        let total = self.tours.get(&tour_id).map(|t| t.steps.len()).unwrap_or(0);
        let next = idx + 1;
        if next >= total {
            self.completed.insert(tour_id.clone());
            self.active = None;
        } else {
            self.active = Some((tour_id, next));
        }
        Ok(())
    }

    /// Prev step.
    pub fn prev(&mut self) -> Result<(), TourError> {
        let (tour_id, idx) = self.active.clone().ok_or(TourError::NoActiveTour)?;
        if idx > 0 {
            self.active = Some((tour_id, idx - 1));
        }
        Ok(())
    }

    /// Dismiss.
    pub fn dismiss(&mut self, reason: &str) -> Result<(), TourError> {
        let (tour_id, _) = self.active.clone().ok_or(TourError::NoActiveTour)?;
        self.dismissed.insert(tour_id, reason.into());
        self.active = None;
        Ok(())
    }

    /// Complete the current tour now.
    pub fn complete(&mut self) -> Result<(), TourError> {
        let (tour_id, _) = self.active.clone().ok_or(TourError::NoActiveTour)?;
        self.completed.insert(tour_id);
        self.active = None;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TourError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TourError::SchemaMismatch);
        }
        for (id, t) in &self.tours {
            if id.is_empty() {
                return Err(TourError::EmptyId);
            }
            if t.steps.is_empty() {
                return Err(TourError::NoSteps(id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for FeatureTour {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(id: &str, steps: usize) -> Tour {
        Tour {
            id: id.into(),
            title: id.into(),
            steps: (0..steps)
                .map(|i| Step {
                    id: format!("s{i}"),
                    anchor_id: format!("a{i}"),
                    title: format!("S{i}"),
                    body: "...".into(),
                    dismissable: true,
                })
                .collect(),
        }
    }

    #[test]
    fn register_and_start() {
        let mut f = FeatureTour::new();
        f.register(t("demo", 2)).unwrap();
        f.start("demo").unwrap();
        let (_, s) = f.current_step().unwrap();
        assert_eq!(s.id, "s0");
    }

    #[test]
    fn next_advances() {
        let mut f = FeatureTour::new();
        f.register(t("demo", 2)).unwrap();
        f.start("demo").unwrap();
        f.next().unwrap();
        let (_, s) = f.current_step().unwrap();
        assert_eq!(s.id, "s1");
    }

    #[test]
    fn next_past_last_completes() {
        let mut f = FeatureTour::new();
        f.register(t("demo", 2)).unwrap();
        f.start("demo").unwrap();
        f.next().unwrap();
        f.next().unwrap();
        assert!(f.active.is_none());
        assert!(f.completed.contains("demo"));
    }

    #[test]
    fn prev_clamps_at_zero() {
        let mut f = FeatureTour::new();
        f.register(t("demo", 2)).unwrap();
        f.start("demo").unwrap();
        f.prev().unwrap();
        let (_, s) = f.current_step().unwrap();
        assert_eq!(s.id, "s0");
    }

    #[test]
    fn dismiss_records_reason() {
        let mut f = FeatureTour::new();
        f.register(t("demo", 2)).unwrap();
        f.start("demo").unwrap();
        f.dismiss("not now").unwrap();
        assert!(f.active.is_none());
        assert_eq!(f.dismissed.get("demo").map(String::as_str), Some("not now"));
        assert!(!f.completed.contains("demo"));
    }

    #[test]
    fn complete_now() {
        let mut f = FeatureTour::new();
        f.register(t("demo", 4)).unwrap();
        f.start("demo").unwrap();
        f.complete().unwrap();
        assert!(f.completed.contains("demo"));
    }

    #[test]
    fn unknown_tour_rejected() {
        let mut f = FeatureTour::new();
        assert!(matches!(
            f.start("nope").unwrap_err(),
            TourError::UnknownTour(_)
        ));
    }

    #[test]
    fn empty_steps_rejected() {
        let mut f = FeatureTour::new();
        assert!(matches!(
            f.register(t("demo", 0)).unwrap_err(),
            TourError::NoSteps(_)
        ));
    }

    #[test]
    fn no_active_tour_actions_rejected() {
        let mut f = FeatureTour::new();
        assert!(matches!(f.next().unwrap_err(), TourError::NoActiveTour));
        assert!(matches!(
            f.dismiss("x").unwrap_err(),
            TourError::NoActiveTour
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = FeatureTour::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            TourError::SchemaMismatch
        ));
    }

    #[test]
    fn tour_serde_roundtrip() {
        let mut f = FeatureTour::new();
        f.register(t("demo", 2)).unwrap();
        f.start("demo").unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: FeatureTour = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
