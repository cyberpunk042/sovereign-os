//! `sovereign-cockpit-cost-meter` — budget gauge.
//!
//! used / budget tracked as u64 (any unit). State{Normal/
//! Warning/Critical/Exceeded} derived from used/budget vs
//! warning_bp + critical_bp. Exceeded when used >= budget.
//! charge(n) increments used.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Level {
    /// Normal.
    Normal,
    /// Warning.
    Warning,
    /// Critical.
    Critical,
    /// Exceeded.
    Exceeded,
}

/// Meter state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CostMeter {
    /// Schema version.
    pub schema_version: String,
    /// Budget (in arbitrary units).
    pub budget: u64,
    /// Used.
    pub used: u64,
    /// Warning threshold (bp).
    pub warning_bp: u32,
    /// Critical threshold (bp).
    pub critical_bp: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CostError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Zero budget.
    #[error("budget must be >= 1")]
    ZeroBudget,
    /// Bad thresholds.
    #[error("warning_bp must be < critical_bp <= 10000")]
    BadThresholds,
}

impl CostMeter {
    /// New.
    pub fn new(budget: u64, warning_bp: u32, critical_bp: u32) -> Result<Self, CostError> {
        if budget == 0 {
            return Err(CostError::ZeroBudget);
        }
        if !(warning_bp < critical_bp && critical_bp <= 10_000) {
            return Err(CostError::BadThresholds);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            budget,
            used: 0,
            warning_bp,
            critical_bp,
        })
    }

    /// Charge n; returns new used.
    pub fn charge(&mut self, n: u64) -> u64 {
        self.used = self.used.saturating_add(n);
        self.used
    }

    /// Reset used.
    pub fn reset(&mut self) {
        self.used = 0;
    }

    /// Usage in bp (0..10000+).
    pub fn usage_bp(&self) -> u32 {
        let ratio = (self.used as u128 * 10_000) / self.budget as u128;
        ratio.min(u32::MAX as u128) as u32
    }

    /// Level classification.
    pub fn level(&self) -> Level {
        if self.used >= self.budget {
            return Level::Exceeded;
        }
        let bp = self.usage_bp();
        if bp >= self.critical_bp {
            Level::Critical
        } else if bp >= self.warning_bp {
            Level::Warning
        } else {
            Level::Normal
        }
    }

    /// Remaining budget (saturating).
    pub fn remaining(&self) -> u64 {
        self.budget.saturating_sub(self.used)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CostError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CostError::SchemaMismatch);
        }
        if self.budget == 0 {
            return Err(CostError::ZeroBudget);
        }
        if !(self.warning_bp < self.critical_bp && self.critical_bp <= 10_000) {
            return Err(CostError::BadThresholds);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn meter() -> CostMeter {
        // budget=1000, warn=5000bp(50%), crit=9000bp(90%).
        CostMeter::new(1000, 5000, 9000).unwrap()
    }

    #[test]
    fn normal_under_warn() {
        let mut m = meter();
        m.charge(200);
        assert_eq!(m.level(), Level::Normal);
    }

    #[test]
    fn warning_at_threshold() {
        let mut m = meter();
        m.charge(500);
        assert_eq!(m.level(), Level::Warning);
    }

    #[test]
    fn critical_above_threshold() {
        let mut m = meter();
        m.charge(900);
        assert_eq!(m.level(), Level::Critical);
    }

    #[test]
    fn exceeded_when_at_budget() {
        let mut m = meter();
        m.charge(1000);
        assert_eq!(m.level(), Level::Exceeded);
    }

    #[test]
    fn over_budget_still_exceeded() {
        let mut m = meter();
        m.charge(2000);
        assert_eq!(m.level(), Level::Exceeded);
    }

    #[test]
    fn remaining_correct() {
        let mut m = meter();
        m.charge(300);
        assert_eq!(m.remaining(), 700);
    }

    #[test]
    fn reset_clears() {
        let mut m = meter();
        m.charge(500);
        m.reset();
        assert_eq!(m.used, 0);
        assert_eq!(m.level(), Level::Normal);
    }

    #[test]
    fn bad_inputs_rejected() {
        assert!(matches!(
            CostMeter::new(0, 5000, 9000).unwrap_err(),
            CostError::ZeroBudget
        ));
        assert!(matches!(
            CostMeter::new(1000, 9000, 5000).unwrap_err(),
            CostError::BadThresholds
        ));
        assert!(matches!(
            CostMeter::new(1000, 5000, 10001).unwrap_err(),
            CostError::BadThresholds
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = meter();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            CostError::SchemaMismatch
        ));
    }

    #[test]
    fn meter_serde_roundtrip() {
        let mut m = meter();
        m.charge(500);
        let j = serde_json::to_string(&m).unwrap();
        let back: CostMeter = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
