//! `sovereign-weighted-reservoir` — sample by importance, in one pass.
//!
//! Uniform reservoir sampling keeps every stream item equally likely. Often you
//! want the opposite: keep *important* items more often — sample log lines by
//! severity, training examples by difficulty, generations by reward. That is
//! **weighted reservoir sampling**, and the elegant solution (Efraimidis &
//! Spirakis, the **A-Res** algorithm) is to give each item a random *key*
//! `u^(1/weight)` for `u` uniform in `(0, 1)`, and keep the `k` items with the
//! largest keys. Because a larger weight makes a large key more likely, heavy
//! items survive more often — and the whole thing runs in `O(k)` space and a
//! single pass, with no knowledge of the stream's length.
//!
//! [`WeightedReservoir::offer`] feeds an item with its weight; the reservoir keeps
//! the current best `k` (a min-heap on the keys, so the weakest is evicted in
//! `O(log k)`). [`samples`](WeightedReservoir::samples) reads the current sample.
//! Randomness is a seeded **splitmix64** generator, so a given seed and stream
//! always produce the same sample — reproducible for replay and testing.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the weighted-reservoir surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One kept item with its A-Res key.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct Keyed<T> {
    key: f64,
    item: T,
}

/// A weighted reservoir of capacity `k`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WeightedReservoir<T> {
    k: usize,
    /// kept items; maintained so `heap[0]` is the smallest key (the eviction
    /// candidate). A simple binary min-heap over the `key` field.
    heap: Vec<Keyed<T>>,
    seen: usize,
    rng: u64,
}

impl<T> WeightedReservoir<T> {
    /// A reservoir of capacity `k`, seeded with `seed`.
    ///
    /// # Panics
    /// Panics if `k == 0`.
    pub fn new(k: usize, seed: u64) -> Self {
        assert!(k > 0, "k must be > 0");
        Self {
            k,
            heap: Vec::with_capacity(k),
            seen: 0,
            rng: seed | 1,
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
    pub fn samples(&self) -> Vec<&T> {
        self.heap.iter().map(|e| &e.item).collect()
    }

    /// Consume the reservoir and return the sampled items.
    pub fn into_samples(self) -> Vec<T> {
        self.heap.into_iter().map(|e| e.item).collect()
    }

    fn next_unit(&mut self) -> f64 {
        self.rng = self.rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.rng;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^= z >> 31;
        // map to (0, 1): add 0.5 so it's never exactly 0.
        ((z >> 11) as f64 + 0.5) / (1u64 << 53) as f64
    }

    /// Offer `item` with `weight`. Non-positive weights are ignored (they would
    /// never be sampled). The item is kept if the reservoir has room or its A-Res
    /// key exceeds the current weakest key.
    pub fn offer(&mut self, item: T, weight: f64) {
        if weight <= 0.0 || !weight.is_finite() {
            return;
        }
        self.seen += 1;
        let u = self.next_unit();
        let key = u.powf(1.0 / weight); // u^(1/weight): larger weight → larger key
        if self.heap.len() < self.k {
            self.heap.push(Keyed { key, item });
            self.sift_up(self.heap.len() - 1);
        } else if key > self.heap[0].key {
            // replace the smallest-key item.
            self.heap[0] = Keyed { key, item };
            self.sift_down(0);
        }
    }

    fn sift_up(&mut self, mut i: usize) {
        while i > 0 {
            let parent = (i - 1) / 2;
            if self.heap[i].key < self.heap[parent].key {
                self.heap.swap(i, parent);
                i = parent;
            } else {
                break;
            }
        }
    }

    fn sift_down(&mut self, mut i: usize) {
        let n = self.heap.len();
        loop {
            let (l, r) = (2 * i + 1, 2 * i + 2);
            let mut smallest = i;
            if l < n && self.heap[l].key < self.heap[smallest].key {
                smallest = l;
            }
            if r < n && self.heap[r].key < self.heap[smallest].key {
                smallest = r;
            }
            if smallest == i {
                break;
            }
            self.heap.swap(i, smallest);
            i = smallest;
        }
    }
}

impl<T: Clone> WeightedReservoir<T> {
    /// Offer every `(item, weight)` of an iterator.
    pub fn extend<I: IntoIterator<Item = (T, f64)>>(&mut self, iter: I) {
        for (item, w) in iter {
            self.offer(item, w);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn keeps_all_when_fewer_than_k() {
        let mut r = WeightedReservoir::new(5, 1);
        for i in 0..3 {
            r.offer(i, 1.0);
        }
        assert_eq!(r.samples().len(), 3);
        let mut got = r.into_samples();
        got.sort();
        assert_eq!(got, vec![0, 1, 2]);
    }

    #[test]
    fn caps_at_k() {
        let mut r = WeightedReservoir::new(4, 42);
        for i in 0..1000 {
            r.offer(i, 1.0);
        }
        assert_eq!(r.samples().len(), 4);
        assert_eq!(r.seen(), 1000);
    }

    #[test]
    fn heavy_items_are_sampled_more_often() {
        // item 0 has 10x the weight of the others; over many independent runs it
        // should appear in the reservoir far more often.
        let n = 50usize;
        let k = 5usize;
        let trials = 3000usize;
        let mut counts: HashMap<usize, usize> = HashMap::new();
        for seed in 0..trials as u64 {
            let mut r = WeightedReservoir::new(k, seed.wrapping_mul(0x9E37_79B9) | 1);
            for i in 0..n {
                let w = if i == 0 { 10.0 } else { 1.0 };
                r.offer(i, w);
            }
            for &x in r.samples() {
                *counts.entry(x).or_insert(0) += 1;
            }
        }
        let heavy = *counts.get(&0).unwrap_or(&0);
        let avg_light: f64 = (1..n)
            .map(|i| *counts.get(&i).unwrap_or(&0) as f64)
            .sum::<f64>()
            / (n - 1) as f64;
        // the 10x-weight item should appear several times more often than a typical
        // light item.
        assert!(
            heavy as f64 > avg_light * 3.0,
            "heavy {heavy} light_avg {avg_light}"
        );
    }

    #[test]
    fn zero_and_negative_weights_ignored() {
        let mut r = WeightedReservoir::new(3, 7);
        r.offer("keep", 1.0);
        r.offer("skip0", 0.0);
        r.offer("skipneg", -5.0);
        let s = r.samples();
        assert_eq!(s, vec![&"keep"]);
        assert_eq!(r.seen(), 1); // only the valid offer counted
    }

    #[test]
    fn deterministic_for_seed() {
        let mut a = WeightedReservoir::new(5, 99);
        let mut b = WeightedReservoir::new(5, 99);
        for i in 0..200 {
            a.offer(i, (i % 5 + 1) as f64);
            b.offer(i, (i % 5 + 1) as f64);
        }
        let mut sa = a.into_samples();
        let mut sb = b.into_samples();
        sa.sort();
        sb.sort();
        assert_eq!(sa, sb);
    }

    #[test]
    fn extend_helper() {
        let mut r = WeightedReservoir::new(3, 1);
        r.extend((0..10).map(|i| (i, 1.0)));
        assert_eq!(r.samples().len(), 3);
    }

    #[test]
    fn serde_round_trip() {
        let mut r = WeightedReservoir::new(3, 5);
        for i in 0..10 {
            r.offer(i, 1.0);
        }
        let j = serde_json::to_string(&r).unwrap();
        let back: WeightedReservoir<i32> = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
