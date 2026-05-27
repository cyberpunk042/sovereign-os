//! `sovereign-inheritance-contracts` — M042 Symphony 6-contract schema.
//!
//! Per M042 + M00705 + F03509-F03515 + dump 12194-12201:
//!
//! > "Workflow belongs in version-controlled repo artifacts" (F03509)
//!
//! Six canonical contracts inherited by every sovereign-os deployment:
//!
//! 1. **SPEC.md** — system thesis + decisions (F03510)
//! 2. **WORKFLOW.md** — operator workflow + lifecycle (F03511)
//! 3. **PROFILES.yaml** — user-selectable operating modes (F03512)
//! 4. **EVALS.yaml** — trace/tool/task/quality/cost/risk evals (F03513)
//! 5. **POLICY.yaml** — hard constraints + capability gates (F03514)
//! 6. **MODEL_REGISTRY.yaml** — local/cloud model roles + eval scores (F03515)
//!
//! This crate exposes the typed manifest + presence/version checks; the
//! actual content discipline lives in the repo files themselves.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::path::Path;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine surface verbatim per F03509 dump 12194.
pub const DOCTRINE_WORKFLOW_VERSIONED: &str =
    "Workflow belongs in version-controlled repo artifacts";

/// One of the 6 canonical Symphony contracts.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ContractKind {
    /// SPEC.md (F03510).
    Spec,
    /// WORKFLOW.md (F03511).
    Workflow,
    /// PROFILES.yaml (F03512).
    Profiles,
    /// EVALS.yaml (F03513).
    Evals,
    /// POLICY.yaml (F03514).
    Policy,
    /// MODEL_REGISTRY.yaml (F03515).
    ModelRegistry,
}

impl ContractKind {
    /// Canonical filename per F03510-F03515.
    pub fn filename(self) -> &'static str {
        match self {
            ContractKind::Spec => "SPEC.md",
            ContractKind::Workflow => "WORKFLOW.md",
            ContractKind::Profiles => "PROFILES.yaml",
            ContractKind::Evals => "EVALS.yaml",
            ContractKind::Policy => "POLICY.yaml",
            ContractKind::ModelRegistry => "MODEL_REGISTRY.yaml",
        }
    }
    /// Canonical extension.
    pub fn extension(self) -> &'static str {
        match self {
            ContractKind::Spec | ContractKind::Workflow => "md",
            _ => "yaml",
        }
    }
}

/// One contract presence + version pin.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContractPin {
    /// Kind.
    pub kind: ContractKind,
    /// Repo-relative path (e.g. "docs/SPEC.md").
    pub repo_path: String,
    /// Operator-chosen semver pin or git revision.
    pub version: String,
    /// SHA-256 hex of the file content (empty until first sealed).
    pub content_hash: String,
}

/// Manifest envelope (the 6-contract index).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContractManifest {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// Doctrine surface — MUST equal [`DOCTRINE_WORKFLOW_VERSIONED`].
    pub doctrine: String,
    /// All 6 contract pins (exactly 6, no fewer, no more).
    pub pins: Vec<ContractPin>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ContractError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Doctrine surface tampered (F03509 verbatim).
    #[error("doctrine surface tampered: expected verbatim \"{expected}\", got \"{actual}\"")]
    DoctrineTampered {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// One of the 6 kinds is missing.
    #[error("required contract kind missing: {0:?}")]
    KindMissing(ContractKind),
    /// Wrong contract count.
    #[error("contract count {0} != 6 (M00705 SATURATED set)")]
    ContractCountInvalid(usize),
    /// Duplicate kind in the manifest.
    #[error("duplicate contract kind: {0:?}")]
    DuplicateKind(ContractKind),
    /// Repo path missing on disk.
    #[error("contract {kind:?} repo_path missing on disk: {path}")]
    PathMissing {
        /// Kind.
        kind: ContractKind,
        /// Repo-relative path.
        path: String,
    },
    /// Filename does not match canonical for the kind.
    #[error("contract {kind:?} filename mismatch: expected {expected}, got {actual}")]
    FilenameMismatch {
        /// Kind.
        kind: ContractKind,
        /// Expected basename.
        expected: String,
        /// Observed basename.
        actual: String,
    },
}

