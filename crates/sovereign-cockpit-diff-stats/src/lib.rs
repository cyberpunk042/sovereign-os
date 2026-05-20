//! `sovereign-cockpit-diff-stats` — per-file diff counters.
//!
//! Per file: added, removed lines. record(path, added, removed)
//! overwrites that path's counts. total returns the sum across
//! all files. files() lists tracked paths sorted by total churn
//! desc.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-file stats.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct FileStat {
    /// Added lines.
    pub added: u64,
    /// Removed lines.
    pub removed: u64,
}

impl FileStat {
    /// Churn (added + removed).
    pub fn churn(&self) -> u64 { self.added.saturating_add(self.removed) }
}

/// Grand total.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct Totals {
    /// Files touched.
    pub files: u32,
    /// Added.
    pub added: u64,
    /// Removed.
    pub removed: u64,
    /// Churn.
    pub churn: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DiffStats {
    /// Schema version.
    pub schema_version: String,
    /// path → stat.
    pub by_path: BTreeMap<String, FileStat>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DiffError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("path empty")]
    EmptyPath,
}

impl DiffStats {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            by_path: BTreeMap::new(),
        }
    }

    /// Record (replaces).
    pub fn record(&mut self, path: &str, added: u64, removed: u64) -> Result<(), DiffError> {
        if path.is_empty() { return Err(DiffError::EmptyPath); }
        self.by_path.insert(path.into(), FileStat { added, removed });
        Ok(())
    }

    /// Remove a file's record.
    pub fn forget(&mut self, path: &str) -> bool {
        self.by_path.remove(path).is_some()
    }

    /// Totals.
    pub fn totals(&self) -> Totals {
        let mut added: u64 = 0;
        let mut removed: u64 = 0;
        for fs in self.by_path.values() {
            added = added.saturating_add(fs.added);
            removed = removed.saturating_add(fs.removed);
        }
        Totals {
            files: self.by_path.len() as u32,
            added,
            removed,
            churn: added.saturating_add(removed),
        }
    }

    /// Files sorted by churn descending, tie-break by path asc.
    pub fn files_by_churn(&self) -> Vec<&str> {
        let mut all: Vec<(&str, u64)> = self.by_path.iter()
            .map(|(k, v)| (k.as_str(), v.churn()))
            .collect();
        all.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));
        all.into_iter().map(|(k, _)| k).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DiffError> {
        if self.schema_version != SCHEMA_VERSION { return Err(DiffError::SchemaMismatch); }
        for k in self.by_path.keys() {
            if k.is_empty() { return Err(DiffError::EmptyPath); }
        }
        Ok(())
    }
}

impl Default for DiffStats {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_and_total() {
        let mut s = DiffStats::new();
        s.record("a.rs", 10, 2).unwrap();
        s.record("b.rs", 5, 1).unwrap();
        let t = s.totals();
        assert_eq!(t.files, 2);
        assert_eq!(t.added, 15);
        assert_eq!(t.removed, 3);
        assert_eq!(t.churn, 18);
    }

    #[test]
    fn record_replaces() {
        let mut s = DiffStats::new();
        s.record("a.rs", 10, 2).unwrap();
        s.record("a.rs", 1, 0).unwrap();
        let t = s.totals();
        assert_eq!(t.added, 1);
    }

    #[test]
    fn forget() {
        let mut s = DiffStats::new();
        s.record("a.rs", 1, 1).unwrap();
        assert!(s.forget("a.rs"));
        assert_eq!(s.totals().files, 0);
    }

    #[test]
    fn files_by_churn_orders() {
        let mut s = DiffStats::new();
        s.record("a.rs", 10, 2).unwrap();
        s.record("b.rs", 1, 1).unwrap();
        s.record("c.rs", 5, 5).unwrap();
        let order = s.files_by_churn();
        assert_eq!(order, vec!["a.rs", "c.rs", "b.rs"]);
    }

    #[test]
    fn empty_path_rejected() {
        let mut s = DiffStats::new();
        assert!(matches!(s.record("", 0, 0).unwrap_err(), DiffError::EmptyPath));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = DiffStats::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), DiffError::SchemaMismatch));
    }

    #[test]
    fn stats_serde_roundtrip() {
        let mut s = DiffStats::new();
        s.record("a.rs", 1, 2).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: DiffStats = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
