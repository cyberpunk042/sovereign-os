//! Integration tests for `sovereign-coat` — exercise the public deliberation API
//! from an external consumer's perspective.
//!
//! Every test uses deterministic stubs (no model), so the suite is fast and
//! replayable — the same inputs always yield the same trace.

use sovereign_coat::{
    AssociativeMemory, CoatConfig, CoatEngine, CoatError, CoatTrace, NoMemory, PathStep, Problem,
    Recall, SearchStrategy, ThoughtCategory, ThoughtContext, ThoughtSeed, ThoughtSource,
};

/// A deterministic thought source that cycles through categories and produces
/// predictable priors so tests can assert on structure without randomness.
struct Cyclic {
    k: usize,
}

impl Cyclic {
    fn new(k: usize) -> Self {
        Self { k }
    }
}

impl ThoughtSource for Cyclic {
    fn expand(
        &mut self,
        _problem: &Problem,
        path: &[PathStep],
        _associated: &[Recall],
        k: usize,
    ) -> Vec<ThoughtSeed> {
        (0..k.min(self.k))
            .map(|i| ThoughtSeed {
                category: ThoughtCategory::ALL[(path.len() + i) % ThoughtCategory::ALL.len()],
                text: format!("t{}d{}", i, path.len()),
                prior: 0.8 - 0.15 * i as f64,
            })
            .collect()
    }

    fn label(&self) -> &str {
        "cyclic"
    }
}

/// A memory that always returns the same fixed hit — for testing recall
/// modulation from an external module.
struct FixedRecall;

impl AssociativeMemory for FixedRecall {
    fn recall(&self, _ctx: &ThoughtContext, k: usize) -> Vec<Recall> {
        (0..k)
            .map(|i| Recall {
                id: 100 + i as u64,
                relevance: 0.9 - 0.1 * i as f64,
                note: format!("hit-{i}"),
            })
            .collect()
    }
}

fn problem() -> Problem {
    Problem::new("prove the theorem")
}

// ---------------------------------------------------------------------------
// Config presets produce valid, distinct traces
// ---------------------------------------------------------------------------

#[test]
fn cot_preset_trace_is_a_linear_chain() {
    let mut engine = CoatEngine::new(Cyclic::new(1), NoMemory, CoatConfig::cot());
    let trace = engine.deliberate(&problem()).unwrap();
    assert_eq!(trace.rung, "CoT");
    assert_eq!(trace.strategy, SearchStrategy::Uct);
    // every non-root node has at most one child → a single chain
    for node in &trace.tree {
        let children: Vec<_> = trace
            .tree
            .iter()
            .filter(|n| n.parent == Some(node.id))
            .collect();
        assert!(
            children.len() <= 1,
            "CoT node {} has {} children",
            node.id,
            children.len()
        );
    }
    assert!(!trace.best_path.is_empty());
    assert_eq!(trace.recalled_total, 0, "CoT has no recall");
}

#[test]
fn tot_preset_branches() {
    let mut engine = CoatEngine::new(Cyclic::new(3), NoMemory, CoatConfig::tot());
    let trace = engine.deliberate(&problem()).unwrap();
    assert_eq!(trace.rung, "ToT");
    assert_eq!(trace.strategy, SearchStrategy::Bfs);
    let root_children = trace.tree.iter().filter(|n| n.parent == Some(0)).count();
    assert!(
        root_children > 1,
        "ToT must branch; got {root_children} root children"
    );
}

#[test]
fn tot_dfs_preset_is_depth_first() {
    let mut engine = CoatEngine::new(Cyclic::new(3), NoMemory, CoatConfig::tot_dfs());
    let trace = engine.deliberate(&problem()).unwrap();
    assert_eq!(trace.rung, "ToT");
    assert_eq!(trace.strategy, SearchStrategy::Dfs);
}

#[test]
fn mcts_preset_runs_uct_and_backprop() {
    let mut engine = CoatEngine::new(Cyclic::new(3), NoMemory, CoatConfig::mcts());
    let trace = engine.deliberate(&problem()).unwrap();
    assert_eq!(trace.rung, "MCTS");
    assert_eq!(trace.strategy, SearchStrategy::Uct);
    // root visits must equal the full budget
    assert_eq!(trace.tree[0].visits, trace.iterations);
}

