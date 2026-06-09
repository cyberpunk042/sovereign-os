//! `sovereign-mmr` — re-rank for relevance *and* diversity.
//!
//! Top-k retrieval by relevance alone tends to return near-duplicates: if three
//! passages all say the same thing, a relevance ranker puts all three at the top
//! and wastes the context budget. **Maximal Marginal Relevance** (Carbonell &
//! Goldstein) fixes that by selecting results one at a time, each time picking the
//! candidate that maximises
//!
//! ```text
//! lambda * relevance(d)  -  (1 - lambda) * max_{s in selected} similarity(d, s)
//! ```
//!
//! — high relevance to the query, *minus* how similar it is to whatever has
//! already been chosen. `lambda = 1` recovers pure relevance ordering; `lambda =
//! 0` maximises diversity regardless of relevance; values in between (≈ 0.5–0.7)
//! give the relevant-but-non-redundant set that makes a good retrieval context.
//!
//! [`select`] works directly from per-document relevance scores and document
//! vectors (cosine similarity); [`select_with_matrix`] takes a precomputed
//! pairwise similarity matrix when similarities come from elsewhere. Both are
//! greedy and deterministic (ties broken by index), returning the chosen document
//! indices in selection order.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the MMR surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Cosine similarity of two equal-length vectors (0 if either is a zero vector).
pub fn cosine(a: &[f32], b: &[f32]) -> f64 {
    let mut dot = 0.0f64;
    let mut na = 0.0f64;
    let mut nb = 0.0f64;
    for (&x, &y) in a.iter().zip(b.iter()) {
        dot += x as f64 * y as f64;
        na += x as f64 * x as f64;
        nb += y as f64 * y as f64;
    }
    if na == 0.0 || nb == 0.0 {
        0.0
    } else {
        dot / (na.sqrt() * nb.sqrt())
    }
}

/// Select up to `k` document indices by MMR, using `relevance[i]` as each
/// document's relevance to the query and cosine over `vectors` for
/// document-to-document similarity. `lambda` in `[0, 1]` trades relevance against
/// diversity. Returns indices in selection order.
///
/// `relevance` and `vectors` must be the same length; an empty input yields an
/// empty selection. `lambda` is clamped into `[0, 1]`.
pub fn select(relevance: &[f64], vectors: &[Vec<f32>], lambda: f64, k: usize) -> Vec<usize> {
    let n = relevance.len().min(vectors.len());
    select_with(relevance, n, lambda, k, |i, j| {
        cosine(&vectors[i], &vectors[j])
    })
}

/// Select up to `k` document indices by MMR using a precomputed `similarity`
/// matrix (`similarity[i][j]` = similarity of `i` and `j`). `relevance` and the
/// matrix must agree in size.
pub fn select_with_matrix(
    relevance: &[f64],
    similarity: &[Vec<f64>],
    lambda: f64,
    k: usize,
) -> Vec<usize> {
    let n = relevance.len().min(similarity.len());
    select_with(relevance, n, lambda, k, |i, j| similarity[i][j])
}

