//! `sovereign-cockpit-view-mode-toggle` — view mode per screen.
//!
//! `Mode { List, Grid, Card }`. Each screen id may have its own
//! preferred mode; unknown screens fall back to `default_mode`.
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
    /// List.
    List,
    /// Grid.
    Grid,
    /// Card.
    Card,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ViewModeToggle {
    /// Schema version.
    pub schema_version: String,
    /// Default mode.
    pub default_mode: Mode,
    /// screen → mode.
    pub by_screen: BTreeMap<String, Mode>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ToggleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("screen id empty")]
    EmptyScreen,
}

impl ViewModeToggle {
    /// New.
    pub fn new(default_mode: Mode) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            default_mode,
            by_screen: BTreeMap::new(),
        }
    }

    /// Set mode for screen.
    pub fn set(&mut self, screen: &str, mode: Mode) -> Result<(), ToggleError> {
        if screen.is_empty() { return Err(ToggleError::EmptyScreen); }
        self.by_screen.insert(screen.into(), mode);
        Ok(())
    }

    /// Clear screen's preference (revert to default).
    pub fn clear(&mut self, screen: &str) -> bool {
        self.by_screen.remove(screen).is_some()
    }

    /// Get effective mode for screen.
    pub fn mode_of(&self, screen: &str) -> Mode {
        self.by_screen.get(screen).copied().unwrap_or(self.default_mode)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ToggleError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ToggleError::SchemaMismatch); }
        for k in self.by_screen.keys() {
            if k.is_empty() { return Err(ToggleError::EmptyScreen); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_returned_for_unknown() {
        let t = ViewModeToggle::new(Mode::Grid);
        assert_eq!(t.mode_of("any"), Mode::Grid);
    }

    #[test]
    fn set_overrides() {
        let mut t = ViewModeToggle::new(Mode::Grid);
        t.set("inbox", Mode::List).unwrap();
        assert_eq!(t.mode_of("inbox"), Mode::List);
        assert_eq!(t.mode_of("other"), Mode::Grid);
    }

    #[test]
    fn clear_reverts() {
        let mut t = ViewModeToggle::new(Mode::Grid);
        t.set("inbox", Mode::Card).unwrap();
        assert!(t.clear("inbox"));
        assert_eq!(t.mode_of("inbox"), Mode::Grid);
    }

    #[test]
    fn empty_screen_rejected() {
        let mut t = ViewModeToggle::new(Mode::Grid);
        assert!(matches!(t.set("", Mode::List).unwrap_err(), ToggleError::EmptyScreen));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = ViewModeToggle::new(Mode::Grid);
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), ToggleError::SchemaMismatch));
    }

    #[test]
    fn toggle_serde_roundtrip() {
        let mut t = ViewModeToggle::new(Mode::Grid);
        t.set("inbox", Mode::List).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: ViewModeToggle = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
