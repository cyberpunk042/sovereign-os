//! `sovereign-vptree` — exact nearest-neighbor in a metric space, with pruning.
//!
//! A vantage-point tree indexes points so that nearest-neighbor and radius
//! queries skip most of the data while still returning the *exact* answer. At
//! each node it picks a *vantage point* and the **median** distance from that
//! vantage to the remaining points; points nearer than the median go in the
//! "inside" subtree, the rest in the "outside" subtree. Because distance is a
//! metric, the triangle inequality bounds how close anything in a subtree can be
//! to a query: once you have a candidate at radius `tau`, a subtree on the far
//! side of the median can be discarded whenever the query is more than `tau` away
//! from that side's band. That pruning is what makes it sublinear on
//! well-structured data, and unlike LSH or product quantization it never trades
//! away correctness — it returns the true neighbors.
//!
//! It works for *any* metric; this crate uses Euclidean distance over `Vec<f32>`
//! (so it indexes embeddings directly). The tree is stored as an arena of nodes
//! for clean serialization, and construction is deterministic (median split,
//! first-point vantage), so the same points always build the same tree.
//!
//! [`VpTree::nearest`] returns the single closest point; [`VpTree::knn`] the `k`
//! closest; [`VpTree::within`] everything inside a radius — all exact.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the vptree surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A node in the arena.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct Node {
    /// Index (into `points`) of this node's vantage point.
    point: usize,
    /// Median distance splitting inside from outside.
    threshold: f64,
    /// Arena index of the inside subtree (distances `<= threshold`).
    inside: Option<usize>,
    /// Arena index of the outside subtree (distances `> threshold`).
    outside: Option<usize>,
}

/// A vantage-point tree over `Vec<f32>` points (Euclidean distance).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct VpTree {
    points: Vec<Vec<f32>>,
    nodes: Vec<Node>,
    root: Option<usize>,
}

impl VpTree {
    /// Build a tree over `points`. All points must share one non-zero dimension;
    /// ragged or empty-dimension input produces an empty tree.
    pub fn build(points: Vec<Vec<f32>>) -> Self {
        if points.is_empty() || points[0].is_empty() {
            return Self {
                points,
                nodes: Vec::new(),
                root: None,
            };
        }
        let dim = points[0].len();
        if points.iter().any(|p| p.len() != dim) {
            return Self {
                points,
                nodes: Vec::new(),
                root: None,
            };
        }
        let mut tree = Self {
            points,
            nodes: Vec::new(),
            root: None,
        };
        let indices: Vec<usize> = (0..tree.points.len()).collect();
        tree.root = tree.build_node(indices);
        tree
    }

    /// The number of indexed points.
    pub fn len(&self) -> usize {
        self.points.len()
    }

    /// Whether the tree has no points.
    pub fn is_empty(&self) -> bool {
        self.root.is_none()
    }

    /// Recursively build a subtree over `indices`; returns its arena slot.
    fn build_node(&mut self, mut indices: Vec<usize>) -> Option<usize> {
        if indices.is_empty() {
            return None;
        }
        // deterministic vantage: the first index.
        let vantage = indices.remove(0);
        if indices.is_empty() {
            let id = self.nodes.len();
            self.nodes.push(Node {
                point: vantage,
                threshold: 0.0,
                inside: None,
                outside: None,
            });
            return Some(id);
        }
        // distances from the vantage to the rest
        let mut dists: Vec<(usize, f64)> = indices
            .iter()
            .map(|&i| (i, dist(&self.points[vantage], &self.points[i])))
            .collect();
        dists.sort_by(|a, b| a.1.total_cmp(&b.1));
        let mid = dists.len() / 2;
        let threshold = dists[mid].1;

        // inside = distance <= threshold (excluding the median pivot itself goes
        // outside-or-inside by the <= rule); outside = strictly greater.
        let mut inside_idx = Vec::new();
        let mut outside_idx = Vec::new();
        for (i, d) in dists {
            if d < threshold {
                inside_idx.push(i);
            } else {
                outside_idx.push(i);
            }
        }

        let id = self.nodes.len();
        self.nodes.push(Node {
            point: vantage,
            threshold,
            inside: None,
            outside: None,
        });
        let inside = self.build_node(inside_idx);
        let outside = self.build_node(outside_idx);
        self.nodes[id].inside = inside;
        self.nodes[id].outside = outside;
        Some(id)
    }

