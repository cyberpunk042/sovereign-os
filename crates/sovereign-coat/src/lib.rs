//! `sovereign-coat` — Chain-of-Associated-Thoughts: deliberate, search-based
//! reasoning as one parameterized engine.
//!
//! The operator's standing directive
//! (`docs/standing-directives/2026-07-12-deliberate-reasoning.md`) codifies the
//! progression **CoT → ToT → MCTS → C-MCTS → CoAT** and the sovereign thesis:
//! the box already implements the ladder as first-class primitives. This crate
//! is the top rung — and it demonstrates the thesis by being a *single* MCTS
//! engine that the earlier rungs fall out of as presets:
//!
//! | rung | what it adds | preset |
//! |------|--------------|--------|
//! | **CoT** | one linear chain of thought | [`CoatConfig::cot`] (`expand_k = 1`) |
//! | **ToT** | a tree: many thoughts, evaluate, backtrack | [`CoatConfig::tot`] (`expand_k > 1`, greedy) |
//! | **MCTS** | UCT selection + expansion + simulation + backprop | [`CoatConfig::mcts`] (`exploration_c > 0`) |
//! | **C-MCTS** | a *constrained* action space | [`ThoughtCategory`] — the engine only ever expands into these five categories |
//! | **CoAT** ⭐ | **associative memory recalled at every expansion, modulating value** | [`CoatConfig::coat`] (`recall_weight > 0`) — the default |
//!
//! ## The four MCTS phases (over the M007 [`sovereign_branch_tree::BranchTree`])
//!
//! 1. **Selection** — walk from the root by UCT (exploit mean value + explore
//!    low-visit nodes) to an expandable node.
//! 2. **Expansion** — [`sovereign_branch_tree::BranchTree::fork`] one child from
//!    an untried thought seed; **and recall associative memory for it (CoAT)**.
//! 3. **Simulation** — estimate the node's reward. Per the value-plane PRM
//!    doctrine ("PRM proposes value"), the thought's prior IS that estimate,
//!    *modulated by what the recall surfaced* — a memory-supported thought is
//!    worth more. No random rollout: the reasoning value estimate is the playout.
//! 4. **Backpropagation** — propagate the reward up the `lineage()`, bumping
//!    visits + accumulated value on every ancestor.
//!
//! After the budget is spent, the winning root→leaf path (by robust/most-visited
//! child) is the reasoning trace; its branches are committed and the rest pruned,
//! exactly as [`sovereign_branch_tree`] intends (fork-and-prune).
//!
//! ## Why it is generic (and therefore testable without a model)
//!
//! The two model-gated inputs are traits: [`ThoughtSource`] (generate candidate
//! thoughts) and [`AssociativeMemory`] (recall related knowledge). In production
//! the LLM satisfies the first and the Memory-OS `retrieve()` the second; in
//! tests deterministic stubs satisfy both — so the whole search **harness** is
//! exercised and proven correct while the **thought content** remains model-gated.
//! The engine itself uses no randomness: same inputs → same trace (replayability,
//! the box's doctrine).

use serde::{Deserialize, Serialize};
use sovereign_branch_tree::{BranchTree, ROOT};

/// Errors the engine can return.
#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum CoatError {
    /// The problem statement was empty — nothing to deliberate about.
    #[error("empty problem statement")]
    EmptyProblem,
}

/// The **constrained action space** (this is the C in C-MCTS): the engine only
/// ever expands a node into one of these five categories, never an arbitrary
/// free-form action. Constraining the branching keeps the search tractable and
/// less prone to the hallucinated, unstructured steps unbounded MCTS invites.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ThoughtCategory {
    /// Restate / decompose the problem — build shared understanding.
    Understand,
    /// Propose an approach or sub-goal.
    Plan,
    /// Critique the path so far; check for a dead end to backtrack from.
    Reflect,
    /// Produce concrete work product (an implementation step).
    Code,
    /// Consolidate the path into a conclusion.
    Summarize,
}

