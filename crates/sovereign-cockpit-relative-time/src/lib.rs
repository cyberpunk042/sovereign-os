//! `sovereign-cockpit-relative-time` — render (now, then) as a bucket label.
//!
//! Buckets, by age in seconds (or future-age):
//!
//!   * `< 45 s` → "just now" / "in a few seconds"
//!   * `< 60 m` → "Nm ago" / "in Nm"
//!   * `< 24 h` → "Nh ago" / "in Nh"
//!   * `< 48 h` → "Yesterday" / "Tomorrow"
//!   * `< 30 d` → "Nd ago" / "in Nd"
//!   * `< 52 w` → "Nw ago" / "in Nw"
//!   * `< 12 mo` → "Nmo ago" / "in Nmo"
//!   * `else`  → "Ny ago" / "in Ny"
//!
//! Boundary uses 1 month = 30 days, 1 year = 365 days. No locale.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State (currently only stores the schema marker — render is pure).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RelativeTime {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RelativeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl RelativeTime {
    /// New.
    pub fn new() -> Self {
        Self { schema_version: SCHEMA_VERSION.into() }
    }

    /// Render relative label for `then_ms` relative to `now_ms`.
    pub fn render(&self, now_ms: u64, then_ms: u64) -> String {
        let (past, dt_s) = if now_ms >= then_ms {
            (true, (now_ms - then_ms) / 1000)
        } else {
            (false, (then_ms - now_ms) / 1000)
        };
        let min = dt_s / 60;
        let hr = dt_s / 3600;
        let day = dt_s / 86_400;
        let wk = day / 7;
        let mo = day / 30;
        let yr = day / 365;
        if dt_s < 45 {
            if past { "just now".into() } else { "in a few seconds".into() }
        } else if min < 60 {
            if past { format!("{min}m ago") } else { format!("in {min}m") }
        } else if hr < 24 {
            if past { format!("{hr}h ago") } else { format!("in {hr}h") }
        } else if day < 2 {
            if past { "Yesterday".into() } else { "Tomorrow".into() }
        } else if day < 30 {
            if past { format!("{day}d ago") } else { format!("in {day}d") }
        } else if wk < 52 && mo < 12 {
            if past { format!("{wk}w ago") } else { format!("in {wk}w") }
        } else if mo < 12 {
            if past { format!("{mo}mo ago") } else { format!("in {mo}mo") }
        } else {
            if past { format!("{yr}y ago") } else { format!("in {yr}y") }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RelativeError> {
        if self.schema_version != SCHEMA_VERSION { return Err(RelativeError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for RelativeTime {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn r() -> RelativeTime { RelativeTime::new() }

    #[test]
    fn just_now() {
        assert_eq!(r().render(10_000, 10_000), "just now");
        assert_eq!(r().render(40_000, 0), "just now");
    }

    #[test]
    fn minutes_past() {
        assert_eq!(r().render(5 * 60_000, 0), "5m ago");
    }

    #[test]
    fn hours_past() {
        assert_eq!(r().render(3 * 3_600_000, 0), "3h ago");
    }

    #[test]
    fn yesterday() {
        assert_eq!(r().render(36 * 3_600_000, 0), "Yesterday");
    }

    #[test]
    fn days_past() {
        assert_eq!(r().render(5 * 86_400_000, 0), "5d ago");
    }

    #[test]
    fn weeks_past() {
        // 60 days → 8w.
        assert_eq!(r().render(60 * 86_400_000, 0), "8w ago");
    }

    #[test]
    fn years_past() {
        // 800 days → 2y.
        assert_eq!(r().render(800 * 86_400_000, 0), "2y ago");
    }

    #[test]
    fn future_minutes() {
        assert_eq!(r().render(0, 5 * 60_000), "in 5m");
    }

    #[test]
    fn future_tomorrow() {
        assert_eq!(r().render(0, 36 * 3_600_000), "Tomorrow");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut x = r();
        x.schema_version = "9.9.9".into();
        assert!(matches!(x.validate().unwrap_err(), RelativeError::SchemaMismatch));
    }

    #[test]
    fn relative_serde_roundtrip() {
        let x = r();
        let j = serde_json::to_string(&x).unwrap();
        let back: RelativeTime = serde_json::from_str(&j).unwrap();
        assert_eq!(x, back);
    }
}
