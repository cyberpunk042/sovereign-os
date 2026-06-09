//! `sovereign-minhash` — MinHash signatures for Jaccard-similarity estimation.
//!
//! Comparing two sets by their exact Jaccard similarity — `|A ∩ B| / |A ∪ B|` —
//! costs `O(|A| + |B|)` and needs both sets in hand. When the "sets" are the word
//! shingles of documents and you want to find near-duplicates among thousands of
//! retrieved chunks, that is too expensive to do pairwise. MinHash trades exact
//! similarity for a fixed-length *signature*: pick `n` hash functions; the `i`-th
//! signature slot is the minimum hash, under function `i`, over all elements of
//! the set. The key property is that for any one function the probability that
//! two sets share the same minimum equals their Jaccard similarity — so the
//! *fraction of equal slots* between two signatures is an unbiased estimate of
//! Jaccard, computable in `O(n)` regardless of set size.
//!
//! The `n` hash functions are a family of `h_i(x) = a_i * x + b_i (mod prime)`
//! over a 64-bit base hash of each element, with `a_i`, `b_i` drawn from a
//! seeded **splitmix64** generator. The same seed and dimension always produce
//! the same family, so signatures from different machines are comparable and the
//! whole thing is deterministic and serializable.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the minhash surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A large prime near 2^61 used as the modulus of the hash family.
const MERSENNE_61: u64 = (1 << 61) - 1;

/// A family of `n` hash functions sharing one seed.
///
/// Build it once and reuse it to sign every set you want to compare — two
/// signatures are only comparable if they came from the *same* family.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MinHasher {
    a: Vec<u64>,
    b: Vec<u64>,
}

impl MinHasher {
    /// A family of `n` hash functions seeded with `seed`.
    ///
    /// # Panics
    /// Panics if `n == 0`.
    pub fn new(n: usize, seed: u64) -> Self {
        assert!(n > 0, "signature dimension must be > 0");
        let mut rng = seed;
        let mut next = || {
            rng = rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = rng;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            z ^ (z >> 31)
        };
        let mut a = Vec::with_capacity(n);
        let mut b = Vec::with_capacity(n);
        for _ in 0..n {
            // a must be non-zero mod prime so the function is a bijection.
            a.push((next() % (MERSENNE_61 - 1)) + 1);
            b.push(next() % MERSENNE_61);
        }
        Self { a, b }
    }

    /// The signature length (number of hash functions).
    pub fn dimension(&self) -> usize {
        self.a.len()
    }

    /// Sign a set given as an iterator of already-hashed 64-bit element keys.
    ///
    /// Each slot `i` of the returned signature is `min_x (a_i * x + b_i mod p)`.
    /// An empty set yields an all-`u64::MAX` signature, which estimates a Jaccard
    /// of 0 against any non-empty set (and 1 against another empty signature).
    pub fn sign_hashes<I: IntoIterator<Item = u64>>(&self, elems: I) -> Signature {
        let n = self.dimension();
        let mut sig = vec![u64::MAX; n];
        for x in elems {
            let xm = x % MERSENNE_61;
            for i in 0..n {
                // (a*x + b) mod p with 128-bit intermediate to avoid overflow.
                let h = ((self.a[i] as u128 * xm as u128 + self.b[i] as u128) % MERSENNE_61 as u128)
                    as u64;
                if h < sig[i] {
                    sig[i] = h;
                }
            }
        }
        Signature(sig)
    }

    /// Sign a set of string elements, hashing each with FNV-1a first. Duplicate
    /// elements are harmless — MinHash is over the *set*, so they don't change
    /// the signature.
    pub fn sign<'a, I: IntoIterator<Item = &'a str>>(&self, elems: I) -> Signature {
        self.sign_hashes(elems.into_iter().map(fnv1a))
    }