impl ThoughtCategory {
    /// The full constrained action space, in canonical order.
    pub const ALL: [ThoughtCategory; 5] = [
        ThoughtCategory::Understand,
        ThoughtCategory::Plan,
        ThoughtCategory::Reflect,
        ThoughtCategory::Code,
        ThoughtCategory::Summarize,
    ];
}

/// The problem to deliberate about. `topic`/`entity` are the sketch bitsets the
/// associative memory queries on (they map onto the Memory-OS `Query`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Problem {
    /// The natural-language statement of the problem.
    pub statement: String,
    /// Topic sketch bitset for associative recall.
    #[serde(default)]
    pub topic: u64,
    /// Entity sketch bitset for associative recall.
    #[serde(default)]
    pub entity: u64,
}

impl Problem {
    /// A problem with no sketch bits (recall keys on the path text only).
    pub fn new(statement: impl Into<String>) -> Self {
        Problem { statement: statement.into(), topic: 0, entity: 0 }
    }
}

/// One step on the reasoning path so far, handed to [`ThoughtSource::expand`] so
/// it can propose context-aware continuations.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PathStep {
    /// The category of this step's thought.
    pub category: ThoughtCategory,
    /// The thought text.
    pub text: String,
}

/// A candidate next thought proposed by a [`ThoughtSource`].
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThoughtSeed {
    /// Which constrained category this thought belongs to.
    pub category: ThoughtCategory,
    /// The thought text.
    pub text: String,
    /// The PRM's proposed base value in `[0, 1]` — "PRM proposes value".
    pub prior: f64,
}

/// One item recalled from associative memory (maps onto a Memory-OS `Hit`). This
/// is CoAT's mechanism: knowledge pulled in *while deliberating*.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Recall {
    /// The recalled item's id (key into the cold store).
    pub id: u64,
    /// Relevance in `[0, 1]` (higher = more supportive of the thought).
    pub relevance: f64,
    /// A short human-readable note about what was recalled.
    #[serde(default)]
    pub note: String,
}

/// The query context handed to [`AssociativeMemory::recall`] at an expansion.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThoughtContext {
    /// Topic sketch bitset (from the [`Problem`]).
    pub topic: u64,
    /// Entity sketch bitset (from the [`Problem`]).
    pub entity: u64,
    /// The accumulated path text including the candidate thought — a real
    /// embedding recall would key on this.
    pub text: String,
}

/// Produces candidate next thoughts. **Model-gated in production** (the LLM);
/// a deterministic stub in tests.
pub trait ThoughtSource {
    /// Propose up to `k` candidate continuations of `path` for `problem`. Fewer
    /// than `k` (or zero) is allowed — the engine stops expanding a node when it
    /// runs dry.
    fn expand(&mut self, problem: &Problem, path: &[PathStep], k: usize) -> Vec<ThoughtSeed>;
}

/// CoAT's associative-memory mechanism: recall knowledge related to a thought
/// while deliberating. In production this is the Memory-OS `retrieve()`; a
/// deterministic stub in tests.
pub trait AssociativeMemory {
    /// Recall up to `k` items relevant to `ctx`. An empty result is fine (the
    /// thought is then valued on its prior alone).
    fn recall(&self, ctx: &ThoughtContext, k: usize) -> Vec<Recall>;
}

/// A memory that recalls nothing — turns CoAT back into plain MCTS/ToT.
#[derive(Debug, Default, Clone, Copy)]
pub struct NoMemory;

impl AssociativeMemory for NoMemory {
    fn recall(&self, _ctx: &ThoughtContext, _k: usize) -> Vec<Recall> {
        Vec::new()
    }
}

