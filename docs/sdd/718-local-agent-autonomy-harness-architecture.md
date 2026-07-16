# SDD-718 — local-agent autonomy: harness architecture (both-tiered) (DESIGN)

> Status: **scoping — architecture decision recorded; sub-decisions pending** (Q-718-A..C below)
> Owner: operator-supervised; agent-authored (design pass, no code)
> Owner directive 2026-07-16 (verbatim): *"I want it like Claude Opus and able to set the Auto mode and just
> in general have it work multiple query and launch sub-agents and continue and do real round, real iterations
> … I want one properly able to think and delegate."* Decision (AskUserQuestion): harness = **both, tiered**;
> **scope both first as SDDs**.
> Number band: **700–799** per SDD-100.
> Mandate module: **E11.M718**.
> Stage: **design**. This SDD scopes + decides the architecture; it does not implement. SDD-719 (/goal lock) and
> SDD-720 (modes-in-loop) are the two implementation tracks that hang off it.

## The framing correction this SDD records (model vs harness)

A local model (vLLM / llama.cpp behind the gateway) is a **token generator** — it answers one prompt. The
behaviors the operator wants — **Auto / Plan / Bypass modes, multi-query iteration, "continue" without being
told, sub-agent delegation, a locked goal** — are **harness** behaviors, not model behaviors. "Claude Opus in
Auto mode running sub-agents" is Anthropic's *model* driven by Claude Code's *harness*. The sovereign analogue:
the local model (SDD-711/712/714/715/717) driven by a harness pointed at the gateway's OpenAI-compatible
endpoint instead of Anthropic's API.

So autonomy is a **harness** build, and the model work (Slices 1–3) is the substrate it runs on.

## What already exists (do not rebuild)

| Piece | Where | State |
|---|---|---|
| Permission modes `manual` / `auto` / `bypass` + approval verbs | `config/permission-modes.yaml` (operator's 2026-07-11 verbatim directive) | Defined; drives cockpit controls |
| Auto-mode safety classifier (routine/unknown/destructive → allow/confirm/block) | `scripts/operator/lib/permission_classifier.py` (SDD-954) | Built; UX heuristic, **not** wired into the agent loop |
| ReAct agent loop (step-cap, repeat-guard) | `crates/sovereign-agent-loop` | Built |
| Server-side agentic loop over the local model | `crates/sovereign-gatewayd/src/agentic.rs` (SDD-712), gated by `SOVEREIGN_GATEWAY_AGENTIC` | Built; single-agent; pure + calc/time/recall tools (SDD-713) |
| OpenClaw harness (OpenArms fork) | integrated by SDD-705 (`sovereign-openclaw.service`, installed-off) | Present |

**The three gaps** (why it doesn't yet feel like Opus): (1) the classifier isn't the gate *inside* the loop's
tool dispatch → SDD-720; (2) there's no persistent goal the loop pursues across iterations → SDD-719; (3)
sub-agent delegation lives in the harness, not the gateway's single-agent loop → this SDD's tiering.

## The decision: both-tiered harness

Two drivers, chosen by task shape — the operator picked **both, tiered**:

| Tier | Driver | Runs the loop | Sub-agents | Use for |
|---|---|---|---|---|
| **Self-loop** | `gatewayd` agentic path (SDD-712) | Inside the daemon; `sovereign_agentic:true` | No (single-agent) | Simple self-driving: "keep going on this until done" over the built-in tool registry. No external process. |
| **Full harness** | **OpenClaw** (SDD-705), `base_url` → the local gateway | In OpenClaw's agent-run | **Yes** (spawns sub-agent sessions) | The Opus-like experience: modes + Plan + sub-agent delegation + rich tool surface. |

Both consume the **same** local model through the **same** gateway endpoint, and both read the **same**
`config/permission-modes.yaml` + `/goal` state (SDD-719) — so switching tiers doesn't change the mode or the
goal. The tiers are not exclusive: the self-loop handles cheap in-daemon iteration; OpenClaw handles anything
needing sub-agents or the full mode UX.

```
            operator ──/goal, /mode──►  shared state (permission-modes.yaml + active-goal)
                                              │                    │
                 ┌────────────────────────────┘                    └───────────────┐
                 ▼                                                                  ▼
        gatewayd self-loop (SDD-712)                                   OpenClaw harness (SDD-705)
         AgentLoop + built-in tools                                    agent-run + sub-agents + tools
                 │                                                                  │
                 └──────────────► gateway /v1/chat/completions (local model) ◄──────┘
                                  (vLLM / llama.cpp — Slices 1–3)
```

## Why both, not one

- **Self-loop alone** can't delegate (single-agent) — fails the operator's "launch sub-agents / delegate".
- **OpenClaw alone** is a heavier external process for what is sometimes just "iterate this in the daemon";
  the self-loop is the zero-dependency path for simple autonomy and is already built.
- Tiering lets the *same goal + same mode* be pursued by whichever driver fits, which is the operator's
  "alternance" instinct at the harness layer.

## Stages (this arc)

1. **design** (this SDD + 719 + 720) — the architecture + the two tracks, operator-reviewed.
2. **scaffold** — shared `active-goal` state file + a mode-resolver both drivers read; `/goal` + `/mode` CLI stubs.
3. **implement** — wire the classifier into the loop (720); the goal-lock loop-until-goal (719); OpenClaw
   `base_url` → gateway + shared-state read.
4. **test** — Auto-mode loop runs a multi-step task to a locked goal without re-prompting; destructive tool is
   blocked mid-loop; OpenClaw spawns a sub-agent against the local model.

## Open questions (operator)

- **Q-718-A** — Default tier when the operator just says "go on X": self-loop (cheap) or OpenClaw (full)?
  Recommendation: **self-loop by default, escalate to OpenClaw when the task names delegation / sub-agents**.
- **Q-718-B** — Where does the shared `active-goal` + mode state live so *both* drivers + the cockpit read it?
  Recommendation: `/etc/sovereign-os/agent-state.json` (root-owned, like the dspark/permission state), mirrored
  read-only to the cockpit. (Detail in SDD-719.)
- **Q-718-C** — Does the OpenClaw tier reuse the gateway's built-in tools (calc/time/recall) or its own tool
  surface? Recommendation: **OpenClaw brings its own richer surface; the gateway tools stay the self-loop's set**
  — they converge later, not in slice 1.

## Non-goals

- Fleet / multi-box orchestration (OpenFleet territory).
- The real security boundary (sandbox + capability-gating) — selfdef; the modes here are UX + workflow, per
  SDD-954's honest framing.
- Any implementation — this SDD is the decision + map; 719 + 720 carry the designs; code lands only after
  operator review of the arc.
