//! `sovereign-cockpit-tab-history` — closed-tab history.
//!
//! ClosedTab{id, title, ts_closed}. close(id, title, now)
//! appends; capacity drops oldest. reopen_last() pops the
//! newest and returns it. find(id) lookup. clear empties.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Closed tab.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClosedTab {
    /// Id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Closed ts ms.
    pub ts_closed: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TabHistory {
    /// Schema version.
    pub schema_version: String,
    /// Capacity.
    pub capacity: u32,
    /// Closed tabs newest-last.
    pub closed: Vec<ClosedTab>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HistoryError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Zero cap.
    #[error("capacity must be >= 1")]
    ZeroCapacity,
}

impl TabHistory {
    /// New.
    pub fn new(capacity: u32) -> Result<Self, HistoryError> {
        if capacity == 0 { return Err(HistoryError::ZeroCapacity); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            closed: Vec::new(),
        })
    }

    /// Close (record).
    pub fn close(&mut self, id: &str, title: &str, ts_closed: u64) -> Result<(), HistoryError> {
        if id.is_empty() { return Err(HistoryError::EmptyId); }
        if title.is_empty() { return Err(HistoryError::EmptyTitle); }
        if (self.closed.len() as u32) >= self.capacity {
            self.closed.remove(0);
        }
        self.closed.push(ClosedTab {
            id: id.into(),
            title: title.into(),
            ts_closed,
        });
        Ok(())
    }

    /// Reopen most recently closed.
    pub fn reopen_last(&mut self) -> Option<ClosedTab> {
        self.closed.pop()
    }

    /// Find by id.
    pub fn find(&self, id: &str) -> Option<&ClosedTab> {
        self.closed.iter().rfind(|t| t.id == id)
    }

    /// Clear.
    pub fn clear(&mut self) { self.closed.clear(); }

    /// Validate.
    pub fn validate(&self) -> Result<(), HistoryError> {
        if self.schema_version != SCHEMA_VERSION { return Err(HistoryError::SchemaMismatch); }
        if self.capacity == 0 { return Err(HistoryError::ZeroCapacity); }
        for t in &self.closed {
            if t.id.is_empty() { return Err(HistoryError::EmptyId); }
            if t.title.is_empty() { return Err(HistoryError::EmptyTitle); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn close_and_reopen() {
        let mut h = TabHistory::new(5).unwrap();
        h.close("a", "Tab A", 100).unwrap();
        h.close("b", "Tab B", 200).unwrap();
        let t = h.reopen_last().unwrap();
        assert_eq!(t.id, "b");
        let t = h.reopen_last().unwrap();
        assert_eq!(t.id, "a");
        assert!(h.reopen_last().is_none());
    }

    #[test]
    fn capacity_drops_oldest() {
        let mut h = TabHistory::new(2).unwrap();
        h.close("a", "A", 1).unwrap();
        h.close("b", "B", 2).unwrap();
        h.close("c", "C", 3).unwrap();
        assert_eq!(h.closed.len(), 2);
        assert_eq!(h.closed[0].id, "b");
    }

    #[test]
    fn find_returns_latest() {
        let mut h = TabHistory::new(5).unwrap();
        h.close("a", "A1", 1).unwrap();
        h.close("a", "A2", 2).unwrap();
        let t = h.find("a").unwrap();
        assert_eq!(t.title, "A2");
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut h = TabHistory::new(5).unwrap();
        assert!(matches!(h.close("", "T", 0).unwrap_err(), HistoryError::EmptyId));
        assert!(matches!(h.close("i", "", 0).unwrap_err(), HistoryError::EmptyTitle));
        assert!(matches!(TabHistory::new(0).unwrap_err(), HistoryError::ZeroCapacity));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = TabHistory::new(5).unwrap();
        h.schema_version = "9.9.9".into();
        assert!(matches!(h.validate().unwrap_err(), HistoryError::SchemaMismatch));
    }

    #[test]
    fn history_serde_roundtrip() {
        let mut h = TabHistory::new(5).unwrap();
        h.close("a", "T", 0).unwrap();
        let j = serde_json::to_string(&h).unwrap();
        let back: TabHistory = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
