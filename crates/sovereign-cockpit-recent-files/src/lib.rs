//! `sovereign-cockpit-recent-files` — bounded MRU list.
//!
//! `touch(path, ts)` marks the file most-recently-used. Capacity
//! bounds the list; overflow drops oldest. `ordered()` returns
//! most-recent first.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Path.
    pub path: String,
    /// Last touched.
    pub last_touched_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RecentFiles {
    /// Schema version.
    pub schema_version: String,
    /// Capacity.
    pub capacity: usize,
    /// path → entry.
    pub entries: BTreeMap<String, Entry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RecentError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty path.
    #[error("path empty")]
    EmptyPath,
    /// Zero capacity.
    #[error("capacity must be > 0")]
    ZeroCapacity,
}

impl RecentFiles {
    /// New.
    pub fn new(capacity: usize) -> Result<Self, RecentError> {
        if capacity == 0 {
            return Err(RecentError::ZeroCapacity);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            entries: BTreeMap::new(),
        })
    }

    /// Touch (upsert).
    pub fn touch(&mut self, path: &str, ts_ms: u64) -> Result<(), RecentError> {
        if path.is_empty() {
            return Err(RecentError::EmptyPath);
        }
        if !self.entries.contains_key(path) && self.entries.len() == self.capacity {
            // Drop oldest.
            if let Some(oldest) = self
                .entries
                .iter()
                .min_by_key(|(_, e)| e.last_touched_ms)
                .map(|(k, _)| k.clone())
            {
                self.entries.remove(&oldest);
            }
        }
        self.entries.insert(
            path.into(),
            Entry {
                path: path.into(),
                last_touched_ms: ts_ms,
            },
        );
        Ok(())
    }

    /// Remove.
    pub fn forget(&mut self, path: &str) -> bool {
        self.entries.remove(path).is_some()
    }

    /// Ordered most-recent-first.
    pub fn ordered(&self) -> Vec<Entry> {
        let mut v: Vec<Entry> = self.entries.values().cloned().collect();
        v.sort_by(|a, b| {
            b.last_touched_ms
                .cmp(&a.last_touched_ms)
                .then(a.path.cmp(&b.path))
        });
        v
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RecentError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RecentError::SchemaMismatch);
        }
        if self.capacity == 0 {
            return Err(RecentError::ZeroCapacity);
        }
        for p in self.entries.keys() {
            if p.is_empty() {
                return Err(RecentError::EmptyPath);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn touch_and_order() {
        let mut r = RecentFiles::new(10).unwrap();
        r.touch("a", 100).unwrap();
        r.touch("b", 200).unwrap();
        let o = r.ordered();
        assert_eq!(o[0].path, "b");
        assert_eq!(o[1].path, "a");
    }

    #[test]
    fn capacity_drops_oldest() {
        let mut r = RecentFiles::new(2).unwrap();
        r.touch("a", 100).unwrap();
        r.touch("b", 200).unwrap();
        r.touch("c", 300).unwrap();
        assert_eq!(r.entries.len(), 2);
        assert!(!r.entries.contains_key("a"));
    }

    #[test]
    fn touch_updates_ts() {
        let mut r = RecentFiles::new(10).unwrap();
        r.touch("a", 100).unwrap();
        r.touch("a", 200).unwrap();
        assert_eq!(r.entries["a"].last_touched_ms, 200);
    }

    #[test]
    fn forget_works() {
        let mut r = RecentFiles::new(10).unwrap();
        r.touch("a", 100).unwrap();
        assert!(r.forget("a"));
        assert!(r.ordered().is_empty());
    }

    #[test]
    fn empty_path_rejected() {
        let mut r = RecentFiles::new(10).unwrap();
        assert!(matches!(
            r.touch("", 0).unwrap_err(),
            RecentError::EmptyPath
        ));
    }

    #[test]
    fn zero_capacity_rejected() {
        assert!(matches!(
            RecentFiles::new(0).unwrap_err(),
            RecentError::ZeroCapacity
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = RecentFiles::new(10).unwrap();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            RecentError::SchemaMismatch
        ));
    }

    #[test]
    fn recent_serde_roundtrip() {
        let mut r = RecentFiles::new(10).unwrap();
        r.touch("a", 100).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: RecentFiles = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
