//! Hardware-capability-aware placement.
//!
//! The base scheduler in `lib.rs` routes by *pressure* — it will fall a
//! workload back to the next-warmest role. But M075 maps each SRP role to
//! a specific physical device (F06211-F06214), and those devices are
//! **not interchangeable**:
//!
//! | Role | Device | Precision it hosts | VRAM | Context ceiling |
//! |------|--------|--------------------|------|-----------------|
//! | Conductor | Host CPU (CCD 0) | ternary / bitnet.cpp (F06221) | — | small blocks (F06225) |
//! | Logic | GPU 0 — RTX 4090 24 GB | quantized Q4/IQ4 (F06235) | 24 GB (F06239) | mid |
//! | Oracle | GPU 1 — Blackwell PRO 6000 | un-quantized FP16 (F06214) | 96 GB | deep (F06244) |
//!
//! So a pressure-only fallback is wrong: you cannot run an un-quantized,
//! 100k-token reasoning job on the ternary CPU just because the Oracle GPU
//! is busy. This module adds the capability gate the spec demands — a
//! workload only lands on a role whose hardware **can actually run it**,
//! and spills to the cloud expert plane (M032) rather than onto
//! incapable silicon.

use crate::{RolePressure, ScheduleRequest, WorkloadClass, canonical_role};
use serde::{Deserialize, Serialize};
use sovereign_router_7axis::SrpRole;
use thiserror::Error;

/// Numeric precision a workload runs at. Ordered by hardware demand:
/// `Ternary < Quantized < Fp16`. A device that hosts a higher precision
/// can also host everything below it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Precision {
    /// 1.58-bit ternary (bitnet.cpp on CPU) — F06221.
    Ternary,
    /// Quantized Q4/IQ4 mid-scale (RTX 4090) — F06235.
    Quantized,
    /// Un-quantized FP16 (Blackwell PRO 6000) — F06214.
    Fp16,
}

/// The physical capability envelope of one SRP role's device (F06211-F06214).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct HardwareTarget {
    /// The SRP role this device backs.
    pub role: SrpRole,
    /// Human-readable device label.
    pub device: &'static str,
    /// On-device VRAM in GB (`0` for the CPU role).
    pub vram_gb: u16,
    /// Highest precision the device hosts (and everything below it).
    pub max_precision: Precision,
    /// Largest context, in tokens, the device serves.
    pub max_context_tokens: u32,
}

impl HardwareTarget {
    /// Canonical hardware envelope for an SRP role per M075.
    pub fn for_role(role: SrpRole) -> Option<HardwareTarget> {
        Some(match role {
            SrpRole::Conductor => HardwareTarget {
                role,
                device: "Host CPU (CCD 0) — bitnet.cpp",
                vram_gb: 0,
                max_precision: Precision::Ternary,
                max_context_tokens: 8_192,
            },
            SrpRole::Logic => HardwareTarget {
                role,
                device: "GPU 0 — RTX 4090 24GB",
                vram_gb: 24,
                max_precision: Precision::Quantized,
                max_context_tokens: 32_768,
            },
            SrpRole::Oracle => HardwareTarget {
                role,
                device: "GPU 1 — Blackwell PRO 6000 96GB",
                vram_gb: 96,
                max_precision: Precision::Fp16,
                max_context_tokens: 200_000,
            },
            SrpRole::Cloud => return None, // cloud is the spill target, not a local device
        })
    }

    /// Whether this device can actually run the workload: precision within
    /// the device's ceiling, context within range, and enough VRAM.
    pub fn can_run(&self, w: &Workload) -> bool {
        w.precision <= self.max_precision
            && w.context_tokens <= self.max_context_tokens
            && w.min_vram_gb <= self.vram_gb
    }
}

/// A unit of work plus its hardware requirements.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Workload {
    /// Work class (drives the canonical role).
    pub class: WorkloadClass,
    /// Numeric precision the model for this work runs at.
    pub precision: Precision,
    /// Context size in tokens.
    pub context_tokens: u32,
    /// Minimum VRAM the model needs, in GB.
    pub min_vram_gb: u16,
}

/// The outcome of placing a workload.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Placement {
    /// The role the work landed on.
    pub role: SrpRole,
    /// The device backing it (or `"cloud expert plane (M032)"` on spill).
    pub device: &'static str,
    /// True if the work did not land on its canonical role.
    pub fell_back: bool,
    /// True if no local device was capable and it spilled to the cloud.
    pub spilled_to_cloud: bool,
}

