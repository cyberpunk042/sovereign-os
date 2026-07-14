//! `sovereign-hardware-dispatch-eligibility` — eligibility filter for SRP dispatch.
//!
//! Given a workload request (VRAM needed, latency tier required, SRP role
//! required) and the current load snapshot, this crate computes the subset
//! of HardwareTargets that can serve the request — and an exclusion reason
//! for each target that didn't qualify. The scheduler picks among the
//! eligible set; the cockpit shows the full eligibility tableau so the
//! operator can see why a dispatch landed where it landed.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_hardware_load_sample::LoadSnapshot;
use sovereign_hardware_registry::{HardwareRegistry, HardwareTarget, LatencyTier, SrpRole};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Workload request.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkloadRequest {
    /// VRAM needed (GB) for non-zero-VRAM targets.
    pub vram_needed_gb: u32,
    /// Maximum acceptable latency tier.
    pub max_latency: LatencyTier,
    /// Required SRP role (None = any role acceptable).
    pub require_role: Option<SrpRole>,
    /// Maximum tolerated utilization % on a target (>= this excludes target).
    pub max_util_pct: u8,
}

/// Reason a target was excluded from eligibility.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ExclusionReason {
    /// Not enough free VRAM (capacity - used < needed).
    InsufficientVram,
    /// Latency tier of target exceeds request's max.
    LatencyTooHigh,
    /// Target's SRP role does not match request's require_role.
    RoleMismatch,
    /// Current utilization >= max_util_pct.
    UtilizationSaturated,
}

/// Per-target eligibility result.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TargetEligibility {
    /// Target.
    pub target: HardwareTarget,
    /// True if eligible.
    pub eligible: bool,
    /// Reason if not eligible.
    pub reason: Option<ExclusionReason>,
}

/// Full 5-target eligibility tableau for one request.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EligibilityTableau {
    /// Schema version.
    pub schema_version: String,
    /// 5 results (one per HardwareTarget).
    pub results: Vec<TargetEligibility>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum EligibilityError {
    /// Load snapshot was missing a target.
    #[error("load snapshot missing target: {0:?}")]
    LoadMissingTarget(HardwareTarget),
    /// Registry was missing a target.
    #[error("registry missing target: {0:?}")]
    RegistryMissingTarget(HardwareTarget),
}

fn rank(t: LatencyTier) -> u8 {
    match t {
        LatencyTier::Snap => 0,
        LatencyTier::Brisk => 1,
        LatencyTier::Steady => 2,
        LatencyTier::Heavy => 3,
    }
}

