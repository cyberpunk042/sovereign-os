//! `sovereign-cockpit-search-history` — query log with dedup.
//!
//! record(query) promotes existing entry to front, else
//! prepends. Capacity-bounded: drops oldest non-pinned (or
//! oldest if all pinned). pin/unpin toggle. clear drops all
//! non-pinned. entries() returns newest-first.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Query entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct QueryEntry {
    /// Query text.
    pub query: String,
    /// Pinned.
    pub pinned: bool,
    /// Hits.
    pub hits: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SearchHistory {
    /// Schema version.
    pub schema_version: String,
    /// Capacity.
    pub capacity: u32,
    /// Newest-first entries.
    pub entries: Vec<QueryEntry>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HistoryError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("query empty")]
    EmptyQuery,
    /// Zero capacity.
    #[error("capacity must be >= 1")]
    ZeroCapacity,
    /// Unknown.
    #[error("unknown query: {0}")]
    UnknownQuery(String),
}

impl SearchHistory {
    /// New.
    pub fn new(capacity: u32) -> Result<Self, HistoryError> {
        if capacity == 0 { return Err(HistoryError::ZeroCapacity); }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            entries: Vec::new(),
        })
    }

    /// Record a query; promotes if present, else prepends.
    pub fn record(&mut self, query: &str) -> Result<(), HistoryError> {
        if query.is_empty() { return Err(HistoryError::EmptyQuery); }
        if let Some(pos) = self.entries.iter().position(|e| e.query == query) {
            let mut e = self.entries.remove(pos);
            e.hits = e.hits.saturating_add(1);
            self.entries.insert(0, e);
            return Ok(());
        }
        // Cap before insert.
        if (self.entries.len() as u32) >= self.capacity {
            let drop_idx = self.entries.iter()
                .enumerate()
                .rev()
                .find(|(_, e)| !e.pinned)
                .map(|(i, _)| i)
                .unwrap_or(self.entries.len() - 1);
            self.entries.remove(drop_idx);
        }
        self.entries.insert(0, QueryEntry { query: query.into(), pinned: false, hits: 1 });
        Ok(())
    }

    /// Pin/unpin.
    pub fn pin(&mut self, query: &str, pinned: bool) -> Result<(), HistoryError> {
        let e = self.entries.iter_mut().find(|e| e.query == query)
            .ok_or_else(|| HistoryError::UnknownQuery(query.into()))?;
        e.pinned = pinned;
        Ok(())
    }

    /// Clear all non-pinned.
    pub fn clear_unpinned(&mut self) {
        self.entries.retain(|e| e.pinned);
    }

    /// Visible entries (newest-first).
    pub fn entries(&self) -> &[QueryEntry] { &self.entries }

    /// Validate.
    pub fn validate(&self) -> Result<(), HistoryError> {
        if self.schema_version != SCHEMA_VERSION { return Err(HistoryError::SchemaMismatch); }
        if self.capacity == 0 { return Err(HistoryError::ZeroCapacity); }
        for e in &self.entries {
            if e.query.is_empty() { return Err(HistoryError::EmptyQuery); }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_prepends() {
        let mut h = SearchHistory::new(5).unwrap();
        h.record("a").unwrap();
        h.record("b").unwrap();
        assert_eq!(h.entries[0].query, "b");
        assert_eq!(h.entries[1].query, "a");
    }

    #[test]
    fn duplicate_promotes() {
        let mut h = SearchHistory::new(5).unwrap();
        h.record("a").unwrap();
        h.record("b").unwrap();
        h.record("a").unwrap();
        assert_eq!(h.entries[0].query, "a");
        assert_eq!(h.entries[0].hits, 2);
    }

    #[test]
    fn capacity_drops_oldest_non_pinned() {
        let mut h = SearchHistory::new(3).unwrap();
        h.record("a").unwrap();
        h.record("b").unwrap();
        h.record("c").unwrap();
        h.pin("a", true).unwrap();
        h.record("d").unwrap();
        // "b" was oldest non-pinned; "a" pinned stays.
        let ids: Vec<&str> = h.entries.iter().map(|e| e.query.as_str()).collect();
        assert_eq!(ids, vec!["d", "c", "a"]);
    }

    #[test]
    fn clear_unpinned_preserves_pinned() {
        let mut h = SearchHistory::new(3).unwrap();
        h.record("a").unwrap();
        h.record("b").unwrap();
        h.pin("a", true).unwrap();
        h.clear_unpinned();
        assert_eq!(h.entries.len(), 1);
        assert_eq!(h.entries[0].query, "a");
    }

    #[test]
    fn empty_query_rejected() {
        let mut h = SearchHistory::new(3).unwrap();
        assert!(matches!(h.record("").unwrap_err(), HistoryError::EmptyQuery));
        assert!(matches!(SearchHistory::new(0).unwrap_err(), HistoryError::ZeroCapacity));
    }

    #[test]
    fn unknown_pin_rejected() {
        let mut h = SearchHistory::new(3).unwrap();
        assert!(matches!(h.pin("nope", true).unwrap_err(), HistoryError::UnknownQuery(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = SearchHistory::new(3).unwrap();
        h.schema_version = "9.9.9".into();
        assert!(matches!(h.validate().unwrap_err(), HistoryError::SchemaMismatch));
    }

    #[test]
    fn history_serde_roundtrip() {
        let mut h = SearchHistory::new(3).unwrap();
        h.record("a").unwrap();
        let j = serde_json::to_string(&h).unwrap();
        let back: SearchHistory = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
