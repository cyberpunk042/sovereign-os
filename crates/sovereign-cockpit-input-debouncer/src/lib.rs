//! `sovereign-cockpit-input-debouncer` — trailing-edge debouncer.
//!
//! Calling `observe(now_ms)` records a fresh event; `ready(now_ms)`
//! returns true once `delay_ms` has elapsed since the last observe
//! AND `consume()` has not yet been called for that quiet period.
//!
//! Typical loop:
//! ```ignore
//! d.observe(t);
//! if d.ready(t + delay) && d.consume() { fire(); }
//! ```
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
pub struct InputDebouncer {
    /// Schema version.
    pub schema_version: String,
    /// Quiet period (ms).
    pub delay_ms: u64,
    /// Last observed ts.
    pub last_observed_ms: Option<u64>,
    /// Last consumed ts (the observe ts whose quiet period was consumed).
    pub last_consumed_observed_ms: Option<u64>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DebounceError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// delay zero.
    #[error("delay_ms must be > 0")]
    DelayZero,
}

impl InputDebouncer {
    /// New.
    pub fn new(delay_ms: u64) -> Result<Self, DebounceError> {
        if delay_ms == 0 { return Err(DebounceError::DelayZero); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            delay_ms,
            last_observed_ms: None,
            last_consumed_observed_ms: None,
        })
    }

    /// Observe an event.
    pub fn observe(&mut self, now_ms: u64) {
        self.last_observed_ms = Some(now_ms);
    }

    /// Ready to fire?
    pub fn ready(&self, now_ms: u64) -> bool {
        let last = match self.last_observed_ms {
            Some(t) => t,
            None => return false,
        };
        if let Some(c) = self.last_consumed_observed_ms {
            if c == last { return false; }
        }
        now_ms.saturating_sub(last) >= self.delay_ms
    }

    /// Consume — returns true if a pending fire was claimed.
    pub fn consume(&mut self) -> bool {
        let last = match self.last_observed_ms {
            Some(t) => t,
            None => return false,
        };
        if self.last_consumed_observed_ms == Some(last) {
            return false;
        }
        self.last_consumed_observed_ms = Some(last);
        true
    }

    /// Cancel any pending fire (e.g. on focus blur).
    pub fn cancel(&mut self) {
        self.last_consumed_observed_ms = self.last_observed_ms;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DebounceError> {
        if self.schema_version != SCHEMA_VERSION { return Err(DebounceError::SchemaMismatch); }
        if self.delay_ms == 0 { return Err(DebounceError::DelayZero); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn delay_zero_rejected() {
        assert!(matches!(InputDebouncer::new(0).unwrap_err(), DebounceError::DelayZero));
    }

    #[test]
    fn no_observe_no_ready() {
        let d = InputDebouncer::new(200).unwrap();
        assert!(!d.ready(1_000_000));
    }

    #[test]
    fn ready_after_delay() {
        let mut d = InputDebouncer::new(200).unwrap();
        d.observe(0);
        assert!(!d.ready(100));
        assert!(d.ready(200));
    }

    #[test]
    fn fresh_observe_resets_timer() {
        let mut d = InputDebouncer::new(200).unwrap();
        d.observe(0);
        d.observe(150);
        assert!(!d.ready(250));
        assert!(d.ready(350));
    }

    #[test]
    fn consume_returns_true_once() {
        let mut d = InputDebouncer::new(200).unwrap();
        d.observe(0);
        assert!(d.ready(200));
        assert!(d.consume());
        assert!(!d.consume());
        assert!(!d.ready(300));
    }

    #[test]
    fn observe_after_consume_arms_again() {
        let mut d = InputDebouncer::new(200).unwrap();
        d.observe(0);
        d.consume();
        d.observe(300);
        assert!(d.ready(500));
        assert!(d.consume());
    }

    #[test]
    fn cancel_clears_pending() {
        let mut d = InputDebouncer::new(200).unwrap();
        d.observe(0);
        d.cancel();
        assert!(!d.ready(500));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = InputDebouncer::new(200).unwrap();
        d.schema_version = "9.9.9".into();
        assert!(matches!(d.validate().unwrap_err(), DebounceError::SchemaMismatch));
    }

    #[test]
    fn debouncer_serde_roundtrip() {
        let mut d = InputDebouncer::new(200).unwrap();
        d.observe(100);
        let j = serde_json::to_string(&d).unwrap();
        let back: InputDebouncer = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
