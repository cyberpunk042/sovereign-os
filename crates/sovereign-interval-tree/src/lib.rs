//! `sovereign-interval-tree` — which intervals cover this point, or hit this range?
//!
//! Reservations, time windows, locked ranges, tagged spans: the recurring question
//! is *which of these intervals contain a given instant, or overlap a given range?*
//! Scanning them all is `O(n)` per query. An **interval tree** answers in time
//! proportional to the depth plus the number of matches, which is what you want when
//! a handful of intervals out of thousands actually hit.
//!
//! This is the center-point (CLRS-style) construction. Pick a center coordinate;
//! every interval that straddles it lives at this node, kept sorted by start and by
//! end; intervals entirely to the left or right recurse into the left or right
//! subtree. A **point query** at `p` reports the straddlers whose start is `≤ p` (or
//! end `≥ p`), then descends only toward `p` — the other subtree cannot contain it.
//! An **overlap query** reports the straddlers that intersect the range and descends
//! left only if the range reaches past the center, right only if it extends beyond —
//! pruning whole subtrees that cannot match.
//!
//! Intervals are inclusive `[start, end]` and carry a payload of any type.
//! [`IntervalTree::build`] constructs the tree; [`IntervalTree::query_point`] and
//! [`IntervalTree::query_overlap`] return the matching intervals' indices (sorted,
//! so output is deterministic), and [`IntervalTree::interval`] reads one back. The
//! tree is static — built once from a set — which is the common case for a snapshot
//! of reservations or spans.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the interval-tree surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One stored interval `[start, end]` with a payload.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Interval<T> {
    /// Inclusive start coordinate.
    pub start: i64,
    /// Inclusive end coordinate.
    pub end: i64,
    /// Associated payload.
    pub data: T,
}

/// A node of the center-point interval tree.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct Node {
    center: i64,
    /// Straddling-interval indices, sorted ascending by start.
    by_start: Vec<usize>,
    /// Straddling-interval indices, sorted descending by end.
    by_end: Vec<usize>,
    left: Option<Box<Node>>,
    right: Option<Box<Node>>,
}

/// A static interval tree over intervals carrying payloads of type `T`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IntervalTree<T> {
    items: Vec<Interval<T>>,
    root: Option<Box<Node>>,
}

fn overlaps(s: i64, e: i64, qs: i64, qe: i64) -> bool {
    s <= qe && qs <= e
}

impl<T> IntervalTree<T> {
    /// Build a tree from `(start, end, data)` triples. A triple with `start > end`
    /// is normalized by swapping.
    pub fn build(intervals: Vec<(i64, i64, T)>) -> Self {
        let items: Vec<Interval<T>> = intervals
            .into_iter()
            .map(|(a, b, d)| {
                let (start, end) = if a <= b { (a, b) } else { (b, a) };
                Interval {
                    start,
                    end,
                    data: d,
                }
            })
            .collect();
        let idxs: Vec<usize> = (0..items.len()).collect();
        let root = Self::build_node(&items, idxs);
        Self { items, root }
    }

    fn build_node(items: &[Interval<T>], idxs: Vec<usize>) -> Option<Box<Node>> {
        if idxs.is_empty() {
            return None;
        }
        // center = median endpoint.
        let mut endpoints: Vec<i64> = Vec::with_capacity(idxs.len() * 2);
        for &i in &idxs {
            endpoints.push(items[i].start);
            endpoints.push(items[i].end);
        }
        endpoints.sort_unstable();
        let center = endpoints[endpoints.len() / 2];

        let mut mid = Vec::new();
        let mut left = Vec::new();
        let mut right = Vec::new();
        for &i in &idxs {
            let it = &items[i];
            if it.end < center {
                left.push(i);
            } else if it.start > center {
                right.push(i);
            } else {
                mid.push(i);
            }
        }

        let mut by_start = mid.clone();
        by_start.sort_by_key(|&i| (items[i].start, i));
        let mut by_end = mid;
        by_end.sort_by(|&a, &b| items[b].end.cmp(&items[a].end).then(a.cmp(&b)));

        Some(Box::new(Node {
            center,
            by_start,
            by_end,
            left: Self::build_node(items, left),
            right: Self::build_node(items, right),
        }))
    }