    /// The `k` nearest points to `query` as `(index, distance)`, sorted by
    /// ascending distance (ties by index). Exact.
    pub fn knn(&self, query: &[f32], k: usize) -> Vec<(usize, f64)> {
        let mut heap: Vec<(usize, f64)> = Vec::new(); // kept sorted ascending
        if k == 0 {
            return heap;
        }
        self.search(self.root, query, k, &mut heap);
        heap
    }

    /// The single nearest point to `query`, or `None` if the tree is empty.
    pub fn nearest(&self, query: &[f32]) -> Option<(usize, f64)> {
        self.knn(query, 1).into_iter().next()
    }

    /// All points within (inclusive) `radius` of `query`, sorted by ascending
    /// distance. Exact.
    pub fn within(&self, query: &[f32], radius: f64) -> Vec<(usize, f64)> {
        let mut out = Vec::new();
        self.search_radius(self.root, query, radius, &mut out);
        out.sort_by(|a, b| a.1.total_cmp(&b.1).then(a.0.cmp(&b.0)));
        out
    }

    fn worst(heap: &[(usize, f64)], k: usize) -> f64 {
        if heap.len() < k {
            f64::INFINITY
        } else {
            heap[heap.len() - 1].1
        }
    }

    fn push_candidate(heap: &mut Vec<(usize, f64)>, cand: (usize, f64), k: usize) {
        // insert keeping ascending order, then trim to k
        let pos = heap
            .binary_search_by(|probe| probe.1.total_cmp(&cand.1).then(probe.0.cmp(&cand.0)))
            .unwrap_or_else(|e| e);
        heap.insert(pos, cand);
        if heap.len() > k {
            heap.truncate(k);
        }
    }

    fn search(&self, node: Option<usize>, query: &[f32], k: usize, heap: &mut Vec<(usize, f64)>) {
        let Some(id) = node else { return };
        let n = &self.nodes[id];
        let d = dist(query, &self.points[n.point]);
        Self::push_candidate(heap, (n.point, d), k);

        if n.inside.is_none() && n.outside.is_none() {
            return;
        }
        // Search the nearer side first; then the far side only if a point there
        // could still be within the current k-th-best radius `tau`. By the
        // triangle inequality, anything inside the median band is `> d - mu` from
        // the query and anything outside is `> mu - d`, so:
        //   - after searching inside, search outside iff `d + tau >= mu`
        //   - after searching outside, search inside iff `d - tau <= mu`
        // `tau` is re-read after the first side, since it may have shrunk.
        if d < n.threshold {
            self.search(n.inside, query, k, heap);
            if d + Self::worst(heap, k) >= n.threshold {
                self.search(n.outside, query, k, heap);
            }
        } else {
            self.search(n.outside, query, k, heap);
            if d - Self::worst(heap, k) <= n.threshold {
                self.search(n.inside, query, k, heap);
            }
        }
    }

    fn search_radius(
        &self,
        node: Option<usize>,
        query: &[f32],
        radius: f64,
        out: &mut Vec<(usize, f64)>,
    ) {
        let Some(id) = node else { return };
        let n = &self.nodes[id];
        let d = dist(query, &self.points[n.point]);
        if d <= radius {
            out.push((n.point, d));
        }
        // inside could hold matches if d - radius <= threshold;
        // outside could hold matches if d + radius >= threshold.
        if d - radius <= n.threshold {
            self.search_radius(n.inside, query, radius, out);
        }
        if d + radius >= n.threshold {
            self.search_radius(n.outside, query, radius, out);
        }
    }
}

