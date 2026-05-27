//! `sovereign-conversation-search-index` — substring + role + branch search.
//!
//! Indexes a set of `ConversationThread`s. Each `SearchHit` references
//! (thread_id, turn_index, role, branch_id, matched_excerpt). The
//! cockpit's search bar invokes `search()` and renders the result list.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_conversation_thread::{ConversationThread, TurnRole};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Search query.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SearchQuery {
    /// Substring (case-insensitive); empty matches every turn.
    pub needle: String,
    /// Optional role filter.
    pub role: Option<TurnRole>,
    /// Optional branch filter.
    pub branch_id: Option<String>,
    /// Max number of hits to return.
    pub max_hits: u32,
}

/// One search hit.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SearchHit {
    /// Thread id.
    pub thread_id: String,
    /// Turn index.
    pub turn_index: u32,
    /// Role.
    pub role: TurnRole,
    /// Branch id.
    pub branch_id: String,
    /// Excerpt of matched text (first 120 chars of turn body).
    pub excerpt: String,
}

/// Index envelope (just refs to threads).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SearchIndex {
    /// Schema version.
    pub schema_version: String,
    /// Indexed threads (operator-owned).
    pub threads: Vec<ConversationThread>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SearchError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// max_hits zero.
    #[error("max_hits zero")]
    ZeroMaxHits,
}

impl SearchIndex {
    /// New empty index.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            threads: Vec::new(),
        }
    }

    /// Add a thread to the index.
    pub fn add(&mut self, t: ConversationThread) {
        self.threads.push(t);
    }

    /// Run a search query.
    pub fn search(&self, q: &SearchQuery) -> Result<Vec<SearchHit>, SearchError> {
        if q.max_hits == 0 {
            return Err(SearchError::ZeroMaxHits);
        }
        let needle = q.needle.to_ascii_lowercase();
        let mut hits = Vec::new();
        for t in &self.threads {
            for turn in &t.turns {
                if let Some(r) = q.role {
                    if turn.role != r {
                        continue;
                    }
                }
                if let Some(b) = &q.branch_id {
                    if &turn.branch_id != b {
                        continue;
                    }
                }
                if !needle.is_empty() && !turn.text.to_ascii_lowercase().contains(&needle) {
                    continue;
                }
                let excerpt: String = turn.text.chars().take(120).collect();
                hits.push(SearchHit {
                    thread_id: t.thread_id.clone(),
                    turn_index: turn.index,
                    role: turn.role,
                    branch_id: turn.branch_id.clone(),
                    excerpt,
                });
                if hits.len() as u32 >= q.max_hits {
                    return Ok(hits);
                }
            }
        }
        Ok(hits)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SearchError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(SearchError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for SearchIndex {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_conversation_thread::Turn;

    fn turn(role: TurnRole, branch: &str, text: &str) -> Turn {
        Turn {
            index: 0,
            role,
            tokens_in: 0,
            tokens_out: 0,
            provider: "p".into(),
            started_at: "t".into(),
            completed_at: "t".into(),
            branch_id: branch.into(),
            text: text.into(),
        }
    }

    fn ix() -> SearchIndex {
        let mut idx = SearchIndex::new();
        let mut a = ConversationThread::new("th-1", "t");
        a.append(turn(TurnRole::Operator, "main", "Please add a new test"));
        a.append(turn(TurnRole::Model, "main", "Added a test for FOO"));
        let mut b = ConversationThread::new("th-2", "t");
        b.append(turn(TurnRole::Operator, "experiment", "Try fork branch"));
        b.append(turn(TurnRole::Tool, "experiment", "result of fork"));
        idx.add(a);
        idx.add(b);
        idx
    }

    #[test]
    fn empty_needle_matches_all() {
        let r = ix()
            .search(&SearchQuery {
                needle: String::new(),
                role: None,
                branch_id: None,
                max_hits: 100,
            })
            .unwrap();
        assert_eq!(r.len(), 4);
    }

    #[test]
    fn substring_filter() {
        let r = ix()
            .search(&SearchQuery {
                needle: "test".into(),
                role: None,
                branch_id: None,
                max_hits: 100,
            })
            .unwrap();
        assert_eq!(r.len(), 2);
    }

    #[test]
    fn case_insensitive_match() {
        let r = ix()
            .search(&SearchQuery {
                needle: "FOO".into(),
                role: None,
                branch_id: None,
                max_hits: 100,
            })
            .unwrap();
        assert_eq!(r.len(), 1);
        let r2 = ix()
            .search(&SearchQuery {
                needle: "foo".into(),
                role: None,
                branch_id: None,
                max_hits: 100,
            })
            .unwrap();
        assert_eq!(r2.len(), 1);
    }

    #[test]
    fn role_filter() {
        let r = ix()
            .search(&SearchQuery {
                needle: String::new(),
                role: Some(TurnRole::Model),
                branch_id: None,
                max_hits: 100,
            })
            .unwrap();
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].role, TurnRole::Model);
    }

    #[test]
    fn branch_filter() {
        let r = ix()
            .search(&SearchQuery {
                needle: String::new(),
                role: None,
                branch_id: Some("experiment".into()),
                max_hits: 100,
            })
            .unwrap();
        assert_eq!(r.len(), 2);
        for h in &r {
            assert_eq!(h.branch_id, "experiment");
        }
    }

    #[test]
    fn combined_filters() {
        let r = ix()
            .search(&SearchQuery {
                needle: "fork".into(),
                role: Some(TurnRole::Tool),
                branch_id: Some("experiment".into()),
                max_hits: 100,
            })
            .unwrap();
        assert_eq!(r.len(), 1);
    }

    #[test]
    fn max_hits_caps() {
        let r = ix()
            .search(&SearchQuery {
                needle: String::new(),
                role: None,
                branch_id: None,
                max_hits: 2,
            })
            .unwrap();
        assert_eq!(r.len(), 2);
    }

    #[test]
    fn max_hits_zero_rejected() {
        let err = ix()
            .search(&SearchQuery {
                needle: String::new(),
                role: None,
                branch_id: None,
                max_hits: 0,
            })
            .unwrap_err();
        assert!(matches!(err, SearchError::ZeroMaxHits));
    }

    #[test]
    fn no_match_returns_empty() {
        let r = ix()
            .search(&SearchQuery {
                needle: "nothingmatches".into(),
                role: None,
                branch_id: None,
                max_hits: 10,
            })
            .unwrap();
        assert!(r.is_empty());
    }

    #[test]
    fn excerpt_capped_at_120() {
        let mut idx = SearchIndex::new();
        let long = "X".repeat(500);
        let mut th = ConversationThread::new("th", "t");
        th.append(turn(TurnRole::Operator, "main", &long));
        idx.add(th);
        let r = idx
            .search(&SearchQuery {
                needle: String::new(),
                role: None,
                branch_id: None,
                max_hits: 1,
            })
            .unwrap();
        assert_eq!(r[0].excerpt.chars().count(), 120);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut idx = SearchIndex::new();
        idx.schema_version = "9.9.9".into();
        assert!(matches!(
            idx.validate().unwrap_err(),
            SearchError::SchemaMismatch
        ));
    }

    #[test]
    fn index_serde_roundtrip() {
        let idx = ix();
        let j = serde_json::to_string(&idx).unwrap();
        let back: SearchIndex = serde_json::from_str(&j).unwrap();
        assert_eq!(idx, back);
    }
}
