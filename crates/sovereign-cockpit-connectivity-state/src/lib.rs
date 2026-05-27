//! `sovereign-cockpit-connectivity-state` — connection state.
//!
//! State{Online/Degraded/Reconnecting/Offline}. observe(rtt_ms,
//! ok) chooses next state:
//! - ok=true: Online if rtt_ms <= degraded_threshold_ms,
//!   else Degraded; reconnect_attempts resets.
//! - ok=false: Offline if attempts >= max_attempts else
//!   Reconnecting; attempts increment.
//! force_online / force_offline override.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    /// Online (RTT under degraded_threshold).
    Online,
    /// Degraded (Online but slow).
    Degraded,
    /// Reconnecting (failing, under max_attempts).
    Reconnecting,
    /// Offline (max_attempts exhausted).
    Offline,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConnectivityState {
    /// Schema version.
    pub schema_version: String,
    /// Current state.
    pub state: State,
    /// RTT threshold for Degraded (ms).
    pub degraded_threshold_ms: u32,
    /// Max reconnect attempts before Offline.
    pub max_attempts: u32,
    /// Current reconnect attempts.
    pub reconnect_attempts: u32,
    /// Last observed RTT ms (None until first ok observation).
    pub last_rtt_ms: Option<u32>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ConnError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero max.
    #[error("max_attempts must be >= 1")]
    ZeroMaxAttempts,
    /// Zero threshold.
    #[error("degraded_threshold_ms must be >= 1")]
    ZeroThreshold,
}

impl ConnectivityState {
    /// New (Online).
    pub fn new(degraded_threshold_ms: u32, max_attempts: u32) -> Result<Self, ConnError> {
        if degraded_threshold_ms == 0 {
            return Err(ConnError::ZeroThreshold);
        }
        if max_attempts == 0 {
            return Err(ConnError::ZeroMaxAttempts);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            state: State::Online,
            degraded_threshold_ms,
            max_attempts,
            reconnect_attempts: 0,
            last_rtt_ms: None,
        })
    }

    /// Observe a probe outcome.
    pub fn observe(&mut self, rtt_ms: u32, ok: bool) -> State {
        if ok {
            self.last_rtt_ms = Some(rtt_ms);
            self.reconnect_attempts = 0;
            self.state = if rtt_ms <= self.degraded_threshold_ms {
                State::Online
            } else {
                State::Degraded
            };
        } else {
            self.reconnect_attempts = self.reconnect_attempts.saturating_add(1);
            self.state = if self.reconnect_attempts >= self.max_attempts {
                State::Offline
            } else {
                State::Reconnecting
            };
        }
        self.state
    }

    /// Force Online (operator override).
    pub fn force_online(&mut self) {
        self.state = State::Online;
        self.reconnect_attempts = 0;
    }

    /// Force Offline (operator override).
    pub fn force_offline(&mut self) {
        self.state = State::Offline;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ConnError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ConnError::SchemaMismatch);
        }
        if self.degraded_threshold_ms == 0 {
            return Err(ConnError::ZeroThreshold);
        }
        if self.max_attempts == 0 {
            return Err(ConnError::ZeroMaxAttempts);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ok_under_threshold_is_online() {
        let mut c = ConnectivityState::new(100, 3).unwrap();
        assert_eq!(c.observe(50, true), State::Online);
    }

    #[test]
    fn ok_over_threshold_is_degraded() {
        let mut c = ConnectivityState::new(100, 3).unwrap();
        assert_eq!(c.observe(200, true), State::Degraded);
    }

    #[test]
    fn fail_under_max_is_reconnecting() {
        let mut c = ConnectivityState::new(100, 3).unwrap();
        assert_eq!(c.observe(0, false), State::Reconnecting);
        assert_eq!(c.observe(0, false), State::Reconnecting);
    }

    #[test]
    fn fail_at_max_is_offline() {
        let mut c = ConnectivityState::new(100, 3).unwrap();
        c.observe(0, false);
        c.observe(0, false);
        assert_eq!(c.observe(0, false), State::Offline);
    }

    #[test]
    fn ok_after_fail_resets_attempts() {
        let mut c = ConnectivityState::new(100, 3).unwrap();
        c.observe(0, false);
        c.observe(0, false);
        c.observe(50, true);
        assert_eq!(c.reconnect_attempts, 0);
        assert_eq!(c.state, State::Online);
    }

    #[test]
    fn force_overrides() {
        let mut c = ConnectivityState::new(100, 3).unwrap();
        c.observe(0, false);
        c.observe(0, false);
        c.force_online();
        assert_eq!(c.state, State::Online);
        c.force_offline();
        assert_eq!(c.state, State::Offline);
    }

    #[test]
    fn bad_inputs_rejected() {
        assert!(matches!(
            ConnectivityState::new(0, 3).unwrap_err(),
            ConnError::ZeroThreshold
        ));
        assert!(matches!(
            ConnectivityState::new(100, 0).unwrap_err(),
            ConnError::ZeroMaxAttempts
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = ConnectivityState::new(100, 3).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            ConnError::SchemaMismatch
        ));
    }

    #[test]
    fn conn_serde_roundtrip() {
        let mut c = ConnectivityState::new(100, 3).unwrap();
        c.observe(50, true);
        let j = serde_json::to_string(&c).unwrap();
        let back: ConnectivityState = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
