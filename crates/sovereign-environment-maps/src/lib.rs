//! `sovereign-environment-maps` — M042 MAP doctrine implementation.
//!
//! Per M042 + R07012-R07020 + M00704 + dump 12175-12189:
//!
//! > "Do not let agents learn the environment only by failing through it."
//! > "Build a map first."
//!
//! Seven map types (R07014-R07020):
//!
//! 1. **repo map** — module tree + ownership + recent change rate
//! 2. **test map** — test inventory + flaky-test history + coverage gaps
//! 3. **tool map** — installed CLIs + MS036 tier + capability_words
//! 4. **risk map** — known fragile files + sensitive paths + secret stores
//! 5. **memory map** — M028 8-memory-type inventory + size + freshness
//! 6. **GUI/world map** — visible windows + shells + browser tabs (M052)
//! 7. **dependency map** — package graph + license posture + CVE status
//!
//! Standing rule: We do not minimize anything. Maps are read-only
//! snapshots; mutations live in the agents that *use* the maps.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine surface preserved verbatim per R07012 dump 12175.
pub const DOCTRINE_BUILD_MAP_FIRST: &str =
    "Do not let agents learn the environment only by failing through it";

/// Canonical 7 map types per R07014-R07020.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum MapKind {
    /// Repo map (R07014 dump 12183).
    Repo,
    /// Test map (R07015 dump 12184).
    Test,
    /// Tool map (R07016 dump 12185).
    Tool,
    /// Risk map (R07017 dump 12186).
    Risk,
    /// Memory map (R07018 dump 12187).
    Memory,
    /// GUI / world map (R07019 dump 12188).
    GuiWorld,
    /// Dependency map (R07020 dump 12189).
    Dependency,
}

/// One map entry (lightweight typed wrapper around free-form key/value).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MapEntry {
    /// Map kind discriminator.
    pub kind: MapKind,
    /// ISO-8601 UTC timestamp when this map was built.
    pub built_at: String,
    /// Total entry count in the underlying map.
    pub entry_count: u32,
    /// Free-form payload keyed by canonical id. Producers fill schema
    /// per-kind; the wrapper stays generic to match the M042 catalog spec.
    pub payload: BTreeMap<String, String>,
    /// MS003 signature over canonical-JSON encoding (hex). Empty until signed.
    pub signature: String,
}

/// Top-level envelope: all 7 maps + a doctrine surface.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EnvironmentMaps {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// Doctrine string — MUST equal [`DOCTRINE_BUILD_MAP_FIRST`].
    pub doctrine: String,
    /// 7 maps keyed by [`MapKind`].
    pub maps: Vec<MapEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MapsError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Doctrine surface tampered (R07012 verbatim).
    #[error("doctrine surface tampered: expected verbatim \"{expected}\", got \"{actual}\"")]
    DoctrineTampered {
        /// Expected canonical doctrine.
        expected: String,
        /// Observed (tampered) value.
        actual: String,
    },
    /// One of the 7 map kinds is missing from the envelope.
    #[error("required map kind missing: {0:?}")]
    KindMissing(MapKind),
    /// Map count != exactly 7.
    #[error("map count {0} != 7 canonical maps (R07014-R07020 + M00704)")]
    MapCountInvalid(usize),
    /// Duplicate kind in the envelope.
    #[error("duplicate map kind: {0:?}")]
    DuplicateKind(MapKind),
}