/// Placement failures.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum PlacementError {
    /// No local device can run this workload and cloud spill is disabled.
    #[error(
        "no local SRP device can run this workload (precision/context/VRAM) and cloud spill is disabled"
    )]
    NoCapableDevice,
    /// Every capable device is overloaded and cloud spill is disabled.
    #[error("every capable SRP device is overloaded and cloud spill is disabled")]
    AllCapableOverloaded,
}

fn pressure_for(role: SrpRole, req: &ScheduleRequest) -> Option<&RolePressure> {
    match role {
        SrpRole::Conductor => Some(&req.conductor),
        SrpRole::Logic => Some(&req.logic),
        SrpRole::Oracle => Some(&req.oracle),
        SrpRole::Cloud => None,
    }
}

fn overloaded(role: SrpRole, req: &ScheduleRequest) -> bool {
    pressure_for(role, req)
        .map(|p| p.util_percent > 90 && p.queue_depth > 50)
        .unwrap_or(false)
}

/// Place a workload on a role whose hardware can run it (F06211-F06245).
///
/// 1. Prefer the canonical role *if* its device is capable and not
///    overloaded.
/// 2. Otherwise fall back only to **other capable** devices that are not
///    overloaded — never onto silicon that cannot run the workload.
/// 3. If no local device is capable, spill to the cloud expert plane
///    (M032) when `allow_cloud`, else [`PlacementError::NoCapableDevice`].
/// 4. If capable devices exist but all are overloaded, spill to cloud when
///    allowed, else [`PlacementError::AllCapableOverloaded`].
///
/// Local fallback prefers the *least* capable device that still fits, so
/// the Oracle GPU is kept free for the deep work only it can do.
pub fn place(
    workload: &Workload,
    req: &ScheduleRequest,
    allow_cloud: bool,
) -> Result<Placement, PlacementError> {
    let canonical = canonical_role(workload.class);

    // Local devices that can actually run this workload, in best-fit order
    // (least capable first), so big GPUs aren't wasted on small jobs.
    let mut capable: Vec<HardwareTarget> = [SrpRole::Conductor, SrpRole::Logic, SrpRole::Oracle]
        .into_iter()
        .filter_map(HardwareTarget::for_role)
        .filter(|t| t.can_run(workload))
        .collect();
    capable.sort_by_key(|t| t.max_precision);

    if capable.is_empty() {
        return if allow_cloud {
            Ok(cloud_spill(canonical))
        } else {
            Err(PlacementError::NoCapableDevice)
        };
    }

    // Prefer canonical when it is itself capable + free.
    if let Some(canon) = capable.iter().find(|t| t.role == canonical)
        && !overloaded(canonical, req)
    {
        return Ok(Placement {
            role: canon.role,
            device: canon.device,
            fell_back: false,
            spilled_to_cloud: false,
        });
    }

    // Otherwise the least-capable, non-overloaded device that fits.
    if let Some(t) = capable.iter().find(|t| !overloaded(t.role, req)) {
        return Ok(Placement {
            role: t.role,
            device: t.device,
            fell_back: t.role != canonical,
            spilled_to_cloud: false,
        });
    }

    // Capable devices exist but are all overloaded.
    if allow_cloud {
        Ok(cloud_spill(canonical))
    } else {
        Err(PlacementError::AllCapableOverloaded)
    }
}

