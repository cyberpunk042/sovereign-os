//! `sovereign-binary-quant` — an embedding in a thirty-second of the space.
//!
//! Storing a 1024-dimension `f32` embedding costs 4 KiB; a billion of them is
//! terabytes. **Binary quantization** trades a little accuracy for a 32× cut: keep
//! only the *sign* of each component (`1` if positive, else `0`) and pack those
//! bits into `u64` words. Comparing two such codes is then a **Hamming
//! distance** — XOR the words and count the set bits with a hardware popcount —
//! which, for embeddings whose components are roughly centered, tracks cosine
//! similarity closely enough to *shortlist* candidates. The usual recipe is
//! exactly that: scan the binary codes to get a cheap shortlist, then rerank the
//! few survivors with the full-precision vectors.
//!
//! [`quantize`] packs a vector into a [`BinaryCode`]; [`BinaryCode::hamming`] and
//! [`BinaryCode::similarity`] compare two codes; [`search`] does the shortlist
//! scan over a code database. Quantizing around a learned mean ([`quantize_centered`])
//! improves the cosine correlation when components are biased.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the binary-quant surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A packed binary embedding code.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct BinaryCode {
    /// bit `i` (in word `i/64`, bit `i%64`) is the sign of component `i`.
    words: Vec<u64>,
    /// the original dimension (number of meaningful bits).
    dim: usize,
}

impl BinaryCode {
    /// The embedding dimension this code represents.
    pub fn dim(&self) -> usize {
        self.dim
    }

    /// The packed words.
    pub fn words(&self) -> &[u64] {
        &self.words
    }

    /// Whether component `i` was positive (bit set).
    pub fn bit(&self, i: usize) -> bool {
        if i >= self.dim {
            return false;
        }
        (self.words[i / 64] >> (i % 64)) & 1 == 1
    }

    /// Hamming distance to `other` (number of differing bits). Only the first
    /// `min(dim, other.dim)` bits are compared.
    pub fn hamming(&self, other: &BinaryCode) -> u32 {
        self.words
            .iter()
            .zip(other.words.iter())
            .map(|(a, b)| (a ^ b).count_ones())
            .sum()
    }

    /// Estimated cosine-like similarity in `[-1, 1]`: `1 − 2·hamming/dim`. Equal
    /// codes give `1.0`, opposite signs everywhere give `−1.0`.
    pub fn similarity(&self, other: &BinaryCode) -> f64 {
        let d = self.dim.min(other.dim).max(1);
        1.0 - 2.0 * self.hamming(other) as f64 / d as f64
    }
}

/// Quantize `embedding`: bit `i` is set iff `embedding[i] > 0`.
pub fn quantize(embedding: &[f32]) -> BinaryCode {
    quantize_centered(embedding, &[])
}

/// Quantize relative to a per-dimension `mean` (bit set iff `embedding[i] > mean[i]`).
/// A shorter or empty `mean` is treated as zeros for the missing dimensions.
pub fn quantize_centered(embedding: &[f32], mean: &[f32]) -> BinaryCode {
    let dim = embedding.len();
    let words = dim.div_ceil(64);
    let mut out = vec![0u64; words];
    for (i, &x) in embedding.iter().enumerate() {
        let m = mean.get(i).copied().unwrap_or(0.0);
        if x > m {
            out[i / 64] |= 1u64 << (i % 64);
        }
    }
    BinaryCode { words: out, dim }
}

