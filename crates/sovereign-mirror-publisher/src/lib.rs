//! `sovereign-mirror-publisher` — typed manifest of the 9 selfdef-mirror
//! endpoints consumed by D-12..D-18 dashboards.
//!
//! Per M060 R10114-R10128 + MS043 R10182-R10193, the cockpit must
//! present cross-repo IPS state via the MS007 8/8 SATURATED typed-mirror
//! trio. This crate enumerates the 9 mirror crates, their dashboard
//! bindings, their schema versions, and the canonical HTTP/SSE paths
//! that publishers must expose.
//!
//! NOT a network server — the manifest is data. Producer daemons read
//! it to know which endpoints to serve; consumer dashboards read it to
//! know which endpoints to subscribe to.
//!
//! Standing rule: We do not minimize anything. We catalogue the
//! 8/8 SATURATED set; we do not invent new mirrors.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the mirror manifest.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// MS007 SATURATED-set count per MS043 R10182-R10193.
pub const SATURATED_MIRROR_COUNT: usize = 9;

/// One of the 9 canonical mirror crates.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum MirrorKind {
    /// selfdef-rules-mirror (D-12)
    Rules,
    /// selfdef-grants-mirror (D-13)
    Grants,
    /// selfdef-capability-mirror (D-14)
    Capability,
    /// selfdef-sandbox-mirror (D-15)
    Sandbox,
    /// selfdef-audit-mirror (D-16/D-19)
    Audit,
    /// selfdef-quarantine-mirror (D-17)
    Quarantine,
    /// selfdef-trust-score-mirror (D-18)
    TrustScore,
    /// selfdef-cli-mirror (introspection)
    Cli,
    /// selfdef-tui-mirror (introspection)
    Tui,
}

impl MirrorKind {
    /// Canonical crate name on disk.
    pub fn crate_name(self) -> &'static str {
        match self {
            MirrorKind::Rules => "selfdef-rules-mirror",
            MirrorKind::Grants => "selfdef-grants-mirror",
            MirrorKind::Capability => "selfdef-capability-mirror",
            MirrorKind::Sandbox => "selfdef-sandbox-mirror",
            MirrorKind::Audit => "selfdef-audit-mirror",
            MirrorKind::Quarantine => "selfdef-quarantine-mirror",
            MirrorKind::TrustScore => "selfdef-trust-score-mirror",
            MirrorKind::Cli => "selfdef-cli-mirror",
            MirrorKind::Tui => "selfdef-tui-mirror",
        }
    }
}

/// Single manifest entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MirrorEntry {
    /// Discriminator.
    pub kind: MirrorKind,
    /// Crate name (canonical on disk).
    pub crate_name: String,
    /// D-NN dashboard(s) consuming this mirror (D-12..D-18 + introspection).
    pub dashboards: Vec<String>,
    /// Schema version pinned at this publisher's emit (semver).
    pub schema_version: String,
    /// HTTP snapshot path (read-only) per MS043 R10212.
    pub snapshot_http_path: String,
    /// SSE event stream path (R10173 — auto-refresh).
    pub sse_path: String,
    /// True if a publisher is currently bound for this endpoint.
    pub bound: bool,
}

/// Top-level mirror manifest.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MirrorManifest {
    /// Wire-stable schema version. MUST equal [`SCHEMA_VERSION`].
    pub schema_version: String,
    /// ISO-8601 UTC timestamp of last manifest refresh.
    pub captured_at: String,
    /// All 9 mirror entries in canonical order. MUST be exactly 9.
    pub entries: Vec<MirrorEntry>,
}

/// Manifest errors.
#[derive(Debug, Error)]
pub enum ManifestError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected version.
        expected: String,
        /// Observed version.
        actual: String,
    },
    /// Entry count != 9 — SATURATED set invariant broken.
    #[error("mirror entry count {0} != 9 SATURATED set (MS043 R10182-R10193)")]
    SaturatedSetBroken(usize),
    /// A required mirror kind is missing from the manifest.
    #[error("mirror kind missing from manifest: {0:?}")]
    KindMissing(MirrorKind),
    /// Duplicate snapshot path across two entries.
    #[error("duplicate snapshot path: {0}")]
    DuplicatePath(String),
}

