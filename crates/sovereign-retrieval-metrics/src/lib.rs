//! `sovereign-retrieval-metrics` — measure how good a ranking actually is.
//!
//! Building retrievers (BM25, embeddings, rank fusion, MMR) is only half the job;
//! you need to *score* their output against known-relevant results to compare and
//! tune them. This crate is the standard IR metric kit, all operating on a ranked
//! list of returned item ids and a set (or graded map) of relevant ids.
//!
//! - **Precision@k / Recall@k / F1@k** — what fraction of the top `k` are
//!   relevant, and what fraction of all relevant items the top `k` caught.
//! - **Reciprocal Rank / MRR** — one over the rank of the first relevant hit,
//!   averaged across queries; rewards getting *a* good answer high.
//! - **Average Precision / MAP** — precision averaged at every relevant hit, the
//!   area under the precision-recall curve; rewards getting *all* answers high.
//! - **DCG / nDCG@k** — graded relevance with a logarithmic position discount,
//!   normalized by the ideal ordering so it lands in `[0, 1]`.
//!
//! Everything is a pure function over plain slices and is generic over the item
//! id type, so it slots onto any retriever's output.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::{HashMap, HashSet};
use std::hash::Hash;

/// Schema version of the retrieval-metrics surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Precision@k: fraction of the top `k` retrieved items that are relevant.
/// Uses `min(k, retrieved.len())` as the denominator; returns 0 if that is 0.
pub fn precision_at_k<T: Eq + Hash>(retrieved: &[T], relevant: &HashSet<T>, k: usize) -> f64 {
    let take = k.min(retrieved.len());
    if take == 0 {
        return 0.0;
    }
    let hits = retrieved[..take]
        .iter()
        .filter(|i| relevant.contains(i))
        .count();
    hits as f64 / take as f64
}

/// Recall@k: fraction of all relevant items found within the top `k`.
/// Returns 0 if there are no relevant items.
pub fn recall_at_k<T: Eq + Hash>(retrieved: &[T], relevant: &HashSet<T>, k: usize) -> f64 {
    if relevant.is_empty() {
        return 0.0;
    }
    let take = k.min(retrieved.len());
    let hits = retrieved[..take]
        .iter()
        .filter(|i| relevant.contains(i))
        .count();
    hits as f64 / relevant.len() as f64
}

/// F1@k: harmonic mean of precision@k and recall@k (0 if both are 0).
pub fn f1_at_k<T: Eq + Hash>(retrieved: &[T], relevant: &HashSet<T>, k: usize) -> f64 {
    let p = precision_at_k(retrieved, relevant, k);
    let r = recall_at_k(retrieved, relevant, k);
    if p + r == 0.0 {
        0.0
    } else {
        2.0 * p * r / (p + r)
    }
}

/// Reciprocal rank: `1 / rank` of the first relevant item (1-based), or 0 if none
/// of `retrieved` is relevant.
pub fn reciprocal_rank<T: Eq + Hash>(retrieved: &[T], relevant: &HashSet<T>) -> f64 {
    for (i, item) in retrieved.iter().enumerate() {
        if relevant.contains(item) {
            return 1.0 / (i + 1) as f64;
        }
    }
    0.0
}

/// Mean Reciprocal Rank over several `(retrieved, relevant)` query results.
pub fn mean_reciprocal_rank<T: Eq + Hash>(queries: &[(Vec<T>, HashSet<T>)]) -> f64 {
    if queries.is_empty() {
        return 0.0;
    }
    let sum: f64 = queries.iter().map(|(r, rel)| reciprocal_rank(r, rel)).sum();
    sum / queries.len() as f64
}

