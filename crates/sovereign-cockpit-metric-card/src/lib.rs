//! `sovereign-cockpit-metric-card` — composable metric card.
//!
//! MetricCard{title, value, unit, prev, samples,
//! last_updated_ms}. set_value(v) shifts prev←value; push_sample
//! appends to bounded sparkline. trend() returns Trend from
//! delta with epsilon. delta_bp computes value/prev change.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Trend.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Trend {
    /// Up.
    Up,
    /// Flat.
    Flat,
    /// Down.
    Down,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MetricCard {
    /// Schema version.
    pub schema_version: String,
    /// Title.
    pub title: String,
    /// Unit.
    pub unit: String,
    /// Current value.
    pub value: i64,
    /// Previous value (None when value not yet set).
    pub prev: Option<i64>,
    /// Sparkline samples (newest-last, bounded).
    pub samples: Vec<i64>,
    /// Sparkline cap.
    pub sparkline_cap: u32,
    /// Last updated ts ms.
    pub last_updated_ms: u64,
    /// Flat-trend epsilon (bp).
    pub flat_epsilon_bp: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CardError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Zero cap.
    #[error("sparkline_cap must be >= 1")]
    ZeroCap,
}

impl MetricCard {
    /// New.
    pub fn new(
        title: &str,
        unit: &str,
        sparkline_cap: u32,
        flat_epsilon_bp: u32,
    ) -> Result<Self, CardError> {
        if title.is_empty() {
            return Err(CardError::EmptyTitle);
        }
        if sparkline_cap == 0 {
            return Err(CardError::ZeroCap);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            title: title.into(),
            unit: unit.into(),
            value: 0,
            prev: None,
            samples: Vec::new(),
            sparkline_cap,
            last_updated_ms: 0,
            flat_epsilon_bp,
        })
    }

    /// Set value (shifts prev ← current; pushes sample).
    pub fn set_value(&mut self, value: i64, now_ms: u64) {
        self.prev = Some(self.value);
        self.value = value;
        self.last_updated_ms = now_ms;
        if (self.samples.len() as u32) >= self.sparkline_cap {
            self.samples.remove(0);
        }
        self.samples.push(value);
    }

    /// Delta bp (value - prev) * 10000 / |prev|.
    pub fn delta_bp(&self) -> i64 {
        let prev = self.prev.unwrap_or(0);
        if prev == 0 {
            if self.value == 0 {
                0
            } else if self.value > 0 {
                10_000
            } else {
                -10_000
            }
        } else {
            ((self.value as i128 - prev as i128) * 10_000 / prev.unsigned_abs() as i128) as i64
        }
    }

    /// Trend.
    pub fn trend(&self) -> Trend {
        let d = self.delta_bp();
        let eps = self.flat_epsilon_bp as i64;
        if d.abs() <= eps {
            Trend::Flat
        } else if d > 0 {
            Trend::Up
        } else {
            Trend::Down
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CardError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CardError::SchemaMismatch);
        }
        if self.title.is_empty() {
            return Err(CardError::EmptyTitle);
        }
        if self.sparkline_cap == 0 {
            return Err(CardError::ZeroCap);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn first_set_no_prev_change() {
        let mut c = MetricCard::new("CPU", "%", 5, 100).unwrap();
        c.set_value(50, 100);
        assert_eq!(c.value, 50);
        assert_eq!(c.prev, Some(0));
    }

    #[test]
    fn set_shifts_prev() {
        let mut c = MetricCard::new("X", "", 5, 100).unwrap();
        c.set_value(100, 10);
        c.set_value(150, 20);
        assert_eq!(c.prev, Some(100));
        assert_eq!(c.value, 150);
    }

    #[test]
    fn sparkline_capped() {
        let mut c = MetricCard::new("X", "", 3, 100).unwrap();
        for i in 1..=5 {
            c.set_value(i, 0);
        }
        assert_eq!(c.samples, vec![3, 4, 5]);
    }

    #[test]
    fn delta_bp_basic() {
        let mut c = MetricCard::new("X", "", 5, 100).unwrap();
        c.set_value(100, 0);
        c.set_value(110, 0);
        // delta = (110 - 100) * 10000 / 100 = 1000 bp.
        assert_eq!(c.delta_bp(), 1000);
        assert_eq!(c.trend(), Trend::Up);
    }

    #[test]
    fn flat_within_epsilon() {
        let mut c = MetricCard::new("X", "", 5, 200).unwrap();
        c.set_value(100, 0);
        c.set_value(101, 0);
        assert_eq!(c.trend(), Trend::Flat);
    }

    #[test]
    fn empty_inputs_rejected() {
        assert!(matches!(
            MetricCard::new("", "", 5, 0).unwrap_err(),
            CardError::EmptyTitle
        ));
        assert!(matches!(
            MetricCard::new("X", "", 0, 0).unwrap_err(),
            CardError::ZeroCap
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = MetricCard::new("X", "", 5, 0).unwrap();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            CardError::SchemaMismatch
        ));
    }

    #[test]
    fn card_serde_roundtrip() {
        let mut c = MetricCard::new("X", "", 5, 0).unwrap();
        c.set_value(50, 100);
        let j = serde_json::to_string(&c).unwrap();
        let back: MetricCard = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
