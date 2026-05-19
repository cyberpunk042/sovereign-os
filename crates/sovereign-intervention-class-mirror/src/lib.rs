//! `sovereign-intervention-class-mirror` — M079 intervention class taxonomy.
//!
//! Per arXiv 2604.09839 ("Steered LLM Activations are Non-Surjective"),
//! activation steering provably pushes the residual stream off the
//! manifold of states reachable from discrete prompts. The practical
//! consequence: a benchmark that proves a model is jailbreakable via
//! white-box activation steering proves NOTHING about black-box prompt
//! vulnerability, and vice versa.
//!
//! This crate exposes a typed taxonomy of intervention classes for
//! eval-protocol separation. Every benchmark, every red-team report,
//! every safety eval should carry an [`InterventionClass`] tag so
//! downstream consumers cannot conflate white-box and black-box claims.
//!
//! Doctrinal preservation — verbatim from arXiv 2604.09839 §4:
//!
//! > "almost surely, no prompt can reproduce"
//!
//! This string is exposed as [`DOCTRINE_NON_SURJECTIVE`] and embedded
//! in the snapshot envelope; consumers MUST refuse drift.
//!
//! Standing rule: We do not minimize anything. We catalogue published
//! peer-reviewed interpretability theory; we do not invent.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the intervention-class mirror.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Verbatim doctrine string surfaced per M079 R(non-surjectivity).
pub const DOCTRINE_NON_SURJECTIVE: &str = "almost surely, no prompt can reproduce";

/// Intervention class taxonomy per arXiv 2604.09839 §3.
///
/// A given benchmark or red-team finding belongs to **exactly one**
/// class. Mixed-class evaluations decompose into per-class subsets.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum InterventionClass {
    /// Black-box prompt — only input text is varied; weights + activations untouched.
    BlackBoxPrompt,
    /// White-box activation steering — residual-stream vectors modified at inference.
    WhiteBoxActivationSteer,
    /// White-box weight edit — model parameters mutated (LoRA / ROME / MEMIT / fine-tune).
    WhiteBoxWeightEdit,
    /// White-box logit edit — output distribution post-processing (logit-bias / lens steering).
    WhiteBoxLogitEdit,
    /// Mixed / undisclosed — refuses to accept the evidence at face value.
    MixedUndisclosed,
}

impl InterventionClass {
    /// Whether this class is white-box (requires internal access).
    pub fn is_white_box(self) -> bool {
        matches!(
            self,
            InterventionClass::WhiteBoxActivationSteer
                | InterventionClass::WhiteBoxWeightEdit
                | InterventionClass::WhiteBoxLogitEdit
        )
    }

    /// Whether this class is black-box (input-only).
    pub fn is_black_box(self) -> bool {
        self == InterventionClass::BlackBoxPrompt
    }

    /// Whether eval-protocol separation per arXiv 2604.09839 forbids
    /// generalising a finding in `from` to claims about `to`.
    pub fn requires_protocol_separation(from: Self, to: Self) -> bool {
        // White-box → black-box and vice versa: separated per the proof.
        // Mixed/undisclosed: never separable until decomposed.
        if from == InterventionClass::MixedUndisclosed || to == InterventionClass::MixedUndisclosed {
            return true;
        }
        from.is_white_box() != to.is_white_box()
    }
}

/// Eval claim with intervention-class tag.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct EvalClaim {
    /// Benchmark identifier (e.g. "HarmBench-v2 / activation-steer-subset").
    pub benchmark: String,
    /// Intervention class.
    pub class: InterventionClass,
    /// Claimed result (free-text; consumer parses).
    pub claim: String,
    /// Model under test (canonical id).
    pub model: String,
    /// ISO-8601 UTC timestamp.
    pub captured_at: String,
    /// Optional cross-class reference (e.g. WB result paired with BB control).
    pub cross_class_reference: Option<String>,
}

/// Aggregate counts per class, suitable for D-10 / D-16 cross-link.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClassSummary {
    /// Intervention class.
    pub class: InterventionClass,
    /// Count of claims in this class.
    pub count: u32,
}

