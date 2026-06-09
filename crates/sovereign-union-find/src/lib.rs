//! `sovereign-union-find` — disjoint-set union for grouping equivalences.
//!
//! Given a set of pairwise relations — "these two retrieved chunks are
//! near-duplicates", "these two records are the same entity" — the question is
//! usually *which items end up in the same group?* Computing that by repeatedly
//! scanning is quadratic; a **disjoint-set (union-find)** structure answers it in
//! near-constant amortised time per operation.
//!
//! Each element starts in its own singleton set. [`DisjointSet::union`] merges
//! the sets of two elements; [`DisjointSet::find`] returns a set's canonical
//! representative; [`DisjointSet::connected`] asks whether two elements are in
//! the same set. Two standard optimisations make the operations effectively
//! flat: **path compression** points every node visited during a `find` straight
//! at the root, and **union by rank** always hangs the shorter tree under the
//! taller one. Together they give an amortised cost of `O(α(n))` — the inverse
//! Ackermann function, ≤ 4 for any practical `n`.
//!
//! [`DisjointSet::groups`] materialises the connected components, which is the
//! usual end goal: turn a pile of "these two are related" edges into the actual
//! clusters.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Schema version of the union-find surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A disjoint-set forest over elements `0..n`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisjointSet {
    parent: Vec<usize>,
    rank: Vec<u32>,
    /// Number of distinct sets currently present.
    sets: usize,
}

impl DisjointSet {
    /// `n` singleton sets, one per element `0..n`.
    pub fn new(n: usize) -> Self {
        Self {
            parent: (0..n).collect(),
            rank: vec![0; n],
            sets: n,
        }
    }

    /// The number of elements.
    pub fn len(&self) -> usize {
        self.parent.len()
    }

    /// Whether there are no elements.
    pub fn is_empty(&self) -> bool {
        self.parent.is_empty()
    }

    /// The number of distinct sets.
    pub fn set_count(&self) -> usize {
        self.sets
    }

    /// The canonical representative of `x`'s set, compressing the path to the
    /// root as it goes.
    ///
    /// # Panics
    /// Panics if `x >= len()`.
    pub fn find(&mut self, x: usize) -> usize {
        assert!(x < self.parent.len(), "element out of range");
        // Iterative two-pass path compression (no recursion, no unsafe).
        let mut root = x;
        while self.parent[root] != root {
            root = self.parent[root];
        }
        let mut cur = x;
        while self.parent[cur] != root {
            let next = self.parent[cur];
            self.parent[cur] = root;
            cur = next;
        }
        root
    }

    /// Merge the sets containing `a` and `b`. Returns `true` if they were in
    /// different sets (a merge happened), `false` if already together.
    ///
    /// # Panics
    /// Panics if either index is out of range.
    pub fn union(&mut self, a: usize, b: usize) -> bool {
        let ra = self.find(a);
        let rb = self.find(b);
        if ra == rb {
            return false;
        }
        // union by rank: attach the lower-rank root under the higher.
        match self.rank[ra].cmp(&self.rank[rb]) {
            std::cmp::Ordering::Less => self.parent[ra] = rb,
            std::cmp::Ordering::Greater => self.parent[rb] = ra,
            std::cmp::Ordering::Equal => {
                self.parent[rb] = ra;
                self.rank[ra] += 1;
            }
        }
        self.sets -= 1;
        true
    }

    /// Whether `a` and `b` are in the same set.
    pub fn connected(&mut self, a: usize, b: usize) -> bool {
        self.find(a) == self.find(b)
    }

    /// The size of the set containing `x`.
    pub fn set_size(&mut self, x: usize) -> usize {
        let root = self.find(x);
        (0..self.parent.len())
            .filter(|&i| self.find(i) == root)
            .count()
    }

    /// The connected components, each a sorted list of element ids; the outer
    /// list is ordered by each group's smallest element. Every element appears in
    /// exactly one group.
    pub fn groups(&mut self) -> Vec<Vec<usize>> {
        let n = self.parent.len();
        let mut by_root: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
        for i in 0..n {
            let r = self.find(i);
            by_root.entry(r).or_default().push(i);
        }
        // Order groups by their smallest member for a stable, predictable result.
        let mut groups: Vec<Vec<usize>> = by_root.into_values().collect();
        groups.sort_by_key(|g| g[0]);
        groups
    }
}

