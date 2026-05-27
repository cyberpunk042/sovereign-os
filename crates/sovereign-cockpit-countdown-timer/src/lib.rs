//! `sovereign-cockpit-countdown-timer` — countdown timer.
//!
//! Phase{Idle/Running{started_at, accumulated_ms}/Paused{
//! accumulated_ms}/Finished}. start/pause/resume/reset/tick.
//! remaining_ms(now) returns the remaining time.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phase.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Phase {
    /// Idle.
    Idle,
    /// Running.
    Running {
        /// Timestamp running entered.
        started_at_ms: u64,
        /// Accumulated elapsed (excluding current run).
        accumulated_ms: u64,
    },
    /// Paused.
    Paused {
        /// Accumulated elapsed.
        accumulated_ms: u64,
    },
    /// Finished.
    Finished,
}

/// State.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct CountdownTimer {
    /// Schema version marker.
    pub schema_version_marker: u32,
    /// Duration.
    pub duration_ms: u64,
    /// Phase.
    pub phase: Phase,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TimerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero duration.
    #[error("duration must be > 0")]
    ZeroDuration,
    /// Invalid transition.
    #[error("invalid transition")]
    InvalidTransition,
}

impl CountdownTimer {
    /// New.
    pub fn new(duration_ms: u64) -> Result<Self, TimerError> {
        if duration_ms == 0 {
            return Err(TimerError::ZeroDuration);
        }
        Ok(Self {
            schema_version_marker: 1,
            duration_ms,
            phase: Phase::Idle,
        })
    }

    /// Start.
    pub fn start(&mut self, now_ms: u64) -> Result<(), TimerError> {
        match self.phase {
            Phase::Idle => {
                self.phase = Phase::Running {
                    started_at_ms: now_ms,
                    accumulated_ms: 0,
                };
                Ok(())
            }
            _ => Err(TimerError::InvalidTransition),
        }
    }

    /// Pause.
    pub fn pause(&mut self, now_ms: u64) -> Result<(), TimerError> {
        match self.phase {
            Phase::Running {
                started_at_ms,
                accumulated_ms,
            } => {
                let run_elapsed = now_ms.saturating_sub(started_at_ms);
                self.phase = Phase::Paused {
                    accumulated_ms: accumulated_ms.saturating_add(run_elapsed),
                };
                Ok(())
            }
            _ => Err(TimerError::InvalidTransition),
        }
    }

    /// Resume.
    pub fn resume(&mut self, now_ms: u64) -> Result<(), TimerError> {
        match self.phase {
            Phase::Paused { accumulated_ms } => {
                self.phase = Phase::Running {
                    started_at_ms: now_ms,
                    accumulated_ms,
                };
                Ok(())
            }
            _ => Err(TimerError::InvalidTransition),
        }
    }

    /// Reset to Idle.
    pub fn reset(&mut self) {
        self.phase = Phase::Idle;
    }

    /// Tick: transitions to Finished if elapsed >= duration.
    pub fn tick(&mut self, now_ms: u64) -> Phase {
        let elapsed = self.elapsed_ms(now_ms);
        if elapsed >= self.duration_ms && !matches!(self.phase, Phase::Finished) {
            self.phase = Phase::Finished;
        }
        self.phase
    }

    /// Elapsed (whether or not finished).
    pub fn elapsed_ms(&self, now_ms: u64) -> u64 {
        match self.phase {
            Phase::Idle => 0,
            Phase::Running {
                started_at_ms,
                accumulated_ms,
            } => accumulated_ms.saturating_add(now_ms.saturating_sub(started_at_ms)),
            Phase::Paused { accumulated_ms } => accumulated_ms,
            Phase::Finished => self.duration_ms,
        }
    }

    /// Remaining.
    pub fn remaining_ms(&self, now_ms: u64) -> u64 {
        self.duration_ms.saturating_sub(self.elapsed_ms(now_ms))
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TimerError> {
        if self.schema_version_marker != 1 {
            return Err(TimerError::SchemaMismatch);
        }
        if self.duration_ms == 0 {
            return Err(TimerError::ZeroDuration);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_run_finish() {
        let mut t = CountdownTimer::new(1000).unwrap();
        t.start(0).unwrap();
        assert_eq!(t.remaining_ms(500), 500);
        t.tick(1500);
        assert!(matches!(t.phase, Phase::Finished));
    }

    #[test]
    fn pause_freezes_elapsed() {
        let mut t = CountdownTimer::new(1000).unwrap();
        t.start(0).unwrap();
        t.pause(300).unwrap();
        // After 5 seconds idle, elapsed remains 300.
        assert_eq!(t.elapsed_ms(5000), 300);
    }

    #[test]
    fn resume_continues() {
        let mut t = CountdownTimer::new(1000).unwrap();
        t.start(0).unwrap();
        t.pause(300).unwrap();
        t.resume(1000).unwrap();
        assert_eq!(t.elapsed_ms(1500), 800);
    }

    #[test]
    fn reset_to_idle() {
        let mut t = CountdownTimer::new(1000).unwrap();
        t.start(0).unwrap();
        t.reset();
        assert_eq!(t.elapsed_ms(500), 0);
    }

    #[test]
    fn invalid_transitions_rejected() {
        let mut t = CountdownTimer::new(1000).unwrap();
        assert!(matches!(
            t.pause(0).unwrap_err(),
            TimerError::InvalidTransition
        ));
        assert!(matches!(
            t.resume(0).unwrap_err(),
            TimerError::InvalidTransition
        ));
        t.start(0).unwrap();
        assert!(matches!(
            t.start(0).unwrap_err(),
            TimerError::InvalidTransition
        ));
    }

    #[test]
    fn zero_duration_rejected() {
        assert!(matches!(
            CountdownTimer::new(0).unwrap_err(),
            TimerError::ZeroDuration
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = CountdownTimer::new(1000).unwrap();
        t.schema_version_marker = 99;
        assert!(matches!(
            t.validate().unwrap_err(),
            TimerError::SchemaMismatch
        ));
    }

    #[test]
    fn timer_serde_roundtrip() {
        let mut t = CountdownTimer::new(1000).unwrap();
        t.start(0).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: CountdownTimer = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
