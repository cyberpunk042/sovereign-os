//! `sovereign-learning-signals` — E0555: Learn (lifecycle step 11).
//!
//! "Continuity is preserving the chain from intent to action to consequence to
//! **learning**." After a task settles, the system learns without touching
//! weights first — seven immediate signals — and later, deferred, curates a
//! dataset and trains a LoRA adapter. This crate fixes both taxonomies and
//! which immediate signals fire for a given outcome.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The 7 immediate learning signals (E0555, "without changing weights first").
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LearningSignal {
    /// Store the trace.
    StoreTrace,
    /// Update memory.
    UpdateMemory,
    /// Update route statistics.
    UpdateRouteStats,
    /// Add an eval case.
    AddEvalCase,
    /// Promote a skill.
    PromoteSkill,
    /// Adjust profile defaults.
    AdjustProfileDefaults,
    /// Tag a model failure.
    TagModelFailure,
}

impl LearningSignal {
    /// All 7 immediate signals.
    pub const ALL: [LearningSignal; 7] = [
        LearningSignal::StoreTrace,
        LearningSignal::UpdateMemory,
        LearningSignal::UpdateRouteStats,
        LearningSignal::AddEvalCase,
        LearningSignal::PromoteSkill,
        LearningSignal::AdjustProfileDefaults,
        LearningSignal::TagModelFailure,
    ];
}

/// The 4 deferred LoRA-adaptation steps (E0555, "later").
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DeferredLoraStep {
    /// Curate a dataset.
    CurateDataset,
    /// Train a LoRA adapter.
    TrainLora,
    /// Evaluate the adapter.
    EvaluateAdapter,
    /// Promote the adapter.
    PromoteAdapter,
}

impl DeferredLoraStep {
    /// All 4 deferred steps, in order.
    pub const ALL: [DeferredLoraStep; 4] = [
        DeferredLoraStep::CurateDataset,
        DeferredLoraStep::TrainLora,
        DeferredLoraStep::EvaluateAdapter,
        DeferredLoraStep::PromoteAdapter,
    ];
}

/// How a task settled (drives which signals fire).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TaskOutcome {
    /// The task committed successfully.
    Success,
    /// The task failed / rolled back.
    Failure,
}

/// Derive the immediate learning signals for an outcome.
///
/// Four signals always fire (store-trace / update-memory / update-route-stats /
/// add-eval-case — every settled task feeds the chain). On success the system
/// additionally promotes the skill and adjusts profile defaults; on failure it
/// tags the model failure instead. Returned in canonical [`LearningSignal::ALL`]
/// order.
#[must_use]
pub fn derive_learning(outcome: TaskOutcome) -> Vec<LearningSignal> {
    let mut out = vec![
        LearningSignal::StoreTrace,
        LearningSignal::UpdateMemory,
        LearningSignal::UpdateRouteStats,
        LearningSignal::AddEvalCase,
    ];
    match outcome {
        TaskOutcome::Success => {
            out.push(LearningSignal::PromoteSkill);
            out.push(LearningSignal::AdjustProfileDefaults);
        }
        TaskOutcome::Failure => out.push(LearningSignal::TagModelFailure),
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seven_immediate_four_deferred_distinct() {
        use std::collections::HashSet;
        assert_eq!(LearningSignal::ALL.len(), 7);
        assert_eq!(LearningSignal::ALL.iter().collect::<HashSet<_>>().len(), 7);
        assert_eq!(DeferredLoraStep::ALL.len(), 4);
    }

    #[test]
    fn every_outcome_feeds_the_chain_baseline() {
        // store-trace / update-memory / update-route-stats / add-eval-case
        // fire regardless of outcome.
        for o in [TaskOutcome::Success, TaskOutcome::Failure] {
            let s = derive_learning(o);
            for base in [
                LearningSignal::StoreTrace,
                LearningSignal::UpdateMemory,
                LearningSignal::UpdateRouteStats,
                LearningSignal::AddEvalCase,
            ] {
                assert!(s.contains(&base), "{o:?} missing {base:?}");
            }
        }
    }

    #[test]
    fn success_promotes_failure_tags() {
        let ok = derive_learning(TaskOutcome::Success);
        assert!(ok.contains(&LearningSignal::PromoteSkill));
        assert!(ok.contains(&LearningSignal::AdjustProfileDefaults));
        assert!(!ok.contains(&LearningSignal::TagModelFailure));

        let bad = derive_learning(TaskOutcome::Failure);
        assert!(bad.contains(&LearningSignal::TagModelFailure));
        assert!(!bad.contains(&LearningSignal::PromoteSkill));
    }

    #[test]
    fn lora_steps_are_ordered_curate_first_promote_last() {
        assert_eq!(DeferredLoraStep::ALL[0], DeferredLoraStep::CurateDataset);
        assert_eq!(DeferredLoraStep::ALL[3], DeferredLoraStep::PromoteAdapter);
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&LearningSignal::UpdateRouteStats).unwrap(),
            "\"update-route-stats\""
        );
        assert_eq!(
            serde_json::to_string(&DeferredLoraStep::TrainLora).unwrap(),
            "\"train-lora\""
        );
    }
}
