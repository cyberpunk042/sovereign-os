//! `sovereign-six-pillars` — M042 6 foundational pillars catalog.
//!
//! Per M042 + R06971-R06986 + dump 12110-12126.
//!
//! Doctrine verbatim per R06979 dump 12121:
//!
//! > "Breakthrough is not one model"
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine verbatim per R06979.
pub const DOCTRINE_NOT_ONE_MODEL: &str = "Breakthrough is not one model";

/// 6 canonical pillars per R06972-R06977.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Pillar {
    /// 1. MAP / map-before-act.
    Map,
    /// 2. Spec + workflow orchestration.
    SpecWorkflow,
    /// 3. Agent harness engineering.
    AgentHarness,
    /// 4. Routing + cost-aware model selection.
    Routing,
    /// 5. Sandboxes + secrets isolation.
    SandboxesSecrets,
    /// 6. Model compression + hardware-aware model lab.
    ModelLab,
}

impl Pillar {
    /// Canonical 1..6 position.
    pub fn position(self) -> u8 {
        match self {
            Pillar::Map => 1,
            Pillar::SpecWorkflow => 2,
            Pillar::AgentHarness => 3,
            Pillar::Routing => 4,
            Pillar::SandboxesSecrets => 5,
            Pillar::ModelLab => 6,
        }
    }
    /// Verbatim short description per dump 12111-12116.
    pub fn description(self) -> &'static str {
        match self {
            Pillar::Map => "MAP / map-before-act",
            Pillar::SpecWorkflow => "Spec + workflow orchestration",
            Pillar::AgentHarness => "Agent harness engineering",
            Pillar::Routing => "Routing + cost-aware model selection",
            Pillar::SandboxesSecrets => "Sandboxes + secrets isolation",
            Pillar::ModelLab => "Model compression + hardware-aware model lab",
        }
    }
    /// All 6 pillars in canonical order.
    pub fn all() -> [Pillar; 6] {
        [
            Pillar::Map,
            Pillar::SpecWorkflow,
            Pillar::AgentHarness,
            Pillar::Routing,
            Pillar::SandboxesSecrets,
            Pillar::ModelLab,
        ]
    }
}

/// 7 verbatim "Breakthrough is..." statements per R06980-R06986.
pub const BREAKTHROUGH_STATEMENTS: [&str; 7] = [
    "Breakthrough is the harness",
    "Breakthrough is the runtime",
    "Breakthrough is the workflow",
    "Breakthrough is the router",
    "Breakthrough is the memory",
    "Breakthrough is the evals",
    "Breakthrough is the hardware-aware execution substrate",
];

/// Per-pillar entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PillarEntry {
    /// Pillar.
    pub pillar: Pillar,
    /// Position 1..6.
    pub position: u8,
    /// Description (must match canonical).
    pub description: String,
}

/// 6-pillar catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PillarsCatalog {
    /// Schema version.
    pub schema_version: String,
    /// Doctrine surface — MUST equal [`DOCTRINE_NOT_ONE_MODEL`].
    pub doctrine: String,
    /// 6 entries (exactly 6).
    pub pillars: Vec<PillarEntry>,
    /// 7 breakthrough statements verbatim.
    pub breakthrough_statements: Vec<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PillarError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Doctrine tampered.
    #[error("doctrine tampered")]
    DoctrineTampered,
    /// Pillar count != 6.
    #[error("pillar count {0} != 6")]
    CountInvalid(usize),
    /// Required pillar missing.
    #[error("required pillar missing: {0:?}")]
    PillarMissing(Pillar),
    /// Duplicate pillar.
    #[error("duplicate pillar: {0:?}")]
    DuplicatePillar(Pillar),
    /// Description mismatch.
    #[error("description mismatch for {pillar:?}")]
    DescriptionMismatch {
        /// Pillar.
        pillar: Pillar,
    },
    /// Position mismatch with Pillar::position().
    #[error("position mismatch for {pillar:?}: declared {declared}, canonical {canonical}")]
    PositionMismatch {
        /// Pillar.
        pillar: Pillar,
        /// Declared.
        declared: u8,
        /// Canonical.
        canonical: u8,
    },
    /// Breakthrough statements count != 7.
    #[error("breakthrough statements count {0} != 7")]
    BreakthroughCountInvalid(usize),
    /// One breakthrough statement tampered.
    #[error("breakthrough statement tampered at index {0}")]
    BreakthroughTampered(usize),
}

