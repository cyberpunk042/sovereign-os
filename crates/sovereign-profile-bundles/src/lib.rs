//! `sovereign-profile-bundles` — M042 4 canonical profile bundles.
//!
//! Per M00710 + R07118-R07132 + dump 12448-12473.
//!
//! - **private** — local models / no network / no cloud / sandbox tools
//! - **careful** — map first / spec required / tests required / oracle review
//! - **fast** — scout first / shallow map / minimal verification
//! - **sovereign** — user-visible gates / local memory / explicit external / replay always
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 4 canonical profile bundle names.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum BundleName {
    /// private — local-only.
    Private,
    /// careful — gate-heavy.
    Careful,
    /// fast — speed-first.
    Fast,
    /// sovereign — user-visible + replay-always.
    Sovereign,
}

impl BundleName {
    /// Canonical 1..4 position.
    pub fn position(self) -> u8 {
        match self {
            BundleName::Private => 1,
            BundleName::Careful => 2,
            BundleName::Fast => 3,
            BundleName::Sovereign => 4,
        }
    }
    /// Verbatim feature list per dump 12453-12473.
    pub fn features(self) -> [&'static str; 4] {
        match self {
            BundleName::Private => [
                "local models",        // R07118
                "no network",          // R07119
                "no cloud",            // R07120
                "sandbox tools",       // R07121
            ],
            BundleName::Careful => [
                "map first",           // R07122
                "spec required",       // R07123
                "tests required",      // R07124
                "oracle review",       // R07125
            ],
            BundleName::Fast => [
                "scout first",         // R07126
                "shallow map",         // R07127
                "minimal verification",// R07128
                "",                    // (only 3 listed; 4th slot reserved)
            ],
            BundleName::Sovereign => [
                "user-visible gates",  // R07129
                "local memory ownership", // R07130
                "explicit external calls", // R07131
                "replay always on",    // R07132
            ],
        }
    }
}

/// Per-bundle state record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BundleEntry {
    /// Bundle name.
    pub bundle: BundleName,
    /// Whether this bundle is selectable (operator hasn't disabled it).
    pub selectable: bool,
    /// 4 features in canonical order.
    pub features: Vec<String>,
}

/// 4-bundle catalog envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BundleCatalog {
    /// Schema version.
    pub schema_version: String,
    /// 4 bundles (MUST be exactly 4).
    pub bundles: Vec<BundleEntry>,
    /// Currently active bundle (must be one of the 4).
    pub active: BundleName,
}

/// Errors.
#[derive(Debug, Error)]
pub enum BundleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 4.
    #[error("bundle count {0} != 4 canonical")]
    CountInvalid(usize),
    /// Required bundle missing.
    #[error("required bundle missing: {0:?}")]
    BundleMissing(BundleName),
    /// Duplicate bundle.
    #[error("duplicate bundle: {0:?}")]
    DuplicateBundle(BundleName),
    /// Active bundle is not selectable.
    #[error("active bundle {0:?} is not selectable")]
    ActiveNotSelectable(BundleName),
    /// Feature list does not match canonical.
    #[error("feature list mismatch for {bundle:?}")]
    FeatureMismatch {
        /// Bundle.
        bundle: BundleName,
    },
}

