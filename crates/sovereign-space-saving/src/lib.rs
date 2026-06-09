//! `sovereign-space-saving` — the top-k of a stream in fixed memory, deterministically.
//!
//! "Which `k` items show up most often?" over a stream too large to count exactly is
//! the frequent-items problem. A [Count-Min sketch][crate] answers it
//! probabilistically with hashing; **Space-Saving** (Metwally, Agrawal & El Abbadi)
//! answers it *deterministically* with `k` counters and a single, elegant rule.
//!
//! Keep at most `capacity` counters. Each item seen that is already tracked just
//! increments its counter. An untracked item, when there is room, gets its own
//! counter. When there is no room, it **evicts the current minimum**: the new item
//! takes over that slot, its counter set to the evicted minimum *plus one*, and the
//! minimum value is remembered as that counter's **over-estimate error**. So a
//! counter says "this item's true count is somewhere in `[count − error, count]`",
//! and the guarantee that follows is strong: any item whose true frequency exceeds
//! `N / capacity` is certain to be in the summary, and no count is ever an
//! under-estimate.
//!
//! Eviction needs the current minimum fast, so counts are indexed by a bucket map;
//! the minimum item is chosen deterministically (smallest by `Ord`), making the
//! whole summary reproducible for a given stream. [`SpaceSaving::observe`] records
//! an item, [`SpaceSaving::top_k`] returns the most frequent with their counts and
//! error bounds, and [`SpaceSaving::estimate`] queries one item.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::hash::Hash;

/// Schema version of the Space-Saving surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A monitored item with its (over-)estimated count and the error bound.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Entry<T> {
    /// The item.
    pub item: T,
    /// Estimated count: an upper bound on the true frequency.
    pub count: u64,
    /// Maximum amount `count` may over-estimate the truth (`true ∈ [count-error, count]`).
    pub error: u64,
}

/// A Space-Saving summary over items of type `T`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SpaceSaving<T: Ord + Hash + Clone> {
    capacity: usize,
    /// item -> (count, error)
    counters: HashMap<T, (u64, u64)>,
    /// count -> items currently at that count (for O(log k) minimum lookup).
    by_count: BTreeMap<u64, BTreeSet<T>>,
    /// total items observed.
    n: u64,
}

impl<T: Ord + Hash + Clone> SpaceSaving<T> {
    /// A summary tracking at most `capacity` items (clamped to at least 1).
    pub fn new(capacity: usize) -> Self {
        Self {
            capacity: capacity.max(1),
            counters: HashMap::new(),
            by_count: BTreeMap::new(),
            n: 0,
        }
    }

    /// The counter capacity.
    pub fn capacity(&self) -> usize {
        self.capacity
    }
    /// Total items observed.
    pub fn total(&self) -> u64 {
        self.n
    }
    /// Number of items currently tracked.
    pub fn len(&self) -> usize {
        self.counters.len()
    }
    /// Whether no items are tracked.
    pub fn is_empty(&self) -> bool {
        self.counters.is_empty()
    }

    /// Remove `item` from the `count` bucket, pruning the bucket if it empties.
    fn bucket_remove(&mut self, count: u64, item: &T) {
        if let Some(set) = self.by_count.get_mut(&count) {
            set.remove(item);
            if set.is_empty() {
                self.by_count.remove(&count);
            }
        }
    }

    /// Add `item` to the `count` bucket.
    fn bucket_add(&mut self, count: u64, item: T) {
        self.by_count.entry(count).or_default().insert(item);
    }

    /// Observe one occurrence of `item`.
    pub fn observe(&mut self, item: T) {
        self.observe_weighted(item, 1);
    }

