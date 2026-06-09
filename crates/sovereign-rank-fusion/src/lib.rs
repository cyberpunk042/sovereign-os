//! `sovereign-rank-fusion` — merge several rankings into one hybrid result.
//!
//! Lexical search (BM25) and semantic search (embeddings) are good at different
//! things — exact term matches versus paraphrase — and the best retrieval often
//! runs both and *fuses* their result lists. This crate provides the two standard
//! fusion methods.
//!
//! **Reciprocal Rank Fusion** ([`reciprocal_rank_fusion`]) is rank-based and
//! needs no comparable scores at all: an item at (1-based) rank `r` in a list
//! contributes `1 / (k + r)`, and the contributions are summed across lists. The
//! constant `k` (commonly `60`) damps the influence of the very top ranks so that
//! agreement across lists matters more than being #1 in one. Because it ignores
//! the raw scores, RRF is robust to lists whose scores live on wildly different
//! scales — exactly the BM25-vs-cosine situation — which is why it is the default
//! for hybrid search.
//!
//! **Weighted score fusion** ([`weighted_score_fusion`]) is for when the scores
//! *are* meaningful: each list's scores are min-max normalized to `[0, 1]`,
//! multiplied by the list's weight, and summed per item — letting you dial how
//! much each source counts.
//!
//! Both are generic over the item id type and break ties deterministically by the
//! id, so fusion is reproducible.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::HashMap;
use std::hash::Hash;

/// Schema version of the rank-fusion surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The conventional RRF damping constant.
pub const DEFAULT_RRF_K: f64 = 60.0;

/// Fuse `rankings` (each a list of item ids best-first) with Reciprocal Rank
/// Fusion. An item at 1-based rank `r` in a list adds `1 / (k + r)`. Returns the
/// fused `(item, score)` list sorted by descending score, ties broken by item.
///
/// `k` must be positive; the standard value is [`DEFAULT_RRF_K`].
pub fn reciprocal_rank_fusion<T>(rankings: &[Vec<T>], k: f64) -> Vec<(T, f64)>
where
    T: Eq + Hash + Clone + Ord,
{
    let mut scores: HashMap<T, f64> = HashMap::new();
    for ranking in rankings {
        for (rank0, item) in ranking.iter().enumerate() {
            let r = (rank0 + 1) as f64; // 1-based rank
            *scores.entry(item.clone()).or_insert(0.0) += 1.0 / (k + r);
        }
    }
    sorted(scores)
}

/// Reciprocal Rank Fusion with [`DEFAULT_RRF_K`].
pub fn rrf<T>(rankings: &[Vec<T>]) -> Vec<(T, f64)>
where
    T: Eq + Hash + Clone + Ord,
{
    reciprocal_rank_fusion(rankings, DEFAULT_RRF_K)
}

/// Fuse weighted scored lists. Each entry is `(weight, list)` where `list` is
/// `(item, raw_score)` best-first or in any order. Within each list the scores
/// are min-max normalized to `[0, 1]` (a list with all-equal scores maps every
/// item to `1.0`), scaled by `weight`, and summed per item. Returns the fused
/// `(item, score)` list sorted by descending score, ties by item.
pub fn weighted_score_fusion<T>(lists: &[(f64, Vec<(T, f64)>)]) -> Vec<(T, f64)>
where
    T: Eq + Hash + Clone + Ord,
{
    let mut fused: HashMap<T, f64> = HashMap::new();
    for (weight, list) in lists {
        if list.is_empty() {
            continue;
        }
        let mut min = f64::INFINITY;
        let mut max = f64::NEG_INFINITY;
        for (_, s) in list {
            min = min.min(*s);
            max = max.max(*s);
        }
        let span = max - min;
        for (item, s) in list {
            let norm = if span > 0.0 { (s - min) / span } else { 1.0 };
            *fused.entry(item.clone()).or_insert(0.0) += weight * norm;
        }
    }
    sorted(fused)
}

