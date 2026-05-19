//! `sovereign-dashboard-coverage` — verifies every M060 D-NN slot has
//! coverage via either a dedicated webapp/ subdirectory or a documented
//! alias to an existing surface.
//!
//! Per M060 R10128 + R10199 the catalog requires 21 dashboards
//! (D-00..D-20) and the operator standing direction "20+ dashboards and
//! a main one" must be satisfied verbatim.
//!
//! This crate exposes a coverage manifest (which D-NN maps to which
//! webapp directory) and a `verify()` entry point that walks the
//! webapp/ tree and flags any gap.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::path::Path;
use thiserror::Error;

/// Schema version of the dashboard coverage manifest.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// M060 catalog dashboard count (D-00..D-20).
pub const CATALOG_COUNT: usize = 21;

/// How a D-NN slot is covered.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CoverageKind {
    /// Dedicated webapp/ subdirectory authored for this D-NN.
    Dedicated,
    /// Existing surface re-used (documented alias).
    Alias,
    /// Catalog-only — no surface yet (deferred / future).
    CatalogOnly,
}

/// Single D-NN coverage entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CoverageEntry {
    /// Slot id, e.g. "D-00", "D-12".
    pub slot: String,
    /// Coverage kind.
    pub kind: CoverageKind,
    /// Path in the repo where the surface lives (relative to repo root).
    pub path: String,
    /// Single-line title.
    pub title: String,
    /// Notes (e.g. "alias for D-16 audit cycles").
    pub notes: String,
}

/// Coverage manifest. Wire-stable.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CoverageManifest {
    /// Schema version. MUST equal [`SCHEMA_VERSION`].
    pub schema_version: String,
    /// All 21 entries (D-00..D-20). MUST be exactly 21.
    pub entries: Vec<CoverageEntry>,
}

/// Coverage errors.
#[derive(Debug, Error)]
pub enum CoverageError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Slot count != 21.
    #[error("dashboard slot count {0} != 21 (M060 catalog)")]
    SlotCountInvalid(usize),
    /// Missing slot in canonical D-00..D-20 range.
    #[error("missing dashboard slot in catalog: {0}")]
    SlotMissing(String),
    /// Dedicated path does not exist on disk.
    #[error("dedicated path missing for {slot}: {path}")]
    DedicatedPathMissing {
        /// Slot id.
        slot: String,
        /// Expected path.
        path: String,
    },
}

impl CoverageManifest {
    /// Construct the canonical 21-entry coverage manifest matching the
    /// current ship state. Aliases reflect operator-approved mappings:
    /// D-16 → `webapp/auditor/`, D-21+ slots reserved.
    pub fn canonical() -> Self {
        let entries = vec![
            slot(
                "D-00",
                CoverageKind::Dedicated,
                "webapp/master-dashboard",
                "master dashboard",
            ),
            slot(
                "D-01",
                CoverageKind::Dedicated,
                "webapp/d-01-active-sessions",
                "active sessions",
            ),
            slot(
                "D-02",
                CoverageKind::Dedicated,
                "webapp/d-02-profile-choices",
                "profile choices",
            ),
            slot(
                "D-03",
                CoverageKind::Dedicated,
                "webapp/d-03-model-health",
                "model health",
            ),
            slot(
                "D-04",
                CoverageKind::Dedicated,
                "webapp/d-04-costs",
                "costs",
            ),
            slot(
                "D-05",
                CoverageKind::Dedicated,
                "webapp/d-05-traces",
                "traces",
            ),
            slot(
                "D-06",
                CoverageKind::Dedicated,
                "webapp/d-06-pending-approvals",
                "pending approvals",
            ),
            slot(
                "D-07",
                CoverageKind::Dedicated,
                "webapp/d-07-memory-changes",
                "memory changes",
            ),
            slot(
                "D-08",
                CoverageKind::Dedicated,
                "webapp/d-08-rollback-points",
                "rollback points",
            ),
            slot(
                "D-09",
                CoverageKind::Dedicated,
                "webapp/d-09-hardware-pressure",
                "hardware pressure",
            ),
            slot(
                "D-10",
                CoverageKind::Dedicated,
                "webapp/d-10-eval-history",
                "eval history",
            ),
            slot(
                "D-11",
                CoverageKind::Dedicated,
                "webapp/d-11-adapter-status",
                "adapter status",
            ),
            slot(
                "D-12",
                CoverageKind::Dedicated,
                "webapp/d-12-networking",
                "networking",
            ),
            slot(
                "D-13",
                CoverageKind::Dedicated,
                "webapp/d-13-filesystem-grants",
                "filesystem grants",
            ),
            slot_notes(
                "D-14",
                CoverageKind::Dedicated,
                "webapp/d-14-capability-tokens",
                "capability tokens",
                "consumes selfdef-capability-mirror",
            ),
            slot(
                "D-15",
                CoverageKind::Dedicated,
                "webapp/d-15-sandboxes",
                "sandboxes",
            ),
            slot_notes(
                "D-16",
                CoverageKind::Alias,
                "webapp/auditor",
                "audit cycles",
                "alias — existing auditor surface; per M060 R09xxx",
            ),
            slot(
                "D-17",
                CoverageKind::Dedicated,
                "webapp/d-17-quarantine",
                "quarantine",
            ),
            slot(
                "D-18",
                CoverageKind::Dedicated,
                "webapp/d-18-trust-scores",
                "trust scores",
            ),
            slot(
                "D-19",
                CoverageKind::Dedicated,
                "webapp/d-19-super-model-manifest",
                "super-model manifest",
            ),
            slot(
                "D-20",
                CoverageKind::Dedicated,
                "webapp/d-20-peace-machine-health",
                "peace machine health",
            ),
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            entries,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), CoverageError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CoverageError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.entries.len() != CATALOG_COUNT {
            return Err(CoverageError::SlotCountInvalid(self.entries.len()));
        }
        // Verify every D-NN in 00..20 is present.
        for n in 0..=20 {
            let want = format!("D-{n:02}");
            if !self.entries.iter().any(|e| e.slot == want) {
                return Err(CoverageError::SlotMissing(want));
            }
        }
        Ok(())
    }

