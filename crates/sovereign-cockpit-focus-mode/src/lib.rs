//! `sovereign-cockpit-focus-mode` — distraction-free workspace.
//!
//! Mode{Off/Focus/Presentation}. Off shows everything. Focus
//! hides chrome (widgets not in allow list) — visible(widget)
//! returns true iff widget is in allow OR allow is empty
//! (treated as "no constraint"). Presentation hides everything
//! except `presentation_widget`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Mode.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Off.
    Off,
    /// Focus (allowlist-only).
    Focus,
    /// Presentation (single widget).
    Presentation,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FocusMode {
    /// Schema version.
    pub schema_version: String,
    /// Mode.
    pub mode: Mode,
    /// Allowlist (used in Focus).
    pub allow: BTreeSet<String>,
    /// Presentation widget id.
    pub presentation_widget: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FocusError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty widget.
    #[error("widget id empty")]
    EmptyWidget,
}

impl FocusMode {
    /// New (Off).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: Mode::Off,
            allow: BTreeSet::new(),
            presentation_widget: None,
        }
    }

    /// Add widget to allow list.
    pub fn allow_add(&mut self, widget: &str) -> Result<(), FocusError> {
        if widget.is_empty() { return Err(FocusError::EmptyWidget); }
        self.allow.insert(widget.into());
        Ok(())
    }

    /// Remove from allowlist.
    pub fn allow_remove(&mut self, widget: &str) -> bool {
        self.allow.remove(widget)
    }

    /// Set mode.
    pub fn set_mode(&mut self, mode: Mode) {
        self.mode = mode;
    }

    /// Set presentation widget.
    pub fn set_presentation_widget(&mut self, widget: &str) -> Result<(), FocusError> {
        if widget.is_empty() { return Err(FocusError::EmptyWidget); }
        self.presentation_widget = Some(widget.into());
        Ok(())
    }

    /// Is widget currently visible?
    pub fn visible(&self, widget: &str) -> bool {
        match self.mode {
            Mode::Off => true,
            Mode::Focus => {
                if self.allow.is_empty() { true }
                else { self.allow.contains(widget) }
            }
            Mode::Presentation => {
                self.presentation_widget.as_deref() == Some(widget)
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FocusError> {
        if self.schema_version != SCHEMA_VERSION { return Err(FocusError::SchemaMismatch); }
        for w in &self.allow {
            if w.is_empty() { return Err(FocusError::EmptyWidget); }
        }
        Ok(())
    }
}

impl Default for FocusMode {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn off_shows_all() {
        let f = FocusMode::new();
        assert!(f.visible("anything"));
    }

    #[test]
    fn focus_with_empty_allow_shows_all() {
        let mut f = FocusMode::new();
        f.set_mode(Mode::Focus);
        assert!(f.visible("anything"));
    }

    #[test]
    fn focus_with_allowlist() {
        let mut f = FocusMode::new();
        f.set_mode(Mode::Focus);
        f.allow_add("editor").unwrap();
        f.allow_add("status-bar").unwrap();
        assert!(f.visible("editor"));
        assert!(!f.visible("sidebar"));
    }

    #[test]
    fn presentation_shows_only_target() {
        let mut f = FocusMode::new();
        f.set_mode(Mode::Presentation);
        f.set_presentation_widget("slide").unwrap();
        assert!(f.visible("slide"));
        assert!(!f.visible("anything-else"));
    }

    #[test]
    fn allow_remove_works() {
        let mut f = FocusMode::new();
        f.allow_add("x").unwrap();
        assert!(f.allow_remove("x"));
        assert!(!f.allow_remove("x"));
    }

    #[test]
    fn empty_widget_rejected() {
        let mut f = FocusMode::new();
        assert!(matches!(f.allow_add("").unwrap_err(), FocusError::EmptyWidget));
        assert!(matches!(f.set_presentation_widget("").unwrap_err(), FocusError::EmptyWidget));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = FocusMode::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), FocusError::SchemaMismatch));
    }

    #[test]
    fn focus_serde_roundtrip() {
        let mut f = FocusMode::new();
        f.set_mode(Mode::Focus);
        f.allow_add("editor").unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: FocusMode = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
