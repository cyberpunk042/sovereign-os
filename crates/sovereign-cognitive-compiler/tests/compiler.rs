//! Integration tests for `sovereign-cognitive-compiler` — exercise the public
//! compile API from an external consumer's perspective.

use sovereign_cognitive_compiler::{
    CompileInputs, CompilerError, DOCTRINE_PIPELINE, DagNode, ReadyAxes, SCHEMA_VERSION,
    WorkflowDag, assert_doctrine_intact, validate_inputs,
};

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

#[test]
fn ok_inputs_validate_from_external_module() {
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
fn empty_hardware_telemetry_rejected() {
    let mut c = ok_inputs();
    c.hardware_telemetry = String::new();
    assert!(matches!(
        validate_inputs(&c).unwrap_err(),
        CompilerError::InputEmpty("hardware_telemetry")
    ));
}

#[test]
fn empty_risk_profile_rejected() {
    let mut c = ok_inputs();
    c.risk_profile = String::new();
    assert!(matches!(
        validate_inputs(&c).unwrap_err(),
        CompilerError::InputEmpty("risk_profile")
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

#[test]
fn empty_model_registry_rejected() {
    let mut c = ok_inputs();
    c.model_registry.clear();
    assert!(matches!(
        validate_inputs(&c).unwrap_err(),
        CompilerError::InputEmpty("model_registry")
    ));
}

#[test]
fn policies_may_be_empty() {
    let mut c = ok_inputs();
    c.policies.clear();
    validate_inputs(&c).unwrap();
}

// ---------------------------------------------------------------------------
// WorkflowDag from an external module
// ---------------------------------------------------------------------------

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
fn schema_version_checked() {
    let mut d = WorkflowDag::empty();
    d.schema_version = "0.0.0".into();
    d.add_node(node("a", &[])).unwrap();
    let err = d.validate().unwrap_err();
    assert!(matches!(err, CompilerError::SchemaMismatch { .. }));
}

#[test]
fn ready_nodes_returns_roots_initially() {
    let mut d = WorkflowDag::empty();
    d.add_node(node("a", &[])).unwrap();
    d.add_node(node("b", &[])).unwrap();
    d.add_node(node("c", &["a"])).unwrap();
    let completed = std::collections::HashSet::new();
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
fn ready_nodes_expands_after_completion() {
    let mut d = WorkflowDag::empty();
    d.add_node(node("a", &[])).unwrap();
    d.add_node(node("b", &["a"])).unwrap();
    let mut completed = std::collections::HashSet::new();
    completed.insert("a".to_string());
    let ready: Vec<String> = d
        .ready_nodes(&completed)
        .iter()
        .map(|n| n.id.clone())
        .collect();
    assert_eq!(ready, vec!["b".to_string()]);
}

// ---------------------------------------------------------------------------
// ReadyAxes
// ---------------------------------------------------------------------------

#[test]
fn all_ready_true_when_all_set() {
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
fn ready_axes_failing_names_correct() {
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
    assert_eq!(f.len(), 3);
    assert!(f.contains(&"capability_allowed"));
    assert!(f.contains(&"risk_ok"));
    assert!(f.contains(&"priority"));
}

// ---------------------------------------------------------------------------
// Doctrine
// ---------------------------------------------------------------------------

#[test]
fn doctrine_verbatim() {
    assert_doctrine_intact(DOCTRINE_PIPELINE).unwrap();
    assert!(matches!(
        assert_doctrine_intact("WRONG").unwrap_err(),
        CompilerError::DoctrineTampered
    ));
}

// ---------------------------------------------------------------------------
// Serde roundtrips
// ---------------------------------------------------------------------------

#[test]
fn compile_inputs_serde_roundtrip() {
    let original = ok_inputs();
    let j = serde_json::to_string(&original).unwrap();
    let back: CompileInputs = serde_json::from_str(&j).unwrap();
    assert_eq!(back.user_goal, original.user_goal);
    assert_eq!(back.available_tools, original.available_tools);
}

#[test]
fn dag_node_serde_roundtrip() {
    let n = node("alpha", &["beta", "gamma"]);
    let j = serde_json::to_string(&n).unwrap();
    let back: DagNode = serde_json::from_str(&j).unwrap();
    assert_eq!(n, back);
}

#[test]
fn workflow_dag_serde_roundtrip() {
    let mut d = WorkflowDag::empty();
    d.add_node(node("a", &[])).unwrap();
    d.add_node(node("b", &["a"])).unwrap();
    let j = serde_json::to_string(&d).unwrap();
    let back: WorkflowDag = serde_json::from_str(&j).unwrap();
    assert_eq!(d.nodes.len(), back.nodes.len());
    assert_eq!(d.schema_version, back.schema_version);
}

#[test]
fn ready_axes_serde_roundtrip() {
    let a = ReadyAxes {
        dependency_satisfied: false,
        capability_allowed: true,
        budget_ok: false,
        risk_ok: true,
        sandbox_available: false,
        model_available: true,
        cache_affinity: false,
        priority: true,
    };
    let j = serde_json::to_string(&a).unwrap();
    let back: ReadyAxes = serde_json::from_str(&j).unwrap();
    assert_eq!(a, back);
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

#[test]
fn schema_version_is_semver() {
    assert_eq!(SCHEMA_VERSION, "1.0.0");
}
