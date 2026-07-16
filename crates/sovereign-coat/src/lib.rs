//! `sovereign-coat` — Chain-of-Associated-Thoughts: deliberate, search-based
//! reasoning as one parameterized engine.
//!
//! The operator's standing directive
//! (`docs/standing-directives/2026-07-12-deliberate-reasoning.md`) codifies the
//! progression **CoT → ToT → MCTS → C-MCTS → CoAT**. This crate is the top rung,
//! and it earns the thesis by being a *single* engine the earlier rungs fall out
//! of as presets — each rung is behaviourally distinct, not a relabel:
//!
//! | rung | what it adds | preset |
//! |------|--------------|--------|
//! | **CoT** | one linear chain of thought | [`CoatConfig::cot`] (`expand_k = 1`) |
//! | **ToT** | a real **BFS or DFS** tree search that can **backtrack** from dead ends | [`CoatConfig::tot`] (BFS) / [`CoatConfig::tot_dfs`] (DFS) |
//! | **MCTS** | UCT selection + expansion + **rollout** simulation + backprop | [`CoatConfig::mcts`] |
//! | **C-MCTS** | a **constrained** action space that actually gates the search | [`CoatConfig::cmcts`] (phase-gates categories per depth) |
//! | **CoAT** ⭐ | associative memory **recalled at every expansion that both conditions generation (RAG) and steers which path wins** | [`CoatConfig::coat`] (the default) |
//!
//! ## The four MCTS phases (over the M007 [`sovereign_branch_tree::BranchTree`])
//!
//! 1. **Selection** — a tree policy: UCT descent, or a BFS/DFS frontier. Abandoned
//!    (backtracked) subtrees are skipped.
//! 2. **Expansion** — [`sovereign_branch_tree::BranchTree::fork`] one child from an
//!    untried thought seed. Under CoAT the node first **recalls** associative
//!    memory for the path-so-far and **feeds it into thought generation** (RAG);
//!    each child then recalls memory keyed on **its own** text, so recall differs
//!    per thought and can change which thought wins.
//! 3. **Simulation** — a real **greedy rollout** to `max_depth` returning the best
//!    value reachable, so a node is valued by where it *leads*, not just its next
//!    step. (Set [`CoatConfig::rollout`] `false` for a one-step value estimate.)
//! 4. **Backpropagation** — propagate the reward up the `lineage()`.
//!
//! **Backtracking** is real: a freshly-scored thought below [`CoatConfig::prune_below`]
//! is *abandoned* — its branch is [`sovereign_branch_tree::BranchTree::prune`]d
//! during the search and never selected again; when a subtree is exhausted the
//! search retreats and pursues another branch. After the budget is spent the
//! best-value root→leaf path is committed and everything else pruned.
//!
//! ## Why it is generic (and therefore testable without a model)
//!
//! The two model-gated inputs are traits — [`ThoughtSource`] (generate thoughts)
//! and [`AssociativeMemory`] (recall knowledge). In production the LLM satisfies
//! the first and the Memory-OS `retrieve()` the second; in tests deterministic
//! stubs satisfy both, so the whole search **harness** is exercised while the
//! **thought content** stays model-gated. The engine uses no randomness: same
//! inputs → same trace (replayability).

use serde::{Deserialize, Serialize};
use sovereign_branch_tree::{BranchTree, ROOT};

/// Errors the engine can return.
#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum CoatError {
    /// The problem statement was empty — nothing to deliberate about.
    #[error("empty problem statement")]
    EmptyProblem,
    /// A budget knob was nonsensical (would do no reasoning).
    #[error("invalid config: {0}")]
    InvalidConfig(String),
}

/// The **constrained action space** (the C in C-MCTS): the engine only ever
/// expands a node into one of these five categories, and under
/// [`CoatConfig::constrain`] it further **phase-gates** which are legal at each
/// depth — keeping the search tractable and less prone to unstructured,
/// hallucinated steps.
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

    /// The categories legal at `depth` when the action space is constrained
    /// (C-MCTS phase-gating): understand/plan early, work/reflect in the middle,
    /// reflect/summarize as the reasoning closes. Constraining therefore prunes
    /// out-of-phase branches the search would otherwise spend budget on.
    pub fn allowed_at(depth: u32, max_depth: u32) -> &'static [ThoughtCategory] {
        use ThoughtCategory::{Code, Plan, Reflect, Summarize, Understand};
        let last = max_depth.saturating_sub(1);
        if depth <= 1 {
            &[Understand, Plan]
        } else if depth >= last {
            &[Reflect, Summarize]
        } else {
            &[Plan, Reflect, Code]
        }
    }
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
        Problem {
            statement: statement.into(),
            topic: 0,
            entity: 0,
        }
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
    /// The proposed base value in `[0, 1]`.
    pub prior: f64,
}

/// One item recalled from associative memory (maps onto a Memory-OS `Hit`). This
/// is CoAT's mechanism: knowledge pulled in *while deliberating*.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Recall {
    /// The recalled item's id (key into the cold store).
    pub id: u64,
    /// Relevance in `[0, 1]` (higher = more supportive of the thought). This is
    /// an **absolute** strength, not a within-batch rank — a weak hit stays weak.
    pub relevance: f64,
    /// A short human-readable note about what was recalled.
    #[serde(default)]
    pub note: String,
}

/// The query context handed to [`AssociativeMemory::recall`]. `text` is the
/// accumulated path **including the candidate thought**, so a real recall can key
/// on the specific thought (that is what lets recall differ per thought).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThoughtContext {
    /// Topic sketch bitset (from the [`Problem`]).
    pub topic: u64,
    /// Entity sketch bitset (from the [`Problem`]).
    pub entity: u64,
    /// The accumulated path text including the candidate thought.
    pub text: String,
}

/// Produces candidate next thoughts, **conditioned on the memory recalled for the
/// path so far** (RAG). Model-gated in production (the LLM); a deterministic stub
/// in tests.
pub trait ThoughtSource {
    /// Propose up to `k` continuations of `path` for `problem`, given the
    /// `associated` memory recalled for the path. Fewer than `k` (or zero) is
    /// allowed; the engine truncates to `k` and stops expanding when a node dries.
    fn expand(
        &mut self,
        problem: &Problem,
        path: &[PathStep],
        associated: &[Recall],
        k: usize,
    ) -> Vec<ThoughtSeed>;

    /// A short label naming the source (`"model"` / `"heuristic"`), surfaced in
    /// the trace so a consumer can tell real reasoning from a placeholder.
    fn label(&self) -> &str {
        "unspecified"
    }
}

