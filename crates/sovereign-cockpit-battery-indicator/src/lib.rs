//! `sovereign-cockpit-battery-indicator` — battery state for the cockpit chrome.
//!
//! Tracks pct + charge state + low/critical thresholds + a naive
//! time-to-empty / time-to-full estimate computed from the last sample
//! delta. Pure presentation crate.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Charge state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ChargeState {
    /// Charging from external power.
    Charging,
    /// Discharging on battery.
    Discharging,
    /// Plugged in and at 100%.
    Full,
    /// Sensor not reporting.
    Unknown,
}

/// Severity zone (mirror).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Ord, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Zone {
    /// Normal.
    Normal,
    /// Low.
    Low,
    /// Critical.
    Critical,
}

/// One observation.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Sample {
    /// monotonic timestamp ms.
    pub ts_ms: u64,
    /// pct 0..=100.
    pub pct: u8,
    /// state at sample time.
    pub state: ChargeState,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BatteryIndicator {
    /// Schema version.
    pub schema_version: String,
    /// Low threshold (pct).
    pub low_pct: u8,
    /// Critical threshold (pct).
    pub critical_pct: u8,
    /// Last sample if any.
    pub last: Option<Sample>,
    /// Sample before last for delta.
    pub prev: Option<Sample>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BatteryError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Pct > 100.
    #[error("pct {0} > 100")]
    PctOver100(u8),
    /// Thresholds inverted.
    #[error("low {0} <= critical {1}")]
    BadThresholds(u8, u8),
    /// Critical over 100.
    #[error("critical_pct {0} > 100")]
    CriticalOver100(u8),
    /// Timestamp not monotonic.
    #[error("non-monotonic ts: prev {prev} >= new {new}")]
    NonMonotonic {
        /// prev ts.
        prev: u64,
        /// new ts.
        new: u64,
    },
}