/// Build the connected components implied by a set of undirected `edges` over
/// `n` elements — the common "cluster these related pairs" shortcut. Each
/// component is a sorted id list; components are ordered by smallest member.
pub fn components(n: usize, edges: &[(usize, usize)]) -> Vec<Vec<usize>> {
    let mut ds = DisjointSet::new(n);
    for &(a, b) in edges {
        ds.union(a, b);
    }
    ds.groups()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn singletons_initially() {
        let mut ds = DisjointSet::new(5);
        assert_eq!(ds.set_count(), 5);
        assert_eq!(ds.len(), 5);
        for i in 0..5 {
            assert_eq!(ds.set_size(i), 1);
            assert!(!ds.connected(i, (i + 1) % 5));
        }
    }

    #[test]
    fn union_merges_and_counts() {
        let mut ds = DisjointSet::new(6);
        assert!(ds.union(0, 1));
        assert!(ds.union(1, 2));
        assert!(!ds.union(0, 2)); // already together
        assert_eq!(ds.set_count(), 4); // {0,1,2}, {3}, {4}, {5}
        assert!(ds.connected(0, 2));
        assert!(!ds.connected(0, 3));
        assert_eq!(ds.set_size(0), 3);
        assert_eq!(ds.set_size(3), 1);
    }

    #[test]
    fn transitive_connectivity() {
        let mut ds = DisjointSet::new(7);
        ds.union(0, 1);
        ds.union(2, 3);
        ds.union(1, 3); // links the two pairs
        assert!(ds.connected(0, 2));
        assert!(ds.connected(0, 3));
        assert_eq!(ds.set_size(0), 4); // {0,1,2,3}
    }

    #[test]
    fn groups_partition_all_elements() {
        let mut ds = DisjointSet::new(8);
        ds.union(0, 2);
        ds.union(2, 4);
        ds.union(1, 3);
        let groups = ds.groups();
        // every element appears exactly once
        let mut seen: Vec<usize> = groups.iter().flatten().copied().collect();
        seen.sort_unstable();
        assert_eq!(seen, (0..8).collect::<Vec<_>>());
        // the {0,2,4} component is present and sorted
        assert!(groups.contains(&vec![0, 2, 4]));
        assert!(groups.contains(&vec![1, 3]));
        // groups ordered by smallest member
        assert_eq!(groups[0][0], 0);
    }

    #[test]
    fn components_helper_clusters_edges() {
        // edges forming two clusters: {0,1,2} and {3,4}, with 5 isolated
        let edges = [(0, 1), (1, 2), (3, 4)];
        let comps = components(6, &edges);
        assert_eq!(comps, vec![vec![0, 1, 2], vec![3, 4], vec![5]]);
    }

    #[test]
    fn path_compression_keeps_results_correct() {
        // chain unions then verify finds are all consistent after compression
        let mut ds = DisjointSet::new(100);
        for i in 0..99 {
            ds.union(i, i + 1);
        }
        assert_eq!(ds.set_count(), 1);
        let root = ds.find(0);
        for i in 0..100 {
            assert_eq!(ds.find(i), root);
        }
        assert_eq!(ds.set_size(50), 100);
    }

    #[test]
    fn union_is_idempotent_on_counts() {
        let mut ds = DisjointSet::new(4);
        assert!(ds.union(0, 1));
        for _ in 0..10 {
            assert!(!ds.union(0, 1)); // repeated unions don't change anything
        }
        assert_eq!(ds.set_count(), 3);
    }

    #[test]
    fn serde_round_trip() {
        let mut ds = DisjointSet::new(5);
        ds.union(0, 1);
        ds.union(2, 3);
        let j = serde_json::to_string(&ds).unwrap();
        let mut back: DisjointSet = serde_json::from_str(&j).unwrap();
        assert_eq!(back.set_count(), 3);
        assert!(back.connected(0, 1));
        assert!(back.connected(2, 3));
        assert!(!back.connected(0, 2));
    }

    #[test]
    fn empty_set_is_well_behaved() {
        let mut ds = DisjointSet::new(0);
        assert!(ds.is_empty());
        assert_eq!(ds.set_count(), 0);
        assert!(ds.groups().is_empty());
        assert_eq!(components(0, &[]), Vec::<Vec<usize>>::new());
    }
}
