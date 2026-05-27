//! `sovereign-cockpit-state` — unified cockpit-side state envelope.
//!
//! Counterpart to `selfdef-state-snapshot` on the IPS side. Every
//! cockpit boot loads this snapshot, every commit writes it. Composes
//! the 6 cockpit-facing typed surfaces into one re-loadable JSON.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_cockpit_personalization::PersonalizationConfig;
use sovereign_dashboard_coverage::CoverageManifest;
use sovereign_dashboard_toggle::ToggleConfig;
use sovereign_mirror_publisher::MirrorManifest;
use sovereign_module_catalog::ModuleManifest;
use sovereign_trinity::TrinityManifest;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Canonical on-disk path.
pub const COCKPIT_STATE_PATH: &str = "/var/lib/sovereign-os/cockpit-state.json";

/// Unified envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CockpitState {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// ISO-8601 UTC capture timestamp.
    pub captured_at: String,
    /// 9-mirror endpoint manifest.
    pub mirror_manifest: MirrorManifest,
    /// 21-slot dashboard coverage manifest.
    pub coverage_manifest: CoverageManifest,
    /// Per-slot toggle config.
    pub toggle_config: ToggleConfig,
    /// Per-profile UX personalization.
    pub personalization: PersonalizationConfig,
    /// Trinity 3-role manifest.
    pub trinity_manifest: TrinityManifest,
    /// 10-module manifest.
    pub module_manifest: ModuleManifest,
    /// MS003 envelope signature.
    pub envelope_signature: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CockpitStateError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Captured_at empty.
    #[error("captured_at empty")]
    CapturedAtMissing,
    /// Envelope signature missing.
    #[error("envelope signature missing (MS003 signing required)")]
    EnvelopeUnsigned,
    /// Embedded sub-schema invalid.
    #[error("embedded {component} invalid: {reason}")]
    SubSchemaInvalid {
        /// Component name.
        component: &'static str,
        /// Inner error message.
        reason: String,
    },
}

impl CockpitState {
    /// Validate composite invariants.
    pub fn validate(&self) -> Result<(), CockpitStateError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CockpitStateError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.captured_at.is_empty() {
            return Err(CockpitStateError::CapturedAtMissing);
        }
        if self.envelope_signature.is_empty() {
            return Err(CockpitStateError::EnvelopeUnsigned);
        }
        self.mirror_manifest
            .validate()
            .map_err(|e| CockpitStateError::SubSchemaInvalid {
                component: "mirror_manifest",
                reason: e.to_string(),
            })?;
        self.coverage_manifest
            .validate()
            .map_err(|e| CockpitStateError::SubSchemaInvalid {
                component: "coverage_manifest",
                reason: e.to_string(),
            })?;
        self.toggle_config
            .validate()
            .map_err(|e| CockpitStateError::SubSchemaInvalid {
                component: "toggle_config",
                reason: e.to_string(),
            })?;
        self.personalization
            .validate()
            .map_err(|e| CockpitStateError::SubSchemaInvalid {
                component: "personalization",
                reason: e.to_string(),
            })?;
        self.trinity_manifest
            .validate()
            .map_err(|e| CockpitStateError::SubSchemaInvalid {
                component: "trinity_manifest",
                reason: e.to_string(),
            })?;
        self.module_manifest
            .validate()
            .map_err(|e| CockpitStateError::SubSchemaInvalid {
                component: "module_manifest",
                reason: e.to_string(),
            })?;
        Ok(())
    }

    /// Construct a canonical empty envelope ready for daemon population.
    pub fn empty_canonical() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            captured_at: "2026-05-19T00:00:00Z".into(),
            mirror_manifest: MirrorManifest::canonical(),
            coverage_manifest: CoverageManifest::canonical(),
            toggle_config: ToggleConfig::default(),
            personalization: PersonalizationConfig::default(),
            trinity_manifest: TrinityManifest::empty_canonical(),
            module_manifest: ModuleManifest::empty_canonical(),
            envelope_signature: String::new(),
        }
    }

    /// Canonical path constant.
    pub fn canonical_path() -> &'static str {
        COCKPIT_STATE_PATH
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ok_state() -> CockpitState {
        let mut s = CockpitState::empty_canonical();
        s.envelope_signature = "ms003-envelope".into();
        s
    }

    #[test]
    fn ok_state_validates() {
        ok_state().validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ok_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            CockpitStateError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn captured_at_empty_rejected() {
        let mut s = ok_state();
        s.captured_at = String::new();
        assert!(matches!(
            s.validate().unwrap_err(),
            CockpitStateError::CapturedAtMissing
        ));
    }

    #[test]
    fn unsigned_rejected() {
        let mut s = ok_state();
        s.envelope_signature = String::new();
        assert!(matches!(
            s.validate().unwrap_err(),
            CockpitStateError::EnvelopeUnsigned
        ));
    }

    #[test]
    fn bad_mirror_manifest_caught() {
        let mut s = ok_state();
        s.mirror_manifest.entries.pop();
        match s.validate().unwrap_err() {
            CockpitStateError::SubSchemaInvalid { component, .. } => {
                assert_eq!(component, "mirror_manifest");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn bad_coverage_manifest_caught() {
        let mut s = ok_state();
        s.coverage_manifest.entries.pop();
        match s.validate().unwrap_err() {
            CockpitStateError::SubSchemaInvalid { component, .. } => {
                assert_eq!(component, "coverage_manifest");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn bad_toggle_config_caught() {
        let mut s = ok_state();
        use sovereign_dashboard_toggle::SlotState;
        s.toggle_config
            .slots
            .insert("D-99".into(), SlotState::Disabled);
        match s.validate().unwrap_err() {
            CockpitStateError::SubSchemaInvalid { component, .. } => {
                assert_eq!(component, "toggle_config");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn bad_personalization_caught() {
        let mut s = ok_state();
        s.personalization.global.accent_hex = "not-hex".into();
        match s.validate().unwrap_err() {
            CockpitStateError::SubSchemaInvalid { component, .. } => {
                assert_eq!(component, "personalization");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn bad_trinity_manifest_caught() {
        let mut s = ok_state();
        s.trinity_manifest.genesis = "tampered".into();
        match s.validate().unwrap_err() {
            CockpitStateError::SubSchemaInvalid { component, .. } => {
                assert_eq!(component, "trinity_manifest");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn bad_module_manifest_caught() {
        let mut s = ok_state();
        s.module_manifest.key_line = "tampered".into();
        match s.validate().unwrap_err() {
            CockpitStateError::SubSchemaInvalid { component, .. } => {
                assert_eq!(component, "module_manifest");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn canonical_path_const() {
        assert_eq!(
            CockpitState::canonical_path(),
            "/var/lib/sovereign-os/cockpit-state.json"
        );
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = ok_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: CockpitState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