/// CoAT's associative-memory mechanism: recall knowledge related to a thought
/// while deliberating. Production: the Memory-OS `retrieve()`; tests: a stub.
pub trait AssociativeMemory {
    /// Recall up to `k` items relevant to `ctx`. Empty is fine.
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

/// The selection (tree) policy.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SearchStrategy {
    /// UCT descent (explore vs exploit) — MCTS/CoAT.
    Uct,
    /// Breadth-first frontier — expand the shallowest open node (ToT/BFS).
    Bfs,
    /// Depth-first frontier — expand the deepest open node (ToT/DFS).
    Dfs,
}

/// Engine knobs. The presets show the whole ladder is one engine.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct CoatConfig {
    /// Search budget: select→expand→simulate→backprop iterations.
    pub iterations: u32,
    /// UCT exploration constant (only used when `strategy == Uct`).
    pub exploration_c: f64,
    /// Branching factor: thoughts proposed per node. `1` = a linear chain (CoT).
    pub expand_k: usize,
    /// Associative items recalled per expansion (`0` disables recall).
    pub recall_k: usize,
    /// Maximum reasoning depth (root is depth 0).
    pub max_depth: u32,
    /// How strongly recall modulates value (`0.0` = ignore memory).
    pub recall_weight: f64,
    /// The tree policy: UCT / BFS / DFS.
    pub strategy: SearchStrategy,
    /// Simulate via a greedy **rollout** to `max_depth` (look-ahead) vs a
    /// one-step value estimate.
    pub rollout: bool,
    /// Constrain the action space by phase-gating categories per depth (C-MCTS).
    pub constrain: bool,
    /// Backtracking threshold: a thought scoring **below** this is abandoned and
    /// its branch pruned during the search (`0.0` disables backtracking).
    pub prune_below: f64,
}

impl Default for CoatConfig {
    fn default() -> Self {
        CoatConfig::coat()
    }
}

impl CoatConfig {
    /// **CoT** — a single linear chain of thought (`expand_k = 1`, no recall).
    pub fn cot() -> Self {
        CoatConfig {
            iterations: 4,
            exploration_c: 0.0,
            expand_k: 1,
            recall_k: 0,
            max_depth: 4,
            recall_weight: 0.0,
            strategy: SearchStrategy::Uct,
            rollout: false,
            constrain: false,
            prune_below: 0.0,
        }
    }

    /// **ToT (BFS)** — a real breadth-first tree search that can backtrack from
    /// dead ends, with look-ahead rollout scoring. No recall, no constraint.
    pub fn tot() -> Self {
        CoatConfig {
            iterations: 32,
            exploration_c: 0.0,
            expand_k: 3,
            recall_k: 0,
            max_depth: 4,
            recall_weight: 0.0,
            strategy: SearchStrategy::Bfs,
            rollout: true,
            constrain: false,
            prune_below: 0.2,
        }
    }

    /// **ToT (DFS)** — depth-first variant of [`Self::tot`].
    pub fn tot_dfs() -> Self {
        CoatConfig {
            strategy: SearchStrategy::Dfs,
            ..CoatConfig::tot()
        }
    }

    /// **MCTS** — UCT selection + rollout simulation + backprop.
    pub fn mcts() -> Self {
        CoatConfig {
            iterations: 64,
            exploration_c: std::f64::consts::SQRT_2,
            expand_k: 3,
            recall_k: 0,
            max_depth: 4,
            recall_weight: 0.0,
            strategy: SearchStrategy::Uct,
            rollout: true,
            constrain: false,
            prune_below: 0.2,
        }
    }

    /// **C-MCTS** — MCTS with the action space constrained (phase-gated
    /// categories), so the branching is bounded by structure, not just `expand_k`.
    pub fn cmcts() -> Self {
        CoatConfig {
            constrain: true,
            ..CoatConfig::mcts()
        }
    }

    /// **CoAT** ⭐ — C-MCTS with associative memory recalled at every expansion,
    /// conditioning generation and steering which path wins. The default.
    pub fn coat() -> Self {
        CoatConfig {
            recall_k: 3,
            recall_weight: 0.35,
            ..CoatConfig::cmcts()
        }
    }

    /// The rung name this config corresponds to — derived from **behaviour**, not
    /// wishful labels.
    pub fn rung(&self) -> &'static str {
        if self.recall_weight > 0.0 && self.recall_k > 0 {
            "CoAT"
        } else if self.constrain {
            "C-MCTS"
        } else if self.expand_k <= 1 {
            "CoT"
        } else if matches!(self.strategy, SearchStrategy::Bfs | SearchStrategy::Dfs) {
            "ToT"
        } else if self.exploration_c > 0.0 {
            "MCTS"
        } else {
            "ToT"
        }
    }

    /// Reject budgets that would do no reasoning.
    pub fn validate(&self) -> Result<(), CoatError> {
        if self.iterations == 0 {
            return Err(CoatError::InvalidConfig("iterations must be > 0".into()));
        }
        if self.expand_k == 0 {
            return Err(CoatError::InvalidConfig("expand_k must be > 0".into()));
        }
        if self.max_depth == 0 {
            return Err(CoatError::InvalidConfig("max_depth must be > 0".into()));
        }
        Ok(())
    }
}

/// The shared value function: a thought's `prior`, modulated upward by the mean
/// relevance of the memory recalled for it (CoAT). `weight == 0` → prior alone.
fn value_of(prior: f64, recall: &[Recall], weight: f64) -> f64 {
    let base = prior.clamp(0.0, 1.0);
    if recall.is_empty() || weight == 0.0 {
        base
    } else {
        let mean = recall.iter().map(|r| r.relevance).sum::<f64>() / recall.len() as f64;
        (base + weight * mean).clamp(0.0, 1.0)
    }
}

