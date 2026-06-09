//! `sovereign-lora-foundry` — M046 8-candidate LoRA adapter catalog + 7-step pipeline.
//!
//! Per M046 + E0442 + M00774 + dump 13966-13988:
//!
//! Doctrine surface verbatim:
//!
//! > "Fine-tuning changes weights. Runtime adaptation changes behavior.
//! > Runtime adaptation comes first."
//!
//! 8 canonical adapters per M00774 dump 13966-13976:
//! 1. selfdef/security
//! 2. sovereign-os/admin
//! 3. coding-style
//! 4. spec-driven
//! 5. TDD-review
//! 6. communication-mediation
//! 7. domain-specific
//! 8. user-preference
//!
//! 6-action runtime decision per E0442 dump 13986-13988:
//!   use-base / use-adapter-a / use-adapter-b / stack-merge / route-specialist / ask-oracle
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod serving;

pub use serving::{ServeRequest, decide_serving};

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine surface verbatim per E0438.
pub const DOCTRINE_RUNTIME_FIRST: &str = "Fine-tuning changes weights. Runtime adaptation changes behavior. Runtime adaptation comes first.";

/// 8 canonical adapter slots per M00774.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AdapterSlot {
    /// 1. selfdef/security LoRA — IPS doctrine.
    SelfdefSecurity,
    /// 2. sovereign-os/admin LoRA — runtime admin.
    SovereignAdmin,
    /// 3. coding-style LoRA.
    CodingStyle,
    /// 4. spec-driven LoRA.
    SpecDriven,
    /// 5. TDD-review LoRA.
    TddReview,
    /// 6. communication-mediation LoRA.
    CommunicationMediation,
    /// 7. domain-specific LoRA (operator-named domain).
    DomainSpecific,
    /// 8. user-preference LoRA.
    UserPreference,
}

impl AdapterSlot {
    /// Canonical 1..8 position.
    pub fn position(self) -> u8 {
        match self {
            AdapterSlot::SelfdefSecurity => 1,
            AdapterSlot::SovereignAdmin => 2,
            AdapterSlot::CodingStyle => 3,
            AdapterSlot::SpecDriven => 4,
            AdapterSlot::TddReview => 5,
            AdapterSlot::CommunicationMediation => 6,
            AdapterSlot::DomainSpecific => 7,
            AdapterSlot::UserPreference => 8,
        }
    }
    /// Which project owns the source of truth.
    pub fn source_repo(self) -> &'static str {
        match self {
            AdapterSlot::SelfdefSecurity => "selfdef",
            _ => "sovereign-os",
        }
    }
}

/// 6 runtime decisions per E0442 dump 13986-13988.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RuntimeDecision {
    /// Use base model only.
    UseBase,
    /// Use exactly one adapter.
    UseAdapter,
    /// Stack-merge two adapters (only when supported).
    StackMerge,
    /// Route to a different specialist model.
    RouteSpecialist,
    /// Skip adapter path and ask oracle directly.
    AskOracle,
    /// Refuse / no adapter applicable.
    Refuse,
}

/// 7-step adapter pipeline per dump 13990.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PipelineStep {
    /// 1. Trace curation.
    TraceCuration,
    /// 2. Dataset creation.
    DatasetCreation,
    /// 3. LoRA training.
    LoraTraining,
    /// 4. Adapter serving.
    AdapterServing,
    /// 5. Eval gating.
    EvalGating,
    /// 6. Profile assignment.
    ProfileAssignment,
    /// 7. Commit (signed promotion).
    SignedPromotion,
}

