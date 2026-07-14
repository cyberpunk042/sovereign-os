//! `sovereign-hardware-registry` — runtime catalog of the 5 SRP hardware targets.
//!
//! Mirrors the selfdef `HardwareTarget` discriminator surface but adds the
//! runtime-only fields the scheduler needs: vram_gb, role, latency_tier,
//! vendor, kernel-driver version. Composes with the M075 SRP topology
//! (Conductor/Logic/Oracle) and the 7-axis router.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 5 canonical hardware targets — exactly mirrors the IPS-side enum.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum HardwareTarget {
    /// Ryzen 9 9900X — Conductor / Pulse role.
    CpuPulse,
    /// Logic Engine device — the RTX 5090 32GB (CUDA) per D-022 (SDD-993). The
    /// variant name + `rocm-4090` wire token are legacy stable keys: the backing
    /// card changed (was the RTX 4090), the discriminator did not.
    #[serde(rename = "rocm-4090")]
    Rocm4090,
    /// Blackwell PRO 6000 96GB — Oracle Core.
    BlackwellOracle,
    /// External cloud provider.
    Cloud,
    /// No hardware (observe-only / dry-run).
    NoHardware,
}

/// SRP topology role.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SrpRole {
    /// Conductor — scheduling + orchestration.
    Conductor,
    /// Logic — bulk inference.
    Logic,
    /// Oracle — flagship reasoning.
    Oracle,
    /// External — cloud-only.
    External,
    /// Inert — no role assigned.
    Inert,
}

/// Latency tier (sub-second classification).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LatencyTier {
    /// < 50ms.
    Snap,
    /// 50-300ms.
    Brisk,
    /// 300-1500ms.
    Steady,
    /// > 1500ms.
    Heavy,
}

/// Per-target hardware record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HardwareRecord {
    /// Target.
    pub target: HardwareTarget,
    /// Human-readable vendor.
    pub vendor: String,
    /// VRAM (GB); 0 for CPU/cloud/none.
    pub vram_gb: u32,
    /// SRP topology role.
    pub role: SrpRole,
    /// Latency tier.
    pub latency_tier: LatencyTier,
    /// Driver/runtime version string (e.g. "ROCm-6.2", "CUDA-13.0", "n/a").
    pub driver: String,
}

/// Registry envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HardwareRegistry {
    /// Schema version.
    pub schema_version: String,
    /// Exactly 5 records.
    pub records: Vec<HardwareRecord>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HardwareError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 5.
    #[error("hardware count {0} != 5 canonical")]
    CountInvalid(usize),
    /// Missing canonical target.
    #[error("missing canonical hardware target: {0:?}")]
    Missing(HardwareTarget),
    /// Duplicate target.
    #[error("duplicate hardware target: {0:?}")]
    Duplicate(HardwareTarget),
    /// Role inconsistency.
    #[error("role mismatch for {target:?}: declared {declared:?}, canonical {canonical:?}")]
    RoleMismatch {
        /// Target.
        target: HardwareTarget,
        /// Declared role.
        declared: SrpRole,
        /// Canonical role.
        canonical: SrpRole,
    },
}

impl HardwareTarget {
    /// Canonical SRP role for this target.
    pub fn canonical_role(self) -> SrpRole {
        match self {
            HardwareTarget::CpuPulse => SrpRole::Conductor,
            HardwareTarget::Rocm4090 => SrpRole::Logic,
            HardwareTarget::BlackwellOracle => SrpRole::Oracle,
            HardwareTarget::Cloud => SrpRole::External,
            HardwareTarget::NoHardware => SrpRole::Inert,
        }
    }
}

