# SDD-713 — production agent tool catalog: calc + time + recall (IMPLEMENTATION)

> Status: draft (implementation — production-catalog follow-up on F-2026-088)
> Owner: operator-directed 2026-07-14 (verbatim): *"go. lets do everything, another big round. take your time to
> do this right"* — authorizing the "curated production tool catalog" follow-up named as a non-goal in SDD-712.
> Addresses: **F-2026-088** (MED) — closed by SDD-711 + SDD-712; this lands the production tool catalog those
> two SDDs deferred to slice-2. No finding re-opens.
> Mandate module: **E11.M713**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## What this delivers

SDD-712 gave the daemon a server-side ReAct loop over a set of **pure-and-trivial** built-in tools
(`upper`/`lower`/`reverse`/`wordcount`/`charcount`) deliberately chosen so executing them on a root-adjacent
daemon needs no sandbox. This adds the **first three production tools** the finding actually wanted — still
side-effect-free, still no sandbox required:

- **`calc`** — real arithmetic, not string-twiddling. Reuses `sovereign-calc::eval` (the pure, dependency-free
  shunting-yard evaluator that until now was a demo-only island). `[[tool:calc|2*(3+4)]]` → `14`; a parse
  error returns `[calc error: …]` as the observation so the model can recover rather than the loop aborting.
  Whole-number results render as integers (`14`, not `14.0`) via a small `fmt_calc` helper.
- **`time`** — the current wall-clock as `"<n> (unix seconds, UTC)"` from `SystemTime::now()`. The first use of
  real wall-clock inside gatewayd (everything else is deterministic); flagged here because it makes this one
  tool non-reproducible by design — a clock read is the point.
- **`recall`** — local memory retrieval. The daemon already runs one process-wide learning `Cortex` (M016);
  `recall` lets the agent query it. `[[tool:recall|blackwell gpu bringup]]` → the best-available text of the
  top memories whose text-sketch overlaps the query, or `[no relevant memory]` when the store has nothing.
  This is the "local retrieval (the daemon already has cortex recall)" the SDD-712 non-goals named.

`recall` is **only registered when a cortex handle is supplied** — the pure tools and `calc`/`time` need no
daemon state, so the loop is exercisable in tests without one; `builtin_specs(include_recall)` mirrors that.
A test asserts the spec list and the live registry names agree, so the model's advertised toolset never drifts
from what the daemon will actually dispatch.

## How `recall` reaches the daemon's memory (the one structural change)

`ToolRegistry` handlers are `'static` closures — they cannot borrow `&GatewayServer`. So `recall` needs an
**owned** handle to the shared cortex. The minimal correct path:

- `GatewayServer.cortex` becomes `Arc<Mutex<Cortex>>` (was `Mutex<Cortex>`); a new `cortex_handle()` returns an
  `Arc::clone`. Existing `&self.cortex` uses deref-coerce unchanged, so the CoAT recall path and every other
  cortex reader are untouched.
- A new **string-level** API on the cortex crate keeps the sketch logic where it belongs:
  `Cortex::recall_text(query, now, half_life, k) -> Vec<String>` — a private `text_sketch` (FNV-1a over
  alphanumeric tokens) keys `recall(topic=bits, entity=bits.rotate_left(29), …)`, then resolves each hit to its
  ground-truth best-available text. `agentic.rs` calls that one method; it does not reimplement sketching.

The `recall` closure captures the `Arc<Mutex<Cortex>>`, and on a poisoned lock returns
`[recall unavailable: memory lock poisoned]` rather than panicking — consistent with the daemon's graceful
lock-poison posture (SDD-992).

## Sovereignty posture (unchanged)

The two gates from SDD-712 still stand and still guard this catalog: per-request `sovereign_agentic: true`
(off by omission) **and** the `SOVEREIGN_GATEWAY_AGENTIC=1` env kill-switch (**default OFF**). All three new
tools remain side-effect-free — no shell, fs, or network — so the "installed-off + no sandbox needed" doctrine
holds. Anything with a side effect stays deferred to selfdef's sandbox + capability-gating story, exactly as
SDD-712 said.

## Verification

- `cargo test -p sovereign-gatewayd` — 71 (lib, incl. **9** `agentic` tests: was 6, +`calc` evaluates+errors,
  +`time` returns unix seconds, +`recall` present-only-with-a-cortex-and-queries-memory) + 16 (main) + 18
  (transports). Loop wiring stays proven with a scripted responder (no model).
- `cargo test -p sovereign-cortex` — 60 + 2 new (`recall_text` returns ground-truth for a matching query;
  empty on an empty store).
- `cargo fmt --all --check` (CI-exact) + `cargo clippy -p sovereign-gatewayd -p sovereign-cortex --all-targets`
  — clean.
- gatewayd now also consumes `sovereign-calc` (previously a demo-only island) — reachability improves;
  crate-graph contract stays green; `docs/architecture/crate-inventory.md` regenerated; **no new crate** (count
  unchanged at 718).
- Full `tests/` + 5 profiles + ruff green.
- **Not model-verified** (no weights in CI): a real model choosing `calc`/`time`/`recall` end-to-end. The
  dispatch, error-shaping, cortex query, and spec↔registry lockstep are proven directly; per-step generation is
  the unchanged `generate_chat`.

## Non-goals (follow-ups)

- **Streaming the loop's intermediate steps** — still returns only the final answer (SDD-712 non-goal, intact).
- **Anthropic `/v1/messages` agentic parity** — the bridge has `outcome_to_anthropic`; wiring it is separate.
- **A retrieval-quality pass on `recall`** — it uses the cortex's existing sketch+decay recall as-is; rerank /
  dedup / diversify (the SDD-977/978 chat-RAG pipeline) is a deliberate later decision, not folded in.
- Any tool with a **side effect** (shell/fs/network) — sandbox + capability-gating territory (selfdef), a
  future decision, not folded in here.