#[test]
fn cmcts_preset_constrains_categories() {
    let mut engine = CoatEngine::new(Cyclic::new(5), NoMemory, CoatConfig::cmcts());
    let trace = engine.deliberate(&problem()).unwrap();
    assert_eq!(trace.rung, "C-MCTS");
    for node in &trace.tree {
        if let Some(cat) = node.category {
            let allowed = ThoughtCategory::allowed_at(node.depth, CoatConfig::cmcts().max_depth);
            assert!(
                allowed.contains(&cat),
                "depth {} has out-of-phase category {:?}",
                node.depth,
                cat
            );
        }
    }
}

#[test]
fn coat_preset_recalls_memory() {
    let mut engine = CoatEngine::new(Cyclic::new(3), FixedRecall, CoatConfig::coat());
    let trace = engine.deliberate(&problem()).unwrap();
    assert_eq!(trace.rung, "CoAT");
    assert!(
        trace.recalled_total > 0,
        "CoAT must recall associative memory"
    );
}

// ---------------------------------------------------------------------------
// Input validation
// ---------------------------------------------------------------------------

#[test]
fn empty_problem_is_rejected() {
    let mut engine = CoatEngine::new(Cyclic::new(1), NoMemory, CoatConfig::cot());
    assert!(matches!(
        engine.deliberate(&Problem::new("   ")),
        Err(CoatError::EmptyProblem)
    ));
}

#[test]
fn zero_iterations_is_rejected() {
    let cfg = CoatConfig {
        iterations: 0,
        ..CoatConfig::cot()
    };
    let mut engine = CoatEngine::new(Cyclic::new(1), NoMemory, cfg);
    assert!(matches!(
        engine.deliberate(&problem()),
        Err(CoatError::InvalidConfig(_))
    ));
}

#[test]
fn zero_expand_k_is_rejected() {
    let cfg = CoatConfig {
        expand_k: 0,
        ..CoatConfig::cot()
    };
    let mut engine = CoatEngine::new(Cyclic::new(1), NoMemory, cfg);
    assert!(matches!(
        engine.deliberate(&problem()),
        Err(CoatError::InvalidConfig(_))
    ));
}

#[test]
fn zero_max_depth_is_rejected() {
    let cfg = CoatConfig {
        max_depth: 0,
        ..CoatConfig::cot()
    };
    let mut engine = CoatEngine::new(Cyclic::new(1), NoMemory, cfg);
    assert!(matches!(
        engine.deliberate(&problem()),
        Err(CoatError::InvalidConfig(_))
    ));
}

// ---------------------------------------------------------------------------
// Determinism and reproducibility
// ---------------------------------------------------------------------------

#[test]
fn repeated_runs_are_identical() {
    let run = || {
        CoatEngine::new(Cyclic::new(3), NoMemory, CoatConfig::mcts())
            .deliberate(&problem())
            .unwrap()
            .summary
    };
    assert_eq!(run(), run(), "same inputs → same trace");
}

#[test]
fn different_configs_produce_different_traces() {
    let a = CoatEngine::new(Cyclic::new(3), NoMemory, CoatConfig::cot())
        .deliberate(&problem())
        .unwrap();
    let b = CoatEngine::new(Cyclic::new(3), NoMemory, CoatConfig::tot())
        .deliberate(&problem())
        .unwrap();
    assert_ne!(a.summary, b.summary, "different presets must differ");
    assert_ne!(a.tree.len(), b.tree.len(), "tree sizes must differ");
}

// ---------------------------------------------------------------------------
// Trace structure invariants
// ---------------------------------------------------------------------------

#[test]
fn trace_root_has_no_parent() {
    let mut engine = CoatEngine::new(Cyclic::new(3), NoMemory, CoatConfig::mcts());
    let trace = engine.deliberate(&problem()).unwrap();
    assert_eq!(trace.tree[0].parent, None);
    assert_eq!(trace.tree[0].depth, 0);
}