/// Euclidean distance between two equal-length vectors.
fn dist(a: &[f32], b: &[f32]) -> f64 {
    a.iter()
        .zip(b.iter())
        .map(|(&x, &y)| {
            let d = x as f64 - y as f64;
            d * d
        })
        .sum::<f64>()
        .sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn brute_knn(points: &[Vec<f32>], query: &[f32], k: usize) -> Vec<(usize, f64)> {
        let mut all: Vec<(usize, f64)> = points
            .iter()
            .enumerate()
            .map(|(i, p)| (i, dist(query, p)))
            .collect();
        all.sort_by(|a, b| a.1.total_cmp(&b.1).then(a.0.cmp(&b.0)));
        all.truncate(k);
        all
    }

    fn grid() -> Vec<Vec<f32>> {
        let mut pts = Vec::new();
        for x in 0..10 {
            for y in 0..10 {
                pts.push(vec![x as f32, y as f32]);
            }
        }
        pts
    }

    #[test]
    fn nearest_matches_brute_force() {
        let pts = grid();
        let tree = VpTree::build(pts.clone());
        for q in [[2.1, 3.9], [9.9, 0.1], [4.5, 4.5], [-1.0, -1.0]] {
            let got = tree.nearest(&q).unwrap();
            let exp = brute_knn(&pts, &q, 1)[0];
            assert_eq!(got.0, exp.0, "query {q:?}");
            assert!((got.1 - exp.1).abs() < 1e-9);
        }
    }

    #[test]
    fn knn_matches_brute_force() {
        let pts = grid();
        let tree = VpTree::build(pts.clone());
        for q in [[2.1, 3.9], [4.5, 4.5], [7.2, 1.3], [0.0, 9.0]] {
            for k in [1usize, 3, 5, 8] {
                let got: Vec<usize> = tree.knn(&q, k).into_iter().map(|(i, _)| i).collect();
                let exp: Vec<usize> = brute_knn(&pts, &q, k).into_iter().map(|(i, _)| i).collect();
                assert_eq!(got, exp, "query {q:?} k {k}");
            }
        }
    }

    #[test]
    fn within_radius_matches_brute_force() {
        let pts = grid();
        let tree = VpTree::build(pts.clone());
        let q = [4.5f32, 4.5];
        for radius in [0.5, 1.5, 3.0] {
            let mut got: Vec<usize> = tree
                .within(&q, radius)
                .into_iter()
                .map(|(i, _)| i)
                .collect();
            got.sort_unstable();
            let mut exp: Vec<usize> = pts
                .iter()
                .enumerate()
                .filter(|(_, p)| dist(&q, p) <= radius)
                .map(|(i, _)| i)
                .collect();
            exp.sort_unstable();
            assert_eq!(got, exp, "radius {radius}");
        }
    }

    #[test]
    fn knn_on_random_data_matches_brute() {
        // pseudo-random 4-D points
        let mut rng = 0xABCDu64;
        let mut next = || {
            rng = rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = rng;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            ((z ^ (z >> 31)) >> 40) as f32 / (1u64 << 24) as f32
        };
        let pts: Vec<Vec<f32>> = (0..200).map(|_| (0..4).map(|_| next()).collect()).collect();
        let tree = VpTree::build(pts.clone());
        for _ in 0..10 {
            let q: Vec<f32> = (0..4).map(|_| next()).collect();
            let got: Vec<usize> = tree.knn(&q, 5).into_iter().map(|(i, _)| i).collect();
            let exp: Vec<usize> = brute_knn(&pts, &q, 5).into_iter().map(|(i, _)| i).collect();
            assert_eq!(got, exp);
        }
    }

    #[test]
    fn single_point_and_empty() {
        let one = VpTree::build(vec![vec![1.0, 2.0]]);
        assert_eq!(one.len(), 1);
        assert_eq!(one.nearest(&[0.0, 0.0]).unwrap().0, 0);

        let empty = VpTree::build(Vec::<Vec<f32>>::new());
        assert!(empty.is_empty());
        assert!(empty.nearest(&[0.0]).is_none());
        assert!(empty.knn(&[0.0], 3).is_empty());
    }

    #[test]
    fn k_larger_than_n_returns_all() {
        let pts = vec![vec![0.0f32], vec![1.0], vec![2.0]];
        let tree = VpTree::build(pts);
        let got = tree.knn(&[0.5], 10);
        assert_eq!(got.len(), 3);
    }

    #[test]
    fn serde_round_trip() {
        let pts = grid();
        let tree = VpTree::build(pts.clone());
        let j = serde_json::to_string(&tree).unwrap();
        let back: VpTree = serde_json::from_str(&j).unwrap();
        // f64 split thresholds can shift by a ULP through JSON, so compare query
        // behaviour (the indices returned), which round-trips exactly.
        assert_eq!(back.len(), tree.len());
        let q = [3.3f32, 6.6];
        let a: Vec<usize> = back.knn(&q, 4).into_iter().map(|(i, _)| i).collect();
        let b: Vec<usize> = tree.knn(&q, 4).into_iter().map(|(i, _)| i).collect();
        assert_eq!(a, b);
    }
}
