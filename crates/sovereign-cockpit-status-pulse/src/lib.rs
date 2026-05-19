//! `sovereign-cockpit-status-pulse` — triangular-wave pulse.
//!
//! brightness_pct(now_ms) returns 0..=100 along a triangular wave
//! with operator-configured period. active=false → static_brightness.
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
pub struct StatusPulse {
    /// Schema version.
    pub schema_version: String,
    /// Pulse period (ms).
    pub period_ms: u32,
    /// Min brightness % during pulse.
    pub min_pct: u8,
    /// Max brightness % during pulse.
    pub max_pct: u8,
    /// Static brightness when not active.
    pub static_pct: u8,
    /// Active?
    pub active: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PulseError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// period zero.
    #[error("period_ms is zero")]
    PeriodZero,
    /// min > max.
    #[error("min_pct {0} > max_pct {1}")]
    BadRange(u8, u8),
    /// pct > 100.
    #[error("pct {0} > 100")]
    PctOver100(u8),
}

impl StatusPulse {
    /// New.
    pub fn new(period_ms: u32, min_pct: u8, max_pct: u8, static_pct: u8, active: bool) -> Result<Self, PulseError> {
        if period_ms == 0 { return Err(PulseError::PeriodZero); }
        if min_pct > max_pct { return Err(PulseError::BadRange(min_pct, max_pct)); }
        for p in [min_pct, max_pct, static_pct] {
            if p > 100 { return Err(PulseError::PctOver100(p)); }
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            period_ms, min_pct, max_pct, static_pct, active,
        })
    }

    /// Brightness percent at now.
    pub fn brightness_pct(&self, now_ms: u64) -> u8 {
        if !self.active { return self.static_pct; }
        let phase = (now_ms % self.period_ms as u64) as u32;
        let half = self.period_ms / 2;
        // Triangular wave: 0..half goes min->max, half..period goes max->min.
        let span = self.max_pct.saturating_sub(self.min_pct) as u32;
        let t = if phase < half {
            (phase * span) / half
        } else {
            span - ((phase - half) * span) / half.max(1)
        };
        self.min_pct.saturating_add(t as u8).min(self.max_pct)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PulseError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PulseError::SchemaMismatch);
        }
        if self.period_ms == 0 { return Err(PulseError::PeriodZero); }
        if self.min_pct > self.max_pct { return Err(PulseError::BadRange(self.min_pct, self.max_pct)); }
        for p in [self.min_pct, self.max_pct, self.static_pct] {
            if p > 100 { return Err(PulseError::PctOver100(p)); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn period_zero_rejected() {
        assert!(matches!(StatusPulse::new(0, 30, 100, 50, true).unwrap_err(), PulseError::PeriodZero));
    }

    #[test]
    fn bad_range_rejected() {
        assert!(matches!(StatusPulse::new(1000, 80, 30, 50, true).unwrap_err(), PulseError::BadRange(80, 30)));
    }

    #[test]
    fn pct_over_100_rejected() {
        assert!(matches!(StatusPulse::new(1000, 30, 150, 50, true).unwrap_err(), PulseError::PctOver100(150)));
    }

    #[test]
    fn inactive_returns_static() {
        let s = StatusPulse::new(1000, 30, 100, 50, false).unwrap();
        for t in [0u64, 500, 999, 1500] {
            assert_eq!(s.brightness_pct(t), 50);
        }
    }

    #[test]
    fn at_phase_zero_is_min() {
        let s = StatusPulse::new(1000, 30, 100, 50, true).unwrap();
        assert_eq!(s.brightness_pct(0), 30);
    }

    #[test]
    fn at_phase_half_is_max() {
        let s = StatusPulse::new(1000, 30, 100, 50, true).unwrap();
        assert_eq!(s.brightness_pct(500), 100);
    }

    #[test]
    fn returns_to_min_at_period() {
        let s = StatusPulse::new(1000, 30, 100, 50, true).unwrap();
        assert_eq!(s.brightness_pct(1000), 30);
    }

    #[test]
    fn brightness_in_bounds_throughout_period() {
        let s = StatusPulse::new(1000, 30, 90, 50, true).unwrap();
        for t in 0..1000 {
            let b = s.brightness_pct(t);
            assert!(b >= 30 && b <= 90, "t={t} b={b}");
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = StatusPulse::new(1000, 30, 100, 50, true).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), PulseError::SchemaMismatch));
    }

    #[test]
    fn pulse_serde_roundtrip() {
        let s = StatusPulse::new(1000, 30, 100, 50, true).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: StatusPulse = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
