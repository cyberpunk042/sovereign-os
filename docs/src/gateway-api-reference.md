# Gateway API reference (`/v1`)

The sovereign gateway daemon (`crates/sovereign-gatewayd`) serves an HTTP API on
**`127.0.0.1:8787`** (loopback-forced). This page is the per-route reference
(source of truth: `crates/sovereign-gatewayd/src/http.rs` — the module doc-comment
+ the route match table). Authored for SDD-983 (closes audit finding F-2026-064);
the Anthropic-compatibility work consumes this page.

> **Transport note**: the gateway currently has no auth / TLS / socket timeouts
> (audit finding F-2026-082) — it is safe only because it is loopback-bound. Do
> not expose it off-host without the F-2026-082 hardening.

## The deliberation ladder

The sovereign routing/reasoning surface is a ladder from cheap-and-raw to
deep-and-deliberate. Every rung returns a typed `kind`:

| Rung | Route | Method | Mutates? | Returns | Purpose |
|---|---|---|---|---|---|
| raw decision | `/v1/infer` (alias `/mcp`) | POST | runs the decision | `{"kind":"decision", …}` | The raw engine alias — the routing DECISION. |
| simplified | `/v1/simple` | POST | runs the decision | `{"kind":"decision", …}` | Simplified request shape (axes + quality) → decision. |
| dry-run | `/v1/explain` | POST | **read-only** | `{"kind":"explanation", …}` | Dry-run rationale for `/v1/infer` — decides nothing. |
| dry-run | `/v1/simple-explain` | POST | **read-only** | `{"kind":"decision", …}` | Read-only sibling of `/v1/simple`: computes + returns the full decision without acting. |
| best-of-N | `/v1/deliberate` | POST | **read-only** | `{"kind":"deliberation", …}` | Cortex best-of-N — generates N candidates, scores by reward, returns the best. |
| CoAT ladder | `/v1/coat` | POST | **read-only** | `{"kind":"coat", …}` | The deepest rung: the `sovereign-coat` engine (CoT→ToT→MCTS→C-MCTS→CoAT), recalling from the daemon's real Cortex memory; each trace honestly flags `thought_source: heuristic\|model`. |

**`/v1/deliberate` vs `/v1/coat`** (the naming overlap F-2026-064 flagged):
`/v1/deliberate` is a flat **best-of-N** over independent candidates; `/v1/coat`
is a **tree/ladder search** (MCTS-family) with associative recall. Use
`deliberate` for "pick the best of a few tries", `coat` for "reason through it".

> **Caveat (F-2026-063 / F-2026-090)**: model-backed `/v1/coat` currently runs
> synchronously on the gateway request thread and holds the generation mutex for
> the duration (bounded ≤12 iterations, rollout off). The planned fix routes it
> through the background-jobs runtime (`scripts/operator/jobs_store.py`) so
> deliberation never blocks the request path.

## Anthropic-compatible surface (SDD-205)

Lets external agents (VS Code / Claude Code) drive the box's own local model.

| Route | Method | Returns | Notes |
|---|---|---|---|
| `/v1/messages` | POST | `{"type":"message", …}` | Anthropic Messages API. `stream:true` → SSE (served in `main.rs`). |
| `/v1/models` | GET | `{"data":[…]}` | Anthropic models list (the local model). |
| `/v1/messages/count_tokens` | POST | `{"input_tokens":N}` | Token count (best-effort). |

## Model management

| Route | Method | Purpose |
|---|---|---|
| `/v1/models/load` | POST | Load a model (precision-selectable per SDD-953). |
| `/v1/models/unload` | POST | Unload the active model. |
| `/v1/models/register` | POST | Register a model definition. |
| `/v1/models/background` | POST | Background model operation. |

## Observability / admin

| Route | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness. |
| `/manifest` | GET | The runtime manifest. |
| `/admin/ledger` | GET | The mutation/audit ledger. |
| `/metrics` | GET | Prometheus-style metrics. |
| `/v1/events` | GET | Event stream (SSE). |

## Related runtime APIs (separate daemons)

The intelligence-layer sidecar daemons (loopback), documented in
[handoff 008](../handoff/008-july-intelligence-layer-arc.md):

- **Brain observatory** — `scripts/operator/brain-api.py` on **:8141** (read-only
  cognitive-state observatory).
- **Background jobs** — `scripts/operator/jobs-api.py` on **:8142** (durable job
  registry + the `/v1/coat` deliberation runner).

## Cross-references

- `crates/sovereign-gatewayd/src/http.rs` — the authoritative route table
- `docs/handoff/008-july-intelligence-layer-arc.md` — the arc these routes belong to
- `crates/sovereign-coat/` — the CoAT engine behind `/v1/coat`
- SDD-205 (Anthropic Messages API) · SDD-953 (configurable model load) · SDD-957 (serve-vs-gatewayd architecture)
