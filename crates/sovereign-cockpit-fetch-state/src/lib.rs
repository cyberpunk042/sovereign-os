//! `sovereign-cockpit-fetch-state` — async-resource state machine.
//!
//! `State::Idle → Loading{started_at} → Ready{loaded_at} | Errored
//! {error, ts}`. Operators drive the state machine via
//! `start_loading/loaded/errored/reset`. `is_stale(now,
//! stale_after_ms)` reports Ready-but-stale.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum State {
    /// Idle.
    Idle,
    /// Loading.
    Loading {
        /// when started.
        started_at_ms: u64,
    },
    /// Ready.
    Ready {
        /// when loaded.
        loaded_at_ms: u64,
    },
    /// Errored.
    Errored {
        /// error label.
        error: String,
        /// ts.
        ts_ms: u64,
    },
}

/// State wrapper.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FetchState {
    /// Schema version.
    pub schema_version: String,
    /// State.
    pub state: State,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FetchError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty error label.
    #[error("error label empty")]
    EmptyError,
}

impl FetchState {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            state: State::Idle,
        }
    }

    /// Start loading.
    pub fn start_loading(&mut self, now_ms: u64) {
        self.state = State::Loading {
            started_at_ms: now_ms,
        };
    }

    /// Loaded successfully.
    pub fn loaded(&mut self, now_ms: u64) {
        self.state = State::Ready {
            loaded_at_ms: now_ms,
        };
    }

    /// Errored.
    pub fn errored(&mut self, error: &str, now_ms: u64) -> Result<(), FetchError> {
        if error.is_empty() {
            return Err(FetchError::EmptyError);
        }
        self.state = State::Errored {
            error: error.into(),
            ts_ms: now_ms,
        };
        Ok(())
    }

    /// Reset to idle.
    pub fn reset(&mut self) {
        self.state = State::Idle;
    }

    /// Is Ready and past stale_after_ms.
    pub fn is_stale(&self, now_ms: u64, stale_after_ms: u64) -> bool {
        match self.state {
            State::Ready { loaded_at_ms } => now_ms.saturating_sub(loaded_at_ms) > stale_after_ms,
            _ => false,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FetchError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FetchError::SchemaMismatch);
        }
        if let State::Errored { error, .. } = &self.state
            && error.is_empty()
        {
            return Err(FetchError::EmptyError);
        }
        Ok(())
    }
}

impl Default for FetchState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn idle_default() {
        assert_eq!(FetchState::new().state, State::Idle);
    }

    #[test]
    fn full_lifecycle() {
        let mut f = FetchState::new();
        f.start_loading(0);
        assert_eq!(f.state, State::Loading { started_at_ms: 0 });
        f.loaded(100);
        assert_eq!(f.state, State::Ready { loaded_at_ms: 100 });
    }

    #[test]
    fn errored_transition() {
        let mut f = FetchState::new();
        f.start_loading(0);
        f.errored("network", 50).unwrap();
        match &f.state {
            State::Errored { error, ts_ms } => {
                assert_eq!(error, "network");
                assert_eq!(*ts_ms, 50);
            }
            _ => panic!(),
        }
    }

    #[test]
    fn empty_error_rejected() {
        let mut f = FetchState::new();
        assert!(matches!(
            f.errored("", 0).unwrap_err(),
            FetchError::EmptyError
        ));
    }

    #[test]
    fn reset_returns_idle() {
        let mut f = FetchState::new();
        f.start_loading(0);
        f.reset();
        assert_eq!(f.state, State::Idle);
    }

    #[test]
    fn is_stale_after_window() {
        let mut f = FetchState::new();
        f.loaded(100);
        assert!(!f.is_stale(500, 1000));
        assert!(f.is_stale(5000, 1000));
    }

    #[test]
    fn is_stale_idle_false() {
        let f = FetchState::new();
        assert!(!f.is_stale(99_999, 1));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = FetchState::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FetchError::SchemaMismatch
        ));
    }

    #[test]
    fn fetch_serde_roundtrip() {
        let mut f = FetchState::new();
        f.loaded(100);
        let j = serde_json::to_string(&f).unwrap();
        let back: FetchState = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
