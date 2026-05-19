//! `sovereign-eval-suite-catalog` — 7 canonical eval suites.
//!
//! Each suite declares dimensions weighted, the minimum mode it can run
//! in, and an expected runtime budget. Composes the eval-plane's
//! 8-dimension surface into operator-runnable bundles.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_eval_plane::EvalDimension;
use sovereign_execution_mode_registry::ExecutionMode;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 7 canonical suites.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SuiteId {
    /// Smoke — fast sanity (<10s).
    Smoke,
    /// Regression — full functional coverage.
    Regression,
    /// Safety — red-team aligned scenarios.
    Safety,
    /// Drift — model drift detection.
    Drift,
    /// Golden path — happy-path UX flows.
    GoldenPath,
    /// Red team — adversarial inputs.
    RedTeam,
    /// Latency budget — tail-latency checks.
    LatencyBudget,
}

/// Per-suite record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SuiteRecord {
    /// Id.
    pub id: SuiteId,
    /// Dimensions evaluated (non-empty).
    pub dimensions: Vec<EvalDimension>,
    /// Minimum mode for dispatch.
    pub allowed_modes: Vec<ExecutionMode>,
    /// Expected runtime budget in seconds.
    pub expected_runtime_seconds: u32,
    /// Operator-readable description.
    pub description: String,
}

/// Catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EvalSuiteCatalog {
    /// Schema version.
    pub schema_version: String,
    /// 7 suites.
    pub suites: Vec<SuiteRecord>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SuiteError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 7.
    #[error("suite count {0} != 7 canonical")]
    CountInvalid(usize),
    /// Missing.
    #[error("missing suite: {0:?}")]
    Missing(SuiteId),
    /// dimensions empty.
    #[error("suite {0:?} declares no dimensions")]
    NoDimensions(SuiteId),
    /// allowed_modes empty.
    #[error("suite {0:?} declares no allowed_modes")]
    NoModes(SuiteId),
    /// Runtime budget 0.
    #[error("suite {0:?} expected_runtime_seconds 0")]
    ZeroRuntime(SuiteId),
}

const REQUIRED: [SuiteId; 7] = [
    SuiteId::Smoke, SuiteId::Regression, SuiteId::Safety, SuiteId::Drift,
    SuiteId::GoldenPath, SuiteId::RedTeam, SuiteId::LatencyBudget,
];

impl EvalSuiteCatalog {
    /// Canonical catalog.
    pub fn canonical() -> Self {
        use EvalDimension::*;
        use ExecutionMode::*;
        let suites = vec![
            SuiteRecord {
                id: SuiteId::Smoke,
                dimensions: vec![Correctness, SchemaValidity],
                allowed_modes: vec![Plan, DryRun, Sandbox, Execute, Debug],
                expected_runtime_seconds: 10,
                description: "Fast sanity — 5 prompts, 2 dimensions.".into(),
            },
            SuiteRecord {
                id: SuiteId::Regression,
                dimensions: vec![Correctness, Evidence, TestPass, SchemaValidity],
                allowed_modes: vec![DryRun, Sandbox, Execute, Debug],
                expected_runtime_seconds: 300,
                description: "Full functional coverage.".into(),
            },
            SuiteRecord {
                id: SuiteId::Safety,
                dimensions: vec![Correctness, Risk],
                allowed_modes: vec![Sandbox, Execute, Debug],
                expected_runtime_seconds: 120,
                description: "Red-team aligned scenarios.".into(),
            },
            SuiteRecord {
                id: SuiteId::Drift,
                dimensions: vec![Correctness, Evidence],
                allowed_modes: vec![DryRun, Execute, Debug],
                expected_runtime_seconds: 600,
                description: "Drift over time tracking.".into(),
            },
            SuiteRecord {
                id: SuiteId::GoldenPath,
                dimensions: vec![Correctness, SchemaValidity, Latency],
                allowed_modes: vec![DryRun, Execute, Debug],
                expected_runtime_seconds: 60,
                description: "Happy-path UX flows.".into(),
            },
            SuiteRecord {
                id: SuiteId::RedTeam,
                dimensions: vec![Risk, Correctness],
                allowed_modes: vec![Sandbox, Execute, Debug],
                expected_runtime_seconds: 240,
                description: "Adversarial inputs.".into(),
            },
            SuiteRecord {
                id: SuiteId::LatencyBudget,
                dimensions: vec![Latency, Cost],
                allowed_modes: vec![DryRun, Execute, Debug],
                expected_runtime_seconds: 30,
                description: "Tail-latency budget checks.".into(),
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            suites,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SuiteError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SuiteError::SchemaMismatch);
        }
        if self.suites.len() != 7 {
            return Err(SuiteError::CountInvalid(self.suites.len()));
        }
        for s in REQUIRED {
            if !self.suites.iter().any(|r| r.id == s) {
                return Err(SuiteError::Missing(s));
            }
        }
        for r in &self.suites {
            if r.dimensions.is_empty() { return Err(SuiteError::NoDimensions(r.id)); }
            if r.allowed_modes.is_empty() { return Err(SuiteError::NoModes(r.id)); }
            if r.expected_runtime_seconds == 0 { return Err(SuiteError::ZeroRuntime(r.id)); }
        }
        Ok(())
    }

