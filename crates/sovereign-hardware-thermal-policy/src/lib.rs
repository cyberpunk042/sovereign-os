//! `sovereign-hardware-thermal-policy` — per-target thermal verdict policy.
//!
//! Each of the 5 HardwareTargets declares 3 thermal thresholds in °C:
//!
//! - `warn_c`     — visual warning on the cockpit dashboard
//! - `throttle_c` — SRP scheduler defers low-priority dispatch
//! - `shutdown_c` — SRP scheduler quarantines the target until temp drops
//!
//! Given a current temp_c reading (from `sovereign-hardware-load-sample`),
//! the policy returns a `ThermalVerdict` (Cool / Warm / Throttle / Shutdown).
//!
//! Cloud + NoHardware targets are always Cool (no thermal signal).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_hardware_load_sample::LoadSnapshot;
use sovereign_hardware_registry::HardwareTarget;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Thermal verdict.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ThermalVerdict {
    /// Below warn threshold.
    Cool,
    /// Above warn, below throttle.
    Warm,
    /// Above throttle, below shutdown.
    Throttle,
    /// Above shutdown — must quarantine target.
    Shutdown,
}

/// Per-target thermal thresholds.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ThermalThresholds {
    /// Target.
    pub target: HardwareTarget,
    /// Warn at this temp (°C).
    pub warn_c: u8,
    /// Throttle at this temp (must be > warn_c).
    pub throttle_c: u8,
    /// Shutdown at this temp (must be > throttle_c).
    pub shutdown_c: u8,
}

/// 5-target thermal policy.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ThermalPolicy {
    /// Schema version.
    pub schema_version: String,
    /// Exactly 5 thresholds.
    pub thresholds: Vec<ThermalThresholds>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ThermalError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 5.
    #[error("threshold count {0} != 5 canonical")]
    CountInvalid(usize),
    /// Missing target.
    #[error("missing thermal thresholds for: {0:?}")]
    Missing(HardwareTarget),
    /// Thresholds not monotonic warn < throttle < shutdown.
    #[error(
        "thresholds non-monotonic for {target:?}: warn={warn} throttle={throttle} shutdown={shutdown}"
    )]
    NonMonotonic {
        /// Target.
        target: HardwareTarget,
        /// Warn.
        warn: u8,
        /// Throttle.
        throttle: u8,
        /// Shutdown.
        shutdown: u8,
    },
}

impl ThermalThresholds {
    /// Evaluate a temp reading.
    pub fn evaluate(&self, temp_c: u8) -> ThermalVerdict {
        if temp_c >= self.shutdown_c {
            ThermalVerdict::Shutdown
        } else if temp_c >= self.throttle_c {
            ThermalVerdict::Throttle
        } else if temp_c >= self.warn_c {
            ThermalVerdict::Warm
        } else {
            ThermalVerdict::Cool
        }
    }
}

impl ThermalPolicy {
    /// Canonical thresholds — silicon-typical defaults.
    /// CPU: 75/88/95. RDNA 4090: 78/85/95. Blackwell: 80/90/105.
    /// Cloud + NoHardware are always Cool (255/255/255 sentinels).
    pub fn canonical() -> Self {
        let thresholds = vec![
            ThermalThresholds {
                target: HardwareTarget::CpuPulse,
                warn_c: 75,
                throttle_c: 88,
                shutdown_c: 95,
            },
            ThermalThresholds {
                target: HardwareTarget::Rocm4090,
                warn_c: 78,
                throttle_c: 85,
                shutdown_c: 95,
            },
            ThermalThresholds {
                target: HardwareTarget::BlackwellOracle,
                warn_c: 80,
                throttle_c: 90,
                shutdown_c: 105,
            },
            ThermalThresholds {
                target: HardwareTarget::Cloud,
                warn_c: 253,
                throttle_c: 254,
                shutdown_c: 255,
            },
            ThermalThresholds {
                target: HardwareTarget::NoHardware,
                warn_c: 253,
                throttle_c: 254,
                shutdown_c: 255,
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            thresholds,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ThermalError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ThermalError::SchemaMismatch);
        }
        if self.thresholds.len() != 5 {
            return Err(ThermalError::CountInvalid(self.thresholds.len()));
        }
        let required = [
            HardwareTarget::CpuPulse,
            HardwareTarget::Rocm4090,
            HardwareTarget::BlackwellOracle,
            HardwareTarget::Cloud,
            HardwareTarget::NoHardware,
        ];
        for t in required {
            if !self.thresholds.iter().any(|th| th.target == t) {
                return Err(ThermalError::Missing(t));
            }
        }
        for th in &self.thresholds {
            if !(th.warn_c < th.throttle_c && th.throttle_c < th.shutdown_c) {
                return Err(ThermalError::NonMonotonic {
                    target: th.target,
                    warn: th.warn_c,
                    throttle: th.throttle_c,
                    shutdown: th.shutdown_c,
                });
            }
        }
        Ok(())
    }

    /// Lookup by target.
    pub fn get(&self, t: HardwareTarget) -> Option<&ThermalThresholds> {
        self.thresholds.iter().find(|th| th.target == t)
    }

