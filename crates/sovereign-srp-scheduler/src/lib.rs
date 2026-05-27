//! `sovereign-srp-scheduler` — M075 SRP work-placement scheduler.
//!
//! Per M075 + E0719-E0721 + dump 813-837:
//!
//! Doctrine surface verbatim per dump 813:
//!
//! > "To scale a sovereign node without succumbing to code maintenance
//! > decay, we map the Single Responsibility Principle (SRP) directly
//! > to physical hardware layers."
//!
//! Roles:
//! - **Conductor Agent** — CPU bound — Routing & State Fabric (E0719)
//! - **Logic Engine** — GPU 0 RTX 3090 — Ingestion & Translation (E0720)
//! - **Oracle Core** — GPU 1 Blackwell PRO 6000 — Long-Term Deep Reasoning (E0721)
//!
//! Each work-class lands on exactly one SRP role; cross-role traffic
//! goes through Conductor (the state fabric).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_router_7axis::SrpRole;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine verbatim per dump 813.
pub const DOCTRINE_SRP_TO_HARDWARE: &str =
    "we map the Single Responsibility Principle (SRP) directly to physical hardware layers";

/// Workload class taxonomy.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum WorkloadClass {
    /// Intent evaluation / routing decision (Conductor SRP).
    IntentEval,
    /// State update (SOUL.md / CLAUDE.md / branching).
    StateUpdate,
    /// Token/embedding generation (Logic SRP).
    TokenStream,
    /// Vision / GUI perception (Logic SRP).
    Vision,
    /// Translation / reranking (Logic SRP).
    Translation,
    /// Long-context reasoning (Oracle SRP).
    DeepReason,
    /// Multi-step planning (Oracle SRP).
    LongPlan,
    /// Critical commit verification (Oracle SRP).
    CommitVerify,
}

/// Pressure descriptor (lower = more free).
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct RolePressure {
    /// Util percent 0..100.
    pub util_percent: u8,
    /// VRAM usage percent (0 for Conductor).
    pub vram_percent: u8,
    /// Queue depth.
    pub queue_depth: u32,
}

impl RolePressure {
    /// Lowest-pressure (free).
    pub fn free() -> Self {
        RolePressure {
            util_percent: 0,
            vram_percent: 0,
            queue_depth: 0,
        }
    }
    /// Overloaded.
    pub fn overloaded() -> Self {
        RolePressure {
            util_percent: 95,
            vram_percent: 95,
            queue_depth: 100,
        }
    }
}

/// Scheduling request: workload class + pressure across the 3 roles.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ScheduleRequest {
    /// Class.
    pub class: WorkloadClass,
    /// Pressure on Conductor.
    pub conductor: RolePressure,
    /// Pressure on Logic Engine.
    pub logic: RolePressure,
    /// Pressure on Oracle Core.
    pub oracle: RolePressure,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ScheduleError {
    /// All 3 roles overloaded.
    #[error("all 3 SRP roles overloaded (util > 90 + queue > 50)")]
    AllOverloaded,
    /// Doctrine tampered.
    #[error("doctrine tampered: expected verbatim")]
    DoctrineTampered,
}

/// Map a workload class to its canonical SRP role.
pub fn canonical_role(class: WorkloadClass) -> SrpRole {
    match class {
        WorkloadClass::IntentEval | WorkloadClass::StateUpdate => SrpRole::Conductor,
        WorkloadClass::TokenStream | WorkloadClass::Vision | WorkloadClass::Translation => {
            SrpRole::Logic
        }
        WorkloadClass::DeepReason | WorkloadClass::LongPlan | WorkloadClass::CommitVerify => {
            SrpRole::Oracle
        }
    }
}

/// Schedule a workload — picks the canonical role unless overloaded,
/// then falls back to next-warmest in topology order.
pub fn schedule(req: &ScheduleRequest) -> Result<SrpRole, ScheduleError> {
    let canonical = canonical_role(req.class);
    if !is_overloaded(canonical, req) {
        return Ok(canonical);
    }
    // Fallback ordering by topology: Logic → Oracle → Conductor.
    // (Conductor never directly handles token generation, so it's last resort.)
    for fallback in [SrpRole::Logic, SrpRole::Oracle, SrpRole::Conductor] {
        if fallback == canonical {
            continue;
        }
        if !is_overloaded(fallback, req) {
            return Ok(fallback);
        }
    }
    Err(ScheduleError::AllOverloaded)
}