impl MirrorManifest {
    /// Construct a default manifest with all 9 entries unbound.
    pub fn canonical() -> Self {
        let entries = vec![
            MirrorEntry {
                kind: MirrorKind::Rules,
                crate_name: MirrorKind::Rules.crate_name().into(),
                dashboards: vec!["D-12".into()],
                schema_version: "1.0.0".into(),
                snapshot_http_path: "/api/d-12/snapshot".into(),
                sse_path: "/api/d-12/stream".into(),
                bound: false,
            },
            MirrorEntry {
                kind: MirrorKind::Grants,
                crate_name: MirrorKind::Grants.crate_name().into(),
                dashboards: vec!["D-13".into()],
                schema_version: "1.0.0".into(),
                snapshot_http_path: "/api/d-13/snapshot".into(),
                sse_path: "/api/d-13/stream".into(),
                bound: false,
            },
            MirrorEntry {
                kind: MirrorKind::Capability,
                crate_name: MirrorKind::Capability.crate_name().into(),
                dashboards: vec!["D-14".into()],
                schema_version: "1.0.0".into(),
                snapshot_http_path: "/api/d-14/snapshot".into(),
                sse_path: "/api/d-14/stream".into(),
                bound: false,
            },
            MirrorEntry {
                kind: MirrorKind::Sandbox,
                crate_name: MirrorKind::Sandbox.crate_name().into(),
                dashboards: vec!["D-15".into()],
                schema_version: "1.0.0".into(),
                snapshot_http_path: "/api/d-15/snapshot".into(),
                sse_path: "/api/d-15/stream".into(),
                bound: false,
            },
            MirrorEntry {
                kind: MirrorKind::Audit,
                crate_name: MirrorKind::Audit.crate_name().into(),
                dashboards: vec!["D-16".into(), "D-19".into()],
                schema_version: "1.0.0".into(),
                snapshot_http_path: "/api/d-16/snapshot".into(),
                sse_path: "/api/d-16/stream".into(),
                bound: false,
            },
            MirrorEntry {
                kind: MirrorKind::Quarantine,
                crate_name: MirrorKind::Quarantine.crate_name().into(),
                dashboards: vec!["D-17".into()],
                schema_version: "1.0.0".into(),
                snapshot_http_path: "/api/d-17/snapshot".into(),
                sse_path: "/api/d-17/stream".into(),
                bound: false,
            },
            MirrorEntry {
                kind: MirrorKind::TrustScore,
                crate_name: MirrorKind::TrustScore.crate_name().into(),
                dashboards: vec!["D-18".into()],
                schema_version: "1.0.0".into(),
                snapshot_http_path: "/api/d-18/snapshot".into(),
                sse_path: "/api/d-18/stream".into(),
                bound: false,
            },
            MirrorEntry {
                kind: MirrorKind::Cli,
                crate_name: MirrorKind::Cli.crate_name().into(),
                dashboards: vec!["introspection".into()],
                schema_version: "1.0.0".into(),
                snapshot_http_path: "/api/cli-mirror/snapshot".into(),
                sse_path: "/api/cli-mirror/stream".into(),
                bound: false,
            },
            MirrorEntry {
                kind: MirrorKind::Tui,
                crate_name: MirrorKind::Tui.crate_name().into(),
                dashboards: vec!["introspection".into()],
                schema_version: "1.0.0".into(),
                snapshot_http_path: "/api/tui-mirror/snapshot".into(),
                sse_path: "/api/tui-mirror/stream".into(),
                bound: false,
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            captured_at: "2026-05-19T00:00:00Z".into(),
            entries,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), ManifestError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ManifestError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.entries.len() != SATURATED_MIRROR_COUNT {
            return Err(ManifestError::SaturatedSetBroken(self.entries.len()));
        }
        for required in [
            MirrorKind::Rules, MirrorKind::Grants, MirrorKind::Capability,
            MirrorKind::Sandbox, MirrorKind::Audit, MirrorKind::Quarantine,
            MirrorKind::TrustScore, MirrorKind::Cli, MirrorKind::Tui,
        ] {
            if !self.entries.iter().any(|e| e.kind == required) {
                return Err(ManifestError::KindMissing(required));
            }
        }
        // Detect duplicate snapshot paths.
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for e in &self.entries {
            if !seen.insert(&e.snapshot_http_path) {
                return Err(ManifestError::DuplicatePath(e.snapshot_http_path.clone()));
            }
        }
        Ok(())
    }

    /// Lookup an entry by kind.
    pub fn entry(&self, kind: MirrorKind) -> Option<&MirrorEntry> {
        self.entries.iter().find(|e| e.kind == kind)
    }

    /// Mark a kind as bound to an active publisher.
    pub fn mark_bound(&mut self, kind: MirrorKind) {
        if let Some(e) = self.entries.iter_mut().find(|e| e.kind == kind) {
            e.bound = true;
        }
    }

    /// Count of currently bound publishers.
    pub fn bound_count(&self) -> usize {
        self.entries.iter().filter(|e| e.bound).count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_manifest_validates() {
        MirrorManifest::canonical().validate().unwrap();
    }

    #[test]
    fn canonical_has_exactly_9_entries() {
        assert_eq!(MirrorManifest::canonical().entries.len(), SATURATED_MIRROR_COUNT);
    }

    #[test]
    fn saturated_set_break_rejected() {
        let mut m = MirrorManifest::canonical();
        m.entries.pop();
        assert!(matches!(m.validate().unwrap_err(), ManifestError::SaturatedSetBroken(8)));
    }

    #[test]
    fn duplicate_path_rejected() {
        let mut m = MirrorManifest::canonical();
        m.entries[1].snapshot_http_path = m.entries[0].snapshot_http_path.clone();
        assert!(matches!(m.validate().unwrap_err(), ManifestError::DuplicatePath(_)));
    }

    #[test]
    fn each_kind_has_unique_endpoints() {
        let m = MirrorManifest::canonical();
        use std::collections::HashSet;
        let snaps: HashSet<&str> = m.entries.iter().map(|e| e.snapshot_http_path.as_str()).collect();
        let sses: HashSet<&str> = m.entries.iter().map(|e| e.sse_path.as_str()).collect();
        assert_eq!(snaps.len(), SATURATED_MIRROR_COUNT);
        assert_eq!(sses.len(), SATURATED_MIRROR_COUNT);
    }

    #[test]
    fn audit_mirror_serves_two_dashboards() {
        let m = MirrorManifest::canonical();
        let audit = m.entry(MirrorKind::Audit).unwrap();
        assert!(audit.dashboards.iter().any(|s| s == "D-16"));
        assert!(audit.dashboards.iter().any(|s| s == "D-19"));
    }

    #[test]
    fn crate_names_match_canonical() {
        assert_eq!(MirrorKind::Rules.crate_name(), "selfdef-rules-mirror");
        assert_eq!(MirrorKind::TrustScore.crate_name(), "selfdef-trust-score-mirror");
        assert_eq!(MirrorKind::Tui.crate_name(), "selfdef-tui-mirror");
    }

    #[test]
    fn bound_lifecycle_count() {
        let mut m = MirrorManifest::canonical();
        assert_eq!(m.bound_count(), 0);
        m.mark_bound(MirrorKind::Rules);
        m.mark_bound(MirrorKind::Grants);
        assert_eq!(m.bound_count(), 2);
        assert!(m.entry(MirrorKind::Rules).unwrap().bound);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = MirrorManifest::canonical();
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), ManifestError::SchemaMismatch { .. }));
    }

    #[test]
    fn missing_kind_rejected_when_replaced_with_duplicate() {
        let mut m = MirrorManifest::canonical();
        // Replace Rules slot with a second Grants entry; count stays 9 but Rules missing.
        m.entries[0] = MirrorEntry {
            kind: MirrorKind::Grants,
            crate_name: MirrorKind::Grants.crate_name().into(),
            dashboards: vec!["D-13-dup".into()],
            schema_version: "1.0.0".into(),
            snapshot_http_path: "/api/d-13-dup/snapshot".into(),
            sse_path: "/api/d-13-dup/stream".into(),
            bound: false,
        };
        assert!(matches!(m.validate().unwrap_err(), ManifestError::KindMissing(MirrorKind::Rules)));
    }

    #[test]
    fn manifest_serde_roundtrip() {
        let m = MirrorManifest::canonical();
        let j = serde_json::to_string(&m).unwrap();
        let back: MirrorManifest = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
        assert_eq!(back.entries.len(), SATURATED_MIRROR_COUNT);
    }

    #[test]
    fn mirror_kind_serde_uses_kebab_case() {
        assert_eq!(serde_json::to_string(&MirrorKind::TrustScore).unwrap(), "\"trust-score\"");
        assert_eq!(serde_json::to_string(&MirrorKind::Cli).unwrap(), "\"cli\"");
    }
}
