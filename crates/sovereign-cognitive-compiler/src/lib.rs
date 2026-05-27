//! `sovereign-cognitive-compiler` — M025 intent-to-DAG compiler.
//!
//! Per M025 + E0230-E0237 + M00410-M00416 + dump 7000-7378:
//!
//! **7-input contract** (M00410 dump 7039-7046):
//!   user_goal / policies / available_tools / model_registry /
//!   memory_state / hardware_telemetry / risk_profile
//!
//! **5-output contract** (M00411 dump 7048-7053):
//!   typed_workflow_dag / capability_plan / model_routing_plan /
//!   cache_plan / eval_verification_plan
//!
//! **DAG node schema** (M00412 dump 7061-7090) — 7 fields:
//!   id / type / depends_on / parallel / output (typed) / model_role / sandbox
//!
//! **8-axis ready-node scheduler** (M00416 dump 7174-7183):
//!   dependency_satisfied / capability_allowed / budget_ok / risk_ok /
//!   sandbox_available / model_available / cache_affinity / priority
//!
//! Doctrine surface verbatim per E0230 dump 7026-7030:
//!
//! > "AI intent → compiler → executable cognitive DAG → scheduler → experts/tools → observations → adaptive recompile"
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Compiler pipeline doctrine verbatim per E0230 dump 7026-7030.
pub const DOCTRINE_PIPELINE: &str = "AI intent → compiler → executable cognitive DAG → scheduler → experts/tools → observations → adaptive recompile";

/// 7-input compile context (M00410).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CompileInputs {
    /// Field 1 — user goal text.
    pub user_goal: String,
    /// Field 2 — active policies (M049/MS033 references).
    pub policies: Vec<String>,
    /// Field 3 — available tools (canonical names).
    pub available_tools: Vec<String>,
    /// Field 4 — model registry entries (e.g. "blackwell-oracle/claude-opus").
    pub model_registry: Vec<String>,
    /// Field 5 — memory state digest.
    pub memory_state: String,
    /// Field 6 — hardware telemetry digest.
    pub hardware_telemetry: String,
    /// Field 7 — risk profile name.
    pub risk_profile: String,
}

/// 5-output compile result (M00411).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CompileOutputs {
    /// Output 1 — typed workflow DAG.
    pub workflow_dag: WorkflowDag,
    /// Output 2 — capability plan (capability_word ids, tool bindings).
    pub capability_plan: Vec<String>,
    /// Output 3 — model routing plan (per-node model assignments).
    pub model_routing_plan: BTreeMap<String, String>,
    /// Output 4 — cache plan (KV / prompt-cache reuse hints).
    pub cache_plan: Vec<String>,
    /// Output 5 — eval verification plan.
    pub eval_verification_plan: Vec<String>,
}

/// 7-field DAG node schema per M00412 dump 7061-7090.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DagNode {
    /// Field 1 — node id (unique within DAG).
    pub id: String,
    /// Field 2 — node type (tool / model / decision / branch).
    pub node_type: String,
    /// Field 3 — depends_on (parent node ids).
    pub depends_on: Vec<String>,
    /// Field 4 — parallel-eligible flag.
    pub parallel: bool,
    /// Field 5 — typed output schema name.
    pub output: String,
    /// Field 6 — model role (Conductor / Logic / Oracle).
    pub model_role: String,
    /// Field 7 — sandbox tier (A/B/C/D).
    pub sandbox: String,
}

/// Workflow DAG = nodes + edges (encoded as depends_on per node).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkflowDag {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// Nodes by id.
    pub nodes: BTreeMap<String, DagNode>,
}

/// 8-axis ready-node scheduler per M00416.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReadyAxes {
    /// Axis 1 — all dependencies satisfied.
    pub dependency_satisfied: bool,
    /// Axis 2 — capability_word permits the action.
    pub capability_allowed: bool,
    /// Axis 3 — within budget.
    pub budget_ok: bool,
    /// Axis 4 — risk within profile envelope.
    pub risk_ok: bool,
    /// Axis 5 — required sandbox tier available.
    pub sandbox_available: bool,
    /// Axis 6 — required model is warm.
    pub model_available: bool,
    /// Axis 7 — KV / prompt cache hit anticipated.
    pub cache_affinity: bool,
    /// Axis 8 — priority gate passed.
    pub priority: bool,
}

