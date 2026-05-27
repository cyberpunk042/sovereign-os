//! `sovereign-eval-plane` — M048 Module 7 Eval/Value Plane.
//!
//! Per M048 + E0464 + M00809 + dump 14682-14702. 10-dimension scoring +
//! 8-profile weighting; every workflow run produces a score envelope
//! that feeds M046 LoRA promotion gate (>= 80) + M027 value plane.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 10 eval dimensions per dump 14682.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EvalDimension {
    /// 1. Correctness vs ground truth.
    Correctness,
    /// 2. Evidence support (sources cited).
    Evidence,
    /// 3. Tests passed.
    TestPass,
    /// 4. Schema validity (typed output passes contract).
    SchemaValidity,
    /// 5. Risk (inverted: lower-is-better).
    Risk,
    /// 6. Cost (inverted: lower-is-better).
    Cost,
    /// 7. Latency (inverted: lower-is-better).
    Latency,
    /// 8. Human burden (inverted: lower-is-better).
    HumanBurden,
    /// 9. Reversibility (rollback path easy).
    Reversibility,
    /// 10. Learning value (signal density for memory/LoRA).
    LearningValue,
}

impl EvalDimension {
    /// Canonical 1..10.
    pub fn position(self) -> u8 {
        match self {
            EvalDimension::Correctness => 1,
            EvalDimension::Evidence => 2,
            EvalDimension::TestPass => 3,
            EvalDimension::SchemaValidity => 4,
            EvalDimension::Risk => 5,
            EvalDimension::Cost => 6,
            EvalDimension::Latency => 7,
            EvalDimension::HumanBurden => 8,
            EvalDimension::Reversibility => 9,
            EvalDimension::LearningValue => 10,
        }
    }
    /// Whether dimension is inverted (lower-is-better).
    pub fn inverted(self) -> bool {
        matches!(
            self,
            EvalDimension::Risk
                | EvalDimension::Cost
                | EvalDimension::Latency
                | EvalDimension::HumanBurden
        )
    }
}

/// 8 eval profiles per dump 14688-14702.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EvalProfile {
    /// fast (latency over correctness).
    Fast,
    /// careful (correctness over latency).
    Careful,
    /// offline.
    Offline,
    /// research.
    Research,
    /// autonomous.
    Autonomous,
    /// production.
    Production,
    /// experimental.
    Experimental,
    /// communication-peace.
    CommunicationPeace,
}

/// 10-dimension score vector (each 0..=1.0).
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct ScoreVector {
    /// Correctness.
    pub correctness: f32,
    /// Evidence.
    pub evidence: f32,
    /// Test pass.
    pub test_pass: f32,
    /// Schema validity.
    pub schema_validity: f32,
    /// Risk (lower better).
    pub risk: f32,
    /// Cost (lower better).
    pub cost: f32,
    /// Latency (lower better).
    pub latency: f32,
    /// Human burden (lower better).
    pub human_burden: f32,
    /// Reversibility.
    pub reversibility: f32,
    /// Learning value.
    pub learning_value: f32,
}

impl ScoreVector {
    /// Contribution at axis (applies inversion for lower-is-better axes).
    pub fn contribution(&self, dim: EvalDimension) -> f32 {
        let v = match dim {
            EvalDimension::Correctness => self.correctness,
            EvalDimension::Evidence => self.evidence,
            EvalDimension::TestPass => self.test_pass,
            EvalDimension::SchemaValidity => self.schema_validity,
            EvalDimension::Risk => self.risk,
            EvalDimension::Cost => self.cost,
            EvalDimension::Latency => self.latency,
            EvalDimension::HumanBurden => self.human_burden,
            EvalDimension::Reversibility => self.reversibility,
            EvalDimension::LearningValue => self.learning_value,
        };
        if dim.inverted() { 1.0 - v } else { v }
    }
}

/// Profile-weighted aggregation.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ProfileWeights {
    /// Profile.
    pub profile: EvalProfile,
    /// 10 weights in canonical dim order.
    pub weights: [f32; 10],
}

impl ProfileWeights {
    /// Aggregate a score vector into a scalar 0..1.
    pub fn aggregate(&self, v: &ScoreVector) -> f32 {
        let dims = [
            EvalDimension::Correctness,
            EvalDimension::Evidence,
            EvalDimension::TestPass,
            EvalDimension::SchemaValidity,
            EvalDimension::Risk,
            EvalDimension::Cost,
            EvalDimension::Latency,
            EvalDimension::HumanBurden,
            EvalDimension::Reversibility,
            EvalDimension::LearningValue,
        ];
        let total_w: f32 = self.weights.iter().sum();
        if total_w <= 0.0 {
            return 0.0;
        }
        let mut acc = 0.0;
        for (i, dim) in dims.iter().enumerate() {
            acc += self.weights[i] * v.contribution(*dim);
        }
        acc / total_w
    }
}

/// Errors.
#[derive(Debug, Error)]
pub enum EvalError {
    /// Out of range.
    #[error("axis {dim:?} value {value} outside [0.0, 1.0]")]
    ValueOutOfRange {
        /// Dim.
        dim: EvalDimension,
        /// Value.
        value: f32,
    },
}

