//! `sovereign-heavy-hitters` — the most frequent items, without keeping them all.
//!
//! "Which tokens does this stream use most?" over a corpus too large to hold is a
//! heavy-hitters problem. An exact answer needs a counter per distinct item; the
//! standard approximation pairs two fixed-memory structures. A
//! [`CountMinSketch`](sovereign_count_min) estimates *any* item's frequency in a
//! few kilobytes (it never undercounts), and a small **bounded set of candidates**
//! tracks the keys that have looked frequent so far. On each item the sketch is
//! incremented, the item's estimated count is read, and if that count beats the
//! weakest tracked candidate the candidate set is updated. The result is the
//! approximate top-`k` most frequent keys of the whole stream, in space
//! independent of the stream's length or alphabet.
//!
//! [`HeavyHitters::offer`] feeds one occurrence; [`HeavyHitters::offer_n`] a
//! weighted batch; [`HeavyHitters::top_k`] returns the tracked keys with their
//! estimated counts, most frequent first. Counts are *over-estimates* by the
//! sketch's bounded error, so two near-tied keys may swap — widen the sketch for
//! tighter ranking.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_count_min::CountMinSketch;
use std::collections::HashMap;

/// Schema version of the heavy-hitters surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// An approximate top-`k` frequent-item tracker over a stream.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HeavyHitters {
    sketch: CountMinSketch,
    k: usize,
    /// candidate key → its last estimated count.
    candidates: HashMap<String, u64>,
}

impl HeavyHitters {
    /// A tracker keeping the top `k` keys, using a Count-Min Sketch sized for the
    /// given error `epsilon` and confidence `delta`.
    ///
    /// # Panics
    /// Panics if `k == 0`.
    pub fn new(k: usize, epsilon: f64, delta: f64) -> Self {
        assert!(k > 0, "k must be > 0");
        Self {
            sketch: CountMinSketch::with_error(epsilon, delta),
            k,
            candidates: HashMap::with_capacity(k + 1),
        }
    }

    /// A tracker with an explicit sketch shape (`depth` rows × `width` counters).
    pub fn with_sketch(k: usize, depth: usize, width: usize) -> Self {
        assert!(k > 0, "k must be > 0");
        Self {
            sketch: CountMinSketch::new(depth, width),
            k,
            candidates: HashMap::with_capacity(k + 1),
        }
    }

    /// Total weight observed.
    pub fn total(&self) -> u64 {
        self.sketch.total()
    }

    /// The number of candidates currently tracked (≤ k).
    pub fn tracked(&self) -> usize {
        self.candidates.len()
    }

    /// The estimated count of `key` from the sketch (an over-estimate).
    pub fn estimate(&self, key: &str) -> u64 {
        self.sketch.estimate_str(key)
    }

    /// Observe `count` occurrences of `key`, updating the sketch and candidate set.
    pub fn offer_n(&mut self, key: &str, count: u64) {
        self.sketch.add(key.as_bytes(), count);
        let est = self.sketch.estimate_str(key);

        // already tracked → just refresh its count.
        if let Some(c) = self.candidates.get_mut(key) {
            *c = est;
            return;
        }
        // room to spare → add it.
        if self.candidates.len() < self.k {
            self.candidates.insert(key.to_string(), est);
            return;
        }
        // full → replace the weakest candidate if this one now beats it.
        if let Some((weak_key, weak_count)) = self
            .candidates
            .iter()
            .min_by(|a, b| a.1.cmp(b.1))
            .map(|(k, c)| (k.clone(), *c))
        {
            if est > weak_count {
                self.candidates.remove(&weak_key);
                self.candidates.insert(key.to_string(), est);
            }
        }
    }

    /// Observe one occurrence of `key`.
    pub fn offer(&mut self, key: &str) {
        self.offer_n(key, 1);
    }

    /// The tracked keys with their estimated counts, most frequent first (ties by
    /// key). At most `k` entries.
    pub fn top_k(&self) -> Vec<(String, u64)> {
        let mut out: Vec<(String, u64)> = self
            .candidates
            .iter()
            .map(|(k, &c)| (k.clone(), self.sketch.estimate_str(k).max(c)))
            .collect();
        out.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_the_frequent_items() {
        let mut hh = HeavyHitters::with_sketch(3, 5, 512);
        // "a" very frequent, "b" frequent, plus lots of rare noise.
        for _ in 0..1000 {
            hh.offer("a");
        }
        for _ in 0..500 {
            hh.offer("b");
        }
        for i in 0..2000 {
            hh.offer(&format!("noise{i}"));
        }
        let top = hh.top_k();
        let keys: Vec<&str> = top.iter().map(|(k, _)| k.as_str()).collect();
        assert!(keys.contains(&"a"), "top: {top:?}");
        assert!(keys.contains(&"b"), "top: {top:?}");
        // "a" should rank above "b"
        let a_rank = keys.iter().position(|&x| x == "a").unwrap();
        let b_rank = keys.iter().position(|&x| x == "b").unwrap();
        assert!(a_rank < b_rank);
    }

    #[test]
    fn respects_k_bound() {
        let mut hh = HeavyHitters::with_sketch(2, 4, 256);
        for c in ["x", "y", "z", "w"] {
            for _ in 0..(c.len() * 100) {
                hh.offer(c);
            }
        }
        assert!(hh.tracked() <= 2);
        assert!(hh.top_k().len() <= 2);
    }

    #[test]
    fn counts_are_at_least_true() {
        let mut hh = HeavyHitters::with_sketch(5, 5, 1024);
        for _ in 0..300 {
            hh.offer("token");
        }
        // count-min never undercounts
        assert!(hh.estimate("token") >= 300);
    }

    #[test]
    fn weighted_offers() {
        let mut hh = HeavyHitters::with_sketch(3, 4, 256);
        hh.offer_n("bulk", 5000);
        hh.offer_n("small", 3);
        let top = hh.top_k();
        assert_eq!(top[0].0, "bulk");
        assert!(top[0].1 >= 5000);
    }

    #[test]
    fn total_tracks_weight() {
        let mut hh = HeavyHitters::with_sketch(2, 4, 256);
        hh.offer("a");
        hh.offer_n("b", 10);
        assert_eq!(hh.total(), 11);
    }

    #[test]
    fn empty_tracker() {
        let hh = HeavyHitters::with_sketch(3, 4, 256);
        assert!(hh.top_k().is_empty());
        assert_eq!(hh.total(), 0);
    }

    #[test]
    fn serde_round_trip() {
        let mut hh = HeavyHitters::with_sketch(3, 4, 256);
        for _ in 0..50 {
            hh.offer("k");
        }
        let j = serde_json::to_string(&hh).unwrap();
        let back: HeavyHitters = serde_json::from_str(&j).unwrap();
        assert_eq!(hh, back);
        assert_eq!(back.top_k()[0].0, "k");
    }
}