impl EligibilityTableau {
    /// Compute the full 5-target tableau.
    pub fn compute(
        request: &WorkloadRequest,
        registry: &HardwareRegistry,
        load: &LoadSnapshot,
    ) -> Result<Self, EligibilityError> {
        let mut results = Vec::with_capacity(5);
        for target in [
            HardwareTarget::CpuPulse,
            HardwareTarget::Rocm4090,
            HardwareTarget::BlackwellOracle,
            HardwareTarget::Cloud,
            HardwareTarget::NoHardware,
        ] {
            let rec = registry
                .get(target)
                .ok_or(EligibilityError::RegistryMissingTarget(target))?;
            let l = load
                .get(target)
                .ok_or(EligibilityError::LoadMissingTarget(target))?;

            // Role check
            if let Some(req_role) = request.require_role
                && rec.role != req_role
            {
                results.push(TargetEligibility {
                    target,
                    eligible: false,
                    reason: Some(ExclusionReason::RoleMismatch),
                });
                continue;
            }

            // Latency check
            if rank(rec.latency_tier) > rank(request.max_latency) {
                results.push(TargetEligibility {
                    target,
                    eligible: false,
                    reason: Some(ExclusionReason::LatencyTooHigh),
                });
                continue;
            }

            // VRAM check (only meaningful when target has VRAM capacity > 0)
            if request.vram_needed_gb > 0 && rec.vram_gb > 0 {
                let free = rec.vram_gb.saturating_sub(l.vram_used_gb);
                if free < request.vram_needed_gb {
                    results.push(TargetEligibility {
                        target,
                        eligible: false,
                        reason: Some(ExclusionReason::InsufficientVram),
                    });
                    continue;
                }
            } else if request.vram_needed_gb > 0 && rec.vram_gb == 0 {
                // Caller wants VRAM but this target has none.
                results.push(TargetEligibility {
                    target,
                    eligible: false,
                    reason: Some(ExclusionReason::InsufficientVram),
                });
                continue;
            }

            // Utilization check
            if l.util_pct >= request.max_util_pct {
                results.push(TargetEligibility {
                    target,
                    eligible: false,
                    reason: Some(ExclusionReason::UtilizationSaturated),
                });
                continue;
            }

            results.push(TargetEligibility {
                target,
                eligible: true,
                reason: None,
            });
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            results,
        })
    }

    /// Targets currently eligible.
    pub fn eligible_targets(&self) -> Vec<HardwareTarget> {
        self.results
            .iter()
            .filter(|r| r.eligible)
            .map(|r| r.target)
            .collect()
    }

    /// Count eligible targets.
    pub fn eligible_count(&self) -> usize {
        self.results.iter().filter(|r| r.eligible).count()
    }

    /// Lookup by target.
    pub fn get(&self, t: HardwareTarget) -> Option<&TargetEligibility> {
        self.results.iter().find(|r| r.target == t)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn reg() -> HardwareRegistry {
        HardwareRegistry::canonical()
    }
    fn empty_load() -> LoadSnapshot {
        LoadSnapshot::empty_canonical("2026-05-19T03:00:00Z")
    }

    fn request_default() -> WorkloadRequest {
        WorkloadRequest {
            vram_needed_gb: 0,
            max_latency: LatencyTier::Heavy,
            require_role: None,
            max_util_pct: 101, // never saturate by default
        }
    }

    #[test]
    fn empty_load_makes_all_eligible() {
        let t = EligibilityTableau::compute(&request_default(), &reg(), &empty_load()).unwrap();
        assert_eq!(t.eligible_count(), 5);
    }

    #[test]
    fn vram_request_eliminates_cpu_and_cloud() {
        let mut req = request_default();
        req.vram_needed_gb = 8;
        let t = EligibilityTableau::compute(&req, &reg(), &empty_load()).unwrap();
        // CpuPulse, Cloud, NoHardware have vram_gb=0 → InsufficientVram
        assert_eq!(
            t.get(HardwareTarget::CpuPulse).unwrap().reason,
            Some(ExclusionReason::InsufficientVram)
        );
        assert_eq!(
            t.get(HardwareTarget::Cloud).unwrap().reason,
            Some(ExclusionReason::InsufficientVram)
        );
        assert_eq!(
            t.get(HardwareTarget::NoHardware).unwrap().reason,
            Some(ExclusionReason::InsufficientVram)
        );
        // Logic (RTX 5090, 32GB) and Blackwell (96GB) eligible
        assert!(t.get(HardwareTarget::Rocm4090).unwrap().eligible);
        assert!(t.get(HardwareTarget::BlackwellOracle).unwrap().eligible);
    }

    #[test]
    fn latency_cap_excludes_slower_tiers() {
        let mut req = request_default();
        req.max_latency = LatencyTier::Snap; // only Snap-tier targets pass
        let t = EligibilityTableau::compute(&req, &reg(), &empty_load()).unwrap();
        // CpuPulse Snap, NoHardware Snap → eligible
        assert!(t.get(HardwareTarget::CpuPulse).unwrap().eligible);
        assert!(t.get(HardwareTarget::NoHardware).unwrap().eligible);
        // Rocm4090 Brisk, Blackwell Steady, Cloud Heavy → excluded
        assert_eq!(
            t.get(HardwareTarget::Rocm4090).unwrap().reason,
            Some(ExclusionReason::LatencyTooHigh)
        );
        assert_eq!(
            t.get(HardwareTarget::BlackwellOracle).unwrap().reason,
            Some(ExclusionReason::LatencyTooHigh)
        );
        assert_eq!(
            t.get(HardwareTarget::Cloud).unwrap().reason,
            Some(ExclusionReason::LatencyTooHigh)
        );
    }

    #[test]
    fn role_requirement_filters_to_one() {
        let mut req = request_default();
        req.require_role = Some(SrpRole::Oracle);
        let t = EligibilityTableau::compute(&req, &reg(), &empty_load()).unwrap();
        assert_eq!(t.eligible_count(), 1);
        assert_eq!(t.eligible_targets(), vec![HardwareTarget::BlackwellOracle]);
    }

    #[test]
    fn util_cap_excludes_saturated() {
        let mut load = empty_load();
        for l in load.loads.iter_mut() {
            if l.target == HardwareTarget::Rocm4090 {
                l.util_pct = 95;
            }
        }
        let mut req = request_default();
        req.max_util_pct = 80;
        let t = EligibilityTableau::compute(&req, &reg(), &load).unwrap();
        assert_eq!(
            t.get(HardwareTarget::Rocm4090).unwrap().reason,
            Some(ExclusionReason::UtilizationSaturated)
        );
        assert!(t.get(HardwareTarget::BlackwellOracle).unwrap().eligible);
    }

    #[test]
    fn vram_used_subtracts_from_capacity() {
        let mut load = empty_load();
        for l in load.loads.iter_mut() {
            if l.target == HardwareTarget::Rocm4090 {
                l.vram_used_gb = 28;
            }
        }
        let mut req = request_default();
        req.vram_needed_gb = 8; // need 8GB, Logic 5090 has 4GB free (32-28) → excluded
        let t = EligibilityTableau::compute(&req, &reg(), &load).unwrap();
        assert_eq!(
            t.get(HardwareTarget::Rocm4090).unwrap().reason,
            Some(ExclusionReason::InsufficientVram)
        );
        // Blackwell has 96GB free → eligible
        assert!(t.get(HardwareTarget::BlackwellOracle).unwrap().eligible);
    }

    #[test]
    fn role_check_runs_before_latency() {
        // Role mismatch should be reported even when latency would also fail.
        let mut req = request_default();
        req.require_role = Some(SrpRole::Conductor);
        req.max_latency = LatencyTier::Snap;
        let t = EligibilityTableau::compute(&req, &reg(), &empty_load()).unwrap();
        assert_eq!(
            t.get(HardwareTarget::Cloud).unwrap().reason,
            Some(ExclusionReason::RoleMismatch)
        );
    }

    #[test]
    fn five_results_always() {
        let t = EligibilityTableau::compute(&request_default(), &reg(), &empty_load()).unwrap();
        assert_eq!(t.results.len(), 5);
    }

    #[test]
    fn exclusion_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ExclusionReason::InsufficientVram).unwrap(),
            "\"insufficient-vram\""
        );
        assert_eq!(
            serde_json::to_string(&ExclusionReason::LatencyTooHigh).unwrap(),
            "\"latency-too-high\""
        );
        assert_eq!(
            serde_json::to_string(&ExclusionReason::RoleMismatch).unwrap(),
            "\"role-mismatch\""
        );
        assert_eq!(
            serde_json::to_string(&ExclusionReason::UtilizationSaturated).unwrap(),
            "\"utilization-saturated\""
        );
    }

    #[test]
    fn tableau_serde_roundtrip() {
        let t = EligibilityTableau::compute(&request_default(), &reg(), &empty_load()).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: EligibilityTableau = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