fn cloud_spill(canonical: SrpRole) -> Placement {
    Placement {
        role: SrpRole::Cloud,
        device: "cloud expert plane (M032)",
        fell_back: canonical != SrpRole::Cloud,
        spilled_to_cloud: true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn free() -> RolePressure {
        RolePressure::free()
    }
    fn req(c: RolePressure, l: RolePressure, o: RolePressure) -> ScheduleRequest {
        ScheduleRequest {
            class: WorkloadClass::IntentEval, // unused by place(); workload.class drives it
            conductor: c,
            logic: l,
            oracle: o,
        }
    }
    fn all_free() -> ScheduleRequest {
        req(free(), free(), free())
    }

    fn workload(class: WorkloadClass, p: Precision, ctx: u32, vram: u16) -> Workload {
        Workload {
            class,
            precision: p,
            context_tokens: ctx,
            min_vram_gb: vram,
        }
    }

    // --- capability gate ---

    #[test]
    fn ternary_small_lands_on_conductor() {
        let w = workload(WorkloadClass::IntentEval, Precision::Ternary, 4096, 0);
        let p = place(&w, &all_free(), false).unwrap();
        assert_eq!(p.role, SrpRole::Conductor);
        assert!(!p.fell_back);
    }

    #[test]
    fn quantized_lands_on_logic() {
        let w = workload(WorkloadClass::TokenStream, Precision::Quantized, 16_000, 20);
        let p = place(&w, &all_free(), false).unwrap();
        assert_eq!(p.role, SrpRole::Logic);
    }

    #[test]
    fn fp16_deep_lands_on_oracle() {
        let w = workload(WorkloadClass::DeepReason, Precision::Fp16, 120_000, 80);
        let p = place(&w, &all_free(), false).unwrap();
        assert_eq!(p.role, SrpRole::Oracle);
    }

    // --- the core bug this layer fixes ---

    #[test]
    fn fp16_job_never_falls_back_to_cpu() {
        // Oracle (the only FP16-capable device) is hammered. A pressure-only
        // scheduler would spill onto Conductor/Logic — which physically
        // cannot run FP16. Capability-aware placement must refuse that.
        let w = workload(WorkloadClass::DeepReason, Precision::Fp16, 120_000, 80);
        let r = req(free(), free(), RolePressure::overloaded());
        // cloud disabled -> error, NOT a wrong CPU placement
        assert_eq!(
            place(&w, &r, false).unwrap_err(),
            PlacementError::AllCapableOverloaded
        );
        // cloud enabled -> spill, still never CPU
        let p = place(&w, &r, true).unwrap();
        assert!(p.spilled_to_cloud);
        assert_eq!(p.role, SrpRole::Cloud);
    }

    #[test]
    fn vram_hungry_job_excludes_logic() {
        // 40 GB model: Logic's 24 GB can't hold it; only Oracle (96 GB) can.
        let w = workload(WorkloadClass::TokenStream, Precision::Quantized, 8_000, 40);
        let p = place(&w, &all_free(), false).unwrap();
        assert_eq!(p.role, SrpRole::Oracle);
        assert!(p.fell_back); // canonical was Logic, but it lacks the VRAM
    }

    #[test]
    fn huge_context_excludes_small_devices() {
        // 100k tokens exceeds Conductor (8k) and Logic (32k); only Oracle (200k).
        let w = workload(WorkloadClass::IntentEval, Precision::Ternary, 100_000, 0);
        let p = place(&w, &all_free(), false).unwrap();
        assert_eq!(p.role, SrpRole::Oracle);
    }

    // --- capability-aware fallback ---

    #[test]
    fn quantized_falls_back_to_oracle_not_conductor() {
        // Logic busy. Quantized can run on Oracle (FP16 device, superset) but
        // NOT Conductor (ternary only). Fallback must pick Oracle.
        let w = workload(WorkloadClass::TokenStream, Precision::Quantized, 8_000, 10);
        let r = req(free(), RolePressure::overloaded(), free());
        let p = place(&w, &r, false).unwrap();
        assert_eq!(p.role, SrpRole::Oracle);
        assert!(p.fell_back);
    }

    #[test]
    fn ternary_prefers_least_capable_on_fallback() {
        // Ternary small job, Conductor busy. Both Logic and Oracle can run
        // ternary; best-fit prefers the less-capable Logic, sparing Oracle.
        let w = workload(WorkloadClass::IntentEval, Precision::Ternary, 4096, 0);
        let r = req(RolePressure::overloaded(), free(), free());
        let p = place(&w, &r, false).unwrap();
        assert_eq!(p.role, SrpRole::Logic);
        assert!(p.fell_back);
    }

    // --- cloud spill ---

    #[test]
    fn no_capable_device_spills_to_cloud_when_allowed() {
        // Needs 200 GB VRAM: no local device qualifies.
        let w = workload(WorkloadClass::DeepReason, Precision::Fp16, 10_000, 200);
        assert_eq!(
            place(&w, &all_free(), false).unwrap_err(),
            PlacementError::NoCapableDevice
        );
        let p = place(&w, &all_free(), true).unwrap();
        assert!(p.spilled_to_cloud);
    }

    // --- hardware envelope sanity ---

    #[test]
    fn precision_ordering_is_demand_ascending() {
        assert!(Precision::Ternary < Precision::Quantized);
        assert!(Precision::Quantized < Precision::Fp16);
    }

    #[test]
    fn cloud_has_no_local_hardware() {
        assert!(HardwareTarget::for_role(SrpRole::Cloud).is_none());
    }

    #[test]
    fn oracle_can_run_everything_local() {
        let oracle = HardwareTarget::for_role(SrpRole::Oracle).unwrap();
        assert!(oracle.can_run(&workload(
            WorkloadClass::IntentEval,
            Precision::Ternary,
            4096,
            0
        )));
        assert!(oracle.can_run(&workload(
            WorkloadClass::TokenStream,
            Precision::Quantized,
            32_000,
            20
        )));
        assert!(oracle.can_run(&workload(
            WorkloadClass::DeepReason,
            Precision::Fp16,
            200_000,
            90
        )));
    }
}