impl PillarsCatalog {
    /// Canonical catalog.
    pub fn canonical() -> Self {
        let pillars = Pillar::all()
            .into_iter()
            .map(|p| PillarEntry {
                pillar: p,
                position: p.position(),
                description: p.description().into(),
            })
            .collect();
        let breakthrough_statements = BREAKTHROUGH_STATEMENTS
            .iter()
            .map(|s| s.to_string())
            .collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            doctrine: DOCTRINE_NOT_ONE_MODEL.into(),
            pillars,
            breakthrough_statements,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PillarError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PillarError::SchemaMismatch);
        }
        if self.doctrine != DOCTRINE_NOT_ONE_MODEL {
            return Err(PillarError::DoctrineTampered);
        }
        if self.pillars.len() != 6 {
            return Err(PillarError::CountInvalid(self.pillars.len()));
        }
        for p in Pillar::all() {
            if !self.pillars.iter().any(|e| e.pillar == p) {
                return Err(PillarError::PillarMissing(p));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<Pillar> = HashSet::new();
        for e in &self.pillars {
            if !seen.insert(e.pillar) {
                return Err(PillarError::DuplicatePillar(e.pillar));
            }
            if e.position != e.pillar.position() {
                return Err(PillarError::PositionMismatch {
                    pillar: e.pillar,
                    declared: e.position,
                    canonical: e.pillar.position(),
                });
            }
            if e.description != e.pillar.description() {
                return Err(PillarError::DescriptionMismatch { pillar: e.pillar });
            }
        }
        if self.breakthrough_statements.len() != 7 {
            return Err(PillarError::BreakthroughCountInvalid(
                self.breakthrough_statements.len(),
            ));
        }
        for (i, s) in self.breakthrough_statements.iter().enumerate() {
            if s != BREAKTHROUGH_STATEMENTS[i] {
                return Err(PillarError::BreakthroughTampered(i));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn six_pillars_positioned_1_to_6() {
        for (p, n) in [
            (Pillar::Map, 1),
            (Pillar::SpecWorkflow, 2),
            (Pillar::AgentHarness, 3),
            (Pillar::Routing, 4),
            (Pillar::SandboxesSecrets, 5),
            (Pillar::ModelLab, 6),
        ] {
            assert_eq!(p.position(), n);
        }
    }

    #[test]
    fn descriptions_verbatim() {
        assert_eq!(Pillar::Map.description(), "MAP / map-before-act");
        assert_eq!(
            Pillar::SpecWorkflow.description(),
            "Spec + workflow orchestration"
        );
        assert_eq!(
            Pillar::ModelLab.description(),
            "Model compression + hardware-aware model lab"
        );
    }

    #[test]
    fn seven_breakthrough_statements_verbatim() {
        assert_eq!(BREAKTHROUGH_STATEMENTS.len(), 7);
        assert_eq!(BREAKTHROUGH_STATEMENTS[0], "Breakthrough is the harness");
        assert_eq!(
            BREAKTHROUGH_STATEMENTS[6],
            "Breakthrough is the hardware-aware execution substrate"
        );
    }

    #[test]
    fn canonical_validates() {
        PillarsCatalog::canonical().validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = PillarsCatalog::canonical();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            PillarError::SchemaMismatch
        ));
    }

    #[test]
    fn doctrine_tamper_caught() {
        let mut c = PillarsCatalog::canonical();
        c.doctrine = "wrong".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            PillarError::DoctrineTampered
        ));
    }

    #[test]
    fn description_tamper_caught() {
        let mut c = PillarsCatalog::canonical();
        c.pillars[0].description = "wrong".into();
        match c.validate().unwrap_err() {
            PillarError::DescriptionMismatch { pillar } => assert_eq!(pillar, Pillar::Map),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn position_tamper_caught() {
        let mut c = PillarsCatalog::canonical();
        c.pillars[0].position = 99;
        match c.validate().unwrap_err() {
            PillarError::PositionMismatch {
                pillar,
                declared,
                canonical,
            } => {
                assert_eq!(pillar, Pillar::Map);
                assert_eq!(declared, 99);
                assert_eq!(canonical, 1);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn breakthrough_tamper_caught() {
        let mut c = PillarsCatalog::canonical();
        c.breakthrough_statements[3] = "tampered".into();
        match c.validate().unwrap_err() {
            PillarError::BreakthroughTampered(i) => assert_eq!(i, 3),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn pillar_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Pillar::SpecWorkflow).unwrap(),
            "\"spec-workflow\""
        );
        assert_eq!(
            serde_json::to_string(&Pillar::SandboxesSecrets).unwrap(),
            "\"sandboxes-secrets\""
        );
        assert_eq!(
            serde_json::to_string(&Pillar::ModelLab).unwrap(),
            "\"model-lab\""
        );
    }

    #[test]
    fn catalog_serde_roundtrip() {
        let c = PillarsCatalog::canonical();
        let j = serde_json::to_string(&c).unwrap();
        let back: PillarsCatalog = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