/// Top-level mirror snapshot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct InterventionMirrorSnapshot {
    /// Wire-stable schema version. MUST equal [`SCHEMA_VERSION`].
    pub schema_version: String,
    /// Doctrine surface — MUST equal [`DOCTRINE_NON_SURJECTIVE`].
    pub doctrine: String,
    /// ISO-8601 UTC capture timestamp.
    pub captured_at: String,
    /// Per-class tiles.
    pub summaries: Vec<ClassSummary>,
    /// Full eval-claim list.
    pub claims: Vec<EvalClaim>,
    /// MS003 signature over the canonical-JSON encoding.
    pub signature: String,
}

/// Errors a consumer may surface.
#[derive(Debug, Error)]
pub enum MirrorError {
    /// Schema major version mismatch.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected version.
        expected: String,
        /// Observed version.
        actual: String,
    },
    /// Doctrine surface tampered.
    #[error("doctrine surface tampered: expected verbatim \"{expected}\", got \"{actual}\"")]
    DoctrineTampered {
        /// Expected canonical doctrine.
        expected: String,
        /// Observed (tampered) value.
        actual: String,
    },
    /// Cross-class generalisation refused per protocol-separation invariant.
    #[error("cross-class generalisation refused: {from:?} → {to:?} requires separated protocol per arXiv 2604.09839")]
    ProtocolSeparationViolation {
        /// Source class.
        from: InterventionClass,
        /// Target class.
        to: InterventionClass,
    },
}

