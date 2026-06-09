//! `sovereign-pagerank` — who matters in a graph of links.
//!
//! When knowledge is a graph — documents that cite documents, entities that
//! mention entities — a good first cut at "which nodes matter most" is
//! **PageRank**. The intuition is a random surfer: most steps they follow an
//! outgoing link at random, but with probability `1 − damping` they teleport to a
//! random node. A node's PageRank is the long-run fraction of time the surfer
//! spends there, so a node is important if important nodes link to it. It is the
//! ranking signal behind link analysis and the entity/document ranking step of
//! GraphRAG.
//!
//! This crate computes it by **power iteration**: start every node equal, and
//! repeatedly push each node's score along its outgoing edges (splitting it among
//! them), mix in the teleport term, and stop when the scores stop moving. Two
//! details make it correct: a **dangling node** (no outgoing edges) would leak
//! probability, so its score is redistributed to everyone each step; and the
//! result is normalized to sum to one, a proper distribution.
//!
//! [`pagerank`] takes the node count and the directed `edges` and returns the
//! score vector; [`top_k`] ranks the nodes; the [`PageRankConfig`] tunes damping,
//! iteration cap, and convergence tolerance.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the pagerank surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// PageRank configuration.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct PageRankConfig {
    /// Damping factor (probability of following a link vs teleporting); 0.85 std.
    pub damping: f64,
    /// Maximum power-iteration steps.
    pub max_iters: usize,
    /// L1 convergence tolerance (stop when the score vector moves less than this).
    pub tolerance: f64,
}

impl Default for PageRankConfig {
    fn default() -> Self {
        Self {
            damping: 0.85,
            max_iters: 100,
            tolerance: 1e-8,
        }
    }
}

/// Compute PageRank for a graph of `num_nodes` nodes and directed `edges`
/// (`(from, to)`). Returns a score per node, summing to ~1 (an empty graph yields
/// an empty vector; edges referencing out-of-range nodes are ignored).
pub fn pagerank(num_nodes: usize, edges: &[(usize, usize)], cfg: PageRankConfig) -> Vec<f64> {
    if num_nodes == 0 {
        return Vec::new();
    }
    let n = num_nodes;
    let d = cfg.damping.clamp(0.0, 1.0);

    // out-edges and out-degree per node.
    let mut out: Vec<Vec<usize>> = vec![Vec::new(); n];
    for &(from, to) in edges {
        if from < n && to < n {
            out[from].push(to);
        }
    }
    let out_deg: Vec<usize> = out.iter().map(|v| v.len()).collect();

    let mut rank = vec![1.0 / n as f64; n];
    let base = (1.0 - d) / n as f64;

    for _ in 0..cfg.max_iters.max(1) {
        let mut next = vec![base; n];

        // dangling mass: scores on nodes with no out-edges, redistributed evenly.
        let dangling: f64 = (0..n).filter(|&i| out_deg[i] == 0).map(|i| rank[i]).sum();
        let dangling_share = d * dangling / n as f64;
        for x in next.iter_mut() {
            *x += dangling_share;
        }

        // push each node's score along its out-edges.
        for i in 0..n {
            if out_deg[i] == 0 {
                continue;
            }
            let share = d * rank[i] / out_deg[i] as f64;
            for &j in &out[i] {
                next[j] += share;
            }
        }

        // convergence check (L1) and normalization.
        let delta: f64 = rank
            .iter()
            .zip(next.iter())
            .map(|(a, b)| (a - b).abs())
            .sum();
        rank = next;
        if delta < cfg.tolerance {
            break;
        }
    }

    // normalize to sum 1 (guards against tiny drift).
    let total: f64 = rank.iter().sum();
    if total > 0.0 {
        for x in rank.iter_mut() {
            *x /= total;
        }
    }
    rank
}

/// The `k` highest-PageRank node indices with their scores, best first (ties by
/// index).
pub fn top_k(scores: &[f64], k: usize) -> Vec<(usize, f64)> {
    let mut idx: Vec<(usize, f64)> = scores.iter().copied().enumerate().collect();
    idx.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
    idx.truncate(k);
    idx
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-6
    }

    #[test]
    fn scores_sum_to_one() {
        let edges = [(0, 1), (1, 2), (2, 0), (0, 2)];
        let r = pagerank(3, &edges, PageRankConfig::default());
        assert!(
            approx(r.iter().sum::<f64>(), 1.0),
            "sum {}",
            r.iter().sum::<f64>()
        );
    }

    #[test]
    fn hub_node_ranks_highest() {
        // everyone links to node 0 → node 0 is the most important.
        let edges = [(1, 0), (2, 0), (3, 0), (1, 2)];
        let r = pagerank(4, &edges, PageRankConfig::default());
        let best = top_k(&r, 1)[0].0;
        assert_eq!(best, 0, "scores {r:?}");
    }

    #[test]
    fn symmetric_graph_is_uniform() {
        // a directed cycle: every node has identical structure → equal ranks.
        let edges = [(0, 1), (1, 2), (2, 3), (3, 0)];
        let r = pagerank(4, &edges, PageRankConfig::default());
        for x in &r {
            assert!(approx(*x, 0.25), "ranks {r:?}");
        }
    }

    #[test]
    fn dangling_node_handled() {
        // node 2 has no out-edges; its mass must be redistributed, not lost.
        let edges = [(0, 1), (1, 2)];
        let r = pagerank(3, &edges, PageRankConfig::default());
        assert!(approx(r.iter().sum::<f64>(), 1.0));
        // node 2 receives from 1 and is a sink → should have decent rank.
        assert!(r[2] > 0.0);
    }

    #[test]
    fn isolated_nodes_get_teleport_share() {
        // no edges at all → uniform from teleportation.
        let r = pagerank(5, &[], PageRankConfig::default());
        for x in &r {
            assert!(approx(*x, 0.2), "ranks {r:?}");
        }
    }

    #[test]
    fn more_inlinks_means_higher_rank() {
        // node 0 gets 3 inlinks, node 4 gets 1 → 0 ranks above 4.
        let edges = [(1, 0), (2, 0), (3, 0), (1, 4)];
        let r = pagerank(5, &edges, PageRankConfig::default());
        assert!(r[0] > r[4]);
    }

    #[test]
    fn top_k_ordering() {
        let scores = [0.1, 0.5, 0.2, 0.4];
        let top = top_k(&scores, 2);
        assert_eq!(top[0].0, 1);
        assert_eq!(top[1].0, 3);
    }

    #[test]
    fn out_of_range_edges_ignored() {
        // an edge to a non-existent node must not panic.
        let r = pagerank(2, &[(0, 9), (1, 0)], PageRankConfig::default());
        assert_eq!(r.len(), 2);
        assert!(approx(r.iter().sum::<f64>(), 1.0));
    }

    #[test]
    fn empty_graph() {
        assert!(pagerank(0, &[], PageRankConfig::default()).is_empty());
    }
}
