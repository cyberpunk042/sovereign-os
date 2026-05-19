//! `sovereign-cockpit-fuzzy-ranker` — fuzzy-match scorer + ranker.
//!
//! Greedy left-to-right matcher with these scoring rules:
//! * +10 per matched char.
//! * +5 bonus if the previous char also matched (consecutive run).
//! * +3 bonus if matched char is at a word start (after `_`/`-`/`/`/space).
//! * -1 per skipped haystack char between matches.
//! * No match → score 0 + matched_all=false.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-candidate score.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Score {
    /// Stable id.
    pub id: String,
    /// Aggregate score.
    pub score: i32,
    /// Did the query fully match?
    pub matched_all: bool,
    /// Byte positions matched (ascending).
    pub positions: Vec<usize>,
}

/// Ranking result.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Ranking {
    /// Schema version.
    pub schema_version: String,
    /// Scores sorted by score desc, stable by input order on tie.
    pub ordered: Vec<Score>,
}

/// One candidate.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Candidate {
    /// Stable id.
    pub id: String,
    /// Haystack text.
    pub text: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FuzzyError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("candidate id empty")]
    EmptyId,
    /// Duplicate id.
    #[error("duplicate candidate id: {0}")]
    DuplicateId(String),
}

/// Pure ranker.
#[derive(Debug, Clone, Default)]
pub struct FuzzyRanker;

impl FuzzyRanker {
    /// Rank candidates by query.
    pub fn rank(query: &str, candidates: &[Candidate]) -> Result<Ranking, FuzzyError> {
        check_candidates(candidates)?;
        let mut scores: Vec<(usize, Score)> = candidates.iter().enumerate()
            .map(|(i, c)| (i, score_one(query, &c.id, &c.text)))
            .collect();
        scores.sort_by(|(ia, a), (ib, b)| b.score.cmp(&a.score).then(ia.cmp(ib)));
        let ordered: Vec<Score> = scores.into_iter().map(|(_, s)| s).collect();
        Ok(Ranking {
            schema_version: SCHEMA_VERSION.into(),
            ordered,
        })
    }
}

fn score_one(query: &str, id: &str, text: &str) -> Score {
    if query.is_empty() {
        return Score {
            id: id.into(),
            score: 0,
            matched_all: true,
            positions: Vec::new(),
        };
    }
    let q_bytes: Vec<u8> = query.bytes().map(|b| b.to_ascii_lowercase()).collect();
    let h_bytes: &[u8] = text.as_bytes();
    let mut qi = 0;
    let mut positions: Vec<usize> = Vec::new();
    let mut score: i32 = 0;
    let mut last_match: Option<usize> = None;
    for (i, &b) in h_bytes.iter().enumerate() {
        if qi >= q_bytes.len() { break; }
        if b.to_ascii_lowercase() == q_bytes[qi] {
            score += 10;
            // Consecutive bonus.
            if last_match == Some(i.wrapping_sub(1)) {
                score += 5;
            }
            // Word-start bonus.
            let is_word_start = i == 0 || matches!(h_bytes[i - 1], b'_' | b'-' | b'/' | b' ');
            if is_word_start {
                score += 3;
            }
            // Skip penalty.
            if let Some(prev) = last_match {
                let skipped = i - prev - 1;
                score -= skipped as i32;
            } else {
                // Initial skip from start.
                score -= i as i32;
            }
            positions.push(i);
            last_match = Some(i);
            qi += 1;
        }
    }
    let matched_all = qi == q_bytes.len();
    if !matched_all {
        score = 0;
        positions.clear();
    }
    Score { id: id.into(), score, matched_all, positions }
}

fn check_candidates(c: &[Candidate]) -> Result<(), FuzzyError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for x in c {
        if x.id.is_empty() { return Err(FuzzyError::EmptyId); }
        if !seen.insert(x.id.as_str()) {
            return Err(FuzzyError::DuplicateId(x.id.clone()));
        }
    }
    Ok(())
}

impl Ranking {
    /// Validate.
    pub fn validate(&self) -> Result<(), FuzzyError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FuzzyError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn c(id: &str, text: &str) -> Candidate {
        Candidate { id: id.into(), text: text.into() }
    }

    #[test]
    fn empty_query_returns_all_matched_zero() {
        let r = FuzzyRanker::rank("", &[c("a", "hello")]).unwrap();
        assert!(r.ordered[0].matched_all);
        assert_eq!(r.ordered[0].score, 0);
    }

    #[test]
    fn unmatched_query_score_zero() {
        let r = FuzzyRanker::rank("xyz", &[c("a", "hello")]).unwrap();
        assert_eq!(r.ordered[0].score, 0);
        assert!(!r.ordered[0].matched_all);
    }

    #[test]
    fn exact_prefix_beats_subsequence() {
        let r = FuzzyRanker::rank("foo", &[c("a", "foobar"), c("b", "f_o_o_x")]).unwrap();
        assert_eq!(r.ordered[0].id, "a");
        assert!(r.ordered[0].score > r.ordered[1].score);
    }

    #[test]
    fn word_start_bonus_applied() {
        // "fb" matches "foo_bar" at positions 0 + 4 (word-start of 'bar').
        // versus "fxby" at 0 + 2.
        let r = FuzzyRanker::rank("fb", &[c("ws", "foo_bar"), c("plain", "fxby")]).unwrap();
        assert_eq!(r.ordered[0].id, "ws");
    }

    #[test]
    fn case_insensitive() {
        let r = FuzzyRanker::rank("HELLO", &[c("a", "hello world")]).unwrap();
        assert!(r.ordered[0].matched_all);
    }

    #[test]
    fn positions_recorded() {
        let r = FuzzyRanker::rank("abc", &[c("a", "a-b-c")]).unwrap();
        assert_eq!(r.ordered[0].positions, vec![0, 2, 4]);
    }

    #[test]
    fn ranking_stable_on_tie() {
        let r = FuzzyRanker::rank("a", &[c("first", "a"), c("second", "a")]).unwrap();
        assert_eq!(r.ordered[0].id, "first");
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            FuzzyRanker::rank("x", &[c("a", "x"), c("a", "x")]).unwrap_err(),
            FuzzyError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        assert!(matches!(
            FuzzyRanker::rank("x", &[c("", "x")]).unwrap_err(),
            FuzzyError::EmptyId
        ));
    }

    #[test]
    fn empty_candidates_returns_empty_ranking() {
        let r = FuzzyRanker::rank("x", &[]).unwrap();
        assert!(r.ordered.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = FuzzyRanker::rank("x", &[c("a", "x")]).unwrap();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), FuzzyError::SchemaMismatch));
    }

    #[test]
    fn ranking_serde_roundtrip() {
        let r = FuzzyRanker::rank("foo", &[c("a", "foobar"), c("b", "afoo")]).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: Ranking = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
