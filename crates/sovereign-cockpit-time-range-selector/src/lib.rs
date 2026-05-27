//! `sovereign-cockpit-time-range-selector` — preset + custom time range.
//!
//! `Range::Last5m` / `Last15m` / `LastHour` / `Last24h` / `Last7d` /
//! `Last30d` resolve relative to `now`. `Custom { from_ms, to_ms }`
//! is absolute. `resolve(now_ms)` returns the `(from_ms, to_ms)` pair.
//! Custom must satisfy `from_ms < to_ms`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Range.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Range {
    /// Last 5 minutes.
    Last5m,
    /// Last 15 minutes.
    Last15m,
    /// Last hour.
    LastHour,
    /// Last 24 hours.
    Last24h,
    /// Last 7 days.
    Last7d,
    /// Last 30 days.
    Last30d,
    /// Custom absolute.
    Custom {
        /// from.
        from_ms: u64,
        /// to.
        to_ms: u64,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TimeRangeSelector {
    /// Schema version.
    pub schema_version: String,
    /// Current range.
    pub range: Range,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SelectorError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Custom from >= to.
    #[error("custom from {0} >= to {1}")]
    BadCustom(u64, u64),
}

impl TimeRangeSelector {
    /// New.
    pub fn new(range: Range) -> Result<Self, SelectorError> {
        if let Range::Custom { from_ms, to_ms } = &range {
            if from_ms >= to_ms {
                return Err(SelectorError::BadCustom(*from_ms, *to_ms));
            }
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            range,
        })
    }

    /// Set range.
    pub fn set(&mut self, range: Range) -> Result<(), SelectorError> {
        if let Range::Custom { from_ms, to_ms } = &range {
            if from_ms >= to_ms {
                return Err(SelectorError::BadCustom(*from_ms, *to_ms));
            }
        }
        self.range = range;
        Ok(())
    }

    /// Resolve to (from_ms, to_ms).
    pub fn resolve(&self, now_ms: u64) -> (u64, u64) {
        match self.range {
            Range::Last5m => (now_ms.saturating_sub(5 * 60_000), now_ms),
            Range::Last15m => (now_ms.saturating_sub(15 * 60_000), now_ms),
            Range::LastHour => (now_ms.saturating_sub(60 * 60_000), now_ms),
            Range::Last24h => (now_ms.saturating_sub(24 * 60 * 60_000), now_ms),
            Range::Last7d => (now_ms.saturating_sub(7 * 24 * 60 * 60_000), now_ms),
            Range::Last30d => (now_ms.saturating_sub(30 * 24 * 60 * 60_000), now_ms),
            Range::Custom { from_ms, to_ms } => (from_ms, to_ms),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SelectorError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SelectorError::SchemaMismatch);
        }
        if let Range::Custom { from_ms, to_ms } = &self.range {
            if from_ms >= to_ms {
                return Err(SelectorError::BadCustom(*from_ms, *to_ms));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn last5m() {
        let s = TimeRangeSelector::new(Range::Last5m).unwrap();
        let (from, to) = s.resolve(1_000_000);
        assert_eq!(to - from, 5 * 60_000);
        assert_eq!(to, 1_000_000);
    }

    #[test]
    fn last_hour() {
        let s = TimeRangeSelector::new(Range::LastHour).unwrap();
        let (from, to) = s.resolve(10_000_000);
        assert_eq!(to - from, 60 * 60_000);
    }

    #[test]
    fn last_30d() {
        let s = TimeRangeSelector::new(Range::Last30d).unwrap();
        let (from, to) = s.resolve(u64::MAX / 2);
        assert_eq!(to - from, 30 * 24 * 60 * 60_000);
    }

    #[test]
    fn custom_round_trips() {
        let s = TimeRangeSelector::new(Range::Custom {
            from_ms: 100,
            to_ms: 1000,
        })
        .unwrap();
        assert_eq!(s.resolve(99_999), (100, 1000));
    }

    #[test]
    fn bad_custom_rejected() {
        assert!(matches!(
            TimeRangeSelector::new(Range::Custom {
                from_ms: 1000,
                to_ms: 100
            })
            .unwrap_err(),
            SelectorError::BadCustom(_, _)
        ));
    }

    #[test]
    fn now_zero_saturates() {
        let s = TimeRangeSelector::new(Range::Last24h).unwrap();
        // now_ms = 0 — saturating_sub leaves both at 0.
        assert_eq!(s.resolve(0), (0, 0));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = TimeRangeSelector::new(Range::Last5m).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SelectorError::SchemaMismatch
        ));
    }

    #[test]
    fn selector_serde_roundtrip() {
        let s = TimeRangeSelector::new(Range::Custom {
            from_ms: 1,
            to_ms: 10,
        })
        .unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: TimeRangeSelector = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
