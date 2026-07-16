# SDD-719 — `/goal`: a locked goal the Auto loop pursues (IMPLEMENTATION — slice 1)

> Status: **active — slice 1 shipped** (goal state + verbs + loop-until-goal core; Q-719 defaults taken, below)
> Owner: operator-supervised; agent-authored (design pass, no code)
> Owner directive 2026-07-16 (verbatim): *"I would also like the '/ goal' command to be able to set a goal and
> have it stay locked in a bit like it does in Auto mode after a plan."* + *"I don't want to be blocker for
> nothing or have to continuously have to tell it to continue or to re-state what I want."*
> Number band: **700–799** per SDD-100.
> Mandate module: **E11.M719**.
> Stage: **design**. Scopes the goal-lock + loop-until-goal; does not implement.

## What the operator wants

Set a goal once → it **stays locked** → the agent **iterates toward it on its own** (Auto mode), across many
model calls and tool steps, **without being told "continue"** and without re-stating the intent — exactly the
"Auto mode after a plan" feel. This is the missing runtime **goal state** + the **loop-until-goal** control on
top of the existing agent loop (SDD-712, which today loops until a final answer or the step cap, with no
persistent objective).

## Design

### 1. The goal state (durable, shared)

A small root-owned JSON at **`/etc/sovereign-os/agent-state.json`** (env-overridable
`SOVEREIGN_OS_AGENT_STATE`), read by *both* SDD-718 tiers + the cockpit (mirrored read-only):

```json
{
  "goal": {
    "text": "<the locked objective, operator-verbatim>",
    "status": "active | paused | done | abandoned",
    "plan": ["step 1", "step 2", "..."],        // optional, from a Plan-mode approval
    "set_at": "<unix>", "set_by": "operator",
    "iterations": 0, "last_progress": "<one-line>"
  }
}
```

Operator-verbatim `text` is **sacrosanct** — the loop may summarize progress, never the goal.

### 2. `/goal` verbs (CLI + cockpit)

`sovereign-osctl goal …` (and a cockpit surface):

| Verb | Effect |
|---|---|
| `set "<text>"` | lock a new goal (status `active`); optionally seeded from a Plan-mode approved plan |
| `show` | current goal + status + iterations + last progress |
| `pause` / `resume` | stop / restart the loop pursuing it (goal stays locked) |
| `done` / `abandon` | close the goal (loop stops; history kept) |
| `progress "<line>"` | append a progress note (the loop writes these each iteration) |

### 3. Loop-until-goal (the control on top of the agent loop)

The existing `AgentLoop` (SDD-712) gains a **goal-completion check** as an additional stop condition, and a
driver wrapper re-arms it while the goal is `active`:

```
while goal.status == "active" and iterations < max_iterations:
    result = agent_loop.run(prompt = goal.text + recent_progress + tool_observations)
    write progress(result.summary); iterations += 1
    if goal_satisfied(result):        # model self-reports done, OR a done-criterion tool passes
        goal.status = "done"; break
    if no_progress_for(N):            # repeat-guard at the GOAL level (not just the step level)
        surface "stuck on <goal>: <reason>"; goal.status = "paused"; break
```

Two guards keep it from running away or spinning: the **max-iterations ceiling** (like the step-cap, but at the
goal level) and a **goal-level no-progress guard** (distinct from SDD-712's per-step repeat-guard) that pauses +
surfaces when N iterations produce no new progress — so "keep going until done" never becomes "burn the box".

### 4. Interaction with modes (SDD-720) and Plan

- In **Auto** mode the loop runs tools per the classifier (SDD-720) without prompting → true unattended pursuit.
- In **manual** mode the loop still pursues the goal but pauses at each mutation for approval — "locked goal,
  supervised execution".
- **Plan → lock**: a Plan-mode approval can seed `goal.plan` + `goal.text`, so "approve the plan" *is* "lock the
  goal and go" — the operator's "like Auto mode after a plan".

## Verification (when implemented)

- Unit: goal state read/write/verbs; loop-until-goal stops on done / max-iters / no-progress; goal text never
  mutated. (All testable without a model — a scripted responder drives the loop, per SDD-712's pattern.)
- Not model-verified in CI (no weights): a real model pursuing a real multi-step goal end-to-end.

## Open questions (operator)

- **Q-719-A** — `max_iterations` default + the no-progress `N` before auto-pause? Recommendation: 50 / 3.
- **Q-719-B** — One goal at a time (a single lock) or a small goal stack? Recommendation: **one active goal**
  (matches "stay locked"); a stack is a later extension.
- **Q-719-C** — Should a completed/paused goal notify the operator (cockpit toast / log), and how loud?
  Recommendation: cockpit status + a log line; no push in slice 1.

## Implementation (slice 1 — shipped 2026-07-16, operator "ready")

Q-719 defaults taken (operator "start with the recommended defaults"): **one active goal** (Q-719-B), **max
50 iterations / 3 no-progress → pause** (Q-719-A), cockpit status + log (no push) for completion (Q-719-C).

- **`scripts/inference/goal-ctl.py`** — the durable goal state + verbs (`set`/`show`/`pause`/`resume`/`done`/
  `abandon`/`progress`) at `/etc/sovereign-os/agent-state.json` (atomic `os.replace`; stdlib-only; non-root →
  rc 2). The goal `text` is written only by `set`; `progress` bumps iterations + records `last_progress`,
  **never rewrites text** (sacrosanct-verbatim — a test enforces it).
- **`scripts/inference/goal-driver.py`** — `run_loop`: the SDD-718 **self-loop tier** realized as an
  orchestrator over the existing gateway agentic endpoint (SDD-712, `sovereign_agentic:true`). While the goal is
  `active` it re-arms one agentic request per iteration (goal + recent progress fed back), stopping on
  **done** (the model ends a reply with `[[GOAL_DONE]]`) / **max-iters** / **no-progress** — the two guards are
  goal-level (distinct from SDD-712's per-step repeat-guard), and both **pause** (not abandon) the goal. The
  per-iteration call is a `Responder` — real = HTTP to the daemon; **tests inject a scripted responder** (no
  model, no network — proven without weights).
- **`sovereign-osctl goal <verb>`** — the CLI surface (`run` → goal-driver; the rest → goal-ctl).
- **`tests/lint/test_goal_lock_contract.py`** — verbs; goal-text-sacrosanct; loop stops on done/max-iters/
  no-progress and pauses the goal; no-op without an active goal.

**Not model-verified** (no weights in CI): a real model driving a real goal to `[[GOAL_DONE]]`. The state, the
verbs, the loop control + guards, and the prompt shaping are proven with the scripted responder.

**Deferred to slice 2** (still open): the mode-gating *inside* the per-iteration tools (SDD-720); the OpenClaw
tier pursuing the same goal (SDD-718); a systemd unit / cockpit surface to run the driver unattended; Plan-mode
seeding the goal from an approved plan (the `plan` field exists; the Plan→lock wiring is the follow-up).

## Non-goals

- Multi-goal scheduling / priorities.
- Auto-decomposing a goal into sub-goals for sub-agents (that's the SDD-718 OpenClaw tier + a follow-up).
- The mode-gating mechanics themselves — those are SDD-720.
