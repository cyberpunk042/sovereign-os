//! `sovereign-value-plane` — M027 Value Plane.
//!
//! Per M027 + E0248-E0257 + dump 7731-8121:
//!
//! - **7-question contract** (E0250 M00447): thought-expand / branch-correct /
//!   tool-plan-safe / memory-trustworthy / answer-return / profile-choose /
//!   compute-justified.
//! - **12-axis reward vector** (E0251 M00448): correctness / evidence /
//!   schema_validity / tool_success / test_success / risk / latency /
//!   cost / novelty / user_preference / cache_reuse / confidence_calibration.
//! - **Profile-weighted reward** (M00449): each MS040 profile applies its
//!   own axis-weights for aggregation.
//! - **5-tier Intelligence Dial** (E0256): reflex / normal / deliberate /
//!   exhaustive / experimental.
//!
//! Doctrines preserved verbatim:
//!
//! > "PRM proposes value, CPU applies law, Oracle verifies high-stakes commitments"
//!   (E0252 dump 7849)
//!
//! > "Intelligence is knowing which thoughts deserve more life"
//!   (E0257 dump 8120 verbatim closing rule)
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine surface verbatim per E0252 dump 7849.
pub const DOCTRINE_PRM_PROPOSES: &str =
    "PRM proposes value, CPU applies law, Oracle verifies high-stakes commitments";

/// Closing-rule doctrine verbatim per E0257 dump 8120.
pub const DOCTRINE_THOUGHTS_DESERVE_MORE_LIFE: &str =
    "Intelligence is knowing which thoughts deserve more life";

/// 12 axes per M00448 + R04451..R04462.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RewardAxis {
    /// Correctness against ground-truth.
    Correctness,
    /// Evidence support (sources cited).
    Evidence,
    /// Schema validity (typed output passes contract).
    SchemaValidity,
    /// Tool invocation succeeded.
    ToolSuccess,
    /// Tests passed (MS009 + M020 layers).
    TestSuccess,
    /// Risk (MS042 declaration-vs-observed).
    Risk,
    /// Latency (lower better; inverted for aggregation).
    Latency,
    /// Cost (lower better; inverted for aggregation).
    Cost,
    /// Novelty (new useful information vs already-known).
    Novelty,
    /// User preference (operator approval / feedback).
    UserPreference,
    /// Cache reuse (KV / prompt-cache hit).
    CacheReuse,
    /// Confidence calibration (predicted vs realised accuracy).
    ConfidenceCalibration,
}

impl RewardAxis {
    /// Canonical position 1..12.
    pub fn position(self) -> u8 {
        match self {
            RewardAxis::Correctness => 1,
            RewardAxis::Evidence => 2,
            RewardAxis::SchemaValidity => 3,
            RewardAxis::ToolSuccess => 4,
            RewardAxis::TestSuccess => 5,
            RewardAxis::Risk => 6,
            RewardAxis::Latency => 7,
            RewardAxis::Cost => 8,
            RewardAxis::Novelty => 9,
            RewardAxis::UserPreference => 10,
            RewardAxis::CacheReuse => 11,
            RewardAxis::ConfidenceCalibration => 12,
        }
    }
    /// Whether the axis is inverted for aggregation (lower-is-better).
    pub fn inverted(self) -> bool {
        matches!(self, RewardAxis::Risk | RewardAxis::Latency | RewardAxis::Cost)
    }
}

/// 12-axis reward vector. Each axis carries a normalised 0..=1.0 score.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct RewardVector {
    /// Correctness score.
    pub correctness: f32,
    /// Evidence support score.
    pub evidence: f32,
    /// Schema validity (1.0 = valid).
    pub schema_validity: f32,
    /// Tool success rate.
    pub tool_success: f32,
    /// Test pass rate.
    pub test_success: f32,
    /// Risk score (0.0 = safest, 1.0 = riskiest — inverted for aggregation).
    pub risk: f32,
    /// Latency relative (0.0 = fastest, 1.0 = slowest — inverted).
    pub latency: f32,
    /// Cost relative (0.0 = cheapest, 1.0 = most expensive — inverted).
    pub cost: f32,
    /// Novelty score.
    pub novelty: f32,
    /// User preference score.
    pub user_preference: f32,
    /// Cache reuse hit rate.
    pub cache_reuse: f32,
    /// Confidence calibration score.
    pub confidence_calibration: f32,
}