impl PipelineStep {
    /// Canonical 1..7 position.
    pub fn position(self) -> u8 {
        match self {
            PipelineStep::TraceCuration => 1,
            PipelineStep::DatasetCreation => 2,
            PipelineStep::LoraTraining => 3,
            PipelineStep::AdapterServing => 4,
            PipelineStep::EvalGating => 5,
            PipelineStep::ProfileAssignment => 6,
            PipelineStep::SignedPromotion => 7,
        }
    }
    /// Next step.
    pub fn next(self) -> Option<Self> {
        match self {
            PipelineStep::TraceCuration => Some(PipelineStep::DatasetCreation),
            PipelineStep::DatasetCreation => Some(PipelineStep::LoraTraining),
            PipelineStep::LoraTraining => Some(PipelineStep::AdapterServing),
            PipelineStep::AdapterServing => Some(PipelineStep::EvalGating),
            PipelineStep::EvalGating => Some(PipelineStep::ProfileAssignment),
            PipelineStep::ProfileAssignment => Some(PipelineStep::SignedPromotion),
            PipelineStep::SignedPromotion => None,
        }
    }
}

/// One adapter promotion record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AdapterPromotion {
    /// Slot.
    pub slot: AdapterSlot,
    /// Operator-readable adapter version (e.g. "v3-2026-05-19").
    pub version: String,
    /// Current pipeline step.
    pub step: PipelineStep,
    /// Eval gate score (0..=100). Promotion requires >= 80.
    pub eval_score: u8,
    /// ZFS snapshot id pre-promotion.
    pub pre_snapshot: String,
    /// MS003 signature over the promotion envelope.
    pub signature: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FoundryError {
    /// Pipeline skip.
    #[error("pipeline skip {from:?} → {to:?}")]
    PipelineSkip {
        /// From step.
        from: PipelineStep,
        /// To step.
        to: PipelineStep,
    },
    /// Pipeline terminal (already at SignedPromotion).
    #[error("pipeline at terminal SignedPromotion")]
    PipelineTerminal,
    /// Eval score below 80 — refuse signed-promotion advance.
    #[error("eval score {0} below 80 — cannot advance to SignedPromotion")]
    EvalGateFailed(u8),
    /// Unsigned promotion at SignedPromotion step.
    #[error("SignedPromotion step requires non-empty signature")]
    PromotionUnsigned,
}