/// Engine knobs. The presets show the whole ladder is one engine.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct CoatConfig {
    /// Search budget: how many select→expand→simulate→backprop iterations.
    pub iterations: u32,
    /// UCT exploration constant. `0.0` = pure exploitation (greedy best-first);
    /// `sqrt(2)` is the textbook default.
    pub exploration_c: f64,
    /// Branching factor: thoughts proposed per node. `1` = a linear chain (CoT).
    pub expand_k: usize,
    /// Associative items recalled per expansion (`0` disables recall).
    pub recall_k: usize,
    /// Maximum reasoning depth (root is depth 0).
    pub max_depth: u32,
    /// How strongly recall modulates a thought's value. `0.0` = ignore memory
    /// (MCTS/ToT); `> 0.0` = CoAT — memory-supported thoughts are worth more.
    pub recall_weight: f64,
}

impl Default for CoatConfig {
    fn default() -> Self {
        CoatConfig::coat()
    }
}

impl CoatConfig {
    /// **CoT** — a single linear chain of thought (`expand_k = 1`, no recall,
    /// pure exploitation). One thought per step, drilled to `max_depth`.
    pub fn cot() -> Self {
        CoatConfig {
            iterations: 4,
            exploration_c: 0.0,
            expand_k: 1,
            recall_k: 0,
            max_depth: 4,
            recall_weight: 0.0,
        }
    }

    /// **ToT** — a tree of thoughts explored greedily (best-first, no UCT
    /// exploration, no recall). Multiple candidates per node, backtrack-capable.
    pub fn tot() -> Self {
        CoatConfig {
            iterations: 24,
            exploration_c: 0.0,
            expand_k: 3,
            recall_k: 0,
            max_depth: 4,
            recall_weight: 0.0,
        }
    }

    /// **MCTS** — the tree searched with UCT (explore/exploit balance) and
    /// backpropagation, still without associative memory.
    pub fn mcts() -> Self {
        CoatConfig {
            iterations: 64,
            exploration_c: std::f64::consts::SQRT_2,
            expand_k: 3,
            recall_k: 0,
            max_depth: 4,
            recall_weight: 0.0,
        }
    }

    /// **CoAT** ⭐ — MCTS with associative memory recalled at every expansion,
    /// modulating each thought's value. The sovereign-native default.
    pub fn coat() -> Self {
        CoatConfig {
            iterations: 64,
            exploration_c: std::f64::consts::SQRT_2,
            expand_k: 3,
            recall_k: 3,
            max_depth: 4,
            recall_weight: 0.35,
        }
    }

    /// The rung name this config corresponds to (for the trace / observatory).
    pub fn rung(&self) -> &'static str {
        if self.recall_weight > 0.0 && self.recall_k > 0 {
            "CoAT"
        } else if self.exploration_c > 0.0 {
            "MCTS"
        } else if self.expand_k > 1 {
            "ToT"
        } else {
            "CoT"
        }
    }
}

/// An internal search node. Wraps a branch id from the [`BranchTree`].
#[derive(Debug)]
struct Node {
    branch_id: u64,
    parent: Option<usize>,
    children: Vec<usize>,
    depth: u32,
    /// `None` for the root (the problem itself).
    thought: Option<Thought>,
    /// Candidate seeds not yet expanded into children (lazily generated).
    untried: Vec<ThoughtSeed>,
    /// Whether [`ThoughtSource::expand`] has been consulted for this node yet.
    seeds_generated: bool,
    visits: u32,
    value_sum: f64,
}

/// A committed thought living on a node: the seed plus the memory recalled for it.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct Thought {
    category: ThoughtCategory,
    text: String,
    prior: f64,
    recall: Vec<Recall>,
}

/// The deliberation engine. Generic over the (model-gated) thought source and
/// associative memory so the search harness is deterministic + testable.
#[derive(Debug)]
pub struct CoatEngine<T: ThoughtSource, M: AssociativeMemory> {
    thoughts: T,
    memory: M,
    config: CoatConfig,
}

impl<T: ThoughtSource, M: AssociativeMemory> CoatEngine<T, M> {
    /// Build an engine from a thought source, an associative memory, and a config.
    pub fn new(thoughts: T, memory: M, config: CoatConfig) -> Self {
        CoatEngine { thoughts, memory, config }
    }

