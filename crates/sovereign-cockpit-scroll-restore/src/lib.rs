//! `sovereign-cockpit-scroll-restore` — per-route scroll memory.
//!
//! Bounded LRU mapping route-id → (x_px, y_px). When the operator
//! returns to a route the cockpit can restore the exact offset.
//! When capacity is reached the least-recently-used entry is evicted.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One offset record (kept in MRU order — last entry = most recent).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Route id (e.g. "/dashboards/security").
    pub route: String,
    /// x px.
    pub x_px: u32,
    /// y px.
    pub y_px: u32,
    /// ISO-8601 UTC last touched.
    pub touched_at: String,
}

/// Memory envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ScrollRestore {
    /// Schema version.
    pub schema_version: String,
    /// Entries (MRU last).
    pub entries: Vec<Entry>,
    /// Max capacity.
    pub capacity: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ScrollRestoreError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Capacity zero.
    #[error("capacity is zero")]
    CapacityZero,
    /// Empty route.
    #[error("route empty")]
    EmptyRoute,
    /// Duplicate route in storage.
    #[error("duplicate route in storage: {0}")]
    DuplicateRoute(String),
    /// Over capacity.
    #[error("entries {entries} exceed capacity {capacity}")]
    OverCapacity {
        /// entries.
        entries: usize,
        /// capacity.
        capacity: u32,
    },
}

impl ScrollRestore {
    /// New empty memory.
    pub fn new(capacity: u32) -> Result<Self, ScrollRestoreError> {
        if capacity == 0 {
            return Err(ScrollRestoreError::CapacityZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            entries: Vec::new(),
            capacity,
        })
    }

    /// Record a scroll offset for a route. Updates timestamp + moves
    /// to MRU. Evicts LRU when over capacity.
    pub fn record(
        &mut self,
        route: &str,
        x_px: u32,
        y_px: u32,
        at: &str,
    ) -> Result<(), ScrollRestoreError> {
        if route.is_empty() {
            return Err(ScrollRestoreError::EmptyRoute);
        }
        // Remove existing.
        self.entries.retain(|e| e.route != route);
        self.entries.push(Entry {
            route: route.into(),
            x_px,
            y_px,
            touched_at: at.into(),
        });
        // Evict oldest if over capacity.
        while self.entries.len() > self.capacity as usize {
            self.entries.remove(0);
        }
        Ok(())
    }

    /// Lookup. Touch-on-read moves to MRU when `touch_at` is supplied.
    pub fn lookup(&mut self, route: &str, touch_at: Option<&str>) -> Option<(u32, u32)> {
        let pos = self.entries.iter().position(|e| e.route == route)?;
        let mut e = self.entries.remove(pos);
        let xy = (e.x_px, e.y_px);
        if let Some(t) = touch_at {
            e.touched_at = t.into();
        }
        self.entries.push(e);
        Some(xy)
    }

    /// Forget a route.
    pub fn forget(&mut self, route: &str) -> bool {
        let n = self.entries.len();
        self.entries.retain(|e| e.route != route);
        self.entries.len() != n
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ScrollRestoreError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ScrollRestoreError::SchemaMismatch);
        }
        if self.capacity == 0 {
            return Err(ScrollRestoreError::CapacityZero);
        }
        if self.entries.len() > self.capacity as usize {
            return Err(ScrollRestoreError::OverCapacity {
                entries: self.entries.len(),
                capacity: self.capacity,
            });
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for e in &self.entries {
            if e.route.is_empty() {
                return Err(ScrollRestoreError::EmptyRoute);
            }
            if !seen.insert(e.route.as_str()) {
                return Err(ScrollRestoreError::DuplicateRoute(e.route.clone()));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn capacity_zero_rejected() {
        assert!(matches!(
            ScrollRestore::new(0).unwrap_err(),
            ScrollRestoreError::CapacityZero
        ));
    }

    #[test]
    fn record_and_lookup() {
        let mut s = ScrollRestore::new(3).unwrap();
        s.record("/a", 10, 20, "t1").unwrap();
        assert_eq!(s.lookup("/a", None), Some((10, 20)));
    }

    #[test]
    fn lookup_missing_returns_none() {
        let mut s = ScrollRestore::new(3).unwrap();
        assert_eq!(s.lookup("/none", None), None);
    }

    #[test]
    fn record_overwrites_route() {
        let mut s = ScrollRestore::new(3).unwrap();
        s.record("/a", 10, 20, "t1").unwrap();
        s.record("/a", 30, 40, "t2").unwrap();
        assert_eq!(s.lookup("/a", None), Some((30, 40)));
        assert_eq!(s.entries.len(), 1);
    }

    #[test]
    fn eviction_when_over_capacity() {
        let mut s = ScrollRestore::new(2).unwrap();
        s.record("/a", 0, 0, "t1").unwrap();
        s.record("/b", 0, 0, "t2").unwrap();
        s.record("/c", 0, 0, "t3").unwrap();
        assert_eq!(s.entries.len(), 2);
        assert!(s.lookup("/a", None).is_none());
        assert!(s.lookup("/b", None).is_some());
        assert!(s.lookup("/c", None).is_some());
    }

    #[test]
    fn touch_on_read_moves_to_mru() {
        let mut s = ScrollRestore::new(2).unwrap();
        s.record("/a", 0, 0, "t1").unwrap();
        s.record("/b", 0, 0, "t2").unwrap();
        // Touch /a -> now MRU.
        s.lookup("/a", Some("t3"));
        s.record("/c", 0, 0, "t4").unwrap();
        // /b should be evicted, /a kept.
        assert!(s.lookup("/a", None).is_some());
        assert!(s.lookup("/b", None).is_none());
    }

    #[test]
    fn forget_removes_entry() {
        let mut s = ScrollRestore::new(3).unwrap();
        s.record("/a", 0, 0, "t1").unwrap();
        assert!(s.forget("/a"));
        assert!(!s.forget("/a"));
    }

    #[test]
    fn empty_route_rejected() {
        let mut s = ScrollRestore::new(3).unwrap();
        assert!(matches!(
            s.record("", 0, 0, "t").unwrap_err(),
            ScrollRestoreError::EmptyRoute
        ));
    }

    #[test]
    fn validate_over_capacity_rejected() {
        let mut s = ScrollRestore::new(1).unwrap();
        s.entries.push(Entry {
            route: "/a".into(),
            x_px: 0,
            y_px: 0,
            touched_at: "t".into(),
        });
        s.entries.push(Entry {
            route: "/b".into(),
            x_px: 0,
            y_px: 0,
            touched_at: "t".into(),
        });
        assert!(matches!(
            s.validate().unwrap_err(),
            ScrollRestoreError::OverCapacity { .. }
        ));
    }

    #[test]
    fn validate_duplicate_rejected() {
        let mut s = ScrollRestore::new(3).unwrap();
        s.entries.push(Entry {
            route: "/a".into(),
            x_px: 0,
            y_px: 0,
            touched_at: "t".into(),
        });
        s.entries.push(Entry {
            route: "/a".into(),
            x_px: 0,
            y_px: 0,
            touched_at: "t".into(),
        });
        assert!(matches!(
            s.validate().unwrap_err(),
            ScrollRestoreError::DuplicateRoute(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ScrollRestore::new(3).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            ScrollRestoreError::SchemaMismatch
        ));
    }

    #[test]
    fn memory_serde_roundtrip() {
        let mut s = ScrollRestore::new(3).unwrap();
        s.record("/a", 10, 20, "t1").unwrap();
        s.record("/b", 30, 40, "t2").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ScrollRestore = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
