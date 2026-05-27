//! `sovereign-cockpit-activity-feed` — bounded timestamped feed.
//!
//! Entry{id, category, ts_ms, label}. push appends; capacity
//! bound drops oldest. mark_read(id) clears unread for that id;
//! mark_all_read clears all. recent(now, since_ms) returns
//! entries with ts >= now - since_ms. by_category filters by
//! category id.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Id.
    pub id: String,
    /// Category.
    pub category: String,
    /// Timestamp ms.
    pub ts_ms: u64,
    /// Label.
    pub label: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActivityFeed {
    /// Schema version.
    pub schema_version: String,
    /// Capacity.
    pub capacity: u32,
    /// Entries in insertion order.
    pub entries: Vec<Entry>,
    /// Unread ids.
    pub unread: BTreeSet<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FeedError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Empty category.
    #[error("category empty")]
    EmptyCategory,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
    /// Zero capacity.
    #[error("capacity must be >= 1")]
    ZeroCapacity,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl ActivityFeed {
    /// New.
    pub fn new(capacity: u32) -> Result<Self, FeedError> {
        if capacity == 0 {
            return Err(FeedError::ZeroCapacity);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            entries: Vec::new(),
            unread: BTreeSet::new(),
        })
    }

    /// Push entry; drops oldest at capacity.
    pub fn push(
        &mut self,
        id: &str,
        category: &str,
        ts_ms: u64,
        label: &str,
    ) -> Result<(), FeedError> {
        if id.is_empty() {
            return Err(FeedError::EmptyId);
        }
        if category.is_empty() {
            return Err(FeedError::EmptyCategory);
        }
        if label.is_empty() {
            return Err(FeedError::EmptyLabel);
        }
        if self.entries.iter().any(|e| e.id == id) {
            return Err(FeedError::DuplicateId(id.into()));
        }
        if (self.entries.len() as u32) >= self.capacity {
            let removed = self.entries.remove(0);
            self.unread.remove(&removed.id);
        }
        self.entries.push(Entry {
            id: id.into(),
            category: category.into(),
            ts_ms,
            label: label.into(),
        });
        self.unread.insert(id.into());
        Ok(())
    }

    /// Mark one entry read.
    pub fn mark_read(&mut self, id: &str) -> bool {
        self.unread.remove(id)
    }

    /// Mark all read.
    pub fn mark_all_read(&mut self) {
        self.unread.clear();
    }

    /// Unread count.
    pub fn unread_count(&self) -> usize {
        self.unread.len()
    }

    /// Recent entries since (now - since_ms).
    pub fn recent(&self, now_ms: u64, since_ms: u64) -> Vec<&Entry> {
        let cutoff = now_ms.saturating_sub(since_ms);
        self.entries.iter().filter(|e| e.ts_ms >= cutoff).collect()
    }

    /// Filter by category.
    pub fn by_category(&self, category: &str) -> Vec<&Entry> {
        self.entries
            .iter()
            .filter(|e| e.category == category)
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FeedError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FeedError::SchemaMismatch);
        }
        if self.capacity == 0 {
            return Err(FeedError::ZeroCapacity);
        }
        for e in &self.entries {
            if e.id.is_empty() {
                return Err(FeedError::EmptyId);
            }
            if e.category.is_empty() {
                return Err(FeedError::EmptyCategory);
            }
            if e.label.is_empty() {
                return Err(FeedError::EmptyLabel);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn push_and_count() {
        let mut f = ActivityFeed::new(3).unwrap();
        f.push("a", "info", 100, "started").unwrap();
        f.push("b", "warn", 200, "stalled").unwrap();
        assert_eq!(f.entries.len(), 2);
        assert_eq!(f.unread_count(), 2);
    }

    #[test]
    fn capacity_drops_oldest() {
        let mut f = ActivityFeed::new(2).unwrap();
        f.push("a", "info", 100, "x").unwrap();
        f.push("b", "info", 200, "y").unwrap();
        f.push("c", "info", 300, "z").unwrap();
        assert_eq!(f.entries.len(), 2);
        assert_eq!(f.entries[0].id, "b");
        assert_eq!(f.unread_count(), 2);
    }

    #[test]
    fn mark_read_clears_unread() {
        let mut f = ActivityFeed::new(3).unwrap();
        f.push("a", "info", 100, "x").unwrap();
        assert!(f.mark_read("a"));
        assert_eq!(f.unread_count(), 0);
        assert!(!f.mark_read("a")); // already read
    }

    #[test]
    fn mark_all_read_clears() {
        let mut f = ActivityFeed::new(3).unwrap();
        f.push("a", "info", 100, "x").unwrap();
        f.push("b", "info", 200, "y").unwrap();
        f.mark_all_read();
        assert_eq!(f.unread_count(), 0);
    }

    #[test]
    fn recent_filters_by_time() {
        let mut f = ActivityFeed::new(5).unwrap();
        f.push("a", "info", 100, "x").unwrap();
        f.push("b", "info", 500, "y").unwrap();
        f.push("c", "info", 1000, "z").unwrap();
        let r = f.recent(1000, 600);
        assert_eq!(r.len(), 2);
        assert_eq!(r[0].id, "b");
    }

    #[test]
    fn by_category_filters() {
        let mut f = ActivityFeed::new(5).unwrap();
        f.push("a", "info", 100, "x").unwrap();
        f.push("b", "warn", 200, "y").unwrap();
        f.push("c", "info", 300, "z").unwrap();
        let r = f.by_category("info");
        assert_eq!(r.len(), 2);
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut f = ActivityFeed::new(3).unwrap();
        f.push("a", "info", 100, "x").unwrap();
        assert!(matches!(
            f.push("a", "info", 200, "y").unwrap_err(),
            FeedError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut f = ActivityFeed::new(3).unwrap();
        assert!(matches!(
            f.push("", "c", 0, "l").unwrap_err(),
            FeedError::EmptyId
        ));
        assert!(matches!(
            f.push("i", "", 0, "l").unwrap_err(),
            FeedError::EmptyCategory
        ));
        assert!(matches!(
            f.push("i", "c", 0, "").unwrap_err(),
            FeedError::EmptyLabel
        ));
        assert!(matches!(
            ActivityFeed::new(0).unwrap_err(),
            FeedError::ZeroCapacity
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = ActivityFeed::new(3).unwrap();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FeedError::SchemaMismatch
        ));
    }

    #[test]
    fn feed_serde_roundtrip() {
        let mut f = ActivityFeed::new(3).unwrap();
        f.push("a", "info", 100, "x").unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: ActivityFeed = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