/// A committed thought living on a node: the seed plus the memory recalled for it.
#[derive(Debug, Clone)]
struct Thought {
    category: ThoughtCategory,
    text: String,
    prior: f64,
    recall: Vec<Recall>,
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
    /// Associative memory recalled for this node's path (feeds child generation).
    associated: Vec<Recall>,
    /// Candidate seeds not yet expanded into children (lazily generated).
    untried: Vec<ThoughtSeed>,
    /// Whether [`ThoughtSource::expand`] has been consulted for this node yet.
    seeds_generated: bool,
    /// Backtracked: pruned from the live search, never selected again.
    abandoned: bool,
    visits: u32,
    value_sum: f64,
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
        CoatEngine {
            thoughts,
            memory,
            config,
        }
    }

    /// Run the full deliberation and return the reasoning trace.
    pub fn deliberate(&mut self, problem: &Problem) -> Result<CoatTrace, CoatError> {
        self.config.validate()?;
        if problem.statement.trim().is_empty() {
            return Err(CoatError::EmptyProblem);
        }
        let mut tree = Tree::new();
        for _ in 0..self.config.iterations {
            let selected = self.select(&mut tree);
            let node = self
                .expand(&mut tree, problem, selected)
                .unwrap_or(selected);
            let reward = self.simulate(problem, &tree, node);
            tree.backprop(node, reward);
            // Backtracking: abandon a freshly-scored thought below the floor.
            if self.config.prune_below > 0.0
                && node != tree.root
                && tree.nodes[node].thought.is_some()
                && reward < self.config.prune_below
            {
                tree.abandon(node);
            }
        }
        Ok(tree.into_trace(problem, &self.config, self.thoughts.label()))
    }

    /// Selection dispatch: UCT descent, or a BFS/DFS frontier.
    fn select(&mut self, tree: &mut Tree) -> usize {
        match self.config.strategy {
            SearchStrategy::Uct => self.select_uct(tree),
            SearchStrategy::Bfs => tree.select_frontier(self.config.max_depth, true),
            SearchStrategy::Dfs => tree.select_frontier(self.config.max_depth, false),
        }
    }

    /// UCT tree policy: descend by best non-abandoned UCT child to an expandable
    /// node. A subtree with no live children is itself abandoned (backtrack).
    fn select_uct(&mut self, tree: &mut Tree) -> usize {
        let mut cur = tree.root;
        loop {
            let n = &tree.nodes[cur];
            if n.depth >= self.config.max_depth {
                return cur;
            }
            if !n.seeds_generated || !n.untried.is_empty() {
                return cur; // expandable here
            }
            match tree.best_uct_child(cur, self.config.exploration_c) {
                Some(child) => cur = child,
                None => {
                    // Fully expanded, every child abandoned → a dead subtree.
                    if cur != tree.root {
                        tree.abandon(cur);
                    }
                    return tree.root;
                }
            }
        }
    }

    /// Expansion: recall for the path (feeds generation, RAG), generate + truncate
    /// + optionally constrain seeds, then fork one child and recall for *its* text.
    fn expand(&mut self, tree: &mut Tree, problem: &Problem, parent: usize) -> Option<usize> {
        if tree.nodes[parent].depth >= self.config.max_depth {
            return None;
        }
        if !tree.nodes[parent].seeds_generated {
            // Node-level associative recall for the path so far (CoAT RAG input).
            let associated = self.recall_for(problem, tree, parent, "");
            let path = tree.path_steps(parent);
            let mut seeds = self
                .thoughts
                .expand(problem, &path, &associated, self.config.expand_k);
            seeds.truncate(self.config.expand_k); // enforce k (protects the CoT invariant)
            if self.config.constrain {
                let allowed = ThoughtCategory::allowed_at(
                    tree.nodes[parent].depth + 1,
                    self.config.max_depth,
                );
                let kept: Vec<ThoughtSeed> = seeds
                    .iter()
                    .filter(|s| allowed.contains(&s.category))
                    .cloned()
                    .collect();
                // Never dead-end a node purely from constraint: keep one if all gated.
                seeds = if kept.is_empty() {
                    seeds.into_iter().take(1).collect()
                } else {
                    kept
                };
            }
            seeds.reverse(); // pop() yields source order
            tree.nodes[parent].untried = seeds;
            tree.nodes[parent].associated = associated;
            tree.nodes[parent].seeds_generated = true;
        }
        let seed = tree.nodes[parent].untried.pop()?;
        // Per-child recall keyed on THIS thought's text — differs per thought, so
        // recall can change which child wins (steering).
        let recall = self.recall_for(problem, tree, parent, &seed.text);
        let branch_id = tree.branches.fork(tree.nodes[parent].branch_id).ok()?;
        let thought = Thought {
            category: seed.category,
            text: seed.text,
            prior: seed.prior,
            recall,
        };
        Some(tree.push_child(parent, branch_id, thought))
    }

    /// Recall associative memory for `parent`'s path plus an optional `next`
    /// thought, keyed on the **evolving path text** (topic/entity from the
    /// problem). Empty when recall is disabled.
    fn recall_for(&self, problem: &Problem, tree: &Tree, parent: usize, next: &str) -> Vec<Recall> {
        if self.config.recall_k == 0 {
            return Vec::new();
        }
        let ctx = ThoughtContext {
            topic: problem.topic,
            entity: problem.entity,
            text: tree.path_text(parent, next),
        };
        self.memory.recall(&ctx, self.config.recall_k)
    }

    /// Simulation. With `rollout`, greedily extend the node to `max_depth` and
    /// return the **best** value reachable — a real look-ahead, so a node is
    /// valued by where it leads. Otherwise, the node's own one-step value.
    fn simulate(&mut self, problem: &Problem, tree: &Tree, node: usize) -> f64 {
        let base = match &tree.nodes[node].thought {
            None => 0.5,
            Some(t) => value_of(t.prior, &t.recall, self.config.recall_weight),
        };
        if !self.config.rollout {
            return base;
        }
        let mut best = base;
        let mut path = tree.path_steps(node);
        let mut depth = tree.nodes[node].depth;
        while depth < self.config.max_depth {
            let assoc = self.recall_for_path(problem, &path, "");
            let mut seeds = self
                .thoughts
                .expand(problem, &path, &assoc, self.config.expand_k);
            seeds.truncate(self.config.expand_k);
            if self.config.constrain {
                let allowed = ThoughtCategory::allowed_at(depth + 1, self.config.max_depth);
                let kept: Vec<ThoughtSeed> = seeds
                    .iter()
                    .filter(|s| allowed.contains(&s.category))
                    .cloned()
                    .collect();
                seeds = if kept.is_empty() {
                    seeds.into_iter().take(1).collect()
                } else {
                    kept
                };
            }
            if seeds.is_empty() {
                break;
            }
            // Greedy: take the highest-value seed (prior modulated by its recall).
            let mut chosen: Option<(ThoughtSeed, f64)> = None;
            for s in &seeds {
                let rec = self.recall_for_path(problem, &path, &s.text);
                let v = value_of(s.prior, &rec, self.config.recall_weight);
                if chosen.as_ref().map(|(_, bv)| v > *bv).unwrap_or(true) {
                    chosen = Some((s.clone(), v));
                }
            }
            let (seed, v) = chosen.expect("seeds non-empty");
            best = best.max(v);
            path.push(PathStep {
                category: seed.category,
                text: seed.text,
            });
            depth += 1;
        }
        best
    }

    /// Recall for an explicit path (used inside a rollout, which does not touch
    /// the tree).
    fn recall_for_path(&self, problem: &Problem, path: &[PathStep], next: &str) -> Vec<Recall> {
        if self.config.recall_k == 0 {
            return Vec::new();
        }
        let mut parts: Vec<&str> = path.iter().map(|s| s.text.as_str()).collect();
        if !next.is_empty() {
            parts.push(next);
        }
        let ctx = ThoughtContext {
            topic: problem.topic,
            entity: problem.entity,
            text: parts.join(" \u{2192} "),
        };
        self.memory.recall(&ctx, self.config.recall_k)
    }
}