/// Average Precision: the mean of precision@k taken at each rank where a relevant
/// item appears, divided by the number of relevant items. 0 if none are relevant.
pub fn average_precision<T: Eq + Hash>(retrieved: &[T], relevant: &HashSet<T>) -> f64 {
    if relevant.is_empty() {
        return 0.0;
    }
    let mut hits = 0usize;
    let mut sum_prec = 0.0;
    for (i, item) in retrieved.iter().enumerate() {
        if relevant.contains(item) {
            hits += 1;
            sum_prec += hits as f64 / (i + 1) as f64;
        }
    }
    sum_prec / relevant.len() as f64
}

/// Mean Average Precision over several query results.
pub fn mean_average_precision<T: Eq + Hash>(queries: &[(Vec<T>, HashSet<T>)]) -> f64 {
    if queries.is_empty() {
        return 0.0;
    }
    let sum: f64 = queries
        .iter()
        .map(|(r, rel)| average_precision(r, rel))
        .sum();
    sum / queries.len() as f64
}

/// Discounted Cumulative Gain at `k` for a ranked list of graded relevances.
/// `gains[i]` is the relevance grade of the item at rank `i` (0 = irrelevant).
/// Uses the standard `gain / log2(rank + 1)` discount (rank 1-based).
pub fn dcg_at_k(gains: &[f64], k: usize) -> f64 {
    gains
        .iter()
        .take(k)
        .enumerate()
        .map(|(i, &g)| g / ((i + 2) as f64).log2())
        .sum()
}

/// Normalized DCG at `k`: DCG of the ranking divided by the DCG of the ideal
/// (descending-gain) ordering of the same grades. Returns 0 if the ideal DCG is
/// 0. Result is in `[0, 1]`.
pub fn ndcg_at_k(gains: &[f64], k: usize) -> f64 {
    let dcg = dcg_at_k(gains, k);
    let mut ideal: Vec<f64> = gains.to_vec();
    ideal.sort_by(|a, b| b.total_cmp(a));
    let idcg = dcg_at_k(&ideal, k);
    if idcg == 0.0 { 0.0 } else { dcg / idcg }
}

