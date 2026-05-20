//! `sovereign-cockpit-stream-pause` — live-stream pause/resume.
//!
//! `pause()` halts the live view; events that arrive while paused
//! are counted in `queued_count` (but not retained — the queue is
//! just a counter for the operator's awareness). `resume()` clears
//! the counter and resumes. `drop_queued()` clears without resuming.
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
pub struct StreamPause {
    /// Schema version.
    pub schema_version: String,
    /// Paused?
    pub paused: bool,
    /// Queued count.
    pub queued_count: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PauseError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl StreamPause {
    /// New (running, no queue).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            paused: false,
            queued_count: 0,
        }
    }

    /// Pause.
    pub fn pause(&mut self) { self.paused = true; }

    /// Resume.
    pub fn resume(&mut self) {
        self.paused = false;
        self.queued_count = 0;
    }

    /// Observe an arriving event. Only counted while paused.
    pub fn observe(&mut self) {
        if self.paused {
            self.queued_count = self.queued_count.saturating_add(1);
        }
    }

    /// Drop queued.
    pub fn drop_queued(&mut self) { self.queued_count = 0; }

    /// Validate.
    pub fn validate(&self) -> Result<(), PauseError> {
        if self.schema_version != SCHEMA_VERSION { return Err(PauseError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for StreamPause {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn observe_running_does_not_count() {
        let mut p = StreamPause::new();
        p.observe();
        p.observe();
        assert_eq!(p.queued_count, 0);
    }

    #[test]
    fn observe_while_paused_counts() {
        let mut p = StreamPause::new();
        p.pause();
        p.observe();
        p.observe();
        p.observe();
        assert_eq!(p.queued_count, 3);
    }

    #[test]
    fn resume_clears() {
        let mut p = StreamPause::new();
        p.pause();
        p.observe();
        p.resume();
        assert_eq!(p.queued_count, 0);
        assert!(!p.paused);
    }

    #[test]
    fn drop_queued_keeps_paused() {
        let mut p = StreamPause::new();
        p.pause();
        p.observe();
        p.drop_queued();
        assert_eq!(p.queued_count, 0);
        assert!(p.paused);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = StreamPause::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), PauseError::SchemaMismatch));
    }

    #[test]
    fn pause_serde_roundtrip() {
        let mut p = StreamPause::new();
        p.pause();
        p.observe();
        let j = serde_json::to_string(&p).unwrap();
        let back: StreamPause = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