impl RewardVector {
    /// Get the axis value (without inversion) by enum tag.
    pub fn get(&self, axis: RewardAxis) -> f32 {
        match axis {
            RewardAxis::Correctness => self.correctness,
            RewardAxis::Evidence => self.evidence,
            RewardAxis::SchemaValidity => self.schema_validity,
            RewardAxis::ToolSuccess => self.tool_success,
            RewardAxis::TestSuccess => self.test_success,
            RewardAxis::Risk => self.risk,
            RewardAxis::Latency => self.latency,
            RewardAxis::Cost => self.cost,
            RewardAxis::Novelty => self.novelty,
            RewardAxis::UserPreference => self.user_preference,
            RewardAxis::CacheReuse => self.cache_reuse,
            RewardAxis::ConfidenceCalibration => self.confidence_calibration,
        }
    }
    /// Return the contribution of each axis (with inversion handled).
    pub fn contribution(&self, axis: RewardAxis) -> f32 {
        let v = self.get(axis);
        if axis.inverted() { 1.0 - v } else { v }
    }
}

/// Per-profile axis weights. 12 weights, one per axis. Must sum to > 0.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ProfileWeights {
    /// Profile name (matches MS040 6-set).
    pub profile: String,
    /// Weights for the 12 axes in canonical order.
    pub weights: [f32; 12],
}

impl ProfileWeights {
    /// Aggregate a reward vector through these weights.
    /// Returns weighted sum normalised by sum-of-weights.
    pub fn aggregate(&self, v: &RewardVector) -> f32 {
        let axes = [
            RewardAxis::Correctness, RewardAxis::Evidence, RewardAxis::SchemaValidity,
            RewardAxis::ToolSuccess, RewardAxis::TestSuccess, RewardAxis::Risk,
            RewardAxis::Latency, RewardAxis::Cost, RewardAxis::Novelty,
            RewardAxis::UserPreference, RewardAxis::CacheReuse, RewardAxis::ConfidenceCalibration,
        ];
        let total_w: f32 = self.weights.iter().sum();
        if total_w <= 0.0 {
            return 0.0;
        }
        let mut acc = 0.0;
        for (i, axis) in axes.iter().enumerate() {
            acc += self.weights[i] * v.contribution(*axis);
        }
        acc / total_w
    }

    /// Canonical weights for the 5 examples documented in M00449.
    pub fn for_profile(profile: &str) -> Option<ProfileWeights> {
        let p = profile;
        let weights = match p {
            "fast" => [
                /* correctness */ 0.6, /* evidence */ 0.3, /* schema */ 0.8,
                /* tool */ 0.7, /* tests */ 0.5, /* risk */ 0.4,
                /* latency */ 1.0, /* cost */ 0.8, /* novelty */ 0.3,
                /* user_pref */ 0.4, /* cache_reuse */ 0.9, /* conf_calib */ 0.5,
            ],
            "careful" => [
                1.0, 0.9, 1.0, 0.9, 1.0, 0.9, 0.4, 0.5, 0.4, 0.7, 0.5, 0.9,
            ],
            "autonomous" => [
                0.9, 0.9, 1.0, 0.9, 0.9, 0.8, 0.6, 0.6, 0.5, 0.7, 0.7, 0.8,
            ],
            "creative" => [
                0.6, 0.5, 0.6, 0.6, 0.5, 0.5, 0.6, 0.5, 1.0, 0.8, 0.4, 0.5,
            ],
            "private" => [
                0.9, 0.9, 1.0, 0.9, 0.9, 1.0, 0.5, 0.7, 0.4, 0.8, 0.5, 0.8,
            ],
            _ => return None,
        };
        Some(ProfileWeights { profile: profile.into(), weights })
    }
}

/// 5-tier Intelligence Dial per E0256.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum IntelligenceTier {
    /// Reflex — single-pass, lowest compute.
    Reflex,
    /// Normal — small N best-of-N.
    Normal,
    /// Deliberate — multi-step plan + verify.
    Deliberate,
    /// Exhaustive — MCTS + PRM.
    Exhaustive,
    /// Experimental — unbounded budget within profile gates.
    Experimental,
}

impl IntelligenceTier {
    /// Suggested branch-fanout multiplier (compute amplifier).
    pub fn fanout(self) -> u32 {
        match self {
            IntelligenceTier::Reflex => 1,
            IntelligenceTier::Normal => 4,
            IntelligenceTier::Deliberate => 16,
            IntelligenceTier::Exhaustive => 64,
            IntelligenceTier::Experimental => 256,
        }
    }
}

