//! `sovereign-cockpit-timezone-bar` — multi-timezone display.
//!
//! Zone{label, utc_offset_minutes}. add appends; offset must
//! be -720..=840 (UTC-12..UTC+14). local_hhmm(utc_minute_of_day)
//! returns (h, m) for that zone normalized to 24h.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Zone.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Zone {
    /// Label.
    pub label: String,
    /// UTC offset (-720..=840 minutes).
    pub utc_offset_minutes: i32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TimezoneBar {
    /// Schema version.
    pub schema_version: String,
    /// Zones.
    pub zones: Vec<Zone>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TzError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Bad offset.
    #[error("offset must be -720..=840 minutes")]
    BadOffset,
    /// Bad minute.
    #[error("minute_of_day must be 0..1440")]
    BadMinute,
    /// Duplicate.
    #[error("duplicate label: {0}")]
    DuplicateLabel(String),
}

impl TimezoneBar {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            zones: Vec::new(),
        }
    }

    /// Add zone.
    pub fn add(&mut self, label: &str, utc_offset_minutes: i32) -> Result<(), TzError> {
        if label.is_empty() {
            return Err(TzError::EmptyLabel);
        }
        if utc_offset_minutes < -720 || utc_offset_minutes > 840 {
            return Err(TzError::BadOffset);
        }
        if self.zones.iter().any(|z| z.label == label) {
            return Err(TzError::DuplicateLabel(label.into()));
        }
        self.zones.push(Zone {
            label: label.into(),
            utc_offset_minutes,
        });
        Ok(())
    }

    /// Remove by label.
    pub fn remove(&mut self, label: &str) -> bool {
        if let Some(pos) = self.zones.iter().position(|z| z.label == label) {
            self.zones.remove(pos);
            true
        } else {
            false
        }
    }

    /// Compute (hour, minute) for a zone given UTC minute-of-day.
    pub fn local_hhmm(
        &self,
        zone_idx: usize,
        utc_minute_of_day: u32,
    ) -> Result<(u32, u32), TzError> {
        if utc_minute_of_day >= 1440 {
            return Err(TzError::BadMinute);
        }
        let z = &self.zones[zone_idx];
        let total = (utc_minute_of_day as i32 + z.utc_offset_minutes).rem_euclid(1440);
        Ok(((total / 60) as u32, (total % 60) as u32))
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TzError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TzError::SchemaMismatch);
        }
        for z in &self.zones {
            if z.label.is_empty() {
                return Err(TzError::EmptyLabel);
            }
            if z.utc_offset_minutes < -720 || z.utc_offset_minutes > 840 {
                return Err(TzError::BadOffset);
            }
        }
        Ok(())
    }
}

impl Default for TimezoneBar {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_local_time() {
        let mut b = TimezoneBar::new();
        b.add("UTC", 0).unwrap();
        b.add("NYC", -300).unwrap(); // UTC-5
        b.add("Tokyo", 540).unwrap(); // UTC+9
        // 12:00 UTC → NYC 07:00 → Tokyo 21:00
        assert_eq!(b.local_hhmm(0, 720).unwrap(), (12, 0));
        assert_eq!(b.local_hhmm(1, 720).unwrap(), (7, 0));
        assert_eq!(b.local_hhmm(2, 720).unwrap(), (21, 0));
    }

    #[test]
    fn wrap_around_midnight() {
        let mut b = TimezoneBar::new();
        b.add("Tokyo", 540).unwrap();
        // 22:00 UTC → Tokyo 07:00 next day.
        assert_eq!(b.local_hhmm(0, 22 * 60).unwrap(), (7, 0));
    }

    #[test]
    fn wrap_around_into_previous_day() {
        let mut b = TimezoneBar::new();
        b.add("NYC", -300).unwrap();
        // 02:00 UTC → NYC 21:00 prev day.
        assert_eq!(b.local_hhmm(0, 2 * 60).unwrap(), (21, 0));
    }

    #[test]
    fn remove_drops() {
        let mut b = TimezoneBar::new();
        b.add("UTC", 0).unwrap();
        assert!(b.remove("UTC"));
        assert!(!b.remove("UTC"));
    }

    #[test]
    fn bad_inputs_rejected() {
        let mut b = TimezoneBar::new();
        assert!(matches!(b.add("", 0).unwrap_err(), TzError::EmptyLabel));
        assert!(matches!(b.add("X", -721).unwrap_err(), TzError::BadOffset));
        assert!(matches!(b.add("X", 841).unwrap_err(), TzError::BadOffset));
        b.add("UTC", 0).unwrap();
        assert!(matches!(
            b.add("UTC", 60).unwrap_err(),
            TzError::DuplicateLabel(_)
        ));
        assert!(matches!(
            b.local_hhmm(0, 1440).unwrap_err(),
            TzError::BadMinute
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = TimezoneBar::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(b.validate().unwrap_err(), TzError::SchemaMismatch));
    }

    #[test]
    fn bar_serde_roundtrip() {
        let mut b = TimezoneBar::new();
        b.add("UTC", 0).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: TimezoneBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
