//! `sovereign-best-of-n` — spend more decode compute, pick the best answer.
//!
//! One cheap way to make a model better at inference time is to sample several
//! candidate generations and *choose* among them rather than trusting the first.
//! How you choose is the question this crate answers, with the three standard
//! strategies.
//!
//! - **Best-of-N by score** ([`best`]): each candidate carries a score — a
//!   sequence log-probability, a reward-model score — and you take the highest.
//! - **Top-k** ([`top_k`]): the `k` highest-scoring candidates, for when a
//!   downstream step wants a shortlist.
//! - **Weighted self-consistency** ([`weighted_vote`]): when many candidates
//!   reduce to the same *answer* (after extracting a final result), sum the scores
//!   of all candidates that agree and take the answer with the greatest total.
//!   This blends voting (agreement is evidence) with scoring (confidence is
//!   evidence) and beats either alone — the standard self-consistency trick,
//!   generalized from a plain count to a weighted sum.
//!
//! Everything is generic over the candidate/answer type and breaks ties
//! deterministically (lower index, then `Ord`), so selection is reproducible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::HashMap;
use std::hash::Hash;

/// Schema version of the best-of-n surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The index of the highest-scoring candidate (ties → lowest index), or `None`
/// if `scores` is empty.
pub fn best_index(scores: &[f64]) -> Option<usize> {
    scores
        .iter()
        .enumerate()
        .max_by(|a, b| a.1.total_cmp(b.1).then(b.0.cmp(&a.0)))
        .map(|(i, _)| i)
}

/// The highest-scoring candidate (by its paired score), or `None` if empty.
pub fn best<T: Clone>(candidates: &[(T, f64)]) -> Option<T> {
    let scores: Vec<f64> = candidates.iter().map(|(_, s)| *s).collect();
    best_index(&scores).map(|i| candidates[i].0.clone())
}

/// The `k` highest-scoring candidates, best first (ties by original index).
pub fn top_k<T: Clone>(candidates: &[(T, f64)], k: usize) -> Vec<T> {
    let mut idx: Vec<usize> = (0..candidates.len()).collect();
    idx.sort_by(|&a, &b| candidates[b].1.total_cmp(&candidates[a].1).then(a.cmp(&b)));
    idx.into_iter()
        .take(k)
        .map(|i| candidates[i].0.clone())
        .collect()
}

/// Weighted self-consistency: given `(answer, weight)` pairs (one per candidate,
/// the weight a score or probability), sum the weights of each distinct answer and
/// return the answer with the greatest total weight. Ties break by the answer's
/// `Ord`. Returns `None` for empty input.
pub fn weighted_vote<T>(answers: &[(T, f64)]) -> Option<T>
where
    T: Eq + Hash + Clone + Ord,
{
    if answers.is_empty() {
        return None;
    }
    let mut totals: HashMap<T, f64> = HashMap::new();
    for (a, w) in answers {
        *totals.entry(a.clone()).or_insert(0.0) += w;
    }
    totals
        .into_iter()
        .max_by(|a, b| a.1.total_cmp(&b.1).then(b.0.cmp(&a.0)))
        .map(|(a, _)| a)
}

/// Plain (unweighted) majority vote: the most frequent answer (ties by `Ord`).
/// Equivalent to [`weighted_vote`] with every weight `1.0`.
pub fn majority_vote<T>(answers: &[T]) -> Option<T>
where
    T: Eq + Hash + Clone + Ord,
{
    let weighted: Vec<(T, f64)> = answers.iter().map(|a| (a.clone(), 1.0)).collect();
    weighted_vote(&weighted)
}

/// The total weight each distinct answer accumulated, sorted by descending weight
/// (ties by answer). Useful for inspecting the vote, not just its winner.
pub fn vote_tally<T>(answers: &[(T, f64)]) -> Vec<(T, f64)>
where
    T: Eq + Hash + Clone + Ord,
{
    let mut totals: HashMap<T, f64> = HashMap::new();
    for (a, w) in answers {
        *totals.entry(a.clone()).or_insert(0.0) += w;
    }
    let mut out: Vec<(T, f64)> = totals.into_iter().collect();
    out.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn best_by_score() {
        let cands = [("a", 0.2), ("b", 0.9), ("c", 0.5)];
        assert_eq!(best(&cands), Some("b"));
        assert_eq!(best_index(&[0.2, 0.9, 0.5]), Some(1));
    }

    #[test]
    fn best_ties_to_lowest_index() {
        assert_eq!(best_index(&[0.5, 0.5, 0.3]), Some(0));
    }

    #[test]
    fn top_k_returns_shortlist() {
        let cands = [("a", 0.1), ("b", 0.9), ("c", 0.5), ("d", 0.7)];
        assert_eq!(top_k(&cands, 2), vec!["b", "d"]);
        // k larger than n returns all sorted
        assert_eq!(top_k(&cands, 10), vec!["b", "d", "c", "a"]);
    }

    #[test]
    fn weighted_vote_blends_agreement_and_confidence() {
        // answer 42 appears twice with low scores; answer 7 once with high score.
        // weighted: 42 → 0.3+0.3=0.6, 7 → 0.5 → 42 wins (agreement matters).
        let answers = [(42, 0.3), (7, 0.5), (42, 0.3)];
        assert_eq!(weighted_vote(&answers), Some(42));
    }

    #[test]
    fn weighted_vote_lets_confidence_overrule_count() {
        // here the single high-confidence answer outweighs two weak agreers.
        let answers = [(42, 0.1), (7, 0.95), (42, 0.1)];
        assert_eq!(weighted_vote(&answers), Some(7));
    }

    #[test]
    fn majority_vote_counts() {
        let answers = ["yes", "no", "yes", "yes", "no"];
        assert_eq!(majority_vote(&answers), Some("yes"));
    }

    #[test]
    fn vote_tally_is_sorted() {
        let answers = [("a", 1.0), ("b", 3.0), ("a", 1.0), ("c", 0.5)];
        let tally = vote_tally(&answers);
        assert_eq!(tally[0], ("b", 3.0));
        assert_eq!(tally[1], ("a", 2.0));
        assert_eq!(tally[2], ("c", 0.5));
    }

    #[test]
    fn empty_inputs() {
        assert_eq!(best::<&str>(&[]), None);
        assert_eq!(best_index(&[]), None);
        assert_eq!(weighted_vote::<i32>(&[]), None);
        assert_eq!(majority_vote::<i32>(&[]), None);
        assert!(top_k::<&str>(&[], 3).is_empty());
    }

    #[test]
    fn single_candidate() {
        assert_eq!(best(&[("only", 0.0)]), Some("only"));
        assert_eq!(weighted_vote(&[(5, 0.0)]), Some(5));
    }
}
