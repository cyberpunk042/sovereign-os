//! `sovereign-cockpit-gutter-marker-set` — code gutter markers.
//!
//! Per editor pane id, the cockpit tracks gutter markers by line
//! number. Each marker is `Marker { kind, label, severity }`. A
//! line can hold multiple markers; `at(pane, line)` returns them in
//! a stable order (kind alphabetical). `top_marker(pane, line)`
//! returns the visually-dominant one ranked by severity, with the
//! kind name breaking ties.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity (higher = more prominent).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Info.
    Info,
    /// Notice.
    Notice,
    /// Warn.
    Warn,
    /// Error.
    Error,
    /// Critical (e.g. breakpoint).
    Critical,
}

/// One marker.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Marker {
    /// Marker kind label.
    pub kind: String,
    /// Hover label.
    pub label: String,
    /// Severity.
    pub severity: Severity,
}

/// Per-pane markers keyed by line.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct PaneMarkers {
    /// line → markers.
    pub lines: BTreeMap<u64, Vec<Marker>>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GutterMarkerSet {
    /// Schema version.
    pub schema_version: String,
    /// pane id → markers.
    pub panes: BTreeMap<String, PaneMarkers>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GutterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty pane id.
    #[error("pane id empty")]
    EmptyPane,
    /// Empty kind.
    #[error("kind empty")]
    EmptyKind,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
    /// Zero line.
    #[error("line must be >= 1")]
    ZeroLine,
}

impl GutterMarkerSet {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            panes: BTreeMap::new(),
        }
    }

    /// Add.
    pub fn add(&mut self, pane: &str, line: u64, marker: Marker) -> Result<(), GutterError> {
        if pane.is_empty() { return Err(GutterError::EmptyPane); }
        if line == 0 { return Err(GutterError::ZeroLine); }
        if marker.kind.is_empty() { return Err(GutterError::EmptyKind); }
        if marker.label.is_empty() { return Err(GutterError::EmptyLabel); }
        let p = self.panes.entry(pane.into()).or_default();
        let entry = p.lines.entry(line).or_default();
        entry.push(marker);
        entry.sort_by(|a, b| a.kind.cmp(&b.kind));
        Ok(())
    }

    /// Remove all markers of a kind on a line (returns count removed).
    pub fn remove_kind(&mut self, pane: &str, line: u64, kind: &str) -> u32 {
        let Some(p) = self.panes.get_mut(pane) else { return 0; };
        let Some(entry) = p.lines.get_mut(&line) else { return 0; };
        let before = entry.len();
        entry.retain(|m| m.kind != kind);
        let removed = (before - entry.len()) as u32;
        if entry.is_empty() { p.lines.remove(&line); }
        if p.lines.is_empty() { self.panes.remove(pane); }
        removed
    }

    /// Markers at line.
    pub fn at(&self, pane: &str, line: u64) -> Vec<Marker> {
        self.panes.get(pane)
            .and_then(|p| p.lines.get(&line))
            .cloned()
            .unwrap_or_default()
    }

    /// Top marker by severity (then kind).
    pub fn top_marker(&self, pane: &str, line: u64) -> Option<Marker> {
        let v = self.at(pane, line);
        v.into_iter()
            .max_by(|a, b| a.severity.cmp(&b.severity).then(b.kind.cmp(&a.kind)))
    }

    /// All lines (sorted) in a pane with at least one marker.
    pub fn marked_lines(&self, pane: &str) -> Vec<u64> {
        self.panes.get(pane).map(|p| p.lines.keys().copied().collect()).unwrap_or_default()
    }

    /// Clear all markers on a pane.
    pub fn clear_pane(&mut self, pane: &str) -> bool {
        self.panes.remove(pane).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GutterError> {
        if self.schema_version != SCHEMA_VERSION { return Err(GutterError::SchemaMismatch); }
        for (p, panes) in &self.panes {
            if p.is_empty() { return Err(GutterError::EmptyPane); }
            for (l, ms) in &panes.lines {
                if *l == 0 { return Err(GutterError::ZeroLine); }
                for m in ms {
                    if m.kind.is_empty() { return Err(GutterError::EmptyKind); }
                    if m.label.is_empty() { return Err(GutterError::EmptyLabel); }
                }
            }
        }
        Ok(())
    }
}