/// The search tree: the node arena plus the real M007 [`BranchTree`] it drives.
#[derive(Debug)]
struct Tree {
    nodes: Vec<Node>,
    branches: BranchTree,
    root: usize,
    abandoned_count: usize,
}

impl Tree {
    fn new() -> Self {
        let root = Node {
            branch_id: ROOT,
            parent: None,
            children: Vec::new(),
            depth: 0,
            thought: None,
            associated: Vec::new(),
            untried: Vec::new(),
            seeds_generated: false,
            abandoned: false,
            visits: 0,
            value_sum: 0.0,
        };
        Tree {
            nodes: vec![root],
            branches: BranchTree::new(),
            root: 0,
            abandoned_count: 0,
        }
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
            associated: Vec::new(),
            untried: Vec::new(),
            seeds_generated: false,
            abandoned: false,
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
                chain.push(PathStep {
                    category: t.category,
                    text: t.text.clone(),
                });
            }
            cur = self.nodes[i].parent;
        }
        chain.reverse();
        chain
    }

    /// The accumulated path text including a candidate `next` thought.
    fn path_text(&self, node: usize, next: &str) -> String {
        let mut parts: Vec<String> = self.path_steps(node).into_iter().map(|s| s.text).collect();
        if !next.is_empty() {
            parts.push(next.to_string());
        }
        parts.join(" \u{2192} ")
    }

    /// Abandon a node (backtracking): mark it dead + prune its branch so it is
    /// never selected again.
    fn abandon(&mut self, node: usize) {
        if !self.nodes[node].abandoned {
            self.nodes[node].abandoned = true;
            self.abandoned_count += 1;
            let _ = self.branches.prune(self.nodes[node].branch_id);
        }
    }

    /// UCT: exploit mean value + explore low-visit nodes. Unvisited sort first;
    /// abandoned children are skipped. Ties break toward the earliest child.
    /// `None` when every child is abandoned.
    fn best_uct_child(&self, node: usize, c: f64) -> Option<usize> {
        let parent_visits = (self.nodes[node].visits.max(1)) as f64;
        let mut best = None;
        let mut best_score = f64::NEG_INFINITY;
        for &child in &self.nodes[node].children {
            if self.nodes[child].abandoned {
                continue;
            }
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
                best = Some(child);
            }
        }
        best
    }

    /// BFS/DFS frontier policy: pick the shallowest (`min_depth`) or deepest open,
    /// non-abandoned node that can still take a child. Falls back to the root.
    fn select_frontier(&self, max_depth: u32, min_depth: bool) -> usize {
        let mut best: Option<usize> = None;
        let mut best_depth = if min_depth { u32::MAX } else { 0 };
        for (i, n) in self.nodes.iter().enumerate() {
            if n.abandoned || n.depth >= max_depth {
                continue;
            }
            let expandable = !n.seeds_generated || !n.untried.is_empty();
            if !expandable {
                continue;
            }
            let take = match best {
                None => true,
                Some(_) => {
                    if min_depth {
                        n.depth < best_depth
                    } else {
                        n.depth >= best_depth
                    }
                }
            };
            if take {
                best_depth = n.depth;
                best = Some(i);
            }
        }
        best.unwrap_or(self.root)
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
        if n.visits == 0 {
            0.0
        } else {
            n.value_sum / n.visits as f64
        }
    }

    /// The winning path: from the root, descend to the highest-value non-abandoned
    /// child (ties → most visits → earliest). Value-first so a look-ahead-strong
    /// branch wins even if a sibling was visited more.
    fn best_path(&self) -> Vec<usize> {
        let mut path = Vec::new();
        let mut cur = self.root;
        loop {
            let mut best: Option<usize> = None;
            for &child in &self.nodes[cur].children {
                if self.nodes[child].abandoned {
                    continue;
                }
                let better = match best {
                    None => true,
                    Some(b) => {
                        let (cv, cm) = (self.nodes[child].visits, self.mean_value(child));
                        let (bv, bm) = (self.nodes[b].visits, self.mean_value(b));
                        cm > bm || (cm == bm && cv > bv)
                    }
                };
                if better {
                    best = Some(child);
                }
            }
            match best {
                Some(b) => {
                    path.push(b);
                    cur = b;
                }
                None => break,
            }
        }
        path
    }

    /// Settle the [`BranchTree`]: commit the winning path, prune everything else
    /// (fork-and-prune). Returns `(committed, pruned)` counts.
    fn settle(&mut self, best: &[usize]) -> (usize, usize) {
        let keep: std::collections::HashSet<u64> =
            best.iter().map(|&i| self.nodes[i].branch_id).collect();
        let ids: Vec<(u64, bool)> = self
            .nodes
            .iter()
            .filter(|n| n.parent.is_some())
            .map(|n| (n.branch_id, keep.contains(&n.branch_id)))
            .collect();
        let (mut committed, mut pruned) = (0usize, 0usize);
        for (bid, winner) in ids {
            if winner {
                if self.branches.commit(bid).is_ok() {
                    committed += 1;
                }
            } else if self.branches.prune(bid).is_ok() {
                pruned += 1;
            }
        }
        (committed, pruned)
    }

    fn into_trace(mut self, problem: &Problem, config: &CoatConfig, source: &str) -> CoatTrace {
        let best = self.best_path();
        let (committed, pruned) = self.settle(&best);
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
            .map(|n| n.thought.as_ref().map(|t| t.recall.len()).unwrap_or(0) + n.associated.len())
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
                text: n
                    .thought
                    .as_ref()
                    .map(|t| t.text.clone())
                    .unwrap_or_default(),
                prior: n.thought.as_ref().map(|t| t.prior).unwrap_or(0.0),
                value: self.mean_value(i),
                visits: n.visits,
                recall_count: n.thought.as_ref().map(|t| t.recall.len()).unwrap_or(0),
                abandoned: n.abandoned,
                on_best_path: on_best.contains(&i),
            })
            .collect();

        // Report the path value as the weakest link along the winning chain — a
        // path aggregate, not just the leaf's own prior.
        let path_value = best_path
            .iter()
            .map(|s| s.value)
            .fold(f64::INFINITY, f64::min);
        let path_value = if path_value.is_finite() {
            path_value
        } else {
            0.0
        };

        let nodes_expanded = self.nodes.len().saturating_sub(1);
        let summary = format!(
            "{} [{:?}{}{}] | \"{}\" | {} iters, {} nodes ({} abandoned) | best {} steps, path_value={:.3} | recalled {} | source={}",
            config.rung(),
            config.strategy,
            if config.rollout { "+rollout" } else { "" },
            if config.constrain { "+constrained" } else { "" },
            truncate(&problem.statement, 48),
            config.iterations,
            nodes_expanded,
            self.abandoned_count,
            best_path.len(),
            path_value,
            recalled_total,
            source,
        );

        CoatTrace {
            problem: problem.statement.clone(),
            rung: config.rung().to_string(),
            strategy: config.strategy,
            thought_source: source.to_string(),
            iterations: config.iterations,
            nodes_expanded,
            abandoned: self.abandoned_count,
            branches_committed: committed,
            branches_pruned: pruned,
            recalled_total,
            path_value,
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
    /// The proposed base value.
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
    /// Proposed prior.
    pub prior: f64,
    /// Backpropagated mean value.
    pub value: f64,
    /// Visit count.
    pub visits: u32,
    /// How many associative-memory items were recalled here.
    pub recall_count: usize,
    /// Whether the search backtracked out of this node.
    pub abandoned: bool,
    /// Whether this node lies on the winning reasoning path.
    pub on_best_path: bool,
}

