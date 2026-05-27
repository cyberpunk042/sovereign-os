//! `sovereign-cockpit-input-mode` — operator preferred input style.
//!
//! 4 modes (Mouse / KeyboardOnly / VimLike / Touch). The cockpit
//! may hide irrelevant affordances per mode.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 4 input modes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum InputMode {
    /// Mouse + keyboard (default).
    Mouse,
    /// Keyboard-only navigation.
    KeyboardOnly,
    /// Vim-like modal keybindings.
    VimLike,
    /// Touch-first.
    Touch,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct InputModeState {
    /// Schema version.
    pub schema_version: String,
    /// Current mode.
    pub mode: InputMode,
}

/// Errors.
#[derive(Debug, Error)]
pub enum InputModeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl InputMode {
    /// True if mode primarily uses pointer.
    pub fn uses_pointer(self) -> bool {
        matches!(self, InputMode::Mouse | InputMode::Touch)
    }

    /// True if mode is keyboard-dominant.
    pub fn keyboard_dominant(self) -> bool {
        matches!(self, InputMode::KeyboardOnly | InputMode::VimLike)
    }
}

impl InputModeState {
    /// Default — Mouse.
    pub fn default_state() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: InputMode::Mouse,
        }
    }

    /// Switch mode.
    pub fn switch(&mut self, m: InputMode) {
        self.mode = m;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), InputModeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(InputModeError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_mouse() {
        assert_eq!(InputModeState::default_state().mode, InputMode::Mouse);
    }

    #[test]
    fn mouse_uses_pointer() {
        assert!(InputMode::Mouse.uses_pointer());
        assert!(InputMode::Touch.uses_pointer());
        assert!(!InputMode::KeyboardOnly.uses_pointer());
        assert!(!InputMode::VimLike.uses_pointer());
    }

    #[test]
    fn keyboard_only_keyboard_dominant() {
        assert!(InputMode::KeyboardOnly.keyboard_dominant());
        assert!(InputMode::VimLike.keyboard_dominant());
        assert!(!InputMode::Mouse.keyboard_dominant());
    }

    #[test]
    fn switch_updates() {
        let mut s = InputModeState::default_state();
        s.switch(InputMode::VimLike);
        assert_eq!(s.mode, InputMode::VimLike);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = InputModeState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            InputModeError::SchemaMismatch
        ));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&InputMode::KeyboardOnly).unwrap(),
            "\"keyboard-only\""
        );
        assert_eq!(
            serde_json::to_string(&InputMode::VimLike).unwrap(),
            "\"vim-like\""
        );
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = InputModeState::default_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: InputModeState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