impl EnvironmentMaps {
    /// Construct an empty 7-map envelope with all kinds present + unsigned.
    pub fn empty_canonical() -> Self {
        let now = "2026-05-19T00:00:00Z";
        let kinds = [
            MapKind::Repo,
            MapKind::Test,
            MapKind::Tool,
            MapKind::Risk,
            MapKind::Memory,
            MapKind::GuiWorld,
            MapKind::Dependency,
        ];
        let maps = kinds
            .into_iter()
            .map(|k| MapEntry {
                kind: k,
                built_at: now.into(),
                entry_count: 0,
                payload: BTreeMap::new(),
                signature: String::new(),
            })
            .collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            doctrine: DOCTRINE_BUILD_MAP_FIRST.into(),
            maps,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), MapsError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MapsError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.doctrine != DOCTRINE_BUILD_MAP_FIRST {
            return Err(MapsError::DoctrineTampered {
                expected: DOCTRINE_BUILD_MAP_FIRST.into(),
                actual: self.doctrine.clone(),
            });
        }
        if self.maps.len() != 7 {
            return Err(MapsError::MapCountInvalid(self.maps.len()));
        }
        let required = [
            MapKind::Repo,
            MapKind::Test,
            MapKind::Tool,
            MapKind::Risk,
            MapKind::Memory,
            MapKind::GuiWorld,
            MapKind::Dependency,
        ];
        for k in required {
            if !self.maps.iter().any(|m| m.kind == k) {
                return Err(MapsError::KindMissing(k));
            }
        }
        // Detect duplicates.
        use std::collections::HashSet;
        let mut seen: HashSet<MapKind> = HashSet::new();
        for m in &self.maps {
            if !seen.insert(m.kind) {
                return Err(MapsError::DuplicateKind(m.kind));
            }
        }
        Ok(())
    }

    /// Lookup by kind.
    pub fn get(&self, kind: MapKind) -> Option<&MapEntry> {
        self.maps.iter().find(|m| m.kind == kind)
    }

    /// Mutable lookup.
    pub fn get_mut(&mut self, kind: MapKind) -> Option<&mut MapEntry> {
        self.maps.iter_mut().find(|m| m.kind == kind)
    }

    /// Total entries across all maps (sum of each map's entry_count).
    pub fn total_entries(&self) -> u64 {
        self.maps.iter().map(|m| m.entry_count as u64).sum()
    }

    /// True if every map has been signed (per-map signature non-empty).
    pub fn all_signed(&self) -> bool {
        self.maps.iter().all(|m| !m.signature.is_empty())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_canonical_validates() {
        EnvironmentMaps::empty_canonical().validate().unwrap();
    }

    #[test]
    fn canonical_has_exactly_7_maps() {
        assert_eq!(EnvironmentMaps::empty_canonical().maps.len(), 7);
    }

    #[test]
    fn all_7_kinds_present() {
        let m = EnvironmentMaps::empty_canonical();
        for k in [
            MapKind::Repo,
            MapKind::Test,
            MapKind::Tool,
            MapKind::Risk,
            MapKind::Memory,
            MapKind::GuiWorld,
            MapKind::Dependency,
        ] {
            assert!(m.get(k).is_some(), "missing kind {k:?}");
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = EnvironmentMaps::empty_canonical();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            MapsError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn doctrine_tamper_caught() {
        let mut m = EnvironmentMaps::empty_canonical();
        m.doctrine = "Let agents learn by failing".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            MapsError::DoctrineTampered { .. }
        ));
    }

    #[test]
    fn map_count_invalid_rejected() {
        let mut m = EnvironmentMaps::empty_canonical();
        m.maps.pop();
        assert!(matches!(
            m.validate().unwrap_err(),
            MapsError::MapCountInvalid(6)
        ));
    }

    #[test]
    fn missing_kind_caught_when_replaced() {
        let mut m = EnvironmentMaps::empty_canonical();
        // Replace Repo with a duplicate Test — count stays 7, but Repo is missing
        // and Test is duplicated.
        m.maps[0] = MapEntry {
            kind: MapKind::Test,
            built_at: "2026-05-19T00:00:00Z".into(),
            entry_count: 0,
            payload: BTreeMap::new(),
            signature: String::new(),
        };
        let err = m.validate().unwrap_err();
        // Either Repo missing OR Test duplicated — both are valid catches.
        assert!(matches!(
            err,
            MapsError::KindMissing(MapKind::Repo) | MapsError::DuplicateKind(MapKind::Test)
        ));
    }

    #[test]
    fn get_mut_allows_payload_population() {
        let mut m = EnvironmentMaps::empty_canonical();
        let entry = m.get_mut(MapKind::Repo).unwrap();
        entry
            .payload
            .insert("crates/sovereign-nvfp4-runtime".into(), "M077".into());
        entry
            .payload
            .insert("crates/sovereign-holderpo".into(), "M078".into());
        entry.entry_count = entry.payload.len() as u32;
        assert_eq!(m.get(MapKind::Repo).unwrap().entry_count, 2);
        m.validate().unwrap();
    }

    #[test]
    fn total_entries_sums_across_maps() {
        let mut m = EnvironmentMaps::empty_canonical();
        m.get_mut(MapKind::Repo).unwrap().entry_count = 100;
        m.get_mut(MapKind::Test).unwrap().entry_count = 50;
        m.get_mut(MapKind::Tool).unwrap().entry_count = 12;
        assert_eq!(m.total_entries(), 162);
    }

    #[test]
    fn all_signed_returns_false_when_any_unsigned() {
        let m = EnvironmentMaps::empty_canonical();
        assert!(!m.all_signed());
    }

    #[test]
    fn all_signed_returns_true_when_complete() {
        let mut m = EnvironmentMaps::empty_canonical();
        for entry in m.maps.iter_mut() {
            entry.signature = format!("sig-{:?}", entry.kind);
        }
        assert!(m.all_signed());
    }

    #[test]
    fn doctrine_constant_verbatim() {
        assert_eq!(
            DOCTRINE_BUILD_MAP_FIRST,
            "Do not let agents learn the environment only by failing through it"
        );
    }

    #[test]
    fn map_kind_serde_kebab_case() {
        assert_eq!(
            serde_json::to_string(&MapKind::GuiWorld).unwrap(),
            "\"gui-world\""
        );
        assert_eq!(serde_json::to_string(&MapKind::Repo).unwrap(), "\"repo\"");
        assert_eq!(
            serde_json::to_string(&MapKind::Dependency).unwrap(),
            "\"dependency\""
        );
    }

    #[test]
    fn envelope_serde_roundtrip() {
        let mut m = EnvironmentMaps::empty_canonical();
        m.get_mut(MapKind::Risk)
            .unwrap()
            .payload
            .insert("/etc/passwd".into(), "high".into());
        m.get_mut(MapKind::Risk).unwrap().entry_count = 1;
        let j = serde_json::to_string(&m).unwrap();
        let back: EnvironmentMaps = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