    /// Observe `weight` occurrences of `item` at once.
    pub fn observe_weighted(&mut self, item: T, weight: u64) {
        if weight == 0 {
            return;
        }
        self.n += weight;

        if let Some(&(count, error)) = self.counters.get(&item) {
            // already tracked: bump its count.
            let new_count = count + weight;
            self.counters.insert(item.clone(), (new_count, error));
            self.bucket_remove(count, &item);
            self.bucket_add(new_count, item);
            return;
        }
        if self.counters.len() < self.capacity {
            // room for a fresh counter.
            self.counters.insert(item.clone(), (weight, 0));
            self.bucket_add(weight, item);
            return;
        }
        // full: evict the current minimum and inherit its count.
        let min_count = *self
            .by_count
            .keys()
            .next()
            .expect("non-empty when at capacity");
        let victim = self
            .by_count
            .get(&min_count)
            .and_then(|s| s.iter().next().cloned())
            .expect("min bucket is non-empty");
        self.counters.remove(&victim);
        self.bucket_remove(min_count, &victim);

        let new_count = min_count + weight;
        // the new item could have appeared up to `min_count` times already.
        self.counters.insert(item.clone(), (new_count, min_count));
        self.bucket_add(new_count, item);
    }

    /// The estimated count and error for `item`, if tracked.
    pub fn estimate(&self, item: &T) -> Option<Entry<T>> {
        self.counters.get(item).map(|&(count, error)| Entry {
            item: item.clone(),
            count,
            error,
        })
    }

    /// All tracked entries, highest count first (ties by item order).
    pub fn entries(&self) -> Vec<Entry<T>> {
        let mut v: Vec<Entry<T>> = self
            .counters
            .iter()
            .map(|(item, &(count, error))| Entry {
                item: item.clone(),
                count,
                error,
            })
            .collect();
        v.sort_by(|a, b| b.count.cmp(&a.count).then(a.item.cmp(&b.item)));
        v
    }

    /// The `k` most frequent tracked items, highest count first.
    pub fn top_k(&self, k: usize) -> Vec<Entry<T>> {
        let mut v = self.entries();
        v.truncate(k);
        v
    }