impl AdapterPromotion {
    /// Advance to the next pipeline step. Enforces eval-gate before SignedPromotion + signature.
    pub fn advance(&mut self) -> Result<PipelineStep, FoundryError> {
        let next = self.step.next().ok_or(FoundryError::PipelineTerminal)?;
        if next == PipelineStep::SignedPromotion {
            if self.eval_score < 80 {
                return Err(FoundryError::EvalGateFailed(self.eval_score));
            }
            if self.signature.is_empty() {
                return Err(FoundryError::PromotionUnsigned);
            }
        }
        self.step = next;
        Ok(self.step)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn promo(slot: AdapterSlot) -> AdapterPromotion {
        AdapterPromotion {
            slot,
            version: "v1".into(),
            step: PipelineStep::TraceCuration,
            eval_score: 85,
            pre_snapshot: "rpool@pre".into(),
            signature: "ms003".into(),
        }
    }

    #[test]
    fn eight_adapter_slots_positioned_1_to_8() {
        for (s, p) in [
            (AdapterSlot::SelfdefSecurity, 1),
            (AdapterSlot::SovereignAdmin, 2),
            (AdapterSlot::CodingStyle, 3),
            (AdapterSlot::SpecDriven, 4),
            (AdapterSlot::TddReview, 5),
            (AdapterSlot::CommunicationMediation, 6),
            (AdapterSlot::DomainSpecific, 7),
            (AdapterSlot::UserPreference, 8),
        ] {
            assert_eq!(s.position(), p);
        }
    }

    #[test]
    fn selfdef_security_is_only_selfdef_owned() {
        assert_eq!(AdapterSlot::SelfdefSecurity.source_repo(), "selfdef");
        for s in [
            AdapterSlot::SovereignAdmin,
            AdapterSlot::CodingStyle,
            AdapterSlot::SpecDriven,
            AdapterSlot::TddReview,
            AdapterSlot::CommunicationMediation,
            AdapterSlot::DomainSpecific,
            AdapterSlot::UserPreference,
        ] {
            assert_eq!(s.source_repo(), "sovereign-os");
        }
    }

    #[test]
    fn seven_pipeline_steps_positioned_1_to_7() {
        for (s, p) in [
            (PipelineStep::TraceCuration, 1),
            (PipelineStep::DatasetCreation, 2),
            (PipelineStep::LoraTraining, 3),
            (PipelineStep::AdapterServing, 4),
            (PipelineStep::EvalGating, 5),
            (PipelineStep::ProfileAssignment, 6),
            (PipelineStep::SignedPromotion, 7),
        ] {
            assert_eq!(s.position(), p);
        }
    }

    #[test]
    fn pipeline_walk_reaches_signed_promotion_in_6_advances() {
        let mut p = promo(AdapterSlot::CodingStyle);
        let mut steps = 0;
        while p.advance().is_ok() {
            steps += 1;
            if steps > 10 {
                panic!("loop did not terminate");
            }
        }
        assert_eq!(p.step, PipelineStep::SignedPromotion);
        // Advance past terminal returns Err PipelineTerminal
        assert!(matches!(
            p.advance().unwrap_err(),
            FoundryError::PipelineTerminal
        ));
    }

    #[test]
    fn eval_score_below_80_blocks_signed_promotion() {
        let mut p = promo(AdapterSlot::TddReview);
        p.eval_score = 70;
        // Walk to ProfileAssignment (step 6)
        for _ in 0..5 {
            p.advance().unwrap();
        }
        assert_eq!(p.step, PipelineStep::ProfileAssignment);
        // Advance to SignedPromotion should fail
        assert!(matches!(
            p.advance().unwrap_err(),
            FoundryError::EvalGateFailed(70)
        ));
    }

    #[test]
    fn unsigned_blocks_signed_promotion() {
        let mut p = promo(AdapterSlot::SpecDriven);
        p.signature = String::new();
        for _ in 0..5 {
            p.advance().unwrap();
        }
        assert!(matches!(
            p.advance().unwrap_err(),
            FoundryError::PromotionUnsigned
        ));
    }

    #[test]
    fn doctrine_verbatim() {
        assert_eq!(
            DOCTRINE_RUNTIME_FIRST,
            "Fine-tuning changes weights. Runtime adaptation changes behavior. Runtime adaptation comes first."
        );
    }

    #[test]
    fn runtime_decision_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&RuntimeDecision::UseAdapter).unwrap(),
            "\"use-adapter\""
        );
        assert_eq!(
            serde_json::to_string(&RuntimeDecision::StackMerge).unwrap(),
            "\"stack-merge\""
        );
        assert_eq!(
            serde_json::to_string(&RuntimeDecision::RouteSpecialist).unwrap(),
            "\"route-specialist\""
        );
        assert_eq!(
            serde_json::to_string(&RuntimeDecision::AskOracle).unwrap(),
            "\"ask-oracle\""
        );
    }

    #[test]
    fn adapter_slot_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&AdapterSlot::SelfdefSecurity).unwrap(),
            "\"selfdef-security\""
        );
        assert_eq!(
            serde_json::to_string(&AdapterSlot::UserPreference).unwrap(),
            "\"user-preference\""
        );
        assert_eq!(
            serde_json::to_string(&AdapterSlot::CommunicationMediation).unwrap(),
            "\"communication-mediation\""
        );
    }

    #[test]
    fn pipeline_step_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&PipelineStep::LoraTraining).unwrap(),
            "\"lora-training\""
        );
        assert_eq!(
            serde_json::to_string(&PipelineStep::SignedPromotion).unwrap(),
            "\"signed-promotion\""
        );
    }

    #[test]
    fn promotion_serde_roundtrip() {
        let p = promo(AdapterSlot::DomainSpecific);
        let j = serde_json::to_string(&p).unwrap();
        let back: AdapterPromotion = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
