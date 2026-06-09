//! `sovereign-community-detect` — find the densely-connected groups in a graph.
//!
//! A knowledge graph clumps: a set of documents about one topic cite each other
//! far more than they cite anything else, a cluster of entities co-occur. Finding
//! those **communities** is the grouping step of GraphRAG (summarize each
//! community) and a general "what belongs together" answer over a link structure.
//!
//! This crate uses **label propagation** (Raghavan, Albert, Kumara). Every node
//! starts with its own label; then, repeatedly and in a randomized order, each
//! node adopts the label held by the most of its neighbours (ties broken
//! randomly). Densely-connected groups quickly agree on a shared label, and the
//! process converges in near-linear time with no parameter to tune and no target
//! number of communities to guess. The randomized order and tie-breaking are
//! seeded, so the result is reproducible.
//!
//! [`detect`] returns a community id per node; [`communities`] groups the nodes;
//! and [`modularity`] scores a partition — the fraction of edges inside
//! communities minus what you'd expect by chance, the standard measure of how
//! good the grouping is (higher, up to ~1, is better).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap};

/// Schema version of the community-detect surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Label-propagation configuration.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Config {
    /// Maximum propagation rounds.
    pub max_iters: usize,
    /// RNG seed for node order and tie-breaking.
    pub seed: u64,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            max_iters: 50,
            seed: 0x5EED,
        }
    }
}

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
    /// Fisher-Yates shuffle.
    fn shuffle(&mut self, v: &mut [usize]) {
        for i in (1..v.len()).rev() {
            let j = (self.next() % (i as u64 + 1)) as usize;
            v.swap(i, j);
        }
    }
}

/// Build an undirected adjacency list from `edges` over `n` nodes (self-loops and
/// out-of-range endpoints ignored; the graph is symmetrized).
fn adjacency(n: usize, edges: &[(usize, usize)]) -> Vec<Vec<usize>> {
    let mut adj = vec![Vec::new(); n];
    for &(a, b) in edges {
        if a < n && b < n && a != b {
            adj[a].push(b);
            adj[b].push(a);
        }
    }
    adj
}

