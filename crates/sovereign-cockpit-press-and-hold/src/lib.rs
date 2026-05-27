//! `sovereign-cockpit-press-and-hold` — confirm-by-hold gauge.
//!
//! Phase{Idle/Pressing/Committed/Cancelled}. press(now) starts
//! Pressing; tick(now) returns progress_bp (0..=10000) based on
//! (now - press_started)/hold_ms. release(now) returns Outcome
//! ::Commit if progress >= 10000 else Outcome::Cancel.
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
#[serde(rename_all = "kebab-case")]
pub enum Phase {
    /// Idle.
    Idle,
    /// Pressing.
    Pressing,
    /// Committed.
    Committed,
    /// Cancelled.
    Cancelled,
}

/// Outcome.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Outcome {
    /// Commit.
    Commit,
    /// Cancel.
    Cancel,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PressAndHold {
    /// Schema version.
    pub schema_version: String,
    /// Hold ms.
    pub hold_ms: u64,
    /// Phase.
    pub phase: Phase,
    /// Press start ts.
    pub started_ms: u64,
    /// Commits count.
    pub commits: u64,
    /// Cancels count.
    pub cancels: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HoldError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero hold.
    #[error("hold_ms must be >= 1")]
    ZeroHold,
    /// Not pressing.
    #[error("not pressing")]
    NotPressing,
}

impl PressAndHold {
    /// New.
    pub fn new(hold_ms: u64) -> Result<Self, HoldError> {
        if hold_ms == 0 {
            return Err(HoldError::ZeroHold);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            hold_ms,
            phase: Phase::Idle,
            started_ms: 0,
            commits: 0,
            cancels: 0,
        })
    }

    /// Start pressing.
    pub fn press(&mut self, now_ms: u64) {
        self.phase = Phase::Pressing;
        self.started_ms = now_ms;
    }

    /// Progress in basis points (0..=10000) at now_ms.
    pub fn progress_bp(&self, now_ms: u64) -> u32 {
        if self.phase != Phase::Pressing {
            return 0;
        }
        let elapsed = now_ms.saturating_sub(self.started_ms);
        ((elapsed.min(self.hold_ms) * 10_000) / self.hold_ms) as u32
    }

    /// Release; returns outcome.
    pub fn release(&mut self, now_ms: u64) -> Result<Outcome, HoldError> {
        if self.phase != Phase::Pressing {
            return Err(HoldError::NotPressing);
        }
        let progress = self.progress_bp(now_ms);
        let outcome = if progress >= 10_000 {
            self.phase = Phase::Committed;
            self.commits = self.commits.saturating_add(1);
            Outcome::Commit
        } else {
            self.phase = Phase::Cancelled;
            self.cancels = self.cancels.saturating_add(1);
            Outcome::Cancel
        };
        Ok(outcome)
    }

    /// Reset to Idle.
    pub fn reset(&mut self) {
        self.phase = Phase::Idle;
        self.started_ms = 0;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HoldError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HoldError::SchemaMismatch);
        }
        if self.hold_ms == 0 {
            return Err(HoldError::ZeroHold);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn release_at_full_commits() {
        let mut h = PressAndHold::new(1000).unwrap();
        h.press(0);
        assert_eq!(h.release(1000).unwrap(), Outcome::Commit);
        assert_eq!(h.phase, Phase::Committed);
    }

    #[test]
    fn early_release_cancels() {
        let mut h = PressAndHold::new(1000).unwrap();
        h.press(0);
        assert_eq!(h.release(500).unwrap(), Outcome::Cancel);
        assert_eq!(h.phase, Phase::Cancelled);
    }

    #[test]
    fn progress_half() {
        let mut h = PressAndHold::new(1000).unwrap();
        h.press(0);
        assert_eq!(h.progress_bp(500), 5000);
    }

    #[test]
    fn progress_caps_at_10000() {
        let mut h = PressAndHold::new(1000).unwrap();
        h.press(0);
        assert_eq!(h.progress_bp(9999), 10000);
    }

    #[test]
    fn release_without_press_rejected() {
        let mut h = PressAndHold::new(1000).unwrap();
        assert!(matches!(h.release(0).unwrap_err(), HoldError::NotPressing));
    }

    #[test]
    fn reset_to_idle() {
        let mut h = PressAndHold::new(1000).unwrap();
        h.press(0);
        h.release(500).unwrap();
        h.reset();
        assert_eq!(h.phase, Phase::Idle);
    }

    #[test]
    fn zero_hold_rejected() {
        assert!(matches!(
            PressAndHold::new(0).unwrap_err(),
            HoldError::ZeroHold
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = PressAndHold::new(1000).unwrap();
        h.schema_version = "9.9.9".into();
        assert!(matches!(
            h.validate().unwrap_err(),
            HoldError::SchemaMismatch
        ));
    }

    #[test]
    fn hold_serde_roundtrip() {
        let mut h = PressAndHold::new(1000).unwrap();
        h.press(100);
        let j = serde_json::to_string(&h).unwrap();
        let back: PressAndHold = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
