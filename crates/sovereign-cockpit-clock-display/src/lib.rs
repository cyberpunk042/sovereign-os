//! `sovereign-cockpit-clock-display` — operator clock preferences.
//!
//! 4 toggles: hour_24 (vs 12h), show_seconds, show_weekday, monospace.
//! Pure UX.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Clock preferences.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClockPreferences {
    /// Schema version.
    pub schema_version: String,
    /// 24-hour clock.
    pub hour_24: bool,
    /// Show seconds.
    pub show_seconds: bool,
    /// Show weekday name (Mon..Sun).
    pub show_weekday: bool,
    /// Use monospace digits.
    pub monospace: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ClockError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl ClockPreferences {
    /// Default — 24h, no seconds, weekday shown, monospace.
    pub fn default_prefs() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            hour_24: true,
            show_seconds: false,
            show_weekday: true,
            monospace: true,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ClockError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ClockError::SchemaMismatch);
        }
        Ok(())
    }

    /// Render an "h:m" string (or "h:m:s") given inputs.
    ///
    /// `hour_24h_input`: hour 0..=23
    /// `minute`: 0..=59
    /// `second`: 0..=59
    /// `weekday`: 0..=6 (0=Mon)
    pub fn render(&self, hour_24h_input: u8, minute: u8, second: u8, weekday: u8) -> String {
        let weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        let (h_display, suffix) = if self.hour_24 {
            (hour_24h_input as u16, "")
        } else {
            let h12 = match hour_24h_input {
                0 => 12,
                1..=12 => hour_24h_input,
                _ => hour_24h_input - 12,
            };
            (h12 as u16, if hour_24h_input < 12 { " AM" } else { " PM" })
        };
        let time = if self.show_seconds {
            format!("{h_display:02}:{minute:02}:{second:02}{suffix}")
        } else {
            format!("{h_display:02}:{minute:02}{suffix}")
        };
        if self.show_weekday {
            let wd = weekdays.get(weekday as usize).copied().unwrap_or("?");
            format!("{wd} {time}")
        } else {
            time
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates() {
        ClockPreferences::default_prefs().validate().unwrap();
    }

    #[test]
    fn render_24h_no_seconds() {
        let p = ClockPreferences::default_prefs();
        let s = p.render(14, 30, 45, 2);
        assert_eq!(s, "Wed 14:30");
    }

    #[test]
    fn render_24h_with_seconds() {
        let mut p = ClockPreferences::default_prefs();
        p.show_seconds = true;
        let s = p.render(9, 5, 7, 0);
        assert_eq!(s, "Mon 09:05:07");
    }

    #[test]
    fn render_12h_am() {
        let mut p = ClockPreferences::default_prefs();
        p.hour_24 = false;
        let s = p.render(9, 5, 0, 0);
        assert_eq!(s, "Mon 09:05 AM");
    }

    #[test]
    fn render_12h_pm() {
        let mut p = ClockPreferences::default_prefs();
        p.hour_24 = false;
        let s = p.render(14, 30, 0, 2);
        assert_eq!(s, "Wed 02:30 PM");
    }

    #[test]
    fn render_12h_midnight() {
        let mut p = ClockPreferences::default_prefs();
        p.hour_24 = false;
        let s = p.render(0, 0, 0, 0);
        assert_eq!(s, "Mon 12:00 AM");
    }

    #[test]
    fn render_12h_noon() {
        let mut p = ClockPreferences::default_prefs();
        p.hour_24 = false;
        let s = p.render(12, 0, 0, 0);
        assert_eq!(s, "Mon 12:00 PM");
    }

    #[test]
    fn render_no_weekday() {
        let mut p = ClockPreferences::default_prefs();
        p.show_weekday = false;
        let s = p.render(14, 30, 0, 2);
        assert_eq!(s, "14:30");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ClockPreferences::default_prefs();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), ClockError::SchemaMismatch));
    }

    #[test]
    fn preferences_serde_roundtrip() {
        let p = ClockPreferences::default_prefs();
        let j = serde_json::to_string(&p).unwrap();
        let back: ClockPreferences = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
