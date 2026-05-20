//! `sovereign-cockpit-widget-registry` — registry of cockpit widgets.
//!
//! Each widget has a stable `id`, a `kind` label (chart/text/meter/…),
//! a display `title`, an `enabled` flag, and minimum render-cell
//! dimensions. The registry exposes `register`, `enable`, `disable`,
//! `enabled_ids`, `visible_in(dashboard_id)` filters.
//!
//! Pure descriptor. Pairs with `sovereign-dashboard-layout` for
//! placement and `sovereign-dashboard-toggle` for global visibility.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One widget.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Widget {
    /// Stable id.
    pub id: String,
    /// Kind label.
    pub kind: String,
    /// Display title.
    pub title: String,
    /// Currently enabled?
    pub enabled: bool,
    /// Minimum grid columns.
    pub min_w: u32,
    /// Minimum grid rows.
    pub min_h: u32,
    /// Dashboards in which this widget may appear.
    pub allowed_in: BTreeSet<String>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WidgetRegistry {
    /// Schema version.
    pub schema_version: String,
    /// id → widget.
    pub widgets: BTreeMap<String, Widget>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RegistryError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("widget id empty")]
    EmptyId,
    /// Duplicate.
    #[error("duplicate widget id: {0}")]
    DuplicateId(String),
    /// Unknown widget.
    #[error("unknown widget: {0}")]
    UnknownWidget(String),
    /// Bad dims.
    #[error("min_w/min_h must be > 0")]
    BadDims,
}

impl WidgetRegistry {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            widgets: BTreeMap::new(),
        }
    }

    /// Register.
    pub fn register(&mut self, w: Widget) -> Result<(), RegistryError> {
        if w.id.is_empty() { return Err(RegistryError::EmptyId); }
        if w.min_w == 0 || w.min_h == 0 { return Err(RegistryError::BadDims); }
        if self.widgets.contains_key(&w.id) {
            return Err(RegistryError::DuplicateId(w.id));
        }
        self.widgets.insert(w.id.clone(), w);
        Ok(())
    }

    /// Enable.
    pub fn enable(&mut self, id: &str) -> Result<(), RegistryError> {
        let w = self.widgets.get_mut(id)
            .ok_or_else(|| RegistryError::UnknownWidget(id.into()))?;
        w.enabled = true;
        Ok(())
    }

    /// Disable.
    pub fn disable(&mut self, id: &str) -> Result<(), RegistryError> {
        let w = self.widgets.get_mut(id)
            .ok_or_else(|| RegistryError::UnknownWidget(id.into()))?;
        w.enabled = false;
        Ok(())
    }

    /// Allow a widget in a dashboard.
    pub fn allow_in(&mut self, id: &str, dashboard_id: &str) -> Result<(), RegistryError> {
        let w = self.widgets.get_mut(id)
            .ok_or_else(|| RegistryError::UnknownWidget(id.into()))?;
        w.allowed_in.insert(dashboard_id.into());
        Ok(())
    }

    /// Enabled ids.
    pub fn enabled_ids(&self) -> Vec<String> {
        self.widgets.values()
            .filter(|w| w.enabled)
            .map(|w| w.id.clone())
            .collect()
    }

    /// Visible in a particular dashboard (enabled AND allowed).
    pub fn visible_in(&self, dashboard_id: &str) -> Vec<Widget> {
        self.widgets.values()
            .filter(|w| w.enabled && w.allowed_in.contains(dashboard_id))
            .cloned()
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RegistryError> {
        if self.schema_version != SCHEMA_VERSION { return Err(RegistryError::SchemaMismatch); }
        for (id, w) in &self.widgets {
            if id.is_empty() { return Err(RegistryError::EmptyId); }
            if w.min_w == 0 || w.min_h == 0 { return Err(RegistryError::BadDims); }
        }
        Ok(())
    }
}

impl Default for WidgetRegistry {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn w(id: &str, kind: &str) -> Widget {
        Widget {
            id: id.into(),
            kind: kind.into(),
            title: id.into(),
            enabled: true,
            min_w: 2,
            min_h: 2,
            allowed_in: BTreeSet::new(),
        }
    }

    #[test]
    fn register_and_enabled() {
        let mut r = WidgetRegistry::new();
        r.register(w("cpu", "meter")).unwrap();
        assert_eq!(r.enabled_ids(), vec!["cpu"]);
    }

    #[test]
    fn duplicate_rejected() {
        let mut r = WidgetRegistry::new();
        r.register(w("cpu", "meter")).unwrap();
        assert!(matches!(r.register(w("cpu", "meter")).unwrap_err(), RegistryError::DuplicateId(_)));
    }

    #[test]
    fn enable_disable() {
        let mut r = WidgetRegistry::new();
        r.register(w("cpu", "meter")).unwrap();
        r.disable("cpu").unwrap();
        assert!(r.enabled_ids().is_empty());
        r.enable("cpu").unwrap();
        assert_eq!(r.enabled_ids(), vec!["cpu"]);
    }

    #[test]
    fn unknown_widget_rejected() {
        let mut r = WidgetRegistry::new();
        assert!(matches!(r.disable("nope").unwrap_err(), RegistryError::UnknownWidget(_)));
    }

    #[test]
    fn visible_in_dashboard() {
        let mut r = WidgetRegistry::new();
        r.register(w("cpu", "meter")).unwrap();
        r.allow_in("cpu", "main").unwrap();
        assert_eq!(r.visible_in("main").len(), 1);
        assert!(r.visible_in("other").is_empty());
    }

    #[test]
    fn disabled_widget_not_visible() {
        let mut r = WidgetRegistry::new();
        r.register(w("cpu", "meter")).unwrap();
        r.allow_in("cpu", "main").unwrap();
        r.disable("cpu").unwrap();
        assert!(r.visible_in("main").is_empty());
    }

    #[test]
    fn empty_id_rejected() {
        let mut r = WidgetRegistry::new();
        let mut bad = w("", "meter");
        bad.id = "".into();
        assert!(matches!(r.register(bad).unwrap_err(), RegistryError::EmptyId));
    }

    #[test]
    fn bad_dims_rejected() {
        let mut r = WidgetRegistry::new();
        let mut bad = w("cpu", "meter");
        bad.min_w = 0;
        assert!(matches!(r.register(bad).unwrap_err(), RegistryError::BadDims));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = WidgetRegistry::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), RegistryError::SchemaMismatch));
    }

    #[test]
    fn registry_serde_roundtrip() {
        let mut r = WidgetRegistry::new();
        r.register(w("cpu", "meter")).unwrap();
        r.allow_in("cpu", "main").unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: WidgetRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
