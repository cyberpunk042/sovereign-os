//! `sovereign-cockpit-dictation-state` — voice dictation FSM.
//!
//! State transitions:
//!   Idle ─request→ Listening ─partial─→ Listening (accumulate partial)
//!   Listening ─finalize→ Finalizing ─complete→ Idle (commit transcript)
//!   Listening|Finalizing ─error→ Errored
//!   Errored ─reset→ Idle
//!
//! The model carries `partial_transcript` (current best-effort
//! interim text) and `committed_transcript` (last finalized text).
//! `mic_level_db` is a clamped -60..=0 indicator.
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
    /// Listening.
    Listening,
    /// Finalizing.
    Finalizing,
    /// Errored.
    Errored,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DictationState {
    /// Schema version.
    pub schema_version: String,
    /// Phase.
    pub phase: Phase,
    /// Interim transcript.
    pub partial_transcript: String,
    /// Last finalized transcript.
    pub committed_transcript: String,
    /// Mic level (dB, clamped -60..=0).
    pub mic_level_db: i32,
    /// Last error message.
    pub last_error: Option<String>,
    /// Times session has started.
    pub session_count: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DictationError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty error message.
    #[error("error message empty")]
    EmptyError,
    /// Invalid transition.
    #[error("invalid transition from {from:?} via {via}")]
    InvalidTransition {
        /// from.
        from: Phase,
        /// via.
        via: &'static str,
    },
}

impl DictationState {
    /// New (Idle).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            phase: Phase::Idle,
            partial_transcript: String::new(),
            committed_transcript: String::new(),
            mic_level_db: -60,
            last_error: None,
            session_count: 0,
        }
    }

    /// Start listening. Idle → Listening or Errored → Listening (via reset).
    pub fn request(&mut self) -> Result<(), DictationError> {
        match self.phase {
            Phase::Idle => {
                self.phase = Phase::Listening;
                self.partial_transcript.clear();
                self.last_error = None;
                self.session_count = self.session_count.saturating_add(1);
                Ok(())
            }
            other => Err(DictationError::InvalidTransition {
                from: other,
                via: "request",
            }),
        }
    }

    /// Update interim transcript. Listening only.
    pub fn partial(&mut self, text: &str, mic_level_db: i32) -> Result<(), DictationError> {
        if self.phase != Phase::Listening {
            return Err(DictationError::InvalidTransition {
                from: self.phase,
                via: "partial",
            });
        }
        self.partial_transcript = text.into();
        self.mic_level_db = mic_level_db.clamp(-60, 0);
        Ok(())
    }

    /// Begin finalization. Listening → Finalizing.
    pub fn finalize(&mut self) -> Result<(), DictationError> {
        if self.phase != Phase::Listening {
            return Err(DictationError::InvalidTransition {
                from: self.phase,
                via: "finalize",
            });
        }
        self.phase = Phase::Finalizing;
        Ok(())
    }

    /// Complete with final text. Finalizing → Idle.
    pub fn complete(&mut self, final_text: &str) -> Result<(), DictationError> {
        if self.phase != Phase::Finalizing {
            return Err(DictationError::InvalidTransition {
                from: self.phase,
                via: "complete",
            });
        }
        self.committed_transcript = final_text.into();
        self.partial_transcript.clear();
        self.phase = Phase::Idle;
        self.mic_level_db = -60;
        Ok(())
    }

    /// Error out from Listening or Finalizing.
    pub fn error(&mut self, message: &str) -> Result<(), DictationError> {
        if message.is_empty() {
            return Err(DictationError::EmptyError);
        }
        match self.phase {
            Phase::Listening | Phase::Finalizing => {
                self.phase = Phase::Errored;
                self.last_error = Some(message.into());
                self.mic_level_db = -60;
                Ok(())
            }
            other => Err(DictationError::InvalidTransition {
                from: other,
                via: "error",
            }),
        }
    }

    /// Reset from Errored → Idle.
    pub fn reset(&mut self) -> Result<(), DictationError> {
        if self.phase != Phase::Errored {
            return Err(DictationError::InvalidTransition {
                from: self.phase,
                via: "reset",
            });
        }
        self.phase = Phase::Idle;
        self.partial_transcript.clear();
        self.last_error = None;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DictationError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DictationError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for DictationState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn happy_path() {
        let mut d = DictationState::new();
        d.request().unwrap();
        d.partial("hello", -10).unwrap();
        d.partial("hello world", -8).unwrap();
        d.finalize().unwrap();
        d.complete("Hello, world.").unwrap();
        assert_eq!(d.phase, Phase::Idle);
        assert_eq!(d.committed_transcript, "Hello, world.");
        assert!(d.partial_transcript.is_empty());
    }

    #[test]
    fn double_request_rejected() {
        let mut d = DictationState::new();
        d.request().unwrap();
        assert!(matches!(
            d.request().unwrap_err(),
            DictationError::InvalidTransition { .. }
        ));
    }

    #[test]
    fn partial_from_idle_rejected() {
        let mut d = DictationState::new();
        assert!(matches!(
            d.partial("x", 0).unwrap_err(),
            DictationError::InvalidTransition { .. }
        ));
    }

    #[test]
    fn finalize_from_idle_rejected() {
        let mut d = DictationState::new();
        assert!(matches!(
            d.finalize().unwrap_err(),
            DictationError::InvalidTransition { .. }
        ));
    }

    #[test]
    fn error_then_reset() {
        let mut d = DictationState::new();
        d.request().unwrap();
        d.error("mic busy").unwrap();
        assert_eq!(d.phase, Phase::Errored);
        d.reset().unwrap();
        assert_eq!(d.phase, Phase::Idle);
        d.request().unwrap();
    }

    #[test]
    fn error_from_idle_rejected() {
        let mut d = DictationState::new();
        assert!(matches!(
            d.error("x").unwrap_err(),
            DictationError::InvalidTransition { .. }
        ));
    }

    #[test]
    fn empty_error_rejected() {
        let mut d = DictationState::new();
        d.request().unwrap();
        assert!(matches!(
            d.error("").unwrap_err(),
            DictationError::EmptyError
        ));
    }

    #[test]
    fn mic_level_clamped() {
        let mut d = DictationState::new();
        d.request().unwrap();
        d.partial("x", 50).unwrap();
        assert_eq!(d.mic_level_db, 0);
        d.partial("x", -100).unwrap();
        assert_eq!(d.mic_level_db, -60);
    }

    #[test]
    fn session_count_increments() {
        let mut d = DictationState::new();
        d.request().unwrap();
        d.finalize().unwrap();
        d.complete("a").unwrap();
        d.request().unwrap();
        assert_eq!(d.session_count, 2);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = DictationState::new();
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            DictationError::SchemaMismatch
        ));
    }

    #[test]
    fn dictation_serde_roundtrip() {
        let mut d = DictationState::new();
        d.request().unwrap();
        d.partial("hi", -5).unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: DictationState = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
