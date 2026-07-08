//! `sovereign-inheritance-artifacts` — M042 8-artifact durable inheritance.
//!
//! Per M042 + M00712 + E0406 + dump 12494-12515.
//!
//! Doctrine verbatim per E0406:
//!
//! > "this is how the conversation becomes executable memory"
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::path::Path;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine verbatim per E0406.
pub const DOCTRINE_EXECUTABLE_MEMORY: &str =
    "this is how the conversation becomes executable memory";

/// 8 inheritance artifact kinds per dump 12500-12513.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ArtifactKind {
    /// VISION.md — philosophy + system thesis.
    Vision,
    /// ARCHITECTURE.md — planes / services / hardware mapping.
    Architecture,
    /// METHODOLOGY.md — MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN.
    Methodology,
    /// PROFILES.yaml — user-selectable operating modes.
    Profiles,
    /// POLICY.yaml — hard constraints + capability gates.
    Policy,
    /// MODEL_REGISTRY.yaml — local/cloud model roles + eval scores.
    ModelRegistry,
    /// HARDWARE_PROFILES.yaml — Blackwell/4090/AVX/ZFS/VFIO/MIG modes.
    HardwareProfiles,
    /// EVALS.yaml — trace/tool/task/quality/cost/risk evals.
    Evals,
}

impl ArtifactKind {
    /// Canonical filename per dump.
    pub fn filename(self) -> &'static str {
        match self {
            ArtifactKind::Vision => "VISION.md",
            ArtifactKind::Architecture => "ARCHITECTURE.md",
            ArtifactKind::Methodology => "METHODOLOGY.md",
            ArtifactKind::Profiles => "PROFILES.yaml",
            ArtifactKind::Policy => "POLICY.yaml",
            ArtifactKind::ModelRegistry => "MODEL_REGISTRY.yaml",
            ArtifactKind::HardwareProfiles => "HARDWARE_PROFILES.yaml",
            ArtifactKind::Evals => "EVALS.yaml",
        }
    }
    /// Canonical 1..8 position.
    pub fn position(self) -> u8 {
        match self {
            ArtifactKind::Vision => 1,
            ArtifactKind::Architecture => 2,
            ArtifactKind::Methodology => 3,
            ArtifactKind::Profiles => 4,
            ArtifactKind::Policy => 5,
            ArtifactKind::ModelRegistry => 6,
            ArtifactKind::HardwareProfiles => 7,
            ArtifactKind::Evals => 8,
        }
    }
    /// Description string per dump 12500-12513.
    pub fn description(self) -> &'static str {
        match self {
            ArtifactKind::Vision => "philosophy and system thesis",
            ArtifactKind::Architecture => "planes services hardware mapping",
            ArtifactKind::Methodology => "MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN",
            ArtifactKind::Profiles => "user-selectable operating modes",
            ArtifactKind::Policy => "hard constraints + capability gates",
            ArtifactKind::ModelRegistry => "local-cloud-model roles + eval scores",
            ArtifactKind::HardwareProfiles => "Blackwell/4090/AVX/ZFS/VFIO/MIG modes",
            ArtifactKind::Evals => "trace tool task quality cost risk evals",
        }
    }
}

/// One artifact pin.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ArtifactPin {
    /// Kind.
    pub kind: ArtifactKind,
    /// Repo-relative path.
    pub repo_path: String,
    /// SHA-256 content hash (hex). Empty until sealed.
    pub content_hash: String,
    /// Operator-supplied version pin (e.g. "v0.42.1" or git rev).
    pub version: String,
}