impl InterventionMirrorSnapshot {
    /// Validate schema version. Same-major bumps OK.
    pub fn validate_schema(&self) -> Result<(), MirrorError> {
        if self.schema_version == SCHEMA_VERSION {
            return Ok(());
        }
        let snap_major = self.schema_version.split('.').next().unwrap_or("");
        let exp_major = SCHEMA_VERSION.split('.').next().unwrap_or("");
        if snap_major != exp_major {
            return Err(MirrorError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        Ok(())
    }

    /// Validate doctrine string verbatim.
    pub fn validate_doctrine(&self) -> Result<(), MirrorError> {
        if self.doctrine != DOCTRINE_NON_SURJECTIVE {
            return Err(MirrorError::DoctrineTampered {
                expected: DOCTRINE_NON_SURJECTIVE.into(),
                actual: self.doctrine.clone(),
            });
        }
        Ok(())
    }

    /// Aggregate claims by class.
    pub fn recompute_summaries(&self) -> Vec<ClassSummary> {
        use std::collections::HashMap;
        let mut m: HashMap<InterventionClass, u32> = HashMap::new();
        for c in &self.claims {
            *m.entry(c.class).or_insert(0) += 1;
        }
        let mut out: Vec<ClassSummary> = m.into_iter()
            .map(|(class, count)| ClassSummary { class, count })
            .collect();
        out.sort_by_key(|s| match s.class {
            InterventionClass::BlackBoxPrompt => 0,
            InterventionClass::WhiteBoxActivationSteer => 1,
            InterventionClass::WhiteBoxWeightEdit => 2,
            InterventionClass::WhiteBoxLogitEdit => 3,
            InterventionClass::MixedUndisclosed => 4,
        });
        out
    }

    /// Refuse a generalisation that mixes intervention classes.
    /// Returns Ok if `from` and `to` share the same access regime.
    pub fn assert_can_generalise(
        from: InterventionClass,
        to: InterventionClass,
    ) -> Result<(), MirrorError> {
        if InterventionClass::requires_protocol_separation(from, to) {
            return Err(MirrorError::ProtocolSeparationViolation { from, to });
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mk_claim(bench: &str, class: InterventionClass) -> EvalClaim {
        EvalClaim {
            benchmark: bench.into(),
            class,
            claim: "harmful output rate 12%".into(),
            model: "test-model".into(),
            captured_at: "2026-05-19T03:30:00Z".into(),
            cross_class_reference: None,
        }
    }
    fn mk_snap(claims: Vec<EvalClaim>) -> InterventionMirrorSnapshot {
        InterventionMirrorSnapshot {
            schema_version: SCHEMA_VERSION.into(),
            doctrine: DOCTRINE_NON_SURJECTIVE.into(),
            captured_at: "2026-05-19T03:30:00Z".into(),
            summaries: vec![],
            claims,
            signature: String::new(),
        }
    }

    #[test]
    fn schema_validates_canonical() {
        mk_snap(vec![]).validate_schema().unwrap();
    }

    #[test]
    fn doctrine_verbatim_preservation() {
        mk_snap(vec![]).validate_doctrine().unwrap();
    }

    #[test]
    fn doctrine_tamper_is_caught() {
        let mut s = mk_snap(vec![]);
        s.doctrine = "prompt can reproduce".into();  // tampered
        assert!(matches!(s.validate_doctrine().unwrap_err(), MirrorError::DoctrineTampered { .. }));
    }

    #[test]
    fn white_box_classification() {
        assert!(InterventionClass::WhiteBoxActivationSteer.is_white_box());
        assert!(InterventionClass::WhiteBoxWeightEdit.is_white_box());
        assert!(InterventionClass::WhiteBoxLogitEdit.is_white_box());
        assert!(!InterventionClass::BlackBoxPrompt.is_white_box());
        assert!(InterventionClass::BlackBoxPrompt.is_black_box());
    }

    #[test]
    fn protocol_separation_required_wb_to_bb() {
        // WB → BB generalisation refused per arXiv 2604.09839 proof.
        assert!(InterventionMirrorSnapshot::assert_can_generalise(
            InterventionClass::WhiteBoxActivationSteer,
            InterventionClass::BlackBoxPrompt,
        ).is_err());
    }

    #[test]
    fn protocol_separation_required_bb_to_wb() {
        assert!(InterventionMirrorSnapshot::assert_can_generalise(
            InterventionClass::BlackBoxPrompt,
            InterventionClass::WhiteBoxWeightEdit,
        ).is_err());
    }

    #[test]
    fn within_white_box_generalisation_allowed() {
        InterventionMirrorSnapshot::assert_can_generalise(
            InterventionClass::WhiteBoxActivationSteer,
            InterventionClass::WhiteBoxWeightEdit,
        ).unwrap();
    }

    #[test]
    fn within_black_box_generalisation_allowed() {
        InterventionMirrorSnapshot::assert_can_generalise(
            InterventionClass::BlackBoxPrompt,
            InterventionClass::BlackBoxPrompt,
        ).unwrap();
    }

    #[test]
    fn mixed_undisclosed_always_separates() {
        // Any pairing with MixedUndisclosed should fail until decomposed.
        assert!(InterventionMirrorSnapshot::assert_can_generalise(
            InterventionClass::MixedUndisclosed,
            InterventionClass::BlackBoxPrompt,
        ).is_err());
        assert!(InterventionMirrorSnapshot::assert_can_generalise(
            InterventionClass::WhiteBoxActivationSteer,
            InterventionClass::MixedUndisclosed,
        ).is_err());
    }

    #[test]
    fn recompute_summaries_groups_by_class() {
        let snap = mk_snap(vec![
            mk_claim("bench-a", InterventionClass::BlackBoxPrompt),
            mk_claim("bench-b", InterventionClass::BlackBoxPrompt),
            mk_claim("bench-c", InterventionClass::WhiteBoxActivationSteer),
            mk_claim("bench-d", InterventionClass::WhiteBoxWeightEdit),
        ]);
        let s = snap.recompute_summaries();
        assert_eq!(s.len(), 3);
        let bb = s.iter().find(|x| x.class == InterventionClass::BlackBoxPrompt).unwrap();
        assert_eq!(bb.count, 2);
        let act = s.iter().find(|x| x.class == InterventionClass::WhiteBoxActivationSteer).unwrap();
        assert_eq!(act.count, 1);
    }

    #[test]
    fn claim_serde_roundtrip() {
        let original = mk_claim("h-bench", InterventionClass::WhiteBoxActivationSteer);
        let j = serde_json::to_string(&original).unwrap();
        let back: EvalClaim = serde_json::from_str(&j).unwrap();
        assert_eq!(original, back);
    }

    #[test]
    fn class_serde_uses_kebab_case() {
        assert_eq!(serde_json::to_string(&InterventionClass::WhiteBoxActivationSteer).unwrap(), "\"white-box-activation-steer\"");
        assert_eq!(serde_json::to_string(&InterventionClass::BlackBoxPrompt).unwrap(), "\"black-box-prompt\"");
        assert_eq!(serde_json::to_string(&InterventionClass::MixedUndisclosed).unwrap(), "\"mixed-undisclosed\"");
    }

    #[test]
    fn doctrine_constant_exposed_publicly() {
        assert_eq!(DOCTRINE_NON_SURJECTIVE, "almost surely, no prompt can reproduce");
    }
}