    /// Run the full deliberation and return the reasoning trace.
    pub fn deliberate(&mut self, problem: &Problem) -> Result<CoatTrace, CoatError> {
        if problem.statement.trim().is_empty() {
            return Err(CoatError::EmptyProblem);
        }
        let mut tree = Tree::new();
        for _ in 0..self.config.iterations {
            // 1. SELECTION — UCT walk to an expandable node.
            let selected = self.select(&mut tree);
            // 2. EXPANSION — fork one child + recall associative memory (CoAT).
            let node = self.expand(&mut tree, problem, selected).unwrap_or(selected);
            // 3. SIMULATION — value estimate (prior modulated by recall).
            let reward = self.simulate(&tree, node);
            // 4. BACKPROPAGATION — up the lineage.
            tree.backprop(node, reward);
        }
        Ok(tree.into_trace(problem, &self.config))
    }

    /// UCT tree policy: descend from the root, picking the best-UCT child, until
    /// reaching an expandable node (seeds not yet generated, or generated with
    /// untried seeds left) or a genuine leaf. Seed generation itself is deferred
    /// to [`Self::expand`], which holds the [`Problem`].
    fn select(&mut self, tree: &mut Tree) -> usize {
        let mut cur = tree.root;
        loop {
            let n = &tree.nodes[cur];
            if n.depth >= self.config.max_depth {
                return cur;
            }
            // expandable: not yet consulted the source, or seeds still untried.
            if !n.seeds_generated || !n.untried.is_empty() {
                return cur;
            }
            if n.children.is_empty() {
                return cur; // fully expanded but sterile (source ran dry)
            }
            cur = tree.best_uct_child(cur, self.config.exploration_c);
        }
    }

    /// Expansion: pop one untried seed, recall associative memory for it, and
    /// fork a child branch. Returns the new child (or `None` if nothing to expand).
    fn expand(&mut self, tree: &mut Tree, problem: &Problem, parent: usize) -> Option<usize> {
        if tree.nodes[parent].depth >= self.config.max_depth {
            return None;
        }
        // Lazily consult the thought source the first time we expand this node.
        if !tree.nodes[parent].seeds_generated {
            let path = tree.path_steps(parent);
            let mut seeds = self.thoughts.expand(problem, &path, self.config.expand_k);
            // pop() yields last-first; reverse so children keep source order.
            seeds.reverse();
            tree.nodes[parent].untried = seeds;
            tree.nodes[parent].seeds_generated = true;
        }
        let seed = tree.nodes[parent].untried.pop()?;

        // CoAT: recall associative memory for this candidate thought.
        let recall = if self.config.recall_k > 0 {
            let ctx = ThoughtContext {
                topic: problem.topic,
                entity: problem.entity,
                text: tree.path_text(parent, &seed.text),
            };
            self.memory.recall(&ctx, self.config.recall_k)
        } else {
            Vec::new()
        };

        let branch_id = tree.branches.fork(tree.nodes[parent].branch_id).ok()?;
        let thought = Thought {
            category: seed.category,
            text: seed.text,
            prior: seed.prior,
            recall,
        };
        Some(tree.push_child(parent, branch_id, thought))
    }

    /// Simulation: the reasoning-value estimate. The thought's prior IS the PRM's
    /// proposed value; recall modulates it upward (CoAT — memory support raises
    /// worth). The root scores a neutral `0.5`.
    fn simulate(&self, tree: &Tree, node: usize) -> f64 {
        match &tree.nodes[node].thought {
            None => 0.5,
            Some(t) => {
                let base = t.prior.clamp(0.0, 1.0);
                if t.recall.is_empty() || self.config.recall_weight == 0.0 {
                    base
                } else {
                    let mean = t.recall.iter().map(|r| r.relevance).sum::<f64>()
                        / t.recall.len() as f64;
                    (base + self.config.recall_weight * mean).clamp(0.0, 1.0)
                }
            }
        }
    }
}

