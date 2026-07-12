# SDD-902 — Compute Plane Phase 2: multi-model gateway (secondary-model hosting)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-12
> Closes findings: operator directive 2026-07-12 (Background Tasks "massive" pass) — *"my rtx4090 jobs I guess or a secondary model in general … lets discuss and plan."* Discussed; approved option (c): in-gateway CPU multi-model **and** GPU serve-process proxy, over one shared compute plane.
> Derived from / extends: SDD-207 (Compute Plane Phase 1 — VRAM-fit placement), the safety spine (input screen + secret/PII redaction on `generate_chat`), SDD-205 (the Anthropic/OpenAI surfaces), the M075 SRP scheduler.
> Band note: numbered **902** in the shared general **900 band** (SDD-100 per-session bands) — the next free slot after a parallel general-session's SDD-900 (real RoPE) + SDD-901 (durable memory). Started life as SDD-900 and collided with that session; renumbered to 902 per the SDD-100 "next free in band" rule. (Earlier increment-1 work briefly mislabelled this the first 900-band SDD.)

## Mission

Host a **secondary model** so background work can run on it while interactive chat
keeps the primary — the second pillar of the "massive" compute-plane. A key
architectural fact shapes it: the gateway's own generator is **CPU** (the Rust
`sovereign-quant-model`); GPU models are **separate serve processes**
(llama-server / vLLM). So "a secondary model" is TWO backend kinds under one
registry, built in three increments over the shared plane.

## Increments

| # | Delivers | Status |
|---|----------|--------|
| **1** | in-gateway CPU multi-model registry | ✓ shipped |
| **2** | GPU serve-process backend (plane-placed llama-server/vLLM) the gateway proxies to | ✓ shipped |
| **3** | routing (model / background hint) + background jobs target the secondary + docs | ✓ this round |

## Increment 1 (shipped)

- The gateway's single `generator: Option<Mutex<Generator>>` becomes a **registry**:
  a primary `Arc<Mutex<Generator>>` + a `RwLock<BTreeMap<id, Arc<Mutex<Generator>>>>`
  of secondaries. Load/unload takes the write lock; a generation clones the
  resident `Arc` and releases the registry, so **different models generate
  concurrently, the same model serialises**, and load/unload never blocks an
  in-flight request.
- `generate_chat(model, prompt, max, on_chunk)` gains a `model` id and **routes**
  via `resolve_model` — a named secondary if it matches, else the primary. All
  four call sites pass it (OpenAI shim, Anthropic non-stream + stream, CoAT
  ModelThoughts). **The safety spine is preserved on every route** (the guards
  live inside `generate_chat`).
- NEW `POST /v1/models/load {id, dir}` + `POST /v1/models/unload {id}` (loopback-
  trust operator actions); `GET /v1/models` now lists the **loaded** residents
  (primary + secondaries), not a static placeholder. A bad dir is an honest
  Anthropic error (422), never a fabricated model.
- The **shared VRAM authority** (SDD-207): jobs-api exposes `POST /plane/place`,
  `/plane/claim`, `/plane/release` — so model residents (increment 2, GPU) and GPU
  jobs claim from ONE VRAM view and never double-book. CPU residents claim no VRAM
  (they run in RAM), so increment 1 needs no plane claim.
- Verified LIVE with a real model: `/v1/models` → load `fast` → `[primary, fast]`
  → a `{"model":"fast"}` message routed to the secondary → unload → `[primary]`.
  53 lib + 4 bin + 14 transport tests; clippy `-D warnings` clean.

## Increment 2 (shipped)

The second backend kind: a **GPU serve-process** the gateway proxies to, so a real
large model runs on the RTX PRO 6000 / VFIO-passed 4090 while the CPU primary keeps
serving interactive chat.

- **Gateway proxy registry.** `ProxyBackend { endpoint, device, vram_gb, dialect }`
  in a `RwLock<BTreeMap<id, _>>`. `register_proxy` / `resolve_proxy(id) → (endpoint,
  dialect)`; `unload_model` removes proxies too; `GET /v1/models` now reports each
  resident's `device` + `vram_gb` (the placed device for a proxy, `cpu` for a
  resident). NEW `POST /v1/models/register {id, endpoint, device?, vram_gb?, dialect?}`
  (loopback-trust).