impl Default for GutterMarkerSet {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn m(kind: &str, sev: Severity) -> Marker {
        Marker { kind: kind.into(), label: format!("{kind} here"), severity: sev }
    }

    #[test]
    fn add_and_query() {
        let mut g = GutterMarkerSet::new();
        g.add("pane1", 10, m("breakpoint", Severity::Critical)).unwrap();
        let v = g.at("pane1", 10);
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].kind, "breakpoint");
    }

    #[test]
    fn multiple_markers_sorted() {
        let mut g = GutterMarkerSet::new();
        g.add("p", 5, m("warning", Severity::Warn)).unwrap();
        g.add("p", 5, m("breakpoint", Severity::Critical)).unwrap();
        let v = g.at("p", 5);
        // Alphabetical by kind.
        assert_eq!(v[0].kind, "breakpoint");
        assert_eq!(v[1].kind, "warning");
    }

    #[test]
    fn top_marker_by_severity() {
        let mut g = GutterMarkerSet::new();
        g.add("p", 5, m("info", Severity::Info)).unwrap();
        g.add("p", 5, m("error", Severity::Error)).unwrap();
        let t = g.top_marker("p", 5).unwrap();
        assert_eq!(t.kind, "error");
    }

    #[test]
    fn remove_kind_deletes_only_that() {
        let mut g = GutterMarkerSet::new();
        g.add("p", 5, m("warn1", Severity::Warn)).unwrap();
        g.add("p", 5, m("warn2", Severity::Warn)).unwrap();
        let r = g.remove_kind("p", 5, "warn1");
        assert_eq!(r, 1);
        assert_eq!(g.at("p", 5).len(), 1);
    }

    #[test]
    fn remove_last_marker_drops_line() {
        let mut g = GutterMarkerSet::new();
        g.add("p", 5, m("k", Severity::Info)).unwrap();
        g.remove_kind("p", 5, "k");
        assert!(g.marked_lines("p").is_empty());
    }

    #[test]
    fn marked_lines_sorted() {
        let mut g = GutterMarkerSet::new();
        g.add("p", 30, m("a", Severity::Info)).unwrap();
        g.add("p", 10, m("a", Severity::Info)).unwrap();
        g.add("p", 20, m("a", Severity::Info)).unwrap();
        assert_eq!(g.marked_lines("p"), vec![10, 20, 30]);
    }

    #[test]
    fn clear_pane() {
        let mut g = GutterMarkerSet::new();
        g.add("p", 1, m("a", Severity::Info)).unwrap();
        assert!(g.clear_pane("p"));
        assert!(g.marked_lines("p").is_empty());
    }

    #[test]
    fn zero_line_rejected() {
        let mut g = GutterMarkerSet::new();
        assert!(matches!(g.add("p", 0, m("a", Severity::Info)).unwrap_err(), GutterError::ZeroLine));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut g = GutterMarkerSet::new();
        assert!(matches!(g.add("", 1, m("a", Severity::Info)).unwrap_err(), GutterError::EmptyPane));
        assert!(matches!(g.add("p", 1, Marker { kind: "".into(), label: "x".into(), severity: Severity::Info }).unwrap_err(), GutterError::EmptyKind));
        assert!(matches!(g.add("p", 1, Marker { kind: "k".into(), label: "".into(), severity: Severity::Info }).unwrap_err(), GutterError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = GutterMarkerSet::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(g.validate().unwrap_err(), GutterError::SchemaMismatch));
    }

    #[test]
    fn gutter_serde_roundtrip() {
        let mut g = GutterMarkerSet::new();
        g.add("p", 5, m("k", Severity::Error)).unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: GutterMarkerSet = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
