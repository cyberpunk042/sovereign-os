# SDD-712 — server-side agentic tool use: the daemon runs the ReAct loop (Option A) (IMPLEMENTATION)

> Status: draft (implementation — closes the multi-step half of F-2026-088)
> Owner: operator-directed 2026-07-14 (verbatim): *"go with A"* (choosing the model-sharing approach from the
> SDD-711 gated-increment decision).
> Addresses: **F-2026-088** (MED) — the multi-step server-side ReAct loop. With SDD-711 (single-turn,
> client-driven) this **fully closes F-2026-088**.
> Mandate module: **E11.M712**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## What this delivers

SDD-711 made `/v1/chat/completions` return `tool_calls` for the **client** to execute (single-turn). This is
the other half: the daemon runs the ReAct loop **itself** over a set of built-in tools it executes, and
returns only the final answer — the "let the gateway run the loop" the finding asked for.

- **Model-sharing = Option A** (operator-chosen). NEW `crates/sovereign-gatewayd/src/agentic.rs` provides
  `GatewayResponder`: a `sovereign_agent_loop::Responder` that wraps the daemon's existing `GatewayServer`
  and calls its `generate_chat` per step — the **same shared `Arc<Mutex<Generator>>` every request already
  uses, with no per-step model clone** (the opposite of `sovereign-agent-runtime`'s clone-per-call
  `SovereignLlm` path, which was the "prohibitively expensive" note in the finding). Each ReAct step re-sends
  the growing transcript to `generate_chat` exactly as an ordinary request would, so **the SDD-206 safety
  spine screens every step**.
- **The loop** (`run_agent` → `run_loop`) composes `AgentLoop` (step cap + repeat-guard) with a built-in
  `ToolRegistry` and the SDD-711 bridge's `tool_specs_to_prompt` preamble, so the model learns the
  `[[tool:…]]` convention and the available tools, then dispatches each call server-side and feeds the
  observation back until a final answer (or the step cap / repeat-guard fires).
- **Built-in tools are pure** — `upper`/`lower`/`reverse`/`wordcount`/`charcount`, deterministic and
  side-effect-free (no shell, fs, or network). The whole point of keeping slice-1 tools pure is that
  executing them on a root-adjacent daemon needs no sandbox. `builtin_tools()` and `builtin_specs()` are
  kept in lockstep (a test asserts the two lists agree).
- **`/v1/chat/completions` gains an agentic path** — a request with `"sovereign_agentic": true` (a vendor
  field) runs the loop and returns the final answer as an ordinary assistant message (`finish_reason:"stop"`;
  the tool calls happened internally). `max_steps` is request-overridable (clamped 1–16). Absent the field,
  the SDD-711 single-turn / plain-streaming paths run unchanged.

## Sovereignty posture (why two gates)

A root-adjacent daemon that **autonomously executes tools** is a capability worth gating, independent of how
safe today's specific tools are:

1. **Per-request opt-in** — `sovereign_agentic: true`. Off by omission.
2. **Env kill-switch** — `SOVEREIGN_GATEWAY_AGENTIC=1`, **default OFF**. Even an opted-in request does nothing
   unless an operator has consciously enabled the capability on the daemon (documented in the daemon USAGE).

Matches the project's "installed-off" doctrine: the runtime ships present but dormant until an operator turns
it on. The bounded step cap + repeat-guard keep a runaway loop from pinning the shared generator.

## Verification

- `cargo test -p sovereign-gatewayd` — 71 + 13 + 18 passed (incl. 6 new `agentic` tests: built-in tools are
  pure + dispatch, specs↔registry lockstep, loop dispatches-a-tool-then-answers, answers-directly,
  step-cap-reported, env-gate parse). The loop wiring is exercised with a `ScriptedResponder` (no model).
- `cargo fmt --all --check` (CI-exact) + `cargo clippy -p sovereign-gatewayd --all-targets` — clean.
- gatewayd now also consumes `sovereign-agent-loop` + `sovereign-tool-dispatch` (previously demo-only) —
  reachability improves; crate-graph contract stays green; no new crate (count unchanged).
- Full `tests/` + 5 profiles + ruff green.
- **Not model-verified** (no weights in CI): a real model driving the loop to a tool-using answer end-to-end
  through `/v1/chat/completions` — the loop wiring + shaping are proven with the scripted responder; the
  per-step generation is the unchanged `generate_chat`.

## Non-goals (follow-ups)

- A **curated production tool catalog** — calc (a real safe arithmetic parser), time, and local retrieval
  (the daemon already has `sovereign-retrieval` / cortex recall). Slice-1 keeps tools pure-and-trivial to
  isolate the runtime.
- **Streaming the loop's intermediate steps** (per-step deltas) — slice-1 returns only the final answer.
- **Anthropic `/v1/messages` agentic parity** — the bridge has `outcome_to_anthropic`; wiring it is separate.
- Any tool with a **side effect** (shell/fs/network) — those require the sandbox + capability-gating story
  (selfdef territory), a deliberate future decision, not folded in here.