/// Errors.
#[derive(Debug, Error)]
pub enum ValuePlaneError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Axis value outside [0.0, 1.0].
    #[error("axis {axis:?} value {value} outside [0.0, 1.0]")]
    AxisOutOfRange {
        /// Axis.
        axis: RewardAxis,
        /// Value.
        value: f32,
    },
    /// Doctrine surface tampered.
    #[error("doctrine tampered: expected verbatim \"{expected}\"")]
    DoctrineTampered {
        /// Expected.
        expected: String,
    },
}

/// Validate a reward vector — every axis must be in [0.0, 1.0] + finite.
pub fn validate(v: &RewardVector) -> Result<(), ValuePlaneError> {
    let axes = [
        (RewardAxis::Correctness, v.correctness),
        (RewardAxis::Evidence, v.evidence),
        (RewardAxis::SchemaValidity, v.schema_validity),
        (RewardAxis::ToolSuccess, v.tool_success),
        (RewardAxis::TestSuccess, v.test_success),
        (RewardAxis::Risk, v.risk),
        (RewardAxis::Latency, v.latency),
        (RewardAxis::Cost, v.cost),
        (RewardAxis::Novelty, v.novelty),
        (RewardAxis::UserPreference, v.user_preference),
        (RewardAxis::CacheReuse, v.cache_reuse),
        (RewardAxis::ConfidenceCalibration, v.confidence_calibration),
    ];
    for (axis, value) in axes {
        if !value.is_finite() || !(0.0..=1.0).contains(&value) {
            return Err(ValuePlaneError::AxisOutOfRange { axis, value });
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn perfect() -> RewardVector {
        RewardVector {
            correctness: 1.0, evidence: 1.0, schema_validity: 1.0,
            tool_success: 1.0, test_success: 1.0,
            risk: 0.0, latency: 0.0, cost: 0.0,
            novelty: 1.0, user_preference: 1.0, cache_reuse: 1.0,
            confidence_calibration: 1.0,
        }
    }

    // --- 12 axes positioned 1..12 ---

    #[test]
    fn twelve_axes_positioned_correctly() {
        let order = [
            (RewardAxis::Correctness, 1), (RewardAxis::Evidence, 2),
            (RewardAxis::SchemaValidity, 3), (RewardAxis::ToolSuccess, 4),
            (RewardAxis::TestSuccess, 5), (RewardAxis::Risk, 6),
            (RewardAxis::Latency, 7), (RewardAxis::Cost, 8),
            (RewardAxis::Novelty, 9), (RewardAxis::UserPreference, 10),
            (RewardAxis::CacheReuse, 11), (RewardAxis::ConfidenceCalibration, 12),
        ];
        for (a, p) in order {
            assert_eq!(a.position(), p);
        }
    }

    #[test]
    fn risk_latency_cost_inverted() {
        assert!(RewardAxis::Risk.inverted());
        assert!(RewardAxis::Latency.inverted());
        assert!(RewardAxis::Cost.inverted());
        assert!(!RewardAxis::Correctness.inverted());
        assert!(!RewardAxis::Evidence.inverted());
    }

    // --- contribution() ---

    #[test]
    fn perfect_vector_contribution_all_one() {
        let v = perfect();
        for axis in [
            RewardAxis::Correctness, RewardAxis::Evidence, RewardAxis::SchemaValidity,
            RewardAxis::ToolSuccess, RewardAxis::TestSuccess, RewardAxis::Risk,
            RewardAxis::Latency, RewardAxis::Cost, RewardAxis::Novelty,
            RewardAxis::UserPreference, RewardAxis::CacheReuse, RewardAxis::ConfidenceCalibration,
        ] {
            assert!((v.contribution(axis) - 1.0).abs() < 1e-6, "axis {axis:?}");
        }
    }

    #[test]
    fn risk_05_contribution_is_05() {
        let mut v = perfect();
        v.risk = 0.5;
        assert!((v.contribution(RewardAxis::Risk) - 0.5).abs() < 1e-6);
    }

    #[test]
    fn correctness_03_contribution_is_03() {
        let mut v = perfect();
        v.correctness = 0.3;
        assert!((v.contribution(RewardAxis::Correctness) - 0.3).abs() < 1e-6);
    }

    // --- validation ---

    #[test]
    fn perfect_validates() {
        validate(&perfect()).unwrap();
    }

    #[test]
    fn out_of_range_rejected() {
        let mut v = perfect();
        v.correctness = 1.5;
        assert!(matches!(validate(&v).unwrap_err(), ValuePlaneError::AxisOutOfRange { .. }));
        let mut v2 = perfect();
        v2.evidence = -0.1;
        assert!(matches!(validate(&v2).unwrap_err(), ValuePlaneError::AxisOutOfRange { .. }));
    }

    #[test]
    fn nan_rejected() {
        let mut v = perfect();
        v.cost = f32::NAN;
        assert!(matches!(validate(&v).unwrap_err(), ValuePlaneError::AxisOutOfRange { .. }));
    }

    // --- Profile-weighted aggregation ---

    #[test]
    fn fast_profile_weights_present() {
        assert!(ProfileWeights::for_profile("fast").is_some());
        assert!(ProfileWeights::for_profile("careful").is_some());
        assert!(ProfileWeights::for_profile("autonomous").is_some());
        assert!(ProfileWeights::for_profile("creative").is_some());
        assert!(ProfileWeights::for_profile("private").is_some());
        assert!(ProfileWeights::for_profile("ghost").is_none());
    }

    #[test]
    fn perfect_vector_aggregates_to_one() {
        for p in ["fast", "careful", "autonomous", "creative", "private"] {
            let w = ProfileWeights::for_profile(p).unwrap();
            let agg = w.aggregate(&perfect());
            assert!((agg - 1.0).abs() < 1e-6, "profile {p} got {agg}");
        }
    }

    #[test]
    fn zero_vector_aggregates_to_zero() {
        let zero = RewardVector::default();
        // default() = all zeros → risk/latency/cost contribute 1.0 due to inversion
        // → not all zeros. Build explicit all-zero contributions.
        let mut v = RewardVector::default();
        v.risk = 1.0; v.latency = 1.0; v.cost = 1.0;
        let w = ProfileWeights::for_profile("fast").unwrap();
        let agg = w.aggregate(&v);
        assert!(agg.abs() < 1e-6, "got {agg}");
    }

    #[test]
    fn zero_weights_aggregate_returns_zero() {
        let w = ProfileWeights {
            profile: "test".into(),
            weights: [0.0; 12],
        };
        assert_eq!(w.aggregate(&perfect()), 0.0);
    }

    // --- Intelligence Dial ---

    #[test]
    fn dial_fanouts_strictly_increasing() {
        let fanouts: Vec<u32> = [
            IntelligenceTier::Reflex, IntelligenceTier::Normal,
            IntelligenceTier::Deliberate, IntelligenceTier::Exhaustive,
            IntelligenceTier::Experimental,
        ].into_iter().map(|t| t.fanout()).collect();
        for w in fanouts.windows(2) {
            assert!(w[0] < w[1]);
        }
        assert_eq!(fanouts[0], 1);
        assert_eq!(fanouts[4], 256);
    }

    // --- Doctrines ---

    #[test]
    fn doctrine_prm_proposes_verbatim() {
        assert_eq!(
            DOCTRINE_PRM_PROPOSES,
            "PRM proposes value, CPU applies law, Oracle verifies high-stakes commitments"
        );
    }

    #[test]
    fn doctrine_thoughts_deserve_more_life_verbatim() {
        assert_eq!(
            DOCTRINE_THOUGHTS_DESERVE_MORE_LIFE,
            "Intelligence is knowing which thoughts deserve more life"
        );
    }

    // --- Serde ---

    #[test]
    fn reward_axis_serde_kebab() {
        assert_eq!(serde_json::to_string(&RewardAxis::SchemaValidity).unwrap(), "\"schema-validity\"");
        assert_eq!(serde_json::to_string(&RewardAxis::ConfidenceCalibration).unwrap(), "\"confidence-calibration\"");
    }

    #[test]
    fn reward_vector_serde_roundtrip() {
        let v = perfect();
        let j = serde_json::to_string(&v).unwrap();
        let back: RewardVector = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }

    #[test]
    fn intelligence_tier_serde_kebab() {
        assert_eq!(serde_json::to_string(&IntelligenceTier::Deliberate).unwrap(), "\"deliberate\"");
    }
}
