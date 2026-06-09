//! `sovereign-reservoir` — uniform sampling from an unbounded stream.
//!
//! To keep a representative sample of logs, traces, or generations you can't
//! buffer the whole stream — it's unbounded and you only want `k` of them.
//! Reservoir sampling (Vitter's Algorithm R) maintains a uniform random sample
//! of size `k` in `O(k)` space, in a single pass, without ever knowing the
//! stream's length: the `i`-th item (0-based) replaces a random reservoir slot
//! with probability `k/(i+1)`, which keeps every item seen so far equally
//! likely to be in the reservoir.
//!
//! Randomness comes from a built-in seeded **splitmix64** generator, so the
//! sampler is deterministic and serializable — the same seed and stream always
//! yield the same sample, which matters for reproducible diagnostics and replay.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the reservoir surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A reservoir sampler holding up to `k` items.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Reservoir<T> {
    k: usize,
    seen: usize,
    samples: Vec<T>,
    rng: u64,
}

impl<T> Reservoir<T> {
    /// A reservoir of capacity `k` seeded with `seed`.
    ///
    /// # Panics
    /// Panics if `k == 0`.
    pub fn new(k: usize, seed: u64) -> Self {
        assert!(k > 0, "k must be > 0");
        Self {
            k,
            seen: 0,
            samples: Vec::with_capacity(k),
            rng: seed,
        }
    }

    /// Reservoir capacity.
    pub fn capacity(&self) -> usize {
        self.k
    }

    /// Total items offered so far.
    pub fn seen(&self) -> usize {
        self.seen
    }

    /// The current sample.
    pub fn samples(&self) -> &[T] {
        &self.samples
    }

    /// Consume and return the sample.
    pub fn into_samples(self) -> Vec<T> {
        self.samples
    }

    /// splitmix64 next value.
    fn next_u64(&mut self) -> u64 {
        self.rng = self.rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.rng;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Offer `item` to the reservoir. While fewer than `k` items have been
    /// offered it is always kept; afterward it replaces a random slot with
    /// probability `k/(seen+1)`.
    pub fn offer(&mut self, item: T) {
        if self.samples.len() < self.k {
            self.samples.push(item);
        } else {
            let j = (self.next_u64() % (self.seen as u64 + 1)) as usize;
            if j < self.k {
                self.samples[j] = item;
            }
        }
        self.seen += 1;
    }

    /// Offer every item of an iterator.
    pub fn extend<I: IntoIterator<Item = T>>(&mut self, iter: I) {
        for item in iter {
            self.offer(item);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn keeps_all_when_fewer_than_k() {
        let mut r = Reservoir::new(5, 1);
        r.extend(1..=3);
        assert_eq!(r.samples().len(), 3);
        assert_eq!(r.seen(), 3);
        let mut got = r.into_samples();
        got.sort();
        assert_eq!(got, vec![1, 2, 3]);
    }

    #[test]
    fn keeps_exactly_k_when_equal() {
        let mut r = Reservoir::new(3, 7);
        r.extend(1..=3);
        let mut got = r.into_samples();
        got.sort();
        assert_eq!(got, vec![1, 2, 3]);
    }

    #[test]
    fn caps_at_k_for_a_long_stream() {
        let mut r = Reservoir::new(4, 42);
        r.extend(0..1000);
        assert_eq!(r.samples().len(), 4);
        assert_eq!(r.seen(), 1000);
        // every sample came from the stream
        assert!(r.samples().iter().all(|&x| (0..1000).contains(&x)));
    }

    #[test]
    fn is_deterministic_for_a_seed() {
        let mut a = Reservoir::new(5, 99);
        let mut b = Reservoir::new(5, 99);
        a.extend(0..500);
        b.extend(0..500);
        assert_eq!(a.samples(), b.samples());
    }

    #[test]
    fn different_seeds_differ() {
        let mut a = Reservoir::new(5, 1);
        let mut b = Reservoir::new(5, 2);
        a.extend(0..500);
        b.extend(0..500);
        assert_ne!(a.samples(), b.samples());
    }

    #[test]
    fn sampling_is_roughly_uniform() {
        // over many independent runs, each of N items should appear ~k/N of the
        // time; check the spread is reasonable (not a strict statistical test).
        let n = 20usize;
        let k = 4usize;
        let trials = 4000usize;
        let mut counts: HashMap<usize, usize> = HashMap::new();
        for seed in 0..trials as u64 {
            let mut r = Reservoir::new(k, seed.wrapping_mul(0x9E37_79B9));
            r.extend(0..n);
            for &x in r.samples() {
                *counts.entry(x).or_insert(0) += 1;
            }
        }
        let expected = (trials * k) as f64 / n as f64; // = 800
        for i in 0..n {
            let c = *counts.get(&i).unwrap_or(&0) as f64;
            // within ±25% of expected — generous, just catches gross bias
            assert!(
                (c - expected).abs() / expected < 0.25,
                "item {i}: count {c} vs expected {expected}"
            );
        }
    }

    #[test]
    fn serde_round_trip() {
        let mut r = Reservoir::new(3, 5);
        r.extend(0..10);
        let j = serde_json::to_string(&r).unwrap();
        let back: Reservoir<i32> = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