impl BatteryIndicator {
    /// New.
    pub fn new(low_pct: u8, critical_pct: u8) -> Result<Self, BatteryError> {
        if low_pct <= critical_pct {
            return Err(BatteryError::BadThresholds(low_pct, critical_pct));
        }
        if low_pct > 100 {
            return Err(BatteryError::PctOver100(low_pct));
        }
        if critical_pct > 100 {
            return Err(BatteryError::CriticalOver100(critical_pct));
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            low_pct,
            critical_pct,
            last: None,
            prev: None,
        })
    }

    /// Push a fresh sample.
    pub fn push(&mut self, s: Sample) -> Result<(), BatteryError> {
        if s.pct > 100 {
            return Err(BatteryError::PctOver100(s.pct));
        }
        if let Some(last) = self.last {
            if s.ts_ms <= last.ts_ms {
                return Err(BatteryError::NonMonotonic {
                    prev: last.ts_ms,
                    new: s.ts_ms,
                });
            }
            self.prev = Some(last);
        }
        self.last = Some(s);
        Ok(())
    }

    /// Current zone.
    pub fn zone(&self) -> Zone {
        match self.last {
            Some(s) if s.pct <= self.critical_pct => Zone::Critical,
            Some(s) if s.pct <= self.low_pct => Zone::Low,
            _ => Zone::Normal,
        }
    }

    /// Naive time-to-empty (ms). None if discharging unknown or state not discharging or no delta.
    pub fn time_to_empty_ms(&self) -> Option<u64> {
        let (last, prev) = (self.last?, self.prev?);
        if last.state != ChargeState::Discharging {
            return None;
        }
        if last.pct >= prev.pct {
            return None;
        }
        let drop = (prev.pct - last.pct) as u64;
        let dt = last.ts_ms.checked_sub(prev.ts_ms)?;
        if dt == 0 {
            return None;
        }
        let pct_per_ms_num = drop;
        let pct_per_ms_den = dt;
        let remaining_pct = last.pct as u64;
        Some(remaining_pct.saturating_mul(pct_per_ms_den) / pct_per_ms_num)
    }

    /// Naive time-to-full (ms).
    pub fn time_to_full_ms(&self) -> Option<u64> {
        let (last, prev) = (self.last?, self.prev?);
        if last.state != ChargeState::Charging {
            return None;
        }
        if last.pct <= prev.pct {
            return None;
        }
        let gain = (last.pct - prev.pct) as u64;
        let dt = last.ts_ms.checked_sub(prev.ts_ms)?;
        if dt == 0 {
            return None;
        }
        let remaining_pct = 100u64.saturating_sub(last.pct as u64);
        Some(remaining_pct.saturating_mul(dt) / gain)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), BatteryError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BatteryError::SchemaMismatch);
        }
        if self.low_pct <= self.critical_pct {
            return Err(BatteryError::BadThresholds(self.low_pct, self.critical_pct));
        }
        if self.low_pct > 100 {
            return Err(BatteryError::PctOver100(self.low_pct));
        }
        if self.critical_pct > 100 {
            return Err(BatteryError::CriticalOver100(self.critical_pct));
        }
        if let Some(s) = self.last {
            if s.pct > 100 {
                return Err(BatteryError::PctOver100(s.pct));
            }
        }
        if let Some(s) = self.prev {
            if s.pct > 100 {
                return Err(BatteryError::PctOver100(s.pct));
            }
        }
        if let (Some(p), Some(l)) = (self.prev, self.last) {
            if p.ts_ms >= l.ts_ms {
                return Err(BatteryError::NonMonotonic {
                    prev: p.ts_ms,
                    new: l.ts_ms,
                });
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(ts: u64, pct: u8, st: ChargeState) -> Sample {
        Sample {
            ts_ms: ts,
            pct,
            state: st,
        }
    }

    #[test]
    fn bad_thresholds_rejected() {
        assert!(matches!(
            BatteryIndicator::new(5, 20).unwrap_err(),
            BatteryError::BadThresholds(_, _)
        ));
    }

    #[test]
    fn push_and_zone_normal() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        b.push(s(100, 80, ChargeState::Discharging)).unwrap();
        assert_eq!(b.zone(), Zone::Normal);
    }

    #[test]
    fn zone_low() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        b.push(s(100, 15, ChargeState::Discharging)).unwrap();
        assert_eq!(b.zone(), Zone::Low);
    }

    #[test]
    fn zone_critical() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        b.push(s(100, 3, ChargeState::Discharging)).unwrap();
        assert_eq!(b.zone(), Zone::Critical);
    }

    #[test]
    fn pct_over_100_rejected() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        assert!(matches!(
            b.push(s(100, 200, ChargeState::Unknown)).unwrap_err(),
            BatteryError::PctOver100(_)
        ));
    }

    #[test]
    fn nonmonotonic_rejected() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        b.push(s(100, 50, ChargeState::Discharging)).unwrap();
        assert!(matches!(
            b.push(s(100, 49, ChargeState::Discharging)).unwrap_err(),
            BatteryError::NonMonotonic { .. }
        ));
    }

    #[test]
    fn time_to_empty_computes() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        b.push(s(0, 50, ChargeState::Discharging)).unwrap();
        b.push(s(60_000, 49, ChargeState::Discharging)).unwrap();
        // 1 pct per minute, 49 pct remaining → ~49 minutes.
        let t = b.time_to_empty_ms().unwrap();
        assert_eq!(t, 49 * 60_000);
    }

    #[test]
    fn time_to_empty_none_when_charging() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        b.push(s(0, 50, ChargeState::Charging)).unwrap();
        b.push(s(1000, 51, ChargeState::Charging)).unwrap();
        assert!(b.time_to_empty_ms().is_none());
    }

    #[test]
    fn time_to_full_computes() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        b.push(s(0, 80, ChargeState::Charging)).unwrap();
        b.push(s(60_000, 81, ChargeState::Charging)).unwrap();
        // 1 pct per minute, 19 pct to full → 19 minutes.
        assert_eq!(b.time_to_full_ms().unwrap(), 19 * 60_000);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            BatteryError::SchemaMismatch
        ));
    }

    #[test]
    fn battery_serde_roundtrip() {
        let mut b = BatteryIndicator::new(20, 5).unwrap();
        b.push(s(0, 80, ChargeState::Charging)).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: BatteryIndicator = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