    /// Sign the word-shingle set of `text`: every window of `k` consecutive
    /// whitespace-separated tokens becomes one element. Shingling captures local
    /// word order, so reordered or lightly edited text still scores high while
    /// unrelated text scores near zero. If the text has fewer than `k` tokens the
    /// whole token sequence is used as a single shingle.
    ///
    /// # Panics
    /// Panics if `k == 0`.
    pub fn sign_text(&self, text: &str, k: usize) -> Signature {
        assert!(k > 0, "shingle size must be > 0");
        let tokens: Vec<&str> = text.split_whitespace().collect();
        if tokens.is_empty() {
            return self.sign_hashes(std::iter::empty());
        }
        if tokens.len() < k {
            return self.sign(std::iter::once(tokens.join(" ").as_str()));
        }
        let shingles: Vec<u64> = tokens.windows(k).map(|w| fnv1a(&w.join(" "))).collect();
        self.sign_hashes(shingles)
    }
}

/// A MinHash signature: a fixed-length vector of minimum hashes.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Signature(Vec<u64>);

impl Signature {
    /// The signature slots.
    pub fn slots(&self) -> &[u64] {
        &self.0
    }

    /// The signature length.
    pub fn len(&self) -> usize {
        self.0.len()
    }

    /// Whether the signature has no slots.
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    /// Estimate the Jaccard similarity to `other` as the fraction of equal slots.
    ///
    /// Returns a value in `[0.0, 1.0]`.
    ///
    /// # Panics
    /// Panics if the signatures have different lengths (they came from different
    /// hash families and are not comparable).
    pub fn jaccard(&self, other: &Signature) -> f64 {
        assert_eq!(
            self.0.len(),
            other.0.len(),
            "signatures from different families are not comparable"
        );
        if self.0.is_empty() {
            return 0.0;
        }
        let equal = self
            .0
            .iter()
            .zip(other.0.iter())
            .filter(|(x, y)| x == y)
            .count();
        equal as f64 / self.0.len() as f64
    }
}

