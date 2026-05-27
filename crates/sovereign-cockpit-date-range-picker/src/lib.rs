//! `sovereign-cockpit-date-range-picker` — bounded date range.
//!
//! State holds `from_ms` and `to_ms` plus a preset registry like
//! "last-7-days" with a `days_back` count. Presets can be applied
//! with `apply_preset(name, now_ms)` which sets to_ms = now and
//! from_ms = now - days_back × DAY_MS.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Day in ms.
pub const DAY_MS: u64 = 86_400_000;

/// One preset.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Preset {
    /// Days back from now.
    pub days_back: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DateRangePicker {
    /// Schema version.
    pub schema_version: String,
    /// Range start.
    pub from_ms: u64,
    /// Range end (exclusive).
    pub to_ms: u64,
    /// Named presets.
    pub presets: BTreeMap<String, Preset>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PickerError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("name empty")]
    EmptyName,
    /// Inverted.
    #[error("from ({from}) >= to ({to})")]
    Inverted {
        /// from.
        from: u64,
        /// to.
        to: u64,
    },
    /// Unknown preset.
    #[error("unknown preset: {0}")]
    UnknownPreset(String),
}

impl DateRangePicker {
    /// New with presets (last-7/30/90).
    pub fn new() -> Self {
        let mut presets = BTreeMap::new();
        presets.insert("last-7-days".into(), Preset { days_back: 7 });
        presets.insert("last-30-days".into(), Preset { days_back: 30 });
        presets.insert("last-90-days".into(), Preset { days_back: 90 });
        Self {
            schema_version: SCHEMA_VERSION.into(),
            from_ms: 0,
            to_ms: 0,
            presets,
        }
    }

    /// Set range directly.
    pub fn set_range(&mut self, from_ms: u64, to_ms: u64) -> Result<(), PickerError> {
        if from_ms >= to_ms {
            return Err(PickerError::Inverted {
                from: from_ms,
                to: to_ms,
            });
        }
        self.from_ms = from_ms;
        self.to_ms = to_ms;
        Ok(())
    }

    /// Register a preset.
    pub fn register_preset(&mut self, name: &str, days_back: u32) -> Result<(), PickerError> {
        if name.is_empty() {
            return Err(PickerError::EmptyName);
        }
        self.presets.insert(name.into(), Preset { days_back });
        Ok(())
    }

    /// Apply preset given `now_ms`.
    pub fn apply_preset(&mut self, name: &str, now_ms: u64) -> Result<(), PickerError> {
        let p = self
            .presets
            .get(name)
            .ok_or_else(|| PickerError::UnknownPreset(name.into()))?;
        let to = now_ms;
        let from = now_ms.saturating_sub((p.days_back as u64).saturating_mul(DAY_MS));
        self.from_ms = from;
        self.to_ms = to;
        Ok(())
    }

    /// Width in days (floor).
    pub fn width_days(&self) -> u64 {
        self.to_ms.saturating_sub(self.from_ms) / DAY_MS
    }

    /// Width in ms.
    pub fn width_ms(&self) -> u64 {
        self.to_ms.saturating_sub(self.from_ms)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PickerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PickerError::SchemaMismatch);
        }
        if self.from_ms >= self.to_ms && (self.from_ms != 0 || self.to_ms != 0) {
            return Err(PickerError::Inverted {
                from: self.from_ms,
                to: self.to_ms,
            });
        }
        for k in self.presets.keys() {
            if k.is_empty() {
                return Err(PickerError::EmptyName);
            }
        }
        Ok(())
    }
}

impl Default for DateRangePicker {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn set_range() {
        let mut p = DateRangePicker::new();
        p.set_range(100, 200).unwrap();
        assert_eq!(p.from_ms, 100);
        assert_eq!(p.to_ms, 200);
    }

    #[test]
    fn apply_preset_seven_days() {
        let mut p = DateRangePicker::new();
        let now = 100 * DAY_MS;
        p.apply_preset("last-7-days", now).unwrap();
        assert_eq!(p.to_ms, now);
        assert_eq!(p.from_ms, now - 7 * DAY_MS);
        assert_eq!(p.width_days(), 7);
    }

    #[test]
    fn custom_preset_works() {
        let mut p = DateRangePicker::new();
        p.register_preset("last-1-day", 1).unwrap();
        p.apply_preset("last-1-day", DAY_MS).unwrap();
        assert_eq!(p.from_ms, 0);
        assert_eq!(p.to_ms, DAY_MS);
    }

    #[test]
    fn unknown_preset_rejected() {
        let mut p = DateRangePicker::new();
        assert!(matches!(
            p.apply_preset("nope", 0).unwrap_err(),
            PickerError::UnknownPreset(_)
        ));
    }

    #[test]
    fn inverted_range_rejected() {
        let mut p = DateRangePicker::new();
        assert!(matches!(
            p.set_range(200, 100).unwrap_err(),
            PickerError::Inverted { .. }
        ));
        assert!(matches!(
            p.set_range(100, 100).unwrap_err(),
            PickerError::Inverted { .. }
        ));
    }

    #[test]
    fn width_helpers() {
        let mut p = DateRangePicker::new();
        p.set_range(0, 3 * DAY_MS + 1000).unwrap();
        assert_eq!(p.width_days(), 3);
        assert_eq!(p.width_ms(), 3 * DAY_MS + 1000);
    }

    #[test]
    fn empty_preset_name_rejected() {
        let mut p = DateRangePicker::new();
        assert!(matches!(
            p.register_preset("", 7).unwrap_err(),
            PickerError::EmptyName
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = DateRangePicker::new();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PickerError::SchemaMismatch
        ));
    }

    #[test]
    fn picker_serde_roundtrip() {
        let mut p = DateRangePicker::new();
        p.apply_preset("last-30-days", 100 * DAY_MS).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: DateRangePicker = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
