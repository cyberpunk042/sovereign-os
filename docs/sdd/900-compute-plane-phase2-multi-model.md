# SDD-900 — Compute Plane Phase 2: multi-model gateway (secondary-model hosting)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-12
> Closes findings: operator directive 2026-07-12 (Background Tasks "massive" pass) — *"my rtx4090 jobs I guess or a secondary model in general … lets discuss and plan."* Discussed; approved option (c): in-gateway CPU multi-model **and** GPU serve-process proxy, over one shared compute plane.
> Derived from / extends: SDD-207 (Compute Plane Phase 1 — VRAM-fit placement), the safety spine (input screen + secret/PII redaction on `generate_chat`), SDD-205 (the Anthropic/OpenAI surfaces), the M075 SRP scheduler.
> Band note: this is the first SDD in this (unassigned) session's **900 band** (SDD-100 per-session bands) — earlier work mistakenly used the 200 band and collided.

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
| **1** | in-gateway CPU multi-model registry | ✓ this round |
| 2 | GPU serve-process backend (plane-placed llama-server/vLLM) the gateway proxies to | planned |
| 3 | routing (model / background hint) + background jobs target the secondary + full docs | planned |

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

## Honest gating

- Increment 1 is **CPU-scale**: a secondary is a second in-process `QuantModel`
  (RAM, no GPU VRAM). Big GPU models are increment 2 — a `model-serve` job that
  launches llama-server/vLLM on a **plane-placed** device (claims VRAM), which the
  gateway registers as a **proxy backend** and forwards to. That is where the
  shared-plane authority becomes load-bearing.
- Loopback-trust on load/unload (no cloud auth on a sovereign box); the requested
  `model` id is echoed; quality is model-gated as ever.