    /// Lookup.
    pub fn get(&self, id: SuiteId) -> Option<&SuiteRecord> {
        self.suites.iter().find(|r| r.id == id)
    }

    /// Eligible suites in given mode.
    pub fn eligible_in(&self, mode: ExecutionMode) -> Vec<&SuiteRecord> {
        self.suites.iter().filter(|r| r.allowed_modes.contains(&mode)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        EvalSuiteCatalog::canonical().validate().unwrap();
    }

    #[test]
    fn seven_suites_present() {
        let c = EvalSuiteCatalog::canonical();
        for s in REQUIRED {
            assert!(c.get(s).is_some(), "missing {s:?}");
        }
    }

    #[test]
    fn smoke_is_fast() {
        let c = EvalSuiteCatalog::canonical();
        assert!(c.get(SuiteId::Smoke).unwrap().expected_runtime_seconds <= 10);
    }

    #[test]
    fn safety_requires_sandbox_or_higher() {
        let c = EvalSuiteCatalog::canonical();
        let modes = &c.get(SuiteId::Safety).unwrap().allowed_modes;
        assert!(!modes.contains(&ExecutionMode::Plan));
        assert!(modes.contains(&ExecutionMode::Sandbox));
    }

    #[test]
    fn eligible_in_plan_returns_smoke_only() {
        let c = EvalSuiteCatalog::canonical();
        let v = c.eligible_in(ExecutionMode::Plan);
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].id, SuiteId::Smoke);
    }

    #[test]
    fn eligible_in_execute_returns_all_seven() {
        let c = EvalSuiteCatalog::canonical();
        let v = c.eligible_in(ExecutionMode::Execute);
        assert_eq!(v.len(), 7);
    }

    #[test]
    fn no_dimensions_caught() {
        let mut c = EvalSuiteCatalog::canonical();
        c.suites[0].dimensions.clear();
        assert!(matches!(c.validate().unwrap_err(), SuiteError::NoDimensions(_)));
    }

    #[test]
    fn no_modes_caught() {
        let mut c = EvalSuiteCatalog::canonical();
        c.suites[0].allowed_modes.clear();
        assert!(matches!(c.validate().unwrap_err(), SuiteError::NoModes(_)));
    }

    #[test]
    fn zero_runtime_caught() {
        let mut c = EvalSuiteCatalog::canonical();
        c.suites[0].expected_runtime_seconds = 0;
        assert!(matches!(c.validate().unwrap_err(), SuiteError::ZeroRuntime(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = EvalSuiteCatalog::canonical();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), SuiteError::SchemaMismatch));
    }

    #[test]
    fn count_invalid_caught() {
        let mut c = EvalSuiteCatalog::canonical();
        c.suites.pop();
        assert!(matches!(c.validate().unwrap_err(), SuiteError::CountInvalid(6)));
    }

    #[test]
    fn suite_serde_kebab() {
        assert_eq!(serde_json::to_string(&SuiteId::Smoke).unwrap(), "\"smoke\"");
        assert_eq!(serde_json::to_string(&SuiteId::GoldenPath).unwrap(), "\"golden-path\"");
        assert_eq!(serde_json::to_string(&SuiteId::RedTeam).unwrap(), "\"red-team\"");
        assert_eq!(serde_json::to_string(&SuiteId::LatencyBudget).unwrap(), "\"latency-budget\"");
    }

    #[test]
    fn catalog_serde_roundtrip() {
        let c = EvalSuiteCatalog::canonical();
        let j = serde_json::to_string(&c).unwrap();
        let back: EvalSuiteCatalog = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
