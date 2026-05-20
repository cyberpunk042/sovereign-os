//! `sovereign-cockpit-stat-trend` — (previous, current) → trend.
//!
//! `trend(previous, current, polarity)` returns:
//!   * direction (Up/Down/Flat)
//!   * percent_change × 100 (signed)
//!   * color hint (Positive/Negative/Neutral) — depends on
//!     `polarity` so that "fewer errors" is Positive and "more
//!     errors" is Negative.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Direction {
    /// Up.
    Up,
    /// Down.
    Down,
    /// Flat.
    Flat,
}

/// Color hint.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ColorHint {
    /// Good change.
    Positive,
    /// Bad change.
    Negative,
    /// Neutral.
    Neutral,
}

/// Polarity of the metric.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Polarity {
    /// Higher is better (revenue, throughput).
    HigherBetter,
    /// Lower is better (errors, latency).
    LowerBetter,
    /// Neither direction is good or bad.
    Neutral,
}

/// Trend.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Trend {
    /// Direction.
    pub direction: Direction,
    /// Percent change × 100 (signed). Saturates at i32 bounds.
    pub percent_change_x100: i32,
    /// Color hint.
    pub color_hint: ColorHint,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StatTrend {
    /// Schema version.
    pub schema_version: String,
    /// Flat threshold in basis points × 100 (so 50 = 0.50%).
    pub flat_threshold_x100: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TrendError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl StatTrend {
    /// New.
    pub fn new(flat_threshold_x100: u32) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            flat_threshold_x100,
        }
    }

    /// Trend.
    pub fn trend(&self, previous: f64, current: f64, polarity: Polarity) -> Trend {
        // Percent change × 100.
        let pct_x100 = if previous == 0.0 {
            if current == 0.0 { 0 }
            else if current > 0.0 { i32::MAX }
            else { i32::MIN }
        } else {
            let raw = ((current - previous) / previous) * 100.0 * 100.0;
            if raw > i32::MAX as f64 { i32::MAX }
            else if raw < i32::MIN as f64 { i32::MIN }
            else { raw as i32 }
        };
        let abs = pct_x100.unsigned_abs();
        let direction = if abs <= self.flat_threshold_x100 {
            Direction::Flat
        } else if pct_x100 > 0 { Direction::Up } else { Direction::Down };
        let color_hint = match (direction, polarity) {
            (Direction::Flat, _) => ColorHint::Neutral,
            (_, Polarity::Neutral) => ColorHint::Neutral,
            (Direction::Up, Polarity::HigherBetter) => ColorHint::Positive,
            (Direction::Down, Polarity::HigherBetter) => ColorHint::Negative,
            (Direction::Up, Polarity::LowerBetter) => ColorHint::Negative,
            (Direction::Down, Polarity::LowerBetter) => ColorHint::Positive,
        };
        Trend { direction, percent_change_x100: pct_x100, color_hint }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TrendError> {
        if self.schema_version != SCHEMA_VERSION { return Err(TrendError::SchemaMismatch); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t() -> StatTrend { StatTrend::new(50) /* 0.50% */ }

    #[test]
    fn flat_when_inside_threshold() {
        // 100 → 100.3 = 0.3% change, below 0.50% threshold.
        let r = t().trend(100.0, 100.3, Polarity::HigherBetter);
        assert_eq!(r.direction, Direction::Flat);
        assert_eq!(r.color_hint, ColorHint::Neutral);
    }

    #[test]
    fn up_higher_better_positive() {
        let r = t().trend(100.0, 110.0, Polarity::HigherBetter);
        assert_eq!(r.direction, Direction::Up);
        assert_eq!(r.color_hint, ColorHint::Positive);
        assert_eq!(r.percent_change_x100, 1000); // +10.00%.
    }

    #[test]
    fn up_lower_better_negative() {
        let r = t().trend(100.0, 110.0, Polarity::LowerBetter);
        assert_eq!(r.color_hint, ColorHint::Negative);
    }

    #[test]
    fn down_lower_better_positive() {
        let r = t().trend(100.0, 90.0, Polarity::LowerBetter);
        assert_eq!(r.direction, Direction::Down);
        assert_eq!(r.color_hint, ColorHint::Positive);
        assert_eq!(r.percent_change_x100, -1000); // -10.00%.
    }

    #[test]
    fn neutral_polarity_neutral_color() {
        let r = t().trend(100.0, 110.0, Polarity::Neutral);
        assert_eq!(r.color_hint, ColorHint::Neutral);
    }

    #[test]
    fn previous_zero_current_positive_saturates_max() {
        let r = t().trend(0.0, 1.0, Polarity::HigherBetter);
        assert_eq!(r.percent_change_x100, i32::MAX);
        assert_eq!(r.direction, Direction::Up);
    }

    #[test]
    fn previous_zero_current_zero_flat() {
        let r = t().trend(0.0, 0.0, Polarity::HigherBetter);
        assert_eq!(r.direction, Direction::Flat);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = t();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), TrendError::SchemaMismatch));
    }

    #[test]
    fn trend_serde_roundtrip() {
        let s = t();
        let j = serde_json::to_string(&s).unwrap();
        let back: StatTrend = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