    /// Items guaranteed to occur more than `n_total / capacity` times are all
    /// present; this returns the tracked items whose *lower-bound* count
    /// (`count - error`) exceeds `threshold` — those that are certainly frequent.
    pub fn frequent(&self, threshold: u64) -> Vec<Entry<T>> {
        let mut v: Vec<Entry<T>> = self
            .entries()
            .into_iter()
            .filter(|e| e.count - e.error > threshold)
            .collect();
        v.sort_by(|a, b| b.count.cmp(&a.count).then(a.item.cmp(&b.item)));
        v
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn counts_of<T: Ord + Hash + Clone>(stream: &[T]) -> HashMap<T, u64> {
        let mut m = HashMap::new();
        for x in stream {
            *m.entry(x.clone()).or_insert(0) += 1;
        }
        m
    }

    #[test]
    fn exact_when_within_capacity() {
        // distinct items <= capacity → no eviction → exact counts, zero error.
        let mut ss = SpaceSaving::new(5);
        for x in [1u32, 1, 2, 3, 3, 3] {
            ss.observe(x);
        }
        assert_eq!(ss.estimate(&3).unwrap().count, 3);
        assert_eq!(ss.estimate(&3).unwrap().error, 0);
        assert_eq!(ss.estimate(&1).unwrap().count, 2);
        assert_eq!(ss.total(), 6);
    }

    #[test]
    fn heavy_hitter_always_found() {
        // one dominant item amid many singletons; capacity small.
        let mut ss = SpaceSaving::new(4);
        let mut stream = vec![0u32; 100]; // the heavy hitter
        stream.extend(1..200u32); // noise singletons
        // shuffle deterministically by interleaving.
        stream.sort_by_key(|&x| (x.wrapping_mul(2654435761)) % 997);
        for x in &stream {
            ss.observe(*x);
        }
        let top = ss.top_k(1);
        assert_eq!(top[0].item, 0);
        // its estimate is at least its true count (never under-counts).
        assert!(top[0].count >= 100);
    }

    #[test]
    fn never_undercounts_and_error_bounds_truth() {
        let mut ss = SpaceSaving::new(8);
        let mut stream = Vec::new();
        for i in 0..1000u32 {
            // a Zipf-ish stream: small ids frequent.
            let v = i % 50;
            stream.push(v);
            if v < 5 {
                stream.push(v); // boost the head
            }
        }
        let truth = counts_of(&stream);
        for x in &stream {
            ss.observe(*x);
        }
        for e in ss.entries() {
            let t = truth[&e.item];
            // upper bound: estimate never under-counts.
            assert!(e.count >= t, "item {} est {} < true {t}", e.item, e.count);
            // lower bound: true >= count - error.
            assert!(
                e.count - e.error <= t,
                "item {} lower {} > true {t}",
                e.item,
                e.count - e.error
            );
        }
    }

    #[test]
    fn error_at_most_n_over_capacity() {
        let mut ss = SpaceSaving::new(10);
        for i in 0..1000u32 {
            ss.observe(i % 100); // 100 distinct, capacity 10 → heavy eviction
        }
        let max_err = ss.entries().iter().map(|e| e.error).max().unwrap();
        // Space-Saving guarantee: error <= floor(N / capacity).
        assert!(
            max_err <= ss.total() / ss.capacity() as u64,
            "err {max_err}"
        );
    }

    #[test]
    fn capacity_respected() {
        let mut ss = SpaceSaving::new(3);
        for i in 0..50u32 {
            ss.observe(i);
        }
        assert!(ss.len() <= 3);
    }

    #[test]
    fn top_k_ordering() {
        let mut ss = SpaceSaving::new(5);
        for x in [1u32, 1, 1, 2, 2, 3] {
            ss.observe(x);
        }
        let top = ss.top_k(2);
        assert_eq!(top[0].item, 1);
        assert_eq!(top[0].count, 3);
        assert_eq!(top[1].item, 2);
    }

    #[test]
    fn frequent_filters_by_lower_bound() {
        let mut ss = SpaceSaving::new(10);
        for _ in 0..200 {
            ss.observe("a".to_string());
        }
        for i in 0..50 {
            ss.observe(format!("noise{i}"));
        }
        let freq = ss.frequent(50);
        assert!(freq.iter().any(|e| e.item == "a"));
        assert!(!freq.iter().any(|e| e.item.starts_with("noise")));
    }

    #[test]
    fn weighted_observe() {
        let mut ss = SpaceSaving::new(5);
        ss.observe_weighted(7u32, 100);
        ss.observe_weighted(8u32, 5);
        assert_eq!(ss.estimate(&7).unwrap().count, 100);
        assert_eq!(ss.total(), 105);
    }

    #[test]
    fn generic_over_strings() {
        let mut ss = SpaceSaving::new(3);
        for w in ["the", "the", "cat", "the", "dog", "cat"] {
            ss.observe(w.to_string());
        }
        assert_eq!(ss.top_k(1)[0].item, "the");
    }

    #[test]
    fn deterministic() {
        let stream: Vec<u32> = (0..500).map(|i| (i * 37) % 60).collect();
        let mut a = SpaceSaving::new(8);
        let mut b = SpaceSaving::new(8);
        for &x in &stream {
            a.observe(x);
            b.observe(x);
        }
        assert_eq!(a.entries(), b.entries());
    }

    #[test]
    fn serde_round_trip() {
        let mut ss = SpaceSaving::new(5);
        for x in [1u32, 1, 2, 3, 3, 3, 9, 9] {
            ss.observe(x);
        }
        let j = serde_json::to_string(&ss).unwrap();
        let back: SpaceSaving<u32> = serde_json::from_str(&j).unwrap();
        assert_eq!(ss, back);
        assert_eq!(ss.top_k(2), back.top_k(2));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
