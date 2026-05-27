//! `sovereign-cockpit-page-transition` — page transition state.
//!
//! 4 phases: Idle (nothing happening), Outgoing (old page sliding
//! out), Entering (new page sliding in), Active (transient settled
//! frame). tick(ms) advances; Direction tracks forward/back so the
//! renderer can pick slide direction.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Direction {
    /// Forward (drill in).
    Forward,
    /// Back (drill out).
    Back,
}

/// Phase.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Phase {
    /// Idle.
    Idle,
    /// Outgoing — old page sliding out.
    Outgoing,
    /// Entering — new page sliding in.
    Entering,
    /// Active — settled.
    Active,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PageTransition {
    /// Schema version.
    pub schema_version: String,
    /// Outgoing duration (ms).
    pub outgoing_ms: u32,
    /// Entering duration (ms).
    pub entering_ms: u32,
    /// Active settle hold (ms).
    pub active_ms: u32,
    /// Current phase.
    pub phase: Phase,
    /// Direction.
    pub direction: Direction,
    /// Elapsed in current phase.
    pub elapsed_ms: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TransitionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero duration.
    #[error("phase {0:?} duration is zero")]
    DurationZero(Phase),
}

impl PageTransition {
    /// New idle.
    pub fn new(
        outgoing_ms: u32,
        entering_ms: u32,
        active_ms: u32,
    ) -> Result<Self, TransitionError> {
        if outgoing_ms == 0 {
            return Err(TransitionError::DurationZero(Phase::Outgoing));
        }
        if entering_ms == 0 {
            return Err(TransitionError::DurationZero(Phase::Entering));
        }
        if active_ms == 0 {
            return Err(TransitionError::DurationZero(Phase::Active));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            outgoing_ms,
            entering_ms,
            active_ms,
            phase: Phase::Idle,
            direction: Direction::Forward,
            elapsed_ms: 0,
        })
    }

    /// Start a navigation.
    pub fn start(&mut self, direction: Direction) {
        self.direction = direction;
        self.phase = Phase::Outgoing;
        self.elapsed_ms = 0;
    }

    /// Tick. Returns whether phase changed.
    pub fn tick(&mut self, dt_ms: u32) -> bool {
        if self.phase == Phase::Idle {
            return false;
        }
        let max = self.duration_for(self.phase);
        self.elapsed_ms = self.elapsed_ms.saturating_add(dt_ms);
        if self.elapsed_ms < max {
            return false;
        }
        // Phase complete; advance.
        let new_phase = match self.phase {
            Phase::Outgoing => Phase::Entering,
            Phase::Entering => Phase::Active,
            Phase::Active => Phase::Idle,
            Phase::Idle => Phase::Idle,
        };
        self.phase = new_phase;
        self.elapsed_ms = 0;
        true
    }

    /// Current phase duration.
    pub fn duration_for(&self, p: Phase) -> u32 {
        match p {
            Phase::Outgoing => self.outgoing_ms,
            Phase::Entering => self.entering_ms,
            Phase::Active => self.active_ms,
            Phase::Idle => 0,
        }
    }

    /// Progress through current phase (0.0..=1.0).
    pub fn progress(&self) -> f32 {
        let d = self.duration_for(self.phase);
        if d == 0 {
            return 0.0;
        }
        (self.elapsed_ms as f32 / d as f32).min(1.0)
    }

    /// Is animating?
    pub fn is_animating(&self) -> bool {
        !matches!(self.phase, Phase::Idle)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TransitionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TransitionError::SchemaMismatch);
        }
        if self.outgoing_ms == 0 {
            return Err(TransitionError::DurationZero(Phase::Outgoing));
        }
        if self.entering_ms == 0 {
            return Err(TransitionError::DurationZero(Phase::Entering));
        }
        if self.active_ms == 0 {
            return Err(TransitionError::DurationZero(Phase::Active));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t() -> PageTransition {
        PageTransition::new(100, 200, 50).unwrap()
    }

    #[test]
    fn duration_zero_rejected() {
        assert!(matches!(
            PageTransition::new(0, 1, 1).unwrap_err(),
            TransitionError::DurationZero(Phase::Outgoing)
        ));
        assert!(matches!(
            PageTransition::new(1, 0, 1).unwrap_err(),
            TransitionError::DurationZero(Phase::Entering)
        ));
        assert!(matches!(
            PageTransition::new(1, 1, 0).unwrap_err(),
            TransitionError::DurationZero(Phase::Active)
        ));
    }

    #[test]
    fn start_sets_outgoing() {
        let mut x = t();
        x.start(Direction::Forward);
        assert_eq!(x.phase, Phase::Outgoing);
        assert_eq!(x.direction, Direction::Forward);
    }

    #[test]
    fn tick_advances_through_phases() {
        let mut x = t();
        x.start(Direction::Forward);
        // 100 ms -> Entering
        assert!(x.tick(100));
        assert_eq!(x.phase, Phase::Entering);
        // 200 ms -> Active
        assert!(x.tick(200));
        assert_eq!(x.phase, Phase::Active);
        // 50 ms -> Idle
        assert!(x.tick(50));
        assert_eq!(x.phase, Phase::Idle);
        // No further ticks effect
        assert!(!x.tick(1000));
    }

    #[test]
    fn idle_tick_is_noop() {
        let mut x = t();
        assert!(!x.tick(100));
        assert_eq!(x.phase, Phase::Idle);
    }

    #[test]
    fn progress_zero_at_start() {
        let mut x = t();
        x.start(Direction::Forward);
        assert_eq!(x.progress(), 0.0);
    }

    #[test]
    fn progress_caps_at_one() {
        let mut x = t();
        x.start(Direction::Forward);
        x.elapsed_ms = 999;
        assert_eq!(x.progress(), 1.0);
    }

    #[test]
    fn is_animating_during_phases() {
        let mut x = t();
        assert!(!x.is_animating());
        x.start(Direction::Forward);
        assert!(x.is_animating());
        x.tick(1000);
        x.tick(1000);
        x.tick(1000);
        assert!(!x.is_animating());
    }

    #[test]
    fn back_direction_preserved() {
        let mut x = t();
        x.start(Direction::Back);
        x.tick(50);
        assert_eq!(x.direction, Direction::Back);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut x = t();
        x.schema_version = "9.9.9".into();
        assert!(matches!(
            x.validate().unwrap_err(),
            TransitionError::SchemaMismatch
        ));
    }

    #[test]
    fn phase_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Phase::Outgoing).unwrap(),
            "\"outgoing\""
        );
        assert_eq!(
            serde_json::to_string(&Phase::Entering).unwrap(),
            "\"entering\""
        );
    }

    #[test]
    fn transition_serde_roundtrip() {
        let mut x = t();
        x.start(Direction::Forward);
        let j = serde_json::to_string(&x).unwrap();
        let back: PageTransition = serde_json::from_str(&j).unwrap();
        assert_eq!(x, back);
    }
}