/// The search tree: the node arena plus the real M007 [`BranchTree`] it drives.
#[derive(Debug)]
struct Tree {
    nodes: Vec<Node>,
    branches: BranchTree,
    root: usize,
}

impl Tree {
    fn new() -> Self {
        let branches = BranchTree::new();
        let root = Node {
            branch_id: ROOT,
            parent: None,
            children: Vec::new(),
            depth: 0,
            thought: None,
            untried: Vec::new(),
            seeds_generated: false,
            visits: 0,
            value_sum: 0.0,
        };
        Tree { nodes: vec![root], branches, root: 0 }
    }

    fn push_child(&mut self, parent: usize, branch_id: u64, thought: Thought) -> usize {
        let depth = self.nodes[parent].depth + 1;
        let idx = self.nodes.len();
        self.nodes.push(Node {
            branch_id,
            parent: Some(parent),
            children: Vec::new(),
            depth,
            thought: Some(thought),
            untried: Vec::new(),
            seeds_generated: false,
            visits: 0,
            value_sum: 0.0,
        });
        self.nodes[parent].children.push(idx);
        idx
    }

    /// The root→node path as [`PathStep`]s (excludes the root, which has no thought).
    fn path_steps(&self, node: usize) -> Vec<PathStep> {
        let mut chain = Vec::new();
        let mut cur = Some(node);
        while let Some(i) = cur {
            if let Some(t) = &self.nodes[i].thought {
                chain.push(PathStep { category: t.category, text: t.text.clone() });
            }
            cur = self.nodes[i].parent;
        }
        chain.reverse();
        chain
    }

    /// The accumulated path text including a candidate `next` thought — the
    /// context an embedding recall would key on.
    fn path_text(&self, node: usize, next: &str) -> String {
        let mut parts: Vec<String> =
            self.path_steps(node).into_iter().map(|s| s.text).collect();
        parts.push(next.to_string());
        parts.join(" \u{2192} ")
    }

    /// UCT: exploit mean value + explore low-visit nodes. Unvisited children sort
    /// first. Ties break toward the earliest-inserted child (deterministic).
    fn best_uct_child(&self, node: usize, c: f64) -> usize {
        let parent_visits = (self.nodes[node].visits.max(1)) as f64;
        let mut best = self.nodes[node].children[0];
        let mut best_score = f64::NEG_INFINITY;
        for &child in &self.nodes[node].children {
            let n = &self.nodes[child];
            let score = if n.visits == 0 {
                f64::INFINITY
            } else {
                let exploit = n.value_sum / n.visits as f64;
                let explore = c * (parent_visits.ln() / n.visits as f64).sqrt();
                exploit + explore
            };
            if score > best_score {
                best_score = score;
                best = child;
            }
        }
        best
    }

    /// Backpropagate a reward up the ancestry: +1 visit, +reward value on each.
    fn backprop(&mut self, mut node: usize, reward: f64) {
        loop {
            let n = &mut self.nodes[node];
            n.visits += 1;
            n.value_sum += reward;
            match n.parent {
                Some(p) => node = p,
                None => break,
            }
        }
    }

    fn mean_value(&self, node: usize) -> f64 {
        let n = &self.nodes[node];
        if n.visits == 0 { 0.0 } else { n.value_sum / n.visits as f64 }
    }

    /// The winning path: from the root, always descend to the robust child (most
    /// visits; ties → higher mean value; then earliest). Returns node indices.
    fn best_path(&self) -> Vec<usize> {
        let mut path = Vec::new();
        let mut cur = self.root;
        loop {
            let children = &self.nodes[cur].children;
            if children.is_empty() {
                break;
            }
            let mut best = children[0];
            for &child in children {
                let (cv, cm) = (self.nodes[child].visits, self.mean_value(child));
                let (bv, bm) = (self.nodes[best].visits, self.mean_value(best));
                if cv > bv || (cv == bv && cm > bm) {
                    best = child;
                }
            }
            path.push(best);
            cur = best;
        }
        path
    }

