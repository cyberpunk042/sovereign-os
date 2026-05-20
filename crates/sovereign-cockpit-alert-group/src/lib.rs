//! `sovereign-cockpit-alert-group` — group alerts by tag.
//!
//! observe(alert) routes by tag, increments count, updates
//! latest_ts, and maxes severity. groups_by_severity() returns
//! groups sorted by max-severity desc, then latest_ts desc.
//! clear(tag) drops one group.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Severity.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Severity {
    /// Info.
    Info,
    /// Warning.
    Warning,
    /// Error.
    Error,
    /// Critical.
    Critical,
}

/// Group.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Group {
    /// Tag.
    pub tag: String,
    /// Count of alerts in group.
    pub count: u64,
    /// Highest severity observed.
    pub max_severity: Severity,
    /// Latest alert ts ms.
    pub latest_ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AlertGroup {
    /// Schema version.
    pub schema_version: String,
    /// tag → group.
    pub groups: BTreeMap<String, Group>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AlertError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("tag empty")]
    EmptyTag,
}

impl AlertGroup {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            groups: BTreeMap::new(),
        }
    }

    /// Observe an alert.
    pub fn observe(&mut self, tag: &str, severity: Severity, ts_ms: u64) -> Result<(), AlertError> {
        if tag.is_empty() { return Err(AlertError::EmptyTag); }
        let g = self.groups.entry(tag.into()).or_insert(Group {
            tag: tag.into(),
            count: 0,
            max_severity: severity,
            latest_ts_ms: ts_ms,
        });
        g.count = g.count.saturating_add(1);
        if severity > g.max_severity { g.max_severity = severity; }
        if ts_ms > g.latest_ts_ms { g.latest_ts_ms = ts_ms; }
        Ok(())
    }

    /// Clear a group.
    pub fn clear(&mut self, tag: &str) -> bool {
        self.groups.remove(tag).is_some()
    }

    /// Groups sorted by severity desc, then latest_ts desc.
    pub fn groups_by_severity(&self) -> Vec<&Group> {
        let mut out: Vec<&Group> = self.groups.values().collect();
        out.sort_by(|a, b| {
            b.max_severity.cmp(&a.max_severity)
                .then(b.latest_ts_ms.cmp(&a.latest_ts_ms))
        });
        out
    }

    /// Total alerts across all groups.
    pub fn total(&self) -> u64 {
        self.groups.values().map(|g| g.count).sum()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), AlertError> {
        if self.schema_version != SCHEMA_VERSION { return Err(AlertError::SchemaMismatch); }
        for k in self.groups.keys() {
            if k.is_empty() { return Err(AlertError::EmptyTag); }
        }
        Ok(())
    }
}

impl Default for AlertGroup {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn observe_creates_group() {
        let mut g = AlertGroup::new();
        g.observe("net", Severity::Warning, 100).unwrap();
        let groups = g.groups_by_severity();
        assert_eq!(groups.len(), 1);
        assert_eq!(groups[0].count, 1);
    }

    #[test]
    fn repeated_increments_count() {
        let mut g = AlertGroup::new();
        g.observe("net", Severity::Warning, 100).unwrap();
        g.observe("net", Severity::Error, 200).unwrap();
        let group = g.groups.get("net").unwrap();
        assert_eq!(group.count, 2);
        assert_eq!(group.max_severity, Severity::Error);
        assert_eq!(group.latest_ts_ms, 200);
    }

    #[test]
    fn sorted_by_severity_then_ts() {
        let mut g = AlertGroup::new();
        g.observe("net", Severity::Warning, 100).unwrap();
        g.observe("auth", Severity::Critical, 200).unwrap();
        g.observe("disk", Severity::Critical, 300).unwrap();
        let groups = g.groups_by_severity();
        assert_eq!(groups[0].tag, "disk"); // critical + newest
        assert_eq!(groups[1].tag, "auth");
        assert_eq!(groups[2].tag, "net");
    }

    #[test]
    fn clear_drops_group() {
        let mut g = AlertGroup::new();
        g.observe("net", Severity::Warning, 0).unwrap();
        assert!(g.clear("net"));
        assert!(!g.clear("net"));
        assert!(g.groups.is_empty());
    }

    #[test]
    fn total_sums() {
        let mut g = AlertGroup::new();
        g.observe("a", Severity::Info, 0).unwrap();
        g.observe("a", Severity::Info, 0).unwrap();
        g.observe("b", Severity::Info, 0).unwrap();
        assert_eq!(g.total(), 3);
    }

    #[test]
    fn empty_tag_rejected() {
        let mut g = AlertGroup::new();
        assert!(matches!(g.observe("", Severity::Info, 0).unwrap_err(), AlertError::EmptyTag));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = AlertGroup::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(g.validate().unwrap_err(), AlertError::SchemaMismatch));
    }

    #[test]
    fn group_serde_roundtrip() {
        let mut g = AlertGroup::new();
        g.observe("net", Severity::Warning, 100).unwrap();
        let j = serde_json::to_string(&g).unwrap();
        let back: AlertGroup = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
