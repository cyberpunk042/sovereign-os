# Standing directive — Deliberate reasoning: CoT → ToT → MCTS → C-MCTS → CoAT (2026-07-12)

> **Why this file exists.** The operator's durable instruction (verbatim,
> sacrosanct):
>
> > "now we need to support: These concepts represent the evolution of
> > Artificial Intelligence and Large Language Models (LLMs) from reactive
> > chatbots into deliberate problem-solvers. They form a progression of
> > techniques designed to help AI 'think slow,' evaluate alternatives, and
> > self-correct. 1. Chain of Thought (CoT) … 2. Tree of Thoughts (ToT) …
> > 3. Monte Carlo Tree Search (MCTS) … 4. C-MCTS (Constrained Monte Carlo Tree
> > Search) … 5. CoAT (Chain-of-Associated-Thoughts) … combines MCTS with an
> > associative memory mechanism … allows the AI to dynamically pull in external
> > information and recall related knowledge while deliberating."
>
> Third in the reasoning/interaction trilogy after
> [QCFA + interactive-clarification](./2026-07-11-qcfa-interactive-clarification.md)
> (*align on intent before acting*) and
> [Plan Mode + User Approval](./2026-07-11-plan-mode-user-approval.md)
> (*review the plan before executing*). This one governs **how the AI thinks
> while it acts** — deliberate, search-based reasoning instead of a single
> reactive forward pass. **One framework, two homes** — the local sovereign AI
> (cortex + gateway + cockpit) and external agents/operators.

## The doctrine — think slow, evaluate alternatives, self-correct

A reactive chatbot answers in one linear pass; a deliberate problem-solver
**searches**. The progression below is a ladder of search sophistication, and —
this is the sovereign-os thesis — **the box already implements the whole ladder
as first-class execution primitives.** The reasoning techniques are not
metaphors bolted on; they map one-to-one onto crates that predate this directive.

## The progression, mapped onto sovereign-os primitives

| # | Technique | What it adds | sovereign-os primitive |
|---|-----------|--------------|-------------------------|
| 1 | **CoT** — Chain of Thought | one linear step-by-step trace; "show your work". Drawback: an early error compounds with no backtrack. | a single `Cortex::act` reasoning path; the **CoT scaffold** (below) |
| 2 | **ToT** — Tree of Thoughts | generalizes CoT to a *tree*: generate multiple thoughts, evaluate each state, look ahead, **backtrack** from dead ends (BFS/DFS). | [`sovereign-branch-tree`](../../crates/sovereign-branch-tree) (`fork`/`commit`/`prune`/`lineage` — pruning cascades) + [`sovereign-value-plane`](../../crates/sovereign-value-plane) (score each state) |
| 3 | **MCTS** — Monte Carlo Tree Search | iterative tree search in four phases — **Selection** (explore vs exploit), **Expansion**, **Simulation** (playout), **Backpropagation**. | `branch-tree` (the tree) + `value-plane`'s **"MCTS + PRM"** critic (evaluation) + backprop over `lineage()` |
| 4 | **C-MCTS** — Constrained MCTS | restricts the action space to a small set of categories (understand / plan / reflect / code / summary) so the search is manageable and less hallucination-prone. | the cortex's **bounded `NextAction`** set + the M048 constrained routing categories — the box never emits arbitrary actions |
| 5 | **CoAT** — Chain-of-Associated-Thoughts ⭐ | MCTS **plus an associative-memory mechanism**: each deliberation step can dynamically pull external info and recall related knowledge, mimicking how humans connect ideas mid-thought. | `Cortex::deliberate` already forks branches "against the same routed/placed/**recalled** context" where "**recalled memory modulates the reward**" — the **Memory-OS `retrieve()`** IS the associative memory. **This is the sovereign centerpiece.** |

### Why CoAT is the sovereign-native centerpiece

Generic MCTS scores nodes from the model's fixed parameters alone. CoAT lets the
search **recall related knowledge while deliberating** — and sovereign-os is the
one system that already *has* that associative memory: the two-brain Memory-OS
(the cortex `HotMeta`/`GroundTruth` store + the Python Memory-OS) you browse in
the `/brain/` observatory. `Cortex::deliberate` already recalls evidence
(`recalled: Vec<Hit>`, per-item + embedding-cosine reward boost) and lets it
modulate every branch's value. So CoAT is not a generic import here — it is the
reasoning framework the box was *built* for. The gap today is only that
`deliberate` is **single-round** best-of-N; CoAT is that primitive run
**iteratively**, growing the tree across rounds with UCT selection + backprop and
a fresh associative recall at each expansion. That iterative engine is
[`sovereign-coat`](../../crates/sovereign-coat) (see the engine round).

## The two homes

- **Local sovereign AI (the engine).** CoT is a single cortex path. ToT/MCTS/CoAT
  are the `sovereign-coat` engine composing `branch-tree` + `value-plane` +
  `Cortex::deliberate`'s memory recall into an iterative search, exposed on the
  gateway (`/v1/coat`), surfaced in the `/brain/` observatory (watch the tree
  grow, see the recalled memory per node). The deep tree search is **model-gated**
  — it needs a capable instruct model to generate + score thoughts; on the tiny
  base model it runs but the thoughts are weak. The **search harness itself is
  deterministic and always correct** — selection, expansion, backprop, and the
  memory-recall wiring are exercised without the model.
- **External agents / operators (the posture).** This file + the **CoT scaffold**
  (`config/prompts/qcfa-system-prompt.md`) are the operating manual: for a hard
  problem, don't answer in one pass — reason step by step, and when the problem
  branches, explore multiple approaches, evaluate them, and backtrack from dead
  ends rather than committing to the first path.

## The honest gating

| Technique | Available now | Needs a capable model |
|-----------|---------------|-----------------------|
| CoT | ✅ scaffold posture, works today | quality scales with the model |
| ToT / MCTS / C-MCTS | search harness real + tested; thought-generation | ✅ for useful thoughts |
| CoAT | harness + Memory-OS recall wiring real + tested | ✅ for useful thoughts |

The search **structure** ships and is tested deterministically today; the
**thought content** improves with the model — same honest gating as Plan Mode's
agent-runtime half.

## References

- Scaffold (CoT posture): `config/prompts/qcfa-system-prompt.md`.
- Primitives: `crates/sovereign-branch-tree`, `crates/sovereign-value-plane`,
  `crates/sovereign-cortex` (`deliberate`, `retrieve`), `crates/sovereign-coat`.
- Gateway: `POST /v1/deliberate` (single-round), `POST /v1/coat` (iterative).
- Observatory: the `/brain/` panel + `scripts/operator/brain-api.py`.
- Siblings: [`2026-07-11-qcfa-interactive-clarification.md`](./2026-07-11-qcfa-interactive-clarification.md),
  [`2026-07-11-plan-mode-user-approval.md`](./2026-07-11-plan-mode-user-approval.md).