- **Dialect translation.** llama-server and vLLM speak the **OpenAI**
  `/v1/chat/completions` API, not Anthropic. So an `openai`-dialect backend (the
  default) has the incoming Anthropic `/v1/messages` request translated
  (`anthropic_to_openai_chat`: system + messages + max_tokens/temperature) to the
  OpenAI chat path, and the reply mapped back to the Anthropic message shape
  (`openai_to_anthropic_message`: `content`, `stop_reason` mapping, `usage`). An
  `anthropic`-dialect backend (another sovereign-gatewayd, e.g. on the 4090-VM) is
  forwarded verbatim. Verified by two http tests (a mock Anthropic upstream +
  a mock OpenAI upstream asserting the translated path/body and the mapped reply).
- **Honest streaming gate.** A proxy model requested with `stream:true` returns an
  Anthropic `invalid_request_error` (retry non-streaming) rather than silently
  substituting the primary's stream — proxy streaming is increment 2b.
- **`model-serve` job kind** (jobs-api). A VRAM-needing job, so the compute plane
  PLACES it on a device (or waits) + CLAIMS the VRAM. The runner launches the
  serve-process argv (`meta.command`, no shell), waits for `meta.endpoint` to accept
  connections (health, bounded by `ready_timeout`, degrade-safe if the process dies
  early), registers the gateway proxy on the **actual placed device**, then stays
  running until cancelled. On ANY exit (cancel / crash / clean) it terminates the
  process + unregisters the proxy; run_job's `finally` releases the plane claim — so
  a served model never leaks VRAM or a stale proxy. Verified LIVE (mock gateway +
  mock serve process): place → launch → register on `gpu0` → cancel → unregister →
  the plane frees the claim.

## Increment 3 (shipped)

The routing that makes the two backend kinds usable *as background compute*: work
that shouldn't block interactive chat targets a **secondary** — CPU resident or GPU
proxy — leaving the primary free.

- **The reserved `"background"` alias.** A request for `model: "background"` (the
  Anthropic/OpenAI surfaces, `/v1/coat`, or the OpenAI shim) routes to a *designated*
  background model. `set_background(id)` / `background_id()` / `expand_alias()` on the
  server; NEW `POST /v1/models/background {id}` designates it (loopback-trust),
  seeded from `SOVEREIGN_GATEWAY_BACKGROUND_MODEL`. **Honest fallback:** a designated
  id that is not currently loaded (or none designated) resolves to `None` → the
  primary, never a dead id. `expand_alias` runs at *every* routing entry point (the
  non-streaming message path, the streaming path, and inside `generate_chat` itself),
  so the alias targets the same backend whether it is a CPU secondary or a GPU proxy.
- **Background deliberations run on the secondary.** `GatewayRequest::Coat` (and the
  `/v1/coat` body) carry an optional `model`; `ModelThoughts` expands the reasoning
  through it. The jobs-api deliberation runner sends `model: "background"` by default
  (overridable via `meta.model`), so a background CoAT job runs on the secondary and
  the interactive primary stays responsive — falling back to the primary honestly
  when no background model is designated.
- **Verified:** gateway lib/http tests — the alias designates + falls back when the
  model is unloaded, `POST /v1/models/background` reports `active`, a
  `model:"background"` message reaches the designated proxy end-to-end, `/v1/coat`
  accepts a model hint; a jobs-runtime test asserts the deliberation sends the
  `"background"` alias to a mock gateway. 62 gateway lib+http + 14 jobs-runtime tests;
  clippy `-D warnings` clean.

## Honest gating

- Increment 1 is **CPU-scale**: a secondary is a second in-process `QuantModel`
  (RAM, no GPU VRAM). Increment 2 adds the **GPU** kind (above) — the shared-plane
  authority becomes load-bearing there (a served model and a GPU job claim from ONE
  VRAM view). The **serve-process itself is operator-provided** (`meta.command`): this
  round ships the plane/register/proxy/lifecycle plumbing, not a bundled llama-server
  or vLLM binary — those are installed on the box. Increment 3 (above) adds the
  `"background"` routing + background-job targeting; a one-shot ergonomic
  `model-serve` *submit* verb on osctl is a small follow-up (the job kind + registry
  already exist, so an operator submits it via `jobs submit` today).
- **Streaming to a GPU proxy is not yet supported** (increment 2b) — honestly gated,
  not silently degraded. Streaming the `"background"` alias to a *CPU* secondary
  works; the alias resolving to a *proxy* under `stream:true` hits the same 2b gate.
- Loopback-trust on load/unload/register/background (no cloud auth on a sovereign
  box); the requested `model` id is echoed; quality is model-gated as ever.