/// Shortlist search: the `k` database codes nearest the `query` code by Hamming
/// distance, as `(index, hamming)` ascending (ties by index). This is the cheap
/// first stage; rerank the result with full-precision vectors.
pub fn search(query: &BinaryCode, database: &[BinaryCode], k: usize) -> Vec<(usize, u32)> {
    let mut scored: Vec<(usize, u32)> = database
        .iter()
        .enumerate()
        .map(|(i, c)| (i, query.hamming(c)))
        .collect();
    scored.sort_by(|a, b| a.1.cmp(&b.1).then(a.0.cmp(&b.0)));
    scored.truncate(k);
    scored
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quantize_packs_signs() {
        let e = [0.5, -0.2, 0.0, 1.0, -3.0];
        let c = quantize(&e);
        assert_eq!(c.dim(), 5);
        assert!(c.bit(0)); // 0.5 > 0
        assert!(!c.bit(1)); // -0.2
        assert!(!c.bit(2)); // 0.0 not > 0
        assert!(c.bit(3)); // 1.0
        assert!(!c.bit(4)); // -3.0
    }

    #[test]
    fn identical_codes_are_maximally_similar() {
        let e = [1.0, -1.0, 2.0, -2.0, 0.5];
        let a = quantize(&e);
        let b = quantize(&e);
        assert_eq!(a.hamming(&b), 0);
        assert!((a.similarity(&b) - 1.0).abs() < 1e-9);
    }

    #[test]
    fn opposite_signs_are_minimally_similar() {
        let e = [1.0, 1.0, 1.0, 1.0];
        let neg = [-1.0, -1.0, -1.0, -1.0];
        let a = quantize(&e);
        let b = quantize(&neg);
        assert_eq!(a.hamming(&b), 4);
        assert!((a.similarity(&b) + 1.0).abs() < 1e-9); // -1.0
    }

    #[test]
    fn similar_vectors_have_low_hamming() {
        // two vectors agreeing on most signs → small Hamming.
        let a = quantize(&[1.0, 1.0, 1.0, 1.0, -1.0, -1.0]);
        let b = quantize(&[1.0, 1.0, 1.0, -0.5, -1.0, -1.0]); // one sign flipped
        assert_eq!(a.hamming(&b), 1);
        assert!(a.similarity(&b) > 0.5);
    }

    #[test]
    fn multiword_codes() {
        // 100-dim vector spans two u64 words.
        let e: Vec<f32> = (0..100)
            .map(|i| if i % 2 == 0 { 1.0 } else { -1.0 })
            .collect();
        let c = quantize(&e);
        assert_eq!(c.words().len(), 2);
        assert!(c.bit(0) && !c.bit(1) && c.bit(98));
        let c2 = c.clone();
        assert_eq!(c.hamming(&c2), 0);
    }

    #[test]
    fn centered_quantization() {
        // with a mean of 5, only components above 5 set their bit.
        let e = [3.0, 7.0, 5.0, 10.0];
        let mean = [5.0, 5.0, 5.0, 5.0];
        let c = quantize_centered(&e, &mean);
        assert!(!c.bit(0)); // 3 < 5
        assert!(c.bit(1)); // 7 > 5
        assert!(!c.bit(2)); // 5 not > 5
        assert!(c.bit(3)); // 10 > 5
    }

    #[test]
    fn search_shortlists_nearest() {
        let db: Vec<BinaryCode> = [
            [1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, -1.0],
            [-1.0, -1.0, -1.0, -1.0],
            [1.0, -1.0, 1.0, -1.0],
        ]
        .iter()
        .map(|v| quantize(v))
        .collect();
        let query = quantize(&[1.0, 1.0, 1.0, 0.5]); // closest to db[0]
        let result = search(&query, &db, 2);
        assert_eq!(result[0].0, 0); // exact match, hamming 0
        assert_eq!(result[0].1, 0);
        assert_eq!(result.len(), 2);
    }

    #[test]
    fn empty_and_edge() {
        let c = quantize(&[]);
        assert_eq!(c.dim(), 0);
        assert!(c.words().is_empty());
        assert!(search(&quantize(&[1.0]), &[], 3).is_empty());
    }

    #[test]
    fn serde_round_trip() {
        let c = quantize(&[1.0, -1.0, 1.0, 1.0, -1.0]);
        let j = serde_json::to_string(&c).unwrap();
        let back: BinaryCode = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