/// FNV-1a 64-bit hash of a string — the base element hash before the MinHash
/// family is applied.
pub fn fnv1a(s: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for byte in s.bytes() {
        h ^= byte as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

/// Exact Jaccard similarity of two string sets — for testing the estimate and
/// for small sets where exactness is cheap enough.
pub fn exact_jaccard(a: &[&str], b: &[&str]) -> f64 {
    use std::collections::HashSet;
    let sa: HashSet<&str> = a.iter().copied().collect();
    let sb: HashSet<&str> = b.iter().copied().collect();
    let inter = sa.intersection(&sb).count();
    let union = sa.union(&sb).count();
    if union == 0 {
        0.0
    } else {
        inter as f64 / union as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identical_sets_have_identical_signatures() {
        let mh = MinHasher::new(64, 1);
        let a = mh.sign(["the", "quick", "brown", "fox"]);
        let b = mh.sign(["fox", "the", "brown", "quick"]); // order irrelevant
        assert_eq!(a, b);
        assert_eq!(a.jaccard(&b), 1.0);
    }

    #[test]
    fn disjoint_sets_estimate_near_zero() {
        let mh = MinHasher::new(128, 7);
        let a = mh.sign(["a", "b", "c", "d", "e"]);
        let b = mh.sign(["v", "w", "x", "y", "z"]);
        assert!(a.jaccard(&b) < 0.05, "got {}", a.jaccard(&b));
    }

    #[test]
    fn estimate_tracks_exact_jaccard() {
        // two sets sharing 5 of 15 distinct elements → exact Jaccard 5/15 ≈ 0.333
        let a: Vec<String> = (0..10).map(|i| format!("x{i}")).collect();
        let mut b: Vec<String> = (5..10).map(|i| format!("x{i}")).collect(); // share x5..x9
        b.extend((10..15).map(|i| format!("x{i}")));
        let ar: Vec<&str> = a.iter().map(String::as_str).collect();
        let br: Vec<&str> = b.iter().map(String::as_str).collect();
        let exact = exact_jaccard(&ar, &br);
        assert!((exact - 0.333).abs() < 0.01, "exact {exact}");

        let mh = MinHasher::new(256, 42);
        let est = mh
            .sign(ar.iter().copied())
            .jaccard(&mh.sign(br.iter().copied()));
        // 256 hashes → estimate within ~0.1 of truth
        assert!((est - exact).abs() < 0.1, "est {est} vs exact {exact}");
    }

    #[test]
    fn more_hashes_reduce_error() {
        // build two sets with a known Jaccard and show the big signature is at
        // least as close as a tiny one, averaged over seeds.
        let a: Vec<String> = (0..20).map(|i| format!("e{i}")).collect();
        let b: Vec<String> = (10..30).map(|i| format!("e{i}")).collect(); // Jaccard 10/30
        let ar: Vec<&str> = a.iter().map(String::as_str).collect();
        let br: Vec<&str> = b.iter().map(String::as_str).collect();
        let exact = exact_jaccard(&ar, &br);

        let err = |n: usize| -> f64 {
            let mut total = 0.0;
            let trials = 20;
            for seed in 0..trials {
                let mh = MinHasher::new(n, seed as u64 * 1000 + 1);
                let est = mh
                    .sign(ar.iter().copied())
                    .jaccard(&mh.sign(br.iter().copied()));
                total += (est - exact).abs();
            }
            total / trials as f64
        };
        assert!(err(512) <= err(8) + 1e-9, "more hashes should not be worse");
    }

    #[test]
    fn near_duplicate_text_scores_high() {
        let mh = MinHasher::new(128, 3);
        let original = "the cat sat on the warm mat by the fire";
        let edited = "the cat sat on the warm mat near the fire"; // one word changed
        let unrelated = "quarterly revenue exceeded analyst expectations again";
        let sim_edit = mh.sign_text(original, 2).jaccard(&mh.sign_text(edited, 2));
        let sim_unrel = mh
            .sign_text(original, 2)
            .jaccard(&mh.sign_text(unrelated, 2));
        assert!(sim_edit > 0.5, "edited similarity {sim_edit}");
        assert!(sim_unrel < 0.1, "unrelated similarity {sim_unrel}");
        assert!(sim_edit > sim_unrel);
    }

    #[test]
    fn empty_set_behaviour() {
        let mh = MinHasher::new(32, 9);
        let empty = mh.sign(std::iter::empty());
        let nonempty = mh.sign(["a", "b"]);
        assert_eq!(empty.jaccard(&nonempty), 0.0);
        // two empties are identical signatures → but jaccard short-circuits to 0
        // only on empty *signatures*; here signatures are full of u64::MAX
        let empty2 = mh.sign(std::iter::empty());
        assert_eq!(empty.jaccard(&empty2), 1.0);
    }

    #[test]
    fn short_text_uses_whole_sequence() {
        let mh = MinHasher::new(16, 1);
        // fewer tokens than k → whole thing is one shingle; identical inputs match
        let a = mh.sign_text("hello world", 5);
        let b = mh.sign_text("hello world", 5);
        assert_eq!(a.jaccard(&b), 1.0);
    }

    #[test]
    fn deterministic_across_instances() {
        let a = MinHasher::new(64, 12345);
        let b = MinHasher::new(64, 12345);
        assert_eq!(a, b);
        assert_eq!(a.sign(["x", "y", "z"]), b.sign(["x", "y", "z"]));
    }

    #[test]
    fn serde_round_trip() {
        let mh = MinHasher::new(8, 1);
        let sig = mh.sign(["alpha", "beta"]);
        let jm = serde_json::to_string(&mh).unwrap();
        let js = serde_json::to_string(&sig).unwrap();
        assert_eq!(serde_json::from_str::<MinHasher>(&jm).unwrap(), mh);
        assert_eq!(serde_json::from_str::<Signature>(&js).unwrap(), sig);
    }

    #[test]
    fn fnv_is_stable() {
        assert_eq!(fnv1a(""), 0xcbf2_9ce4_8422_2325);
        assert_ne!(fnv1a("a"), fnv1a("b"));
    }
}
