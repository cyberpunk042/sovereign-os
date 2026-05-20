//! `sovereign-cockpit-log-level-filter` — level filter + counts.
//!
//! Level{Trace<Debug<Info<Warn<Error}. min level threshold passes
//! events at >= min. observe(level) increments per-level count
//! regardless of threshold; visible_count returns count of events
//! at >= min. Pure data.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Level.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Level {
    /// Trace.
    Trace,
    /// Debug.
    Debug,
    /// Info.
    Info,
    /// Warn.
    Warn,
    /// Error.
    Error,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LogLevelFilter {
    /// Schema version.
    pub schema_version: String,
    /// Minimum visible level.
    pub min: Level,
    /// Trace count.
    pub trace: u64,
    /// Debug count.
    pub debug: u64,
    /// Info count.
    pub info: u64,
    /// Warn count.
    pub warn: u64,
    /// Error count.
    pub error: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FilterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl LogLevelFilter {
    /// New with given min level.
    pub fn new(min: Level) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            min,
            trace: 0,
            debug: 0,
            info: 0,
            warn: 0,
            error: 0,
        }
    }

    /// Set min level.
    pub fn set_min(&mut self, level: Level) {
        self.min = level;
    }

    /// Should level pass the current min threshold?
    pub fn passes(&self, level: Level) -> bool {
        level >= self.min
    }

    /// Observe a log event; increment its count regardless of threshold.
    pub fn observe(&mut self, level: Level) {
        match level {
            Level::Trace => self.trace = self.trace.saturating_add(1),
            Level::Debug => self.debug = self.debug.saturating_add(1),
            Level::Info => self.info = self.info.saturating_add(1),
            Level::Warn => self.warn = self.warn.saturating_add(1),
            Level::Error => self.error = self.error.saturating_add(1),
        }
    }

    /// Count visible at current threshold.
    pub fn visible_count(&self) -> u64 {
        let mut total = 0u64;
        let buckets: [(Level, u64); 5] = [
            (Level::Trace, self.trace),
            (Level::Debug, self.debug),
            (Level::Info, self.info),
            (Level::Warn, self.warn),
            (Level::Error, self.error),
        ];
        for (lvl, n) in buckets {
            if lvl >= self.min { total = total.saturating_add(n); }
        }
        total
    }

    /// Total count (regardless of threshold).
    pub fn total(&self) -> u64 {
        self.trace
            .saturating_add(self.debug)
            .saturating_add(self.info)
            .saturating_add(self.warn)
            .saturating_add(self.error)
    }

    /// Reset counts.
    pub fn reset(&mut self) {
        self.trace = 0;
        self.debug = 0;
        self.info = 0;
        self.warn = 0;
        self.error = 0;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FilterError> {
        if self.schema_version != SCHEMA_VERSION { return Err(FilterError::SchemaMismatch); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn order_correct() {
        assert!(Level::Error > Level::Warn);
        assert!(Level::Warn > Level::Info);
        assert!(Level::Info > Level::Debug);
        assert!(Level::Debug > Level::Trace);
    }

    #[test]
    fn passes_at_or_above_min() {
        let f = LogLevelFilter::new(Level::Info);
        assert!(!f.passes(Level::Trace));
        assert!(!f.passes(Level::Debug));
        assert!(f.passes(Level::Info));
        assert!(f.passes(Level::Warn));
        assert!(f.passes(Level::Error));
    }

    #[test]
    fn observe_counts() {
        let mut f = LogLevelFilter::new(Level::Info);
        f.observe(Level::Trace);
        f.observe(Level::Info);
        f.observe(Level::Info);
        f.observe(Level::Error);
        assert_eq!(f.trace, 1);
        assert_eq!(f.info, 2);
        assert_eq!(f.error, 1);
    }

    #[test]
    fn visible_count_filters() {
        let mut f = LogLevelFilter::new(Level::Warn);
        f.observe(Level::Trace);
        f.observe(Level::Info);
        f.observe(Level::Warn);
        f.observe(Level::Error);
        assert_eq!(f.visible_count(), 2);
        assert_eq!(f.total(), 4);
    }

    #[test]
    fn set_min_changes_visibility() {
        let mut f = LogLevelFilter::new(Level::Trace);
        f.observe(Level::Trace);
        f.observe(Level::Info);
        assert_eq!(f.visible_count(), 2);
        f.set_min(Level::Info);
        assert_eq!(f.visible_count(), 1);
    }

    #[test]
    fn reset_clears() {
        let mut f = LogLevelFilter::new(Level::Trace);
        f.observe(Level::Info);
        f.observe(Level::Error);
        f.reset();
        assert_eq!(f.total(), 0);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = LogLevelFilter::new(Level::Info);
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), FilterError::SchemaMismatch));
    }

    #[test]
    fn filter_serde_roundtrip() {
        let mut f = LogLevelFilter::new(Level::Warn);
        f.observe(Level::Error);
        let j = serde_json::to_string(&f).unwrap();
        let back: LogLevelFilter = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
