//! `sovereign-workflow-graph` — E0552: Plan/Compile (lifecycle step 5).
//!
//! "Plan/Compile produces a workflow graph … Edges define dependency and
//! order. The plan is not fixed forever; it can recompile after observations."
//! A workflow is a DAG of typed nodes; this crate fixes the eight node types,
//! validates the graph (no dangling edges, no cycles), and yields a
//! topological execution order.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::{HashMap, HashSet, VecDeque};

use serde::{Deserialize, Serialize};

/// The 8 workflow node types (E0552).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum NodeType {
    /// A model call.
    ModelCall,
    /// A tool call.
    ToolCall,
    /// A memory read.
    MemoryRead,
    /// A test run.
    TestRun,
    /// A policy gate.
    PolicyGate,
    /// A human gate.
    HumanGate,
    /// An eval.
    Eval,
    /// A commit.
    Commit,
}

/// One workflow node.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Node {
    /// Unique node id within the graph.
    pub id: String,
    /// What the node does.
    pub node_type: NodeType,
}

/// A dependency edge: `from` must complete before `to`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Edge {
    /// Predecessor node id.
    pub from: String,
    /// Successor node id (depends on `from`).
    pub to: String,
}

/// A workflow graph: typed nodes + dependency edges.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkflowGraph {
    /// The nodes.
    pub nodes: Vec<Node>,
    /// The dependency edges.
    pub edges: Vec<Edge>,
}

/// Why a graph is invalid.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GraphError {
    /// Two nodes share an id.
    DuplicateNode(String),
    /// An edge references a node id that doesn't exist.
    DanglingEdge(String),
    /// The graph contains a cycle (not a DAG).
    Cycle,
}

impl std::fmt::Display for GraphError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            GraphError::DuplicateNode(id) => write!(f, "duplicate node id {id:?}"),
            GraphError::DanglingEdge(id) => write!(f, "edge references unknown node {id:?}"),
            GraphError::Cycle => write!(f, "workflow graph has a cycle (not a DAG)"),
        }
    }
}

impl std::error::Error for GraphError {}

impl WorkflowGraph {
    /// Validate structural integrity: unique node ids, every edge endpoint a
    /// real node, and the whole thing acyclic (a DAG).
    pub fn validate(&self) -> Result<(), GraphError> {
        let mut ids: HashSet<&str> = HashSet::new();
        for n in &self.nodes {
            if !ids.insert(n.id.as_str()) {
                return Err(GraphError::DuplicateNode(n.id.clone()));
            }
        }
        for e in &self.edges {
            if !ids.contains(e.from.as_str()) {
                return Err(GraphError::DanglingEdge(e.from.clone()));
            }
            if !ids.contains(e.to.as_str()) {
                return Err(GraphError::DanglingEdge(e.to.clone()));
            }
        }
        // Acyclicity is proven by a successful topological sort.
        self.topological_order().map(|_| ())
    }

