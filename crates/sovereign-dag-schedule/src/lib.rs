//! `sovereign-dag-schedule` — turn "X before Y" constraints into a runnable plan.
//!
//! An agent's work is rarely a flat list: this tool call needs that file written
//! first, those two fetches can run at once, the summary waits on all of them.
//! Expressed as a **directed acyclic graph** of dependencies, the question becomes
//! scheduling — in what order, and what may overlap. This crate answers it.
//!
//! [`Dag::topological_order`] gives a single linear order respecting every
//! dependency (Kahn's algorithm, ties broken by lowest index for determinism), and
//! fails cleanly if the constraints contain a **cycle** — a contradiction no order
//! can satisfy. [`Dag::waves`] goes further: it groups the tasks into parallel
//! levels where every task in a wave depends only on earlier waves, so a runtime
//! can fire each wave concurrently — the wave count is the number of sequential
//! rounds the plan needs.
//!
//! [`Dag::critical_path`] finds the longest weighted chain through the graph: with
//! unlimited parallelism that chain *is* the makespan, the soonest everything can
//! finish, and the tasks on it are the ones worth speeding up. [`Dag::critical_path_length`]
//! is the unit-cost version (the depth of the deepest dependency chain).
//!
//! Edges read "before → after": `add_dependency(a, b)` means `a` must complete
//! before `b` starts. Cycle detection is built into every query, so an invalid
//! plan is always reported rather than silently mis-ordered.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BinaryHeap;

/// Schema version of the DAG-schedule surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A directed dependency graph over `num_nodes` tasks indexed `0..num_nodes`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Dag {
    num_nodes: usize,
    /// `succ[u]` = tasks that depend on `u` (must run after it).
    succ: Vec<Vec<usize>>,
    /// In-degree (number of dependencies) of each task.
    indegree: Vec<usize>,
    /// Number of edges added (deduplicated).
    edge_count: usize,
}

/// Errors from building or scheduling a DAG.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum DagError {
    /// A referenced node id was outside `0..num_nodes`.
    NodeOutOfRange {
        /// The offending node id.
        node: usize,
        /// The graph's node count.
        num_nodes: usize,
    },
    /// The dependencies contain a cycle, so no valid order exists.
    Cycle,
}

impl std::fmt::Display for DagError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DagError::NodeOutOfRange { node, num_nodes } => {
                write!(f, "node {node} out of range 0..{num_nodes}")
            }
            DagError::Cycle => write!(f, "dependency cycle: no valid topological order"),
        }
    }
}
impl std::error::Error for DagError {}

impl Dag {
    /// A graph of `num_nodes` tasks and no dependencies.
    pub fn new(num_nodes: usize) -> Self {
        Self {
            num_nodes,
            succ: vec![Vec::new(); num_nodes],
            indegree: vec![0; num_nodes],
            edge_count: 0,
        }
    }

    /// Number of tasks.
    pub fn num_nodes(&self) -> usize {
        self.num_nodes
    }
    /// Number of (deduplicated) dependency edges.
    pub fn edge_count(&self) -> usize {
        self.edge_count
    }

    /// Add a dependency: `before` must complete before `after` starts. A duplicate
    /// or self-edge is rejected/ignored: a self-edge would be an immediate cycle, so
    /// it is recorded as an edge (and later surfaces as a cycle); duplicates are
    /// skipped so in-degrees stay correct.
    pub fn add_dependency(&mut self, before: usize, after: usize) -> Result<(), DagError> {
        if before >= self.num_nodes {
            return Err(DagError::NodeOutOfRange {
                node: before,
                num_nodes: self.num_nodes,
            });
        }
        if after >= self.num_nodes {
            return Err(DagError::NodeOutOfRange {
                node: after,
                num_nodes: self.num_nodes,
            });
        }
        // skip exact duplicates so indegree counting stays consistent.
        if self.succ[before].contains(&after) {
            return Ok(());
        }
        self.succ[before].push(after);
        self.indegree[after] += 1;
        self.edge_count += 1;
        Ok(())
    }

    /// The tasks `task` directly depends on are not stored explicitly; the tasks
    /// that depend on `task` (its successors) are.
    pub fn dependents(&self, task: usize) -> &[usize] {
        self.succ.get(task).map(|v| v.as_slice()).unwrap_or(&[])
    }

