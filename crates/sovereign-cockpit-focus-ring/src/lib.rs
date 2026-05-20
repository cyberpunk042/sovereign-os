//! `sovereign-cockpit-focus-ring` — `:focus-visible`-style ring tracker.
//!
//! The ring is visible if the most recent input source was keyboard,
//! and hidden as soon as a pointer (mouse/touch) event happens. The
//! visibility persists across focus transitions until a new pointer
//! event flips it off.
//!
//! Events:
//!   * `key()` — keyboard input observed.
//!   * `pointer()` — mouse/touch observed.
//!   * `focus_changed()` — focus moved (does not flip visibility).
//!   * `visible()` — current ring state.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Last input source.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum InputSource {
    /// Unknown (initial).
    Unknown,
    /// Keyboard.
    Keyboard,
    /// Pointer.
    Pointer,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FocusRing {
    /// Schema version.
    pub schema_version: String,
    /// Last source.
    pub last_source: InputSource,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RingError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl FocusRing {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            last_source: InputSource::Unknown,
        }
    }

    /// Keyboard event.
    pub fn key(&mut self) { self.last_source = InputSource::Keyboard; }

    /// Pointer event.
    pub fn pointer(&mut self) { self.last_source = InputSource::Pointer; }

    /// Focus transition — does NOT flip visibility.
    pub fn focus_changed(&mut self) { /* no-op intentional */ }

    /// Should the focus ring render?
    pub fn visible(&self) -> bool {
        matches!(self.last_source, InputSource::Keyboard)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RingError> {
        if self.schema_version != SCHEMA_VERSION { return Err(RingError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for FocusRing {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn initial_hidden() {
        let r = FocusRing::new();
        assert!(!r.visible());
    }

    #[test]
    fn key_shows() {
        let mut r = FocusRing::new();
        r.key();
        assert!(r.visible());
    }

    #[test]
    fn pointer_hides() {
        let mut r = FocusRing::new();
        r.key();
        r.pointer();
        assert!(!r.visible());
    }

    #[test]
    fn focus_change_preserves() {
        let mut r = FocusRing::new();
        r.key();
        r.focus_changed();
        assert!(r.visible());
    }

    #[test]
    fn pointer_then_key_shows() {
        let mut r = FocusRing::new();
        r.pointer();
        r.key();
        assert!(r.visible());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = FocusRing::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), RingError::SchemaMismatch));
    }

    #[test]
    fn ring_serde_roundtrip() {
        let mut r = FocusRing::new();
        r.key();
        let j = serde_json::to_string(&r).unwrap();
        let back: FocusRing = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