/// Core greedy MMR over `n` items with a similarity closure.
fn select_with<F: Fn(usize, usize) -> f64>(
    relevance: &[f64],
    n: usize,
    lambda: f64,
    k: usize,
    sim: F,
) -> Vec<usize> {
    let lambda = lambda.clamp(0.0, 1.0);
    let k = k.min(n);
    let mut selected: Vec<usize> = Vec::with_capacity(k);
    let mut chosen = vec![false; n];

    while selected.len() < k {
        let mut best = None;
        let mut best_score = f64::NEG_INFINITY;
        for i in 0..n {
            if chosen[i] {
                continue;
            }
            // redundancy = max similarity to anything already selected.
            let redundancy = selected
                .iter()
                .map(|&s| sim(i, s))
                .fold(f64::NEG_INFINITY, f64::max);
            let redundancy = if selected.is_empty() { 0.0 } else { redundancy };
            let score = lambda * relevance[i] - (1.0 - lambda) * redundancy;
            if score > best_score {
                best_score = score;
                best = Some(i);
            }
        }
        match best {
            Some(i) => {
                chosen[i] = true;
                selected.push(i);
            }
            None => break,
        }
    }
    selected
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lambda_one_is_pure_relevance_order() {
        // unit vectors so similarity doesn't matter; lambda=1 ignores it anyway
        let rel = vec![0.2, 0.9, 0.5, 0.7];
        let vecs = vec![
            vec![1.0, 0.0],
            vec![0.0, 1.0],
            vec![1.0, 1.0],
            vec![1.0, -1.0],
        ];
        let order = select(&rel, &vecs, 1.0, 4);
        // descending relevance: 1 (0.9), 3 (0.7), 2 (0.5), 0 (0.2)
        assert_eq!(order, vec![1, 3, 2, 0]);
    }

    #[test]
    fn diversity_avoids_redundant_duplicates() {
        // docs 0 and 1 are identical (redundant); doc 2 is different.
        let rel = vec![1.0, 0.99, 0.5];
        let vecs = vec![
            vec![1.0, 0.0, 0.0],
            vec![1.0, 0.0, 0.0],
            vec![0.0, 1.0, 0.0],
        ];
        // with moderate lambda, after picking 0 the near-duplicate 1 is penalised
        // so the diverse doc 2 should be chosen second.
        let order = select(&rel, &vecs, 0.5, 2);
        assert_eq!(order[0], 0);
        assert_eq!(
            order[1], 2,
            "should pick the diverse doc, not the duplicate"
        );
    }

    #[test]
    fn lambda_one_keeps_duplicates() {
        // pure relevance: the redundant near-duplicate is NOT penalised
        let rel = vec![1.0, 0.99, 0.5];
        let vecs = vec![
            vec![1.0, 0.0, 0.0],
            vec![1.0, 0.0, 0.0],
            vec![0.0, 1.0, 0.0],
        ];
        let order = select(&rel, &vecs, 1.0, 2);
        assert_eq!(order, vec![0, 1]); // takes both duplicates by relevance
    }

    #[test]
    fn matrix_variant_matches_intent() {
        // similarity matrix: 0 and 1 very similar, 2 dissimilar to both
        let rel = vec![1.0, 0.95, 0.6];
        let sim = vec![
            vec![1.0, 0.95, 0.1],
            vec![0.95, 1.0, 0.1],
            vec![0.1, 0.1, 1.0],
        ];
        let order = select_with_matrix(&rel, &sim, 0.5, 2);
        assert_eq!(order[0], 0);
        assert_eq!(order[1], 2);
    }

    #[test]
    fn k_caps_and_zero_k() {
        let rel = vec![1.0, 0.5];
        let vecs = vec![vec![1.0], vec![1.0]];
        assert_eq!(select(&rel, &vecs, 0.5, 0).len(), 0);
        assert_eq!(select(&rel, &vecs, 0.5, 10).len(), 2); // capped at n
    }

    #[test]
    fn empty_input() {
        let empty: Vec<f64> = Vec::new();
        let vecs: Vec<Vec<f32>> = Vec::new();
        assert!(select(&empty, &vecs, 0.5, 3).is_empty());
    }

    #[test]
    fn lambda_is_clamped() {
        // out-of-range lambda must not panic and should behave like the clamp
        let rel = vec![1.0, 0.5];
        let vecs = vec![vec![1.0, 0.0], vec![0.0, 1.0]];
        assert_eq!(select(&rel, &vecs, 5.0, 2), select(&rel, &vecs, 1.0, 2));
        assert_eq!(select(&rel, &vecs, -5.0, 2), select(&rel, &vecs, 0.0, 2));
    }

    #[test]
    fn cosine_basics() {
        assert!((cosine(&[1.0, 0.0], &[1.0, 0.0]) - 1.0).abs() < 1e-12);
        assert!(cosine(&[1.0, 0.0], &[0.0, 1.0]).abs() < 1e-12);
        assert_eq!(cosine(&[0.0, 0.0], &[1.0, 1.0]), 0.0);
    }
}