impl BundleCatalog {
    /// Construct canonical empty catalog — all 4 selectable, active=Private.
    pub fn empty_canonical() -> Self {
        let bundles = [
            BundleName::Private, BundleName::Careful,
            BundleName::Fast, BundleName::Sovereign,
        ].into_iter().map(|b| BundleEntry {
            bundle: b,
            selectable: true,
            features: b.features().iter().map(|s| s.to_string()).collect(),
        }).collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            bundles,
            active: BundleName::Private,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), BundleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(BundleError::SchemaMismatch);
        }
        if self.bundles.len() != 4 {
            return Err(BundleError::CountInvalid(self.bundles.len()));
        }
        let required = [BundleName::Private, BundleName::Careful, BundleName::Fast, BundleName::Sovereign];
        for b in required {
            if !self.bundles.iter().any(|e| e.bundle == b) {
                return Err(BundleError::BundleMissing(b));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<BundleName> = HashSet::new();
        for e in &self.bundles {
            if !seen.insert(e.bundle) {
                return Err(BundleError::DuplicateBundle(e.bundle));
            }
            // Feature list must match canonical.
            let canonical: Vec<String> = e.bundle.features().iter().map(|s| s.to_string()).collect();
            if e.features != canonical {
                return Err(BundleError::FeatureMismatch { bundle: e.bundle });
            }
        }
        // Active must be selectable.
        let active_entry = self.bundles.iter().find(|e| e.bundle == self.active).unwrap();
        if !active_entry.selectable {
            return Err(BundleError::ActiveNotSelectable(self.active));
        }
        Ok(())
    }

    /// Switch active bundle.
    pub fn switch_active(&mut self, target: BundleName) -> Result<(), BundleError> {
        let target_entry = self.bundles.iter().find(|e| e.bundle == target)
            .ok_or(BundleError::BundleMissing(target))?;
        if !target_entry.selectable {
            return Err(BundleError::ActiveNotSelectable(target));
        }
        self.active = target;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn four_bundles_positioned_1_to_4() {
        for (b, p) in [
            (BundleName::Private, 1), (BundleName::Careful, 2),
            (BundleName::Fast, 3), (BundleName::Sovereign, 4),
        ] {
            assert_eq!(b.position(), p);
        }
    }

    #[test]
    fn private_features_verbatim() {
        let f = BundleName::Private.features();
        assert_eq!(f[0], "local models");
        assert_eq!(f[1], "no network");
        assert_eq!(f[2], "no cloud");
        assert_eq!(f[3], "sandbox tools");
    }

    #[test]
    fn careful_features_verbatim() {
        let f = BundleName::Careful.features();
        assert_eq!(f[0], "map first");
        assert_eq!(f[1], "spec required");
        assert_eq!(f[2], "tests required");
        assert_eq!(f[3], "oracle review");
    }

    #[test]
    fn fast_features_verbatim() {
        let f = BundleName::Fast.features();
        assert_eq!(f[0], "scout first");
        assert_eq!(f[1], "shallow map");
        assert_eq!(f[2], "minimal verification");
    }

    #[test]
    fn sovereign_features_verbatim() {
        let f = BundleName::Sovereign.features();
        assert_eq!(f[0], "user-visible gates");
        assert_eq!(f[1], "local memory ownership");
        assert_eq!(f[2], "explicit external calls");
        assert_eq!(f[3], "replay always on");
    }

    #[test]
    fn empty_canonical_validates() {
        BundleCatalog::empty_canonical().validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = BundleCatalog::empty_canonical();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), BundleError::SchemaMismatch));
    }

    #[test]
    fn count_invalid_caught() {
        let mut c = BundleCatalog::empty_canonical();
        c.bundles.pop();
        assert!(matches!(c.validate().unwrap_err(), BundleError::CountInvalid(3)));
    }

    #[test]
    fn switch_active_to_selectable() {
        let mut c = BundleCatalog::empty_canonical();
        c.switch_active(BundleName::Careful).unwrap();
        assert_eq!(c.active, BundleName::Careful);
    }

    #[test]
    fn switch_to_non_selectable_refused() {
        let mut c = BundleCatalog::empty_canonical();
        if let Some(e) = c.bundles.iter_mut().find(|e| e.bundle == BundleName::Fast) {
            e.selectable = false;
        }
        assert!(matches!(c.switch_active(BundleName::Fast).unwrap_err(), BundleError::ActiveNotSelectable(_)));
    }

    #[test]
    fn feature_mismatch_caught() {
        let mut c = BundleCatalog::empty_canonical();
        if let Some(e) = c.bundles.iter_mut().find(|e| e.bundle == BundleName::Private) {
            e.features[0] = "tampered".into();
        }
        match c.validate().unwrap_err() {
            BundleError::FeatureMismatch { bundle } => assert_eq!(bundle, BundleName::Private),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn bundle_serde_kebab() {
        assert_eq!(serde_json::to_string(&BundleName::Sovereign).unwrap(), "\"sovereign\"");
        assert_eq!(serde_json::to_string(&BundleName::Private).unwrap(), "\"private\"");
    }

    #[test]
    fn catalog_serde_roundtrip() {
        let c = BundleCatalog::empty_canonical();
        let j = serde_json::to_string(&c).unwrap();
        let back: BundleCatalog = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
