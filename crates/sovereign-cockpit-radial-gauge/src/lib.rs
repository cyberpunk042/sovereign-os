//! `sovereign-cockpit-radial-gauge` — circular gauge state.
//!
//! min < max; value clamped to [min, max]. fill_bp = (value-
//! min)*10000/(max-min). Zone{Cold/Warm/Hot} from thresholds
//! warm_bp + hot_bp (strictly increasing). set_value clamps.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Zone.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Zone {
    /// Cold (under warm_bp).
    Cold,
    /// Warm (>= warm_bp, < hot_bp).
    Warm,
    /// Hot (>= hot_bp).
    Hot,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RadialGauge {
    /// Schema version.
    pub schema_version: String,
    /// Min.
    pub min: i64,
    /// Max.
    pub max: i64,
    /// Value (clamped).
    pub value: i64,
    /// Warm threshold in bp.
    pub warm_bp: u32,
    /// Hot threshold in bp.
    pub hot_bp: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GaugeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad range.
    #[error("min must be < max")]
    BadRange,
    /// Bad thresholds.
    #[error("warm_bp must be < hot_bp <= 10000")]
    BadThresholds,
}

impl RadialGauge {
    /// New.
    pub fn new(min: i64, max: i64, warm_bp: u32, hot_bp: u32) -> Result<Self, GaugeError> {
        if min >= max {
            return Err(GaugeError::BadRange);
        }
        if !(warm_bp < hot_bp && hot_bp <= 10_000) {
            return Err(GaugeError::BadThresholds);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            min,
            max,
            value: min,
            warm_bp,
            hot_bp,
        })
    }

    /// Set value (clamped).
    pub fn set_value(&mut self, value: i64) {
        self.value = value.clamp(self.min, self.max);
    }

    /// Fill ratio in bp (0..=10000).
    pub fn fill_bp(&self) -> u32 {
        let span = (self.max - self.min) as i128;
        let v = (self.value - self.min) as i128;
        ((v * 10_000) / span).max(0).min(10_000) as u32
    }

    /// Zone classification.
    pub fn zone(&self) -> Zone {
        let bp = self.fill_bp();
        if bp < self.warm_bp {
            Zone::Cold
        } else if bp < self.hot_bp {
            Zone::Warm
        } else {
            Zone::Hot
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GaugeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(GaugeError::SchemaMismatch);
        }
        if self.min >= self.max {
            return Err(GaugeError::BadRange);
        }
        if !(self.warm_bp < self.hot_bp && self.hot_bp <= 10_000) {
            return Err(GaugeError::BadThresholds);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn gauge() -> RadialGauge {
        // Range 0..100; warm at 60%, hot at 85%.
        RadialGauge::new(0, 100, 6000, 8500).unwrap()
    }

    #[test]
    fn fill_half() {
        let mut g = gauge();
        g.set_value(50);
        assert_eq!(g.fill_bp(), 5000);
    }

    #[test]
    fn clamp_low() {
        let mut g = gauge();
        g.set_value(-50);
        assert_eq!(g.value, 0);
        assert_eq!(g.fill_bp(), 0);
    }

    #[test]
    fn clamp_high() {
        let mut g = gauge();
        g.set_value(200);
        assert_eq!(g.value, 100);
        assert_eq!(g.fill_bp(), 10_000);
    }

    #[test]
    fn cold_warm_hot() {
        let mut g = gauge();
        g.set_value(40); // 4000 < 6000 → Cold
        assert_eq!(g.zone(), Zone::Cold);
        g.set_value(70); // 7000 < 8500 → Warm
        assert_eq!(g.zone(), Zone::Warm);
        g.set_value(95); // 9500 >= 8500 → Hot
        assert_eq!(g.zone(), Zone::Hot);
    }

    #[test]
    fn negative_range() {
        let mut g = RadialGauge::new(-50, 50, 5000, 8000).unwrap();
        g.set_value(0);
        assert_eq!(g.fill_bp(), 5000);
        assert_eq!(g.zone(), Zone::Warm);
    }

    #[test]
    fn bad_inputs_rejected() {
        assert!(matches!(
            RadialGauge::new(100, 0, 5000, 8000).unwrap_err(),
            GaugeError::BadRange
        ));
        assert!(matches!(
            RadialGauge::new(0, 100, 8000, 5000).unwrap_err(),
            GaugeError::BadThresholds
        ));
        assert!(matches!(
            RadialGauge::new(0, 100, 5000, 10_001).unwrap_err(),
            GaugeError::BadThresholds
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = gauge();
        g.schema_version = "9.9.9".into();
        assert!(matches!(
            g.validate().unwrap_err(),
            GaugeError::SchemaMismatch
        ));
    }

    #[test]
    fn gauge_serde_roundtrip() {
        let mut g = gauge();
        g.set_value(50);
        let j = serde_json::to_string(&g).unwrap();
        let back: RadialGauge = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
