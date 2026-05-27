//! `sovereign-cockpit-keyboard-layout` — keyboard-layout descriptor.
//!
//! Just a thin selector + label table for the settings UI. Actual
//! physical-key remap lives in the OS keyboard config; this crate
//! holds the operator's stated preference + provides the localized
//! display string.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Layout.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Layout {
    /// US QWERTY.
    Qwerty,
    /// UK QWERTY.
    QwertyUk,
    /// Dvorak.
    Dvorak,
    /// Colemak.
    Colemak,
    /// French AZERTY.
    Azerty,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeyboardLayout {
    /// Schema version.
    pub schema_version: String,
    /// Chosen layout.
    pub layout: Layout,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LayoutError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl KeyboardLayout {
    /// New.
    pub fn new(layout: Layout) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            layout,
        }
    }

    /// Set.
    pub fn set(&mut self, layout: Layout) {
        self.layout = layout;
    }

    /// Current.
    pub fn current(&self) -> Layout {
        self.layout
    }

    /// Operator-facing label.
    pub fn description(layout: Layout) -> &'static str {
        match layout {
            Layout::Qwerty => "QWERTY (US)",
            Layout::QwertyUk => "QWERTY (UK)",
            Layout::Dvorak => "Dvorak",
            Layout::Colemak => "Colemak",
            Layout::Azerty => "AZERTY (FR)",
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LayoutError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LayoutError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn set_and_current() {
        let mut k = KeyboardLayout::new(Layout::Qwerty);
        assert_eq!(k.current(), Layout::Qwerty);
        k.set(Layout::Dvorak);
        assert_eq!(k.current(), Layout::Dvorak);
    }

    #[test]
    fn description_covers_all() {
        for &l in &[
            Layout::Qwerty,
            Layout::QwertyUk,
            Layout::Dvorak,
            Layout::Colemak,
            Layout::Azerty,
        ] {
            assert!(!KeyboardLayout::description(l).is_empty());
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut k = KeyboardLayout::new(Layout::Qwerty);
        k.schema_version = "9.9.9".into();
        assert!(matches!(
            k.validate().unwrap_err(),
            LayoutError::SchemaMismatch
        ));
    }

    #[test]
    fn layout_serde_roundtrip() {
        let k = KeyboardLayout::new(Layout::Azerty);
        let j = serde_json::to_string(&k).unwrap();
        let back: KeyboardLayout = serde_json::from_str(&j).unwrap();
        assert_eq!(k, back);
    }
}