    /// Settle the [`BranchTree`]: commit the winning path, prune everything else
    /// (fork-and-prune, exactly as `cortex.deliberate` does for best-of-N).
    fn settle(&mut self, best: &[usize]) {
        let keep: std::collections::HashSet<u64> =
            best.iter().map(|&i| self.nodes[i].branch_id).collect();
        // Prune non-winning leaves' branches; commit winners. Iterate a snapshot
        // of branch ids so we don't borrow `nodes` while mutating `branches`.
        let ids: Vec<(u64, bool)> = self
            .nodes
            .iter()
            .filter(|n| n.parent.is_some())
            .map(|n| (n.branch_id, keep.contains(&n.branch_id)))
            .collect();
        for (bid, winner) in ids {
            if winner {
                let _ = self.branches.commit(bid);
            } else {
                let _ = self.branches.prune(bid);
            }
        }
    }

    fn into_trace(mut self, problem: &Problem, config: &CoatConfig) -> CoatTrace {
        let best = self.best_path();
        self.settle(&best);
        let on_best: std::collections::HashSet<usize> = best.iter().copied().collect();

        let best_path: Vec<TraceStep> = best
            .iter()
            .map(|&i| {
                let n = &self.nodes[i];
                let t = n.thought.as_ref().expect("non-root on best path");
                TraceStep {
                    depth: n.depth,
                    category: t.category,
                    text: t.text.clone(),
                    prior: t.prior,
                    value: self.mean_value(i),
                    visits: n.visits,
                    recall: t.recall.clone(),
                }
            })
            .collect();

        let recalled_total: usize = self
            .nodes
            .iter()
            .filter_map(|n| n.thought.as_ref())
            .map(|t| t.recall.len())
            .sum();

        let tree: Vec<TraceNode> = self
            .nodes
            .iter()
            .enumerate()
            .map(|(i, n)| TraceNode {
                id: i,
                branch_id: n.branch_id,
                parent: n.parent,
                depth: n.depth,
                category: n.thought.as_ref().map(|t| t.category),
                text: n.thought.as_ref().map(|t| t.text.clone()).unwrap_or_default(),
                prior: n.thought.as_ref().map(|t| t.prior).unwrap_or(0.0),
                value: self.mean_value(i),
                visits: n.visits,
                recall_count: n.thought.as_ref().map(|t| t.recall.len()).unwrap_or(0),
                on_best_path: on_best.contains(&i),
            })
            .collect();

        let nodes_expanded = self.nodes.len().saturating_sub(1);
        let summary = format!(
            "{} | \"{}\" | {} iters, {} nodes, depth\u{2264}{} | best path {} steps, value={:.3} | recalled {} item(s)",
            config.rung(),
            truncate(&problem.statement, 60),
            config.iterations,
            nodes_expanded,
            config.max_depth,
            best_path.len(),
            best_path.last().map(|s| s.value).unwrap_or(0.0),
            recalled_total,
        );

        CoatTrace {
            problem: problem.statement.clone(),
            rung: config.rung().to_string(),
            iterations: config.iterations,
            nodes_expanded,
            recalled_total,
            best_path,
            tree,
            summary,
        }
    }
}

fn truncate(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let head: String = s.chars().take(max.saturating_sub(1)).collect();
        format!("{head}\u{2026}")
    }
}

/// One step of the winning reasoning trace.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceStep {
    /// Depth in the tree (1 = first thought after the root).
    pub depth: u32,
    /// The step's constrained category.
    pub category: ThoughtCategory,
    /// The thought text.
    pub text: String,
    /// The PRM's proposed base value.
    pub prior: f64,
    /// The backpropagated mean value at this node.
    pub value: f64,
    /// How many times the search visited this node.
    pub visits: u32,
    /// The associative memory recalled here (CoAT).
    pub recall: Vec<Recall>,
}

