//! `sovereign-routing-preference` — per-bundle router weights.
//!
//! 5 weighted preferences (0..=100) per bundle:
//! - `prefer_local`   — favor local providers
//! - `prefer_fast`    — favor low-latency
//! - `prefer_cheap`   — favor low-cost
//! - `prefer_quality` — favor flagship reasoning
//! - `prefer_privacy` — favor providers with no-log policy
//!
//! The sum is unconstrained; router normalizes at decision time.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_profile_bundles::BundleName;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Weight tuple.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Weights {
    /// Prefer local providers.
    pub prefer_local: u8,
    /// Prefer fast (low-latency) providers.
    pub prefer_fast: u8,
    /// Prefer cheap providers.
    pub prefer_cheap: u8,
    /// Prefer quality providers.
    pub prefer_quality: u8,
    /// Prefer privacy.
    pub prefer_privacy: u8,
}

/// Per-bundle preference row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BundlePreference {
    /// Bundle.
    pub bundle: BundleName,
    /// Weights.
    pub weights: Weights,
}

/// Preferences envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RoutingPreferences {
    /// Schema version.
    pub schema_version: String,
    /// 4 bundle rows.
    pub rows: Vec<BundlePreference>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PreferenceError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 4.
    #[error("preference count {0} != 4 canonical")]
    CountInvalid(usize),
    /// Missing.
    #[error("missing bundle: {0:?}")]
    Missing(BundleName),
    /// Weight > 100.
    #[error("bundle {bundle:?} weight {field} out of 0..=100: {value}")]
    OutOfRange {
        /// bundle.
        bundle: BundleName,
        /// field.
        field: &'static str,
        /// value.
        value: u8,
    },
    /// All weights zero (no preference).
    #[error("bundle {0:?} has zero total weight")]
    AllZero(BundleName),
}

const REQUIRED: [BundleName; 4] = [BundleName::Private, BundleName::Careful, BundleName::Fast, BundleName::Sovereign];

impl RoutingPreferences {
    /// Canonical defaults — operator-tuned per-bundle weights.
    pub fn canonical() -> Self {
        let rows = vec![
            BundlePreference {
                bundle: BundleName::Private,
                weights: Weights { prefer_local: 100, prefer_fast: 30, prefer_cheap: 50, prefer_quality: 20, prefer_privacy: 100 },
            },
            BundlePreference {
                bundle: BundleName::Careful,
                weights: Weights { prefer_local: 60, prefer_fast: 40, prefer_cheap: 50, prefer_quality: 60, prefer_privacy: 40 },
            },
            BundlePreference {
                bundle: BundleName::Fast,
                weights: Weights { prefer_local: 30, prefer_fast: 100, prefer_cheap: 40, prefer_quality: 50, prefer_privacy: 20 },
            },
            BundlePreference {
                bundle: BundleName::Sovereign,
                weights: Weights { prefer_local: 70, prefer_fast: 50, prefer_cheap: 30, prefer_quality: 80, prefer_privacy: 60 },
            },
        ];
        Self {
            schema_version: SCHEMA_VERSION.into(),
            rows,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PreferenceError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PreferenceError::SchemaMismatch);
        }
        if self.rows.len() != 4 {
            return Err(PreferenceError::CountInvalid(self.rows.len()));
        }
        for b in REQUIRED {
            if !self.rows.iter().any(|r| r.bundle == b) {
                return Err(PreferenceError::Missing(b));
            }
        }
        for r in &self.rows {
            let w = &r.weights;
            if w.prefer_local > 100 { return Err(PreferenceError::OutOfRange { bundle: r.bundle, field: "prefer_local", value: w.prefer_local }); }
            if w.prefer_fast > 100 { return Err(PreferenceError::OutOfRange { bundle: r.bundle, field: "prefer_fast", value: w.prefer_fast }); }
            if w.prefer_cheap > 100 { return Err(PreferenceError::OutOfRange { bundle: r.bundle, field: "prefer_cheap", value: w.prefer_cheap }); }
            if w.prefer_quality > 100 { return Err(PreferenceError::OutOfRange { bundle: r.bundle, field: "prefer_quality", value: w.prefer_quality }); }
            if w.prefer_privacy > 100 { return Err(PreferenceError::OutOfRange { bundle: r.bundle, field: "prefer_privacy", value: w.prefer_privacy }); }
            let total: u32 = w.prefer_local as u32 + w.prefer_fast as u32 + w.prefer_cheap as u32 + w.prefer_quality as u32 + w.prefer_privacy as u32;
            if total == 0 {
                return Err(PreferenceError::AllZero(r.bundle));
            }
        }
        Ok(())
    }

    /// Lookup by bundle.
    pub fn get(&self, bundle: BundleName) -> Option<&Weights> {
        self.rows.iter().find(|r| r.bundle == bundle).map(|r| &r.weights)
    }

    /// Sum of all weights for a bundle (used by router for normalization).
    pub fn weight_total(&self, bundle: BundleName) -> u32 {
        match self.get(bundle) {
            Some(w) => w.prefer_local as u32 + w.prefer_fast as u32 + w.prefer_cheap as u32 + w.prefer_quality as u32 + w.prefer_privacy as u32,
            None => 0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        RoutingPreferences::canonical().validate().unwrap();
    }

    #[test]
    fn four_bundles_present() {
        let p = RoutingPreferences::canonical();
        for b in REQUIRED {
            assert!(p.get(b).is_some(), "missing {b:?}");
        }
    }

    #[test]
    fn private_max_local_and_privacy() {
        let p = RoutingPreferences::canonical();
        let w = p.get(BundleName::Private).unwrap();
        assert_eq!(w.prefer_local, 100);
        assert_eq!(w.prefer_privacy, 100);
    }

    #[test]
    fn fast_max_fast() {
        let p = RoutingPreferences::canonical();
        let w = p.get(BundleName::Fast).unwrap();
        assert_eq!(w.prefer_fast, 100);
    }

    #[test]
    fn weight_total_positive() {
        let p = RoutingPreferences::canonical();
        for b in REQUIRED {
            assert!(p.weight_total(b) > 0);
        }
    }

    #[test]
    fn out_of_range_caught() {
        let mut p = RoutingPreferences::canonical();
        p.rows[0].weights.prefer_local = 200;
        assert!(matches!(p.validate().unwrap_err(), PreferenceError::OutOfRange { .. }));
    }

    #[test]
    fn all_zero_caught() {
        let mut p = RoutingPreferences::canonical();
        p.rows[0].weights = Weights { prefer_local: 0, prefer_fast: 0, prefer_cheap: 0, prefer_quality: 0, prefer_privacy: 0 };
        match p.validate().unwrap_err() {
            PreferenceError::AllZero(b) => assert_eq!(b, p.rows[0].bundle),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = RoutingPreferences::canonical();
        p.schema_version = "9.9.9".into();
        assert!(matches!(p.validate().unwrap_err(), PreferenceError::SchemaMismatch));
    }

    #[test]
    fn count_invalid_caught() {
        let mut p = RoutingPreferences::canonical();
        p.rows.pop();
        assert!(matches!(p.validate().unwrap_err(), PreferenceError::CountInvalid(3)));
    }

    #[test]
    fn preferences_serde_roundtrip() {
        let p = RoutingPreferences::canonical();
        let j = serde_json::to_string(&p).unwrap();
        let back: RoutingPreferences = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