/// Validate a score vector — every axis in [0.0, 1.0] + finite.
pub fn validate(v: &ScoreVector) -> Result<(), EvalError> {
    let axes = [
        (EvalDimension::Correctness, v.correctness),
        (EvalDimension::Evidence, v.evidence),
        (EvalDimension::TestPass, v.test_pass),
        (EvalDimension::SchemaValidity, v.schema_validity),
        (EvalDimension::Risk, v.risk),
        (EvalDimension::Cost, v.cost),
        (EvalDimension::Latency, v.latency),
        (EvalDimension::HumanBurden, v.human_burden),
        (EvalDimension::Reversibility, v.reversibility),
        (EvalDimension::LearningValue, v.learning_value),
    ];
    for (dim, value) in axes {
        if !value.is_finite() || !(0.0..=1.0).contains(&value) {
            return Err(EvalError::ValueOutOfRange { dim, value });
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn perfect() -> ScoreVector {
        ScoreVector {
            correctness: 1.0,
            evidence: 1.0,
            test_pass: 1.0,
            schema_validity: 1.0,
            risk: 0.0,
            cost: 0.0,
            latency: 0.0,
            human_burden: 0.0,
            reversibility: 1.0,
            learning_value: 1.0,
        }
    }

    #[test]
    fn ten_dimensions_positioned_1_to_10() {
        for (d, p) in [
            (EvalDimension::Correctness, 1),
            (EvalDimension::Evidence, 2),
            (EvalDimension::TestPass, 3),
            (EvalDimension::SchemaValidity, 4),
            (EvalDimension::Risk, 5),
            (EvalDimension::Cost, 6),
            (EvalDimension::Latency, 7),
            (EvalDimension::HumanBurden, 8),
            (EvalDimension::Reversibility, 9),
            (EvalDimension::LearningValue, 10),
        ] {
            assert_eq!(d.position(), p);
        }
    }

    #[test]
    fn risk_cost_latency_human_burden_inverted() {
        for d in [
            EvalDimension::Risk,
            EvalDimension::Cost,
            EvalDimension::Latency,
            EvalDimension::HumanBurden,
        ] {
            assert!(d.inverted(), "{d:?} should be inverted");
        }
        for d in [
            EvalDimension::Correctness,
            EvalDimension::Evidence,
            EvalDimension::TestPass,
            EvalDimension::SchemaValidity,
            EvalDimension::Reversibility,
            EvalDimension::LearningValue,
        ] {
            assert!(!d.inverted(), "{d:?} should not be inverted");
        }
    }

    #[test]
    fn perfect_contribution_all_one() {
        let v = perfect();
        for d in [
            EvalDimension::Correctness,
            EvalDimension::Risk,
            EvalDimension::Cost,
            EvalDimension::HumanBurden,
            EvalDimension::Reversibility,
        ] {
            assert!((v.contribution(d) - 1.0).abs() < 1e-6);
        }
    }

    #[test]
    fn perfect_validates() {
        validate(&perfect()).unwrap();
    }

    #[test]
    fn out_of_range_rejected() {
        let mut v = perfect();
        v.correctness = 1.5;
        assert!(matches!(
            validate(&v).unwrap_err(),
            EvalError::ValueOutOfRange { .. }
        ));
    }

    #[test]
    fn perfect_aggregates_to_one_under_equal_weights() {
        let w = ProfileWeights {
            profile: EvalProfile::Careful,
            weights: [1.0; 10],
        };
        assert!((w.aggregate(&perfect()) - 1.0).abs() < 1e-6);
    }

    #[test]
    fn zero_weights_aggregate_to_zero() {
        let w = ProfileWeights {
            profile: EvalProfile::Fast,
            weights: [0.0; 10],
        };
        assert_eq!(w.aggregate(&perfect()), 0.0);
    }

    #[test]
    fn eight_profiles_enumerated() {
        let all = [
            EvalProfile::Fast,
            EvalProfile::Careful,
            EvalProfile::Offline,
            EvalProfile::Research,
            EvalProfile::Autonomous,
            EvalProfile::Production,
            EvalProfile::Experimental,
            EvalProfile::CommunicationPeace,
        ];
        assert_eq!(all.len(), 8);
    }

    #[test]
    fn eval_dimension_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&EvalDimension::SchemaValidity).unwrap(),
            "\"schema-validity\""
        );
        assert_eq!(
            serde_json::to_string(&EvalDimension::LearningValue).unwrap(),
            "\"learning-value\""
        );
        assert_eq!(
            serde_json::to_string(&EvalDimension::HumanBurden).unwrap(),
            "\"human-burden\""
        );
    }

    #[test]
    fn eval_profile_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&EvalProfile::CommunicationPeace).unwrap(),
            "\"communication-peace\""
        );
        assert_eq!(
            serde_json::to_string(&EvalProfile::Production).unwrap(),
            "\"production\""
        );
    }

    #[test]
    fn score_vector_serde_roundtrip() {
        let v = perfect();
        let j = serde_json::to_string(&v).unwrap();
        let back: ScoreVector = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }
}