/// One node of the full search tree, for the observatory.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceNode {
    /// Node index (arena id).
    pub id: usize,
    /// The M007 branch-tree id this node forked.
    pub branch_id: u64,
    /// Parent node index (`None` for the root).
    pub parent: Option<usize>,
    /// Depth (root = 0).
    pub depth: u32,
    /// Category (`None` for the root).
    pub category: Option<ThoughtCategory>,
    /// Thought text (empty for the root).
    pub text: String,
    /// PRM prior.
    pub prior: f64,
    /// Backpropagated mean value.
    pub value: f64,
    /// Visit count.
    pub visits: u32,
    /// How many associative-memory items were recalled here.
    pub recall_count: usize,
    /// Whether this node lies on the winning reasoning path.
    pub on_best_path: bool,
}

/// The result of a deliberation: the winning reasoning trace + the full tree.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoatTrace {
    /// The problem statement.
    pub problem: String,
    /// Which rung of the ladder ran (CoT / ToT / MCTS / CoAT).
    pub rung: String,
    /// The search budget spent.
    pub iterations: u32,
    /// Nodes expanded (excludes the root).
    pub nodes_expanded: usize,
    /// Total associative-memory items recalled across the whole tree.
    pub recalled_total: usize,
    /// The winning root→leaf reasoning chain.
    pub best_path: Vec<TraceStep>,
    /// Every node, for rendering the tree in the observatory.
    pub tree: Vec<TraceNode>,
    /// A one-line human summary.
    pub summary: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A deterministic thought source: `k` seeds per node, priors decreasing by
    /// index (seed 0 best), categories cycling through the constrained space,
    /// text encoding depth + index so recall stubs can key on it.
    struct Fixed;
    impl ThoughtSource for Fixed {
        fn expand(&mut self, _p: &Problem, path: &[PathStep], k: usize) -> Vec<ThoughtSeed> {
            (0..k)
                .map(|i| ThoughtSeed {
                    category: ThoughtCategory::ALL[(path.len() + i) % 5],
                    text: format!("d{}#{i}", path.len()),
                    prior: 0.9 - 0.1 * i as f64,
                })
                .collect()
        }
    }

    /// Two equal-prior seeds: one "supported", one "bare". Recall fires only for
    /// the supported one — the CoAT-bias test.
    struct TwoEqual;
    impl ThoughtSource for TwoEqual {
        fn expand(&mut self, _p: &Problem, _path: &[PathStep], _k: usize) -> Vec<ThoughtSeed> {
            vec![
                ThoughtSeed { category: ThoughtCategory::Plan, text: "supported".into(), prior: 0.5 },
                ThoughtSeed { category: ThoughtCategory::Plan, text: "bare".into(), prior: 0.5 },
            ]
        }
    }

    /// Recalls a strong item iff the context text mentions "supported".
    struct KeyedMemory;
    impl AssociativeMemory for KeyedMemory {
        fn recall(&self, ctx: &ThoughtContext, k: usize) -> Vec<Recall> {
            if k > 0 && ctx.text.contains("supported") {
                vec![Recall { id: 1, relevance: 1.0, note: "prior success".into() }]
            } else {
                Vec::new()
            }
        }
    }

    fn problem() -> Problem {
        Problem::new("prove the theorem")
    }

    #[test]
    fn empty_problem_is_an_error() {
        let mut e = CoatEngine::new(Fixed, NoMemory, CoatConfig::coat());
        assert!(matches!(e.deliberate(&Problem::new("   ")), Err(CoatError::EmptyProblem)));
    }

    #[test]
    fn cot_preset_is_a_linear_chain() {
        let mut e = CoatEngine::new(Fixed, NoMemory, CoatConfig::cot());
        let t = e.deliberate(&problem()).unwrap();
        assert_eq!(t.rung, "CoT");
        // expand_k == 1 → every node has at most one child → the tree IS the path.
        assert_eq!(t.tree.len(), t.best_path.len() + 1, "CoT must be a single chain");
        assert!(!t.best_path.is_empty());
    }

    #[test]
    fn tot_preset_branches_into_a_tree() {
        let mut e = CoatEngine::new(Fixed, NoMemory, CoatConfig::tot());
        let t = e.deliberate(&problem()).unwrap();
        assert_eq!(t.rung, "ToT");
        // the root must sprout more than one child (a tree, not a chain).
        let root_children = t.tree.iter().filter(|n| n.parent == Some(0)).count();
        assert!(root_children > 1, "ToT must branch; got {root_children} root children");
    }

    #[test]
    fn mcts_backprop_accounts_every_iteration_at_the_root() {
        let cfg = CoatConfig::mcts();
        let mut e = CoatEngine::new(Fixed, NoMemory, cfg);
        let t = e.deliberate(&problem()).unwrap();
        assert_eq!(t.rung, "MCTS");
        // every iteration backpropagates to the root exactly once.
        let root_visits = t.tree[0].visits;
        assert_eq!(root_visits, cfg.iterations, "root visits must equal the budget");
        // a parent is visited at least as often as any child (backprop invariant).
        for n in &t.tree {
            if let Some(p) = n.parent {
                assert!(t.tree[p].visits >= n.visits, "parent must dominate child visits");
            }
        }
    }

    #[test]
    fn constrained_action_space_only() {
        let mut e = CoatEngine::new(Fixed, NoMemory, CoatConfig::coat());
        let t = e.deliberate(&problem()).unwrap();
        for n in &t.tree {
            if let Some(c) = n.category {
                assert!(ThoughtCategory::ALL.contains(&c), "action outside the constrained space");
            }
        }
    }

    #[test]
    fn coat_recall_biases_the_winning_path() {
        // With recall ON, the memory-supported thought (equal prior) must win.
        let mut on = CoatEngine::new(TwoEqual, KeyedMemory, CoatConfig::coat());
        let won = on.deliberate(&problem()).unwrap();
        assert_eq!(won.rung, "CoAT");
        assert_eq!(won.best_path[0].text, "supported",
            "recall must lift the supported thought to the winning path");
        assert!(won.recalled_total > 0, "CoAT must recall associative memory");
        assert!(won.best_path[0].value > won.best_path[0].prior,
            "recall must modulate value above the bare prior");

        // With recall OFF (weight 0), the tie breaks by source order → "supported"
        // still first, but its value must NOT exceed its prior (no memory lift).
        let mut cfg = CoatConfig::coat();
        cfg.recall_weight = 0.0;
        cfg.recall_k = 0;
        let mut off = CoatEngine::new(TwoEqual, KeyedMemory, cfg);
        let plain = off.deliberate(&problem()).unwrap();
        assert_eq!(plain.recalled_total, 0, "recall_k 0 must pull no memory");
        let sup = plain.best_path[0].value;
        assert!((sup - plain.best_path[0].prior).abs() < 1e-9,
            "without recall, value must equal the prior");
    }

    #[test]
    fn deliberation_is_deterministic() {
        let run = || {
            CoatEngine::new(Fixed, NoMemory, CoatConfig::mcts())
                .deliberate(&problem())
                .unwrap()
                .summary
        };
        assert_eq!(run(), run(), "same inputs must yield the same trace (replayability)");
    }

    #[test]
    fn winning_branch_is_committed_and_traces_serialize() {
        let mut e = CoatEngine::new(Fixed, KeyedMemory, CoatConfig::coat());
        let t = e.deliberate(&problem()).unwrap();
        assert!(t.tree.iter().any(|n| n.on_best_path), "some node must be on the best path");
        // the trace must round-trip through JSON (the gateway serves it).
        let j = serde_json::to_string(&t).unwrap();
        let back: CoatTrace = serde_json::from_str(&j).unwrap();
        assert_eq!(back.summary, t.summary);
    }
}
