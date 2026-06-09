//! `sovereign-bloom` — a Bloom filter for probabilistic membership.
//!
//! "Have I already seen this prompt / document / request id?" is a question a
//! runtime asks constantly — for dedup, cache priming, replay detection — and
//! storing every key to answer it exactly is wasteful. A Bloom filter answers
//! it in *constant* space with one guarantee that makes it safe to use:
//! **no false negatives**. If it says *absent*, the item was never inserted; if
//! it says *present*, the item is probably there (with a tunable false-positive
//! rate). You only ever pay the cost of a false *positive* (a redundant exact
//! check), never miss a real hit.
//!
//! [`BloomFilter::with_capacity`] sizes the bit array and hash count optimally
//! from the expected item count and target FP rate; membership uses FNV
//! double-hashing (`hᵢ = h₁ + i·h₂`), which is deterministic, so two filters
//! built the same way agree exactly.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the bloom surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A Bloom filter over byte keys.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BloomFilter {
    bits: Vec<u64>,
    num_bits: usize,
    num_hashes: u32,
    inserted: u64,
}

impl BloomFilter {
    /// A filter with an explicit bit count and hash count.
    ///
    /// # Panics
    /// Panics if `num_bits == 0` or `num_hashes == 0`.
    pub fn new(num_bits: usize, num_hashes: u32) -> Self {
        assert!(
            num_bits > 0 && num_hashes > 0,
            "num_bits/num_hashes must be > 0"
        );
        let words = num_bits.div_ceil(64);
        Self {
            bits: vec![0; words],
            num_bits,
            num_hashes,
            inserted: 0,
        }
    }

    /// A filter sized for `expected_items` at a target false-positive rate
    /// `fp_rate` in `(0, 1)`.
    ///
    /// # Panics
    /// Panics if `expected_items == 0` or `fp_rate` is not in `(0, 1)`.
    pub fn with_capacity(expected_items: usize, fp_rate: f64) -> Self {
        assert!(expected_items > 0, "expected_items must be > 0");
        assert!(fp_rate > 0.0 && fp_rate < 1.0, "fp_rate must be in (0, 1)");
        let n = expected_items as f64;
        let ln2 = std::f64::consts::LN_2;
        // m = -n ln p / (ln2)^2 ; k = (m/n) ln2
        let m = (-n * fp_rate.ln() / (ln2 * ln2)).ceil().max(1.0) as usize;
        let k = ((m as f64 / n) * ln2).round().max(1.0) as u32;
        Self::new(m, k)
    }

    /// Bit capacity.
    pub fn num_bits(&self) -> usize {
        self.num_bits
    }

    /// Number of hash functions.
    pub fn num_hashes(&self) -> u32 {
        self.num_hashes
    }

    /// How many items have been inserted.
    pub fn inserted(&self) -> u64 {
        self.inserted
    }

    fn bit_indices(&self, key: &[u8]) -> impl Iterator<Item = usize> + '_ {
        let h1 = fnv1a(key, 0xcbf2_9ce4_8422_2325);
        let h2 = fnv1a(key, 0x100_0000_01b3) | 1; // odd, nonzero step
        let m = self.num_bits as u64;
        (0..self.num_hashes)
            .map(move |i| (h1.wrapping_add((i as u64).wrapping_mul(h2)) % m) as usize)
    }

    /// Insert `key`.
    pub fn insert(&mut self, key: &[u8]) {
        let indices: Vec<usize> = self.bit_indices(key).collect();
        for idx in indices {
            self.bits[idx / 64] |= 1 << (idx % 64);
        }
        self.inserted += 1;
    }

    /// Whether `key` is *probably present* (`true` may be a false positive) or
    /// *definitely absent* (`false` is exact).
    pub fn contains(&self, key: &[u8]) -> bool {
        self.bit_indices(key)
            .all(|idx| self.bits[idx / 64] & (1 << (idx % 64)) != 0)
    }

    /// Insert a string key.
    pub fn insert_str(&mut self, s: &str) {
        self.insert(s.as_bytes());
    }

    /// Membership for a string key.
    pub fn contains_str(&self, s: &str) -> bool {
        self.contains(s.as_bytes())
    }
}

/// FNV-1a 64-bit with a seed/offset basis.
fn fnv1a(bytes: &[u8], basis: u64) -> u64 {
    let mut h = basis;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inserted_items_are_present_no_false_negatives() {
        let mut bf = BloomFilter::with_capacity(1000, 0.01);
        for i in 0..500 {
            bf.insert_str(&format!("item-{i}"));
        }
        // every inserted item must report present — the core guarantee
        for i in 0..500 {
            assert!(bf.contains_str(&format!("item-{i}")), "missing item-{i}");
        }
        assert_eq!(bf.inserted(), 500);
    }

    #[test]
    fn empty_filter_contains_nothing() {
        let bf = BloomFilter::new(1024, 4);
        assert!(!bf.contains_str("anything"));
    }

    #[test]
    fn false_positive_rate_is_near_target() {
        let mut bf = BloomFilter::with_capacity(1000, 0.01);
        for i in 0..1000 {
            bf.insert_str(&format!("present-{i}"));
        }
        // probe 5000 keys that were never inserted
        let mut fps = 0;
        for i in 0..5000 {
            if bf.contains_str(&format!("absent-{i}")) {
                fps += 1;
            }
        }
        let rate = fps as f64 / 5000.0;
        // generous bound: well under 5% for a 1% design target
        assert!(rate < 0.05, "fp rate {rate} too high");
    }

    #[test]
    fn with_capacity_sizes_sensibly() {
        let bf = BloomFilter::with_capacity(1000, 0.01);
        // ~9585 bits, ~7 hashes for 1% @ 1000 items
        assert!(
            bf.num_bits() > 9000 && bf.num_bits() < 10500,
            "{}",
            bf.num_bits()
        );
        assert!((6..=8).contains(&bf.num_hashes()), "{}", bf.num_hashes());
    }

    #[test]
    fn distinct_keys_set_distinct_bits() {
        let mut bf = BloomFilter::new(4096, 5);
        bf.insert_str("alpha");
        // a different, un-inserted key is (almost surely) absent here
        assert!(bf.contains_str("alpha"));
        assert!(!bf.contains_str("zzzzz-unlikely"));
    }

    #[test]
    fn serde_round_trip() {
        let mut bf = BloomFilter::with_capacity(100, 0.05);
        bf.insert_str("x");
        let j = serde_json::to_string(&bf).unwrap();
        let back: BloomFilter = serde_json::from_str(&j).unwrap();
        assert_eq!(bf, back);
        assert!(back.contains_str("x"));
    }
}
