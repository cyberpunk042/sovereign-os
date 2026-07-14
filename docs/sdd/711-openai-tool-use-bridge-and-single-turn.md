# SDD-711 — OpenAI/Anthropic tool use: the schema bridge + single-turn `/v1/chat/completions` (IMPLEMENTATION + arc design)

> Status: draft (implementation of the first slice + design of the arc)
> Owner: operator-directed 2026-07-14 (verbatim): *"next! yes of course we want tools, good catch, so many
> things come from tools."*
> Addresses: **F-2026-088** (MED) — the ReAct agent + tools are built and tested but unwired from the
> daemon; `/v1/chat/completions` can't use tools; the tool syntax is a bespoke `[[tool:NAME|ARGS]]`, not
> OpenAI/Anthropic `tool_use`. **Single-turn client-driven tool use CLOSED here; multi-step agentic loop scoped as a gated increment.**
> Mandate module: **E11.M711**.
> Number band: **700–799** per SDD-100.
> Stage: **implement** (first slice) + **design** (the arc).

## What the map found (behaving FROM the project)

A full read of the Rust workspace (crates/) established the real shape, correcting the ledger's one-liner:

- **The daemon has its own model stack.** `sovereign-gatewayd` generates through a shared
  `Arc<Mutex<Generator>>` (`QuantModel` + `HfBpeTokenizer`), locked once per request and mutated in place —
  **completely separate** from the `SovereignLlm` stack that `sovereign-agent-loop` / `sovereign-agent-runtime`
  are built on (which clones the whole model every call). `sovereign-gatewayd` has **zero** dependency on
  agent-loop / agent-runtime / tool-dispatch.
- **The handlers are schema-blind.** `/v1/chat/completions` and `/v1/messages` parse requests as raw
  `serde_json::Value`, flatten `messages[].content` to a string prompt, call `generate_chat` directly, and
  hard-code `finish_reason:"stop"`. Neither reads a `tools` field; no typed request/response structs exist.
- **Two tool dialects, never bridged.** `sovereign-tool-dispatch` speaks the bespoke `[[tool:NAME|ARGS]]`
  convention; a separate, well-tested, **zero-consumer** crate `sovereign-tool-call-parse` already parses the
  OpenAI/Anthropic `tool_calls` / `{name,arguments}` JSON shapes. Nothing connected them.
- **OpenAI tool use is client-driven.** In the OpenAI/Anthropic protocols the SERVER returns `tool_calls` /
  `tool_use`; the CLIENT executes the tool and sends back a `tool` / `tool_result` message. So single-turn
  tool use needs **no** server-side ReAct loop and **no** model-sharing change — only: accept `tools`, prompt
  the model, detect a call, return it. The server-side multi-step agentic loop is a *separate, larger*
  feature (the one the "fresh model clone each call" note and the F-2026-089 coupling flag).

## What this SDD delivers (the first slice — landed)

