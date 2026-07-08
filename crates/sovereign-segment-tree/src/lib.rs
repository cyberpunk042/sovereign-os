//! `sovereign-segment-tree` — update a range and query a range, both in log time.
//!
//! A [Fenwick tree][crate] updates one position and queries a prefix. Plenty of
//! workloads need the dual power: add a value to *every* element in a range, and
//! ask for the sum (or min, or max) over *any* range — windowed throughput
//! accounting, interval reservations, range allocation. Doing the range-add
//! naively is `O(n)` per update. A **segment tree with lazy propagation** keeps
//! both the update and the query at `O(log n)`.
//!
//! The tree stores each range's aggregate at an internal node. A range-add does not
//! touch every leaf; instead it stops at the nodes that exactly cover the target
//! range and leaves a **lazy tag** there — "everything below me still owes this
//! increment". The tag is only pushed down to children when a later operation
//! actually needs to descend through that node, so pending updates accumulate and
//! apply just in time. Each node carries sum, min, and max together, so one tree
//! answers all three kinds of range query.
//!
//! [`SegmentTree::build`] initialises from a slice; [`SegmentTree::range_add`]
//! applies a delta to a half-open `[l, r)` range; and
//! [`range_sum`](SegmentTree::range_sum), [`range_min`](SegmentTree::range_min),
//! and [`range_max`](SegmentTree::range_max) query one. Point access is just a
//! width-one range.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the segment-tree surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A segment tree over `i64` values supporting range-add and range sum/min/max.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SegmentTree {
    n: usize,
    sum: Vec<i64>,
    min: Vec<i64>,
    max: Vec<i64>,
    lazy: Vec<i64>,
}

impl SegmentTree {
    /// Build a tree from `data` (empty input yields an empty tree).
    pub fn build(data: &[i64]) -> Self {
        let n = data.len();
        let size = 4 * n.max(1);
        let mut t = SegmentTree {
            n,
            sum: vec![0; size],
            min: vec![0; size],
            max: vec![0; size],
            lazy: vec![0; size],
        };
        if n > 0 {
            t.build_rec(1, 0, n, data);
        }
        t
    }

    /// A tree of `n` zeros.
    pub fn zeros(n: usize) -> Self {
        Self::build(&vec![0i64; n])
    }

    /// Number of elements.
    pub fn len(&self) -> usize {
        self.n
    }
    /// Whether the tree is empty.
    pub fn is_empty(&self) -> bool {
        self.n == 0
    }

    fn build_rec(&mut self, node: usize, lo: usize, hi: usize, data: &[i64]) {
        if hi - lo == 1 {
            self.sum[node] = data[lo];
            self.min[node] = data[lo];
            self.max[node] = data[lo];
            return;
        }
        let mid = (lo + hi) / 2;
        self.build_rec(node * 2, lo, mid, data);
        self.build_rec(node * 2 + 1, mid, hi, data);
        self.pull(node);
    }

    /// Recompute a node's aggregates from its children.
    fn pull(&mut self, node: usize) {
        let (l, r) = (node * 2, node * 2 + 1);
        self.sum[node] = self.sum[l] + self.sum[r];
        self.min[node] = self.min[l].min(self.min[r]);
        self.max[node] = self.max[l].max(self.max[r]);
    }

    /// Apply a pending `delta` to a node covering `len` elements.
    fn apply(&mut self, node: usize, len: usize, delta: i64) {
        self.sum[node] += delta * len as i64;
        self.min[node] += delta;
        self.max[node] += delta;
        self.lazy[node] += delta;
    }

    /// Push a node's lazy tag down to its children.
    fn push_down(&mut self, node: usize, lo: usize, hi: usize) {
        let d = self.lazy[node];
        if d != 0 {
            let mid = (lo + hi) / 2;
            self.apply(node * 2, mid - lo, d);
            self.apply(node * 2 + 1, hi - mid, d);
            self.lazy[node] = 0;
        }
    }

