//! `sovereign-mode-default-policy` — per-bundle landing mode at cockpit boot.
//!
//! Operator standing rule: Private → Plan, Careful → DryRun,
//! Fast → Execute, Sovereign → Execute. The cockpit consults this at
//! boot and again at every bundle switch.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_profile_bundles::BundleName;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-bundle mapping.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BundleDefault {
    /// Bundle.
    pub bundle: BundleName,
    /// Landing mode.
    pub mode: ExecutionMode,
}

/// Policy envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModeDefaultPolicy {
    /// Schema version.
    pub schema_version: String,
    /// 4 bundle mappings.
    pub mappings: Vec<BundleDefault>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DefaultError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 4.
    #[error("default mapping count {0} != 4 canonical")]
    CountInvalid(usize),
    /// Missing.
    #[error("missing bundle mapping: {0:?}")]
    Missing(BundleName),
    /// Disallowed landing mode (Replay can only be entered explicitly).
    #[error("bundle {bundle:?} cannot land in Replay mode")]
    ReplayLandingForbidden {
        /// bundle.
        bundle: BundleName,
    },
}

const REQUIRED: [BundleName; 4] = [BundleName::Private, BundleName::Careful, BundleName::Fast, BundleName::Sovereign];

impl ModeDefaultPolicy {
    /// Canonical mapping.
    pub fn canonical() -> Self {
        let mappings = vec![
            BundleDefault { bundle: BundleName::Private,   mode: ExecutionMode::Plan },
            BundleDefault { bundle: BundleName::Careful,   mode: ExecutionMode::DryRun },
            BundleDefault { bundle: BundleName::Fast,      mode: ExecutionMode::Execute },
            BundleDefault { bundle: BundleName::Sovereign, mode: ExecutionMode::Execute },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            mappings,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DefaultError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DefaultError::SchemaMismatch);
        }
        if self.mappings.len() != 4 {
            return Err(DefaultError::CountInvalid(self.mappings.len()));
        }
        for b in REQUIRED {
            if !self.mappings.iter().any(|m| m.bundle == b) {
                return Err(DefaultError::Missing(b));
            }
        }
        for m in &self.mappings {
            if m.mode == ExecutionMode::Replay {
                return Err(DefaultError::ReplayLandingForbidden { bundle: m.bundle });
            }
        }
        Ok(())
    }

    /// Lookup landing mode for a bundle.
    pub fn landing_mode(&self, bundle: BundleName) -> Option<ExecutionMode> {
        self.mappings.iter().find(|m| m.bundle == bundle).map(|m| m.mode)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        ModeDefaultPolicy::canonical().validate().unwrap();
    }

    #[test]
    fn private_lands_in_plan() {
        let p = ModeDefaultPolicy::canonical();
        assert_eq!(p.landing_mode(BundleName::Private), Some(ExecutionMode::Plan));
    }

    #[test]
    fn careful_lands_in_dry_run() {
        let p = ModeDefaultPolicy::canonical();
        assert_eq!(p.landing_mode(BundleName::Careful), Some(ExecutionMode::DryRun));
    }

    #[test]
    fn fast_lands_in_execute() {
        let p = ModeDefaultPolicy::canonical();
        assert_eq!(p.landing_mode(BundleName::Fast), Some(ExecutionMode::Execute));
    }

    #[test]
    fn sovereign_lands_in_execute() {
        let p = ModeDefaultPolicy::canonical();
        assert_eq!(p.landing_mode(BundleName::Sovereign), Some(ExecutionMode::Execute));
    }

    #[test]
    fn replay_landing_forbidden() {
        let mut p = ModeDefaultPolicy::canonical();
        p.mappings[0].mode = ExecutionMode::Replay;
        match p.validate().unwrap_err() {
            DefaultError::ReplayLandingForbidden { bundle } => {
                assert_eq!(bundle, p.mappings[0].bundle);
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = ModeDefaultPolicy::canonical();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), DefaultError::SchemaMismatch));
    }

    #[test]
    fn count_invalid_caught() {
        let mut p = ModeDefaultPolicy::canonical();
        p.mappings.pop();
        assert!(matches!(p.validate().unwrap_err(), DefaultError::CountInvalid(3)));
    }

    #[test]
    fn missing_bundle_caught() {
        let mut p = ModeDefaultPolicy::canonical();
        // Replace Careful with duplicate Private.
        for m in p.mappings.iter_mut() {
            if m.bundle == BundleName::Careful { m.bundle = BundleName::Private; }
        }
        assert!(matches!(p.validate().unwrap_err(), DefaultError::Missing(BundleName::Careful)));
    }

    #[test]
    fn policy_serde_roundtrip() {
        let p = ModeDefaultPolicy::canonical();
        let j = serde_json::to_string(&p).unwrap();
        let back: ModeDefaultPolicy = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