impl ReadyAxes {
    /// True iff every axis is satisfied (node is ready to dispatch).
    pub fn all_ready(&self) -> bool {
        self.dependency_satisfied
            && self.capability_allowed
            && self.budget_ok
            && self.risk_ok
            && self.sandbox_available
            && self.model_available
            && self.cache_affinity
            && self.priority
    }
    /// Names of failing axes (operator-readable).
    pub fn failing(&self) -> Vec<&'static str> {
        let mut v = vec![];
        if !self.dependency_satisfied {
            v.push("dependency_satisfied");
        }
        if !self.capability_allowed {
            v.push("capability_allowed");
        }
        if !self.budget_ok {
            v.push("budget_ok");
        }
        if !self.risk_ok {
            v.push("risk_ok");
        }
        if !self.sandbox_available {
            v.push("sandbox_available");
        }
        if !self.model_available {
            v.push("model_available");
        }
        if !self.cache_affinity {
            v.push("cache_affinity");
        }
        if !self.priority {
            v.push("priority");
        }
        v
    }
}

/// Errors.
#[derive(Debug, Error)]
pub enum CompilerError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Inputs missing required field.
    #[error("required compile input empty: {0}")]
    InputEmpty(&'static str),
    /// DAG has a cycle.
    #[error("DAG has cycle involving node {0}")]
    Cycle(String),
    /// DAG references unknown parent.
    #[error("DAG node {child} depends on unknown parent {parent}")]
    UnknownParent {
        /// Child node.
        child: String,
        /// Missing parent.
        parent: String,
    },
    /// Doctrine surface tampered.
    #[error("doctrine tampered: expected verbatim")]
    DoctrineTampered,
}

impl WorkflowDag {
    /// Construct empty DAG.
    pub fn empty() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            nodes: BTreeMap::new(),
        }
    }

    /// Add a node. Refuses duplicates.
    pub fn add_node(&mut self, node: DagNode) -> Result<(), CompilerError> {
        if self.nodes.contains_key(&node.id) {
            return Err(CompilerError::Cycle(format!("duplicate id {}", node.id)));
        }
        self.nodes.insert(node.id.clone(), node);
        Ok(())
    }

    /// Validate the DAG structure — cycle-free, parents present.
    pub fn validate(&self) -> Result<(), CompilerError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CompilerError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        // Every depends_on must exist.
        for (id, node) in &self.nodes {
            for parent in &node.depends_on {
                if !self.nodes.contains_key(parent) {
                    return Err(CompilerError::UnknownParent {
                        child: id.clone(),
                        parent: parent.clone(),
                    });
                }
            }
        }
        // Cycle detection via DFS with white/gray/black coloring.
        use std::collections::HashMap;
        #[derive(PartialEq, Eq, Clone, Copy)]
        enum Color {
            White,
            Gray,
            Black,
        }
        let mut color: HashMap<&String, Color> =
            self.nodes.keys().map(|k| (k, Color::White)).collect();
        fn dfs<'a>(
            id: &'a String,
            nodes: &'a BTreeMap<String, DagNode>,
            color: &mut HashMap<&'a String, Color>,
        ) -> Result<(), CompilerError> {
            color.insert(id, Color::Gray);
            if let Some(node) = nodes.get(id) {
                for parent in &node.depends_on {
                    if let Some(parent_key) = nodes.keys().find(|k| *k == parent) {
                        match color.get(parent_key) {
                            Some(Color::Gray) => return Err(CompilerError::Cycle(id.clone())),
                            Some(Color::White) => dfs(parent_key, nodes, color)?,
                            _ => {}
                        }
                    }
                }
            }
            color.insert(id, Color::Black);
            Ok(())
        }
        // Collect keys first to avoid borrow conflict
        let keys: Vec<&String> = self.nodes.keys().collect();
        for k in keys {
            if color.get(k) == Some(&Color::White) {
                dfs(k, &self.nodes, &mut color)?;
            }
        }
        Ok(())
    }

    /// Return all nodes whose dependencies are all satisfied
    /// given a set of completed-node ids.
    pub fn ready_nodes(&self, completed: &std::collections::HashSet<String>) -> Vec<&DagNode> {
        self.nodes
            .values()
            .filter(|n| !completed.contains(&n.id))
            .filter(|n| n.depends_on.iter().all(|p| completed.contains(p)))
            .collect()
    }
}