impl HardwareRegistry {
    /// Canonical empty registry — operator's actual hardware stack.
    pub fn canonical() -> Self {
        let records = vec![
            HardwareRecord {
                target: HardwareTarget::CpuPulse,
                vendor: "AMD Ryzen 9 9900X".into(),
                vram_gb: 0,
                role: SrpRole::Conductor,
                latency_tier: LatencyTier::Snap,
                driver: "linux-6.18".into(),
            },
            HardwareRecord {
                target: HardwareTarget::Rocm4090,
                vendor: "NVIDIA RTX 5090".into(),
                vram_gb: 32,
                role: SrpRole::Logic,
                latency_tier: LatencyTier::Brisk,
                driver: "CUDA-13.0".into(),
            },
            HardwareRecord {
                target: HardwareTarget::BlackwellOracle,
                vendor: "NVIDIA Blackwell PRO 6000".into(),
                vram_gb: 96,
                role: SrpRole::Oracle,
                latency_tier: LatencyTier::Steady,
                driver: "CUDA-13.0".into(),
            },
            HardwareRecord {
                target: HardwareTarget::Cloud,
                vendor: "external-provider".into(),
                vram_gb: 0,
                role: SrpRole::External,
                latency_tier: LatencyTier::Heavy,
                driver: "n/a".into(),
            },
            HardwareRecord {
                target: HardwareTarget::NoHardware,
                vendor: "none".into(),
                vram_gb: 0,
                role: SrpRole::Inert,
                latency_tier: LatencyTier::Snap,
                driver: "n/a".into(),
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            records,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HardwareError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HardwareError::SchemaMismatch);
        }
        if self.records.len() != 5 {
            return Err(HardwareError::CountInvalid(self.records.len()));
        }
        let required = [
            HardwareTarget::CpuPulse,
            HardwareTarget::Rocm4090,
            HardwareTarget::BlackwellOracle,
            HardwareTarget::Cloud,
            HardwareTarget::NoHardware,
        ];
        for t in required {
            if !self.records.iter().any(|r| r.target == t) {
                return Err(HardwareError::Missing(t));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<HardwareTarget> = HashSet::new();
        for r in &self.records {
            if !seen.insert(r.target) {
                return Err(HardwareError::Duplicate(r.target));
            }
            let canonical = r.target.canonical_role();
            if r.role != canonical {
                return Err(HardwareError::RoleMismatch {
                    target: r.target,
                    declared: r.role,
                    canonical,
                });
            }
        }
        Ok(())
    }

    /// Total local VRAM (excludes Cloud + NoHardware).
    pub fn total_local_vram_gb(&self) -> u32 {
        self.records
            .iter()
            .filter(|r| !matches!(r.target, HardwareTarget::Cloud | HardwareTarget::NoHardware))
            .map(|r| r.vram_gb)
            .sum()
    }

    /// Lookup by target.
    pub fn get(&self, t: HardwareTarget) -> Option<&HardwareRecord> {
        self.records.iter().find(|r| r.target == t)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        HardwareRegistry::canonical().validate().unwrap();
    }

    #[test]
    fn five_targets_present() {
        let r = HardwareRegistry::canonical();
        assert_eq!(r.records.len(), 5);
        for t in [
            HardwareTarget::CpuPulse,
            HardwareTarget::Rocm4090,
            HardwareTarget::BlackwellOracle,
            HardwareTarget::Cloud,
            HardwareTarget::NoHardware,
        ] {
            assert!(r.get(t).is_some(), "missing {t:?}");
        }
    }

    #[test]
    fn canonical_roles_match() {
        assert_eq!(
            HardwareTarget::CpuPulse.canonical_role(),
            SrpRole::Conductor
        );
        assert_eq!(HardwareTarget::Rocm4090.canonical_role(), SrpRole::Logic);
        assert_eq!(
            HardwareTarget::BlackwellOracle.canonical_role(),
            SrpRole::Oracle
        );
        assert_eq!(HardwareTarget::Cloud.canonical_role(), SrpRole::External);
        assert_eq!(HardwareTarget::NoHardware.canonical_role(), SrpRole::Inert);
    }

    #[test]
    fn vram_totals_32_plus_96() {
        let r = HardwareRegistry::canonical();
        assert_eq!(r.total_local_vram_gb(), 32 + 96);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = HardwareRegistry::canonical();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            HardwareError::SchemaMismatch
        ));
    }

    #[test]
    fn count_invalid_caught() {
        let mut r = HardwareRegistry::canonical();
        r.records.pop();
        assert!(matches!(
            r.validate().unwrap_err(),
            HardwareError::CountInvalid(4)
        ));
    }

    #[test]
    fn role_mismatch_caught() {
        let mut r = HardwareRegistry::canonical();
        r.records[0].role = SrpRole::Oracle;
        match r.validate().unwrap_err() {
            HardwareError::RoleMismatch {
                target,
                declared,
                canonical,
            } => {
                assert_eq!(target, HardwareTarget::CpuPulse);
                assert_eq!(declared, SrpRole::Oracle);
                assert_eq!(canonical, SrpRole::Conductor);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn target_serde_kebab_with_rename() {
        assert_eq!(
            serde_json::to_string(&HardwareTarget::CpuPulse).unwrap(),
            "\"cpu-pulse\""
        );
        assert_eq!(
            serde_json::to_string(&HardwareTarget::Rocm4090).unwrap(),
            "\"rocm-4090\""
        );
        assert_eq!(
            serde_json::to_string(&HardwareTarget::BlackwellOracle).unwrap(),
            "\"blackwell-oracle\""
        );
        assert_eq!(
            serde_json::to_string(&HardwareTarget::NoHardware).unwrap(),
            "\"no-hardware\""
        );
    }

    #[test]
    fn role_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&SrpRole::Conductor).unwrap(),
            "\"conductor\""
        );
        assert_eq!(
            serde_json::to_string(&SrpRole::Oracle).unwrap(),
            "\"oracle\""
        );
    }

    #[test]
    fn registry_serde_roundtrip() {
        let r = HardwareRegistry::canonical();
        let j = serde_json::to_string(&r).unwrap();
        let back: HardwareRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
