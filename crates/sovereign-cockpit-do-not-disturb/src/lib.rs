//! `sovereign-cockpit-do-not-disturb` — silence notifications.
//!
//! Mode{Off/Manual/Scheduled}. Manual is silenced unconditionally;
//! Scheduled is silenced when (now_ms / 86_400_000) day-of-time
//! falls in [start_min, end_min) (minutes since midnight UTC).
//! suppress(now, tag) returns true iff silenced AND tag not in
//! exempt set. exempt tags always pass.
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
    /// Off — no suppression.
    Off,
    /// Manual — silenced unconditionally.
    Manual,
    /// Scheduled — silenced inside [start_min, end_min) (mod 1440).
    Scheduled,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DoNotDisturb {
    /// Schema version.
    pub schema_version: String,
    /// Mode.
    pub mode: Mode,
    /// Start minute (0..1440).
    pub start_min: u32,
    /// End minute (0..1440); may wrap (end < start means overnight).
    pub end_min: u32,
    /// Exempt tags (always pass through).
    pub exempt: BTreeSet<String>,
    /// Suppressions counted.
    pub suppressed: u64,
    /// Pass-throughs counted.
    pub passed: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DndError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad minute.
    #[error("minute must be 0..1440")]
    BadMinute,
    /// Empty tag.
    #[error("tag empty")]
    EmptyTag,
}

impl DoNotDisturb {
    /// New (Off).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mode: Mode::Off,
            start_min: 0,
            end_min: 0,
            exempt: BTreeSet::new(),
            suppressed: 0,
            passed: 0,
        }
    }

    /// Set mode + schedule window.
    pub fn set(&mut self, mode: Mode, start_min: u32, end_min: u32) -> Result<(), DndError> {
        if start_min >= 1440 || end_min >= 1440 {
            return Err(DndError::BadMinute);
        }
        self.mode = mode;
        self.start_min = start_min;
        self.end_min = end_min;
        Ok(())
    }

    /// Add exempt tag.
    pub fn exempt_add(&mut self, tag: &str) -> Result<(), DndError> {
        if tag.is_empty() {
            return Err(DndError::EmptyTag);
        }
        self.exempt.insert(tag.into());
        Ok(())
    }

    /// Remove exempt tag.
    pub fn exempt_remove(&mut self, tag: &str) -> bool {
        self.exempt.remove(tag)
    }

    /// Is the schedule active at now_ms?
    pub fn scheduled_active(&self, now_ms: u64) -> bool {
        let minute_of_day = ((now_ms / 60_000) % 1440) as u32;
        if self.start_min == self.end_min {
            return false; // empty window
        }
        if self.start_min < self.end_min {
            minute_of_day >= self.start_min && minute_of_day < self.end_min
        } else {
            // overnight wrap
            minute_of_day >= self.start_min || minute_of_day < self.end_min
        }
    }

    /// True iff `tag` would be suppressed at `now_ms`. Mutates counters.
    pub fn suppress(&mut self, now_ms: u64, tag: &str) -> bool {
        if self.exempt.contains(tag) {
            self.passed = self.passed.saturating_add(1);
            return false;
        }
        let silenced = match self.mode {
            Mode::Off => false,
            Mode::Manual => true,
            Mode::Scheduled => self.scheduled_active(now_ms),
        };
        if silenced {
            self.suppressed = self.suppressed.saturating_add(1);
        } else {
            self.passed = self.passed.saturating_add(1);
        }
        silenced
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DndError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DndError::SchemaMismatch);
        }
        if self.start_min >= 1440 || self.end_min >= 1440 {
            return Err(DndError::BadMinute);
        }
        for t in &self.exempt {
            if t.is_empty() {
                return Err(DndError::EmptyTag);
            }
        }
        Ok(())
    }
}

impl Default for DoNotDisturb {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const MIN: u64 = 60_000;

    #[test]
    fn off_passes_all() {
        let mut d = DoNotDisturb::new();
        assert!(!d.suppress(0, "any"));
        assert_eq!(d.passed, 1);
    }

    #[test]
    fn manual_suppresses_all() {
        let mut d = DoNotDisturb::new();
        d.set(Mode::Manual, 0, 0).unwrap();
        assert!(d.suppress(0, "any"));
        assert!(d.suppress(99_999, "another"));
    }

    #[test]
    fn exempt_always_passes() {
        let mut d = DoNotDisturb::new();
        d.set(Mode::Manual, 0, 0).unwrap();
        d.exempt_add("critical").unwrap();
        assert!(!d.suppress(0, "critical"));
    }

    #[test]
    fn scheduled_window_normal() {
        let mut d = DoNotDisturb::new();
        // 22:00 → 23:00
        d.set(Mode::Scheduled, 22 * 60, 23 * 60).unwrap();
        let in_window = (22 * 60 + 30) as u64 * MIN; // 22:30
        let out_window = (10 * 60) as u64 * MIN; // 10:00
        assert!(d.suppress(in_window, "x"));
        assert!(!d.suppress(out_window, "x"));
    }

    #[test]
    fn scheduled_window_overnight() {
        let mut d = DoNotDisturb::new();
        // 23:00 → 06:00 (wraps midnight)
        d.set(Mode::Scheduled, 23 * 60, 6 * 60).unwrap();
        let at_2am = (2 * 60) as u64 * MIN;
        let at_noon = (12 * 60) as u64 * MIN;
        assert!(d.suppress(at_2am, "x"));
        assert!(!d.suppress(at_noon, "x"));
    }

    #[test]
    fn scheduled_empty_window_does_not_silence() {
        let mut d = DoNotDisturb::new();
        d.set(Mode::Scheduled, 600, 600).unwrap();
        let at_10 = 600u64 * MIN;
        assert!(!d.suppress(at_10, "x"));
    }

    #[test]
    fn exempt_remove() {
        let mut d = DoNotDisturb::new();
        d.exempt_add("x").unwrap();
        assert!(d.exempt_remove("x"));
        assert!(!d.exempt_remove("x"));
    }

    #[test]
    fn bad_minute_rejected() {
        let mut d = DoNotDisturb::new();
        assert!(matches!(
            d.set(Mode::Scheduled, 1440, 0).unwrap_err(),
            DndError::BadMinute
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = DoNotDisturb::new();
        d.schema_version = "9.9.9".into();
        assert!(matches!(
            d.validate().unwrap_err(),
            DndError::SchemaMismatch
        ));
    }

    #[test]
    fn dnd_serde_roundtrip() {
        let mut d = DoNotDisturb::new();
        d.set(Mode::Scheduled, 60, 120).unwrap();
        d.exempt_add("alert").unwrap();
        let j = serde_json::to_string(&d).unwrap();
        let back: DoNotDisturb = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
