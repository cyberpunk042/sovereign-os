//! `sovereign-cockpit-dashboard-profile` — dashboard preset profiles.
//!
//! Each preset is a named bundle of `(widget_allowlist, default_layout_id)`.
//! The cockpit chrome activates one at a time; toggling between presets
//! swaps which widgets are reachable in the toggle UI. `activate(id)`
//! swaps the active preset; `widget_enabled(widget_id)` reports
//! membership in the active set.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One preset.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Preset {
    /// Stable id (operator/engineer/security/trader/custom-<n>).
    pub id: String,
    /// Display title.
    pub title: String,
    /// Allowed widget ids.
    pub widget_allowlist: BTreeSet<String>,
    /// Default layout id to apply when this preset activates.
    pub default_layout_id: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DashboardProfile {
    /// Schema version.
    pub schema_version: String,
    /// id → preset.
    pub presets: BTreeMap<String, Preset>,
    /// Currently active.
    pub active: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ProfileError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate preset id: {0}")]
    DuplicateId(String),
    /// Unknown preset.
    #[error("unknown preset id: {0}")]
    UnknownPreset(String),
}

impl DashboardProfile {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            presets: BTreeMap::new(),
            active: None,
        }
    }

    /// Canonical defaults (4 personas).
    pub fn canonical() -> Self {
        let mut p = Self::new();
        p.register(Preset {
            id: "operator".into(),
            title: "Operator".into(),
            widget_allowlist: ["cpu", "memory", "disk", "network", "alerts", "tasks"]
                .into_iter()
                .map(String::from)
                .collect(),
            default_layout_id: "operator-default".into(),
        })
        .unwrap();
        p.register(Preset {
            id: "engineer".into(),
            title: "Engineer".into(),
            widget_allowlist: [
                "cpu",
                "memory",
                "gpu",
                "logs",
                "build-status",
                "deploy-status",
                "tests-status",
            ]
            .into_iter()
            .map(String::from)
            .collect(),
            default_layout_id: "engineer-default".into(),
        })
        .unwrap();
        p.register(Preset {
            id: "security".into(),
            title: "Security".into(),
            widget_allowlist: [
                "alerts",
                "auth-events",
                "policy-violations",
                "audit-log",
                "actor-trust",
                "quarantine",
            ]
            .into_iter()
            .map(String::from)
            .collect(),
            default_layout_id: "security-default".into(),
        })
        .unwrap();
        p.register(Preset {
            id: "trader".into(),
            title: "Trader".into(),
            widget_allowlist: [
                "price-ticker",
                "depth-of-book",
                "positions",
                "p&l",
                "alerts",
                "watchlist",
            ]
            .into_iter()
            .map(String::from)
            .collect(),
            default_layout_id: "trader-default".into(),
        })
        .unwrap();
        p.active = Some("operator".into());
        p
    }

    /// Register or replace.
    pub fn register(&mut self, preset: Preset) -> Result<(), ProfileError> {
        if preset.id.is_empty() {
            return Err(ProfileError::EmptyId);
        }
        self.presets.insert(preset.id.clone(), preset);
        Ok(())
    }

    /// Register, rejecting duplicates explicitly.
    pub fn register_unique(&mut self, preset: Preset) -> Result<(), ProfileError> {
        if preset.id.is_empty() {
            return Err(ProfileError::EmptyId);
        }
        if self.presets.contains_key(&preset.id) {
            return Err(ProfileError::DuplicateId(preset.id));
        }
        self.presets.insert(preset.id.clone(), preset);
        Ok(())
    }

    /// Activate.
    pub fn activate(&mut self, id: &str) -> Result<(), ProfileError> {
        if !self.presets.contains_key(id) {
            return Err(ProfileError::UnknownPreset(id.into()));
        }
        self.active = Some(id.into());
        Ok(())
    }

    /// Currently active.
    pub fn active(&self) -> Option<&Preset> {
        self.active.as_deref().and_then(|id| self.presets.get(id))
    }

    /// Is the widget enabled in the active preset?
    pub fn widget_enabled(&self, widget_id: &str) -> bool {
        match self.active() {
            Some(p) => p.widget_allowlist.contains(widget_id),
            None => false,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ProfileError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ProfileError::SchemaMismatch);
        }
        for id in self.presets.keys() {
            if id.is_empty() {
                return Err(ProfileError::EmptyId);
            }
        }
        if let Some(a) = &self.active
            && !self.presets.contains_key(a)
        {
            return Err(ProfileError::UnknownPreset(a.clone()));
        }
        Ok(())
    }
}

impl Default for DashboardProfile {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        DashboardProfile::canonical().validate().unwrap();
    }

    #[test]
    fn canonical_starts_on_operator() {
        let p = DashboardProfile::canonical();
        assert_eq!(p.active.as_deref(), Some("operator"));
        assert!(p.widget_enabled("cpu"));
        assert!(!p.widget_enabled("price-ticker"));
    }

    #[test]
    fn activate_changes_active() {
        let mut p = DashboardProfile::canonical();
        p.activate("trader").unwrap();
        assert!(p.widget_enabled("price-ticker"));
        assert!(!p.widget_enabled("policy-violations"));
    }

    #[test]
    fn unknown_preset_rejected() {
        let mut p = DashboardProfile::canonical();
        assert!(matches!(
            p.activate("nope").unwrap_err(),
            ProfileError::UnknownPreset(_)
        ));
    }

    #[test]
    fn register_unique_dedups() {
        let mut p = DashboardProfile::canonical();
        let dup = Preset {
            id: "operator".into(),
            title: "x".into(),
            widget_allowlist: BTreeSet::new(),
            default_layout_id: "x".into(),
        };
        assert!(matches!(
            p.register_unique(dup).unwrap_err(),
            ProfileError::DuplicateId(_)
        ));
    }

    #[test]
    fn register_replaces() {
        let mut p = DashboardProfile::canonical();
        let custom = Preset {
            id: "custom-1".into(),
            title: "Custom".into(),
            widget_allowlist: BTreeSet::new(),
            default_layout_id: "blank".into(),
        };
        p.register(custom.clone()).unwrap();
        // re-register overwrites without error.
        p.register(custom).unwrap();
    }

    #[test]
    fn empty_id_rejected() {
        let mut p = DashboardProfile::new();
        let bad = Preset {
            id: "".into(),
            title: "x".into(),
            widget_allowlist: BTreeSet::new(),
            default_layout_id: "x".into(),
        };
        assert!(matches!(
            p.register(bad).unwrap_err(),
            ProfileError::EmptyId
        ));
    }

    #[test]
    fn widget_enabled_when_no_active() {
        let p = DashboardProfile::new();
        assert!(!p.widget_enabled("cpu"));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = DashboardProfile::canonical();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            ProfileError::SchemaMismatch
        ));
    }

    #[test]
    fn profile_serde_roundtrip() {
        let p = DashboardProfile::canonical();
        let j = serde_json::to_string(&p).unwrap();
        let back: DashboardProfile = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
