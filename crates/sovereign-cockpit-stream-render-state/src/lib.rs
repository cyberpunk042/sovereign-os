//! `sovereign-cockpit-stream-render-state` — streaming chunks.
//!
//! Phase{Idle/Streaming/Complete/Errored/Aborted}. append_chunk
//! pushes text; complete/error/abort transition terminal. Aborted
//! is sticky.
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
    /// Streaming.
    Streaming,
    /// Complete.
    Complete,
    /// Errored.
    Errored,
    /// Aborted.
    Aborted,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StreamRenderState {
    /// Schema version.
    pub schema_version: String,
    /// Phase.
    pub phase: Phase,
    /// Accumulated text.
    pub text: String,
    /// Chunks appended.
    pub chunk_count: u64,
    /// First chunk ts.
    pub first_chunk_ms: Option<u64>,
    /// Last update ts.
    pub last_update_ms: u64,
    /// Last error.
    pub last_error: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StreamError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty error.
    #[error("error message empty")]
    EmptyError,
    /// Invalid transition.
    #[error("invalid transition from {0:?}")]
    InvalidTransition(Phase),
}

impl StreamRenderState {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            phase: Phase::Idle,
            text: String::new(),
            chunk_count: 0,
            first_chunk_ms: None,
            last_update_ms: 0,
            last_error: None,
        }
    }

    /// Start.
    pub fn start(&mut self, ts_ms: u64) -> Result<(), StreamError> {
        if !matches!(self.phase, Phase::Idle) {
            return Err(StreamError::InvalidTransition(self.phase));
        }
        self.phase = Phase::Streaming;
        self.text.clear();
        self.chunk_count = 0;
        self.first_chunk_ms = None;
        self.last_update_ms = ts_ms;
        self.last_error = None;
        Ok(())
    }

    /// Append chunk.
    pub fn append_chunk(&mut self, text: &str, ts_ms: u64) -> Result<(), StreamError> {
        if self.phase != Phase::Streaming {
            return Err(StreamError::InvalidTransition(self.phase));
        }
        if self.first_chunk_ms.is_none() {
            self.first_chunk_ms = Some(ts_ms);
        }
        self.text.push_str(text);
        self.chunk_count = self.chunk_count.saturating_add(1);
        self.last_update_ms = ts_ms;
        Ok(())
    }

    /// Complete.
    pub fn complete(&mut self, ts_ms: u64) -> Result<(), StreamError> {
        if self.phase != Phase::Streaming {
            return Err(StreamError::InvalidTransition(self.phase));
        }
        self.phase = Phase::Complete;
        self.last_update_ms = ts_ms;
        Ok(())
    }

    /// Error.
    pub fn error(&mut self, message: &str, ts_ms: u64) -> Result<(), StreamError> {
        if message.is_empty() { return Err(StreamError::EmptyError); }
        if !matches!(self.phase, Phase::Streaming) {
            return Err(StreamError::InvalidTransition(self.phase));
        }
        self.phase = Phase::Errored;
        self.last_error = Some(message.into());
        self.last_update_ms = ts_ms;
        Ok(())
    }

    /// Abort.
    pub fn abort(&mut self, ts_ms: u64) -> Result<(), StreamError> {
        if !matches!(self.phase, Phase::Streaming) {
            return Err(StreamError::InvalidTransition(self.phase));
        }
        self.phase = Phase::Aborted;
        self.last_update_ms = ts_ms;
        Ok(())
    }

    /// Reset to Idle (from any terminal).
    pub fn reset(&mut self) {
        self.phase = Phase::Idle;
        self.text.clear();
        self.chunk_count = 0;
        self.first_chunk_ms = None;
        self.last_error = None;
    }

    /// Time-to-first-chunk.
    pub fn ttfb_ms(&self, started_ms: u64) -> Option<u64> {
        self.first_chunk_ms.map(|t| t.saturating_sub(started_ms))
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StreamError> {
        if self.schema_version != SCHEMA_VERSION { return Err(StreamError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for StreamRenderState {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn happy_stream() {
        let mut s = StreamRenderState::new();
        s.start(0).unwrap();
        s.append_chunk("hello ", 10).unwrap();
        s.append_chunk("world", 20).unwrap();
        s.complete(30).unwrap();
        assert_eq!(s.text, "hello world");
        assert_eq!(s.chunk_count, 2);
        assert_eq!(s.phase, Phase::Complete);
    }

    #[test]
    fn ttfb_computed() {
        let mut s = StreamRenderState::new();
        s.start(0).unwrap();
        s.append_chunk("hi", 50).unwrap();
        assert_eq!(s.ttfb_ms(0), Some(50));
    }

    #[test]
    fn append_in_wrong_phase_rejected() {
        let mut s = StreamRenderState::new();
        assert!(matches!(s.append_chunk("x", 0).unwrap_err(), StreamError::InvalidTransition(_)));
    }

    #[test]
    fn error_path() {
        let mut s = StreamRenderState::new();
        s.start(0).unwrap();
        s.error("timeout", 100).unwrap();
        assert_eq!(s.phase, Phase::Errored);
        assert_eq!(s.last_error.as_deref(), Some("timeout"));
    }

    #[test]
    fn abort_path() {
        let mut s = StreamRenderState::new();
        s.start(0).unwrap();
        s.abort(100).unwrap();
        assert_eq!(s.phase, Phase::Aborted);
    }

    #[test]
    fn reset_to_idle() {
        let mut s = StreamRenderState::new();
        s.start(0).unwrap();
        s.append_chunk("x", 1).unwrap();
        s.complete(2).unwrap();
        s.reset();
        assert_eq!(s.phase, Phase::Idle);
        assert!(s.text.is_empty());
    }

    #[test]
    fn empty_error_rejected() {
        let mut s = StreamRenderState::new();
        s.start(0).unwrap();
        assert!(matches!(s.error("", 0).unwrap_err(), StreamError::EmptyError));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = StreamRenderState::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), StreamError::SchemaMismatch));
    }

    #[test]
    fn stream_serde_roundtrip() {
        let mut s = StreamRenderState::new();
        s.start(0).unwrap();
        s.append_chunk("hi", 10).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: StreamRenderState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
