//! `sovereign-cockpit-color-blind-mode` — accessibility palette adjustments.
//!
//! 4 modes: None / Protanopia / Deuteranopia / Tritanopia. Each remaps
//! the cockpit's semantic color tokens (success / warning / danger /
//! info) to color-blind-safe alternatives.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Color-blind mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ColorBlindMode {
    /// No remapping.
    None,
    /// Protanopia (red-blind).
    Protanopia,
    /// Deuteranopia (green-blind).
    Deuteranopia,
    /// Tritanopia (blue-blind).
    Tritanopia,
}

/// 4-color semantic palette (hex, no `#`).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SemanticPalette {
    /// Success.
    pub success: String,
    /// Warning.
    pub warning: String,
    /// Danger.
    pub danger: String,
    /// Info.
    pub info: String,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColorBlindState {
    /// Schema version.
    pub schema_version: String,
    /// Mode.
    pub mode: ColorBlindMode,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ColorBlindError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl ColorBlindMode {
    /// All 4.
    pub const ALL: [ColorBlindMode; 4] = [
        ColorBlindMode::None, ColorBlindMode::Protanopia,
        ColorBlindMode::Deuteranopia, ColorBlindMode::Tritanopia,
    ];

    /// Semantic palette for this mode.
    pub fn palette(self) -> SemanticPalette {
        match self {
            ColorBlindMode::None => SemanticPalette {
                success: "16a34a".into(), warning: "f59e0b".into(),
                danger: "dc2626".into(),  info: "2563eb".into(),
            },
            ColorBlindMode::Protanopia => SemanticPalette {
                // Avoid red-green pairs; use yellow + blue.
                success: "60a5fa".into(), warning: "facc15".into(),
                danger: "1e40af".into(),  info: "78716c".into(),
            },
            ColorBlindMode::Deuteranopia => SemanticPalette {
                // Similar to protanopia but slightly cooler.
                success: "38bdf8".into(), warning: "fde047".into(),
                danger: "1e3a8a".into(),  info: "525252".into(),
            },
            ColorBlindMode::Tritanopia => SemanticPalette {
                // Avoid blue-yellow pairs; use red + green.
                success: "16a34a".into(), warning: "ea580c".into(),
                danger: "dc2626".into(),  info: "a3a3a3".into(),
            },
        }
    }
}

impl ColorBlindState {
    /// Default (no remapping).
    pub fn default_state() -> Self {
        Self { schema_version: SCHEMA_VERSION.into(), mode: ColorBlindMode::None }
    }

    /// Switch.
    pub fn switch(&mut self, mode: ColorBlindMode) { self.mode = mode; }

    /// Resolved palette.
    pub fn palette(&self) -> SemanticPalette { self.mode.palette() }

    /// Validate.
    pub fn validate(&self) -> Result<(), ColorBlindError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ColorBlindError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_none() {
        assert_eq!(ColorBlindState::default_state().mode, ColorBlindMode::None);
    }

    #[test]
    fn all_modes_yield_palettes() {
        for m in ColorBlindMode::ALL {
            let p = m.palette();
            assert_eq!(p.success.len(), 6);
            assert_eq!(p.warning.len(), 6);
            assert_eq!(p.danger.len(), 6);
            assert_eq!(p.info.len(), 6);
        }
    }

    #[test]
    fn switch_updates() {
        let mut s = ColorBlindState::default_state();
        s.switch(ColorBlindMode::Protanopia);
        assert_eq!(s.mode, ColorBlindMode::Protanopia);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ColorBlindState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), ColorBlindError::SchemaMismatch));
    }

    #[test]
    fn mode_serde_kebab() {
        assert_eq!(serde_json::to_string(&ColorBlindMode::Protanopia).unwrap(), "\"protanopia\"");
        assert_eq!(serde_json::to_string(&ColorBlindMode::Deuteranopia).unwrap(), "\"deuteranopia\"");
        assert_eq!(serde_json::to_string(&ColorBlindMode::Tritanopia).unwrap(), "\"tritanopia\"");
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = ColorBlindState::default_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: ColorBlindState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