    /// Number of intervals.
    pub fn len(&self) -> usize {
        self.items.len()
    }
    /// Whether the tree is empty.
    pub fn is_empty(&self) -> bool {
        self.items.is_empty()
    }
    /// The interval at `index` (insertion order), if present.
    pub fn interval(&self, index: usize) -> Option<&Interval<T>> {
        self.items.get(index)
    }

    /// Indices of all intervals containing the point `p`, sorted ascending.
    pub fn query_point(&self, p: i64) -> Vec<usize> {
        let mut out = Vec::new();
        self.point_rec(self.root.as_deref(), p, &mut out);
        out.sort_unstable();
        out
    }

    fn point_rec(&self, node: Option<&Node>, p: i64, out: &mut Vec<usize>) {
        let Some(node) = node else { return };
        if p < node.center {
            // straddlers with start <= p contain p.
            for &i in &node.by_start {
                if self.items[i].start <= p {
                    out.push(i);
                } else {
                    break;
                }
            }
            self.point_rec(node.left.as_deref(), p, out);
        } else if p > node.center {
            for &i in &node.by_end {
                if self.items[i].end >= p {
                    out.push(i);
                } else {
                    break;
                }
            }
            self.point_rec(node.right.as_deref(), p, out);
        } else {
            // p == center: every straddler contains it.
            out.extend_from_slice(&node.by_start);
        }
    }

    /// Indices of all intervals overlapping the inclusive range `[qs, qe]`, sorted
    /// ascending. If `qs > qe` the bounds are swapped.
    pub fn query_overlap(&self, qs: i64, qe: i64) -> Vec<usize> {
        let (qs, qe) = if qs <= qe { (qs, qe) } else { (qe, qs) };
        let mut out = Vec::new();
        self.overlap_rec(self.root.as_deref(), qs, qe, &mut out);
        out.sort_unstable();
        out
    }