    /// Walk the filesystem at `repo_root` and verify every Dedicated /
    /// Alias entry points at an existing path.
    pub fn verify_on_disk(&self, repo_root: &Path) -> Result<(), CoverageError> {
        for e in &self.entries {
            if e.kind == CoverageKind::CatalogOnly {
                continue;
            }
            let p = repo_root.join(&e.path);
            if !p.is_dir() {
                return Err(CoverageError::DedicatedPathMissing {
                    slot: e.slot.clone(),
                    path: e.path.clone(),
                });
            }
        }
        Ok(())
    }

    /// Count of slots covered by a dedicated webapp/ subdirectory.
    pub fn dedicated_count(&self) -> usize {
        self.entries
            .iter()
            .filter(|e| e.kind == CoverageKind::Dedicated)
            .count()
    }

    /// Count of slots covered by alias.
    pub fn alias_count(&self) -> usize {
        self.entries
            .iter()
            .filter(|e| e.kind == CoverageKind::Alias)
            .count()
    }

    /// Count of slots that are catalog-only (no surface yet).
    pub fn catalog_only_count(&self) -> usize {
        self.entries
            .iter()
            .filter(|e| e.kind == CoverageKind::CatalogOnly)
            .count()
    }
}

fn slot(s: &str, k: CoverageKind, path: &str, title: &str) -> CoverageEntry {
    CoverageEntry {
        slot: s.into(),
        kind: k,
        path: path.into(),
        title: title.into(),
        notes: String::new(),
    }
}

fn slot_notes(s: &str, k: CoverageKind, path: &str, title: &str, notes: &str) -> CoverageEntry {
    CoverageEntry {
        slot: s.into(),
        kind: k,
        path: path.into(),
        title: title.into(),
        notes: notes.into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_manifest_validates() {
        CoverageManifest::canonical().validate().unwrap();
    }

    #[test]
    fn canonical_has_21_entries() {
        assert_eq!(CoverageManifest::canonical().entries.len(), 21);
    }

    #[test]
    fn d00_through_d20_present() {
        let m = CoverageManifest::canonical();
        for n in 0..=20 {
            let want = format!("D-{n:02}");
            assert!(m.entries.iter().any(|e| e.slot == want), "missing {want}");
        }
    }

    #[test]
    fn missing_slot_caught() {
        let mut m = CoverageManifest::canonical();
        m.entries.retain(|e| e.slot != "D-07");
        m.entries
            .push(slot("D-99", CoverageKind::CatalogOnly, "", "ghost"));
        let err = m.validate().unwrap_err();
        match err {
            CoverageError::SlotMissing(s) => assert_eq!(s, "D-07"),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn slot_count_invalid_caught() {
        let mut m = CoverageManifest::canonical();
        m.entries.pop();
        assert!(matches!(
            m.validate().unwrap_err(),
            CoverageError::SlotCountInvalid(20)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = CoverageManifest::canonical();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            CoverageError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn d16_is_alias_to_auditor() {
        let m = CoverageManifest::canonical();
        let d16 = m.entries.iter().find(|e| e.slot == "D-16").unwrap();
        assert_eq!(d16.kind, CoverageKind::Alias);
        assert_eq!(d16.path, "webapp/auditor");
        assert!(d16.notes.contains("alias"));
    }

    #[test]
    fn coverage_counts_sum_to_21() {
        let m = CoverageManifest::canonical();
        assert_eq!(
            m.dedicated_count() + m.alias_count() + m.catalog_only_count(),
            21
        );
    }

    #[test]
    fn at_least_20_surfaces_satisfy_operator_target() {
        // operator standing direction 2026-05-19: "20+ dashboards and a main one"
        let m = CoverageManifest::canonical();
        let live = m.dedicated_count() + m.alias_count();
        assert!(
            live >= 20,
            "operator target unsatisfied: only {live} live surfaces"
        );
    }

    #[test]
    fn verify_on_disk_catches_missing_path() {
        // Use a tempdir that has no webapp/ tree at all.
        let tmp = tempfile::tempdir().unwrap();
        let m = CoverageManifest::canonical();
        match m.verify_on_disk(tmp.path()).unwrap_err() {
            CoverageError::DedicatedPathMissing { slot, .. } => assert_eq!(slot, "D-00"),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn manifest_serde_roundtrip() {
        let m = CoverageManifest::canonical();
        let j = serde_json::to_string(&m).unwrap();
        let back: CoverageManifest = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }

    #[test]
    fn coverage_kind_serde_uses_kebab_case() {
        assert_eq!(
            serde_json::to_string(&CoverageKind::Dedicated).unwrap(),
            "\"dedicated\""
        );
        assert_eq!(
            serde_json::to_string(&CoverageKind::Alias).unwrap(),
            "\"alias\""
        );
        assert_eq!(
            serde_json::to_string(&CoverageKind::CatalogOnly).unwrap(),
            "\"catalog-only\""
        );
    }
}