fn is_overloaded(role: SrpRole, req: &ScheduleRequest) -> bool {
    let p = match role {
        SrpRole::Conductor => &req.conductor,
        SrpRole::Logic => &req.logic,
        SrpRole::Oracle => &req.oracle,
        SrpRole::Cloud => return false, // never overloaded locally
    };
    p.util_percent > 90 && p.queue_depth > 50
}

/// Validate the doctrine constant.
pub fn assert_doctrine_intact(observed: &str) -> Result<(), ScheduleError> {
    if observed != DOCTRINE_SRP_TO_HARDWARE {
        return Err(ScheduleError::DoctrineTampered);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn free_req(class: WorkloadClass) -> ScheduleRequest {
        ScheduleRequest {
            class,
            conductor: RolePressure::free(),
            logic: RolePressure::free(),
            oracle: RolePressure::free(),
        }
    }

    #[test]
    fn intent_eval_canonical_conductor() {
        assert_eq!(
            canonical_role(WorkloadClass::IntentEval),
            SrpRole::Conductor
        );
    }

    #[test]
    fn state_update_canonical_conductor() {
        assert_eq!(
            canonical_role(WorkloadClass::StateUpdate),
            SrpRole::Conductor
        );
    }

    #[test]
    fn token_stream_canonical_logic() {
        assert_eq!(canonical_role(WorkloadClass::TokenStream), SrpRole::Logic);
    }

    #[test]
    fn vision_canonical_logic() {
        assert_eq!(canonical_role(WorkloadClass::Vision), SrpRole::Logic);
    }

    #[test]
    fn deep_reason_canonical_oracle() {
        assert_eq!(canonical_role(WorkloadClass::DeepReason), SrpRole::Oracle);
    }

    #[test]
    fn long_plan_canonical_oracle() {
        assert_eq!(canonical_role(WorkloadClass::LongPlan), SrpRole::Oracle);
    }

    #[test]
    fn commit_verify_canonical_oracle() {
        assert_eq!(canonical_role(WorkloadClass::CommitVerify), SrpRole::Oracle);
    }

    #[test]
    fn schedule_free_returns_canonical() {
        for class in [
            WorkloadClass::IntentEval,
            WorkloadClass::TokenStream,
            WorkloadClass::DeepReason,
        ] {
            let r = free_req(class);
            assert_eq!(schedule(&r).unwrap(), canonical_role(class));
        }
    }

    #[test]
    fn overloaded_canonical_falls_back() {
        let mut r = free_req(WorkloadClass::DeepReason);
        r.oracle = RolePressure::overloaded(); // canonical role busy
        // Fallback should be Logic (3090) next in topology order.
        let role = schedule(&r).unwrap();
        assert_eq!(role, SrpRole::Logic);
    }

    #[test]
    fn all_overloaded_returns_error() {
        let r = ScheduleRequest {
            class: WorkloadClass::DeepReason,
            conductor: RolePressure::overloaded(),
            logic: RolePressure::overloaded(),
            oracle: RolePressure::overloaded(),
        };
        assert!(matches!(
            schedule(&r).unwrap_err(),
            ScheduleError::AllOverloaded
        ));
    }

    #[test]
    fn high_util_low_queue_not_overloaded() {
        // util_percent > 90 but queue_depth <= 50 → not overloaded
        let mut r = free_req(WorkloadClass::DeepReason);
        r.oracle = RolePressure {
            util_percent: 95,
            vram_percent: 50,
            queue_depth: 30,
        };
        assert_eq!(schedule(&r).unwrap(), SrpRole::Oracle);
    }

    #[test]
    fn doctrine_verbatim() {
        assert_doctrine_intact(DOCTRINE_SRP_TO_HARDWARE).unwrap();
        assert!(matches!(
            assert_doctrine_intact("WRONG").unwrap_err(),
            ScheduleError::DoctrineTampered
        ));
    }

    #[test]
    fn workload_class_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&WorkloadClass::StateUpdate).unwrap(),
            "\"state-update\""
        );
        assert_eq!(
            serde_json::to_string(&WorkloadClass::TokenStream).unwrap(),
            "\"token-stream\""
        );
        assert_eq!(
            serde_json::to_string(&WorkloadClass::CommitVerify).unwrap(),
            "\"commit-verify\""
        );
    }

    #[test]
    fn role_pressure_free_and_overloaded_constructors() {
        let f = RolePressure::free();
        assert_eq!(f.util_percent, 0);
        let o = RolePressure::overloaded();
        assert_eq!(o.queue_depth, 100);
    }

    #[test]
    fn schedule_request_serde_roundtrip() {
        let r = free_req(WorkloadClass::DeepReason);
        let j = serde_json::to_string(&r).unwrap();
        let back: ScheduleRequest = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
