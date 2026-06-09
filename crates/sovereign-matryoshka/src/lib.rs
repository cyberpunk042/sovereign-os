//! `sovereign-matryoshka` — one embedding, many sizes.
//!
//! Matryoshka Representation Learning trains an embedding so that its *prefixes*
//! are themselves usable embeddings: the first 64 dimensions capture the coarse
//! meaning, the first 256 a finer one, the full 1024 the finest. Like the nesting
//! dolls it is named for, a smaller embedding sits inside the larger. That lets a
//! system spend memory and compute adaptively — store and search a short prefix
//! cheaply, and only consult more dimensions when a decision is close.
//!
//! This crate provides the truncation and the two retrieval patterns. [`truncate`]
//! takes the first `dim` components and **renormalizes** to unit length (so cosine
//! comparisons stay calibrated across dimensions). [`coarse_to_fine`] is the
//! adaptive search: rank a database at a small dimension to get a cheap shortlist,
//! then rerank just that shortlist at the full dimension — most of the work done
//! on short vectors, the final ordering at full fidelity.
//!
//! Cosine similarity is included so the crate is self-contained; pass in
//! already-truncated vectors or let the helpers truncate for you.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the matryoshka surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Truncate `embedding` to its first `dim` components and renormalize to unit
/// length. `dim` is clamped to the embedding's length; a zero-norm prefix is
/// returned as-is (all zeros).
pub fn truncate(embedding: &[f32], dim: usize) -> Vec<f32> {
    let d = dim.min(embedding.len());
    let prefix = &embedding[..d];
    let norm: f32 = prefix.iter().map(|&x| x * x).sum::<f32>().sqrt();
    if norm == 0.0 {
        return prefix.to_vec();
    }
    prefix.iter().map(|&x| x / norm).collect()
}

/// Truncate to several `dims`, returning one renormalized vector per level.
pub fn truncate_levels(embedding: &[f32], dims: &[usize]) -> Vec<Vec<f32>> {
    dims.iter().map(|&d| truncate(embedding, d)).collect()
}

/// Cosine similarity of two equal-length vectors (0 if either is a zero vector).
pub fn cosine(a: &[f32], b: &[f32]) -> f32 {
    let mut dot = 0.0f32;
    let mut na = 0.0f32;
    let mut nb = 0.0f32;
    for (&x, &y) in a.iter().zip(b.iter()) {
        dot += x * y;
        na += x * x;
        nb += y * y;
    }
    if na == 0.0 || nb == 0.0 {
        0.0
    } else {
        dot / (na.sqrt() * nb.sqrt())
    }
}

/// Coarse-to-fine retrieval: rank `database` against `query` at `coarse_dim` to
/// take the top `shortlist` candidates, then rerank those at the full dimension,
/// returning the final top `k` as `(index, full_similarity)` best-first.
///
/// `database` rows and `query` must share a dimension. `coarse_dim` is clamped.
pub fn coarse_to_fine(
    query: &[f32],
    database: &[Vec<f32>],
    coarse_dim: usize,
    shortlist: usize,
    k: usize,
) -> Vec<(usize, f32)> {
    if database.is_empty() {
        return Vec::new();
    }
    // 1. coarse ranking on truncated vectors.
    let q_coarse = truncate(query, coarse_dim);
    let mut coarse: Vec<(usize, f32)> = database
        .iter()
        .enumerate()
        .map(|(i, row)| (i, cosine(&q_coarse, &truncate(row, coarse_dim))))
        .collect();
    coarse.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
    coarse.truncate(shortlist.max(k));

    // 2. rerank the shortlist at full dimension.
    let mut fine: Vec<(usize, f32)> = coarse
        .into_iter()
        .map(|(i, _)| (i, cosine(query, &database[i])))
        .collect();
    fine.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
    fine.truncate(k);
    fine
}

/// The storage saving from using `dim` of `full_dim` dimensions: `1 − dim/full`.
pub fn storage_saving(dim: usize, full_dim: usize) -> f64 {
    if full_dim == 0 {
        0.0
    } else {
        1.0 - (dim.min(full_dim) as f64 / full_dim as f64)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f32, b: f32) -> bool {
        (a - b).abs() < 1e-5
    }

    #[test]
    fn truncate_takes_prefix_and_normalizes() {
        let e = [3.0, 4.0, 1.0, 1.0];
        let t = truncate(&e, 2);
        // [3,4] normalized → [0.6, 0.8]
        assert_eq!(t.len(), 2);
        assert!(approx(t[0], 0.6) && approx(t[1], 0.8));
        // unit length
        let norm: f32 = t.iter().map(|x| x * x).sum::<f32>().sqrt();
        assert!(approx(norm, 1.0));
    }

    #[test]
    fn truncate_clamps_and_handles_zero() {
        let e = [1.0, 2.0];
        assert_eq!(truncate(&e, 10).len(), 2); // clamped to len
        assert_eq!(truncate(&[0.0, 0.0], 2), vec![0.0, 0.0]); // zero norm
    }

    #[test]
    fn truncate_levels_multiple() {
        let e = [1.0, 1.0, 1.0, 1.0];
        let levels = truncate_levels(&e, &[1, 2, 4]);
        assert_eq!(levels.len(), 3);
        assert_eq!(levels[0].len(), 1);
        assert_eq!(levels[2].len(), 4);
    }

    #[test]
    fn cosine_basics() {
        assert!(approx(cosine(&[1.0, 0.0], &[1.0, 0.0]), 1.0));
        assert!(cosine(&[1.0, 0.0], &[0.0, 1.0]).abs() < 1e-6);
    }

    #[test]
    fn coarse_to_fine_finds_true_neighbor() {
        // 4-D vectors where the coarse prefix already separates the clusters.
        let db = vec![
            vec![1.0, 0.0, 0.1, 0.0], // cluster A
            vec![0.9, 0.1, 0.0, 0.1], // cluster A
            vec![0.0, 1.0, 0.0, 0.1], // cluster B
            vec![0.1, 0.9, 0.1, 0.0], // cluster B
        ];
        let query = vec![1.0, 0.05, 0.0, 0.0]; // closest to cluster A
        let result = coarse_to_fine(&query, &db, 2, 3, 1);
        assert_eq!(result.len(), 1);
        // the top result should be one of the A-cluster rows (0 or 1)
        assert!(result[0].0 == 0 || result[0].0 == 1, "got {result:?}");
    }

    #[test]
    fn coarse_to_fine_matches_brute_force_top1() {
        let db = vec![
            vec![1.0, 0.0, 0.0, 0.0],
            vec![0.0, 1.0, 0.0, 0.0],
            vec![0.0, 0.0, 1.0, 0.0],
            vec![0.7, 0.7, 0.0, 0.0],
        ];
        let query = vec![0.6, 0.8, 0.0, 0.0];
        // brute force full-dim nearest
        let brute = db
            .iter()
            .enumerate()
            .max_by(|a, b| cosine(&query, a.1).total_cmp(&cosine(&query, b.1)))
            .unwrap()
            .0;
        // with a generous shortlist, coarse-to-fine recovers the exact top-1
        let result = coarse_to_fine(&query, &db, 2, 4, 1);
        assert_eq!(result[0].0, brute);
    }

    #[test]
    fn storage_saving_math() {
        assert!((storage_saving(64, 1024) - 0.9375).abs() < 1e-9);
        assert_eq!(storage_saving(1024, 1024), 0.0);
        assert_eq!(storage_saving(64, 0), 0.0);
    }

    #[test]
    fn empty_database() {
        assert!(coarse_to_fine(&[1.0, 2.0], &[], 1, 5, 3).is_empty());
    }
}
