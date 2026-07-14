# Reasoning & operability

> The box does not just answer — it can *deliberate* (a real search over its own
> memory), it lets you *observe and operate* the intelligence layer, and it runs
> long work in the *background*. This chapter is the operator guide to those
> surfaces. Built by the deliberate-reasoning directive (CoT→ToT→MCTS→C-MCTS→CoAT),
> SDD-204 (Background Tasks), and SDD-112 (the Code Console).

## Deliberate reasoning — the CoAT ladder

A reactive chatbot answers in one pass. A deliberate problem-solver **searches**.
sovereign-os implements the whole progression as one engine
(`crates/sovereign-coat`), and — the sovereign thesis — each rung maps onto a real
execution primitive the box already had:

| Rung | What it adds | Maps onto |
|---|---|---|
| **CoT** — Chain of Thought | one linear reasoning chain | a single `Cortex::act` path |
| **ToT** — Tree of Thoughts | branch, evaluate, **backtrack** (BFS/DFS) | `sovereign-branch-tree` + `sovereign-value-plane` |
| **MCTS** | UCT select → expand → **rollout** → backprop | the tree + the value-plane critic |
| **C-MCTS** | a **constrained** action space (understand/plan/reflect/code/summarize) | phase-gated categories |
| **CoAT** ⭐ | recall associative memory that **steers** which path wins | `Cortex::deliberate` over the **Memory-OS** |

It is one engine parameterized — the earlier rungs are presets of the last. Run it
over the gateway:

```bash
curl -s http://127.0.0.1:8787/v1/coat \
  -H 'content-type: application/json' \
  -d '{"problem":"optimize the SRP scheduler admission rule","rung":"coat","topic":15}' \
  | python3 -c 'import sys,json;t=json.load(sys.stdin)["trace"];print(t["summary"]);[print(" ",s["category"],"v=%.2f"%s["value"],s["text"]) for s in t["best_path"]]'
```

`rung` ∈ `cot | tot | dfs | mcts | cmcts | coat` (default `coat`). It is **read-only**:
it decides without learning, so a deliberation never pollutes memory. CoAT recalls
the box's own two-brain memory at every step; whether the recall *visibly* steers a
run depends on how much the live Memory-OS holds.

> Honest gating: the search *harness* (selection, backtracking, the memory wiring)
> is real and tested; useful *thoughts* need a capable instruct model. On the tiny
> base model the structure runs but the thoughts are weak.

## The Brain observatory (`/brain/`)

The cockpit panel that makes the intelligence layer concrete — open
`http://127.0.0.1:8100/brain/` (or its own port). It shows:

- **Both memories** decoded: the Rust cortex store (the 8 CoALA types, trust/value,
  ground-truth episodes) beside the Python Memory-OS operational store.
- **Live gateway telemetry** + the never-cloud-spill tripwire.
- A **routing probe** — send a real 7-axis request and watch which role/device/verdict
  the brain reaches (a read-only preview; it never pollutes memory).
- A **CoAT deliberation** card — pick a rung, deliberate, and watch the winning
  reasoning chain with each step's value, recall, and memory-lift.
- The **daemon/crate map** behind it all.

Everything in the panel is read-only over the gateway's read surfaces plus a
non-mutating decide/chat — `forget`/`clear` stay CLI-gated.

## Background Tasks — run work off the request path

Long-running work — a background deliberation, a model eval, a secondary-model
load, a GPU job, or a job mirrored from the RTX-4090 OcuLink eGPU sandbox (when
VFIO-opted-in) — runs in the **jobs runtime** (`jobs-api`, loopback `:8142`) and
shows up in the Code Console.

```bash
sovereign-osctl jobs submit deliberation --problem "prove the routing invariant"
sovereign-osctl jobs list
sovereign-osctl jobs status <id>
sovereign-osctl jobs cancel <id>
sovereign-osctl jobs submit eval -- python3 scripts/models/eval.py …
```

- `list`/`status` are read-only; **`submit`/`cancel` are actions** — from the
  cockpit they are copied `sovereign-osctl jobs …` verbs routed through the one
  sanctioned execute daemon (`control-exec-api`), never a web mutation (R10212).
- The registry **persists** (survives a restart); an orphaned job is marked failed
  on restart, never a zombie.
- When the **RTX 4090 OcuLink eGPU** is opted into the VFIO sandbox (a guest VM;
  host-resident by default per SDD-993 / D-022), the host can't see its GPU jobs
  directly. `scripts/jobs/vm-bridge-guest.py` runs inside the guest,
  probes its `nvidia-smi`, and reports back to the host runtime — so those jobs
  appear too. (Wiring the guest→host channel, `SOVEREIGN_JOBS_HOST`, is a
  deployment step; until then the agent is inert and says so.)

## The Code Console — where it all comes together

`http://127.0.0.1:8100/code-console/` is the claude.ai/code-style panel over the
box's own local LM. It unifies everything above in one three-pane surface:

- **Sessions** (left) — live M057 OS task-sessions.
- **Conversation** (center) — chat with the local LM over loopback. When the AI
  needs to **ask** (a clarifying question) or **plan**, it renders an interactive
  card you click — not raw text.
- **Plan** (right) — a live pane that mirrors the **active plan** from the
  conversation (steps + approvals) and renders a clicked background deliberation's
  **CoAT reasoning trace**. Toggle **◱ Tasks** to split it 50/50 with the live
  **Background Tasks** list.

Read-only by construction: the one mutating call is the loopback chat; every real
action is a copied signed CLI verb.

## Interaction doctrine (how the AI behaves)

Three standing directives govern how the sovereign AI thinks and acts — the same
frameworks these panels render:

- **QCFA + interactive clarification** — align on intent before acting: ask 1–4
  decision-shaped questions as clickable cards, not a vague "what do you want?".
- **Plan Mode + User Approval** — propose a plan and hold execution until you
  Approve / Reject / Approve-with-changes / Approve-and-remember; permission modes
  (manual/auto/bypass) with an Auto-mode classifier that blocks destructive ops.
- **Deliberate reasoning** — the CoAT ladder above.

## See also

- Design: `docs/sdd/204-background-tasks.md`, `docs/sdd/112-code-console.md`,
  and the directives in `docs/standing-directives/` (deliberate-reasoning,
  plan-mode-user-approval, qcfa-interactive-clarification).
- Point your editor at the box: [Use the box as your AI backend](./ai-backend.md).
- The cockpit at large: [The cockpit — dashboards + control surface](./ops/cockpit.md).