#[test]
fn best_path_nodes_are_marked_on_best_path() {
    let mut engine = CoatEngine::new(Cyclic::new(3), NoMemory, CoatConfig::mcts());
    let trace = engine.deliberate(&problem()).unwrap();
    assert!(
        trace.tree.iter().any(|n| n.on_best_path),
        "at least one node must be on the best path"
    );
    for step in &trace.best_path {
        let node = trace.tree.iter().find(|n| n.depth == step.depth).unwrap();
        assert!(
            node.on_best_path,
            "best-path step at depth {} not marked",
            step.depth
        );
    }
}

#[test]
fn branches_committed_and_pruned_accounted() {
    let mut engine = CoatEngine::new(Cyclic::new(3), NoMemory, CoatConfig::coat());
    let trace = engine.deliberate(&problem()).unwrap();
    assert!(
        trace.branches_committed >= 1,
        "winning path must commit at least one branch"
    );
    // committed + pruned + root == nodes (approximately; exact depends on tree shape)
    let non_root = trace.tree.len().saturating_sub(1);
    assert!(
        trace.branches_committed + trace.branches_pruned <= non_root,
        "committed+pruned ({}) exceeded non-root nodes ({non_root})",
        trace.branches_committed + trace.branches_pruned
    );
}

// ---------------------------------------------------------------------------
// Serde roundtrips
// ---------------------------------------------------------------------------

#[test]
fn coat_trace_serde_roundtrip() {
    let mut engine = CoatEngine::new(Cyclic::new(3), FixedRecall, CoatConfig::coat());
    let trace = engine.deliberate(&problem()).unwrap();
    let json = serde_json::to_string(&trace).unwrap();
    let back: CoatTrace = serde_json::from_str(&json).unwrap();
    assert_eq!(back.summary, trace.summary);
    assert_eq!(back.rung, trace.rung);
    assert_eq!(back.iterations, trace.iterations);
    assert_eq!(back.best_path.len(), trace.best_path.len());
}

#[test]
fn config_serde_roundtrip() {
    let original = CoatConfig::coat();
    let json = serde_json::to_string(&original).unwrap();
    let back: CoatConfig = serde_json::from_str(&json).unwrap();
    assert_eq!(back.rung(), original.rung());
    assert_eq!(back.strategy, original.strategy);
    assert_eq!(back.iterations, original.iterations);
    assert_eq!(back.expand_k, original.expand_k);
}

#[test]
fn problem_serde_roundtrip() {
    let original = Problem {
        statement: "test".into(),
        topic: 42,
        entity: 7,
    };
    let json = serde_json::to_string(&original).unwrap();
    let back: Problem = serde_json::from_str(&json).unwrap();
    assert_eq!(back.statement, original.statement);
    assert_eq!(back.topic, original.topic);
    assert_eq!(back.entity, original.entity);
}

// ---------------------------------------------------------------------------
// ThoughtCategory helpers
// ---------------------------------------------------------------------------

#[test]
fn allowed_at_respects_depth_boundaries() {
    let max = 4;
    let early = ThoughtCategory::allowed_at(0, max);
    assert!(early.contains(&ThoughtCategory::Understand));
    assert!(early.contains(&ThoughtCategory::Plan));

    let mid = ThoughtCategory::allowed_at(2, max);
    assert!(mid.contains(&ThoughtCategory::Plan));
    assert!(mid.contains(&ThoughtCategory::Reflect));
    assert!(mid.contains(&ThoughtCategory::Code));

    let late = ThoughtCategory::allowed_at(3, max);
    assert!(late.contains(&ThoughtCategory::Reflect));
    assert!(late.contains(&ThoughtCategory::Summarize));
}

// ---------------------------------------------------------------------------
// NoMemory is a valid AssociativeMemory
// ---------------------------------------------------------------------------

#[test]
fn no_memory_recalls_nothing() {
    let ctx = ThoughtContext {
        topic: 1,
        entity: 2,
        text: "test".into(),
    };
    assert!(NoMemory.recall(&ctx, 5).is_empty());
    assert!(NoMemory.recall(&ctx, 0).is_empty());
}
