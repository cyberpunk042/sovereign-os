//! `sovereign-choice-envelope` — M042 9-axis sovereignty boundary policy.
//!
//! Per M042 + R07096-R07105 + dump 12384-12395.
//!
//! Doctrine verbatim per R07105 dump 12395:
//!
//! > "That is sovereignty"
//!
//! 9 boundary axes — each one is operator-overridable:
//! 1. local-or-cloud
//! 2. fast-or-careful
//! 3. private-or-shared
//! 4. automatic-or-gated
//! 5. cheap-or-best
//! 6. sandbox-or-host
//! 7. scout-or-oracle
//! 8. spec-first-or-exploratory
//! 9. tdd-strict-or-prototype
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine verbatim per R07105 dump 12395.
pub const DOCTRINE_THAT_IS_SOVEREIGNTY: &str = "That is sovereignty";

/// 9 sovereignty boundary axes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum BoundaryAxis {
    /// 1. local-or-cloud (R07096).
    LocalOrCloud,
    /// 2. fast-or-careful (R07097).
    FastOrCareful,
    /// 3. private-or-shared (R07098).
    PrivateOrShared,
    /// 4. automatic-or-gated (R07099).
    AutomaticOrGated,
    /// 5. cheap-or-best (R07100).
    CheapOrBest,
    /// 6. sandbox-or-host (R07101).
    SandboxOrHost,
    /// 7. scout-or-oracle (R07102).
    ScoutOrOracle,
    /// 8. spec-first-or-exploratory (R07103).
    SpecFirstOrExploratory,
    /// 9. tdd-strict-or-prototype (R07104).
    TddStrictOrPrototype,
}

impl BoundaryAxis {
    /// Canonical 1..9.
    pub fn position(self) -> u8 {
        match self {
            BoundaryAxis::LocalOrCloud => 1,
            BoundaryAxis::FastOrCareful => 2,
            BoundaryAxis::PrivateOrShared => 3,
            BoundaryAxis::AutomaticOrGated => 4,
            BoundaryAxis::CheapOrBest => 5,
            BoundaryAxis::SandboxOrHost => 6,
            BoundaryAxis::ScoutOrOracle => 7,
            BoundaryAxis::SpecFirstOrExploratory => 8,
            BoundaryAxis::TddStrictOrPrototype => 9,
        }
    }
    /// Verbatim text per dump 12384-12392.
    pub fn text(self) -> &'static str {
        match self {
            BoundaryAxis::LocalOrCloud => "local or cloud",
            BoundaryAxis::FastOrCareful => "fast or careful",
            BoundaryAxis::PrivateOrShared => "private or shared",
            BoundaryAxis::AutomaticOrGated => "automatic or gated",
            BoundaryAxis::CheapOrBest => "cheap or best",
            BoundaryAxis::SandboxOrHost => "sandbox or host",
            BoundaryAxis::ScoutOrOracle => "scout or oracle",
            BoundaryAxis::SpecFirstOrExploratory => "spec-first or exploratory",
            BoundaryAxis::TddStrictOrPrototype => "TDD strict or prototype",
        }
    }
    /// All 9 axes in canonical order.
    pub fn all() -> [BoundaryAxis; 9] {
        [
            BoundaryAxis::LocalOrCloud,
            BoundaryAxis::FastOrCareful,
            BoundaryAxis::PrivateOrShared,
            BoundaryAxis::AutomaticOrGated,
            BoundaryAxis::CheapOrBest,
            BoundaryAxis::SandboxOrHost,
            BoundaryAxis::ScoutOrOracle,
            BoundaryAxis::SpecFirstOrExploratory,
            BoundaryAxis::TddStrictOrPrototype,
        ]
    }
}

/// One side of an axis (left or right of the "or").
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AxisSide {
    /// Left side (first option in the axis text).
    Left,
    /// Right side (second option).
    Right,
    /// Both — operator allows runtime to pick per task.
    Both,
}

/// Per-axis choice record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AxisChoice {
    /// Axis.
    pub axis: BoundaryAxis,
    /// Operator's chosen side.
    pub side: AxisSide,
    /// Reason text (operator-readable; may be empty).
    pub reason: String,
}

/// 9-choice envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChoiceEnvelope {
    /// Schema version.
    pub schema_version: String,
    /// Doctrine surface — MUST equal [`DOCTRINE_THAT_IS_SOVEREIGNTY`].
    pub doctrine: String,
    /// 9 axis choices (MUST be exactly 9).
    pub choices: Vec<AxisChoice>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ChoiceError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Doctrine tampered.
    #[error("doctrine tampered")]
    DoctrineTampered,
    /// Count != 9.
    #[error("choice count {0} != 9 canonical axes")]
    CountInvalid(usize),
    /// Required axis missing.
    #[error("required axis missing: {0:?}")]
    AxisMissing(BoundaryAxis),
    /// Duplicate axis.
    #[error("duplicate axis: {0:?}")]
    DuplicateAxis(BoundaryAxis),
}

