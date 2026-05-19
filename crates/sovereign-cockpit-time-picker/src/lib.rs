//! `sovereign-cockpit-time-picker` — time-of-day picker.
//!
//! Hour [0..24) + minute [0..60) with operator-configured step
//! (1/5/15/30) and 12h/24h display. step_up/step_down navigate
//! by step, carrying minute → hour with wrap-around at 24h. Pure
//! UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Display style.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DisplayStyle {
    /// 12-hour with AM/PM suffix.
    H12,
    /// 24-hour zero-padded.
    H24,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TimePicker {
    /// Schema version.
    pub schema_version: String,
    /// Current hour [0..24).
    pub hour: u8,
    /// Current minute [0..60).
    pub minute: u8,
    /// Step minute (1, 5, 15, 30).
    pub step_minutes: u8,
    /// Display style.
    pub style: DisplayStyle,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TimePickerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad hour.
    #[error("hour {0} out of [0,24)")]
    BadHour(u8),
    /// Bad minute.
    #[error("minute {0} out of [0,60)")]
    BadMinute(u8),
    /// Bad step.
    #[error("step_minutes {0} not in {{1,5,15,30}}")]
    BadStep(u8),
}

impl TimePicker {
    /// New picker.
    pub fn new(hour: u8, minute: u8, step_minutes: u8, style: DisplayStyle) -> Result<Self, TimePickerError> {
        if hour >= 24 { return Err(TimePickerError::BadHour(hour)); }
        if minute >= 60 { return Err(TimePickerError::BadMinute(minute)); }
        if !matches!(step_minutes, 1 | 5 | 15 | 30) {
            return Err(TimePickerError::BadStep(step_minutes));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            hour,
            minute,
            step_minutes,
            style,
        })
    }

    /// Step minute up by step. Carries to hour. Wraps 24h.
    pub fn step_up(&mut self) {
        let total = self.hour as u16 * 60 + self.minute as u16 + self.step_minutes as u16;
        self.set_total(total);
    }

    /// Step minute down by step. Carries to hour. Wraps to 23:55 from 00:00.
    pub fn step_down(&mut self) {
        let cur = self.hour as i32 * 60 + self.minute as i32;
        let step = self.step_minutes as i32;
        let new = ((cur - step).rem_euclid(24 * 60)) as u16;
        self.set_total(new);
    }

    fn set_total(&mut self, total: u16) {
        let t = total % (24 * 60);
        self.hour = (t / 60) as u8;
        self.minute = (t % 60) as u8;
    }

    /// Total minutes since midnight.
    pub fn total_minutes(&self) -> u16 {
        self.hour as u16 * 60 + self.minute as u16
    }

    /// Format per display style.
    pub fn display(&self) -> String {
        match self.style {
            DisplayStyle::H24 => format!("{:02}:{:02}", self.hour, self.minute),
            DisplayStyle::H12 => {
                let suffix = if self.hour < 12 { "AM" } else { "PM" };
                let h12 = match self.hour % 12 {
                    0 => 12,
                    n => n,
                };
                format!("{}:{:02} {}", h12, self.minute, suffix)
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TimePickerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TimePickerError::SchemaMismatch);
        }
        if self.hour >= 24 { return Err(TimePickerError::BadHour(self.hour)); }
        if self.minute >= 60 { return Err(TimePickerError::BadMinute(self.minute)); }
        if !matches!(self.step_minutes, 1 | 5 | 15 | 30) {
            return Err(TimePickerError::BadStep(self.step_minutes));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_bad_hour_rejected() {
        assert!(matches!(TimePicker::new(24, 0, 1, DisplayStyle::H24).unwrap_err(), TimePickerError::BadHour(24)));
    }

    #[test]
    fn new_bad_minute_rejected() {
        assert!(matches!(TimePicker::new(0, 60, 1, DisplayStyle::H24).unwrap_err(), TimePickerError::BadMinute(60)));
    }

    #[test]
    fn new_bad_step_rejected() {
        assert!(matches!(TimePicker::new(0, 0, 7, DisplayStyle::H24).unwrap_err(), TimePickerError::BadStep(7)));
    }

    #[test]
    fn step_up_basic() {
        let mut t = TimePicker::new(10, 30, 5, DisplayStyle::H24).unwrap();
        t.step_up();
        assert_eq!(t.minute, 35);
        assert_eq!(t.hour, 10);
    }

    #[test]
    fn step_up_carries_to_hour() {
        let mut t = TimePicker::new(10, 55, 15, DisplayStyle::H24).unwrap();
        t.step_up();
        assert_eq!(t.hour, 11);
        assert_eq!(t.minute, 10);
    }

    #[test]
    fn step_up_wraps_at_midnight() {
        let mut t = TimePicker::new(23, 45, 30, DisplayStyle::H24).unwrap();
        t.step_up();
        assert_eq!(t.hour, 0);
        assert_eq!(t.minute, 15);
    }

    #[test]
    fn step_down_carries() {
        let mut t = TimePicker::new(10, 5, 15, DisplayStyle::H24).unwrap();
        t.step_down();
        assert_eq!(t.hour, 9);
        assert_eq!(t.minute, 50);
    }

    #[test]
    fn step_down_wraps_from_midnight() {
        let mut t = TimePicker::new(0, 0, 15, DisplayStyle::H24).unwrap();
        t.step_down();
        assert_eq!(t.hour, 23);
        assert_eq!(t.minute, 45);
    }

    #[test]
    fn total_minutes() {
        let t = TimePicker::new(10, 30, 5, DisplayStyle::H24).unwrap();
        assert_eq!(t.total_minutes(), 630);
    }

    #[test]
    fn display_h24_padded() {
        let t = TimePicker::new(5, 3, 5, DisplayStyle::H24).unwrap();
        assert_eq!(t.display(), "05:03");
    }

    #[test]
    fn display_h12_am_pm() {
        assert_eq!(TimePicker::new(0, 0, 5, DisplayStyle::H12).unwrap().display(), "12:00 AM");
        assert_eq!(TimePicker::new(12, 30, 5, DisplayStyle::H12).unwrap().display(), "12:30 PM");
        assert_eq!(TimePicker::new(13, 45, 5, DisplayStyle::H12).unwrap().display(), "1:45 PM");
        assert_eq!(TimePicker::new(9, 5, 5, DisplayStyle::H12).unwrap().display(), "9:05 AM");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TimePicker::new(10, 0, 5, DisplayStyle::H24).unwrap();
        t.schema_version = "9.9.9".into();
        assert!(matches!(t.validate().unwrap_err(), TimePickerError::SchemaMismatch));
    }

    #[test]
    fn style_serde_kebab() {
        assert_eq!(serde_json::to_string(&DisplayStyle::H12).unwrap(), "\"h12\"");
        assert_eq!(serde_json::to_string(&DisplayStyle::H24).unwrap(), "\"h24\"");
    }

    #[test]
    fn picker_serde_roundtrip() {
        let t = TimePicker::new(10, 30, 5, DisplayStyle::H24).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: TimePicker = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
