//! `sovereign-cockpit-did-you-mean` — nearest-candidate suggester.
//!
//! suggest(query, candidates, n) returns up to n nearest matches,
//! ranked by char-overlap score (count of shared chars / len_max).
//! Ties broken by lexicographic candidate. Empty query → empty.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Suggestion.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Suggestion {
    /// Candidate.
    pub candidate: String,
    /// Score 0..=10000.
    pub score_bp: u32,
}

/// Versioned state placeholder.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DidYouMean {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DymError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

fn char_overlap_bp(query: &str, candidate: &str) -> u32 {
    let q: Vec<char> = query.chars().collect();
    let c: Vec<char> = candidate.chars().collect();
    let max_len = q.len().max(c.len()) as u32;
    if max_len == 0 {
        return 10_000;
    }
    // Multiset overlap (count, capped by min occurrence).
    let mut q_counts: BTreeMap<char, u32> = BTreeMap::new();
    for ch in &q {
        *q_counts.entry(*ch).or_insert(0) += 1;
    }
    let mut c_counts: BTreeMap<char, u32> = BTreeMap::new();
    for ch in &c {
        *c_counts.entry(*ch).or_insert(0) += 1;
    }
    let mut shared: u32 = 0;
    for (k, &vq) in &q_counts {
        if let Some(&vc) = c_counts.get(k) {
            shared += vq.min(vc);
        }
    }
    ((shared as u64 * 10_000) / max_len as u64) as u32
}

/// Suggest.
pub fn suggest(query: &str, candidates: &[String], n: usize) -> Vec<Suggestion> {
    if query.is_empty() || candidates.is_empty() {
        return Vec::new();
    }
    let mut scored: Vec<Suggestion> = candidates
        .iter()
        .map(|c| Suggestion {
            candidate: c.clone(),
            score_bp: char_overlap_bp(query, c),
        })
        .collect();
    scored.sort_by(|a, b| {
        b.score_bp
            .cmp(&a.score_bp)
            .then(a.candidate.cmp(&b.candidate))
    });
    scored.into_iter().take(n).collect()
}

impl DidYouMean {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DymError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DymError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for DidYouMean {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cands(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn empty_query() {
        let s = suggest("", &cands(&["alpha", "beta"]), 2);
        assert!(s.is_empty());
    }

    #[test]
    fn typo_suggests_closest() {
        let s = suggest("alpa", &cands(&["alpha", "beta", "gamma"]), 1);
        assert_eq!(s.len(), 1);
        assert_eq!(s[0].candidate, "alpha");
    }

    #[test]
    fn multiple_suggestions_score_ordered() {
        let s = suggest("alp", &cands(&["alpha", "beta", "lap"]), 3);
        assert_eq!(s.len(), 3);
        assert_eq!(s[0].candidate, "lap"); // 3 chars shared, len 3 → 10000 bp
    }

    #[test]
    fn ties_lex_asc() {
        let s = suggest("ab", &cands(&["ba", "ab"]), 2);
        assert_eq!(s[0].candidate, "ab"); // lex tie-break
    }

    #[test]
    fn no_candidates() {
        let s = suggest("xyz", &cands(&[]), 5);
        assert!(s.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = DidYouMean::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            DymError::SchemaMismatch
        ));
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = DidYouMean::new();
        let j = serde_json::to_string(&s).unwrap();
        let back: DidYouMean = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