/// The result of a deliberation: the winning reasoning trace + the full tree.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoatTrace {
    /// The problem statement.
    pub problem: String,
    /// Which rung of the ladder ran (CoT / ToT / MCTS / C-MCTS / CoAT).
    pub rung: String,
    /// The tree policy used.
    pub strategy: SearchStrategy,
    /// Where the thoughts came from (`"model"` / `"heuristic"`).
    pub thought_source: String,
    /// The search budget spent.
    pub iterations: u32,
    /// Nodes expanded (excludes the root).
    pub nodes_expanded: usize,
    /// Nodes the search backtracked out of (abandoned).
    pub abandoned: usize,
    /// Branches committed to the M007 tree (the winning path).
    pub branches_committed: usize,
    /// Branches pruned from the M007 tree.
    pub branches_pruned: usize,
    /// Total associative-memory items recalled across the tree (per-thought +
    /// per-node RAG recall).
    pub recalled_total: usize,
    /// The winning path's aggregate value (its weakest link).
    pub path_value: f64,
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

    /// Deterministic source: `k` seeds/node, priors decreasing by index, all five
    /// categories available (so `constrain` has something to gate).
    struct Fixed;
    impl ThoughtSource for Fixed {
        fn expand(
            &mut self,
            _p: &Problem,
            path: &[PathStep],
            _a: &[Recall],
            k: usize,
        ) -> Vec<ThoughtSeed> {
            (0..k)
                .map(|i| ThoughtSeed {
                    category: ThoughtCategory::ALL[(path.len() + i) % 5],
                    text: format!("d{}#{i}", path.len()),
                    prior: 0.9 - 0.1 * i as f64,
                })
                .collect()
        }
        fn label(&self) -> &str {
            "heuristic"
        }
    }

    /// Two equal-prior seeds: "supported" and "bare" — the CoAT-steering probe.
    struct TwoEqual;
    impl ThoughtSource for TwoEqual {
        fn expand(
            &mut self,
            _p: &Problem,
            _path: &[PathStep],
            _a: &[Recall],
            _k: usize,
        ) -> Vec<ThoughtSeed> {
            vec![
                ThoughtSeed {
                    category: ThoughtCategory::Plan,
                    text: "supported".into(),
                    prior: 0.5,
                },
                ThoughtSeed {
                    category: ThoughtCategory::Plan,
                    text: "bare".into(),
                    prior: 0.5,
                },
            ]
        }
    }

    /// A dead-end source: one root move is a trap whose whole subtree is low, the
    /// other is good — exercises backtracking (rollout can't rescue the trap).
    struct DeadEnd;
    impl ThoughtSource for DeadEnd {
        fn expand(
            &mut self,
            _p: &Problem,
            path: &[PathStep],
            _a: &[Recall],
            _k: usize,
        ) -> Vec<ThoughtSeed> {
            if path.is_empty() {
                vec![
                    ThoughtSeed {
                        category: ThoughtCategory::Plan,
                        text: "trap".into(),
                        prior: 0.05,
                    },
                    ThoughtSeed {
                        category: ThoughtCategory::Plan,
                        text: "good".into(),
                        prior: 0.9,
                    },
                ]
            } else if path.iter().any(|s| s.text == "trap") {
                // everything under the trap stays low — a genuine dead end
                vec![ThoughtSeed {
                    category: ThoughtCategory::Code,
                    text: "dead".into(),
                    prior: 0.05,
                }]
            } else {
                vec![ThoughtSeed {
                    category: ThoughtCategory::Code,
                    text: format!("cont{}", path.len()),
                    prior: 0.85,
                }]
            }
        }
    }

    /// Recalls a strong item iff the context text mentions "supported".
    struct KeyedMemory;
    impl AssociativeMemory for KeyedMemory {
        fn recall(&self, ctx: &ThoughtContext, k: usize) -> Vec<Recall> {
            if k > 0 && ctx.text.contains("supported") {
                vec![Recall {
                    id: 1,
                    relevance: 1.0,
                    note: "prior success".into(),
                }]
            } else {
                Vec::new()
            }
        }
    }

    fn problem() -> Problem {
        Problem::new("prove the theorem")
    }

    #[test]
    fn empty_problem_and_bad_config_are_errors() {
        let mut e = CoatEngine::new(Fixed, NoMemory, CoatConfig::coat());
        assert!(matches!(
            e.deliberate(&Problem::new("   ")),
            Err(CoatError::EmptyProblem)
        ));
        let bad = CoatConfig {
            expand_k: 0,
            ..CoatConfig::coat()
        };
        let mut e2 = CoatEngine::new(Fixed, NoMemory, bad);
        assert!(matches!(
            e2.deliberate(&problem()),
            Err(CoatError::InvalidConfig(_))
        ));
    }

    #[test]
    fn cot_preset_is_a_linear_chain() {
        let mut e = CoatEngine::new(Fixed, NoMemory, CoatConfig::cot());
        let t = e.deliberate(&problem()).unwrap();
        assert_eq!(t.rung, "CoT");
        assert_eq!(t.thought_source, "heuristic");
        assert_eq!(
            t.tree.len(),
            t.best_path.len() + 1,
            "CoT must be a single chain"
        );
        assert!(!t.best_path.is_empty());
    }

    #[test]
    fn cot_truncates_an_over_eager_source() {
        // A source that returns 2 seeds for k=1 must NOT break the chain invariant.
        struct Chatty;
        impl ThoughtSource for Chatty {
            fn expand(
                &mut self,
                _p: &Problem,
                _pa: &[PathStep],
                _a: &[Recall],
                _k: usize,
            ) -> Vec<ThoughtSeed> {
                vec![
                    ThoughtSeed {
                        category: ThoughtCategory::Plan,
                        text: "a".into(),
                        prior: 0.8,
                    },
                    ThoughtSeed {
                        category: ThoughtCategory::Code,
                        text: "b".into(),
                        prior: 0.7,
                    },
                ]
            }
        }
        let mut e = CoatEngine::new(Chatty, NoMemory, CoatConfig::cot());
        let t = e.deliberate(&problem()).unwrap();
        // every node has at most one child → tree is a chain
        for n in &t.tree {
            let kids = t.tree.iter().filter(|c| c.parent == Some(n.id)).count();
            assert!(
                kids <= 1,
                "expand_k=1 must be enforced; node {} has {kids} kids",
                n.id
            );
        }
    }

    #[test]
    fn tot_bfs_branches_and_backtracks() {
        let mut e = CoatEngine::new(Fixed, NoMemory, CoatConfig::tot());
        let t = e.deliberate(&problem()).unwrap();
        assert_eq!(t.rung, "ToT");
        assert_eq!(t.strategy, SearchStrategy::Bfs);
        let root_children = t.tree.iter().filter(|n| n.parent == Some(0)).count();
        assert!(root_children > 1, "ToT must branch; got {root_children}");
    }

    #[test]
    fn backtracking_abandons_a_dead_end() {
        // prune_below fires on the low-value "trap"; the search recovers to "good".
        let cfg = CoatConfig {
            prune_below: 0.3,
            ..CoatConfig::mcts()
        };
        let mut e = CoatEngine::new(DeadEnd, NoMemory, cfg);
        let t = e.deliberate(&problem()).unwrap();
        assert!(t.abandoned >= 1, "the trap must be abandoned");
        assert!(t.branches_pruned >= 1, "an abandoned branch must be pruned");
        assert_eq!(
            t.best_path[0].text, "good",
            "the winning path avoids the dead end"
        );
    }

    #[test]
    fn mcts_backprop_accounts_every_iteration_at_the_root() {
        let cfg = CoatConfig::mcts();
        let mut e = CoatEngine::new(Fixed, NoMemory, cfg);
        let t = e.deliberate(&problem()).unwrap();
        assert_eq!(t.rung, "MCTS");
        assert_eq!(
            t.tree[0].visits, cfg.iterations,
            "root visits must equal the budget"
        );
        for n in &t.tree {
            if let Some(p) = n.parent {
                assert!(
                    t.tree[p].visits >= n.visits,
                    "parent must dominate child visits"
                );
            }
        }
    }

    #[test]
    fn rollout_looks_ahead_under_a_tight_budget() {
        // A low-prior first move leads to an excellent terminal; a high-prior first
        // move dead-ends. Under a budget too small for backprop-averaging to have
        // propagated the subtree, only look-ahead (rollout) can see it.
        struct Lookahead;
        impl ThoughtSource for Lookahead {
            fn expand(
                &mut self,
                _p: &Problem,
                path: &[PathStep],
                _a: &[Recall],
                k: usize,
            ) -> Vec<ThoughtSeed> {
                if path.is_empty() {
                    return vec![
                        ThoughtSeed {
                            category: ThoughtCategory::Plan,
                            text: "slow-burn".into(),
                            prior: 0.55,
                        },
                        ThoughtSeed {
                            category: ThoughtCategory::Plan,
                            text: "flashy".into(),
                            prior: 0.85,
                        },
                    ];
                }
                let root = &path[0].text;
                let prior = if root == "slow-burn" { 0.99 } else { 0.10 };
                (0..k)
                    .map(|i| ThoughtSeed {
                        category: ThoughtCategory::Code,
                        text: format!("c{i}"),
                        prior,
                    })
                    .collect()
            }
        }
        // Budget = 2: just enough to expand each root child once, not to drill them,
        // so a node's value is its FIRST-visit estimate — prior alone vs look-ahead.
        let tight = |rollout| CoatConfig {
            iterations: 2,
            rollout,
            prune_below: 0.0,
            ..CoatConfig::mcts()
        };
        // Without rollout: the flashy prior (0.85) wins — no look-ahead.
        let mut greedy = CoatEngine::new(Lookahead, NoMemory, tight(false));
        assert_eq!(
            greedy.deliberate(&problem()).unwrap().best_path[0].text,
            "flashy"
        );
        // With rollout: look-ahead sees slow-burn leads to 0.99 and prefers it.
        let mut looka = CoatEngine::new(Lookahead, NoMemory, tight(true));
        assert_eq!(
            looka.deliberate(&problem()).unwrap().best_path[0].text,
            "slow-burn",
            "rollout must let a strong continuation win before averaging has propagated it"
        );
    }

    #[test]
    fn constrain_changes_the_search() {
        // Fixed offers all 5 categories; constraining must gate some out, yielding
        // a different set of categories in the tree than the unconstrained run.
        let mut unc = CoatEngine::new(
            Fixed,
            NoMemory,
            CoatConfig {
                constrain: false,
                ..CoatConfig::mcts()
            },
        );
        let mut con = CoatEngine::new(
            Fixed,
            NoMemory,
            CoatConfig {
                constrain: true,
                ..CoatConfig::mcts()
            },
        );
        let cats = |t: &CoatTrace| {
            let mut v: Vec<String> = t
                .tree
                .iter()
                .filter_map(|n| n.category.map(|c| format!("{c:?}")))
                .collect();
            v.sort();
            v.dedup();
            v
        };
        let u = unc.deliberate(&problem()).unwrap();
        let c = con.deliberate(&problem()).unwrap();
        assert_eq!(c.rung, "C-MCTS");
        let _ = cats; // (kept for debugging; the load-bearing check is the phase gate)
        // The constrained tree must NEVER hold an out-of-phase category; the
        // unconstrained one does — proving the gate actually changes the search.
        let violates = |t: &CoatTrace| {
            t.tree.iter().any(|n| {
                n.category.is_some_and(|cat| {
                    n.depth >= 1 && !ThoughtCategory::allowed_at(n.depth, 4).contains(&cat)
                })
            })
        };
        assert!(
            violates(&u),
            "unconstrained search should place out-of-phase categories"
        );
        assert!(
            !violates(&c),
            "constrained search must gate every node to its phase"
        );
    }

    #[test]
    fn constrained_action_space_only() {
        let mut e = CoatEngine::new(Fixed, NoMemory, CoatConfig::coat());
        let t = e.deliberate(&problem()).unwrap();
        for n in &t.tree {
            if let Some(c) = n.category {
                assert!(
                    ThoughtCategory::ALL.contains(&c),
                    "action outside the constrained space"
                );
            }
        }
    }

    #[test]
    fn coat_recall_steers_the_winning_path() {
        // Recall ON: the memory-supported thought (equal prior) wins.
        let mut on = CoatEngine::new(TwoEqual, KeyedMemory, CoatConfig::coat());
        let won = on.deliberate(&problem()).unwrap();
        assert_eq!(won.rung, "CoAT");
        assert_eq!(
            won.best_path[0].text, "supported",
            "recall must steer the supported thought onto the winning path"
        );
        assert!(
            won.recalled_total > 0,
            "CoAT must recall associative memory"
        );
        assert!(
            won.best_path[0].value > won.best_path[0].prior,
            "recall must modulate value above the bare prior"
        );

        // Recall OFF: no memory lift; value equals prior.
        let off_cfg = CoatConfig {
            recall_weight: 0.0,
            recall_k: 0,
            ..CoatConfig::coat()
        };
        let mut off = CoatEngine::new(TwoEqual, KeyedMemory, off_cfg);
        let plain = off.deliberate(&problem()).unwrap();
        assert_eq!(plain.recalled_total, 0, "recall_k 0 must pull no memory");
        assert!(
            (plain.best_path[0].value - plain.best_path[0].prior).abs() < 1e-9,
            "without recall, value must equal the prior"
        );
    }

    #[test]
    fn deliberation_is_deterministic() {
        let run = || {
            CoatEngine::new(Fixed, NoMemory, CoatConfig::mcts())
                .deliberate(&problem())
                .unwrap()
                .summary
        };
        assert_eq!(
            run(),
            run(),
            "same inputs must yield the same trace (replayability)"
        );
    }

    #[test]
    fn rung_is_behavioural_not_wishful() {
        assert_eq!(CoatConfig::cot().rung(), "CoT");
        assert_eq!(CoatConfig::tot().rung(), "ToT");
        assert_eq!(CoatConfig::tot_dfs().rung(), "ToT");
        assert_eq!(CoatConfig::mcts().rung(), "MCTS");
        assert_eq!(CoatConfig::cmcts().rung(), "C-MCTS");
        assert_eq!(CoatConfig::coat().rung(), "CoAT");
    }

    #[test]
    fn winning_branch_is_committed_and_traces_serialize() {
        let mut e = CoatEngine::new(Fixed, KeyedMemory, CoatConfig::coat());
        let t = e.deliberate(&problem()).unwrap();
        assert!(
            t.branches_committed >= 1,
            "the winning path must commit branches"
        );
        assert!(
            t.tree.iter().any(|n| n.on_best_path),
            "some node must be on the best path"
        );
        let j = serde_json::to_string(&t).unwrap();
        let back: CoatTrace = serde_json::from_str(&j).unwrap();
        assert_eq!(back.summary, t.summary);
    }

    // --- Config validation edge cases ---

    #[test]
    fn config_validate_rejects_zero_iterations() {
        let cfg = CoatConfig {
            iterations: 0,
            ..CoatConfig::cot()
        };
        assert!(matches!(cfg.validate(), Err(CoatError::InvalidConfig(_))));
    }

    #[test]
    fn config_validate_rejects_zero_max_depth() {
        let cfg = CoatConfig {
            max_depth: 0,
            ..CoatConfig::cot()
        };
        assert!(matches!(cfg.validate(), Err(CoatError::InvalidConfig(_))));
    }

    #[test]
    fn config_validate_accepts_valid() {
        CoatConfig::cot().validate().unwrap();
        CoatConfig::tot().validate().unwrap();
        CoatConfig::mcts().validate().unwrap();
        CoatConfig::coat().validate().unwrap();
    }

    // --- Internal Tree mechanics ---

    #[test]
    fn tree_best_uct_child_skips_abandoned() {
        let mut tree = Tree::new();
        // root → child_a, child_b
        let a = tree.push_child(
            tree.root,
            10,
            Thought {
                category: ThoughtCategory::Plan,
                text: "a".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        let b = tree.push_child(
            tree.root,
            11,
            Thought {
                category: ThoughtCategory::Plan,
                text: "b".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        // give both visits so UCT scores are defined
        tree.backprop(a, 0.6);
        tree.backprop(b, 0.4);
        // abandon child_a; best_uct_child should pick child_b
        tree.abandon(a);
        assert_eq!(
            tree.best_uct_child(tree.root, std::f64::consts::SQRT_2),
            Some(b)
        );
    }

    #[test]
    fn tree_best_uct_child_none_when_all_abandoned() {
        let mut tree = Tree::new();
        let a = tree.push_child(
            tree.root,
            10,
            Thought {
                category: ThoughtCategory::Plan,
                text: "a".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        tree.abandon(a);
        assert_eq!(tree.best_uct_child(tree.root, 1.0), None);
    }

    #[test]
    fn tree_select_frontier_returns_root_when_nothing_expandable() {
        let mut tree = Tree::new();
        // root has no untried seeds and is at depth 0 < max_depth,
        // but it has no children and seeds_generated is false → still expandable
        // so this test needs a node that IS at max_depth.
        let child = tree.push_child(
            tree.root,
            10,
            Thought {
                category: ThoughtCategory::Plan,
                text: "c".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        tree.nodes[child].depth = 4; // simulate max_depth
        tree.nodes[child].seeds_generated = true;
        let sel = tree.select_frontier(4, true);
        assert_eq!(
            sel, tree.root,
            "only root is expandable when child is at max_depth"
        );
    }

    #[test]
    fn tree_select_frontier_bfs_prefers_shallowest() {
        let mut tree = Tree::new();
        // root is fully expanded (no more seeds), so frontier moves to children
        tree.nodes[tree.root].seeds_generated = true;
        let a = tree.push_child(
            tree.root,
            10,
            Thought {
                category: ThoughtCategory::Plan,
                text: "a".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        let _b = tree.push_child(
            tree.root,
            11,
            Thought {
                category: ThoughtCategory::Plan,
                text: "b".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        let _a1 = tree.push_child(
            a,
            12,
            Thought {
                category: ThoughtCategory::Plan,
                text: "a1".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        // all children have untried seeds (seeds_generated=false by default)
        // BFS picks shallowest expandable → depth 1 (a or _b), never depth 2 (_a1)
        let sel = tree.select_frontier(10, true);
        assert_eq!(
            tree.nodes[sel].depth, 1,
            "BFS must pick depth 1 over depth 2"
        );
        assert!(sel == a, "BFS should pick a (depth 1, earliest in arena)");
    }

    #[test]
    fn tree_select_frontier_dfs_prefers_deepest() {
        let mut tree = Tree::new();
        tree.nodes[tree.root].seeds_generated = true;
        let a = tree.push_child(
            tree.root,
            10,
            Thought {
                category: ThoughtCategory::Plan,
                text: "a".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        let _b = tree.push_child(
            tree.root,
            11,
            Thought {
                category: ThoughtCategory::Plan,
                text: "b".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        let a1 = tree.push_child(
            a,
            12,
            Thought {
                category: ThoughtCategory::Plan,
                text: "a1".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        // DFS picks deepest expandable → a1 at depth 2
        let sel = tree.select_frontier(10, false);
        assert_eq!(sel, a1, "DFS should prefer the deepest expandable node");
    }

    #[test]
    fn tree_path_text_with_empty_next() {
        let mut tree = Tree::new();
        let a = tree.push_child(
            tree.root,
            10,
            Thought {
                category: ThoughtCategory::Plan,
                text: "first".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        let _b = tree.push_child(
            a,
            11,
            Thought {
                category: ThoughtCategory::Plan,
                text: "second".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        let txt = tree.path_text(tree.root, "");
        assert_eq!(txt, "", "empty next on root should yield empty text");
        let txt_a = tree.path_text(a, "");
        assert_eq!(
            txt_a, "first",
            "path_text without next excludes the node itself"
        );
    }

    #[test]
    fn tree_settle_empty_best_path_commits_nothing() {
        let mut tree = Tree::new();
        let (committed, pruned) = tree.settle(&[]);
        assert_eq!(committed, 0);
        assert_eq!(pruned, 0);
    }

    #[test]
    fn tree_abandon_increments_count() {
        let mut tree = Tree::new();
        let a = tree.push_child(
            tree.root,
            10,
            Thought {
                category: ThoughtCategory::Plan,
                text: "a".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        assert_eq!(tree.abandoned_count, 0);
        tree.abandon(a);
        assert_eq!(tree.abandoned_count, 1);
        tree.abandon(a); // idempotent
        assert_eq!(tree.abandoned_count, 1);
    }

    #[test]
    fn tree_mean_value_is_zero_for_unvisited() {
        let tree = Tree::new();
        assert_eq!(tree.mean_value(tree.root), 0.0);
    }

    #[test]
    fn tree_backprop_updates_ancestry() {
        let mut tree = Tree::new();
        let a = tree.push_child(
            tree.root,
            10,
            Thought {
                category: ThoughtCategory::Plan,
                text: "a".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        let b = tree.push_child(
            a,
            11,
            Thought {
                category: ThoughtCategory::Plan,
                text: "b".into(),
                prior: 0.5,
                recall: vec![],
            },
        );
        tree.backprop(b, 0.7);
        assert_eq!(tree.nodes[b].visits, 1);
        assert_eq!(tree.nodes[a].visits, 1);
        assert_eq!(tree.nodes[tree.root].visits, 1);
        assert!((tree.nodes[b].value_sum - 0.7).abs() < 1e-9);
        assert!((tree.nodes[a].value_sum - 0.7).abs() < 1e-9);
    }

    // --- Problem and helpers ---

    #[test]
    fn problem_new_has_zero_sketch_bits() {
        let p = Problem::new("test");
        assert_eq!(p.statement, "test");
        assert_eq!(p.topic, 0);
        assert_eq!(p.entity, 0);
    }

    // --- ThoughtCategory boundaries ---

    #[test]
    fn allowed_at_depth_zero_is_early_phase() {
        let cats = ThoughtCategory::allowed_at(0, 4);
        assert!(cats.contains(&ThoughtCategory::Understand));
        assert!(cats.contains(&ThoughtCategory::Plan));
        assert!(!cats.contains(&ThoughtCategory::Code));
    }

    #[test]
    fn allowed_at_last_depth_is_late_phase() {
        let cats = ThoughtCategory::allowed_at(3, 4);
        assert!(cats.contains(&ThoughtCategory::Reflect));
        assert!(cats.contains(&ThoughtCategory::Summarize));
        assert!(!cats.contains(&ThoughtCategory::Code));
    }

    #[test]
    fn allowed_at_saturating_sub_handles_zero_max_depth() {
        let cats = ThoughtCategory::allowed_at(0, 0);
        assert_eq!(cats.len(), 2); // Understand + Plan (the early-phase default)
    }

    // --- Serde roundtrips for individual types ---

    #[test]
    fn thought_seed_serde_roundtrip() {
        let s = ThoughtSeed {
            category: ThoughtCategory::Code,
            text: "hello".into(),
            prior: 0.75,
        };
        let j = serde_json::to_string(&s).unwrap();
        let back: ThoughtSeed = serde_json::from_str(&j).unwrap();
        assert_eq!(s.category, back.category);
        assert_eq!(s.text, back.text);
        assert!((s.prior - back.prior).abs() < 1e-9);
    }

    #[test]
    fn recall_serde_roundtrip() {
        let r = Recall {
            id: 7,
            relevance: 0.95,
            note: "note".into(),
        };
        let j = serde_json::to_string(&r).unwrap();
        let back: Recall = serde_json::from_str(&j).unwrap();
        assert_eq!(r.id, back.id);
        assert!((r.relevance - back.relevance).abs() < 1e-9);
    }

    #[test]
    fn trace_step_serde_roundtrip() {
        let s = TraceStep {
            depth: 2,
            category: ThoughtCategory::Reflect,
            text: "text".into(),
            prior: 0.6,
            value: 0.55,
            visits: 3,
            recall: vec![Recall {
                id: 1,
                relevance: 0.8,
                note: "".into(),
            }],
        };
        let j = serde_json::to_string(&s).unwrap();
        let back: TraceStep = serde_json::from_str(&j).unwrap();
        assert_eq!(s.depth, back.depth);
        assert_eq!(s.category, back.category);
        assert!((s.value - back.value).abs() < 1e-9);
    }

    #[test]
    fn trace_node_serde_roundtrip() {
        let n = TraceNode {
            id: 5,
            branch_id: 99,
            parent: Some(2),
            depth: 3,
            category: Some(ThoughtCategory::Plan),
            text: "plan".into(),
            prior: 0.7,
            value: 0.65,
            visits: 4,
            recall_count: 1,
            abandoned: false,
            on_best_path: true,
        };
        let j = serde_json::to_string(&n).unwrap();
        let back: TraceNode = serde_json::from_str(&j).unwrap();
        assert_eq!(n.id, back.id);
        assert_eq!(n.parent, back.parent);
        assert_eq!(n.on_best_path, back.on_best_path);
    }

    #[test]
    fn search_strategy_serde_roundtrip() {
        for s in [
            SearchStrategy::Uct,
            SearchStrategy::Bfs,
            SearchStrategy::Dfs,
        ] {
            let j = serde_json::to_string(&s).unwrap();
            let back: SearchStrategy = serde_json::from_str(&j).unwrap();
            assert_eq!(s, back);
        }
    }

    #[test]
    fn thought_category_serde_roundtrip() {
        for c in ThoughtCategory::ALL {
            let j = serde_json::to_string(&c).unwrap();
            let back: ThoughtCategory = serde_json::from_str(&j).unwrap();
            assert_eq!(c, back);
        }
    }
}
