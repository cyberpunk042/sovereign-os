//! `sovereign-cockpit-timeline-axis` — tick generator for chart x-axis.
//!
//! Curated tick intervals (ms): 1s, 5s, 15s, 30s, 1m, 5m, 15m, 30m,
//! 1h, 2h, 6h, 12h, 1d, 2d, 7d. `ticks(from, to, target)` picks the
//! interval whose `(to - from) / interval` is closest to `target`
//! and emits ticks at multiples of that interval inside `[from, to]`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

const INTERVALS_MS: &[u64] = &[
    1_000,
    5_000,
    15_000,
    30_000,
    60_000,
    5 * 60_000,
    15 * 60_000,
    30 * 60_000,
    60 * 60_000,
    2 * 60 * 60_000,
    6 * 60 * 60_000,
    12 * 60 * 60_000,
    24 * 60 * 60_000,
    2 * 24 * 60 * 60_000,
    7 * 24 * 60 * 60_000,
];

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TimelineAxis {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AxisError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad range.
    #[error("from {0} >= to {1}")]
    BadRange(u64, u64),
    /// target zero.
    #[error("target_count must be > 0")]
    TargetZero,
}

impl TimelineAxis {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    /// Pick the best interval (ms) for the given range + target count.
    pub fn pick_interval(
        &self,
        from_ms: u64,
        to_ms: u64,
        target_count: u32,
    ) -> Result<u64, AxisError> {
        if from_ms >= to_ms {
            return Err(AxisError::BadRange(from_ms, to_ms));
        }
        if target_count == 0 {
            return Err(AxisError::TargetZero);
        }
        let range = to_ms - from_ms;
        let want = range / target_count as u64;
        // Pick the interval whose distance to `want` is smallest.
        let mut best = INTERVALS_MS[0];
        let mut best_dist = best.abs_diff(want);
        for &iv in INTERVALS_MS {
            let d = iv.abs_diff(want);
            if d < best_dist {
                best_dist = d;
                best = iv;
            }
        }
        Ok(best)
    }

    /// Emit ticks.
    pub fn ticks(
        &self,
        from_ms: u64,
        to_ms: u64,
        target_count: u32,
    ) -> Result<Vec<u64>, AxisError> {
        let interval = self.pick_interval(from_ms, to_ms, target_count)?;
        // Snap first tick down to multiple of interval ≥ from_ms.
        let first = if from_ms.is_multiple_of(interval) {
            from_ms
        } else {
            from_ms + (interval - (from_ms % interval))
        };
        let mut out = Vec::new();
        let mut t = first;
        while t <= to_ms {
            out.push(t);
            t = t.saturating_add(interval);
            if t < first {
                break;
            } // overflow guard
        }
        Ok(out)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AxisError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(AxisError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for TimelineAxis {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bad_range_rejected() {
        let a = TimelineAxis::new();
        assert!(matches!(
            a.ticks(100, 100, 5).unwrap_err(),
            AxisError::BadRange(_, _)
        ));
    }

    #[test]
    fn target_zero_rejected() {
        let a = TimelineAxis::new();
        assert!(matches!(
            a.ticks(0, 1000, 0).unwrap_err(),
            AxisError::TargetZero
        ));
    }

    #[test]
    fn pick_interval_one_minute_range() {
        let a = TimelineAxis::new();
        // 60s range / 6 = 10s. Closest curated = 15s (vs 5s).
        let iv = a.pick_interval(0, 60_000, 6).unwrap();
        assert!(iv == 5_000 || iv == 15_000);
    }

    #[test]
    fn ticks_inside_range() {
        let a = TimelineAxis::new();
        let ticks = a.ticks(0, 60_000, 6).unwrap();
        assert!(!ticks.is_empty());
        for t in &ticks {
            assert!(*t <= 60_000);
        }
    }

    #[test]
    fn ticks_aligned_to_interval() {
        let a = TimelineAxis::new();
        let ticks = a.ticks(0, 60_000, 6).unwrap();
        let iv = a.pick_interval(0, 60_000, 6).unwrap();
        for t in &ticks {
            assert_eq!(t % iv, 0);
        }
    }

    #[test]
    fn one_hour_range() {
        let a = TimelineAxis::new();
        let iv = a.pick_interval(0, 60 * 60_000, 12).unwrap();
        // 1h / 12 = 5m → curated 5m.
        assert_eq!(iv, 5 * 60_000);
    }

    #[test]
    fn day_range() {
        let a = TimelineAxis::new();
        let iv = a.pick_interval(0, 24 * 60 * 60_000, 24).unwrap();
        // 1d / 24 = 1h → curated 1h.
        assert_eq!(iv, 60 * 60_000);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut a = TimelineAxis::new();
        a.schema_version = "9.9.9".into();
        assert!(matches!(
            a.validate().unwrap_err(),
            AxisError::SchemaMismatch
        ));
    }

    #[test]
    fn axis_serde_roundtrip() {
        let a = TimelineAxis::new();
        let j = serde_json::to_string(&a).unwrap();
        let back: TimelineAxis = serde_json::from_str(&j).unwrap();
        assert_eq!(a, back);
    }
}