impl ContractManifest {
    /// Construct a canonical empty manifest with all 6 pins unsealed.
    pub fn empty_canonical() -> Self {
        let kinds = [
            ContractKind::Spec,
            ContractKind::Workflow,
            ContractKind::Profiles,
            ContractKind::Evals,
            ContractKind::Policy,
            ContractKind::ModelRegistry,
        ];
        let pins = kinds
            .into_iter()
            .map(|k| ContractPin {
                kind: k,
                repo_path: format!("docs/{}", k.filename()),
                version: "unsealed".into(),
                content_hash: String::new(),
            })
            .collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            doctrine: DOCTRINE_WORKFLOW_VERSIONED.into(),
            pins,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), ContractError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ContractError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.doctrine != DOCTRINE_WORKFLOW_VERSIONED {
            return Err(ContractError::DoctrineTampered {
                expected: DOCTRINE_WORKFLOW_VERSIONED.into(),
                actual: self.doctrine.clone(),
            });
        }
        if self.pins.len() != 6 {
            return Err(ContractError::ContractCountInvalid(self.pins.len()));
        }
        let required = [
            ContractKind::Spec,
            ContractKind::Workflow,
            ContractKind::Profiles,
            ContractKind::Evals,
            ContractKind::Policy,
            ContractKind::ModelRegistry,
        ];
        for k in required {
            if !self.pins.iter().any(|p| p.kind == k) {
                return Err(ContractError::KindMissing(k));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<ContractKind> = HashSet::new();
        for p in &self.pins {
            if !seen.insert(p.kind) {
                return Err(ContractError::DuplicateKind(p.kind));
            }
            // Filename must match the canonical extension for the kind.
            let basename = std::path::Path::new(&p.repo_path)
                .file_name()
                .map(|s| s.to_string_lossy().to_string())
                .unwrap_or_default();
            if basename != p.kind.filename() {
                return Err(ContractError::FilenameMismatch {
                    kind: p.kind,
                    expected: p.kind.filename().into(),
                    actual: basename,
                });
            }
        }
        Ok(())
    }

    /// Walk the filesystem and verify each contract path exists.
    pub fn verify_on_disk(&self, repo_root: &Path) -> Result<(), ContractError> {
        for p in &self.pins {
            let full = repo_root.join(&p.repo_path);
            if !full.is_file() {
                return Err(ContractError::PathMissing {
                    kind: p.kind,
                    path: p.repo_path.clone(),
                });
            }
        }
        Ok(())
    }

    /// Count of sealed contracts (content_hash non-empty).
    pub fn sealed_count(&self) -> usize {
        self.pins
            .iter()
            .filter(|p| !p.content_hash.is_empty())
            .count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_canonical_validates() {
        ContractManifest::empty_canonical().validate().unwrap();
    }

    #[test]
    fn canonical_has_exactly_6_pins() {
        assert_eq!(ContractManifest::empty_canonical().pins.len(), 6);
    }

    #[test]
    fn canonical_filenames_match_f03510_to_f03515() {
        assert_eq!(ContractKind::Spec.filename(), "SPEC.md");
        assert_eq!(ContractKind::Workflow.filename(), "WORKFLOW.md");
        assert_eq!(ContractKind::Profiles.filename(), "PROFILES.yaml");
        assert_eq!(ContractKind::Evals.filename(), "EVALS.yaml");
        assert_eq!(ContractKind::Policy.filename(), "POLICY.yaml");
        assert_eq!(
            ContractKind::ModelRegistry.filename(),
            "MODEL_REGISTRY.yaml"
        );
    }

    #[test]
    fn extensions_match_md_or_yaml() {
        assert_eq!(ContractKind::Spec.extension(), "md");
        assert_eq!(ContractKind::Workflow.extension(), "md");
        assert_eq!(ContractKind::Profiles.extension(), "yaml");
        assert_eq!(ContractKind::Evals.extension(), "yaml");
        assert_eq!(ContractKind::Policy.extension(), "yaml");
        assert_eq!(ContractKind::ModelRegistry.extension(), "yaml");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = ContractManifest::empty_canonical();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            ContractError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn doctrine_tamper_caught() {
        let mut m = ContractManifest::empty_canonical();
        m.doctrine = "Workflow belongs in agent memory".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            ContractError::DoctrineTampered { .. }
        ));
    }

    #[test]
    fn pin_count_invalid_rejected() {
        let mut m = ContractManifest::empty_canonical();
        m.pins.pop();
        assert!(matches!(
            m.validate().unwrap_err(),
            ContractError::ContractCountInvalid(5)
        ));
    }

    #[test]
    fn missing_kind_caught() {
        let mut m = ContractManifest::empty_canonical();
        // Replace EVALS with a second POLICY entry — count stays 6 but EVALS missing.
        m.pins[3] = ContractPin {
            kind: ContractKind::Policy,
            repo_path: "docs/POLICY.yaml".into(),
            version: "unsealed".into(),
            content_hash: String::new(),
        };
        let err = m.validate().unwrap_err();
        assert!(matches!(
            err,
            ContractError::KindMissing(ContractKind::Evals)
                | ContractError::DuplicateKind(ContractKind::Policy)
        ));
    }

    #[test]
    fn filename_mismatch_caught() {
        let mut m = ContractManifest::empty_canonical();
        m.pins[0].repo_path = "docs/wrong-name.txt".into();
        match m.validate().unwrap_err() {
            ContractError::FilenameMismatch {
                kind,
                expected,
                actual,
            } => {
                assert_eq!(kind, ContractKind::Spec);
                assert_eq!(expected, "SPEC.md");
                assert_eq!(actual, "wrong-name.txt");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn verify_on_disk_catches_missing_paths() {
        let tmp = std::env::temp_dir();
        let m = ContractManifest::empty_canonical();
        let err = m.verify_on_disk(&tmp).unwrap_err();
        assert!(matches!(err, ContractError::PathMissing { .. }));
    }

    #[test]
    fn sealed_count_tracks_content_hash() {
        let mut m = ContractManifest::empty_canonical();
        assert_eq!(m.sealed_count(), 0);
        m.pins[0].content_hash = "deadbeef".into();
        m.pins[3].content_hash = "cafebabe".into();
        assert_eq!(m.sealed_count(), 2);
    }

    #[test]
    fn doctrine_verbatim_constant() {
        assert_eq!(
            DOCTRINE_WORKFLOW_VERSIONED,
            "Workflow belongs in version-controlled repo artifacts"
        );
    }

    #[test]
    fn contract_kind_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ContractKind::ModelRegistry).unwrap(),
            "\"model-registry\""
        );
        assert_eq!(
            serde_json::to_string(&ContractKind::Workflow).unwrap(),
            "\"workflow\""
        );
    }

    #[test]
    fn manifest_serde_roundtrip() {
        let mut m = ContractManifest::empty_canonical();
        m.pins[0].content_hash = "sha".into();
        let j = serde_json::to_string(&m).unwrap();
        let back: ContractManifest = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
