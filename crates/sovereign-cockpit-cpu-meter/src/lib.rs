//! `sovereign-cockpit-cpu-meter` — CPU/load gauge.
//!
//! Records per-sample load (0..=100 % per core average). Emits
//! current, smoothed (last-N average), and color tier
//! (Green / Yellow / Red).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Color tier.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Tier {
    /// Green (low load).
    Green,
    /// Yellow (medium).
    Yellow,
    /// Red (high).
    Red,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CpuMeter {
    /// Schema version.
    pub schema_version: String,
    /// Sample ring (oldest first).
    pub samples: Vec<u8>,
    /// Max ring length.
    pub window: u32,
    /// Smoothing window for tier (count of newest samples averaged).
    pub smoothing_window: u32,
    /// Yellow threshold (%).
    pub yellow_pct: u8,
    /// Red threshold (%).
    pub red_pct: u8,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MeterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// window zero.
    #[error("window is zero")]
    WindowZero,
    /// smoothing > window.
    #[error("smoothing_window {0} > window {1}")]
    SmoothingExceedsWindow(u32, u32),
    /// Bad thresholds.
    #[error("yellow {0} >= red {1}")]
    BadThresholds(u8, u8),
    /// Sample > 100.
    #[error("sample {0} > 100")]
    SampleOverflow(u8),
}

impl CpuMeter {
    /// New.
    pub fn new(
        window: u32,
        smoothing_window: u32,
        yellow_pct: u8,
        red_pct: u8,
    ) -> Result<Self, MeterError> {
        if window == 0 {
            return Err(MeterError::WindowZero);
        }
        if smoothing_window > window {
            return Err(MeterError::SmoothingExceedsWindow(smoothing_window, window));
        }
        if yellow_pct >= red_pct {
            return Err(MeterError::BadThresholds(yellow_pct, red_pct));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            samples: Vec::new(),
            window,
            smoothing_window,
            yellow_pct,
            red_pct,
        })
    }

    /// Record a sample.
    pub fn record(&mut self, pct: u8) -> Result<(), MeterError> {
        if pct > 100 {
            return Err(MeterError::SampleOverflow(pct));
        }
        self.samples.push(pct);
        while (self.samples.len() as u32) > self.window {
            self.samples.remove(0);
        }
        Ok(())
    }

    /// Current sample (last); 0 if empty.
    pub fn current(&self) -> u8 {
        *self.samples.last().unwrap_or(&0)
    }

    /// Smoothed average over last smoothing_window samples (or all if fewer).
    pub fn smoothed(&self) -> u8 {
        if self.samples.is_empty() {
            return 0;
        }
        let n = self.smoothing_window as usize;
        let tail = if self.samples.len() > n {
            &self.samples[self.samples.len() - n..]
        } else {
            &self.samples[..]
        };
        let sum: u32 = tail.iter().map(|s| *s as u32).sum();
        (sum / tail.len() as u32) as u8
    }

    /// Color tier from smoothed.
    pub fn tier(&self) -> Tier {
        let s = self.smoothed();
        if s >= self.red_pct {
            Tier::Red
        } else if s >= self.yellow_pct {
            Tier::Yellow
        } else {
            Tier::Green
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MeterError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MeterError::SchemaMismatch);
        }
        if self.window == 0 {
            return Err(MeterError::WindowZero);
        }
        if self.smoothing_window > self.window {
            return Err(MeterError::SmoothingExceedsWindow(
                self.smoothing_window,
                self.window,
            ));
        }
        if self.yellow_pct >= self.red_pct {
            return Err(MeterError::BadThresholds(self.yellow_pct, self.red_pct));
        }
        for s in &self.samples {
            if *s > 100 {
                return Err(MeterError::SampleOverflow(*s));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn window_zero_rejected() {
        assert!(matches!(
            CpuMeter::new(0, 0, 70, 90).unwrap_err(),
            MeterError::WindowZero
        ));
    }

    #[test]
    fn smoothing_over_window_rejected() {
        assert!(matches!(
            CpuMeter::new(5, 10, 70, 90).unwrap_err(),
            MeterError::SmoothingExceedsWindow(_, _)
        ));
    }

    #[test]
    fn bad_thresholds_rejected() {
        assert!(matches!(
            CpuMeter::new(5, 3, 90, 70).unwrap_err(),
            MeterError::BadThresholds(_, _)
        ));
    }

    #[test]
    fn record_sample_over_100_rejected() {
        let mut m = CpuMeter::new(5, 3, 70, 90).unwrap();
        assert!(matches!(
            m.record(150).unwrap_err(),
            MeterError::SampleOverflow(_)
        ));
    }

    #[test]
    fn current_and_smoothed() {
        let mut m = CpuMeter::new(5, 3, 70, 90).unwrap();
        for v in [10u8, 20, 30, 40, 50] {
            m.record(v).unwrap();
        }
        assert_eq!(m.current(), 50);
        // Smoothed over last 3 = (30+40+50)/3 = 40
        assert_eq!(m.smoothed(), 40);
    }

    #[test]
    fn tier_green() {
        let mut m = CpuMeter::new(5, 3, 70, 90).unwrap();
        for _ in 0..3 {
            m.record(20).unwrap();
        }
        assert_eq!(m.tier(), Tier::Green);
    }

    #[test]
    fn tier_yellow() {
        let mut m = CpuMeter::new(5, 3, 70, 90).unwrap();
        for _ in 0..3 {
            m.record(80).unwrap();
        }
        assert_eq!(m.tier(), Tier::Yellow);
    }

    #[test]
    fn tier_red() {
        let mut m = CpuMeter::new(5, 3, 70, 90).unwrap();
        for _ in 0..3 {
            m.record(95).unwrap();
        }
        assert_eq!(m.tier(), Tier::Red);
    }

    #[test]
    fn window_evicts() {
        let mut m = CpuMeter::new(3, 2, 70, 90).unwrap();
        for v in [10u8, 20, 30, 40] {
            m.record(v).unwrap();
        }
        assert_eq!(m.samples.len(), 3);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = CpuMeter::new(5, 3, 70, 90).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            MeterError::SchemaMismatch
        ));
    }

    #[test]
    fn meter_serde_roundtrip() {
        let mut m = CpuMeter::new(5, 3, 70, 90).unwrap();
        m.record(40).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: CpuMeter = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
