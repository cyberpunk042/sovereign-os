//! The PRM branch critic — the behavioral half of the value plane.
//!
//! The data model in `lib.rs` defines *what* a reward is (the 12-axis
//! [`RewardVector`]) and *how a profile weights it* ([`ProfileWeights`]).
//! This module is the part that actually answers the value-plane
//! questions (F02222-F02228): given a branch of reasoning, **is this
//! thought worth expanding? likely correct? safe? done?**
//!
//! It implements the PRM-as-branch-critic contract:
//!
//! - inputs (M00450, F02246-F02250): [`BranchState`] — partial reasoning,
//!   tool observations, memory evidence, the candidate next step, and the
//!   measured [`RewardVector`] for the branch so far.
//! - outputs (M00451, F02251-F02255): [`BranchAssessment`] — `step_score`,
//!   `risk_score`, `uncertainty`, `failure_mode`, `suggested_next_action`.
//!
//! On top of single-branch assessment it provides **best-of-N selection**
//! (M00444, F02218) and a **compute-justification** gate (F02228 — "how
//! much more compute is justified?") bounded by the
//! [`IntelligenceTier`] fanout budget.
//!
//! The PRM scores *intermediate steps*, not just final answers (F02215):
//! `assess` runs on a partial branch.

use crate::{DOCTRINE_THOUGHTS_DESERVE_MORE_LIFE, IntelligenceTier, ProfileWeights, RewardVector};
use serde::{Deserialize, Serialize};

/// A branch of reasoning presented to the critic (M00450).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BranchState {
    /// Stable branch identifier.
    pub branch_id: u64,
    /// Partial reasoning trace so far (F02247).
    pub partial_reasoning: String,
    /// Observations returned by tools on this branch (F02248).
    pub tool_observations: Vec<String>,
    /// Memory evidence wired into this branch (F02249).
    pub memory_evidence: Vec<String>,
    /// The candidate next step under consideration (F02250).
    pub candidate_next_step: String,
    /// Measured reward signals for the branch so far.
    pub reward: RewardVector,
}

impl BranchState {
    /// A minimal branch carrying just an id and its reward signals.
    pub fn from_reward(branch_id: u64, reward: RewardVector) -> Self {
        Self {
            branch_id,
            partial_reasoning: String::new(),
            tool_observations: Vec::new(),
            memory_evidence: Vec::new(),
            candidate_next_step: String::new(),
            reward,
        }
    }
}

/// Why a branch is judged to be failing (M00451 `failure_mode`, F02254).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum FailureMode {
    /// No failure detected.
    None,
    /// Typed/contract output is invalid.
    SchemaInvalid,
    /// A tool invocation on the branch failed.
    ToolFailure,
    /// Tests on the branch failed.
    TestFailure,
    /// Risk exceeds the critic's ceiling.
    HighRisk,
    /// Confidence too low to act on yet.
    LowConfidence,
}

impl FailureMode {
    /// Whether this failure mode is *hard* — a branch in this state should
    /// be pruned, not expanded.
    pub fn is_hard(self) -> bool {
        matches!(
            self,
            FailureMode::SchemaInvalid
                | FailureMode::ToolFailure
                | FailureMode::TestFailure
                | FailureMode::HighRisk
        )
    }
}

/// What the critic recommends doing with a branch (M00451
/// `suggested_next_action`, F02255).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum NextAction {
    /// Good enough and certain enough — return this branch's answer.
    Commit,
    /// Promising but unfinished — expand it further.
    Expand,
    /// Uncertain — spend more compute (more samples / deeper search).
    NeedMoreCompute,
    /// Failing — abandon this branch.
    Prune,
}

/// The critic's verdict on a branch (M00451).
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct BranchAssessment {
    /// Branch this assessment is for.
    pub branch_id: u64,
    /// Profile-weighted aggregate value of the branch, `0..=1` (F02251).
    pub step_score: f32,
    /// Risk score, `0..=1` (higher = riskier) (F02252).
    pub risk_score: f32,
    /// Uncertainty, `0..=1` (higher = less sure) (F02253).
    pub uncertainty: f32,
    /// Diagnosed failure mode (F02254).
    pub failure_mode: FailureMode,
    /// Recommended next action (F02255).
    pub suggested_next_action: NextAction,
}

/// The branch critic. Holds the active profile weighting plus the
/// decision thresholds that turn scores into actions.
#[derive(Debug, Clone)]
pub struct BranchCritic {
    /// Profile weighting applied to each branch's reward vector.
    pub weights: ProfileWeights,
    /// `step_score` at/above which a certain branch may commit.
    pub commit_threshold: f32,
    /// `risk_score` above which a branch is judged [`FailureMode::HighRisk`].
    pub risk_ceiling: f32,
    /// `uncertainty` above which more compute is required before acting.
    pub uncertainty_ceiling: f32,
}

impl BranchCritic {
    /// Critic with the documented default thresholds for a given weighting.
    pub fn new(weights: ProfileWeights) -> Self {
        Self {
            weights,
            commit_threshold: 0.75,
            risk_ceiling: 0.70,
            uncertainty_ceiling: 0.40,
        }
    }

