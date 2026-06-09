//! `sovereign-graph-path` — how are two things connected, and how far?
//!
//! Reasoning over a knowledge graph often comes down to a path: *how* is this
//! entity related to that one, and what is the cheapest chain of links between
//! them? This crate answers that with the two standard shortest-path algorithms.
//!
//! **Dijkstra** ([`shortest_path`], [`distances_from`]) handles edges with
//! non-negative weights — a relationship strength, a distance, an inverse
//! confidence — finding the minimum-total-weight route by always expanding the
//! closest not-yet-settled node from a priority queue. **BFS**
//! ([`bfs_path`]) handles the unweighted case, returning a path with the fewest
//! hops, which is what you want when every edge counts the same.
//!
//! Both return the actual node sequence (reconstructed from predecessor links),
//! not just the distance, so you can show the chain of entities and relations.
//! [`distances_from`] gives the cost to every reachable node from one source —
//! the basis for "what is within N hops" neighbourhood queries.
//!
//! Graphs are directed; pass each edge twice for an undirected graph. Edges with
//! out-of-range endpoints are ignored.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{BinaryHeap, VecDeque};

/// Schema version of the graph-path surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A found path with its total cost.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Path {
    /// The node sequence from source to destination (inclusive).
    pub nodes: Vec<usize>,
    /// The total edge weight (hop count for BFS).
    pub cost: f64,
}

/// Build a directed weighted adjacency list. Edges are `(from, to, weight)`;
/// out-of-range endpoints and negative weights are dropped (Dijkstra needs
/// non-negative weights).
fn adjacency(n: usize, edges: &[(usize, usize, f64)]) -> Vec<Vec<(usize, f64)>> {
    let mut adj = vec![Vec::new(); n];
    for &(a, b, w) in edges {
        if a < n && b < n && w >= 0.0 && w.is_finite() {
            adj[a].push((b, w));
        }
    }
    adj
}

