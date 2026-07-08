//! `sovereign-fenwick` — prefix sums and sampling over a *changing* distribution.
//!
//! A static distribution can be sampled in `O(1)` with an alias table — but if
//! the weights keep changing (a frequency-penalized sampler that decrements a
//! token's weight each time it is emitted, a running rank/quantile over a
//! sliding window), rebuilding that table every update is `O(n)`. A **Fenwick
//! tree** (binary indexed tree) supports both a point update and a prefix-sum
//! query in `O(log n)`, and — the operation that makes it a sampler — a
//! cumulative-weight search ([`Fenwick::sample`]) that maps a target in
//! `[0, total)` to the index whose weight bucket contains it, also in
//! `O(log n)`.
//!
//! The structure exploits binary representation: index `i` (1-based internally)
//! stores the partial sum of the `lowbit(i)` elements ending at `i`, so a prefix
//! sum walks down by clearing the lowest set bit, an update walks up by adding
//! it, and the cumulative search lifts one bit at a time from the high end. The
//! public API is 0-indexed; weights are `i64` so the tree handles both counts and
//! signed adjustments (sampling assumes the current weights are non-negative).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the Fenwick surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A Fenwick tree over `n` slots, each holding an `i64` weight.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Fenwick {
    /// 1-indexed tree array of length `n + 1`; `tree[0]` is unused.
    tree: Vec<i64>,
}

impl Fenwick {
    /// A tree of `n` zero-weight slots.
    pub fn new(n: usize) -> Self {
        Self {
            tree: vec![0; n + 1],
        }
    }

    /// Build from initial weights in `O(n)` (faster than `n` updates).
    pub fn from_values(values: &[i64]) -> Self {
        let n = values.len();
        let mut tree = vec![0i64; n + 1];
        // 1-indexed in-place construction: push each value up to its parent.
        for (i, &v) in values.iter().enumerate() {
            let idx = i + 1;
            tree[idx] += v;
            let parent = idx + lowbit(idx);
            if parent <= n {
                let add = tree[idx];
                tree[parent] += add;
            }
        }
        Self { tree }
    }

    /// The number of slots.
    pub fn len(&self) -> usize {
        self.tree.len() - 1
    }

    /// Whether the tree has no slots.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Add `delta` to the weight at index `i`.
    ///
    /// # Panics
    /// Panics if `i >= len()`.
    pub fn add(&mut self, i: usize, delta: i64) {
        assert!(i < self.len(), "index out of range");
        let mut idx = i + 1;
        while idx <= self.len() {
            self.tree[idx] += delta;
            idx += lowbit(idx);
        }
    }

    /// Set the weight at index `i` to exactly `value`.
    pub fn set(&mut self, i: usize, value: i64) {
        let cur = self.get(i);
        self.add(i, value - cur);
    }

    /// The sum of weights over indices `[0, i)` (a *prefix* of `i` elements).
    /// `prefix_sum(0) == 0`; `prefix_sum(len()) == total()`.
    ///
    /// # Panics
    /// Panics if `i > len()`.
    pub fn prefix_sum(&self, i: usize) -> i64 {
        assert!(i <= self.len(), "prefix bound out of range");
        let mut idx = i;
        let mut sum = 0;
        while idx > 0 {
            sum += self.tree[idx];
            idx -= lowbit(idx);
        }
        sum
    }

    /// The sum over the half-open range `[lo, hi)`.
    ///
    /// # Panics
    /// Panics if `lo > hi` or `hi > len()`.
    pub fn range_sum(&self, lo: usize, hi: usize) -> i64 {
        assert!(lo <= hi, "lo must be <= hi");
        self.prefix_sum(hi) - self.prefix_sum(lo)
    }

    /// The weight currently at index `i`.
    pub fn get(&self, i: usize) -> i64 {
        self.range_sum(i, i + 1)
    }

    /// The total weight.
    pub fn total(&self) -> i64 {
        self.prefix_sum(self.len())
    }

    /// The smallest index `i` whose cumulative weight strictly exceeds `target`
    /// — i.e. `prefix_sum(i) <= target < prefix_sum(i+1)`. Drawing `target`
    /// uniformly from `[0, total())` and calling this samples index `i` with
    /// probability proportional to its weight, in `O(log n)`.
    ///
    /// Returns `None` if `target` is negative or `>= total()` (out of the
    /// sampleable range). Assumes all current weights are non-negative.
    pub fn sample(&self, target: i64) -> Option<usize> {
        if target < 0 || target >= self.total() {
            return None;
        }
        let n = self.len();
        let mut pos = 0usize; // 1-indexed position accumulator
        let mut remaining = target;
        // highest power of two <= n
        let mut bit = 1usize;
        while bit << 1 <= n {
            bit <<= 1;
        }
        while bit > 0 {
            let next = pos + bit;
            if next <= n && self.tree[next] <= remaining {
                pos = next;
                remaining -= self.tree[next];
            }
            bit >>= 1;
        }
        // pos is the count of elements fully consumed; the target falls in slot
        // `pos` (0-indexed), which is the answer.
        Some(pos)
    }
}

