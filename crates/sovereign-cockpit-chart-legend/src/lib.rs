//! `sovereign-cockpit-chart-legend` — series visibility + hover.
//!
//! Series{id, label, color, visible}. `toggle(id)` flips visibility,
//! `solo(id)` hides all but the named series, `show_all()` brings
//! everything back. `hover(id)/unhover()` track the hovered series
//! id (None = no hover).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One series.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Series {
    /// Stable id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Color (hex / token / etc).
    pub color: String,
    /// Visible?
    pub visible: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChartLegend {
    /// Schema version.
    pub schema_version: String,
    /// Series in render order.
    pub series: Vec<Series>,
    /// Currently hovered id.
    pub hovered: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LegendError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("series id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate series id: {0}")]
    DuplicateId(String),
    /// Unknown id.
    #[error("unknown series id: {0}")]
    UnknownId(String),
}

impl ChartLegend {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            series: Vec::new(),
            hovered: None,
        }
    }

    /// Add.
    pub fn add(&mut self, s: Series) -> Result<(), LegendError> {
        if s.id.is_empty() { return Err(LegendError::EmptyId); }
        if self.series.iter().any(|x| x.id == s.id) {
            return Err(LegendError::DuplicateId(s.id));
        }
        self.series.push(s);
        Ok(())
    }

    /// Toggle visibility.
    pub fn toggle(&mut self, id: &str) -> Result<(), LegendError> {
        let s = self.series.iter_mut().find(|x| x.id == id)
            .ok_or_else(|| LegendError::UnknownId(id.into()))?;
        s.visible = !s.visible;
        Ok(())
    }

    /// Solo (only `id` visible, all others hidden).
    pub fn solo(&mut self, id: &str) -> Result<(), LegendError> {
        if !self.series.iter().any(|x| x.id == id) {
            return Err(LegendError::UnknownId(id.into()));
        }
        for s in self.series.iter_mut() {
            s.visible = s.id == id;
        }
        Ok(())
    }

    /// Show all.
    pub fn show_all(&mut self) {
        for s in self.series.iter_mut() { s.visible = true; }
    }

    /// Hover.
    pub fn hover(&mut self, id: &str) -> Result<(), LegendError> {
        if !self.series.iter().any(|x| x.id == id) {
            return Err(LegendError::UnknownId(id.into()));
        }
        self.hovered = Some(id.into());
        Ok(())
    }

    /// Unhover.
    pub fn unhover(&mut self) { self.hovered = None; }

    /// Visible series.
    pub fn visible_series(&self) -> Vec<Series> {
        self.series.iter().filter(|s| s.visible).cloned().collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LegendError> {
        if self.schema_version != SCHEMA_VERSION { return Err(LegendError::SchemaMismatch); }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for s in &self.series {
            if s.id.is_empty() { return Err(LegendError::EmptyId); }
            if !seen.insert(s.id.as_str()) {
                return Err(LegendError::DuplicateId(s.id.clone()));
            }
        }
        Ok(())
    }
}

impl Default for ChartLegend {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(id: &str) -> Series { Series { id: id.into(), label: id.into(), color: "#000".into(), visible: true } }

    #[test]
    fn add_and_visible() {
        let mut l = ChartLegend::new();
        l.add(s("a")).unwrap();
        l.add(s("b")).unwrap();
        assert_eq!(l.visible_series().len(), 2);
    }

    #[test]
    fn duplicate_rejected() {
        let mut l = ChartLegend::new();
        l.add(s("a")).unwrap();
        assert!(matches!(l.add(s("a")).unwrap_err(), LegendError::DuplicateId(_)));
    }

    #[test]
    fn toggle_flips() {
        let mut l = ChartLegend::new();
        l.add(s("a")).unwrap();
        l.toggle("a").unwrap();
        assert!(l.visible_series().is_empty());
        l.toggle("a").unwrap();
        assert_eq!(l.visible_series().len(), 1);
    }

    #[test]
    fn solo_isolates() {
        let mut l = ChartLegend::new();
        l.add(s("a")).unwrap();
        l.add(s("b")).unwrap();
        l.add(s("c")).unwrap();
        l.solo("b").unwrap();
        let v = l.visible_series();
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].id, "b");
    }

    #[test]
    fn show_all_restores() {
        let mut l = ChartLegend::new();
        l.add(s("a")).unwrap();
        l.add(s("b")).unwrap();
        l.solo("a").unwrap();
        l.show_all();
        assert_eq!(l.visible_series().len(), 2);
    }

    #[test]
    fn hover_unhover() {
        let mut l = ChartLegend::new();
        l.add(s("a")).unwrap();
        l.hover("a").unwrap();
        assert_eq!(l.hovered.as_deref(), Some("a"));
        l.unhover();
        assert!(l.hovered.is_none());
    }

    #[test]
    fn unknown_id_rejected() {
        let mut l = ChartLegend::new();
        assert!(matches!(l.toggle("nope").unwrap_err(), LegendError::UnknownId(_)));
        assert!(matches!(l.solo("nope").unwrap_err(), LegendError::UnknownId(_)));
        assert!(matches!(l.hover("nope").unwrap_err(), LegendError::UnknownId(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = ChartLegend::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), LegendError::SchemaMismatch));
    }

    #[test]
    fn legend_serde_roundtrip() {
        let mut l = ChartLegend::new();
        l.add(s("a")).unwrap();
        l.add(s("b")).unwrap();
        l.solo("a").unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: ChartLegend = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
