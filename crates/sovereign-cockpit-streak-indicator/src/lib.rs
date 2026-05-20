//! `sovereign-cockpit-streak-indicator` — consecutive-success counter.
//!
//! hit(key) increments current; miss(key) resets current to 0.
//! best tracks the all-time max current observed. Surface shows
//! both current + best per key (e.g. daily-checkin badge).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-key streak.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct Streak {
    /// Current consecutive count.
    pub current: u32,
    /// All-time best.
    pub best: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StreakIndicator {
    /// Schema version.
    pub schema_version: String,
    /// key → streak.
    pub streaks: BTreeMap<String, Streak>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StreakError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("key empty")]
    EmptyKey,
}

impl StreakIndicator {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            streaks: BTreeMap::new(),
        }
    }

    /// Register a success — increments current; updates best.
    pub fn hit(&mut self, key: &str) -> Result<u32, StreakError> {
        if key.is_empty() { return Err(StreakError::EmptyKey); }
        let s = self.streaks.entry(key.into()).or_default();
        s.current = s.current.saturating_add(1);
        if s.current > s.best { s.best = s.current; }
        Ok(s.current)
    }

    /// Register a miss — resets current to 0; best preserved.
    pub fn miss(&mut self, key: &str) -> Result<(), StreakError> {
        if key.is_empty() { return Err(StreakError::EmptyKey); }
        let s = self.streaks.entry(key.into()).or_default();
        s.current = 0;
        Ok(())
    }

    /// Look up.
    pub fn get(&self, key: &str) -> Option<&Streak> {
        self.streaks.get(key)
    }

    /// Reset current + best for a key.
    pub fn clear(&mut self, key: &str) -> Result<(), StreakError> {
        if key.is_empty() { return Err(StreakError::EmptyKey); }
        self.streaks.remove(key);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StreakError> {
        if self.schema_version != SCHEMA_VERSION { return Err(StreakError::SchemaMismatch); }
        for k in self.streaks.keys() {
            if k.is_empty() { return Err(StreakError::EmptyKey); }
        }
        Ok(())
    }
}

impl Default for StreakIndicator {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hit_increments_current_and_best() {
        let mut s = StreakIndicator::new();
        assert_eq!(s.hit("daily").unwrap(), 1);
        assert_eq!(s.hit("daily").unwrap(), 2);
        assert_eq!(s.hit("daily").unwrap(), 3);
        let st = s.get("daily").unwrap();
        assert_eq!(st.current, 3);
        assert_eq!(st.best, 3);
    }

    #[test]
    fn miss_resets_current_keeps_best() {
        let mut s = StreakIndicator::new();
        s.hit("a").unwrap();
        s.hit("a").unwrap();
        s.hit("a").unwrap();
        s.miss("a").unwrap();
        let st = s.get("a").unwrap();
        assert_eq!(st.current, 0);
        assert_eq!(st.best, 3);
    }

    #[test]
    fn best_does_not_regress() {
        let mut s = StreakIndicator::new();
        s.hit("a").unwrap();
        s.hit("a").unwrap();
        s.hit("a").unwrap();
        s.hit("a").unwrap();
        s.miss("a").unwrap();
        s.hit("a").unwrap();
        s.hit("a").unwrap();
        assert_eq!(s.get("a").unwrap().best, 4);
        assert_eq!(s.get("a").unwrap().current, 2);
    }

    #[test]
    fn independent_keys() {
        let mut s = StreakIndicator::new();
        s.hit("a").unwrap();
        s.hit("b").unwrap();
        s.hit("a").unwrap();
        assert_eq!(s.get("a").unwrap().current, 2);
        assert_eq!(s.get("b").unwrap().current, 1);
    }

    #[test]
    fn clear_removes_key() {
        let mut s = StreakIndicator::new();
        s.hit("a").unwrap();
        s.clear("a").unwrap();
        assert!(s.get("a").is_none());
    }

    #[test]
    fn empty_key_rejected() {
        let mut s = StreakIndicator::new();
        assert!(matches!(s.hit("").unwrap_err(), StreakError::EmptyKey));
        assert!(matches!(s.miss("").unwrap_err(), StreakError::EmptyKey));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = StreakIndicator::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), StreakError::SchemaMismatch));
    }

    #[test]
    fn streak_serde_roundtrip() {
        let mut s = StreakIndicator::new();
        s.hit("a").unwrap();
        s.hit("a").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: StreakIndicator = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