    /// Add `delta` to every element in the half-open range `[l, r)`.
    pub fn range_add(&mut self, l: usize, r: usize, delta: i64) {
        let (l, r) = (l.min(self.n), r.min(self.n));
        if l >= r {
            return;
        }
        self.add_rec(1, 0, self.n, l, r, delta);
    }

    fn add_rec(&mut self, node: usize, lo: usize, hi: usize, l: usize, r: usize, delta: i64) {
        if l <= lo && hi <= r {
            self.apply(node, hi - lo, delta);
            return;
        }
        self.push_down(node, lo, hi);
        let mid = (lo + hi) / 2;
        if l < mid {
            self.add_rec(node * 2, lo, mid, l, r, delta);
        }
        if r > mid {
            self.add_rec(node * 2 + 1, mid, hi, l, r, delta);
        }
        self.pull(node);
    }

    /// The sum over `[l, r)` (0 for an empty range).
    pub fn range_sum(&mut self, l: usize, r: usize) -> i64 {
        let (l, r) = (l.min(self.n), r.min(self.n));
        if l >= r {
            return 0;
        }
        self.sum_rec(1, 0, self.n, l, r)
    }

    fn sum_rec(&mut self, node: usize, lo: usize, hi: usize, l: usize, r: usize) -> i64 {
        if l <= lo && hi <= r {
            return self.sum[node];
        }
        self.push_down(node, lo, hi);
        let mid = (lo + hi) / 2;
        let mut s = 0;
        if l < mid {
            s += self.sum_rec(node * 2, lo, mid, l, r);
        }
        if r > mid {
            s += self.sum_rec(node * 2 + 1, mid, hi, l, r);
        }
        s
    }

    /// The minimum over `[l, r)` (`None` for an empty range).
    pub fn range_min(&mut self, l: usize, r: usize) -> Option<i64> {
        let (l, r) = (l.min(self.n), r.min(self.n));
        if l >= r {
            return None;
        }
        Some(self.min_rec(1, 0, self.n, l, r))
    }

    fn min_rec(&mut self, node: usize, lo: usize, hi: usize, l: usize, r: usize) -> i64 {
        if l <= lo && hi <= r {
            return self.min[node];
        }
        self.push_down(node, lo, hi);
        let mid = (lo + hi) / 2;
        let mut m = i64::MAX;
        if l < mid {
            m = m.min(self.min_rec(node * 2, lo, mid, l, r));
        }
        if r > mid {
            m = m.min(self.min_rec(node * 2 + 1, mid, hi, l, r));
        }
        m
    }

    /// The maximum over `[l, r)` (`None` for an empty range).
    pub fn range_max(&mut self, l: usize, r: usize) -> Option<i64> {
        let (l, r) = (l.min(self.n), r.min(self.n));
        if l >= r {
            return None;
        }
        Some(self.max_rec(1, 0, self.n, l, r))
    }

    fn max_rec(&mut self, node: usize, lo: usize, hi: usize, l: usize, r: usize) -> i64 {
        if l <= lo && hi <= r {
            return self.max[node];
        }
        self.push_down(node, lo, hi);
        let mid = (lo + hi) / 2;
        let mut m = i64::MIN;
        if l < mid {
            m = m.max(self.max_rec(node * 2, lo, mid, l, r));
        }
        if r > mid {
            m = m.max(self.max_rec(node * 2 + 1, mid, hi, l, r));
        }
        m
    }

