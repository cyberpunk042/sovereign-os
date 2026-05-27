//! `sovereign-cockpit-color-mode` — resolve Light vs Dark.
//!
//! Inputs: `user_preference` (Light/Dark/Auto), `system_signal`
//! (LightSystem/DarkSystem/Unknown), and an optional per-context
//! `override`. `effective(context)` resolves them:
//!
//!   1. If a context override exists, use it (Light or Dark).
//!   2. Else if `user_preference` is Light/Dark, use it.
//!   3. Else (Auto): if `system_signal` is LightSystem/DarkSystem,
//!      use it; if Unknown, default to Light.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// User-stated preference.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum UserPreference {
    /// Light.
    Light,
    /// Dark.
    Dark,
    /// Auto.
    Auto,
}

/// Observed system signal.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SystemSignal {
    /// System says light.
    LightSystem,
    /// System says dark.
    DarkSystem,
    /// No signal.
    Unknown,
}

/// Resolved mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    /// Light.
    Light,
    /// Dark.
    Dark,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ColorMode {
    /// Schema version.
    pub schema_version: String,
    /// User preference.
    pub user_preference: UserPreference,
    /// System signal.
    pub system_signal: SystemSignal,
    /// Per-context overrides.
    pub overrides: BTreeMap<String, Mode>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ModeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty context.
    #[error("context empty")]
    EmptyContext,
}

impl ColorMode {
    /// New.
    pub fn new(user_preference: UserPreference, system_signal: SystemSignal) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            user_preference,
            system_signal,
            overrides: BTreeMap::new(),
        }
    }

    /// Set context override.
    pub fn set_override(&mut self, context: &str, mode: Mode) -> Result<(), ModeError> {
        if context.is_empty() {
            return Err(ModeError::EmptyContext);
        }
        self.overrides.insert(context.into(), mode);
        Ok(())
    }

    /// Clear context override.
    pub fn clear_override(&mut self, context: &str) -> bool {
        self.overrides.remove(context).is_some()
    }

    /// Effective mode for a context (use "" for the default context).
    pub fn effective(&self, context: &str) -> Mode {
        if let Some(&m) = self.overrides.get(context) {
            return m;
        }
        match self.user_preference {
            UserPreference::Light => Mode::Light,
            UserPreference::Dark => Mode::Dark,
            UserPreference::Auto => match self.system_signal {
                SystemSignal::LightSystem => Mode::Light,
                SystemSignal::DarkSystem => Mode::Dark,
                SystemSignal::Unknown => Mode::Light,
            },
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ModeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ModeError::SchemaMismatch);
        }
        for k in self.overrides.keys() {
            if k.is_empty() {
                return Err(ModeError::EmptyContext);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pref_light_wins() {
        let m = ColorMode::new(UserPreference::Light, SystemSignal::DarkSystem);
        assert_eq!(m.effective(""), Mode::Light);
    }

    #[test]
    fn pref_dark_wins() {
        let m = ColorMode::new(UserPreference::Dark, SystemSignal::LightSystem);
        assert_eq!(m.effective(""), Mode::Dark);
    }

    #[test]
    fn auto_follows_system_dark() {
        let m = ColorMode::new(UserPreference::Auto, SystemSignal::DarkSystem);
        assert_eq!(m.effective(""), Mode::Dark);
    }

    #[test]
    fn auto_follows_system_light() {
        let m = ColorMode::new(UserPreference::Auto, SystemSignal::LightSystem);
        assert_eq!(m.effective(""), Mode::Light);
    }

    #[test]
    fn auto_unknown_defaults_light() {
        let m = ColorMode::new(UserPreference::Auto, SystemSignal::Unknown);
        assert_eq!(m.effective(""), Mode::Light);
    }

    #[test]
    fn context_override_wins() {
        let mut m = ColorMode::new(UserPreference::Light, SystemSignal::LightSystem);
        m.set_override("docs", Mode::Dark).unwrap();
        assert_eq!(m.effective("docs"), Mode::Dark);
        assert_eq!(m.effective(""), Mode::Light);
    }

    #[test]
    fn clear_override() {
        let mut m = ColorMode::new(UserPreference::Light, SystemSignal::LightSystem);
        m.set_override("docs", Mode::Dark).unwrap();
        assert!(m.clear_override("docs"));
        assert_eq!(m.effective("docs"), Mode::Light);
    }

    #[test]
    fn empty_context_rejected() {
        let mut m = ColorMode::new(UserPreference::Light, SystemSignal::LightSystem);
        assert!(matches!(
            m.set_override("", Mode::Dark).unwrap_err(),
            ModeError::EmptyContext
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = ColorMode::new(UserPreference::Light, SystemSignal::LightSystem);
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            ModeError::SchemaMismatch
        ));
    }

    #[test]
    fn mode_serde_roundtrip() {
        let mut m = ColorMode::new(UserPreference::Auto, SystemSignal::DarkSystem);
        m.set_override("editor", Mode::Light).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: ColorMode = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
