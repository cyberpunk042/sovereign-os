# SDD-720 — permission modes wired into the agent loop (DESIGN)

> Status: **scoping — design for operator review; pending Q-720-A..B** (implementation track of SDD-718)
> Owner: operator-supervised; agent-authored (design pass, no code)
> Owner directive 2026-07-16 (verbatim): *"how is my vLLM or llama.cpp going to be in the various modes such as
> Auto and permission-mode bypassPermissions and Plan and Edit allowed and such … I don't want it to always be
> a single answer for a single question … set the Auto mode."*
> Number band: **700–799** per SDD-100.
> Mandate module: **E11.M720**.
> Stage: **design**. Scopes wiring the classifier into the loop; does not implement.

## The gap

The permission modes (`manual` / `auto` / `bypass`, `config/permission-modes.yaml`) and the safety classifier
(`permission_classifier.py`, SDD-954) **exist**, but they gate the **cockpit controls** (control-exec-api) —
**not** the agent loop's tool dispatch. So the gateway's agentic loop (SDD-712) currently runs its built-in
tools unconditionally; "Auto mode auto-runs the safe tools and blocks the destructive ones **inside the
iteration**" is not wired. This SDD closes that — it makes a mode an actual property of how the loop executes,
which is what turns "a single answer" into "a self-driving agent you can trust in Auto".

## Design

### 1. A gate between "model proposed a tool" and "the loop runs it"

Today: `AgentLoop` parses `[[tool:NAME|ARGS]]` → dispatches via the `ToolRegistry`. New: a **permission gate**
sits in that seam. For each proposed tool call the loop asks the classifier (reused as a library — same
patterns as the cockpit path, single source of truth):

```
verdict = classify(tool_name, args, mode = active_permission_mode())
match verdict:
  allow           → run the tool, feed the observation back
  block           → do NOT run; feed "[blocked: <reason>]" back so the model re-plans (Auto + destructive)
  confirm         → in an attended session, surface the approval verbs (approve / reject /
                    approve-with-changes / approve-and-remember); in an unattended loop, treat as block-and-note
```

- **`auto`** → routine tools run free, destructive blocked, unknown confirmed (or block-and-note when
  unattended) — the operator's "let it operate, classifier guards the cliff", now *in the loop*.
- **`manual`** → every mutating tool pauses for an approval verb; reads run.
- **`bypass`** → gate is a pass-through (everything runs) — the `--dangerously-skip-permissions` analogue, for
  trusted unattended runs.

### 2. Tool risk classification (extends the classifier to tool calls)

The classifier today reads shell command strings. Tool calls need a risk tag too. Two-part:
- **Built-in gateway tools** (calc/time/recall — SDD-713) are **pure/read-only → `routine`** by construction.
- **Side-effecting tools** (shell / fs / network — deferred to selfdef's sandbox) carry a declared
  `risk: routine|destructive` in their spec; unknown/undeclared → `unknown` → confirm (fail-safe, per SDD-954).

So in Auto mode the current pure toolset runs unattended safely, and the moment a real side-effecting tool is
added it lands in `unknown`/`destructive` and is gated — the safe default holds as the tool surface grows.

### 3. "Edit allowed" / "Auto Edit On" as a preset

The operator's "Edit allowed" / "Auto Edit On" = a **named preset over the same machinery**: `auto` mode with
file-edit tools tagged `routine` (auto-run) while shell/network stay `destructive`/`unknown`. Presets are just
mode + a per-tool-class allow map, so the operator can say "auto-edit on" and get edits-run-free without opening
shell/network. (The preset table is a config extension of `permission-modes.yaml`, not new code paths.)

### 4. Where the mode lives (shared with SDD-718 / 719)

`active_permission_mode()` reads `SOVEREIGN_OS_PERMISSION_MODE` (env) falling back to the shared
`agent-state.json` (SDD-719), so `/mode auto` and `/goal` share one state both SDD-718 tiers + the cockpit read.
Switching mode mid-goal is allowed and takes effect on the next iteration (the operator's Plan↔Auto "alternance").

## Verification (when implemented)

- Unit (no model): each mode × {routine, unknown, destructive} tool → the right allow/block/confirm verdict; a
  destructive tool is refused mid-loop and the block observation is fed back; bypass runs everything; the
  built-in pure tools classify `routine`. Reuses SDD-712's scripted-responder loop harness.
- Not model-verified in CI: a real model proposing a real destructive tool and being stopped live.

## Open questions (operator)

- **Q-720-A** — In an **unattended Auto loop**, is `confirm` (the unknown middle) treated as **block-and-note**
  (safe; the model re-plans) or does it **pause the loop** for later operator approval? Recommendation:
  **block-and-note** in unattended, **pause** only when a human is attached — keeps the loop moving.
- **Q-720-B** — Ship the "Auto Edit On" preset in this slice, or just the three base modes first? Recommendation:
  **base three modes first**; the edit preset lands once a real file-edit tool exists (today's tools are pure).

## Non-goals

- The real enforcement boundary (sandbox / capability-gating around side-effecting tools) — **selfdef**; this is
  the UX/workflow gate on top of it (SDD-954's honest framing: "spared the operator a mistake", not "stopped an
  attacker").
- Adding side-effecting tools themselves (shell/fs/network) — a separate, deliberate decision.
- The goal-lock loop mechanics — SDD-719.