    fn overlap_rec(&self, node: Option<&Node>, qs: i64, qe: i64, out: &mut Vec<usize>) {
        let Some(node) = node else { return };
        // straddlers at this node: test each against the query range.
        for &i in &node.by_start {
            let it = &self.items[i];
            if overlaps(it.start, it.end, qs, qe) {
                out.push(i);
            }
        }
        // a left-subtree interval lies entirely left of center; it can overlap only
        // if the query reaches left of center.
        if qs < node.center {
            self.overlap_rec(node.left.as_deref(), qs, qe, out);
        }
        if qe > node.center {
            self.overlap_rec(node.right.as_deref(), qs, qe, out);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tree(specs: &[(i64, i64)]) -> IntervalTree<usize> {
        let v: Vec<(i64, i64, usize)> = specs
            .iter()
            .enumerate()
            .map(|(i, &(s, e))| (s, e, i))
            .collect();
        IntervalTree::build(v)
    }

    /// Brute-force point containment.
    fn brute_point(specs: &[(i64, i64)], p: i64) -> Vec<usize> {
        specs
            .iter()
            .enumerate()
            .filter(|&(_, &(s, e))| s <= p && p <= e)
            .map(|(i, _)| i)
            .collect()
    }
    fn brute_overlap(specs: &[(i64, i64)], qs: i64, qe: i64) -> Vec<usize> {
        specs
            .iter()
            .enumerate()
            .filter(|&(_, &(s, e))| s <= qe && qs <= e)
            .map(|(i, _)| i)
            .collect()
    }

    #[test]
    fn point_query_basic() {
        let specs = [(1, 5), (3, 8), (10, 12), (6, 7)];
        let t = tree(&specs);
        assert_eq!(t.query_point(4), vec![0, 1]); // [1,5] and [3,8]
        assert_eq!(t.query_point(7), vec![1, 3]); // [3,8] and [6,7]
        assert_eq!(t.query_point(11), vec![2]);
        assert!(t.query_point(9).is_empty());
    }

    #[test]
    fn boundary_inclusive() {
        let t = tree(&[(2, 5)]);
        assert_eq!(t.query_point(2), vec![0]);
        assert_eq!(t.query_point(5), vec![0]);
        assert!(t.query_point(1).is_empty());
        assert!(t.query_point(6).is_empty());
    }

    #[test]
    fn overlap_query_basic() {
        let specs = [(1, 3), (5, 8), (7, 10), (12, 15)];
        let t = tree(&specs);
        assert_eq!(t.query_overlap(6, 9), vec![1, 2]); // overlaps [5,8] and [7,10]
        assert_eq!(t.query_overlap(0, 100), vec![0, 1, 2, 3]);
        assert!(t.query_overlap(16, 20).is_empty());
        // touching at a boundary counts (inclusive).
        assert_eq!(t.query_overlap(3, 3), vec![0]);
    }

    #[test]
    fn nested_intervals() {
        let specs = [(0, 100), (10, 90), (40, 60), (50, 50)];
        let t = tree(&specs);
        assert_eq!(t.query_point(50), vec![0, 1, 2, 3]); // all contain 50
        assert_eq!(t.query_point(5), vec![0]); // only the outer
    }

    #[test]
    fn empty_tree() {
        let t: IntervalTree<usize> = IntervalTree::build(vec![]);
        assert!(t.is_empty());
        assert!(t.query_point(5).is_empty());
        assert!(t.query_overlap(0, 10).is_empty());
    }

    #[test]
    fn reversed_bounds_normalized() {
        let t = IntervalTree::build(vec![(8, 2, "x")]);
        assert_eq!(t.interval(0).unwrap().start, 2);
        assert_eq!(t.interval(0).unwrap().end, 8);
        assert_eq!(t.query_point(5), vec![0]);
        assert_eq!(t.query_overlap(7, 3), vec![0]); // query bounds also normalized
    }

    #[test]
    fn payload_retrieval() {
        let t = IntervalTree::build(vec![(1, 4, "a"), (3, 9, "b")]);
        let hits = t.query_point(3);
        let payloads: Vec<&str> = hits.iter().map(|&i| t.interval(i).unwrap().data).collect();
        assert_eq!(payloads, vec!["a", "b"]);
    }

    #[test]
    fn matches_brute_force_random() {
        // build a pseudo-random interval set and check both query kinds exhaustively.
        let mut s = 0x9E3779B97F4A7C15u64;
        let mut rng = || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            s
        };
        let specs: Vec<(i64, i64)> = (0..200)
            .map(|_| {
                let a = (rng() % 1000) as i64;
                let b = a + (rng() % 50) as i64;
                (a, b)
            })
            .collect();
        let t = tree(&specs);
        for p in (0..1050).step_by(7) {
            let mut got = t.query_point(p as i64);
            got.sort_unstable();
            let mut want = brute_point(&specs, p as i64);
            want.sort_unstable();
            assert_eq!(got, want, "point {p}");
        }
        for qs in (0..1000).step_by(53) {
            let qe = qs + 30;
            let mut got = t.query_overlap(qs as i64, qe as i64);
            got.sort_unstable();
            let mut want = brute_overlap(&specs, qs as i64, qe as i64);
            want.sort_unstable();
            assert_eq!(got, want, "overlap [{qs},{qe}]");
        }
    }

    #[test]
    fn serde_round_trip() {
        let t = IntervalTree::build(vec![(1, 5, 10u32), (3, 8, 20), (10, 12, 30)]);
        let j = serde_json::to_string(&t).unwrap();
        let back: IntervalTree<u32> = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
        assert_eq!(t.query_point(4), back.query_point(4));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
