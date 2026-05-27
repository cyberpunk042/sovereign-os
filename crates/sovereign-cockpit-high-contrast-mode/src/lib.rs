//! `sovereign-cockpit-high-contrast-mode` — a11y high-contrast.
//!
//! Mode{Off/On}. add_override(class, fg, bg) registers a class-
//! level color pair. resolve(class) returns the override iff
//! Mode::On, else None. set_mode flips. Pure data; no rendering.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Mode.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Off (use theme colors).
    Off,
    /// On (use overrides).
    On,
}

/// Color pair.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pair {
    /// Foreground.
    pub fg: String,
    /// Background.
    pub bg: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HighContrastMode {
    /// Schema version.
    pub schema_version: String,
    /// Mode.
    pub mode: Mode,
    /// class → pair.
    pub overrides: BTreeMap<String, Pair>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ContrastError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("class empty")]
    EmptyClass,
    /// Empty.
    #[error("color empty")]
    EmptyColor,
}

impl HighContrastMode {
    /// New (Off).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: Mode::Off,
            overrides: BTreeMap::new(),
        }
    }

    /// Set mode.
    pub fn set_mode(&mut self, mode: Mode) {
        self.mode = mode;
    }

    /// Add or replace override.
    pub fn add_override(&mut self, class: &str, fg: &str, bg: &str) -> Result<(), ContrastError> {
        if class.is_empty() {
            return Err(ContrastError::EmptyClass);
        }
        if fg.is_empty() || bg.is_empty() {
            return Err(ContrastError::EmptyColor);
        }
        self.overrides.insert(
            class.into(),
            Pair {
                fg: fg.into(),
                bg: bg.into(),
            },
        );
        Ok(())
    }

    /// Remove override.
    pub fn remove_override(&mut self, class: &str) -> bool {
        self.overrides.remove(class).is_some()
    }

    /// Resolve color pair for a class (None when Off or class not overridden).
    pub fn resolve(&self, class: &str) -> Option<&Pair> {
        if self.mode == Mode::Off {
            return None;
        }
        self.overrides.get(class)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ContrastError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ContrastError::SchemaMismatch);
        }
        for (k, p) in &self.overrides {
            if k.is_empty() {
                return Err(ContrastError::EmptyClass);
            }
            if p.fg.is_empty() || p.bg.is_empty() {
                return Err(ContrastError::EmptyColor);
            }
        }
        Ok(())
    }
}

impl Default for HighContrastMode {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn off_returns_none() {
        let mut h = HighContrastMode::new();
        h.add_override("text", "#fff", "#000").unwrap();
        assert!(h.resolve("text").is_none());
    }

    #[test]
    fn on_returns_override() {
        let mut h = HighContrastMode::new();
        h.add_override("text", "#fff", "#000").unwrap();
        h.set_mode(Mode::On);
        let p = h.resolve("text").unwrap();
        assert_eq!(p.fg, "#fff");
        assert_eq!(p.bg, "#000");
    }

    #[test]
    fn on_returns_none_for_unknown_class() {
        let mut h = HighContrastMode::new();
        h.set_mode(Mode::On);
        assert!(h.resolve("text").is_none());
    }

    #[test]
    fn remove_override_works() {
        let mut h = HighContrastMode::new();
        h.add_override("text", "#fff", "#000").unwrap();
        assert!(h.remove_override("text"));
        assert!(!h.remove_override("text"));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut h = HighContrastMode::new();
        assert!(matches!(
            h.add_override("", "#fff", "#000").unwrap_err(),
            ContrastError::EmptyClass
        ));
        assert!(matches!(
            h.add_override("c", "", "#000").unwrap_err(),
            ContrastError::EmptyColor
        ));
        assert!(matches!(
            h.add_override("c", "#fff", "").unwrap_err(),
            ContrastError::EmptyColor
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = HighContrastMode::new();
        h.schema_version = "9.9.9".into();
        assert!(matches!(
            h.validate().unwrap_err(),
            ContrastError::SchemaMismatch
        ));
    }

    #[test]
    fn mode_serde_roundtrip() {
        let mut h = HighContrastMode::new();
        h.set_mode(Mode::On);
        h.add_override("text", "#fff", "#000").unwrap();
        let j = serde_json::to_string(&h).unwrap();
        let back: HighContrastMode = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
