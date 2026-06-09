//! `sovereign-rerank` — coverage-based reranking of retrieved passages.
//!
//! A first-stage retriever (lexical frequency, or embedding cosine) is built
//! for *recall* and speed: it returns a pool of plausible passages cheaply, but
//! its ranking is crude — a passage that repeats one query word ten times can
//! outrank one that actually touches every concept in the query. This crate is
//! the *precision* pass that fixes that. It rescores the pool by **coverage**:
//! what fraction of the query's distinct terms a passage contains, with raw
//! match count only as a tiebreak. So a passage about *rust ownership memory*
//! beats one that just says *rust rust rust* for the query *rust ownership
//! memory*.
//!
//! It is deterministic and dependency-free, and slots between any retriever and
//! the prompt: retrieve a wide pool, rerank it, keep the top few.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// Schema version of the rerank surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A reranked candidate.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RerankHit {
    /// The candidate's id.
    pub id: String,
    /// The candidate text.
    pub text: String,
    /// Fraction of distinct query terms the text covers, in `[0, 1]`.
    pub coverage: f64,
    /// Total query-term matches (frequency), the tiebreak.
    pub matches: usize,
}

fn tokens(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_lowercase())
        .collect()
}

/// Rerank `candidates` (`(id, text)` pairs) for `query` by coverage, returning
/// the top `top_k` highest-scoring. Candidates with zero coverage are dropped.
/// Ties (equal coverage) break by total match count, then by id ascending.
pub fn rerank(query: &str, candidates: &[(String, String)], top_k: usize) -> Vec<RerankHit> {
    let q_terms: HashSet<String> = tokens(query).into_iter().collect();
    if q_terms.is_empty() {
        return Vec::new();
    }

    let mut hits: Vec<RerankHit> = candidates
        .iter()
        .filter_map(|(id, text)| {
            let doc_tokens = tokens(text);
            let doc_set: HashSet<&String> = doc_tokens.iter().collect();
            let covered = q_terms.iter().filter(|t| doc_set.contains(t)).count();
            if covered == 0 {
                return None;
            }
            let matches = doc_tokens.iter().filter(|t| q_terms.contains(*t)).count();
            Some(RerankHit {
                id: id.clone(),
                text: text.clone(),
                coverage: covered as f64 / q_terms.len() as f64,
                matches,
            })
        })
        .collect();

    hits.sort_by(|a, b| {
        b.coverage
            .partial_cmp(&a.coverage)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| b.matches.cmp(&a.matches))
            .then_with(|| a.id.cmp(&b.id))
    });
    hits.truncate(top_k);
    hits
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cands(pairs: &[(&str, &str)]) -> Vec<(String, String)> {
        pairs
            .iter()
            .map(|(i, t)| (i.to_string(), t.to_string()))
            .collect()
    }

    #[test]
    fn coverage_beats_raw_frequency() {
        // "a" repeats the query word many times but covers only 1/3 terms;
        // "b" covers all three. b must rank first even though a has more "rust".
        let c = cands(&[
            ("a", "rust rust rust rust rust"),
            ("b", "rust ownership and memory safety"),
        ]);
        let r = rerank("rust ownership memory", &c, 5);
        assert_eq!(r[0].id, "b");
        assert!((r[0].coverage - 1.0).abs() < 1e-9);
        assert!(r[1].coverage < r[0].coverage);
    }

    #[test]
    fn zero_coverage_is_dropped() {
        let c = cands(&[("a", "tomato basil pasta"), ("b", "rust memory")]);
        let r = rerank("rust ownership memory", &c, 5);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].id, "b");
    }

    #[test]
    fn top_k_limits_results() {
        let c = cands(&[
            ("a", "rust ownership memory"),
            ("b", "rust ownership"),
            ("c", "memory"),
        ]);
        assert_eq!(rerank("rust ownership memory", &c, 2).len(), 2);
    }

    #[test]
    fn ties_break_by_matches_then_id() {
        // both cover 1/1, but "a" mentions the term more often → ranks first
        let c = cands(&[("z", "rust"), ("a", "rust rust rust")]);
        let r = rerank("rust", &c, 5);
        assert_eq!(r[0].id, "a"); // more matches
        assert_eq!(r[1].id, "z");
    }

    #[test]
    fn equal_coverage_and_matches_break_by_id() {
        let c = cands(&[("b", "rust"), ("a", "rust")]);
        let r = rerank("rust", &c, 5);
        assert_eq!(r[0].id, "a"); // id ascending
    }

    #[test]
    fn empty_query_returns_nothing() {
        let c = cands(&[("a", "rust")]);
        assert!(rerank("", &c, 5).is_empty());
    }

    #[test]
    fn coverage_is_fractional() {
        let c = cands(&[("a", "rust ownership")]); // covers 2 of 3
        let r = rerank("rust ownership memory", &c, 5);
        assert!((r[0].coverage - 2.0 / 3.0).abs() < 1e-9);
    }

    #[test]
    fn hit_serde_round_trip() {
        let c = cands(&[("a", "rust memory")]);
        let r = rerank("rust memory", &c, 5);
        let j = serde_json::to_string(&r).unwrap();
        let back: Vec<RerankHit> = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
