//! `sovereign-cockpit-stale-banner` — content-staleness banner.
//!
//! Tracks `last_refresh_ms` + `max_fresh_ms` threshold. status(now)
//! returns Fresh / SlightlyStale (1..3× fresh) / Stale (3..10×) /
//! VeryStale (≥10×). age_text formats compact human-readable age.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Staleness.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Staleness {
    /// Fresh.
    Fresh,
    /// Slightly stale (1..3× threshold).
    SlightlyStale,
    /// Stale (3..10× threshold).
    Stale,
    /// Very stale (≥10× threshold).
    VeryStale,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StaleBanner {
    /// Schema version.
    pub schema_version: String,
    /// Last refresh ms.
    pub last_refresh_ms: u64,
    /// Threshold ms (below = fresh).
    pub max_fresh_ms: u64,
}

/// Result.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StaleStatus {
    /// Staleness tier.
    pub staleness: Staleness,
    /// Age ms.
    pub age_ms: u64,
    /// Human-readable age.
    pub age_text: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StaleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// max_fresh zero.
    #[error("max_fresh_ms is zero")]
    MaxFreshZero,
}

impl StaleBanner {
    /// New (last_refresh = 0 means never refreshed; status returns VeryStale).
    pub fn new(max_fresh_ms: u64) -> Result<Self, StaleError> {
        if max_fresh_ms == 0 { return Err(StaleError::MaxFreshZero); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            last_refresh_ms: 0,
            max_fresh_ms,
        })
    }

    /// Mark refreshed.
    pub fn refresh(&mut self, now_ms: u64) {
        self.last_refresh_ms = now_ms;
    }

    /// Compute status.
    pub fn status(&self, now_ms: u64) -> StaleStatus {
        if self.last_refresh_ms == 0 {
            return StaleStatus {
                staleness: Staleness::VeryStale,
                age_ms: 0,
                age_text: "never".into(),
            };
        }
        let age = now_ms.saturating_sub(self.last_refresh_ms);
        let staleness = if age < self.max_fresh_ms {
            Staleness::Fresh
        } else if age < self.max_fresh_ms * 3 {
            Staleness::SlightlyStale
        } else if age < self.max_fresh_ms * 10 {
            Staleness::Stale
        } else {
            Staleness::VeryStale
        };
        StaleStatus {
            staleness,
            age_ms: age,
            age_text: format_age(age),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StaleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(StaleError::SchemaMismatch);
        }
        if self.max_fresh_ms == 0 { return Err(StaleError::MaxFreshZero); }
        Ok(())
    }
}

fn format_age(ms: u64) -> String {
    let s = ms / 1000;
    if s < 60 { return format!("{s}s"); }
    let m = s / 60;
    if m < 60 { return format!("{m}m"); }
    let h = m / 60;
    if h < 24 { return format!("{h}h"); }
    let d = h / 24;
    format!("{d}d")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn max_fresh_zero_rejected() {
        assert!(matches!(StaleBanner::new(0).unwrap_err(), StaleError::MaxFreshZero));
    }

    #[test]
    fn never_refreshed_very_stale() {
        let b = StaleBanner::new(1_000).unwrap();
        let s = b.status(10_000);
        assert_eq!(s.staleness, Staleness::VeryStale);
        assert_eq!(s.age_text, "never");
    }

    #[test]
    fn fresh_under_threshold() {
        let mut b = StaleBanner::new(1_000).unwrap();
        b.refresh(1_000);
        let s = b.status(1_500);
        assert_eq!(s.staleness, Staleness::Fresh);
    }

    #[test]
    fn slightly_stale_1x_to_3x() {
        let mut b = StaleBanner::new(1_000).unwrap();
        b.refresh(1_000);
        let s = b.status(3_500);
        assert_eq!(s.staleness, Staleness::SlightlyStale);
    }

    #[test]
    fn stale_3x_to_10x() {
        let mut b = StaleBanner::new(1_000).unwrap();
        b.refresh(1_000);
        let s = b.status(6_000);
        assert_eq!(s.staleness, Staleness::Stale);
    }

    #[test]
    fn very_stale_at_10x() {
        let mut b = StaleBanner::new(1_000).unwrap();
        b.refresh(1_000);
        let s = b.status(12_000);
        assert_eq!(s.staleness, Staleness::VeryStale);
    }

    #[test]
    fn age_text_seconds() {
        assert_eq!(format_age(500), "0s");
        assert_eq!(format_age(5_000), "5s");
    }

    #[test]
    fn age_text_minutes() {
        assert_eq!(format_age(120_000), "2m");
    }

    #[test]
    fn age_text_hours() {
        assert_eq!(format_age(2 * 3600 * 1000), "2h");
    }

    #[test]
    fn age_text_days() {
        assert_eq!(format_age(3 * 86400 * 1000), "3d");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = StaleBanner::new(1_000).unwrap();
        b.schema_version = "9.9.9".into();
        assert!(matches!(b.validate().unwrap_err(), StaleError::SchemaMismatch));
    }

    #[test]
    fn banner_serde_roundtrip() {
        let mut b = StaleBanner::new(1_000).unwrap();
        b.refresh(500);
        let j = serde_json::to_string(&b).unwrap();
        let back: StaleBanner = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