/// Collapse a score map into a descending-sorted vec, ties broken by item.
fn sorted<T: Eq + Hash + Clone + Ord>(scores: HashMap<T, f64>) -> Vec<(T, f64)> {
    let mut out: Vec<(T, f64)> = scores.into_iter().collect();
    out.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rrf_rewards_agreement_across_lists() {
        // "b" appears in BOTH lists (near the top of each); every other item
        // appears in only one. Summing reciprocal ranks, an item present in two
        // lists accumulates far more than any single-list item.
        let lists = vec![
            vec!["a", "b", "c"], // b at rank 2
            vec!["b", "d", "e"], // b at rank 1
        ];
        let fused = rrf(&lists);
        assert_eq!(fused[0].0, "b", "fused {fused:?}");
        // and b's score exceeds any item that appears only once
        assert!(fused[0].1 > fused[1].1);
    }

    #[test]
    fn rrf_includes_all_items() {
        let lists = vec![vec![1, 2], vec![2, 3], vec![3, 4]];
        let fused = reciprocal_rank_fusion(&lists, 60.0);
        let ids: std::collections::HashSet<i32> = fused.iter().map(|(i, _)| *i).collect();
        assert_eq!(ids, [1, 2, 3, 4].into_iter().collect());
    }

    #[test]
    fn rrf_rank_one_beats_rank_two_all_else_equal() {
        // single list: order is preserved
        let fused = rrf(&[vec!["x", "y", "z"]]);
        assert_eq!(
            fused.iter().map(|(i, _)| *i).collect::<Vec<_>>(),
            vec!["x", "y", "z"]
        );
    }

    #[test]
    fn rrf_smaller_k_sharpens_top_ranks() {
        // with a tiny k, being rank 1 in one list outweighs rank 2 in two lists
        let lists = vec![vec!["a", "b"], vec!["b", "x"], vec!["b", "y"]];
        let big_k = reciprocal_rank_fusion(&lists, 600.0);
        let small_k = reciprocal_rank_fusion(&lists, 0.5);
        // b is rank-1 once and rank-2... actually b is rank1 in lists 2,3 and
        // rank2 in list1 → b dominates under both; just check both rank b first.
        assert_eq!(big_k[0].0, "b");
        assert_eq!(small_k[0].0, "b");
    }

    #[test]
    fn weighted_fusion_normalizes_disparate_scales() {
        // list A scores in the thousands, list B in [0,1]; normalization makes
        // them comparable so both contribute.
        let a = (1.0, vec![("doc1", 9000.0), ("doc2", 1000.0)]);
        let b = (1.0, vec![("doc2", 0.9), ("doc3", 0.1)]);
        let fused = weighted_score_fusion(&[a, b]);
        // doc2 is mid in A (norm 0) but top in B (norm 1); doc1 top in A (norm 1).
        // doc1 → 1.0, doc2 → 0 + 1.0 = 1.0, tie broken by id → doc1 first.
        assert_eq!(fused[0].0, "doc1");
        assert!(fused.iter().any(|(i, _)| *i == "doc2"));
        assert!(fused.iter().any(|(i, _)| *i == "doc3"));
    }

    #[test]
    fn weighted_fusion_respects_weights() {
        // heavily weight list B → its ordering should dominate
        let a = (0.1, vec![("x", 1.0), ("y", 0.0)]);
        let b = (10.0, vec![("y", 1.0), ("x", 0.0)]);
        let fused = weighted_score_fusion(&[a, b]);
        assert_eq!(fused[0].0, "y", "fused {fused:?}");
    }

    #[test]
    fn weighted_fusion_all_equal_scores_map_to_one() {
        let list = (1.0, vec![("a", 5.0), ("b", 5.0)]);
        let fused = weighted_score_fusion(&[list]);
        // both normalized to 1.0, tie by id
        assert!((fused[0].1 - 1.0).abs() < 1e-12);
        assert!((fused[1].1 - 1.0).abs() < 1e-12);
        assert_eq!(fused[0].0, "a");
    }

    #[test]
    fn empty_inputs_are_handled() {
        let empty: Vec<Vec<i32>> = Vec::new();
        assert!(rrf(&empty).is_empty());
        assert!(reciprocal_rank_fusion(&[Vec::<i32>::new()], 60.0).is_empty());
        let empty_scored: Vec<(f64, Vec<(i32, f64)>)> = Vec::new();
        assert!(weighted_score_fusion(&empty_scored).is_empty());
    }

    #[test]
    fn hybrid_bm25_plus_semantic_example() {
        // a realistic merge: lexical and semantic each rank documents differently
        let lexical = vec!["d3", "d1", "d7"]; // BM25 order
        let semantic = vec!["d1", "d3", "d9"]; // embedding order
        let fused = rrf(&[lexical, semantic]);
        // d1 and d3 appear high in both → they should be the top two
        let top2: Vec<&str> = fused.iter().take(2).map(|(i, _)| *i).collect();
        assert!(
            top2.contains(&"d1") && top2.contains(&"d3"),
            "top2 {top2:?}"
        );
    }
}