1. **NEW crate `sovereign-tool-bridge`** — the model-free, side-effect-free schema adapter between the two
   dialects, unit-tested without a model (18 tests):
   - `openai_tools_to_specs` (parse request `tools[]`, both OpenAI-nested and Anthropic-flat/`input_schema`),
     `tool_specs_to_prompt` (teach the bracket convention),
   - `json_call_to_dispatch` / `dispatch_call_to_json` / `render_bracket` / `extract_call` (both-dialect
     extraction) / `extract_advertised_call` (extract only a call to a tool the caller actually offered — so a
     model can't make the server emit a bogus `tool_calls` for an unadvertised name),
   - `tool_call_to_openai` (client-driven `tool_calls[]` entry) + `outcome_to_openai` / `outcome_to_anthropic`
     (the server-runs-the-tool response blocks, for the future agentic increment).
2. **`sovereign-gatewayd` `/v1/chat/completions` is now tool-aware** — when the request carries a non-empty
   `tools` array, a tool-aware path (`tool_aware_chat_completion` + the pure, model-free `shape_tool_completion`)
   prepends the tool-descriptions preamble, generates the reply **buffered** (a call is only detectable once
   the whole reply is in hand), then returns a `tool_calls` response with `finish_reason:"tool_calls"` (the
   client executes the tool) or plain content otherwise. **Absent/empty `tools` → the existing token-streaming
   path runs byte-identically.** It reuses `generate_chat` (the SDD-206 **safety spine stays intact**); no
   multi-step loop, no model-sharing change. 3 gatewayd tests cover the shaping (advertised call → tool_calls;
   plain output → content; unadvertised call → treated as text).

This is the reviewed-in-isolation-then-wired pattern (cf. MS003 SDD-989→990): the bridge is a clean primitive
AND it is genuinely consumed in the same PR (the workspace forbids orphan non-cockpit crates — F-2026-001/graph
contract), so it never becomes another island.

## The arc design — the multi-step agentic increment (gated, NOT built here)

Server-side multi-step tool use (the daemon runs the ReAct loop itself) is deferred with its decisions surfaced:

- **D1 — model-sharing.** The loop needs to generate ≥2 times per turn sharing one model instance. Two paths:
  **(A, recommended)** give the loop a `Responder` that wraps the daemon's existing `Arc<Mutex<Generator>>`
  (`QuantModel::generate_masked_with`, in place — no clone, reuses the daemon pattern); **(B)** port the daemon
  onto `SovereignLlm` (clone-per-call) — materially bigger, touches the tokenizer type + every `generate_chat`
  caller. Recommendation A; needs an operator/architect nod because it touches the daemon request path.
- **D2 — streaming contract.** OpenAI streams `delta.tool_calls[].function.arguments` incrementally; the loop
  returns whole replies per step. First increment: **non-streamed tool_calls** (as this slice does); streaming
  deltas later.
- **D3 — Anthropic `/v1/messages` parity.** `outcome_to_anthropic` + `tool_use`/`tool_result` framing is
  built in the bridge but not yet wired into the Anthropic handler.
- **Adjacency — F-2026-089** (serve-vs-gatewayd) lands in the same `generate_chat` region; sequence to avoid collision.

## Non-goals

- The multi-step server-side ReAct loop, streaming tool-call deltas, and `/v1/messages` tool parity (the
  gated increment above).
- Typed request/response structs replacing the raw-`Value` handlers (a larger, orthogonal refactor).

## Verification

- `cargo test -p sovereign-tool-bridge` — 18 passed; `cargo test -p sovereign-gatewayd` — 71 + 7 + 18 passed
  (incl. the 3 new `shape_tool_completion` tests).
- `cargo fmt --all --check` (CI-exact) clean; `cargo clippy -p sovereign-tool-bridge -p sovereign-gatewayd
  --all-targets` clean.
- Crate registers refreshed: `crate-inventory.md` regenerated, crate count 717→718, graph contract green (the
  bridge is consumed by gatewayd — not an orphan), workspace-hygiene baseline green (the new crate inherits
  `[lints] workspace = true`, per SDD-710).
- Full `tests/` + 5 profiles + ruff green.
- **Not verified on a real model** (no weights in CI): the actual model emitting a `[[tool:…]]` call end-to-end
  through `/v1/chat/completions` — the *shaping* is proven by the model-free tests; the generation path is the
  unchanged `generate_chat`.

## Incidental: a pre-existing doc-coverage test flipped to its milestone

Running the full suite surfaced a failure **not caused by this change**:
`test_doc_coverage_contract.py::test_gaps_verb_high_threshold_exits_2` asserted "at threshold 6, gaps MUST
exit 2 (no module has all 6 doc-kinds)". The `sovereign-osctl` man-page arc (PR #177, just merged to main)
added the `docs/man/` stubs that were the last-missing `man-page` kind, so all 9 tracked modules reached 6/6
and gaps now exits 0. Verified pre-existing by reverting every SDD-711 doc change and re-running gaps (still
count 0). The test is updated to record the fully-documented state as the milestone baseline (a new
under-documented module re-introduces a gap and flips it back), so the contract still guards coverage.
