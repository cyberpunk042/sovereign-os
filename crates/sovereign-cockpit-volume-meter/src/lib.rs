//! `sovereign-cockpit-volume-meter` — audio level meter.
//!
//! Level: 0..=10000 bp (0..100%). observe(sample, now_ms) sets
//! current level and updates peak; peak holds for hold_ms then
//! decays by decay_bp_per_sec each second. tick(now_ms) just
//! decays the peak without updating the current level.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct VolumeMeter {
    /// Schema version.
    pub schema_version: String,
    /// Current level (bp 0..=10000).
    pub level_bp: u32,
    /// Peak level (bp 0..=10000).
    pub peak_bp: u32,
    /// When peak was last updated.
    pub peak_ts_ms: u64,
    /// Hold time before peak decays (ms).
    pub hold_ms: u64,
    /// Decay rate (bp/s) after hold.
    pub decay_bp_per_sec: u32,
    /// Last tick/observe ts.
    pub last_ts_ms: u64,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MeterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Bad bp.
    #[error("bp must be 0..=10000")]
    BadBp,
}

impl VolumeMeter {
    /// New.
    pub fn new(hold_ms: u64, decay_bp_per_sec: u32) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            level_bp: 0,
            peak_bp: 0,
            peak_ts_ms: 0,
            hold_ms,
            decay_bp_per_sec,
            last_ts_ms: 0,
        }
    }

    /// Apply hold + decay relative to now_ms.
    fn decay_peak(&mut self, now_ms: u64) {
        let since_peak = now_ms.saturating_sub(self.peak_ts_ms);
        if since_peak <= self.hold_ms {
            return;
        }
        let decay_window = since_peak - self.hold_ms;
        // Decay amount (bp) = decay_bp_per_sec * decay_window_ms / 1000
        let decay = ((self.decay_bp_per_sec as u64).saturating_mul(decay_window) / 1000) as u32;
        self.peak_bp = self.peak_bp.saturating_sub(decay);
        // Roll the peak_ts_ms forward to the end of the decay window so we don't double-decay.
        self.peak_ts_ms = now_ms.saturating_sub(self.hold_ms);
    }

    /// Observe sample (bp).
    pub fn observe(&mut self, sample_bp: u32, now_ms: u64) -> Result<(), MeterError> {
        if sample_bp > 10000 { return Err(MeterError::BadBp); }
        // First decay before lifting peak.
        self.decay_peak(now_ms);
        self.level_bp = sample_bp;
        if sample_bp > self.peak_bp {
            self.peak_bp = sample_bp;
            self.peak_ts_ms = now_ms;
        }
        self.last_ts_ms = now_ms;
        Ok(())
    }

    /// Decay-only tick.
    pub fn tick(&mut self, now_ms: u64) {
        self.decay_peak(now_ms);
        self.last_ts_ms = now_ms;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MeterError> {
        if self.schema_version != SCHEMA_VERSION { return Err(MeterError::SchemaMismatch); }
        if self.level_bp > 10000 || self.peak_bp > 10000 { return Err(MeterError::BadBp); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_is_zero() {
        let m = VolumeMeter::new(500, 1000);
        assert_eq!(m.level_bp, 0);
        assert_eq!(m.peak_bp, 0);
    }

    #[test]
    fn observe_sets_level_and_peak() {
        let mut m = VolumeMeter::new(500, 1000);
        m.observe(7000, 0).unwrap();
        assert_eq!(m.level_bp, 7000);
        assert_eq!(m.peak_bp, 7000);
    }

    #[test]
    fn peak_holds_during_hold_window() {
        let mut m = VolumeMeter::new(500, 1000);
        m.observe(8000, 0).unwrap();
        m.observe(2000, 400).unwrap();
        // Within hold window: peak should remain 8000.
        assert_eq!(m.level_bp, 2000);
        assert_eq!(m.peak_bp, 8000);
    }

    #[test]
    fn peak_decays_after_hold() {
        let mut m = VolumeMeter::new(500, 1000); // decay 1000 bp/sec
        m.observe(8000, 0).unwrap();
        // At t=1500 ms: 1500-500 = 1000 ms decay window → 1000 bp decay → peak=7000
        m.tick(1500);
        assert_eq!(m.peak_bp, 7000);
    }

    #[test]
    fn lower_sample_does_not_raise_peak() {
        let mut m = VolumeMeter::new(500, 1000);
        m.observe(8000, 0).unwrap();
        m.observe(5000, 100).unwrap();
        assert_eq!(m.peak_bp, 8000);
    }

    #[test]
    fn higher_sample_raises_peak() {
        let mut m = VolumeMeter::new(500, 1000);
        m.observe(3000, 0).unwrap();
        m.observe(9000, 100).unwrap();
        assert_eq!(m.peak_bp, 9000);
    }

    #[test]
    fn out_of_range_rejected() {
        let mut m = VolumeMeter::new(500, 1000);
        assert!(matches!(m.observe(10001, 0).unwrap_err(), MeterError::BadBp));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = VolumeMeter::new(500, 1000);
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), MeterError::SchemaMismatch));
    }

    #[test]
    fn meter_serde_roundtrip() {
        let mut m = VolumeMeter::new(500, 1000);
        m.observe(4000, 100).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: VolumeMeter = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
