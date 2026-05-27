//! `sovereign-cockpit-pull-to-refresh` — pull-down gesture state machine.
//!
//! Transitions:
//!
//!   Idle ─start()→ Pulling{distance:0, progress:0}
//!   Pulling ─move(d)→ Pulling{d, p} where p = clamp(d / trigger_px, 0, 100)
//!     when d ≥ trigger_px → enters Armed{d}
//!   Armed ─move(d)→ Armed if d ≥ trigger_px, else back to Pulling{d, p}
//!   Pulling ─release()→ Idle  (cancelled)
//!   Armed ─release()→ Refreshing
//!   Refreshing ─finish()→ Idle
//!
//! `progress` is reported 0..=100 so the chrome can spin its indicator.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Phase {
    /// Idle.
    Idle,
    /// Pulling down, below trigger.
    Pulling {
        /// distance px.
        distance_px: u32,
        /// progress 0..=100.
        progress_pct: u8,
    },
    /// Armed — release will fire refresh.
    Armed {
        /// distance px.
        distance_px: u32,
    },
    /// Refresh in flight.
    Refreshing,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PullToRefresh {
    /// Schema version.
    pub schema_version: String,
    /// Distance (px) at which the gesture arms.
    pub trigger_px: u32,
    /// Current phase.
    pub phase: Phase,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PullError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// trigger_px zero.
    #[error("trigger_px must be > 0")]
    TriggerZero,
    /// Wrong phase for action.
    #[error("invalid transition from current phase")]
    InvalidTransition,
}

impl PullToRefresh {
    /// New.
    pub fn new(trigger_px: u32) -> Result<Self, PullError> {
        if trigger_px == 0 {
            return Err(PullError::TriggerZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            trigger_px,
            phase: Phase::Idle,
        })
    }

    /// Start the gesture.
    pub fn start(&mut self) -> Result<Phase, PullError> {
        match self.phase {
            Phase::Idle => {
                self.phase = Phase::Pulling {
                    distance_px: 0,
                    progress_pct: 0,
                };
                Ok(self.phase)
            }
            _ => Err(PullError::InvalidTransition),
        }
    }

    /// Update distance.
    pub fn r#move(&mut self, distance_px: u32) -> Result<Phase, PullError> {
        match self.phase {
            Phase::Pulling { .. } | Phase::Armed { .. } => {
                if distance_px >= self.trigger_px {
                    self.phase = Phase::Armed { distance_px };
                } else {
                    let progress = ((distance_px as u32) * 100 / self.trigger_px) as u8;
                    self.phase = Phase::Pulling {
                        distance_px,
                        progress_pct: progress,
                    };
                }
                Ok(self.phase)
            }
            _ => Err(PullError::InvalidTransition),
        }
    }

    /// Release the gesture. Returns true if a refresh was armed.
    pub fn release(&mut self) -> Result<bool, PullError> {
        match self.phase {
            Phase::Pulling { .. } => {
                self.phase = Phase::Idle;
                Ok(false)
            }
            Phase::Armed { .. } => {
                self.phase = Phase::Refreshing;
                Ok(true)
            }
            _ => Err(PullError::InvalidTransition),
        }
    }

    /// Caller signals the refresh I/O is done.
    pub fn finish(&mut self) -> Result<(), PullError> {
        match self.phase {
            Phase::Refreshing => {
                self.phase = Phase::Idle;
                Ok(())
            }
            _ => Err(PullError::InvalidTransition),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PullError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PullError::SchemaMismatch);
        }
        if self.trigger_px == 0 {
            return Err(PullError::TriggerZero);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trigger_zero_rejected() {
        assert!(matches!(
            PullToRefresh::new(0).unwrap_err(),
            PullError::TriggerZero
        ));
    }

    #[test]
    fn start_enters_pulling() {
        let mut p = PullToRefresh::new(60).unwrap();
        let s = p.start().unwrap();
        assert_eq!(
            s,
            Phase::Pulling {
                distance_px: 0,
                progress_pct: 0
            }
        );
    }

    #[test]
    fn move_progress_partial() {
        let mut p = PullToRefresh::new(100).unwrap();
        p.start().unwrap();
        let s = p.r#move(50).unwrap();
        assert_eq!(
            s,
            Phase::Pulling {
                distance_px: 50,
                progress_pct: 50
            }
        );
    }

    #[test]
    fn move_past_trigger_arms() {
        let mut p = PullToRefresh::new(60).unwrap();
        p.start().unwrap();
        let s = p.r#move(80).unwrap();
        assert_eq!(s, Phase::Armed { distance_px: 80 });
    }

    #[test]
    fn move_back_below_trigger_disarms() {
        let mut p = PullToRefresh::new(60).unwrap();
        p.start().unwrap();
        p.r#move(80).unwrap();
        let s = p.r#move(40).unwrap();
        assert!(matches!(s, Phase::Pulling { .. }));
    }

    #[test]
    fn release_pulling_cancels() {
        let mut p = PullToRefresh::new(60).unwrap();
        p.start().unwrap();
        p.r#move(20).unwrap();
        assert!(!p.release().unwrap());
        assert_eq!(p.phase, Phase::Idle);
    }

    #[test]
    fn release_armed_refreshes() {
        let mut p = PullToRefresh::new(60).unwrap();
        p.start().unwrap();
        p.r#move(80).unwrap();
        assert!(p.release().unwrap());
        assert_eq!(p.phase, Phase::Refreshing);
    }

    #[test]
    fn finish_returns_idle() {
        let mut p = PullToRefresh::new(60).unwrap();
        p.start().unwrap();
        p.r#move(80).unwrap();
        p.release().unwrap();
        p.finish().unwrap();
        assert_eq!(p.phase, Phase::Idle);
    }

    #[test]
    fn invalid_transitions_rejected() {
        let mut p = PullToRefresh::new(60).unwrap();
        // move() while Idle.
        assert!(matches!(
            p.r#move(10).unwrap_err(),
            PullError::InvalidTransition
        ));
        // release() while Idle.
        assert!(matches!(
            p.release().unwrap_err(),
            PullError::InvalidTransition
        ));
        // finish() while Idle.
        assert!(matches!(
            p.finish().unwrap_err(),
            PullError::InvalidTransition
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = PullToRefresh::new(60).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PullError::SchemaMismatch
        ));
    }

    #[test]
    fn pull_serde_roundtrip() {
        let mut p = PullToRefresh::new(60).unwrap();
        p.start().unwrap();
        p.r#move(20).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: PullToRefresh = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
