//! `sovereign-cockpit-retry-banner` — retry-banner state.
//!
//! Phase{Idle, Failed{retry_at_ms, attempt}, Retrying, Succeeded}.
//! fail(now, retry_after_ms) → Failed; tick(now) checks if retry
//! window elapsed (returns true when ready). retry(now) → Retrying.
//! succeed → Succeeded. dismiss → Idle. attempt counter increments
//! on each failure.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phase.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "phase")]
pub enum Phase {
    /// Idle.
    Idle,
    /// Failed and waiting for retry.
    Failed {
        /// Earliest retry-allowed ms.
        retry_at_ms: u64,
        /// Attempt count (1-based).
        attempt: u32,
        /// Last error message.
        error: String,
    },
    /// Retrying.
    Retrying {
        /// Attempt being made (1-based).
        attempt: u32,
    },
    /// Succeeded.
    Succeeded,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RetryBanner {
    /// Schema version.
    pub schema_version: String,
    /// Phase.
    pub phase: Phase,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BannerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Invalid phase.
    #[error("invalid phase for operation")]
    InvalidPhase,
    /// Empty.
    #[error("error empty")]
    EmptyError,
}

impl RetryBanner {
    /// New (Idle).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            phase: Phase::Idle,
        }
    }

    /// Record a failure.
    pub fn fail(&mut self, now_ms: u64, retry_after_ms: u64, err: &str) -> Result<(), BannerError> {
        if err.is_empty() {
            return Err(BannerError::EmptyError);
        }
        let attempt = match &self.phase {
            Phase::Failed { attempt, .. } => attempt + 1,
            Phase::Retrying { attempt } => *attempt,
            _ => 1,
        };
        self.phase = Phase::Failed {
            retry_at_ms: now_ms.saturating_add(retry_after_ms),
            attempt,
            error: err.into(),
        };
        Ok(())
    }

    /// Is the retry window open?
    pub fn ready(&self, now_ms: u64) -> bool {
        match &self.phase {
            Phase::Failed { retry_at_ms, .. } => now_ms >= *retry_at_ms,
            _ => false,
        }
    }

    /// Time remaining until retry (None if not Failed).
    pub fn time_left(&self, now_ms: u64) -> Option<u64> {
        match &self.phase {
            Phase::Failed { retry_at_ms, .. } => Some(retry_at_ms.saturating_sub(now_ms)),
            _ => None,
        }
    }

    /// Begin retrying.
    pub fn retry(&mut self, now_ms: u64) -> Result<(), BannerError> {
        let attempt = match &self.phase {
            Phase::Failed {
                attempt,
                retry_at_ms,
                ..
            } => {
                if now_ms < *retry_at_ms {
                    return Err(BannerError::InvalidPhase);
                }
                *attempt
            }
            _ => return Err(BannerError::InvalidPhase),
        };
        self.phase = Phase::Retrying { attempt };
        Ok(())
    }

    /// Succeed.
    pub fn succeed(&mut self) {
        self.phase = Phase::Succeeded;
    }

    /// Dismiss.
    pub fn dismiss(&mut self) {
        self.phase = Phase::Idle;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BannerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BannerError::SchemaMismatch);
        }
        if let Phase::Failed { error, .. } = &self.phase {
            if error.is_empty() {
                return Err(BannerError::EmptyError);
            }
        }
        Ok(())
    }
}

impl Default for RetryBanner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fail_records_attempt() {
        let mut b = RetryBanner::new();
        b.fail(0, 1000, "timeout").unwrap();
        match &b.phase {
            Phase::Failed {
                attempt,
                retry_at_ms,
                error,
            } => {
                assert_eq!(*attempt, 1);
                assert_eq!(*retry_at_ms, 1000);
                assert_eq!(error, "timeout");
            }
            _ => panic!(),
        }
    }

    #[test]
    fn second_fail_increments_attempt() {
        let mut b = RetryBanner::new();
        b.fail(0, 100, "x").unwrap();
        b.fail(100, 200, "y").unwrap();
        match &b.phase {
            Phase::Failed { attempt, .. } => assert_eq!(*attempt, 2),
            _ => panic!(),
        }
    }

    #[test]
    fn ready_only_after_retry_at() {
        let mut b = RetryBanner::new();
        b.fail(0, 1000, "x").unwrap();
        assert!(!b.ready(500));
        assert!(b.ready(1500));
    }

    #[test]
    fn retry_before_window_rejected() {
        let mut b = RetryBanner::new();
        b.fail(0, 1000, "x").unwrap();
        assert!(matches!(
            b.retry(500).unwrap_err(),
            BannerError::InvalidPhase
        ));
    }

    #[test]
    fn full_cycle_succeeds() {
        let mut b = RetryBanner::new();
        b.fail(0, 100, "x").unwrap();
        b.retry(200).unwrap();
        b.succeed();
        assert_eq!(b.phase, Phase::Succeeded);
    }

    #[test]
    fn time_left_decreases() {
        let mut b = RetryBanner::new();
        b.fail(0, 1000, "x").unwrap();
        assert_eq!(b.time_left(0), Some(1000));
        assert_eq!(b.time_left(700), Some(300));
        assert_eq!(b.time_left(1500), Some(0));
    }

    #[test]
    fn empty_error_rejected() {
        let mut b = RetryBanner::new();
        assert!(matches!(
            b.fail(0, 100, "").unwrap_err(),
            BannerError::EmptyError
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = RetryBanner::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            BannerError::SchemaMismatch
        ));
    }

    #[test]
    fn banner_serde_roundtrip() {
        let mut b = RetryBanner::new();
        b.fail(10, 100, "x").unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: RetryBanner = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