    /// Critic for one of the canonical profiles (`fast` / `careful` /
    /// `autonomous` / `creative` / `private`). Returns `None` for unknown.
    pub fn for_profile(profile: &str) -> Option<Self> {
        ProfileWeights::for_profile(profile).map(Self::new)
    }

    /// The doctrine this critic enforces.
    pub fn doctrine(&self) -> &'static str {
        DOCTRINE_THOUGHTS_DESERVE_MORE_LIFE
    }

    /// Assess a single branch (PRM on an intermediate step, F02215).
    pub fn assess(&self, branch: &BranchState) -> BranchAssessment {
        let r = &branch.reward;
        let step_score = self.weights.aggregate(r);
        let risk_score = r.risk;
        // Uncertainty rises as calibration falls; tool/test gaps add to it.
        let uncertainty = (1.0 - r.confidence_calibration).clamp(0.0, 1.0);

        let failure_mode = self.classify_failure(r, risk_score, uncertainty);
        let suggested_next_action = self.decide(step_score, uncertainty, failure_mode);

        BranchAssessment {
            branch_id: branch.branch_id,
            step_score,
            risk_score,
            uncertainty,
            failure_mode,
            suggested_next_action,
        }
    }

    fn classify_failure(&self, r: &RewardVector, risk: f32, uncertainty: f32) -> FailureMode {
        if r.schema_validity < 0.5 {
            FailureMode::SchemaInvalid
        } else if r.tool_success < 0.5 {
            FailureMode::ToolFailure
        } else if r.test_success < 0.5 {
            FailureMode::TestFailure
        } else if risk > self.risk_ceiling {
            FailureMode::HighRisk
        } else if uncertainty > self.uncertainty_ceiling {
            FailureMode::LowConfidence
        } else {
            FailureMode::None
        }
    }

    fn decide(&self, step_score: f32, uncertainty: f32, failure: FailureMode) -> NextAction {
        if failure.is_hard() {
            NextAction::Prune
        } else if step_score >= self.commit_threshold && uncertainty <= self.uncertainty_ceiling {
            NextAction::Commit
        } else if uncertainty > self.uncertainty_ceiling {
            NextAction::NeedMoreCompute
        } else {
            NextAction::Expand
        }
    }

    /// Best-of-N selection (M00444, F02218): assess every candidate and
    /// return the highest-value *non-pruned* branch — "which thought
    /// deserves more life". Ties break toward lower risk, then lower id.
    /// Returns `None` if every branch is a hard failure.
    pub fn select_best_of_n(&self, branches: &[BranchState]) -> Option<BranchAssessment> {
        branches
            .iter()
            .map(|b| self.assess(b))
            .filter(|a| !a.failure_mode.is_hard())
            .max_by(|a, b| {
                a.step_score
                    .total_cmp(&b.step_score)
                    .then(b.risk_score.total_cmp(&a.risk_score)) // lower risk wins
                    .then(b.branch_id.cmp(&a.branch_id)) // lower id wins
            })
    }

    /// How much more compute is justified (F02228): expanding/sampling
    /// further is justified only while the best branch is still uncertain
    /// **and** the tier's fanout budget is not yet spent.
    pub fn compute_justified(
        &self,
        best: &BranchAssessment,
        tier: IntelligenceTier,
        expansions_so_far: u32,
    ) -> bool {
        best.uncertainty > self.uncertainty_ceiling && expansions_so_far < tier.fanout()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A strong, certain branch.
    fn good_reward() -> RewardVector {
        RewardVector {
            correctness: 0.95,
            evidence: 0.9,
            schema_validity: 1.0,
            tool_success: 1.0,
            test_success: 1.0,
            risk: 0.1,
            latency: 0.2,
            cost: 0.2,
            novelty: 0.5,
            user_preference: 0.8,
            cache_reuse: 0.6,
            confidence_calibration: 0.95,
        }
    }

    #[test]
    fn strong_certain_branch_commits() {
        let critic = BranchCritic::for_profile("careful").unwrap();
        let a = critic.assess(&BranchState::from_reward(1, good_reward()));
        assert_eq!(a.failure_mode, FailureMode::None);
        assert_eq!(a.suggested_next_action, NextAction::Commit);
        assert!(a.step_score >= critic.commit_threshold);
    }

    #[test]
    fn schema_invalid_branch_is_pruned() {
        let critic = BranchCritic::for_profile("careful").unwrap();
        let mut r = good_reward();
        r.schema_validity = 0.0;
        let a = critic.assess(&BranchState::from_reward(2, r));
        assert_eq!(a.failure_mode, FailureMode::SchemaInvalid);
        assert_eq!(a.suggested_next_action, NextAction::Prune);
    }

    #[test]
    fn high_risk_branch_is_pruned() {
        let critic = BranchCritic::for_profile("careful").unwrap();
        let mut r = good_reward();
        r.risk = 0.9;
        let a = critic.assess(&BranchState::from_reward(3, r));
        assert_eq!(a.failure_mode, FailureMode::HighRisk);
        assert_eq!(a.suggested_next_action, NextAction::Prune);
        assert_eq!(a.risk_score, 0.9);
    }

    #[test]
    fn uncertain_branch_needs_more_compute() {
        let critic = BranchCritic::for_profile("careful").unwrap();
        let mut r = good_reward();
        r.confidence_calibration = 0.3; // uncertainty 0.7 > ceiling 0.4
        let a = critic.assess(&BranchState::from_reward(4, r));
        assert_eq!(a.failure_mode, FailureMode::LowConfidence);
        assert_eq!(a.suggested_next_action, NextAction::NeedMoreCompute);
        assert!((a.uncertainty - 0.7).abs() < 1e-6);
    }

    #[test]
    fn mid_score_certain_branch_expands() {
        let critic = BranchCritic::for_profile("careful").unwrap();
        // Certain (calibration high) but middling value -> not commit, not fail.
        let r = RewardVector {
            correctness: 0.6,
            evidence: 0.55,
            schema_validity: 1.0,
            tool_success: 1.0,
            test_success: 1.0,
            risk: 0.3,
            latency: 0.4,
            cost: 0.4,
            novelty: 0.5,
            user_preference: 0.5,
            cache_reuse: 0.5,
            confidence_calibration: 0.9, // uncertainty 0.1 <= ceiling
        };
        let a = critic.assess(&BranchState::from_reward(5, r));
        assert_eq!(a.failure_mode, FailureMode::None);
        assert!(a.step_score < critic.commit_threshold);
        assert_eq!(a.suggested_next_action, NextAction::Expand);
    }

    #[test]
    fn best_of_n_picks_highest_value_non_pruned() {
        let critic = BranchCritic::for_profile("careful").unwrap();
        let mut weak = good_reward();
        weak.correctness = 0.6;
        weak.evidence = 0.5;
        let mut bad = good_reward();
        bad.schema_validity = 0.0; // hard failure -> excluded

        let branches = vec![
            BranchState::from_reward(10, weak),
            BranchState::from_reward(20, good_reward()),
            BranchState::from_reward(30, bad),
        ];
        let best = critic.select_best_of_n(&branches).unwrap();
        assert_eq!(best.branch_id, 20, "the strong branch should win");
    }

    #[test]
    fn best_of_n_all_hard_failures_returns_none() {
        let critic = BranchCritic::for_profile("careful").unwrap();
        let mut bad = good_reward();
        bad.schema_validity = 0.0;
        let branches = vec![
            BranchState::from_reward(1, bad.clone()),
            BranchState::from_reward(2, bad),
        ];
        assert!(critic.select_best_of_n(&branches).is_none());
    }

    #[test]
    fn compute_justified_only_while_uncertain_and_in_budget() {
        let critic = BranchCritic::for_profile("careful").unwrap();
        let uncertain = BranchAssessment {
            branch_id: 1,
            step_score: 0.5,
            risk_score: 0.2,
            uncertainty: 0.8,
            failure_mode: FailureMode::LowConfidence,
            suggested_next_action: NextAction::NeedMoreCompute,
        };
        // Deliberate tier fanout = 16.
        assert!(critic.compute_justified(&uncertain, IntelligenceTier::Deliberate, 4));
        // Budget spent -> stop.
        assert!(!critic.compute_justified(&uncertain, IntelligenceTier::Deliberate, 16));
        // Certain branch -> no more compute justified.
        let certain = BranchAssessment {
            uncertainty: 0.1,
            ..uncertain
        };
        assert!(!critic.compute_justified(&certain, IntelligenceTier::Deliberate, 0));
    }

    #[test]
    fn profile_changes_the_verdict() {
        // A fast-profile branch that trades correctness for latency can score
        // differently than under careful — proving weights actually bite.
        let r = RewardVector {
            correctness: 0.7,
            evidence: 0.6,
            schema_validity: 1.0,
            tool_success: 1.0,
            test_success: 1.0,
            risk: 0.2,
            latency: 0.05, // very fast
            cost: 0.1,
            novelty: 0.5,
            user_preference: 0.6,
            cache_reuse: 0.95,
            confidence_calibration: 0.9,
        };
        let fast = BranchCritic::for_profile("fast")
            .unwrap()
            .assess(&BranchState::from_reward(1, r.clone()));
        let careful = BranchCritic::for_profile("careful")
            .unwrap()
            .assess(&BranchState::from_reward(1, r));
        // fast profile rewards the low latency + cache reuse more highly.
        assert!(fast.step_score > careful.step_score);
    }

    #[test]
    fn unknown_profile_is_none() {
        assert!(BranchCritic::for_profile("nope").is_none());
    }

    #[test]
    fn doctrine_surface() {
        let critic = BranchCritic::for_profile("fast").unwrap();
        assert_eq!(critic.doctrine(), DOCTRINE_THOUGHTS_DESERVE_MORE_LIFE);
    }
}
