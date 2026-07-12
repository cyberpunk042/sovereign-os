# SDD-956 — gateway API reference: route-parity contract + the routing-vs-generation "two brains" clarification

> Status: draft
> Owner: operator-directed ("continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-12
> Number band: **950–999 (general / audit session)** per SDD-100.
> Closes findings: **F-2026-094**. From `docs/review/phase-1/99-findings-ledger.md`.
> Derived from / extends: `docs/src/ai-backend.md` (the existing API reference) + the counts-as-contract discipline of SDD-952/955.

## Mission

F-2026-094 asked for two things: (1) a **single gateway API reference** that delineates every `/v1/*` surface, and (2) a clarification of the **routing-vs-generation split** (the `/v1/deliberate` vs `/v1/coat` naming overlap and the "disjoint brains" — cortex routes, the safetensors path generates).

Part (1) already exists: **`docs/src/ai-backend.md`** enumerates all 19 served routes with request/response shapes (the Anthropic Messages API, the OpenAI shim, the model registry, and the sovereign routing/reasoning surfaces). The real gap is that nothing kept it **honest against the code** — the pre-existing `test_ai_backend_docs_contract.py` only checks that a static hand-listed subset of endpoints appears in the doc, so a route added/renamed/removed in the daemon could silently desync the reference (exactly the living-doc drift the audit warns about, theme #2).

This SDD closes that with a **route-parity contract**, and records the routing-vs-generation clarification as the audit's answer to the "two brains" concern.

## What this SDD builds

### 1. `tests/lint/test_gateway_route_parity.py` — the enforced contract

Extracts the **served route set** directly from the daemon dispatch (`sovereign-gatewayd/src/http.rs` `match (method, route)` block + the streaming intercepts in `main.rs`, excluding each file's `#[cfg(test)]` module) and the **documented route set** from `ai-backend.md`, and asserts they are **equal both directions**:

- a route served but not documented → CI fails (no undocumented surface);
- a route documented but not served → CI fails (no fictional / renamed / removed route).

Extraction is by route **string literal**, not Rust match-arm parsing, so it is robust to formatting and only reacts to a route genuinely being added/renamed/removed. On the current tree both sets are **19 and identical** — the contract passes today and locks the reference to the code. Same self-maintaining discipline as SDD-952 (`context.md` counts) and SDD-955 (island register).

This SDD does **not** edit `ai-backend.md` — it is complete and accurate, and is actively maintained by the compute-plane workstream. The lint only guarantees it stays that way.

### 2. The routing-vs-generation split — the "two brains" (the finding's clarification)

The gateway fronts **two disjoint subsystems** on one loopback door:

| "Brain" | Crate path | Job | Routes | Produces |
|---|---|---|---|---|
| **Generation** | `safetensors-loader → quant-model → quant-llm → stream-decode → logit-mask → hf-tokenizer` | run the local model, emit tokens | `POST /v1/messages` (Anthropic), `POST /v1/chat/completions` (OpenAI shim) | **text** |
| **Routing / decision** | `sovereign-cortex` (7-axis router + value plane + memory) | decide *where/how* a request should run; deliberate; recall | `POST /v1/infer` (alias `/mcp`), `/v1/simple`, `/v1/simple-explain`, `/v1/explain`, `/v1/deliberate`, `/v1/coat` | **a decision / rationale / trace — never text** |

The key clarification the finding asked for: **cortex generates no text.** The routing brain answers "route / device / verdict / quality" (`{kind:"decision"|"explanation"|"deliberation"|"coat-trace"}`); the generation brain answers with model tokens. A request that wants an answer hits `/v1/messages`; a request that wants a *decision about* an answer hits the cortex surfaces. The model registry routes (`/v1/models[/load|unload|register|background]`) select *which* generation model a `/v1/messages` call targets — they are generation-side control, not a third brain.

### 3. `/v1/deliberate` vs `/v1/coat` — the naming overlap resolved

Both are read-only cortex reasoning surfaces, but they are different shapes:

- **`/v1/deliberate`** — *best-of-N*: score `candidates[]` for a `request` at a `tier` and return the pick (`{kind:"deliberation"}`). A single-layer selection.
- **`/v1/coat`** — *CoAT ladder*: run a Chain-of-Associated-Thoughts search over a `problem` at a `rung` and return the reasoning trace (`{kind:"coat-trace", trace:{best_path, …}}`). A multi-step deliberation.

They are not duplicates: deliberate picks among given candidates; coat generates and explores a reasoning path. The finding's optional "fold best-of-N into the ladder narrative" is left as a future consolidation (a design choice with runtime cost, not a doc fix) — recorded here, not done.

## Verification

- `python3 -m pytest tests/lint/test_gateway_route_parity.py` — 4 passed: source + doc exist; every served route documented; every documented route served; the two reasoning surfaces present. Current parity is **19 served == 19 documented**.
- `ruff check tests/lint/test_gateway_route_parity.py` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Rewriting or restructuring `ai-backend.md`** — it is the reference; this SDD enforces it, it does not duplicate it. (Duplicating it into a second "API reference" would create the exact two-sources-of-truth drift the audit warns against.)
- **Folding best-of-N into the CoAT ladder** — a runtime consolidation, not a doc change; recorded as a future option.
- **Method-level parity** (GET vs POST per route) — the contract is at the path level; method correctness is already covered by the daemon's 405 tests.

## Safety invariants

Read-only lint + docs only — no daemon code, no route change, no gateway edit. The lint reads source + doc text; it cannot alter behavior. Purely additive. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/src/ai-backend.md` — the gateway API reference (now enforced by the parity contract)
- `tests/lint/test_gateway_route_parity.py` — the enforcing lint
- `tests/lint/test_ai_backend_docs_contract.py` — the pre-existing partial (static) endpoint check this complements
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-094 (source)
- SDD-952 (counts-as-contract) · SDD-955 (island register) — the same self-maintaining-contract pattern
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