    /// A topological execution order (Kahn's algorithm). Nodes with no
    /// unmet dependencies come first. Returns [`GraphError::Cycle`] if the
    /// graph isn't a DAG, or [`GraphError::DanglingEdge`] for an edge to an
    /// unknown node.
    pub fn topological_order(&self) -> Result<Vec<String>, GraphError> {
        let node_ids: HashSet<&str> = self.nodes.iter().map(|n| n.id.as_str()).collect();
        let mut indegree: HashMap<&str, usize> =
            self.nodes.iter().map(|n| (n.id.as_str(), 0usize)).collect();
        let mut succ: HashMap<&str, Vec<&str>> = HashMap::new();
        for e in &self.edges {
            if !node_ids.contains(e.from.as_str()) {
                return Err(GraphError::DanglingEdge(e.from.clone()));
            }
            if !node_ids.contains(e.to.as_str()) {
                return Err(GraphError::DanglingEdge(e.to.clone()));
            }
            *indegree.get_mut(e.to.as_str()).unwrap() += 1;
            succ.entry(e.from.as_str()).or_default().push(e.to.as_str());
        }
        // Seed with in-degree-0 nodes, in declaration order for determinism.
        let mut queue: VecDeque<&str> = self
            .nodes
            .iter()
            .map(|n| n.id.as_str())
            .filter(|id| indegree[id] == 0)
            .collect();
        let mut order: Vec<String> = Vec::with_capacity(self.nodes.len());
        while let Some(id) = queue.pop_front() {
            order.push(id.to_string());
            if let Some(succs) = succ.get(id) {
                for &s in succs {
                    let d = indegree.get_mut(s).unwrap();
                    *d -= 1;
                    if *d == 0 {
                        queue.push_back(s);
                    }
                }
            }
        }
        if order.len() != self.nodes.len() {
            return Err(GraphError::Cycle);
        }
        Ok(order)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn node(id: &str, t: NodeType) -> Node {
        Node {
            id: id.into(),
            node_type: t,
        }
    }
    fn edge(from: &str, to: &str) -> Edge {
        Edge {
            from: from.into(),
            to: to.into(),
        }
    }

    /// The E0552 example: read → draft → verify → apply → retest, gated.
    fn sample() -> WorkflowGraph {
        WorkflowGraph {
            nodes: vec![
                node("read", NodeType::MemoryRead),
                node("draft", NodeType::ModelCall),
                node("policy", NodeType::PolicyGate),
                node("apply", NodeType::ToolCall),
                node("retest", NodeType::TestRun),
                node("eval", NodeType::Eval),
                node("commit", NodeType::Commit),
            ],
            edges: vec![
                edge("read", "draft"),
                edge("draft", "policy"),
                edge("policy", "apply"),
                edge("apply", "retest"),
                edge("retest", "eval"),
                edge("eval", "commit"),
            ],
        }
    }

    #[test]
    fn valid_dag_topo_sorts_in_dependency_order() {
        let g = sample();
        g.validate().unwrap();
        let order = g.topological_order().unwrap();
        // read before draft before policy ... before commit.
        let pos = |id: &str| order.iter().position(|x| x == id).unwrap();
        assert!(pos("read") < pos("draft"));
        assert!(pos("policy") < pos("apply"));
        assert!(pos("eval") < pos("commit"));
        assert_eq!(order.len(), 7);
    }

    #[test]
    fn cycle_is_detected() {
        let mut g = sample();
        g.edges.push(edge("commit", "read")); // back-edge → cycle
        assert_eq!(g.validate(), Err(GraphError::Cycle));
        assert_eq!(g.topological_order(), Err(GraphError::Cycle));
    }

    #[test]
    fn dangling_edge_is_rejected() {
        let mut g = sample();
        g.edges.push(edge("apply", "ghost"));
        assert_eq!(g.validate(), Err(GraphError::DanglingEdge("ghost".into())));
    }

    #[test]
    fn duplicate_node_is_rejected() {
        let mut g = sample();
        g.nodes.push(node("read", NodeType::ToolCall));
        assert_eq!(g.validate(), Err(GraphError::DuplicateNode("read".into())));
    }

    #[test]
    fn parallel_branches_both_appear() {
        // two independent branches that join at commit.
        let g = WorkflowGraph {
            nodes: vec![
                node("a", NodeType::ModelCall),
                node("b", NodeType::ToolCall),
                node("commit", NodeType::Commit),
            ],
            edges: vec![edge("a", "commit"), edge("b", "commit")],
        };
        let order = g.topological_order().unwrap();
        let pos = |id: &str| order.iter().position(|x| x == id).unwrap();
        assert!(pos("a") < pos("commit"));
        assert!(pos("b") < pos("commit"));
    }

    #[test]
    fn node_type_serializes_kebab() {
        assert_eq!(
            serde_json::to_string(&NodeType::HumanGate).unwrap(),
            "\"human-gate\""
        );
        assert_eq!(
            serde_json::to_string(&NodeType::MemoryRead).unwrap(),
            "\"memory-read\""
        );
    }
}
