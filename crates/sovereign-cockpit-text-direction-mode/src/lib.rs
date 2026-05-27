//! `sovereign-cockpit-text-direction-mode` — LTR/RTL state.
//!
//! Cockpit text direction can be `Ltr`, `Rtl`, or `Auto` (defer to
//! locale). `bind_locale(locale, direction)` records that a locale
//! tag (e.g. "ar", "he") implies a direction. `direction_for(
//! locale)` resolves the chosen mode + locale-binding table:
//!   * Mode::Ltr → Ltr.
//!   * Mode::Rtl → Rtl.
//!   * Mode::Auto → bound direction if locale is bound, else Ltr.
//!
//! `set_mode(mode)` is operator-explicit override; `is_rtl()` is a
//! convenience for the currently-effective direction given the
//! configured default locale.
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
    /// Left-to-right.
    Ltr,
    /// Right-to-left.
    Rtl,
    /// Defer to locale binding.
    Auto,
}

/// Direction.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Direction {
    /// Ltr.
    Ltr,
    /// Rtl.
    Rtl,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TextDirectionMode {
    /// Schema version.
    pub schema_version: String,
    /// Operator-configured mode.
    pub mode: Mode,
    /// Default locale tag.
    pub default_locale: String,
    /// locale → direction binding.
    pub locale_bindings: BTreeMap<String, Direction>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DirectionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty locale.
    #[error("locale empty")]
    EmptyLocale,
}

impl TextDirectionMode {
    /// New with default locale (use "en" if unsure).
    pub fn new(default_locale: &str) -> Result<Self, DirectionError> {
        if default_locale.is_empty() {
            return Err(DirectionError::EmptyLocale);
        }
        let mut s = Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: Mode::Auto,
            default_locale: default_locale.into(),
            locale_bindings: BTreeMap::new(),
        };
        // Seed with the standard RTL locales — operator may override
        // or extend.
        s.locale_bindings.insert("ar".into(), Direction::Rtl);
        s.locale_bindings.insert("fa".into(), Direction::Rtl);
        s.locale_bindings.insert("he".into(), Direction::Rtl);
        s.locale_bindings.insert("ur".into(), Direction::Rtl);
        Ok(s)
    }

    /// Bind locale → direction.
    pub fn bind_locale(
        &mut self,
        locale: &str,
        direction: Direction,
    ) -> Result<(), DirectionError> {
        if locale.is_empty() {
            return Err(DirectionError::EmptyLocale);
        }
        self.locale_bindings.insert(locale.into(), direction);
        Ok(())
    }

    /// Set explicit operator mode.
    pub fn set_mode(&mut self, mode: Mode) {
        self.mode = mode;
    }

    /// Set default locale.
    pub fn set_default_locale(&mut self, locale: &str) -> Result<(), DirectionError> {
        if locale.is_empty() {
            return Err(DirectionError::EmptyLocale);
        }
        self.default_locale = locale.into();
        Ok(())
    }

    /// Resolve direction for a specific locale.
    pub fn direction_for(&self, locale: &str) -> Direction {
        match self.mode {
            Mode::Ltr => Direction::Ltr,
            Mode::Rtl => Direction::Rtl,
            Mode::Auto => self
                .locale_bindings
                .get(locale)
                .copied()
                .unwrap_or(Direction::Ltr),
        }
    }

    /// Effective direction at the configured default locale.
    pub fn effective(&self) -> Direction {
        self.direction_for(&self.default_locale)
    }

    /// Convenience boolean.
    pub fn is_rtl(&self) -> bool {
        matches!(self.effective(), Direction::Rtl)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DirectionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DirectionError::SchemaMismatch);
        }
        if self.default_locale.is_empty() {
            return Err(DirectionError::EmptyLocale);
        }
        for k in self.locale_bindings.keys() {
            if k.is_empty() {
                return Err(DirectionError::EmptyLocale);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn auto_uses_locale_binding() {
        let s = TextDirectionMode::new("ar").unwrap();
        assert!(s.is_rtl());
        assert_eq!(s.direction_for("en"), Direction::Ltr);
    }

    #[test]
    fn ltr_override() {
        let mut s = TextDirectionMode::new("ar").unwrap();
        s.set_mode(Mode::Ltr);
        assert_eq!(s.effective(), Direction::Ltr);
    }

    #[test]
    fn rtl_override() {
        let mut s = TextDirectionMode::new("en").unwrap();
        s.set_mode(Mode::Rtl);
        assert_eq!(s.effective(), Direction::Rtl);
    }

    #[test]
    fn unknown_locale_defaults_ltr_in_auto() {
        let s = TextDirectionMode::new("xx").unwrap();
        assert_eq!(s.effective(), Direction::Ltr);
    }

    #[test]
    fn bind_locale_custom() {
        let mut s = TextDirectionMode::new("zz").unwrap();
        s.bind_locale("zz", Direction::Rtl).unwrap();
        assert!(s.is_rtl());
    }

    #[test]
    fn change_default_locale() {
        let mut s = TextDirectionMode::new("en").unwrap();
        assert!(!s.is_rtl());
        s.set_default_locale("he").unwrap();
        assert!(s.is_rtl());
    }

    #[test]
    fn seeded_rtl_locales_present() {
        let s = TextDirectionMode::new("en").unwrap();
        assert_eq!(s.direction_for("ar"), Direction::Rtl);
        assert_eq!(s.direction_for("he"), Direction::Rtl);
        assert_eq!(s.direction_for("fa"), Direction::Rtl);
        assert_eq!(s.direction_for("ur"), Direction::Rtl);
    }

    #[test]
    fn empty_locale_rejected() {
        let s = TextDirectionMode::new("");
        assert!(matches!(s.unwrap_err(), DirectionError::EmptyLocale));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = TextDirectionMode::new("en").unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            DirectionError::SchemaMismatch
        ));
    }

    #[test]
    fn direction_serde_roundtrip() {
        let mut s = TextDirectionMode::new("ar").unwrap();
        s.bind_locale("xx", Direction::Rtl).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: TextDirectionMode = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
