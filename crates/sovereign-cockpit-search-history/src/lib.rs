//! `sovereign-cockpit-search-history` — recent-query ring buffer
//! with MRU semantics + dedup + bounded capacity.
//!
//! Every cockpit search bar needs the same state machine:
//!   1. Record an executed query at the head of the recents list.
//!   2. If the same query is already in the list, MOVE it to the
//!      head (don't duplicate; preserve operator intent that
//!      "recent" means "last used").
//!   3. Cap the list at N entries; pop the oldest when full.
//!   4. Empty / whitespace queries are NOT recorded.
//!   5. Optional case-insensitive matching for dedup.
//!
//! Standing rule: we do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Dedup mode for matching against existing entries.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum DedupMode {
    /// Exact-byte comparison ("Foo" ≠ "foo").
    CaseSensitive,
    /// ASCII case-insensitive ("Foo" == "foo").
    CaseInsensitive,
}

/// Errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum SearchHistoryError {
    /// `capacity` was 0.
    #[error("capacity must be ≥ 1")]
    InvalidCapacity,
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

/// Recent-query ring buffer.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SearchHistory {
    /// Capacity ceiling.
    capacity: usize,
    /// Dedup mode (default: case-sensitive).
    dedup: DedupMode,
    /// Most-recent first; never longer than `capacity`.
    entries: Vec<String>,
}

impl SearchHistory {
    /// Construct an empty history.
    pub fn new(capacity: usize, dedup: DedupMode) -> Result<Self, SearchHistoryError> {
        if capacity == 0 {
            return Err(SearchHistoryError::InvalidCapacity);
        }
        Ok(Self {
            capacity,
            dedup,
            entries: Vec::new(),
        })
    }

    /// Capacity ceiling.
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Number of stored entries.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// True iff `len() == 0`.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Snapshot the entries — most-recent first.
    pub fn entries(&self) -> &[String] {
        &self.entries
    }

    /// Record an executed query. Returns true iff the buffer
    /// changed (new entry added OR existing entry moved to head).
    /// No-op for empty / whitespace-only queries.
    pub fn record(&mut self, query: &str) -> bool {
        let trimmed = query.trim();
        if trimmed.is_empty() {
            return false;
        }
        // Find existing match.
        let pos = self.entries.iter().position(|e| self.matches(e, trimmed));
        match pos {
            Some(0) => false, // already at head; no change
            Some(idx) => {
                let existing = self.entries.remove(idx);
                self.entries.insert(0, existing);
                true
            }
            None => {
                self.entries.insert(0, trimmed.to_string());
                if self.entries.len() > self.capacity {
                    self.entries.pop();
                }
                true
            }
        }
    }

    /// Remove all entries.
    pub fn clear(&mut self) {
        self.entries.clear();
    }

    fn matches(&self, a: &str, b: &str) -> bool {
        match self.dedup {
            DedupMode::CaseSensitive => a == b,
            DedupMode::CaseInsensitive => a.eq_ignore_ascii_case(b),
        }
    }
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), SearchHistoryError> {
    if s != SCHEMA_VERSION {
        return Err(SearchHistoryError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cs(n: usize) -> SearchHistory {
        SearchHistory::new(n, DedupMode::CaseSensitive).unwrap()
    }

    #[test]
    fn zero_capacity_rejected() {
        assert_eq!(
            SearchHistory::new(0, DedupMode::CaseSensitive).unwrap_err(),
            SearchHistoryError::InvalidCapacity
        );
    }

    #[test]
    fn empty_query_is_no_op() {
        let mut h = cs(5);
        assert!(!h.record(""));
        assert!(!h.record("   "));
        assert!(!h.record("\t\n"));
        assert!(h.is_empty());
    }

    #[test]
    fn query_is_trimmed_before_recording() {
        let mut h = cs(5);
        h.record("  hello  ");
        assert_eq!(h.entries(), &["hello"]);
    }

    #[test]
    fn entries_are_mru_ordered() {
        let mut h = cs(5);
        h.record("first");
        h.record("second");
        h.record("third");
        assert_eq!(h.entries(), &["third", "second", "first"]);
    }

    #[test]
    fn duplicate_moves_to_head_not_added() {
        let mut h = cs(5);
        h.record("a");
        h.record("b");
        h.record("c");
        let changed = h.record("a");
        assert!(changed, "moving to head IS a change");
        assert_eq!(h.entries(), &["a", "c", "b"]);
        assert_eq!(h.len(), 3);
    }

    #[test]
    fn duplicate_at_head_is_no_op() {
        let mut h = cs(5);
        h.record("a");
        let changed = h.record("a");
        assert!(!changed);
        assert_eq!(h.entries(), &["a"]);
    }

    #[test]
    fn capacity_evicts_oldest() {
        let mut h = cs(3);
        h.record("1");
        h.record("2");
        h.record("3");
        h.record("4");
        assert_eq!(h.entries(), &["4", "3", "2"]);
        assert_eq!(h.len(), 3);
    }

    #[test]
    fn case_sensitive_dedup_keeps_both() {
        let mut h = cs(5);
        h.record("Foo");
        h.record("foo");
        assert_eq!(h.entries(), &["foo", "Foo"]);
    }

    #[test]
    fn case_insensitive_dedup_merges() {
        let mut h = SearchHistory::new(5, DedupMode::CaseInsensitive).unwrap();
        h.record("Foo");
        h.record("foo");
        // "foo" matches "Foo" case-insensitively → "Foo" moves to head.
        // The MOVED entry keeps its ORIGINAL casing, not the new one.
        assert_eq!(h.entries(), &["Foo"]);
        assert_eq!(h.len(), 1);
    }

    #[test]
    fn clear_empties_the_buffer() {
        let mut h = cs(5);
        h.record("a");
        h.record("b");
        h.clear();
        assert!(h.is_empty());
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            SearchHistoryError::SchemaMismatch
        ));
    }

    #[test]
    fn round_trip_serde() {
        let mut h = cs(3);
        h.record("alpha");
        h.record("beta");
        let j = serde_json::to_string(&h).unwrap();
        let back: SearchHistory = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }

    #[test]
    fn dedup_mode_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&DedupMode::CaseSensitive).unwrap(),
            "\"case-sensitive\""
        );
        assert_eq!(
            serde_json::to_string(&DedupMode::CaseInsensitive).unwrap(),
            "\"case-insensitive\""
        );
    }
}