/// Convenience: build the graded-relevance vector for a ranked id list from a
/// `id → grade` map (missing ids grade 0), then compute nDCG@k.
pub fn ndcg_at_k_for<T: Eq + Hash>(retrieved: &[T], grades: &HashMap<T, f64>, k: usize) -> f64 {
    let gains: Vec<f64> = retrieved
        .iter()
        .map(|i| grades.get(i).copied().unwrap_or(0.0))
        .collect();
    // ideal is over ALL graded items, not just the retrieved order
    let dcg = dcg_at_k(&gains, k);
    let mut ideal: Vec<f64> = grades.values().copied().collect();
    ideal.sort_by(|a, b| b.total_cmp(a));
    let idcg = dcg_at_k(&ideal, k);
    if idcg == 0.0 { 0.0 } else { dcg / idcg }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn set(items: &[i32]) -> HashSet<i32> {
        items.iter().copied().collect()
    }

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn precision_and_recall() {
        let retrieved = [1, 2, 3, 4, 5];
        let relevant = set(&[2, 4, 6]); // 6 not retrieved
        // top-4: 2 and 4 relevant → precision 2/4
        assert!(approx(precision_at_k(&retrieved, &relevant, 4), 0.5));
        // recall: found 2 of 3 relevant
        assert!(approx(recall_at_k(&retrieved, &relevant, 4), 2.0 / 3.0));
        // full list: still 2 of 3
        assert!(approx(recall_at_k(&retrieved, &relevant, 5), 2.0 / 3.0));
    }

    #[test]
    fn f1_combines_precision_recall() {
        let retrieved = [1, 2];
        let relevant = set(&[1, 2]);
        // perfect → 1.0
        assert!(approx(f1_at_k(&retrieved, &relevant, 2), 1.0));
        // nothing relevant retrieved → 0
        assert!(approx(f1_at_k(&[9, 8], &relevant, 2), 0.0));
    }

    #[test]
    fn reciprocal_rank_and_mrr() {
        // first relevant at rank 3 → 1/3
        assert!(approx(
            reciprocal_rank(&[9, 8, 2, 4], &set(&[2, 4])),
            1.0 / 3.0
        ));
        // none relevant → 0
        assert!(approx(reciprocal_rank(&[9, 8], &set(&[2])), 0.0));
        // mrr over two queries: 1/1 and 1/2 → 0.75
        let queries = vec![(vec![2, 9], set(&[2])), (vec![9, 4], set(&[4]))];
        assert!(approx(mean_reciprocal_rank(&queries), 0.75));
    }

    #[test]
    fn average_precision_textbook() {
        // relevant at ranks 1 and 3 of 5; precision at hits = 1/1 and 2/3.
        // AP = (1.0 + 0.6667) / 2 relevant ≈ 0.8333
        let retrieved = [1, 9, 2, 8, 7];
        let relevant = set(&[1, 2]);
        let ap = average_precision(&retrieved, &relevant);
        assert!(approx(ap, (1.0 + 2.0 / 3.0) / 2.0), "ap {ap}");
    }

    #[test]
    fn map_averages_queries() {
        let queries = vec![
            (vec![1, 2], set(&[1, 2])), // AP 1.0
            (vec![9, 1], set(&[1])),    // AP 0.5
        ];
        assert!(approx(mean_average_precision(&queries), 0.75));
    }

    #[test]
    fn dcg_and_ndcg() {
        // graded relevances in ranked order
        let gains = [3.0, 2.0, 3.0, 0.0, 1.0, 2.0];
        // DCG = 3/log2(2) + 2/log2(3) + 3/log2(4) + 0 + 1/log2(6) + 2/log2(7)
        let dcg = dcg_at_k(&gains, 6);
        let expected = 3.0 / 1.0
            + 2.0 / 3f64.log2()
            + 3.0 / 4f64.log2()
            + 0.0
            + 1.0 / 6f64.log2()
            + 2.0 / 7f64.log2();
        assert!(approx(dcg, expected), "dcg {dcg} vs {expected}");
        // nDCG is in [0,1] and a perfectly-ordered list scores 1.0
        let nd = ndcg_at_k(&gains, 6);
        assert!(nd > 0.0 && nd <= 1.0);
        let sorted = [3.0, 3.0, 2.0, 2.0, 1.0, 0.0];
        assert!(approx(ndcg_at_k(&sorted, 6), 1.0));
    }

    #[test]
    fn ndcg_for_id_map() {
        let retrieved = [10, 20, 30];
        let mut grades = HashMap::new();
        grades.insert(10, 3.0);
        grades.insert(20, 0.0);
        grades.insert(30, 2.0);
        grades.insert(40, 3.0); // relevant but not retrieved → hurts nDCG
        let nd = ndcg_at_k_for(&retrieved, &grades, 3);
        assert!(nd > 0.0 && nd < 1.0, "ndcg {nd}");
    }

    #[test]
    fn empty_and_edge_cases() {
        let empty: Vec<i32> = Vec::new();
        assert_eq!(precision_at_k(&empty, &set(&[1]), 5), 0.0);
        assert_eq!(recall_at_k(&[1, 2], &HashSet::new(), 5), 0.0);
        assert_eq!(mean_reciprocal_rank::<i32>(&[]), 0.0);
        assert_eq!(dcg_at_k(&[], 5), 0.0);
        assert_eq!(ndcg_at_k(&[0.0, 0.0], 2), 0.0); // all-zero gains
    }

    #[test]
    fn perfect_ranking_scores_one_everywhere() {
        let retrieved = [1, 2, 3];
        let relevant = set(&[1, 2, 3]);
        assert!(approx(precision_at_k(&retrieved, &relevant, 3), 1.0));
        assert!(approx(recall_at_k(&retrieved, &relevant, 3), 1.0));
        assert!(approx(average_precision(&retrieved, &relevant), 1.0));
        assert!(approx(reciprocal_rank(&retrieved, &relevant), 1.0));
    }
}