impl ChoiceEnvelope {
    /// Canonical empty envelope — all 9 axes set to Both (runtime decides).
    pub fn empty_canonical() -> Self {
        let choices = BoundaryAxis::all()
            .into_iter()
            .map(|a| AxisChoice {
                axis: a,
                side: AxisSide::Both,
                reason: String::new(),
            })
            .collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            doctrine: DOCTRINE_THAT_IS_SOVEREIGNTY.into(),
            choices,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), ChoiceError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ChoiceError::SchemaMismatch);
        }
        if self.doctrine != DOCTRINE_THAT_IS_SOVEREIGNTY {
            return Err(ChoiceError::DoctrineTampered);
        }
        if self.choices.len() != 9 {
            return Err(ChoiceError::CountInvalid(self.choices.len()));
        }
        for a in BoundaryAxis::all() {
            if !self.choices.iter().any(|c| c.axis == a) {
                return Err(ChoiceError::AxisMissing(a));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<BoundaryAxis> = HashSet::new();
        for c in &self.choices {
            if !seen.insert(c.axis) {
                return Err(ChoiceError::DuplicateAxis(c.axis));
            }
        }
        Ok(())
    }

    /// Get chosen side for an axis.
    pub fn side_of(&self, axis: BoundaryAxis) -> Option<AxisSide> {
        self.choices.iter().find(|c| c.axis == axis).map(|c| c.side)
    }

    /// Apply a side choice with an operator-supplied reason.
    pub fn set_side(&mut self, axis: BoundaryAxis, side: AxisSide, reason: &str) {
        if let Some(c) = self.choices.iter_mut().find(|c| c.axis == axis) {
            c.side = side;
            c.reason = reason.into();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nine_axes_positioned_1_to_9() {
        for (a, p) in [
            (BoundaryAxis::LocalOrCloud, 1),
            (BoundaryAxis::FastOrCareful, 2),
            (BoundaryAxis::PrivateOrShared, 3),
            (BoundaryAxis::AutomaticOrGated, 4),
            (BoundaryAxis::CheapOrBest, 5),
            (BoundaryAxis::SandboxOrHost, 6),
            (BoundaryAxis::ScoutOrOracle, 7),
            (BoundaryAxis::SpecFirstOrExploratory, 8),
            (BoundaryAxis::TddStrictOrPrototype, 9),
        ] {
            assert_eq!(a.position(), p);
        }
    }

    #[test]
    fn nine_axes_text_verbatim() {
        assert_eq!(BoundaryAxis::LocalOrCloud.text(), "local or cloud");
        assert_eq!(BoundaryAxis::FastOrCareful.text(), "fast or careful");
        assert_eq!(
            BoundaryAxis::TddStrictOrPrototype.text(),
            "TDD strict or prototype"
        );
    }

    #[test]
    fn all_returns_9_in_canonical_order() {
        let a = BoundaryAxis::all();
        assert_eq!(a.len(), 9);
        for (i, axis) in a.iter().enumerate() {
            assert_eq!(axis.position(), (i + 1) as u8);
        }
    }

    #[test]
    fn empty_canonical_validates() {
        ChoiceEnvelope::empty_canonical().validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut e = ChoiceEnvelope::empty_canonical();
        e.schema_version = "9.9.9".into();
        assert!(matches!(
            e.validate().unwrap_err(),
            ChoiceError::SchemaMismatch
        ));
    }

    #[test]
    fn doctrine_tamper_caught() {
        let mut e = ChoiceEnvelope::empty_canonical();
        e.doctrine = "wrong".into();
        assert!(matches!(
            e.validate().unwrap_err(),
            ChoiceError::DoctrineTampered
        ));
    }

    #[test]
    fn count_invalid_caught() {
        let mut e = ChoiceEnvelope::empty_canonical();
        e.choices.pop();
        assert!(matches!(
            e.validate().unwrap_err(),
            ChoiceError::CountInvalid(8)
        ));
    }

    #[test]
    fn side_of_lookup() {
        let mut e = ChoiceEnvelope::empty_canonical();
        e.set_side(
            BoundaryAxis::PrivateOrShared,
            AxisSide::Left,
            "operator data is private",
        );
        assert_eq!(
            e.side_of(BoundaryAxis::PrivateOrShared),
            Some(AxisSide::Left)
        );
        assert_eq!(e.side_of(BoundaryAxis::CheapOrBest), Some(AxisSide::Both));
    }

    #[test]
    fn doctrine_verbatim() {
        assert_eq!(DOCTRINE_THAT_IS_SOVEREIGNTY, "That is sovereignty");
    }

    #[test]
    fn axis_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&BoundaryAxis::LocalOrCloud).unwrap(),
            "\"local-or-cloud\""
        );
        assert_eq!(
            serde_json::to_string(&BoundaryAxis::SpecFirstOrExploratory).unwrap(),
            "\"spec-first-or-exploratory\""
        );
        assert_eq!(
            serde_json::to_string(&BoundaryAxis::TddStrictOrPrototype).unwrap(),
            "\"tdd-strict-or-prototype\""
        );
    }

    #[test]
    fn side_serde_kebab() {
        assert_eq!(serde_json::to_string(&AxisSide::Left).unwrap(), "\"left\"");
        assert_eq!(serde_json::to_string(&AxisSide::Both).unwrap(), "\"both\"");
    }

    #[test]
    fn envelope_serde_roundtrip() {
        let mut e = ChoiceEnvelope::empty_canonical();
        e.set_side(
            BoundaryAxis::ScoutOrOracle,
            AxisSide::Right,
            "operator wants Blackwell",
        );
        let j = serde_json::to_string(&e).unwrap();
        let back: ChoiceEnvelope = serde_json::from_str(&j).unwrap();
        assert_eq!(e, back);
    }
}