/// Lowest set bit of `x` (`x & (-x)` for unsigned via two's complement).
fn lowbit(x: usize) -> usize {
    x & x.wrapping_neg()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prefix_sums_match_naive() {
        let vals = [3, 1, 4, 1, 5, 9, 2, 6];
        let f = Fenwick::from_values(&vals);
        for i in 0..=vals.len() {
            let naive: i64 = vals[..i].iter().sum();
            assert_eq!(f.prefix_sum(i), naive, "prefix {i}");
        }
        assert_eq!(f.total(), vals.iter().sum::<i64>());
    }

    #[test]
    fn get_returns_individual_weights() {
        let vals = [10, 20, 30, 40];
        let f = Fenwick::from_values(&vals);
        for (i, &v) in vals.iter().enumerate() {
            assert_eq!(f.get(i), v);
        }
    }

    #[test]
    fn add_and_set_update_sums() {
        let mut f = Fenwick::from_values(&[1, 2, 3, 4, 5]);
        f.add(2, 10); // index 2: 3 -> 13
        assert_eq!(f.get(2), 13);
        assert_eq!(f.total(), 1 + 2 + 13 + 4 + 5);
        f.set(0, 100); // index 0: 1 -> 100
        assert_eq!(f.get(0), 100);
        assert_eq!(f.range_sum(0, 3), 100 + 2 + 13);
    }

    #[test]
    fn range_sum_is_consistent() {
        let vals = [5, 5, 5, 5, 5, 5];
        let f = Fenwick::from_values(&vals);
        assert_eq!(f.range_sum(1, 4), 15);
        assert_eq!(f.range_sum(0, 6), 30);
        assert_eq!(f.range_sum(3, 3), 0);
    }

    #[test]
    fn sample_selects_correct_bucket() {
        // weights [2, 0, 3, 1] → cumulative boundaries: [0,2)->0, [2,5)->2,
        // [5,6)->3 ; index 1 has weight 0 and is never selected.
        let f = Fenwick::from_values(&[2, 0, 3, 1]);
        assert_eq!(f.sample(0), Some(0));
        assert_eq!(f.sample(1), Some(0));
        assert_eq!(f.sample(2), Some(2));
        assert_eq!(f.sample(4), Some(2));
        assert_eq!(f.sample(5), Some(3));
        assert_eq!(f.sample(6), None); // == total, out of range
        assert_eq!(f.sample(-1), None);
    }

    #[test]
    fn sample_frequencies_are_proportional() {
        // sample many targets evenly across [0,total) and check the empirical
        // distribution matches the weights.
        let weights = [1i64, 2, 3, 4]; // total 10
        let f = Fenwick::from_values(&weights);
        let total = f.total();
        let mut counts = [0usize; 4];
        for t in 0..total {
            counts[f.sample(t).unwrap()] += 1;
        }
        // each index i selected exactly weights[i] times across the full sweep
        for i in 0..4 {
            assert_eq!(counts[i] as i64, weights[i], "bucket {i}");
        }
    }

    #[test]
    fn dynamic_updates_change_sampling() {
        // frequency-penalty style: zero out a bucket and confirm it stops being
        // sampled, and the others still cover the range.
        let mut f = Fenwick::from_values(&[5, 5, 5]);
        f.set(1, 0); // penalize index 1 to nothing
        assert_eq!(f.total(), 10);
        let mut seen_one = false;
        for t in 0..f.total() {
            if f.sample(t) == Some(1) {
                seen_one = true;
            }
        }
        assert!(!seen_one, "zero-weight index must not be sampled");
        // boost it back above the others
        f.set(1, 100);
        assert_eq!(f.sample(50), Some(1));
    }

    #[test]
    fn from_values_equals_repeated_add() {
        let vals = [7, 3, 9, 1, 4, 4, 2];
        let built = Fenwick::from_values(&vals);
        let mut added = Fenwick::new(vals.len());
        for (i, &v) in vals.iter().enumerate() {
            added.add(i, v);
        }
        assert_eq!(built, added);
    }

    #[test]
    fn empty_and_singleton() {
        let e = Fenwick::new(0);
        assert!(e.is_empty());
        assert_eq!(e.total(), 0);
        assert_eq!(e.sample(0), None);

        let mut s = Fenwick::new(1);
        s.set(0, 42);
        assert_eq!(s.total(), 42);
        assert_eq!(s.sample(0), Some(0));
        assert_eq!(s.sample(41), Some(0));
        assert_eq!(s.sample(42), None);
    }

    #[test]
    fn serde_round_trip() {
        let f = Fenwick::from_values(&[1, 2, 3, 4]);
        let j = serde_json::to_string(&f).unwrap();
        let back: Fenwick = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
        assert_eq!(back.total(), 10);
    }
}
