//! `sovereign-cockpit-leaderboard` — ranked-row list.
//!
//! `submit(id, label, score)` replaces a row's score. `ranked()`
//! returns rows sorted score-desc; rank starts at 1; tied scores
//! share the same rank and the next rank skips the tie count
//! (standard competition ranking).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Row {
    /// Stable id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Score.
    pub score: i64,
}

/// Ranked row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RankedRow {
    /// Rank (1-based).
    pub rank: u32,
    /// Row.
    pub row: Row,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Leaderboard {
    /// Schema version.
    pub schema_version: String,
    /// id → row.
    pub rows: BTreeMap<String, Row>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LeaderError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("row id empty")]
    EmptyId,
    /// Empty label.
    #[error("row label empty")]
    EmptyLabel,
}

impl Leaderboard {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            rows: BTreeMap::new(),
        }
    }

    /// Submit / replace.
    pub fn submit(&mut self, id: &str, label: &str, score: i64) -> Result<(), LeaderError> {
        if id.is_empty() { return Err(LeaderError::EmptyId); }
        if label.is_empty() { return Err(LeaderError::EmptyLabel); }
        self.rows.insert(id.into(), Row { id: id.into(), label: label.into(), score });
        Ok(())
    }

    /// Ranked rows. Standard competition ranking ("1224" style).
    pub fn ranked(&self) -> Vec<RankedRow> {
        let mut v: Vec<Row> = self.rows.values().cloned().collect();
        v.sort_by(|a, b| b.score.cmp(&a.score).then(a.id.cmp(&b.id)));
        let mut out = Vec::with_capacity(v.len());
        let mut last_score: Option<i64> = None;
        let mut last_rank: u32 = 0;
        for (i, row) in v.into_iter().enumerate() {
            let pos = (i as u32) + 1;
            let rank = match last_score {
                Some(s) if s == row.score => last_rank,
                _ => { last_rank = pos; pos }
            };
            last_score = Some(row.score);
            out.push(RankedRow { rank, row });
        }
        out
    }

    /// Remove.
    pub fn remove(&mut self, id: &str) -> bool {
        self.rows.remove(id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LeaderError> {
        if self.schema_version != SCHEMA_VERSION { return Err(LeaderError::SchemaMismatch); }
        for (id, r) in &self.rows {
            if id.is_empty() { return Err(LeaderError::EmptyId); }
            if r.label.is_empty() { return Err(LeaderError::EmptyLabel); }
        }
        Ok(())
    }
}

impl Default for Leaderboard {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ranked_desc() {
        let mut l = Leaderboard::new();
        l.submit("a", "A", 30).unwrap();
        l.submit("b", "B", 10).unwrap();
        l.submit("c", "C", 20).unwrap();
        let r = l.ranked();
        assert_eq!(r[0].row.id, "a");
        assert_eq!(r[1].row.id, "c");
        assert_eq!(r[2].row.id, "b");
        assert_eq!(r[0].rank, 1);
        assert_eq!(r[1].rank, 2);
        assert_eq!(r[2].rank, 3);
    }

    #[test]
    fn ties_share_rank_skip() {
        let mut l = Leaderboard::new();
        l.submit("a", "A", 30).unwrap();
        l.submit("b", "B", 20).unwrap();
        l.submit("c", "C", 20).unwrap();
        l.submit("d", "D", 10).unwrap();
        let r = l.ranked();
        // a=1, b=2, c=2, d=4 (competition ranking).
        assert_eq!(r[0].rank, 1);
        assert_eq!(r[1].rank, 2);
        assert_eq!(r[2].rank, 2);
        assert_eq!(r[3].rank, 4);
    }

    #[test]
    fn submit_replaces() {
        let mut l = Leaderboard::new();
        l.submit("a", "A", 10).unwrap();
        l.submit("a", "A", 50).unwrap();
        assert_eq!(l.rows["a"].score, 50);
    }

    #[test]
    fn remove() {
        let mut l = Leaderboard::new();
        l.submit("a", "A", 10).unwrap();
        assert!(l.remove("a"));
        assert!(!l.remove("a"));
    }

    #[test]
    fn empty_fields_rejected() {
        let mut l = Leaderboard::new();
        assert!(matches!(l.submit("", "A", 0).unwrap_err(), LeaderError::EmptyId));
        assert!(matches!(l.submit("a", "", 0).unwrap_err(), LeaderError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = Leaderboard::new();
        l.schema_version = "9.9.9".into();
        assert!(matches!(l.validate().unwrap_err(), LeaderError::SchemaMismatch));
    }

    #[test]
    fn leaderboard_serde_roundtrip() {
        let mut l = Leaderboard::new();
        l.submit("a", "A", 30).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: Leaderboard = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