    /// A linear order satisfying every dependency (lowest index first among ready
    /// tasks). `Err(Cycle)` if no order exists.
    pub fn topological_order(&self) -> Result<Vec<usize>, DagError> {
        let mut indeg = self.indegree.clone();
        // min-heap via Reverse so the smallest ready index comes first.
        let mut ready: BinaryHeap<std::cmp::Reverse<usize>> = BinaryHeap::new();
        for (i, &d) in indeg.iter().enumerate() {
            if d == 0 {
                ready.push(std::cmp::Reverse(i));
            }
        }
        let mut order = Vec::with_capacity(self.num_nodes);
        while let Some(std::cmp::Reverse(u)) = ready.pop() {
            order.push(u);
            for &v in &self.succ[u] {
                indeg[v] -= 1;
                if indeg[v] == 0 {
                    ready.push(std::cmp::Reverse(v));
                }
            }
        }
        if order.len() == self.num_nodes {
            Ok(order)
        } else {
            Err(DagError::Cycle)
        }
    }

    /// Parallel-wave schedule: `waves[k]` is the set of tasks (ascending) whose
    /// dependencies all lie in earlier waves, so each wave can run concurrently.
    /// The number of waves is the count of sequential rounds. `Err(Cycle)` if no
    /// schedule exists.
    pub fn waves(&self) -> Result<Vec<Vec<usize>>, DagError> {
        let mut indeg = self.indegree.clone();
        let mut current: Vec<usize> = (0..self.num_nodes).filter(|&i| indeg[i] == 0).collect();
        let mut waves = Vec::new();
        let mut scheduled = 0usize;
        while !current.is_empty() {
            current.sort_unstable();
            scheduled += current.len();
            let mut next = Vec::new();
            for &u in &current {
                for &v in &self.succ[u] {
                    indeg[v] -= 1;
                    if indeg[v] == 0 {
                        next.push(v);
                    }
                }
            }
            waves.push(std::mem::take(&mut current));
            current = next;
        }
        if scheduled == self.num_nodes {
            Ok(waves)
        } else {
            Err(DagError::Cycle)
        }
    }

    /// Whether the dependencies contain a cycle.
    pub fn has_cycle(&self) -> bool {
        self.topological_order().is_err()
    }
    /// Whether this is a valid DAG (no cycle).
    pub fn is_dag(&self) -> bool {
        !self.has_cycle()
    }

    /// The depth of the deepest dependency chain (number of tasks on it). With
    /// unit task costs this is the minimum number of sequential rounds. `None` on a
    /// cycle.
    pub fn critical_path_length(&self) -> Option<usize> {
        let order = self.topological_order().ok()?;
        let mut depth = vec![1usize; self.num_nodes];
        let mut best = 0;
        for &u in &order {
            for &v in &self.succ[u] {
                if depth[u] + 1 > depth[v] {
                    depth[v] = depth[u] + 1;
                }
            }
            best = best.max(depth[u]);
        }
        Some(best)
    }

