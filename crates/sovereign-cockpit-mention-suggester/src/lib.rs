//! `sovereign-cockpit-mention-suggester` — @-mention typeahead.
//!
//! `active_query(input, cursor)` returns Some(query) if the cursor
//! sits inside an @-token (no preceding whitespace before '@', no
//! whitespace after the '@'); else None. `suggest(query, operators,
//! max)` returns up to `max` operators whose handle starts with
//! the query (case-insensitive), preserving input order.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One operator handle.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Operator {
    /// Handle (no '@').
    pub handle: String,
    /// Display name.
    pub display: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MentionSuggester {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MentionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl MentionSuggester {
    /// New.
    pub fn new() -> Self {
        Self { schema_version: SCHEMA_VERSION.into() }
    }

    /// Active @-query at cursor.
    pub fn active_query(&self, input: &str, cursor: usize) -> Option<String> {
        if cursor > input.len() { return None; }
        let prefix = &input[..cursor];
        // Walk backwards from cursor to find '@'.
        let mut at_pos: Option<usize> = None;
        for (i, ch) in prefix.char_indices().rev() {
            if ch == '@' { at_pos = Some(i); break; }
            if ch.is_whitespace() { return None; }
        }
        let at = at_pos?;
        // '@' must be at start or preceded by whitespace.
        if at > 0 {
            let prev = prefix[..at].chars().next_back()?;
            if !prev.is_whitespace() { return None; }
        }
        let q = &prefix[at + 1..];
        if q.is_empty() { return Some(String::new()); }
        // Must contain no whitespace (we already checked back-to-@).
        Some(q.to_string())
    }

    /// Suggest matches.
    pub fn suggest<'a>(&self, query: &str, operators: &'a [Operator], max: usize) -> Vec<&'a Operator> {
        let q = query.to_lowercase();
        operators.iter()
            .filter(|o| o.handle.to_lowercase().starts_with(&q))
            .take(max)
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), MentionError> {
        if self.schema_version != SCHEMA_VERSION { return Err(MentionError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for MentionSuggester {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn op(handle: &str) -> Operator {
        Operator { handle: handle.into(), display: handle.into() }
    }

    #[test]
    fn active_at_start() {
        let m = MentionSuggester::new();
        let q = m.active_query("@al", 3);
        assert_eq!(q.as_deref(), Some("al"));
    }

    #[test]
    fn active_after_space() {
        let m = MentionSuggester::new();
        let q = m.active_query("hello @al", 9);
        assert_eq!(q.as_deref(), Some("al"));
    }

    #[test]
    fn no_active_when_not_after_whitespace() {
        let m = MentionSuggester::new();
        // "foo@al" — '@' preceded by non-whitespace.
        let q = m.active_query("foo@al", 6);
        assert!(q.is_none());
    }

    #[test]
    fn no_active_when_no_at() {
        let m = MentionSuggester::new();
        assert!(m.active_query("hello world", 11).is_none());
    }

    #[test]
    fn suggest_case_insensitive_starts_with() {
        let m = MentionSuggester::new();
        let ops = vec![op("alice"), op("bob"), op("alex")];
        let s = m.suggest("AL", &ops, 10);
        assert_eq!(s.len(), 2);
        assert_eq!(s[0].handle, "alice");
        assert_eq!(s[1].handle, "alex");
    }

    #[test]
    fn suggest_capped() {
        let m = MentionSuggester::new();
        let ops = vec![op("a1"), op("a2"), op("a3"), op("a4")];
        let s = m.suggest("a", &ops, 2);
        assert_eq!(s.len(), 2);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = MentionSuggester::new();
        m.schema_version = "9.9.9".into();
        assert!(matches!(m.validate().unwrap_err(), MentionError::SchemaMismatch));
    }

    #[test]
    fn mention_serde_roundtrip() {
        let m = MentionSuggester::new();
        let j = serde_json::to_string(&m).unwrap();
        let back: MentionSuggester = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
