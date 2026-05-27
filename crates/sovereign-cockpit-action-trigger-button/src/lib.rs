//! `sovereign-cockpit-action-trigger-button` — single-action button.
//!
//! Phase{Idle/Pending/Success/Failed}. trigger → Pending; complete
//! → Success; fail → Failed. Success/Failed auto-reset to Idle
//! after `transient_ms` via tick(now).
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
    /// Pending.
    Pending,
    /// Success.
    Success,
    /// Failed.
    Failed,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionTriggerButton {
    /// Schema version.
    pub schema_version: String,
    /// Phase.
    pub phase: Phase,
    /// Transient duration (Success/Failed auto-reset).
    pub transient_ms: u64,
    /// Last phase change ts.
    pub last_change_ms: u64,
    /// Last error.
    pub last_error: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ButtonError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty error.
    #[error("error empty")]
    EmptyError,
    /// Invalid transition.
    #[error("invalid transition")]
    InvalidTransition,
}

impl ActionTriggerButton {
    /// New.
    pub fn new(transient_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            phase: Phase::Idle,
            transient_ms,
            last_change_ms: 0,
            last_error: None,
        }
    }

    /// Trigger.
    pub fn trigger(&mut self, ts_ms: u64) -> Result<(), ButtonError> {
        if !matches!(self.phase, Phase::Idle | Phase::Failed | Phase::Success) {
            return Err(ButtonError::InvalidTransition);
        }
        self.phase = Phase::Pending;
        self.last_change_ms = ts_ms;
        self.last_error = None;
        Ok(())
    }

    /// Complete (success).
    pub fn complete(&mut self, ts_ms: u64) -> Result<(), ButtonError> {
        if self.phase != Phase::Pending {
            return Err(ButtonError::InvalidTransition);
        }
        self.phase = Phase::Success;
        self.last_change_ms = ts_ms;
        Ok(())
    }

    /// Fail.
    pub fn fail(&mut self, error: &str, ts_ms: u64) -> Result<(), ButtonError> {
        if error.is_empty() {
            return Err(ButtonError::EmptyError);
        }
        if self.phase != Phase::Pending {
            return Err(ButtonError::InvalidTransition);
        }
        self.phase = Phase::Failed;
        self.last_error = Some(error.into());
        self.last_change_ms = ts_ms;
        Ok(())
    }

    /// Tick — auto-reset Success/Failed after transient_ms.
    pub fn tick(&mut self, now_ms: u64) -> Phase {
        if matches!(self.phase, Phase::Success | Phase::Failed) {
            if now_ms.saturating_sub(self.last_change_ms) >= self.transient_ms {
                self.phase = Phase::Idle;
            }
        }
        self.phase
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ButtonError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ButtonError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn happy_path() {
        let mut b = ActionTriggerButton::new(1000);
        b.trigger(0).unwrap();
        b.complete(100).unwrap();
        assert_eq!(b.phase, Phase::Success);
    }

    #[test]
    fn fail_path() {
        let mut b = ActionTriggerButton::new(1000);
        b.trigger(0).unwrap();
        b.fail("oops", 100).unwrap();
        assert_eq!(b.phase, Phase::Failed);
        assert_eq!(b.last_error.as_deref(), Some("oops"));
    }

    #[test]
    fn auto_reset_after_transient() {
        let mut b = ActionTriggerButton::new(1000);
        b.trigger(0).unwrap();
        b.complete(100).unwrap();
        assert_eq!(b.tick(1500), Phase::Idle);
    }

    #[test]
    fn retrigger_from_failed() {
        let mut b = ActionTriggerButton::new(1000);
        b.trigger(0).unwrap();
        b.fail("x", 100).unwrap();
        b.trigger(200).unwrap();
        assert_eq!(b.phase, Phase::Pending);
    }

    #[test]
    fn double_trigger_rejected() {
        let mut b = ActionTriggerButton::new(1000);
        b.trigger(0).unwrap();
        assert!(matches!(
            b.trigger(100).unwrap_err(),
            ButtonError::InvalidTransition
        ));
    }

    #[test]
    fn complete_without_trigger_rejected() {
        let mut b = ActionTriggerButton::new(1000);
        assert!(matches!(
            b.complete(0).unwrap_err(),
            ButtonError::InvalidTransition
        ));
    }

    #[test]
    fn empty_error_rejected() {
        let mut b = ActionTriggerButton::new(1000);
        b.trigger(0).unwrap();
        assert!(matches!(
            b.fail("", 0).unwrap_err(),
            ButtonError::EmptyError
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = ActionTriggerButton::new(1000);
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            ButtonError::SchemaMismatch
        ));
    }

    #[test]
    fn button_serde_roundtrip() {
        let mut b = ActionTriggerButton::new(1000);
        b.trigger(0).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: ActionTriggerButton = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
