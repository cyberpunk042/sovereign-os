//! `sovereign-bktree` — fuzzy string lookup by edit distance, with pruning.
//!
//! "Did you mean…" over a misspelled tool name, command, or vocabulary entry is a
//! nearest-neighbour query in *edit-distance space*. Scanning the whole
//! dictionary and scoring every entry is `O(N)` per query; a **BK-tree** makes it
//! far cheaper by exploiting that Levenshtein distance is a *metric* and obeys
//! the triangle inequality.
//!
//! The tree stores each term at a node; every child edge is labelled with the
//! edit distance from the parent term to the child term, and a node has at most
//! one child per distance. To find all terms within radius `r` of a query `q`,
//! compute `d = dist(q, node.term)`; report the node if `d ≤ r`, then — by the
//! triangle inequality — only descend into child edges whose label lies in
//! `[d − r, d + r]`, because any term reachable through an edge labelled `e`
//! differs from `node.term` by exactly `e` and so differs from `q` by at least
//! `|d − e|`. Every other subtree is pruned without a single distance
//! computation, which is what keeps lookup sublinear on realistic dictionaries.
//!
//! Distances come from [`sovereign_edit_distance::levenshtein`], so the metric is
//! exactly the one used elsewhere in the stack.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_edit_distance::levenshtein;
use std::collections::BTreeMap;

/// Schema version of the BK-tree surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One node: a term plus its children keyed by edit distance from this term.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct Node {
    term: String,
    /// distance-from-this-term → child node index.
    children: BTreeMap<usize, usize>,
}

/// A BK-tree over a set of terms, queried by edit distance.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct BkTree {
    nodes: Vec<Node>,
}

/// A query hit: a term and its edit distance from the query.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Hit {
    /// The matched term.
    pub term: String,
    /// Its Levenshtein distance from the query.
    pub distance: usize,
}

impl BkTree {
    /// An empty tree.
    pub fn new() -> Self {
        Self::default()
    }

    /// Build a tree from a collection of terms.
    pub fn from_terms<I, S>(terms: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        let mut t = Self::new();
        for term in terms {
            t.insert(term);
        }
        t
    }