    /// The longest weighted chain (critical path) given per-task `durations`: the
    /// total duration and the task sequence. With unlimited parallelism this total
    /// is the makespan. `None` on a cycle or if `durations.len() != num_nodes`.
    pub fn critical_path(&self, durations: &[f64]) -> Option<(f64, Vec<usize>)> {
        if durations.len() != self.num_nodes {
            return None;
        }
        let order = self.topological_order().ok()?;
        // longest finishing time to each node, with predecessor for traceback.
        let mut finish = durations.to_vec();
        let mut prev = vec![usize::MAX; self.num_nodes];
        for &u in &order {
            for &v in &self.succ[u] {
                let cand = finish[u] + durations[v];
                if cand > finish[v] {
                    finish[v] = cand;
                    prev[v] = u;
                }
            }
        }
        // node with the maximum finishing time ends the critical path.
        let mut end = 0usize;
        for i in 1..self.num_nodes {
            if finish[i] > finish[end] {
                end = i;
            }
        }
        if self.num_nodes == 0 {
            return Some((0.0, Vec::new()));
        }
        let total = finish[end];
        let mut path = vec![end];
        let mut cur = end;
        while prev[cur] != usize::MAX {
            cur = prev[cur];
            path.push(cur);
        }
        path.reverse();
        Some((total, path))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dag(n: usize, deps: &[(usize, usize)]) -> Dag {
        let mut d = Dag::new(n);
        for &(a, b) in deps {
            d.add_dependency(a, b).unwrap();
        }
        d
    }

    /// Check an order respects all dependencies.
    fn respects(order: &[usize], deps: &[(usize, usize)]) -> bool {
        let pos: std::collections::HashMap<usize, usize> =
            order.iter().enumerate().map(|(p, &n)| (n, p)).collect();
        deps.iter().all(|&(a, b)| pos[&a] < pos[&b])
    }

    #[test]
    fn linear_chain() {
        let d = dag(4, &[(0, 1), (1, 2), (2, 3)]);
        assert_eq!(d.topological_order().unwrap(), vec![0, 1, 2, 3]);
        assert_eq!(d.critical_path_length(), Some(4));
    }

    #[test]
    fn diamond() {
        let deps = [(0, 1), (0, 2), (1, 3), (2, 3)];
        let d = dag(4, &deps);
        let order = d.topological_order().unwrap();
        assert!(respects(&order, &deps));
        assert_eq!(order, vec![0, 1, 2, 3]); // deterministic lowest-index
        let waves = d.waves().unwrap();
        assert_eq!(waves, vec![vec![0], vec![1, 2], vec![3]]);
        assert_eq!(d.critical_path_length(), Some(3));
    }

    #[test]
    fn independent_tasks_one_wave() {
        let d = dag(3, &[]);
        let waves = d.waves().unwrap();
        assert_eq!(waves, vec![vec![0, 1, 2]]);
        assert_eq!(d.critical_path_length(), Some(1));
    }

    #[test]
    fn cycle_detected() {
        let d = dag(3, &[(0, 1), (1, 2), (2, 0)]);
        assert!(d.has_cycle());
        assert_eq!(d.topological_order(), Err(DagError::Cycle));
        assert_eq!(d.waves(), Err(DagError::Cycle));
        assert_eq!(d.critical_path_length(), None);
    }

    #[test]
    fn self_loop_is_cycle() {
        let mut d = Dag::new(2);
        d.add_dependency(0, 0).unwrap();
        assert!(d.has_cycle());
    }

    #[test]
    fn out_of_range_rejected() {
        let mut d = Dag::new(2);
        assert_eq!(
            d.add_dependency(0, 5),
            Err(DagError::NodeOutOfRange {
                node: 5,
                num_nodes: 2
            })
        );
        assert_eq!(
            d.add_dependency(9, 0),
            Err(DagError::NodeOutOfRange {
                node: 9,
                num_nodes: 2
            })
        );
    }

    #[test]
    fn duplicate_edges_ignored() {
        let mut d = Dag::new(2);
        d.add_dependency(0, 1).unwrap();
        d.add_dependency(0, 1).unwrap();
        assert_eq!(d.edge_count(), 1);
        // indegree stays correct → still a valid single ordering.
        assert_eq!(d.topological_order().unwrap(), vec![0, 1]);
    }

    #[test]
    fn weighted_critical_path() {
        // 0 -> {1, 2} -> 3 ; durations make the 0-2-3 branch the critical one.
        let d = dag(4, &[(0, 1), (0, 2), (1, 3), (2, 3)]);
        let durations = [1.0, 2.0, 5.0, 1.0];
        let (total, path) = d.critical_path(&durations).unwrap();
        // 0(1) + 2(5) + 3(1) = 7 ; vs 0+1+3 = 1+2+1 = 4.
        assert!((total - 7.0).abs() < 1e-9, "total {total}");
        assert_eq!(path, vec![0, 2, 3]);
    }

    #[test]
    fn critical_path_bad_durations() {
        let d = dag(3, &[(0, 1)]);
        assert!(d.critical_path(&[1.0, 2.0]).is_none()); // wrong length
    }

    #[test]
    fn disconnected_components() {
        // two independent chains.
        let deps = [(0, 1), (2, 3)];
        let d = dag(4, &deps);
        let order = d.topological_order().unwrap();
        assert!(respects(&order, &deps));
        let waves = d.waves().unwrap();
        assert_eq!(waves, vec![vec![0, 2], vec![1, 3]]);
    }

    #[test]
    fn dependents_listed() {
        let d = dag(3, &[(0, 1), (0, 2)]);
        assert_eq!(d.dependents(0), &[1, 2]);
        assert_eq!(d.dependents(1), &[] as &[usize]);
    }

    #[test]
    fn larger_random_order_is_valid() {
        // a wider DAG; the order must respect every edge.
        let deps = [
            (0, 3),
            (1, 3),
            (1, 4),
            (2, 4),
            (3, 5),
            (4, 5),
            (5, 6),
            (2, 6),
        ];
        let d = dag(7, &deps);
        let order = d.topological_order().unwrap();
        assert!(respects(&order, &deps));
        assert_eq!(order.len(), 7);
        // the longest chain is 0/1 -> 3 -> 5 -> 6 (or via 4): length 4.
        assert_eq!(d.critical_path_length(), Some(4));
    }

    #[test]
    fn serde_round_trip() {
        let d = dag(4, &[(0, 1), (1, 2), (2, 3)]);
        let j = serde_json::to_string(&d).unwrap();
        let back: Dag = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
        assert_eq!(back.topological_order().unwrap(), vec![0, 1, 2, 3]);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
