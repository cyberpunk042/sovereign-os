//! `sovereign-cockpit-emergency-stop` — double-confirm kill button.
//!
//! Phase{Locked/Armed/Triggered}. arm(now) Locked → Armed and
//! records armed_at_ms. trigger(now, reason) Armed → Triggered
//! iff (now - armed_at_ms) <= arm_window_ms. cancel returns to
//! Locked.
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
    /// Locked.
    Locked,
    /// Armed.
    Armed,
    /// Triggered (one-way).
    Triggered,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EmergencyStop {
    /// Schema version.
    pub schema_version: String,
    /// Phase.
    pub phase: Phase,
    /// Arm window ms.
    pub arm_window_ms: u64,
    /// armed_at_ms.
    pub armed_at_ms: u64,
    /// Reason when triggered.
    pub reason: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StopError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero window.
    #[error("arm_window_ms must be >= 1")]
    ZeroWindow,
    /// Empty.
    #[error("reason empty")]
    EmptyReason,
    /// Not armed.
    #[error("not armed")]
    NotArmed,
    /// Window expired.
    #[error("arm window expired")]
    WindowExpired,
}

impl EmergencyStop {
    /// New (Locked).
    pub fn new(arm_window_ms: u64) -> Result<Self, StopError> {
        if arm_window_ms == 0 {
            return Err(StopError::ZeroWindow);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            phase: Phase::Locked,
            arm_window_ms,
            armed_at_ms: 0,
            reason: None,
        })
    }

    /// Arm.
    pub fn arm(&mut self, now_ms: u64) {
        if self.phase == Phase::Triggered {
            return;
        }
        self.phase = Phase::Armed;
        self.armed_at_ms = now_ms;
    }

    /// Cancel back to Locked (only when Armed).
    pub fn cancel(&mut self) {
        if self.phase == Phase::Armed {
            self.phase = Phase::Locked;
        }
    }

    /// Trigger.
    pub fn trigger(&mut self, now_ms: u64, reason: &str) -> Result<(), StopError> {
        if self.phase != Phase::Armed {
            return Err(StopError::NotArmed);
        }
        if reason.is_empty() {
            return Err(StopError::EmptyReason);
        }
        if now_ms.saturating_sub(self.armed_at_ms) > self.arm_window_ms {
            self.phase = Phase::Locked;
            return Err(StopError::WindowExpired);
        }
        self.phase = Phase::Triggered;
        self.reason = Some(reason.into());
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StopError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(StopError::SchemaMismatch);
        }
        if self.arm_window_ms == 0 {
            return Err(StopError::ZeroWindow);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn locked_initially() {
        let s = EmergencyStop::new(1000).unwrap();
        assert_eq!(s.phase, Phase::Locked);
    }

    #[test]
    fn arm_then_trigger_within_window() {
        let mut s = EmergencyStop::new(1000).unwrap();
        s.arm(0);
        s.trigger(500, "operator").unwrap();
        assert_eq!(s.phase, Phase::Triggered);
        assert_eq!(s.reason.as_deref(), Some("operator"));
    }

    #[test]
    fn trigger_outside_window_returns_to_locked() {
        let mut s = EmergencyStop::new(1000).unwrap();
        s.arm(0);
        assert!(matches!(
            s.trigger(5000, "operator").unwrap_err(),
            StopError::WindowExpired
        ));
        assert_eq!(s.phase, Phase::Locked);
    }

    #[test]
    fn trigger_without_arm_rejected() {
        let mut s = EmergencyStop::new(1000).unwrap();
        assert!(matches!(
            s.trigger(0, "operator").unwrap_err(),
            StopError::NotArmed
        ));
    }

    #[test]
    fn cancel_returns_to_locked() {
        let mut s = EmergencyStop::new(1000).unwrap();
        s.arm(0);
        s.cancel();
        assert_eq!(s.phase, Phase::Locked);
    }

    #[test]
    fn empty_reason_rejected() {
        let mut s = EmergencyStop::new(1000).unwrap();
        s.arm(0);
        assert!(matches!(
            s.trigger(0, "").unwrap_err(),
            StopError::EmptyReason
        ));
    }

    #[test]
    fn zero_window_rejected() {
        assert!(matches!(
            EmergencyStop::new(0).unwrap_err(),
            StopError::ZeroWindow
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = EmergencyStop::new(1000).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            StopError::SchemaMismatch
        ));
    }

    #[test]
    fn stop_serde_roundtrip() {
        let mut s = EmergencyStop::new(1000).unwrap();
        s.arm(0);
        let j = serde_json::to_string(&s).unwrap();
        let back: EmergencyStop = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