/// A min-heap entry keyed on distance (smaller distance = higher priority).
#[derive(PartialEq)]
struct HeapItem {
    dist: f64,
    node: usize,
}
impl Eq for HeapItem {}
impl Ord for HeapItem {
    fn cmp(&self, other: &Self) -> Ordering {
        // reverse so BinaryHeap (max-heap) yields the smallest distance first.
        other
            .dist
            .total_cmp(&self.dist)
            .then(other.node.cmp(&self.node))
    }
}
impl PartialOrd for HeapItem {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

/// The shortest-path cost from `src` to every node (`None` if unreachable), by
/// Dijkstra. Returns an empty vector for an out-of-range source.
pub fn distances_from(n: usize, edges: &[(usize, usize, f64)], src: usize) -> Vec<Option<f64>> {
    if src >= n {
        return Vec::new();
    }
    let adj = adjacency(n, edges);
    let mut dist = vec![f64::INFINITY; n];
    dist[src] = 0.0;
    let mut heap = BinaryHeap::new();
    heap.push(HeapItem {
        dist: 0.0,
        node: src,
    });
    while let Some(HeapItem { dist: d, node }) = heap.pop() {
        if d > dist[node] {
            continue; // stale entry
        }
        for &(to, w) in &adj[node] {
            let nd = d + w;
            if nd < dist[to] {
                dist[to] = nd;
                heap.push(HeapItem { dist: nd, node: to });
            }
        }
    }
    dist.into_iter()
        .map(|d| if d.is_finite() { Some(d) } else { None })
        .collect()
}

/// The minimum-weight path from `src` to `dst` by Dijkstra, or `None` if `dst` is
/// unreachable (or either endpoint is out of range).
pub fn shortest_path(
    n: usize,
    edges: &[(usize, usize, f64)],
    src: usize,
    dst: usize,
) -> Option<Path> {
    if src >= n || dst >= n {
        return None;
    }
    let adj = adjacency(n, edges);
    let mut dist = vec![f64::INFINITY; n];
    let mut prev = vec![usize::MAX; n];
    dist[src] = 0.0;
    let mut heap = BinaryHeap::new();
    heap.push(HeapItem {
        dist: 0.0,
        node: src,
    });
    while let Some(HeapItem { dist: d, node }) = heap.pop() {
        if node == dst {
            break;
        }
        if d > dist[node] {
            continue;
        }
        for &(to, w) in &adj[node] {
            let nd = d + w;
            if nd < dist[to] {
                dist[to] = nd;
                prev[to] = node;
                heap.push(HeapItem { dist: nd, node: to });
            }
        }
    }
    reconstruct(src, dst, &prev).map(|nodes| Path {
        nodes,
        cost: dist[dst],
    })
}

/// The fewest-hops path from `src` to `dst` over `edges` treated as unweighted,
/// by BFS. `None` if unreachable.
pub fn bfs_path(n: usize, edges: &[(usize, usize)], src: usize, dst: usize) -> Option<Path> {
    if src >= n || dst >= n {
        return None;
    }
    let mut adj = vec![Vec::new(); n];
    for &(a, b) in edges {
        if a < n && b < n {
            adj[a].push(b);
        }
    }
    let mut prev = vec![usize::MAX; n];
    let mut visited = vec![false; n];
    visited[src] = true;
    let mut q = VecDeque::new();
    q.push_back(src);
    while let Some(node) = q.pop_front() {
        if node == dst {
            break;
        }
        for &to in &adj[node] {
            if !visited[to] {
                visited[to] = true;
                prev[to] = node;
                q.push_back(to);
            }
        }
    }
    if !visited[dst] {
        return None;
    }
    reconstruct(src, dst, &prev).map(|nodes| {
        let cost = (nodes.len() - 1) as f64;
        Path { nodes, cost }
    })
}

/// Rebuild the path src..=dst from predecessor links, or `None` if dst is
/// unreached (and not the source itself).
fn reconstruct(src: usize, dst: usize, prev: &[usize]) -> Option<Vec<usize>> {
    if src == dst {
        return Some(vec![src]);
    }
    if prev[dst] == usize::MAX {
        return None;
    }
    let mut path = vec![dst];
    let mut cur = dst;
    while cur != src {
        cur = prev[cur];
        if cur == usize::MAX {
            return None;
        }
        path.push(cur);
    }
    path.reverse();
    Some(path)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn dijkstra_finds_cheapest_route() {
        // 0 →(1)→ 1 →(1)→ 3  total 2 ; vs 0 →(5)→ 3 direct
        let edges = [
            (0, 1, 1.0),
            (1, 3, 1.0),
            (0, 3, 5.0),
            (0, 2, 2.0),
            (2, 3, 2.0),
        ];
        let p = shortest_path(4, &edges, 0, 3).unwrap();
        assert_eq!(p.nodes, vec![0, 1, 3]);
        assert!(approx(p.cost, 2.0));
    }

    #[test]
    fn unreachable_is_none() {
        let edges = [(0, 1, 1.0)];
        assert!(shortest_path(3, &edges, 0, 2).is_none());
        assert!(bfs_path(3, &[(0, 1)], 0, 2).is_none());
    }

    #[test]
    fn source_to_self() {
        let p = shortest_path(3, &[(0, 1, 1.0)], 1, 1).unwrap();
        assert_eq!(p.nodes, vec![1]);
        assert!(approx(p.cost, 0.0));
    }

    #[test]
    fn bfs_finds_fewest_hops() {
        // a longer cheap-weight route vs a short hop route: BFS picks fewest hops.
        let edges = [(0, 1), (1, 2), (2, 3), (0, 3)];
        let p = bfs_path(4, &edges, 0, 3).unwrap();
        assert_eq!(p.nodes, vec![0, 3]); // 1 hop, not 0-1-2-3
        assert!(approx(p.cost, 1.0));
    }

    #[test]
    fn distances_from_source() {
        let edges = [(0, 1, 2.0), (1, 2, 3.0), (0, 2, 10.0)];
        let d = distances_from(3, &edges, 0);
        assert_eq!(d[0], Some(0.0));
        assert_eq!(d[1], Some(2.0));
        assert_eq!(d[2], Some(5.0)); // via 1, not the direct 10
    }

    #[test]
    fn multi_hop_entity_connection() {
        // a knowledge-graph-style chain: alice(0) - paper(1) - topic(2) - bob(3)
        let edges = [(0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0)];
        let p = shortest_path(4, &edges, 0, 3).unwrap();
        assert_eq!(p.nodes, vec![0, 1, 2, 3]);
        assert!(approx(p.cost, 3.0));
    }

    #[test]
    fn negative_weights_dropped() {
        // a negative-weight edge is ignored (Dijkstra requires non-negative).
        let edges = [(0, 1, -5.0), (0, 1, 2.0)];
        let p = shortest_path(2, &edges, 0, 1).unwrap();
        assert!(approx(p.cost, 2.0));
    }

    #[test]
    fn out_of_range() {
        assert!(shortest_path(2, &[(0, 1, 1.0)], 5, 0).is_none());
        assert!(distances_from(2, &[], 9).is_empty());
    }

    #[test]
    fn serde_round_trip() {
        let p = shortest_path(3, &[(0, 1, 1.0), (1, 2, 1.0)], 0, 2).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: Path = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