/// Detect communities by label propagation. Returns a community id (a small
/// integer, densely packed from 0) for each of the `n` nodes.
pub fn detect(n: usize, edges: &[(usize, usize)], cfg: Config) -> Vec<usize> {
    if n == 0 {
        return Vec::new();
    }
    let adj = adjacency(n, edges);
    let mut label: Vec<usize> = (0..n).collect();
    let mut rng = Rng(cfg.seed | 1);
    let mut order: Vec<usize> = (0..n).collect();

    for _ in 0..cfg.max_iters.max(1) {
        rng.shuffle(&mut order);
        let mut changed = false;
        for &node in &order {
            if adj[node].is_empty() {
                continue;
            }
            // count neighbour labels.
            let mut counts: HashMap<usize, usize> = HashMap::new();
            for &nbr in &adj[node] {
                *counts.entry(label[nbr]).or_insert(0) += 1;
            }
            let max = counts.values().copied().max().unwrap();
            // tie-break, Raghavan-style: if the node's *current* label is already
            // among the most-frequent neighbour labels, retain it. This stabilizes
            // the partition and is what stops two well-separated groups from
            // collapsing into one community during the noisy early sweeps.
            let cur = label[node];
            let cur_is_max = counts.get(&cur).copied().unwrap_or(0) == max;
            let chosen = if cur_is_max {
                cur
            } else {
                // otherwise pick uniformly among the maxima. The candidate list is
                // sorted first because `HashMap` iteration order is randomized per
                // process — without it the seeded pick would not be reproducible.
                let mut top: Vec<usize> = counts
                    .iter()
                    .filter(|&(_, &c)| c == max)
                    .map(|(&l, _)| l)
                    .collect();
                top.sort_unstable();
                top[(rng.next() as usize) % top.len()]
            };
            if chosen != label[node] {
                label[node] = chosen;
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }

    // densely renumber labels to 0..num_communities.
    let mut remap: BTreeMap<usize, usize> = BTreeMap::new();
    for &l in &label {
        let next = remap.len();
        remap.entry(l).or_insert(next);
    }
    label.iter().map(|l| remap[l]).collect()
}

/// Group node indices by their community label (sorted: communities by smallest
/// member, members ascending).
pub fn communities(labels: &[usize]) -> Vec<Vec<usize>> {
    let mut by_label: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
    for (node, &l) in labels.iter().enumerate() {
        by_label.entry(l).or_default().push(node);
    }
    let mut groups: Vec<Vec<usize>> = by_label.into_values().collect();
    groups.sort_by_key(|g| g[0]);
    groups
}

/// Newman modularity of a partition: the fraction of edges that fall *within*
/// communities minus the expected fraction if edges were placed at random
/// (preserving degrees). Range roughly `[-0.5, 1]`; higher is a stronger
/// community structure. Returns 0 for an edgeless graph.
pub fn modularity(n: usize, edges: &[(usize, usize)], labels: &[usize]) -> f64 {
    let adj = adjacency(n, edges);
    let degree: Vec<usize> = adj.iter().map(|v| v.len()).collect();
    let two_m: f64 = degree.iter().sum::<usize>() as f64; // = 2 * |edges|
    if two_m == 0.0 {
        return 0.0;
    }
    let mut q = 0.0;
    for i in 0..n {
        for j in 0..n {
            if labels.get(i) == labels.get(j) {
                let a_ij = adj[i].iter().filter(|&&x| x == j).count() as f64;
                let expected = degree[i] as f64 * degree[j] as f64 / two_m;
                q += a_ij - expected;
            }
        }
    }
    q / two_m
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn two_cliques_are_two_communities() {
        // {0,1,2} fully connected and {3,4,5} fully connected, one bridge edge.
        let edges = [
            (0, 1),
            (1, 2),
            (0, 2), // clique A
            (3, 4),
            (4, 5),
            (3, 5), // clique B
            (2, 3), // weak bridge
        ];
        let labels = detect(6, &edges, Config::default());
        // 0,1,2 share a label; 3,4,5 share a (different) label.
        assert_eq!(labels[0], labels[1]);
        assert_eq!(labels[1], labels[2]);
        assert_eq!(labels[3], labels[4]);
        assert_eq!(labels[4], labels[5]);
        assert_ne!(labels[0], labels[3]);
    }

    #[test]
    fn communities_groups_nodes() {
        let edges = [(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5)];
        let labels = detect(6, &edges, Config::default());
        let groups = communities(&labels);
        assert_eq!(groups.len(), 2);
        // every node accounted for once
        let all: Vec<usize> = groups.iter().flatten().copied().collect();
        let mut s = all.clone();
        s.sort_unstable();
        assert_eq!(s, (0..6).collect::<Vec<_>>());
    }

    #[test]
    fn modularity_higher_for_good_partition() {
        let edges = [(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5), (2, 3)];
        // good partition: the two cliques.
        let good = [0, 0, 0, 1, 1, 1];
        // bad partition: everyone in one community.
        let bad = [0, 0, 0, 0, 0, 0];
        let q_good = modularity(6, &edges, &good);
        let q_bad = modularity(6, &edges, &bad);
        assert!(q_good > q_bad, "good {q_good} bad {q_bad}");
        assert!(q_good > 0.3, "good modularity {q_good}");
    }

    #[test]
    fn isolated_nodes_keep_own_community() {
        // node 2 has no edges → its own community.
        let edges = [(0, 1)];
        let labels = detect(3, &edges, Config::default());
        assert_eq!(labels[0], labels[1]);
        assert_ne!(labels[2], labels[0]);
    }

    #[test]
    fn deterministic_for_seed() {
        let edges = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (2, 3)];
        let a = detect(
            6,
            &edges,
            Config {
                max_iters: 50,
                seed: 7,
            },
        );
        let b = detect(
            6,
            &edges,
            Config {
                max_iters: 50,
                seed: 7,
            },
        );
        assert_eq!(a, b);
    }

    #[test]
    fn labels_are_densely_numbered() {
        let edges = [(0, 1), (2, 3)];
        let labels = detect(4, &edges, Config::default());
        let max = *labels.iter().max().unwrap();
        // 2 communities → labels are 0 and 1.
        assert!(max <= 1);
    }

    #[test]
    fn empty_graph() {
        assert!(detect(0, &[], Config::default()).is_empty());
        assert_eq!(modularity(0, &[], &[]), 0.0);
    }

    #[test]
    fn serde_config_round_trip() {
        let c = Config {
            max_iters: 30,
            seed: 123,
        };
        let j = serde_json::to_string(&c).unwrap();
        assert_eq!(serde_json::from_str::<Config>(&j).unwrap(), c);
    }
}
