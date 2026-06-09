//! `sovereign-simhash` — one 64-bit fingerprint per document for fast dedup.
//!
//! Where MinHash estimates Jaccard set overlap with a vector of hashes, **SimHash**
//! (Charikar) collapses a whole document into a *single* 64-bit fingerprint such
//! that similar documents have fingerprints differing in few bits. It is a
//! random-hyperplane LSH for cosine similarity: each feature (a token or a
//! shingle, with a weight) is hashed to 64 bits, and for every bit position the
//! feature votes `+weight` if its hash has a 1 there and `−weight` if a 0; the
//! fingerprint's bit is 1 where the summed vote is positive. Each bit is thus the
//! sign of the feature set projected onto a fixed pseudo-random hyperplane, and
//! the probability two documents agree on a bit grows with their cosine
//! similarity — so the **Hamming distance** between fingerprints is a cheap
//! similarity estimate: `similarity ≈ 1 − hamming / 64`.
//!
//! The single-word fingerprint is the appeal: storing and comparing millions of
//! them is trivial, and near-duplicates can be found by bucketing on fingerprint
//! bits. Hashing is FNV-1a with an avalanche finalizer, so fingerprints are
//! deterministic and portable.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the simhash surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A 64-bit SimHash fingerprint.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct SimHash(pub u64);

impl SimHash {
    /// The raw fingerprint bits.
    pub fn bits(&self) -> u64 {
        self.0
    }

    /// The Hamming distance (number of differing bits) to `other`, in `0..=64`.
    pub fn hamming(&self, other: &SimHash) -> u32 {
        (self.0 ^ other.0).count_ones()
    }

    /// Estimated similarity to `other` in `[0.0, 1.0]`: `1 − hamming / 64`.
    pub fn similarity(&self, other: &SimHash) -> f64 {
        1.0 - self.hamming(other) as f64 / 64.0
    }

    /// Whether `other` is within `max_hamming` differing bits — the usual
    /// near-duplicate test.
    pub fn is_near(&self, other: &SimHash, max_hamming: u32) -> bool {
        self.hamming(other) <= max_hamming
    }
}

/// FNV-1a 64-bit hash with an avalanche finalizer (so each bit is well mixed).
fn hash_feature(s: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for b in s.bytes() {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h ^= h >> 33;
    h = h.wrapping_mul(0xff51_afd7_ed55_8ccd);
    h ^= h >> 33;
    h = h.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    h ^= h >> 33;
    h
}

/// Fold a set of weighted features into a fingerprint.
fn fingerprint<'a, I: IntoIterator<Item = (&'a str, i64)>>(features: I) -> SimHash {
    let mut votes = [0i64; 64];
    for (feature, weight) in features {
        let h = hash_feature(feature);
        for (bit, v) in votes.iter_mut().enumerate() {
            if (h >> bit) & 1 == 1 {
                *v += weight;
            } else {
                *v -= weight;
            }
        }
    }
    let mut bits = 0u64;
    for (bit, &v) in votes.iter().enumerate() {
        if v > 0 {
            bits |= 1 << bit;
        }
    }
    SimHash(bits)
}

/// Fingerprint a bag of tokens, each weighted by how often it occurs.
pub fn simhash_tokens<'a, I: IntoIterator<Item = &'a str>>(tokens: I) -> SimHash {
    use std::collections::HashMap;
    let mut weights: HashMap<&str, i64> = HashMap::new();
    for t in tokens {
        *weights.entry(t).or_insert(0) += 1;
    }
    fingerprint(weights)
}

/// Fingerprint text by its word `k`-shingles (windows of `k` consecutive
/// whitespace tokens), weighted by frequency. Shingling captures local word
/// order so reordered or lightly edited text stays close. With fewer than `k`
/// tokens the whole token sequence is one shingle.
///
/// # Panics
/// Panics if `k == 0`.
pub fn simhash_text(text: &str, k: usize) -> SimHash {
    assert!(k > 0, "shingle size must be > 0");
    let tokens: Vec<&str> = text.split_whitespace().collect();
    if tokens.is_empty() {
        return SimHash(0);
    }
    if tokens.len() < k {
        return simhash_tokens(std::iter::once(text));
    }
    let shingles: Vec<String> = tokens.windows(k).map(|w| w.join(" ")).collect();
    simhash_tokens(shingles.iter().map(String::as_str))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identical_inputs_have_identical_fingerprints() {
        let a = simhash_text("the quick brown fox jumps over the lazy dog", 2);
        let b = simhash_text("the quick brown fox jumps over the lazy dog", 2);
        assert_eq!(a, b);
        assert_eq!(a.hamming(&b), 0);
        assert_eq!(a.similarity(&b), 1.0);
    }

    #[test]
    fn token_order_independent_for_bag_of_tokens() {
        let a = simhash_tokens(["alpha", "beta", "gamma", "delta"]);
        let b = simhash_tokens(["delta", "gamma", "beta", "alpha"]);
        assert_eq!(a, b); // bag of tokens ignores order
    }

    #[test]
    fn near_duplicate_text_has_small_hamming() {
        let original = "the cat sat on the warm mat beside the glowing fire tonight";
        let edited = "the cat sat on the warm mat beside the glowing fire today"; // 1 word
        let a = simhash_text(original, 2);
        let b = simhash_text(edited, 2);
        // a single edited word flips only a modest number of bits (it touches
        // the two shingles containing that word), far fewer than unrelated text.
        assert!(a.hamming(&b) < 16, "hamming {}", a.hamming(&b));
        assert!(a.similarity(&b) > 0.75, "sim {}", a.similarity(&b));
        assert!(a.is_near(&b, 16));
    }

    #[test]
    fn unrelated_text_has_large_hamming() {
        let a = simhash_text(
            "quarterly revenue exceeded analyst expectations again this year",
            2,
        );
        let b = simhash_text(
            "the migratory birds returned to the northern wetlands in spring",
            2,
        );
        // unrelated docs should differ in a substantial fraction of bits
        assert!(a.hamming(&b) > 18, "hamming {}", a.hamming(&b));
        assert!(a.similarity(&b) < 0.75, "sim {}", a.similarity(&b));
    }

    #[test]
    fn near_beats_unrelated() {
        let base = "machine learning models require large amounts of training data to generalize";
        let near = "machine learning models need large amounts of training data to generalize";
        let far = "the chef prepared a delicate sauce for the evening banquet downtown";
        let b = simhash_text(base, 2);
        let n = simhash_text(near, 2);
        let f = simhash_text(far, 2);
        assert!(
            b.hamming(&n) < b.hamming(&f),
            "near {} far {}",
            b.hamming(&n),
            b.hamming(&f)
        );
    }

    #[test]
    fn hamming_and_similarity_are_consistent() {
        let a = SimHash(0b1010);
        let b = SimHash(0b1001);
        assert_eq!(a.hamming(&b), 2); // bits 0 and 1 differ
        assert!((a.similarity(&b) - (1.0 - 2.0 / 64.0)).abs() < 1e-12);
    }

    #[test]
    fn empty_text_is_zero() {
        assert_eq!(simhash_text("   ", 2), SimHash(0));
    }

    #[test]
    fn serde_round_trip() {
        let h = simhash_text("some representative document text here", 2);
        let j = serde_json::to_string(&h).unwrap();
        let back: SimHash = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
