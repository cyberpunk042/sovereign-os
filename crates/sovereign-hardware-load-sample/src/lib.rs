//! `sovereign-hardware-load-sample` — per-target runtime load snapshot.
//!
//! For each of the 5 canonical hardware targets (from
//! `sovereign-hardware-registry`), captures a sample of VRAM used,
//! compute utilization (0..100), and thermal reading (°C). The SRP
//! scheduler consumes the bundle to decide dispatch; the cockpit
//! dashboard renders it on the hardware tile.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_hardware_registry::{HardwareRegistry, HardwareTarget};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-target load sample.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TargetLoad {
    /// Hardware target.
    pub target: HardwareTarget,
    /// VRAM used (GB); 0 for non-VRAM targets.
    pub vram_used_gb: u32,
    /// Compute utilization (0..=100).
    pub util_pct: u8,
    /// Thermal reading (°C); 0 for cloud/none.
    pub temp_c: u8,
    /// ISO-8601 UTC timestamp the sample was captured.
    pub captured_at: String,
}

/// 5-target load snapshot bundle.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LoadSnapshot {
    /// Schema version.
    pub schema_version: String,
    /// ISO-8601 UTC wall-clock for the bundle.
    pub captured_at: String,
    /// One load per HardwareTarget (exactly 5).
    pub loads: Vec<TargetLoad>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LoadError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 5.
    #[error("load count {0} != 5 canonical")]
    CountInvalid(usize),
    /// Missing target.
    #[error("missing load for target: {0:?}")]
    Missing(HardwareTarget),
    /// Util out of range.
    #[error("util_pct {pct} out of range for {target:?}")]
    UtilOutOfRange {
        /// Target.
        target: HardwareTarget,
        /// Percent.
        pct: u8,
    },
    /// VRAM used exceeds capacity declared in the registry.
    #[error("vram_used {used} > capacity {cap} for {target:?}")]
    VramOverflow {
        /// Target.
        target: HardwareTarget,
        /// Used GB.
        used: u32,
        /// Capacity GB.
        cap: u32,
    },
}