/// 8-artifact manifest envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ArtifactManifest {
    /// Schema version.
    pub schema_version: String,
    /// Doctrine surface — MUST equal [`DOCTRINE_EXECUTABLE_MEMORY`].
    pub doctrine: String,
    /// 8 artifact pins (exactly 8).
    pub artifacts: Vec<ArtifactPin>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ArtifactError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Doctrine tampered.
    #[error("doctrine tampered")]
    DoctrineTampered,
    /// Count != 8.
    #[error("artifact count {0} != 8 canonical")]
    CountInvalid(usize),
    /// Required artifact missing.
    #[error("required artifact missing: {0:?}")]
    ArtifactMissing(ArtifactKind),
    /// Duplicate artifact kind.
    #[error("duplicate artifact: {0:?}")]
    DuplicateArtifact(ArtifactKind),
    /// Filename mismatch.
    #[error("filename mismatch for {kind:?}: expected {expected}, got {actual}")]
    FilenameMismatch {
        /// Kind.
        kind: ArtifactKind,
        /// Expected basename.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Path missing on disk.
    #[error("artifact {kind:?} path missing on disk: {path}")]
    PathMissing {
        /// Kind.
        kind: ArtifactKind,
        /// Repo path.
        path: String,
    },
}

impl ArtifactManifest {
    /// Empty canonical manifest with all 8 unsealed.
    pub fn empty_canonical() -> Self {
        let artifacts = [
            ArtifactKind::Vision,
            ArtifactKind::Architecture,
            ArtifactKind::Methodology,
            ArtifactKind::Profiles,
            ArtifactKind::Policy,
            ArtifactKind::ModelRegistry,
            ArtifactKind::HardwareProfiles,
            ArtifactKind::Evals,
        ]
        .into_iter()
        .map(|k| ArtifactPin {
            kind: k,
            repo_path: format!("docs/{}", k.filename()),
            content_hash: String::new(),
            version: "unsealed".into(),
        })
        .collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            doctrine: DOCTRINE_EXECUTABLE_MEMORY.into(),
            artifacts,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ArtifactError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ArtifactError::SchemaMismatch);
        }
        if self.doctrine != DOCTRINE_EXECUTABLE_MEMORY {
            return Err(ArtifactError::DoctrineTampered);
        }
        if self.artifacts.len() != 8 {
            return Err(ArtifactError::CountInvalid(self.artifacts.len()));
        }
        let required = [
            ArtifactKind::Vision,
            ArtifactKind::Architecture,
            ArtifactKind::Methodology,
            ArtifactKind::Profiles,
            ArtifactKind::Policy,
            ArtifactKind::ModelRegistry,
            ArtifactKind::HardwareProfiles,
            ArtifactKind::Evals,
        ];
        for k in required {
            if !self.artifacts.iter().any(|a| a.kind == k) {
                return Err(ArtifactError::ArtifactMissing(k));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<ArtifactKind> = HashSet::new();
        for a in &self.artifacts {
            if !seen.insert(a.kind) {
                return Err(ArtifactError::DuplicateArtifact(a.kind));
            }
            let basename = Path::new(&a.repo_path)
                .file_name()
                .map(|s| s.to_string_lossy().to_string())
                .unwrap_or_default();
            if basename != a.kind.filename() {
                return Err(ArtifactError::FilenameMismatch {
                    kind: a.kind,
                    expected: a.kind.filename().into(),
                    actual: basename,
                });
            }
        }
        Ok(())
    }

    /// Walk filesystem and verify every artifact path exists.
    pub fn verify_on_disk(&self, repo_root: &Path) -> Result<(), ArtifactError> {
        for a in &self.artifacts {
            let full = repo_root.join(&a.repo_path);
            if !full.is_file() {
                return Err(ArtifactError::PathMissing {
                    kind: a.kind,
                    path: a.repo_path.clone(),
                });
            }
        }
        Ok(())
    }

    /// Sealed count (content_hash non-empty).
    pub fn sealed_count(&self) -> usize {
        self.artifacts
            .iter()
            .filter(|a| !a.content_hash.is_empty())
            .count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn eight_kinds_positioned() {
        for (k, p) in [
            (ArtifactKind::Vision, 1),
            (ArtifactKind::Architecture, 2),
            (ArtifactKind::Methodology, 3),
            (ArtifactKind::Profiles, 4),
            (ArtifactKind::Policy, 5),
            (ArtifactKind::ModelRegistry, 6),
            (ArtifactKind::HardwareProfiles, 7),
            (ArtifactKind::Evals, 8),
        ] {
            assert_eq!(k.position(), p);
        }
    }

    #[test]
    fn filenames_canonical() {
        assert_eq!(ArtifactKind::Vision.filename(), "VISION.md");
        assert_eq!(ArtifactKind::Methodology.filename(), "METHODOLOGY.md");
        assert_eq!(
            ArtifactKind::HardwareProfiles.filename(),
            "HARDWARE_PROFILES.yaml"
        );
        assert_eq!(
            ArtifactKind::ModelRegistry.filename(),
            "MODEL_REGISTRY.yaml"
        );
    }

    #[test]
    fn descriptions_verbatim() {
        assert_eq!(
            ArtifactKind::Vision.description(),
            "philosophy and system thesis"
        );
        assert_eq!(
            ArtifactKind::Architecture.description(),
            "planes services hardware mapping"
        );
        assert_eq!(
            ArtifactKind::Methodology.description(),
            "MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN"
        );
    }

    #[test]
    fn empty_canonical_validates() {
        ArtifactManifest::empty_canonical().validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = ArtifactManifest::empty_canonical();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            ArtifactError::SchemaMismatch
        ));
    }

    #[test]
    fn doctrine_tamper_caught() {
        let mut m = ArtifactManifest::empty_canonical();
        m.doctrine = "wrong".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            ArtifactError::DoctrineTampered
        ));
    }

    #[test]
    fn count_invalid_caught() {
        let mut m = ArtifactManifest::empty_canonical();
        m.artifacts.pop();
        assert!(matches!(
            m.validate().unwrap_err(),
            ArtifactError::CountInvalid(7)
        ));
    }

    #[test]
    fn filename_mismatch_caught() {
        let mut m = ArtifactManifest::empty_canonical();
        m.artifacts[0].repo_path = "docs/wrong.txt".into();
        match m.validate().unwrap_err() {
            ArtifactError::FilenameMismatch {
                kind,
                expected,
                actual,
            } => {
                assert_eq!(kind, ArtifactKind::Vision);
                assert_eq!(expected, "VISION.md");
                assert_eq!(actual, "wrong.txt");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn verify_on_disk_catches_missing() {
        let tmp = std::env::temp_dir();
        let m = ArtifactManifest::empty_canonical();
        assert!(matches!(
            m.verify_on_disk(&tmp).unwrap_err(),
            ArtifactError::PathMissing { .. }
        ));
    }

    #[test]
    fn sealed_count_tracks_hash() {
        let mut m = ArtifactManifest::empty_canonical();
        assert_eq!(m.sealed_count(), 0);
        m.artifacts[0].content_hash = "deadbeef".into();
        m.artifacts[4].content_hash = "cafebabe".into();
        assert_eq!(m.sealed_count(), 2);
    }

    #[test]
    fn doctrine_verbatim() {
        assert_eq!(
            DOCTRINE_EXECUTABLE_MEMORY,
            "this is how the conversation becomes executable memory"
        );
    }

    #[test]
    fn artifact_kind_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ArtifactKind::ModelRegistry).unwrap(),
            "\"model-registry\""
        );
        assert_eq!(
            serde_json::to_string(&ArtifactKind::HardwareProfiles).unwrap(),
            "\"hardware-profiles\""
        );
        assert_eq!(
            serde_json::to_string(&ArtifactKind::Methodology).unwrap(),
            "\"methodology\""
        );
    }

    #[test]
    fn manifest_serde_roundtrip() {
        let mut m = ArtifactManifest::empty_canonical();
        m.artifacts[3].content_hash = "sha".into();
        let j = serde_json::to_string(&m).unwrap();
        let back: ArtifactManifest = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
