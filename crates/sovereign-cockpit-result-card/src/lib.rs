//! `sovereign-cockpit-result-card` — search-result card list.
//!
//! Card{id, title, snippet, source, score}. add appends.
//! sorted_by_score returns cards score-desc + id-asc tie-break.
//! top_n bounds to N. by_source filters.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Card.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Card {
    /// Id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Snippet body.
    pub snippet: String,
    /// Source label.
    pub source: String,
    /// Score (higher = more relevant).
    pub score: i64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ResultCardList {
    /// Schema version.
    pub schema_version: String,
    /// Cards.
    pub cards: Vec<Card>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CardError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("title empty")]
    EmptyTitle,
    /// Empty.
    #[error("source empty")]
    EmptySource,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

impl ResultCardList {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            cards: Vec::new(),
        }
    }

    /// Add card.
    pub fn add(&mut self, id: &str, title: &str, snippet: &str, source: &str, score: i64) -> Result<(), CardError> {
        if id.is_empty() { return Err(CardError::EmptyId); }
        if title.is_empty() { return Err(CardError::EmptyTitle); }
        if source.is_empty() { return Err(CardError::EmptySource); }
        if self.cards.iter().any(|c| c.id == id) {
            return Err(CardError::DuplicateId(id.into()));
        }
        self.cards.push(Card {
            id: id.into(),
            title: title.into(),
            snippet: snippet.into(),
            source: source.into(),
            score,
        });
        Ok(())
    }

    /// Sorted by score desc + id asc.
    pub fn sorted_by_score(&self) -> Vec<&Card> {
        let mut all: Vec<&Card> = self.cards.iter().collect();
        all.sort_by(|a, b| b.score.cmp(&a.score).then(a.id.cmp(&b.id)));
        all
    }

    /// Top N.
    pub fn top_n(&self, n: usize) -> Vec<&Card> {
        self.sorted_by_score().into_iter().take(n).collect()
    }

    /// By source.
    pub fn by_source(&self, source: &str) -> Vec<&Card> {
        self.cards.iter().filter(|c| c.source == source).collect()
    }

    /// Clear.
    pub fn clear(&mut self) {
        self.cards.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CardError> {
        if self.schema_version != SCHEMA_VERSION { return Err(CardError::SchemaMismatch); }
        for c in &self.cards {
            if c.id.is_empty() { return Err(CardError::EmptyId); }
            if c.title.is_empty() { return Err(CardError::EmptyTitle); }
            if c.source.is_empty() { return Err(CardError::EmptySource); }
        }
        Ok(())
    }
}

impl Default for ResultCardList {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lst() -> ResultCardList {
        let mut l = ResultCardList::new();
        l.add("a", "A", "s", "src", 5).unwrap();
        l.add("b", "B", "s", "src", 10).unwrap();
        l.add("c", "C", "s", "other", 8).unwrap();
        l
    }

    #[test]
    fn sorted_by_score() {
        let l = lst();
        let s = l.sorted_by_score();
        let ids: Vec<&str> = s.iter().map(|c| c.id.as_str()).collect();
        assert_eq!(ids, vec!["b", "c", "a"]);
    }

    #[test]
    fn top_n_limits() {
        let l = lst();
        assert_eq!(l.top_n(2).len(), 2);
    }

    #[test]
    fn by_source_filters() {
        let l = lst();
        let r = l.by_source("src");
        assert_eq!(r.len(), 2);
    }

    #[test]
    fn duplicate_rejected() {
        let mut l = ResultCardList::new();
        l.add("a", "A", "s", "src", 1).unwrap();
        assert!(matches!(l.add("a", "B", "s", "src", 2).unwrap_err(), CardError::DuplicateId(_)));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut l = ResultCardList::new();
        assert!(matches!(l.add("", "T", "s", "src", 1).unwrap_err(), CardError::EmptyId));
        assert!(matches!(l.add("i", "", "s", "src", 1).unwrap_err(), CardError::EmptyTitle));
        assert!(matches!(l.add("i", "T", "s", "", 1).unwrap_err(), CardError::EmptySource));
    }

    #[test]
    fn clear_resets() {
        let mut l = lst();
        l.clear();
        assert!(l.cards.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = ResultCardList::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), CardError::SchemaMismatch));
    }

    #[test]
    fn list_serde_roundtrip() {
        let l = lst();
        let j = serde_json::to_string(&l).unwrap();
        let back: ResultCardList = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