    /// The value at `i` (a width-one range), or `None` if out of range.
    pub fn get(&mut self, i: usize) -> Option<i64> {
        if i >= self.n {
            return None;
        }
        Some(self.sum_rec(1, 0, self.n, i, i + 1))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_and_full_sum() {
        let mut t = SegmentTree::build(&[1, 2, 3, 4, 5]);
        assert_eq!(t.len(), 5);
        assert_eq!(t.range_sum(0, 5), 15);
        assert_eq!(t.range_min(0, 5), Some(1));
        assert_eq!(t.range_max(0, 5), Some(5));
    }

    #[test]
    fn partial_range_queries() {
        let mut t = SegmentTree::build(&[5, 3, 8, 1, 9, 2]);
        assert_eq!(t.range_sum(1, 4), 3 + 8 + 1);
        assert_eq!(t.range_min(1, 4), Some(1));
        assert_eq!(t.range_max(2, 6), Some(9));
        assert_eq!(t.get(3), Some(1));
    }

    #[test]
    fn range_add_updates_aggregates() {
        let mut t = SegmentTree::build(&[0, 0, 0, 0, 0]);
        t.range_add(1, 4, 10); // [0,10,10,10,0]
        assert_eq!(t.range_sum(0, 5), 30);
        assert_eq!(t.range_max(0, 5), Some(10));
        assert_eq!(t.range_min(0, 5), Some(0));
        assert_eq!(t.get(2), Some(10));
        assert_eq!(t.get(0), Some(0));
    }

    #[test]
    fn overlapping_adds_accumulate() {
        let mut t = SegmentTree::zeros(6);
        t.range_add(0, 4, 5); // [5,5,5,5,0,0]
        t.range_add(2, 6, 3); // [5,5,8,8,3,3]
        assert_eq!(t.get(0), Some(5));
        assert_eq!(t.get(2), Some(8));
        assert_eq!(t.get(5), Some(3));
        assert_eq!(t.range_sum(0, 6), 5 + 5 + 8 + 8 + 3 + 3);
        assert_eq!(t.range_max(0, 6), Some(8));
    }

    #[test]
    fn negative_deltas() {
        let mut t = SegmentTree::build(&[10, 10, 10]);
        t.range_add(0, 3, -4);
        assert_eq!(t.range_sum(0, 3), 18);
        assert_eq!(t.range_min(0, 3), Some(6));
    }

    #[test]
    fn single_element() {
        let mut t = SegmentTree::build(&[42]);
        assert_eq!(t.range_sum(0, 1), 42);
        t.range_add(0, 1, 8);
        assert_eq!(t.get(0), Some(50));
    }

    #[test]
    fn empty_ranges_and_tree() {
        let mut t = SegmentTree::build(&[1, 2, 3]);
        assert_eq!(t.range_sum(2, 2), 0);
        assert_eq!(t.range_min(2, 2), None);
        assert!(t.get(9).is_none());
        let mut e = SegmentTree::build(&[]);
        assert!(e.is_empty());
        assert_eq!(e.range_sum(0, 0), 0);
    }

    #[test]
    fn matches_brute_force_under_random_ops() {
        // mirror every operation on a plain array and compare.
        let n = 64;
        let mut arr = vec![0i64; n];
        let mut t = SegmentTree::zeros(n);
        let mut s = 0x2545F4914F6CDD1Du64;
        let mut rng = || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            s
        };
        for _ in 0..2000 {
            let a = (rng() as usize) % n;
            let b = (rng() as usize) % n;
            let (l, r) = (a.min(b), a.max(b) + 1);
            if rng() % 2 == 0 {
                let delta = (rng() % 21) as i64 - 10; // -10..=10
                for x in arr.iter_mut().take(r).skip(l) {
                    *x += delta;
                }
                t.range_add(l, r, delta);
            } else {
                let want_sum: i64 = arr[l..r].iter().sum();
                let want_min = *arr[l..r].iter().min().unwrap();
                let want_max = *arr[l..r].iter().max().unwrap();
                assert_eq!(t.range_sum(l, r), want_sum, "sum [{l},{r})");
                assert_eq!(t.range_min(l, r), Some(want_min), "min [{l},{r})");
                assert_eq!(t.range_max(l, r), Some(want_max), "max [{l},{r})");
            }
        }
    }

    #[test]
    fn serde_round_trip() {
        let mut t = SegmentTree::build(&[1, 2, 3, 4]);
        t.range_add(0, 2, 5);
        let j = serde_json::to_string(&t).unwrap();
        let mut back: SegmentTree = serde_json::from_str(&j).unwrap();
        assert_eq!(back.range_sum(0, 4), t.clone().range_sum(0, 4));
        assert_eq!(back.get(0), Some(6));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
