//! `sovereign-cockpit-incremental-search` — find-in-page state.
//!
//! `set_query(q, total)` updates the query + match-count. `next`/
//! `prev` cycles current_zero through 0..total. `current_index()`
//! returns the 1-based index for the chrome status (or None when
//! total == 0). `close()` resets.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct IncrementalSearch {
    /// Schema version.
    pub schema_version: String,
    /// Current query.
    pub query: String,
    /// Total matches.
    pub total_matches: u32,
    /// Current match (0-based).
    pub current_zero: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SearchError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl IncrementalSearch {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            query: String::new(),
            total_matches: 0,
            current_zero: 0,
        }
    }

    /// Update query + total.
    pub fn set_query(&mut self, query: &str, total_matches: u32) {
        self.query = query.into();
        self.total_matches = total_matches;
        // New query resets the cursor to the first match (0-indexed); 0 is
        // also the inert sentinel when there are no matches.
        self.current_zero = 0;
    }

    /// Next.
    pub fn next(&mut self) {
        if self.total_matches == 0 {
            self.current_zero = 0;
            return;
        }
        self.current_zero = (self.current_zero + 1) % self.total_matches;
    }

    /// Prev.
    pub fn prev(&mut self) {
        if self.total_matches == 0 {
            self.current_zero = 0;
            return;
        }
        self.current_zero = if self.current_zero == 0 {
            self.total_matches - 1
        } else {
            self.current_zero - 1
        };
    }

    /// 1-based current index (None when no matches).
    pub fn current_index(&self) -> Option<u32> {
        if self.total_matches == 0 {
            None
        } else {
            Some(self.current_zero + 1)
        }
    }

    /// Close.
    pub fn close(&mut self) {
        self.query.clear();
        self.total_matches = 0;
        self.current_zero = 0;
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SearchError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SearchError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for IncrementalSearch {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_matches_no_index() {
        let mut s = IncrementalSearch::new();
        s.set_query("x", 0);
        assert_eq!(s.current_index(), None);
    }

    #[test]
    fn next_wraps() {
        let mut s = IncrementalSearch::new();
        s.set_query("x", 3);
        assert_eq!(s.current_index(), Some(1));
        s.next();
        assert_eq!(s.current_index(), Some(2));
        s.next();
        s.next();
        assert_eq!(s.current_index(), Some(1));
    }

    #[test]
    fn prev_wraps() {
        let mut s = IncrementalSearch::new();
        s.set_query("x", 3);
        s.prev();
        assert_eq!(s.current_index(), Some(3));
    }

    #[test]
    fn next_no_matches_is_zero() {
        let mut s = IncrementalSearch::new();
        s.set_query("x", 0);
        s.next();
        assert!(s.current_index().is_none());
    }

    #[test]
    fn close_resets() {
        let mut s = IncrementalSearch::new();
        s.set_query("x", 3);
        s.next();
        s.close();
        assert!(s.query.is_empty());
        assert_eq!(s.total_matches, 0);
        assert_eq!(s.current_zero, 0);
    }

    #[test]
    fn set_query_resets_position() {
        let mut s = IncrementalSearch::new();
        s.set_query("x", 5);
        s.next();
        s.next();
        s.set_query("y", 10);
        assert_eq!(s.current_index(), Some(1));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = IncrementalSearch::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            SearchError::SchemaMismatch
        ));
    }

    #[test]
    fn search_serde_roundtrip() {
        let mut s = IncrementalSearch::new();
        s.set_query("x", 3);
        s.next();
        let j = serde_json::to_string(&s).unwrap();
        let back: IncrementalSearch = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
