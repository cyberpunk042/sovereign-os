//! `sovereign-cockpit-feature-toggle-grid` — settings-UI toggle grid.
//!
//! Each toggle has `(id, label, hint, group, on, disabled_reason)`.
//! `toggle(id)` flips the `on` flag unless `disabled_reason` is set.
//! `disable(id, reason)` locks the toggle off with a visible reason.
//! `clear_disable(id)` unlocks. `visible_by_group()` partitions
//! visible entries by `group` so the settings UI can render them
//! as labeled sections.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One toggle.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Toggle {
    /// Stable id.
    pub id: String,
    /// Operator-visible label.
    pub label: String,
    /// Hint line shown under the label.
    pub hint: String,
    /// Group section.
    pub group: String,
    /// Currently on?
    pub on: bool,
    /// If set, toggle is disabled with this reason.
    pub disabled_reason: Option<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FeatureToggleGrid {
    /// Schema version.
    pub schema_version: String,
    /// id → toggle.
    pub toggles: BTreeMap<String, Toggle>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GridError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("toggle id empty")]
    EmptyId,
    /// Duplicate.
    #[error("duplicate toggle id: {0}")]
    DuplicateId(String),
    /// Unknown.
    #[error("unknown toggle id: {0}")]
    UnknownId(String),
    /// Toggle is disabled.
    #[error("toggle {0} is disabled: {1}")]
    Disabled(String, String),
}

impl FeatureToggleGrid {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            toggles: BTreeMap::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, t: Toggle) -> Result<(), GridError> {
        if t.id.is_empty() { return Err(GridError::EmptyId); }
        if self.toggles.contains_key(&t.id) {
            return Err(GridError::DuplicateId(t.id));
        }
        self.toggles.insert(t.id.clone(), t);
        Ok(())
    }

    /// Toggle.
    pub fn toggle(&mut self, id: &str) -> Result<bool, GridError> {
        let t = self.toggles.get_mut(id).ok_or_else(|| GridError::UnknownId(id.into()))?;
        if let Some(r) = &t.disabled_reason {
            return Err(GridError::Disabled(id.into(), r.clone()));
        }
        t.on = !t.on;
        Ok(t.on)
    }

    /// Disable with reason.
    pub fn disable(&mut self, id: &str, reason: &str) -> Result<(), GridError> {
        let t = self.toggles.get_mut(id).ok_or_else(|| GridError::UnknownId(id.into()))?;
        t.disabled_reason = Some(reason.into());
        Ok(())
    }

    /// Clear disable.
    pub fn clear_disable(&mut self, id: &str) -> Result<(), GridError> {
        let t = self.toggles.get_mut(id).ok_or_else(|| GridError::UnknownId(id.into()))?;
        t.disabled_reason = None;
        Ok(())
    }

    /// Group → ordered toggles.
    pub fn visible_by_group(&self) -> BTreeMap<String, Vec<Toggle>> {
        let mut out: BTreeMap<String, Vec<Toggle>> = BTreeMap::new();
        for t in self.toggles.values() {
            out.entry(t.group.clone()).or_default().push(t.clone());
        }
        for v in out.values_mut() {
            v.sort_by(|a, b| a.label.cmp(&b.label));
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GridError> {
        if self.schema_version != SCHEMA_VERSION { return Err(GridError::SchemaMismatch); }
        for (id, _) in &self.toggles {
            if id.is_empty() { return Err(GridError::EmptyId); }
        }
        Ok(())
    }
}

impl Default for FeatureToggleGrid {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(id: &str, group: &str, on: bool) -> Toggle {
        Toggle {
            id: id.into(),
            label: id.into(),
            hint: "".into(),
            group: group.into(),
            on,
            disabled_reason: None,
        }
    }

    #[test]
    fn register_and_toggle() {
        let mut g = FeatureToggleGrid::new();
        g.register(t("dark", "Appearance", false)).unwrap();
        assert!(g.toggle("dark").unwrap());
        assert!(!g.toggle("dark").unwrap());
    }

    #[test]
    fn duplicate_rejected() {
        let mut g = FeatureToggleGrid::new();
        g.register(t("dark", "x", false)).unwrap();
        assert!(matches!(g.register(t("dark", "y", true)).unwrap_err(), GridError::DuplicateId(_)));
    }

    #[test]
    fn disabled_toggle_rejects() {
        let mut g = FeatureToggleGrid::new();
        g.register(t("dark", "x", false)).unwrap();
        g.disable("dark", "policy: light only").unwrap();
        assert!(matches!(g.toggle("dark").unwrap_err(), GridError::Disabled(_, _)));
    }

    #[test]
    fn clear_disable_reenables() {
        let mut g = FeatureToggleGrid::new();
        g.register(t("dark", "x", false)).unwrap();
        g.disable("dark", "policy").unwrap();
        g.clear_disable("dark").unwrap();
        assert!(g.toggle("dark").is_ok());
    }

    #[test]
    fn group_partitioning() {
        let mut g = FeatureToggleGrid::new();
        g.register(t("dark", "Appearance", false)).unwrap();
        g.register(t("animations", "Appearance", true)).unwrap();
        g.register(t("dnd", "Notifications", false)).unwrap();
        let by_group = g.visible_by_group();
        assert_eq!(by_group["Appearance"].len(), 2);
        assert_eq!(by_group["Notifications"].len(), 1);
    }

    #[test]
    fn group_sorted_by_label() {
        let mut g = FeatureToggleGrid::new();
        g.register(t("z", "Appearance", false)).unwrap();
        g.register(t("a", "Appearance", false)).unwrap();
        let by_group = g.visible_by_group();
        let labels: Vec<_> = by_group["Appearance"].iter().map(|t| t.label.clone()).collect();
        assert_eq!(labels, vec!["a", "z"]);
    }

    #[test]
    fn unknown_id() {
        let mut g = FeatureToggleGrid::new();
        assert!(matches!(g.toggle("nope").unwrap_err(), GridError::UnknownId(_)));
    }

    #[test]
    fn empty_id_rejected() {
        let mut g = FeatureToggleGrid::new();
        assert!(matches!(g.register(t("", "x", false)).unwrap_err(), GridError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = FeatureToggleGrid::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(g.validate().unwrap_err(), GridError::SchemaMismatch));
    }

    #[test]
    fn grid_serde_roundtrip() {
        let mut g = FeatureToggleGrid::new();
        g.register(t("dark", "Appearance", true)).unwrap();
        g.disable("dark", "policy").unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: FeatureToggleGrid = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