    /// Number of distinct terms in the tree.
    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    /// Whether the tree is empty.
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }

    /// Insert `term`. A duplicate term (distance 0 to an existing node) is a
    /// no-op, so the tree holds a set. Returns `true` if a new term was added.
    pub fn insert(&mut self, term: impl Into<String>) -> bool {
        let term = term.into();
        if self.nodes.is_empty() {
            self.nodes.push(Node {
                term,
                children: BTreeMap::new(),
            });
            return true;
        }
        let mut cur = 0usize;
        loop {
            let d = levenshtein(&term, &self.nodes[cur].term);
            if d == 0 {
                return false; // already present
            }
            match self.nodes[cur].children.get(&d) {
                Some(&next) => cur = next,
                None => {
                    let new_idx = self.nodes.len();
                    self.nodes.push(Node {
                        term,
                        children: BTreeMap::new(),
                    });
                    self.nodes[cur].children.insert(d, new_idx);
                    return true;
                }
            }
        }
    }

    /// Whether `term` is present exactly.
    pub fn contains(&self, term: &str) -> bool {
        self.within(term, 0).iter().any(|h| h.distance == 0)
    }

    /// All terms within edit distance `max_distance` of `query`, sorted by
    /// ascending distance then term. Prunes subtrees via the triangle inequality.
    pub fn within(&self, query: &str, max_distance: usize) -> Vec<Hit> {
        let mut hits = Vec::new();
        if self.nodes.is_empty() {
            return hits;
        }
        // explicit stack to avoid recursion depth limits on deep trees
        let mut stack = vec![0usize];
        while let Some(idx) = stack.pop() {
            let node = &self.nodes[idx];
            let d = levenshtein(query, &node.term);
            if d <= max_distance {
                hits.push(Hit {
                    term: node.term.clone(),
                    distance: d,
                });
            }
            // only children with edge label in [d - max, d + max] can hold a
            // term within max_distance of the query.
            let lo = d.saturating_sub(max_distance);
            let hi = d + max_distance;
            for (&edge, &child) in node.children.range(lo..=hi) {
                debug_assert!(edge >= lo && edge <= hi);
                stack.push(child);
            }
        }
        hits.sort_by(|a, b| {
            a.distance
                .cmp(&b.distance)
                .then_with(|| a.term.cmp(&b.term))
        });
        hits
    }

    /// The single closest term to `query` within `max_distance` (ties broken by
    /// term order), or `None` if nothing is close enough.
    pub fn closest(&self, query: &str, max_distance: usize) -> Option<Hit> {
        self.within(query, max_distance).into_iter().next()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dictionary() -> BkTree {
        BkTree::from_terms([
            "book", "books", "boo", "cook", "cake", "cape", "boon", "cart",
        ])
    }

    #[test]
    fn finds_terms_within_radius() {
        let t = dictionary();
        let mut got: Vec<String> = t.within("book", 1).into_iter().map(|h| h.term).collect();
        got.sort();
        // within edit distance 1 of "book": book(0), books(1), boo(1), cook(1), boon(1)
        assert_eq!(got, vec!["book", "books", "boo", "boon", "cook"].tap_sort());
    }

    #[test]
    fn distances_are_correct_and_sorted() {
        let t = dictionary();
        let hits = t.within("book", 1);
        assert_eq!(hits[0].term, "book");
        assert_eq!(hits[0].distance, 0);
        // all reported distances are <= 1 and ascending
        assert!(hits.windows(2).all(|w| w[0].distance <= w[1].distance));
        assert!(hits.iter().all(|h| h.distance <= 1));
    }

    #[test]
    fn matches_brute_force_for_many_queries() {
        let terms = [
            "alpha", "alpine", "alphabet", "beta", "delta", "gamma", "gammon", "ramp", "tramp",
            "stamp", "camp", "lamp",
        ];
        let t = BkTree::from_terms(terms);
        for q in ["alpha", "amp", "gamma", "tramp", "zzz", "alphz"] {
            for r in 0..=3 {
                let mut tree_hits: Vec<(String, usize)> = t
                    .within(q, r)
                    .into_iter()
                    .map(|h| (h.term, h.distance))
                    .collect();
                tree_hits.sort();
                let mut brute: Vec<(String, usize)> = terms
                    .iter()
                    .map(|s| (s.to_string(), levenshtein(q, s)))
                    .filter(|&(_, d)| d <= r)
                    .collect();
                brute.sort();
                assert_eq!(tree_hits, brute, "mismatch for query '{q}' radius {r}");
            }
        }
    }

    #[test]
    fn closest_returns_best_match() {
        let t = dictionary();
        // "cok" is not a member; nearest is "cook" at distance 1
        let c = t.closest("cok", 2).unwrap();
        assert_eq!(c.term, "cook");
        assert_eq!(c.distance, 1);
        // nothing within 0 of a non-member
        assert!(t.closest("xyzzy", 1).is_none());
    }

    #[test]
    fn contains_exact_terms_only() {
        let t = dictionary();
        assert!(t.contains("book"));
        assert!(t.contains("cake"));
        assert!(!t.contains("books2"));
        assert!(!t.contains("boo k"));
    }

    #[test]
    fn duplicate_inserts_are_ignored() {
        let mut t = BkTree::new();
        assert!(t.insert("hello"));
        assert!(!t.insert("hello")); // duplicate
        assert_eq!(t.len(), 1);
    }

    #[test]
    fn empty_tree_queries_are_empty() {
        let t = BkTree::new();
        assert!(t.is_empty());
        assert!(t.within("anything", 3).is_empty());
        assert!(t.closest("anything", 3).is_none());
        assert!(!t.contains("anything"));
    }

    #[test]
    fn serde_round_trip() {
        let t = dictionary();
        let j = serde_json::to_string(&t).unwrap();
        let back: BkTree = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
        assert_eq!(back.within("book", 1).len(), t.within("book", 1).len());
    }

    // tiny helper to sort a list of &str into a sorted Vec<String> inline
    trait TapSort {
        fn tap_sort(self) -> Vec<String>;
    }
    impl TapSort for Vec<&str> {
        fn tap_sort(self) -> Vec<String> {
            let mut v: Vec<String> = self.into_iter().map(String::from).collect();
            v.sort();
            v
        }
    }
}
