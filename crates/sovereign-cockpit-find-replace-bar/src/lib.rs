//! `sovereign-cockpit-find-replace-bar` — find/replace state.
//!
//! Holds: the current `query`, current `replacement`, case-sensitivity
//! and whole-word flags, the set of `match_offsets` (sorted byte
//! positions), and the current `cursor_index` into that set (None =
//! before first). `next()` / `prev()` cycle through matches.
//! `replace_current(new_text)` produces an EditOp the caller can
//! apply; `replace_all()` returns a Vec of EditOps in offset order.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One edit operation the caller applies.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EditOp {
    /// Start (inclusive).
    pub start: u64,
    /// End (exclusive).
    pub end: u64,
    /// Replacement text.
    pub replacement: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FindReplaceBar {
    /// Schema version.
    pub schema_version: String,
    /// Query.
    pub query: String,
    /// Replacement.
    pub replacement: String,
    /// Case-sensitive search.
    pub case_sensitive: bool,
    /// Whole-word search.
    pub whole_word: bool,
    /// Match start offsets, sorted ascending.
    pub match_offsets: Vec<u64>,
    /// Match length (assumed equal to query.len() in bytes).
    pub match_len: u64,
    /// Cursor into match_offsets (None = before first).
    pub cursor_index: Option<usize>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FindReplaceError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty query.
    #[error("query empty")]
    EmptyQuery,
    /// No matches.
    #[error("no matches available")]
    NoMatches,
}

impl FindReplaceBar {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            query: String::new(),
            replacement: String::new(),
            case_sensitive: false,
            whole_word: false,
            match_offsets: Vec::new(),
            match_len: 0,
            cursor_index: None,
        }
    }

    /// Set query (clears matches).
    pub fn set_query(&mut self, q: &str) {
        self.query = q.into();
        self.match_offsets.clear();
        self.match_len = q.len() as u64;
        self.cursor_index = None;
    }

    /// Set replacement.
    pub fn set_replacement(&mut self, r: &str) {
        self.replacement = r.into();
    }

    /// Toggle case sensitivity.
    pub fn set_case_sensitive(&mut self, b: bool) {
        self.case_sensitive = b;
    }

    /// Toggle whole word.
    pub fn set_whole_word(&mut self, b: bool) {
        self.whole_word = b;
    }

    /// Replace the entire match set (caller scanned the doc).
    pub fn set_matches(&mut self, offsets: Vec<u64>) {
        self.match_offsets = offsets;
        self.match_offsets.sort();
        if self.match_offsets.is_empty() {
            self.cursor_index = None;
        } else {
            self.cursor_index = Some(0);
        }
    }

    /// Next match (wraps).
    pub fn next(&mut self) -> Result<u64, FindReplaceError> {
        if self.match_offsets.is_empty() {
            return Err(FindReplaceError::NoMatches);
        }
        let idx = match self.cursor_index {
            None => 0,
            Some(i) => (i + 1) % self.match_offsets.len(),
        };
        self.cursor_index = Some(idx);
        Ok(self.match_offsets[idx])
    }

    /// Previous match (wraps).
    pub fn prev(&mut self) -> Result<u64, FindReplaceError> {
        if self.match_offsets.is_empty() {
            return Err(FindReplaceError::NoMatches);
        }
        let len = self.match_offsets.len();
        let idx = match self.cursor_index {
            None => len - 1,
            Some(0) => len - 1,
            Some(i) => i - 1,
        };
        self.cursor_index = Some(idx);
        Ok(self.match_offsets[idx])
    }

    /// Match count.
    pub fn count(&self) -> usize {
        self.match_offsets.len()
    }

    /// Replace current match.
    pub fn replace_current(&self) -> Result<EditOp, FindReplaceError> {
        let Some(i) = self.cursor_index else {
            return Err(FindReplaceError::NoMatches);
        };
        if self.match_offsets.is_empty() {
            return Err(FindReplaceError::NoMatches);
        }
        let start = self.match_offsets[i];
        Ok(EditOp {
            start,
            end: start + self.match_len,
            replacement: self.replacement.clone(),
        })
    }

    /// Replace all (offset order — caller applies in reverse to keep offsets stable).
    pub fn replace_all(&self) -> Vec<EditOp> {
        self.match_offsets
            .iter()
            .map(|&o| EditOp {
                start: o,
                end: o + self.match_len,
                replacement: self.replacement.clone(),
            })
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FindReplaceError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FindReplaceError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for FindReplaceBar {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn set_query_resets_state() {
        let mut b = FindReplaceBar::new();
        b.set_query("foo");
        b.set_matches(vec![0, 10, 20]);
        b.set_query("bar");
        assert!(b.match_offsets.is_empty());
        assert!(b.cursor_index.is_none());
    }

    #[test]
    fn next_wraps() {
        let mut b = FindReplaceBar::new();
        b.set_query("x");
        b.set_matches(vec![0, 10, 20]);
        assert_eq!(b.next().unwrap(), 10); // started at 0, next → 10
        assert_eq!(b.next().unwrap(), 20);
        assert_eq!(b.next().unwrap(), 0); // wraps
    }

    #[test]
    fn prev_wraps() {
        let mut b = FindReplaceBar::new();
        b.set_query("x");
        b.set_matches(vec![0, 10, 20]);
        assert_eq!(b.prev().unwrap(), 20); // 0 → 20
        assert_eq!(b.prev().unwrap(), 10);
    }

    #[test]
    fn no_matches_navigation_rejected() {
        let mut b = FindReplaceBar::new();
        b.set_query("x");
        assert!(matches!(b.next().unwrap_err(), FindReplaceError::NoMatches));
        assert!(matches!(b.prev().unwrap_err(), FindReplaceError::NoMatches));
    }

    #[test]
    fn replace_current() {
        let mut b = FindReplaceBar::new();
        b.set_query("foo");
        b.set_replacement("bar");
        b.set_matches(vec![5]);
        let op = b.replace_current().unwrap();
        assert_eq!(op.start, 5);
        assert_eq!(op.end, 8);
        assert_eq!(op.replacement, "bar");
    }

    #[test]
    fn replace_all() {
        let mut b = FindReplaceBar::new();
        b.set_query("foo");
        b.set_replacement("X");
        b.set_matches(vec![0, 10, 20]);
        let ops = b.replace_all();
        assert_eq!(ops.len(), 3);
        assert_eq!(ops[0].start, 0);
        assert_eq!(ops[2].start, 20);
    }

    #[test]
    fn count() {
        let mut b = FindReplaceBar::new();
        b.set_query("x");
        b.set_matches(vec![0, 1, 2]);
        assert_eq!(b.count(), 3);
    }

    #[test]
    fn replace_current_without_matches_rejected() {
        let b = FindReplaceBar::new();
        assert!(matches!(
            b.replace_current().unwrap_err(),
            FindReplaceError::NoMatches
        ));
    }

    #[test]
    fn case_sensitive_and_whole_word_toggle() {
        let mut b = FindReplaceBar::new();
        b.set_case_sensitive(true);
        b.set_whole_word(true);
        assert!(b.case_sensitive);
        assert!(b.whole_word);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = FindReplaceBar::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            FindReplaceError::SchemaMismatch
        ));
    }

    #[test]
    fn findbar_serde_roundtrip() {
        let mut b = FindReplaceBar::new();
        b.set_query("x");
        b.set_replacement("y");
        b.set_matches(vec![0, 5]);
        let j = serde_json::to_string(&b).unwrap();
        let back: FindReplaceBar = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
