//! `sovereign-cockpit-shortcut-recorder` — chord capture state machine.
//!
//! `arm()` opens recording; `record(mods, key)` finalizes the chord
//! if it has a non-modifier key and is not the literal Escape
//! (reserved for cancel); `cancel()` drops without finalizing.
//! `last_captured()` returns the most-recent capture; `clear()`
//! drops it.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Modifiers.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Modifiers {
    /// Ctrl.
    pub ctrl: bool,
    /// Alt.
    pub alt: bool,
    /// Shift.
    pub shift: bool,
    /// Meta.
    pub meta: bool,
}

impl Modifiers {
    /// True if no modifier set.
    pub fn is_empty(&self) -> bool {
        !self.ctrl && !self.alt && !self.shift && !self.meta
    }
}

/// Captured chord.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Captured {
    /// Modifiers.
    pub modifiers: Modifiers,
    /// Non-modifier key name (e.g. "P", "ArrowLeft", "Enter").
    pub key: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ShortcutRecorder {
    /// Schema version.
    pub schema_version: String,
    /// Currently recording.
    pub armed: bool,
    /// Last captured.
    pub last: Option<Captured>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RecorderError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Not armed.
    #[error("recorder not armed")]
    NotArmed,
    /// Key is a bare modifier.
    #[error("bare modifier captured: {0}")]
    BareModifier(String),
    /// Escape reserved.
    #[error("Escape key is reserved for cancel")]
    EscapeReserved,
    /// Empty key.
    #[error("key empty")]
    EmptyKey,
}

impl ShortcutRecorder {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            armed: false,
            last: None,
        }
    }

    /// Arm.
    pub fn arm(&mut self) {
        self.armed = true;
    }

    /// Cancel.
    pub fn cancel(&mut self) {
        self.armed = false;
    }

    /// Record.
    pub fn record(&mut self, modifiers: Modifiers, key: &str) -> Result<Captured, RecorderError> {
        if !self.armed {
            return Err(RecorderError::NotArmed);
        }
        if key.is_empty() {
            return Err(RecorderError::EmptyKey);
        }
        if key.eq_ignore_ascii_case("Escape") || key.eq_ignore_ascii_case("Esc") {
            return Err(RecorderError::EscapeReserved);
        }
        // Detect bare-modifier keys (caller sent the modifier name as the key).
        let lower = key.to_ascii_lowercase();
        if matches!(
            lower.as_str(),
            "control" | "ctrl" | "alt" | "shift" | "meta" | "super" | "cmd" | "win"
        ) {
            return Err(RecorderError::BareModifier(key.into()));
        }
        let cap = Captured {
            modifiers,
            key: key.into(),
        };
        self.last = Some(cap.clone());
        self.armed = false;
        Ok(cap)
    }

    /// Last captured.
    pub fn last_captured(&self) -> Option<&Captured> {
        self.last.as_ref()
    }

    /// Clear last.
    pub fn clear(&mut self) {
        self.last = None;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RecorderError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RecorderError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for ShortcutRecorder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ctrl() -> Modifiers {
        Modifiers {
            ctrl: true,
            ..Default::default()
        }
    }

    #[test]
    fn not_armed_rejects() {
        let mut r = ShortcutRecorder::new();
        assert!(matches!(
            r.record(ctrl(), "P").unwrap_err(),
            RecorderError::NotArmed
        ));
    }

    #[test]
    fn arm_then_record_captures() {
        let mut r = ShortcutRecorder::new();
        r.arm();
        let c = r.record(ctrl(), "P").unwrap();
        assert_eq!(c.key, "P");
        assert!(c.modifiers.ctrl);
        assert!(!r.armed);
        assert_eq!(r.last_captured().unwrap().key, "P");
    }

    #[test]
    fn escape_reserved() {
        let mut r = ShortcutRecorder::new();
        r.arm();
        assert!(matches!(
            r.record(Modifiers::default(), "Escape").unwrap_err(),
            RecorderError::EscapeReserved
        ));
    }

    #[test]
    fn bare_modifier_rejected() {
        let mut r = ShortcutRecorder::new();
        r.arm();
        assert!(matches!(
            r.record(ctrl(), "Control").unwrap_err(),
            RecorderError::BareModifier(_)
        ));
    }

    #[test]
    fn empty_key_rejected() {
        let mut r = ShortcutRecorder::new();
        r.arm();
        assert!(matches!(
            r.record(ctrl(), "").unwrap_err(),
            RecorderError::EmptyKey
        ));
    }

    #[test]
    fn cancel_drops_armed() {
        let mut r = ShortcutRecorder::new();
        r.arm();
        r.cancel();
        assert!(!r.armed);
    }

    #[test]
    fn clear_drops_last() {
        let mut r = ShortcutRecorder::new();
        r.arm();
        r.record(ctrl(), "P").unwrap();
        r.clear();
        assert!(r.last.is_none());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = ShortcutRecorder::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            RecorderError::SchemaMismatch
        ));
    }

    #[test]
    fn recorder_serde_roundtrip() {
        let mut r = ShortcutRecorder::new();
        r.arm();
        r.record(ctrl(), "P").unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: ShortcutRecorder = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
