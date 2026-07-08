//! `sovereign-count-min` — streaming frequency estimation in fixed memory.
//!
//! To penalise tokens by how often they have already appeared, or to find the
//! heavy hitters in a long stream, you need per-item counts — but storing an
//! exact count for every distinct item can blow past the memory budget when the
//! stream is huge and the alphabet large. A **Count-Min Sketch** keeps a fixed
//! `depth × width` grid of counters instead: each item is hashed by `depth`
//! independent functions to one counter per row, and adding the item increments
//! all `depth` of them. The estimate for an item is the **minimum** of its
//! counters — because every collision can only push a counter *up*, the minimum
//! is the row least polluted by other items, so the sketch **never undercounts**
//! and overcounts by a bounded amount.
//!
//! Sizing follows the standard bounds: `width = ⌈e / ε⌉` and `depth = ⌈ln(1/δ)⌉`
//! give, with probability `1 − δ`, an overestimate of at most `ε · N` over a
//! stream of total weight `N`. [`CountMinSketch::with_error`] computes those
//! dimensions for you; [`CountMinSketch::new`] takes them directly.
//!
//! The `depth` hash functions come from FNV-1a double hashing seeded per row, so
//! the sketch is deterministic and serializable. Counts are `u64` and saturate
//! rather than overflow.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the count-min surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A Count-Min Sketch: `depth` rows of `width` `u64` counters.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CountMinSketch {
    depth: usize,
    width: usize,
    /// row-major counters, length `depth * width`.
    counts: Vec<u64>,
    /// total weight added (the stream's `N`).
    total: u64,
}

impl CountMinSketch {
    /// A sketch with `depth` rows and `width` counters per row.
    ///
    /// # Panics
    /// Panics if `depth == 0` or `width == 0`.
    pub fn new(depth: usize, width: usize) -> Self {
        assert!(depth > 0 && width > 0, "depth and width must be > 0");
        Self {
            depth,
            width,
            counts: vec![0; depth * width],
            total: 0,
        }
    }

    /// A sketch sized so that, with probability at least `1 − delta`, the
    /// over-estimate is at most `epsilon · N`.
    ///
    /// # Panics
    /// Panics unless `0 < epsilon < 1` and `0 < delta < 1`.
    pub fn with_error(epsilon: f64, delta: f64) -> Self {
        assert!(epsilon > 0.0 && epsilon < 1.0, "epsilon must be in (0, 1)");
        assert!(delta > 0.0 && delta < 1.0, "delta must be in (0, 1)");
        let width = (std::f64::consts::E / epsilon).ceil() as usize;
        let depth = (1.0 / delta).ln().ceil() as usize;
        Self::new(depth.max(1), width.max(1))
    }

    /// Number of rows.
    pub fn depth(&self) -> usize {
        self.depth
    }

    /// Counters per row.
    pub fn width(&self) -> usize {
        self.width
    }

    /// Total weight added so far.
    pub fn total(&self) -> u64 {
        self.total
    }

    /// FNV-1a 64-bit base hash of a key.
    fn fnv1a(key: &[u8]) -> u64 {
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        for &b in key {
            h ^= b as u64;
            h = h.wrapping_mul(0x0000_0100_0000_01b3);
        }
        h
    }

    /// Two (near-)independent 64-bit hashes of `key` for Kirsch-Mitzenmacher
    /// double hashing: `h1` is FNV-1a, `h2` is a Murmur3 finalizer of `h1` (a
    /// strong bit-mixer), forced odd so the row functions stay distinct.
    fn hash_pair(key: &[u8]) -> (u64, u64) {
        let h1 = Self::fnv1a(key);
        let mut h2 = h1;
        h2 ^= h2 >> 33;
        h2 = h2.wrapping_mul(0xff51_afd7_ed55_8ccd);
        h2 ^= h2 >> 33;
        h2 = h2.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
        h2 ^= h2 >> 33;
        (h1, h2 | 1)
    }

    /// The column in row `row` for the hash pair `(h1, h2)`.
    fn column(&self, row: usize, h1: u64, h2: u64) -> usize {
        let combined = h1.wrapping_add((row as u64).wrapping_mul(h2));
        (combined % self.width as u64) as usize
    }

    /// Add `count` occurrences of `key`.
    pub fn add(&mut self, key: &[u8], count: u64) {
        let (h1, h2) = Self::hash_pair(key);
        for row in 0..self.depth {
            let col = self.column(row, h1, h2);
            let idx = row * self.width + col;
            self.counts[idx] = self.counts[idx].saturating_add(count);
        }
        self.total = self.total.saturating_add(count);
    }

    /// Add one occurrence of `key`.
    pub fn increment(&mut self, key: &[u8]) {
        self.add(key, 1);
    }

    /// Add one occurrence of a string key.
    pub fn increment_str(&mut self, key: &str) {
        self.add(key.as_bytes(), 1);
    }

