//! `sovereign-cockpit-typing-indicator` — chat-style "is typing…" surface.
//!
//! Holds 0..N concurrent indicators keyed by `who`. Each carries an
//! auto-clear timeout (ms). Caller ticks elapsed_ms; entries that
//! exceed timeout drop automatically.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One indicator.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Indicator {
    /// Who is typing (operator label / model id / etc.).
    pub who: String,
    /// Auto-clear timeout in milliseconds.
    pub timeout_ms: u32,
    /// Milliseconds elapsed since indicator set.
    pub elapsed_ms: u32,
}

/// Indicator set.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TypingIndicatorSet {
    /// Schema version.
    pub schema_version: String,
    /// Active indicators.
    pub indicators: Vec<Indicator>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum IndicatorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty who.
    #[error("indicator `who` empty")]
    EmptyWho,
    /// Timeout 0.
    #[error("indicator timeout_ms zero")]
    ZeroTimeout,
}

impl TypingIndicatorSet {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            indicators: Vec::new(),
        }
    }

    /// Set / refresh an indicator. Same `who` updates elapsed back to 0.
    pub fn set(&mut self, who: &str, timeout_ms: u32) -> Result<(), IndicatorError> {
        if who.is_empty() {
            return Err(IndicatorError::EmptyWho);
        }
        if timeout_ms == 0 {
            return Err(IndicatorError::ZeroTimeout);
        }
        if let Some(i) = self.indicators.iter_mut().find(|i| i.who == who) {
            i.timeout_ms = timeout_ms;
            i.elapsed_ms = 0;
            return Ok(());
        }
        self.indicators.push(Indicator {
            who: who.into(),
            timeout_ms,
            elapsed_ms: 0,
        });
        Ok(())
    }

    /// Tick all indicators by `delta_ms` ms; drops any past timeout.
    pub fn tick(&mut self, delta_ms: u32) {
        for i in self.indicators.iter_mut() {
            i.elapsed_ms = i.elapsed_ms.saturating_add(delta_ms);
        }
        self.indicators.retain(|i| i.elapsed_ms < i.timeout_ms);
    }

    /// Clear an indicator by `who`.
    pub fn clear(&mut self, who: &str) -> bool {
        let n = self.indicators.len();
        self.indicators.retain(|i| i.who != who);
        self.indicators.len() < n
    }

    /// Live indicators.
    pub fn active(&self) -> &[Indicator] {
        &self.indicators
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), IndicatorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(IndicatorError::SchemaMismatch);
        }
        for i in &self.indicators {
            if i.who.is_empty() {
                return Err(IndicatorError::EmptyWho);
            }
            if i.timeout_ms == 0 {
                return Err(IndicatorError::ZeroTimeout);
            }
        }
        Ok(())
    }
}

impl Default for TypingIndicatorSet {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_set_validates() {
        TypingIndicatorSet::new().validate().unwrap();
    }

    #[test]
    fn set_and_active() {
        let mut s = TypingIndicatorSet::new();
        s.set("model-a", 5_000).unwrap();
        assert_eq!(s.active().len(), 1);
        assert_eq!(s.active()[0].who, "model-a");
    }

    #[test]
    fn set_same_who_refreshes() {
        let mut s = TypingIndicatorSet::new();
        s.set("a", 1000).unwrap();
        s.tick(800);
        s.set("a", 1000).unwrap();
        assert_eq!(s.active()[0].elapsed_ms, 0);
    }

    #[test]
    fn tick_drops_past_timeout() {
        let mut s = TypingIndicatorSet::new();
        s.set("a", 1000).unwrap();
        s.tick(500);
        assert_eq!(s.active().len(), 1);
        s.tick(600);
        assert_eq!(s.active().len(), 0);
    }

    #[test]
    fn clear_removes() {
        let mut s = TypingIndicatorSet::new();
        s.set("a", 1000).unwrap();
        assert!(s.clear("a"));
        assert!(s.active().is_empty());
        assert!(!s.clear("a"));
    }

    #[test]
    fn empty_who_rejected() {
        let mut s = TypingIndicatorSet::new();
        assert!(matches!(
            s.set("", 1000).unwrap_err(),
            IndicatorError::EmptyWho
        ));
    }

    #[test]
    fn zero_timeout_rejected() {
        let mut s = TypingIndicatorSet::new();
        assert!(matches!(
            s.set("a", 0).unwrap_err(),
            IndicatorError::ZeroTimeout
        ));
    }

    #[test]
    fn multiple_concurrent_indicators() {
        let mut s = TypingIndicatorSet::new();
        s.set("a", 1000).unwrap();
        s.set("b", 1000).unwrap();
        s.set("c", 1000).unwrap();
        assert_eq!(s.active().len(), 3);
        s.tick(2000);
        assert!(s.active().is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = TypingIndicatorSet::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            IndicatorError::SchemaMismatch
        ));
    }

    #[test]
    fn set_serde_roundtrip() {
        let mut s = TypingIndicatorSet::new();
        s.set("a", 1000).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: TypingIndicatorSet = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