    /// Evaluate a single sample.
    pub fn evaluate(&self, t: HardwareTarget, temp_c: u8) -> ThermalVerdict {
        match self.get(t) {
            Some(th) => th.evaluate(temp_c),
            None => ThermalVerdict::Cool,
        }
    }

    /// Evaluate the full load snapshot — returns 5-target verdict tuples.
    pub fn evaluate_snapshot(&self, load: &LoadSnapshot) -> Vec<(HardwareTarget, ThermalVerdict)> {
        load.loads
            .iter()
            .map(|l| (l.target, self.evaluate(l.target, l.temp_c)))
            .collect()
    }

    /// True if any target is in Shutdown verdict.
    pub fn any_shutdown(&self, load: &LoadSnapshot) -> bool {
        self.evaluate_snapshot(load)
            .iter()
            .any(|(_, v)| *v == ThermalVerdict::Shutdown)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        ThermalPolicy::canonical().validate().unwrap();
    }

    #[test]
    fn cool_below_warn() {
        let p = ThermalPolicy::canonical();
        assert_eq!(
            p.evaluate(HardwareTarget::CpuPulse, 60),
            ThermalVerdict::Cool
        );
    }

    #[test]
    fn warm_band() {
        let p = ThermalPolicy::canonical();
        // CpuPulse: warn=75, throttle=88
        assert_eq!(
            p.evaluate(HardwareTarget::CpuPulse, 75),
            ThermalVerdict::Warm
        );
        assert_eq!(
            p.evaluate(HardwareTarget::CpuPulse, 80),
            ThermalVerdict::Warm
        );
        assert_eq!(
            p.evaluate(HardwareTarget::CpuPulse, 87),
            ThermalVerdict::Warm
        );
    }

    #[test]
    fn throttle_band() {
        let p = ThermalPolicy::canonical();
        // CpuPulse: throttle=88, shutdown=95
        assert_eq!(
            p.evaluate(HardwareTarget::CpuPulse, 88),
            ThermalVerdict::Throttle
        );
        assert_eq!(
            p.evaluate(HardwareTarget::CpuPulse, 90),
            ThermalVerdict::Throttle
        );
    }

    #[test]
    fn shutdown_at_or_above() {
        let p = ThermalPolicy::canonical();
        assert_eq!(
            p.evaluate(HardwareTarget::CpuPulse, 95),
            ThermalVerdict::Shutdown
        );
        assert_eq!(
            p.evaluate(HardwareTarget::CpuPulse, 110),
            ThermalVerdict::Shutdown
        );
    }

    #[test]
    fn cloud_and_none_always_cool() {
        let p = ThermalPolicy::canonical();
        assert_eq!(p.evaluate(HardwareTarget::Cloud, 0), ThermalVerdict::Cool);
        assert_eq!(
            p.evaluate(HardwareTarget::NoHardware, 0),
            ThermalVerdict::Cool
        );
        // Even at 200°C (impossible but) they stay below sentinel warn=253.
        assert_eq!(p.evaluate(HardwareTarget::Cloud, 200), ThermalVerdict::Cool);
    }

    #[test]
    fn evaluate_snapshot_returns_five() {
        let p = ThermalPolicy::canonical();
        let load = LoadSnapshot::empty_canonical("t");
        let r = p.evaluate_snapshot(&load);
        assert_eq!(r.len(), 5);
        assert!(r.iter().all(|(_, v)| *v == ThermalVerdict::Cool));
    }

    #[test]
    fn any_shutdown_detects_overheat() {
        let p = ThermalPolicy::canonical();
        let mut load = LoadSnapshot::empty_canonical("t");
        for l in load.loads.iter_mut() {
            if l.target == HardwareTarget::BlackwellOracle {
                l.temp_c = 110;
            }
        }
        assert!(p.any_shutdown(&load));
    }

    #[test]
    fn non_monotonic_rejected() {
        let mut p = ThermalPolicy::canonical();
        p.thresholds[0].warn_c = 90;
        p.thresholds[0].throttle_c = 88; // now warn > throttle
        match p.validate().unwrap_err() {
            ThermalError::NonMonotonic { target, .. } => {
                assert_eq!(target, HardwareTarget::CpuPulse);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ThermalPolicy::canonical();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            ThermalError::SchemaMismatch
        ));
    }

    #[test]
    fn count_invalid_caught() {
        let mut p = ThermalPolicy::canonical();
        p.thresholds.pop();
        assert!(matches!(
            p.validate().unwrap_err(),
            ThermalError::CountInvalid(4)
        ));
    }

    #[test]
    fn verdict_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ThermalVerdict::Cool).unwrap(),
            "\"cool\""
        );
        assert_eq!(
            serde_json::to_string(&ThermalVerdict::Throttle).unwrap(),
            "\"throttle\""
        );
        assert_eq!(
            serde_json::to_string(&ThermalVerdict::Shutdown).unwrap(),
            "\"shutdown\""
        );
    }

    #[test]
    fn policy_serde_roundtrip() {
        let p = ThermalPolicy::canonical();
        let j = serde_json::to_string(&p).unwrap();
        let back: ThermalPolicy = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