impl LoadSnapshot {
    /// Empty canonical — all targets at zero load.
    pub fn empty_canonical(at: &str) -> Self {
        let loads = [
            HardwareTarget::CpuPulse,
            HardwareTarget::Rocm4090,
            HardwareTarget::BlackwellOracle,
            HardwareTarget::Cloud,
            HardwareTarget::NoHardware,
        ]
        .into_iter()
        .map(|t| TargetLoad {
            target: t,
            vram_used_gb: 0,
            util_pct: 0,
            temp_c: 0,
            captured_at: at.into(),
        })
        .collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            captured_at: at.into(),
            loads,
        }
    }

    /// Validate against the registry's declared capacities.
    pub fn validate_against(&self, registry: &HardwareRegistry) -> Result<(), LoadError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LoadError::SchemaMismatch);
        }
        if self.loads.len() != 5 {
            return Err(LoadError::CountInvalid(self.loads.len()));
        }
        let required = [
            HardwareTarget::CpuPulse,
            HardwareTarget::Rocm4090,
            HardwareTarget::BlackwellOracle,
            HardwareTarget::Cloud,
            HardwareTarget::NoHardware,
        ];
        for t in required {
            if !self.loads.iter().any(|l| l.target == t) {
                return Err(LoadError::Missing(t));
            }
        }
        for l in &self.loads {
            if l.util_pct > 100 {
                return Err(LoadError::UtilOutOfRange {
                    target: l.target,
                    pct: l.util_pct,
                });
            }
            if let Some(rec) = registry.get(l.target)
                && l.vram_used_gb > rec.vram_gb
            {
                return Err(LoadError::VramOverflow {
                    target: l.target,
                    used: l.vram_used_gb,
                    cap: rec.vram_gb,
                });
            }
        }
        Ok(())
    }

    /// Sum of VRAM used across all local targets (excludes Cloud + None).
    pub fn total_local_vram_used_gb(&self) -> u32 {
        self.loads
            .iter()
            .filter(|l| !matches!(l.target, HardwareTarget::Cloud | HardwareTarget::NoHardware))
            .map(|l| l.vram_used_gb)
            .sum()
    }

    /// Average compute utilization across all targets (0..=100).
    pub fn avg_util_pct(&self) -> u8 {
        if self.loads.is_empty() {
            return 0;
        }
        let sum: u32 = self.loads.iter().map(|l| l.util_pct as u32).sum();
        (sum / self.loads.len() as u32) as u8
    }

    /// Lookup by target.
    pub fn get(&self, t: HardwareTarget) -> Option<&TargetLoad> {
        self.loads.iter().find(|l| l.target == t)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn reg() -> HardwareRegistry {
        HardwareRegistry::canonical()
    }

    #[test]
    fn empty_canonical_validates() {
        let s = LoadSnapshot::empty_canonical("2026-05-19T03:00:00Z");
        s.validate_against(&reg()).unwrap();
    }

    #[test]
    fn five_loads_present() {
        let s = LoadSnapshot::empty_canonical("2026-05-19T03:00:00Z");
        assert_eq!(s.loads.len(), 5);
        for t in [
            HardwareTarget::CpuPulse,
            HardwareTarget::Rocm4090,
            HardwareTarget::BlackwellOracle,
            HardwareTarget::Cloud,
            HardwareTarget::NoHardware,
        ] {
            assert!(s.get(t).is_some(), "missing {t:?}");
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = LoadSnapshot::empty_canonical("t");
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate_against(&reg()).unwrap_err(),
            LoadError::SchemaMismatch
        ));
    }

    #[test]
    fn count_invalid_caught() {
        let mut s = LoadSnapshot::empty_canonical("t");
        s.loads.pop();
        assert!(matches!(
            s.validate_against(&reg()).unwrap_err(),
            LoadError::CountInvalid(4)
        ));
    }

    #[test]
    fn util_out_of_range_caught() {
        let mut s = LoadSnapshot::empty_canonical("t");
        s.loads[0].util_pct = 150;
        match s.validate_against(&reg()).unwrap_err() {
            LoadError::UtilOutOfRange { target, pct } => {
                assert_eq!(target, HardwareTarget::CpuPulse);
                assert_eq!(pct, 150);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn vram_overflow_caught() {
        let mut s = LoadSnapshot::empty_canonical("t");
        // rocm-4090 has 24GB capacity in canonical registry
        for l in s.loads.iter_mut() {
            if l.target == HardwareTarget::Rocm4090 {
                l.vram_used_gb = 30;
            }
        }
        match s.validate_against(&reg()).unwrap_err() {
            LoadError::VramOverflow { target, used, cap } => {
                assert_eq!(target, HardwareTarget::Rocm4090);
                assert_eq!(used, 30);
                assert_eq!(cap, 24);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn local_vram_totalling() {
        let mut s = LoadSnapshot::empty_canonical("t");
        for l in s.loads.iter_mut() {
            if l.target == HardwareTarget::Rocm4090 {
                l.vram_used_gb = 18;
            }
            if l.target == HardwareTarget::BlackwellOracle {
                l.vram_used_gb = 60;
            }
            if l.target == HardwareTarget::Cloud {
                l.vram_used_gb = 999;
            } // excluded
        }
        assert_eq!(s.total_local_vram_used_gb(), 78);
    }

    #[test]
    fn avg_util_computed() {
        let mut s = LoadSnapshot::empty_canonical("t");
        s.loads[0].util_pct = 100;
        s.loads[1].util_pct = 50;
        s.loads[2].util_pct = 0;
        s.loads[3].util_pct = 0;
        s.loads[4].util_pct = 0;
        // (100 + 50 + 0 + 0 + 0) / 5 = 30
        assert_eq!(s.avg_util_pct(), 30);
    }

    #[test]
    fn snapshot_serde_roundtrip() {
        let s = LoadSnapshot::empty_canonical("2026-05-19T03:00:00Z");
        let j = serde_json::to_string(&s).unwrap();
        let back: LoadSnapshot = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
