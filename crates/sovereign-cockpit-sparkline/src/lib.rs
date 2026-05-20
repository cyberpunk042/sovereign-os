//! `sovereign-cockpit-sparkline` — sparkline projection.
//!
//! Maps a series of f64 values to per-bar heights in [0..=height_px]
//! normalized against observed min/max. NaN values are treated as
//! 0. Series shorter than width_px → fewer bars; longer → caller
//! must downsample.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Sparkline {
    /// Schema version.
    pub schema_version: String,
    /// Series values.
    pub values: Vec<f64>,
    /// Render height in px.
    pub height_px: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SparkError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Height zero.
    #[error("height_px is zero")]
    HeightZero,
}

impl Sparkline {
    /// New.
    pub fn new(height_px: u32) -> Result<Self, SparkError> {
        if height_px == 0 { return Err(SparkError::HeightZero); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            values: Vec::new(),
            height_px,
        })
    }

    /// Push value.
    pub fn push(&mut self, v: f64) {
        self.values.push(if v.is_nan() { 0.0 } else { v });
    }

    /// Compute per-bar heights normalized.
    pub fn bar_heights(&self) -> Vec<u32> {
        if self.values.is_empty() { return Vec::new(); }
        let (min, max) = self.values.iter().fold((f64::INFINITY, f64::NEG_INFINITY), |(lo, hi), &v| {
            (lo.min(v), hi.max(v))
        });
        let range = max - min;
        let h = self.height_px as f64;
        self.values.iter().map(|&v| {
            if range <= 0.0 { (h * 0.5) as u32 }
            else {
                let norm = ((v - min) / range).clamp(0.0, 1.0);
                (norm * h) as u32
            }
        }).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SparkError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SparkError::SchemaMismatch);
        }
        if self.height_px == 0 { return Err(SparkError::HeightZero); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn height_zero_rejected() {
        assert!(matches!(Sparkline::new(0).unwrap_err(), SparkError::HeightZero));
    }

    #[test]
    fn empty_returns_empty() {
        let s = Sparkline::new(20).unwrap();
        assert!(s.bar_heights().is_empty());
    }

    #[test]
    fn constant_returns_midline() {
        let mut s = Sparkline::new(20).unwrap();
        for _ in 0..5 { s.push(7.0); }
        let h = s.bar_heights();
        for v in &h { assert_eq!(*v, 10); }
    }

    #[test]
    fn ascending_grows() {
        let mut s = Sparkline::new(100).unwrap();
        for v in 0..10 { s.push(v as f64); }
        let h = s.bar_heights();
        assert_eq!(h[0], 0);
        assert_eq!(h[9], 100);
    }

    #[test]
    fn nan_treated_as_zero() {
        let mut s = Sparkline::new(10).unwrap();
        s.push(f64::NAN);
        s.push(10.0);
        let h = s.bar_heights();
        assert_eq!(h.len(), 2);
        assert_eq!(h[0], 0);
        assert_eq!(h[1], 10);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = Sparkline::new(10).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SparkError::SchemaMismatch));
    }

    #[test]
    fn spark_serde_roundtrip() {
        let mut s = Sparkline::new(20).unwrap();
        s.push(1.0); s.push(2.0);
        let j = serde_json::to_string(&s).unwrap();
        let back: Sparkline = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