    /// The estimated count of `key`: the minimum across its rows. Never less than
    /// the true count; over by a bounded amount.
    pub fn estimate(&self, key: &[u8]) -> u64 {
        let (h1, h2) = Self::hash_pair(key);
        (0..self.depth)
            .map(|row| self.counts[row * self.width + self.column(row, h1, h2)])
            .min()
            .unwrap_or(0)
    }

    /// The estimated count of a string key.
    pub fn estimate_str(&self, key: &str) -> u64 {
        self.estimate(key.as_bytes())
    }

    /// Merge another sketch of identical dimensions into this one (summing
    /// counters) — for combining sketches built over stream shards.
    ///
    /// # Panics
    /// Panics if the dimensions differ.
    pub fn merge(&mut self, other: &CountMinSketch) {
        assert_eq!(self.depth, other.depth, "depth mismatch");
        assert_eq!(self.width, other.width, "width mismatch");
        for (a, b) in self.counts.iter_mut().zip(other.counts.iter()) {
            *a = a.saturating_add(*b);
        }
        self.total = self.total.saturating_add(other.total);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn never_undercounts() {
        let mut cms = CountMinSketch::new(4, 64);
        let truth = [("apple", 10u64), ("banana", 3), ("cherry", 25), ("date", 1)];
        for &(k, n) in &truth {
            cms.add(k.as_bytes(), n);
        }
        for &(k, n) in &truth {
            assert!(cms.estimate_str(k) >= n, "{k}: est < true");
        }
        assert_eq!(cms.total(), 39);
    }

    #[test]
    fn exact_when_no_collisions_fit() {
        // a wide sketch over few distinct items should be exact in practice
        let mut cms = CountMinSketch::new(5, 1024);
        for _ in 0..7 {
            cms.increment_str("x");
        }
        for _ in 0..3 {
            cms.increment_str("y");
        }
        assert_eq!(cms.estimate_str("x"), 7);
        assert_eq!(cms.estimate_str("y"), 3);
        // an unseen key estimates 0 (no collisions in a wide sketch)
        assert_eq!(cms.estimate_str("z"), 0);
    }

    #[test]
    fn error_stays_within_bound_on_a_skewed_stream() {
        // Zipf-ish stream: item i appears (100 - i) times for i in 0..100.
        let n: u64 = (1..=100).sum();
        let cms_eps = 0.01;
        let mut cms = CountMinSketch::with_error(cms_eps, 0.01);
        let mut truth = vec![0u64; 100];
        for i in 0..100u64 {
            let times = 100 - i;
            truth[i as usize] = times;
            cms.add(format!("item{i}").as_bytes(), times);
        }
        // CMS guarantees: (a) it NEVER undercounts — hard, holds for every item;
        // (b) the overcount exceeds eps*N only with probability <= delta per
        // query, so over 100 queries only a small fraction may breach the slack.
        let slack = (cms_eps * n as f64).ceil() as u64;
        let mut breaches = 0;
        for i in 0..100 {
            let est = cms.estimate_str(&format!("item{i}"));
            assert!(est >= truth[i as usize], "item{i} undercounted"); // (a)
            if est > truth[i as usize] + slack {
                breaches += 1; // (b)
            }
        }
        // delta = 0.01 over 100 queries → expect ~1; allow generous headroom for
        // finite-hash effects without letting the bound be meaningless.
        assert!(breaches <= 5, "{breaches} of 100 exceeded the eps*N slack");
    }

    #[test]
    fn with_error_sizes_sensibly() {
        let cms = CountMinSketch::with_error(0.01, 0.01);
        // width ≈ ceil(e/0.01) = 272, depth ≈ ceil(ln 100) = 5
        assert_eq!(cms.width(), (std::f64::consts::E / 0.01).ceil() as usize);
        assert_eq!(cms.depth(), (1.0_f64 / 0.01).ln().ceil() as usize);
    }

    #[test]
    fn heavy_hitter_ranks_above_light_one() {
        let mut cms = CountMinSketch::with_error(0.001, 0.01);
        for _ in 0..1000 {
            cms.increment_str("frequent");
        }
        for _ in 0..5 {
            cms.increment_str("rare");
        }
        assert!(cms.estimate_str("frequent") > cms.estimate_str("rare"));
        assert!(cms.estimate_str("frequent") >= 1000);
    }

    #[test]
    fn merge_sums_counts() {
        let mut a = CountMinSketch::new(4, 128);
        let mut b = CountMinSketch::new(4, 128);
        a.add(b"k", 5);
        b.add(b"k", 8);
        a.merge(&b);
        assert!(a.estimate(b"k") >= 13);
        assert_eq!(a.total(), 13);
    }

    #[test]
    fn serde_round_trip() {
        let mut cms = CountMinSketch::new(3, 32);
        cms.add(b"hello", 4);
        let j = serde_json::to_string(&cms).unwrap();
        let back: CountMinSketch = serde_json::from_str(&j).unwrap();
        assert_eq!(cms, back);
        assert_eq!(back.estimate(b"hello"), 4);
    }
}