/// Validate the 7 input fields are non-empty (except policies which may be empty list).
pub fn validate_inputs(c: &CompileInputs) -> Result<(), CompilerError> {
    if c.user_goal.is_empty() {
        return Err(CompilerError::InputEmpty("user_goal"));
    }
    if c.memory_state.is_empty() {
        return Err(CompilerError::InputEmpty("memory_state"));
    }
    if c.hardware_telemetry.is_empty() {
        return Err(CompilerError::InputEmpty("hardware_telemetry"));
    }
    if c.risk_profile.is_empty() {
        return Err(CompilerError::InputEmpty("risk_profile"));
    }
    if c.available_tools.is_empty() {
        return Err(CompilerError::InputEmpty("available_tools"));
    }
    if c.model_registry.is_empty() {
        return Err(CompilerError::InputEmpty("model_registry"));
    }
    Ok(())
}

/// Validate the doctrine constant is intact.
pub fn assert_doctrine_intact(observed: &str) -> Result<(), CompilerError> {
    if observed != DOCTRINE_PIPELINE {
        return Err(CompilerError::DoctrineTampered);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    fn ok_inputs() -> CompileInputs {
        CompileInputs {
            user_goal: "Implement feature X".into(),
            policies: vec!["P-001".into()],
            available_tools: vec!["rg".into(), "cargo".into()],
            model_registry: vec!["blackwell-oracle/claude-opus".into()],
            memory_state: "memos.v1183".into(),
            hardware_telemetry: "psi: low".into(),
            risk_profile: "careful".into(),
        }
    }
    fn node(id: &str, deps: &[&str]) -> DagNode {
        DagNode {
            id: id.into(),
            node_type: "tool".into(),
            depends_on: deps.iter().map(|s| s.to_string()).collect(),
            parallel: false,
            output: "TypedOutput".into(),
            model_role: "logic".into(),
            sandbox: "B".into(),
        }
    }

    // --- 7-input contract ---

    #[test]
    fn ok_inputs_validate() {
        validate_inputs(&ok_inputs()).unwrap();
    }

    #[test]
    fn empty_user_goal_rejected() {
        let mut c = ok_inputs();
        c.user_goal = String::new();
        assert!(matches!(
            validate_inputs(&c).unwrap_err(),
            CompilerError::InputEmpty("user_goal")
        ));
    }

    #[test]
    fn empty_memory_state_rejected() {
        let mut c = ok_inputs();
        c.memory_state = String::new();
        assert!(matches!(
            validate_inputs(&c).unwrap_err(),
            CompilerError::InputEmpty("memory_state")
        ));
    }

    #[test]
    fn empty_available_tools_rejected() {
        let mut c = ok_inputs();
        c.available_tools.clear();
        assert!(matches!(
            validate_inputs(&c).unwrap_err(),
            CompilerError::InputEmpty("available_tools")
        ));
    }

    // --- WorkflowDag ---

    #[test]
    fn empty_dag_validates() {
        WorkflowDag::empty().validate().unwrap();
    }

    #[test]
    fn linear_dag_validates() {
        let mut d = WorkflowDag::empty();
        d.add_node(node("a", &[])).unwrap();
        d.add_node(node("b", &["a"])).unwrap();
        d.add_node(node("c", &["b"])).unwrap();
        d.validate().unwrap();
    }

    #[test]
    fn diamond_dag_validates() {
        let mut d = WorkflowDag::empty();
        d.add_node(node("a", &[])).unwrap();
        d.add_node(node("b", &["a"])).unwrap();
        d.add_node(node("c", &["a"])).unwrap();
        d.add_node(node("d", &["b", "c"])).unwrap();
        d.validate().unwrap();
    }

    #[test]
    fn cycle_detected_two_nodes() {
        let mut d = WorkflowDag::empty();
        d.add_node(node("a", &["b"])).unwrap();
        d.add_node(node("b", &["a"])).unwrap();
        let err = d.validate().unwrap_err();
        assert!(matches!(err, CompilerError::Cycle(_)));
    }

    #[test]
    fn cycle_detected_three_nodes() {
        let mut d = WorkflowDag::empty();
        d.add_node(node("a", &["c"])).unwrap();
        d.add_node(node("b", &["a"])).unwrap();
        d.add_node(node("c", &["b"])).unwrap();
        assert!(matches!(d.validate().unwrap_err(), CompilerError::Cycle(_)));
    }

    #[test]
    fn unknown_parent_caught() {
        let mut d = WorkflowDag::empty();
        d.add_node(node("a", &["missing"])).unwrap();
        match d.validate().unwrap_err() {
            CompilerError::UnknownParent { child, parent } => {
                assert_eq!(child, "a");
                assert_eq!(parent, "missing");
            }
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn duplicate_id_rejected() {
        let mut d = WorkflowDag::empty();
        d.add_node(node("a", &[])).unwrap();
        assert!(d.add_node(node("a", &[])).is_err());
    }

    #[test]
    fn ready_nodes_return_roots_when_nothing_completed() {
        let mut d = WorkflowDag::empty();
        d.add_node(node("a", &[])).unwrap();
        d.add_node(node("b", &[])).unwrap();
        d.add_node(node("c", &["a"])).unwrap();
        let completed = HashSet::new();
        let ready: Vec<String> = d
            .ready_nodes(&completed)
            .iter()
            .map(|n| n.id.clone())
            .collect();
        assert!(ready.contains(&"a".to_string()));
        assert!(ready.contains(&"b".to_string()));
        assert!(!ready.contains(&"c".to_string()));
    }

    #[test]
    fn ready_nodes_expand_after_completion() {
        let mut d = WorkflowDag::empty();
        d.add_node(node("a", &[])).unwrap();
        d.add_node(node("b", &["a"])).unwrap();
        let mut completed = HashSet::new();
        completed.insert("a".to_string());
        let ready: Vec<String> = d
            .ready_nodes(&completed)
            .iter()
            .map(|n| n.id.clone())
            .collect();
        assert_eq!(ready, vec!["b".to_string()]);
    }

    // --- 8-axis ReadyAxes ---

    #[test]
    fn all_ready_returns_true_when_all_set() {
        let a = ReadyAxes {
            dependency_satisfied: true,
            capability_allowed: true,
            budget_ok: true,
            risk_ok: true,
            sandbox_available: true,
            model_available: true,
            cache_affinity: true,
            priority: true,
        };
        assert!(a.all_ready());
        assert!(a.failing().is_empty());
    }

    #[test]
    fn ready_axes_failing_names_listed() {
        let a = ReadyAxes {
            dependency_satisfied: true,
            capability_allowed: false,
            budget_ok: true,
            risk_ok: false,
            sandbox_available: true,
            model_available: true,
            cache_affinity: true,
            priority: false,
        };
        assert!(!a.all_ready());
        let f = a.failing();
        assert!(f.contains(&"capability_allowed"));
        assert!(f.contains(&"risk_ok"));
        assert!(f.contains(&"priority"));
    }

    // --- Doctrine + Serde ---

    #[test]
    fn doctrine_verbatim() {
        assert_doctrine_intact(DOCTRINE_PIPELINE).unwrap();
        assert!(matches!(
            assert_doctrine_intact("WRONG").unwrap_err(),
            CompilerError::DoctrineTampered
        ));
    }

    #[test]
    fn dag_node_serde_roundtrip() {
        let n = node("alpha", &["beta", "gamma"]);
        let j = serde_json::to_string(&n).unwrap();
        let back: DagNode = serde_json::from_str(&j).unwrap();
        assert_eq!(n, back);
    }
}
