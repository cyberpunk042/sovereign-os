# SDD-512 — Token-law serving boundary: CONNECT the engine to live `/v1/messages` generation (M00155)

> Status: active · Mandate: **E11.M512** (control-bits band 500–599)
>
> Cross-link: opens the **M00155 Connect fork** (`backlog/milestones/M010-deterministic-data-plane.md`) over the M00117 engine. The eleventh SDD in the control-bits band, and the **first of the Connect arc** — after the Expose arc (SDD-507 route → SDD-510 osctl verb + profile/env → SDD-511 dashboard) made the engine's decision inspectable and configurable, this makes it **load-bearing on real traffic**.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-23** — operator-directed (*"Fork 2 — CONNECT"*). The Expose arc could inspect and dial the mask but never *applied* it to a served token; CONNECT closes that gap: a `/v1/messages` request may carry a `token_law` constraint that confines every decoded token, on the local model, honoring the no-logit-access boundary.

## Mission

The M00117 engine's per-step decision — the fused allow-mask — was, until now, exposed (SDD-507 route), configurable (SDD-510 layer selection), and visualized (SDD-511 heatmap), but it **never touched a token the daemon actually served**. `complete_with_token_law` in `sovereign-llm` drove the mask over a `DecoderStack`; the production `/v1/messages` path drives a **different** decode stack — `sovereign-quant-model`'s `QuantModel` — whose only constrained entry point applied one *static* `LogitMask` every step. So the engine that the whole control-bits session built could not confine live generation. CONNECT closes the boundary: it teaches the serving model the same **incremental** per-step masking the engine already gives `sovereign-llm`, and wires an optional `token_law` constraint onto the `/v1/messages` request.

## The honesty insight — the no-logit-access boundary

A token-law mask can only bite where the box **holds the logits**. Two obstacles, both honored rather than papered over:

1. **Proxy backends have no logits.** A model resolved to a proxy (`resolve_proxy` → an upstream llama-server / vLLM / sibling gatewayd) generates out-of-process; the serving daemon never sees its logits. A `token_law`-carrying request against a proxy model is therefore **refused (HTTP 422)** — never forwarded and silently served *unconstrained*. Enforcement that can't happen is reported as such, not faked.
2. **The serving model used a different, static-only decode path.** Even where logits *are* accessible (a local `QuantModel`), the daemon had no per-step mask hook on that stack. CONNECT adds one, mirroring `DecoderStack::generate_dynamic_token_law_until` so the quantized serving model is confined by the **same** checkpoint-free `sovereign-token-law-fuse` primitive as `sovereign-llm` — generation and inspection share one mask definition and can never diverge.

Because the mask is a pure function of the law sources + the vocabulary strings (SDD-507's insight), the confinement is exact even on the untrained in-repo fixture — the serving-contract test proves a `[a-z]+` law confines a real loaded model's output with no trained checkpoint behind it.

## Design

### 1. The decode primitive — `QuantModel::generate_dynamic_token_law_until[_with]`

`crates/sovereign-quant-model/src/lib.rs`. Mirrors `DecoderStack`'s dynamic loop: a per-step hook `law_fn(&generated) -> Option<Vec<u64>>` returns the token-law **allow-bitset** (the `FusedMask::mask` wire shape) or `None` to **stop** (grammar complete / no token keeps every plane satisfiable — never sample an all-masked row). Each step `-inf`-masks every disallowed token via `sovereign_token_law_mask::mask_logits` before sampling. The `_with` variant streams each sampled id through an `on_token` sink (what the gateway's chunked output path drives); the plain variant is the non-streaming convenience. `forbid(unsafe_code)` preserved; the crate gains a single new dep (`sovereign-token-law-mask`, the same the decoder-stack already uses).

### 2. The request-side constraint — `ServingTokenLaw`

`crates/sovereign-gatewayd/src/lib.rs`. An optional `token_law` object on the `/v1/messages` body carrying the SAME law planes the fuse route inspects — `schema` / `regex` / `denylist` / `regex_denylist` / `policy_planes` + `mask_layers` (SDD-510 selection) — **minus** `vocab` (serving masks over the model's REAL tokenizer, not a client sample) and `generated` (the decode loop supplies the running prefix). Absent / all-empty ⇒ unconstrained, byte-identical to the pre-CONNECT path. It compiles once against the model's vocab into a `CompiledFuse`; the per-step hook (`token_law_step`) decodes the generated ids to text and fuses at that prefix.

### 3. The serving wiring — `generate_chat_with_sampler_law` + `anthropic_message`

`generate_chat_with_sampler` becomes a thin delegate; the logic moves to `generate_chat_with_sampler_law`, which takes `law: Option<&ServingTokenLaw>` and — when active — swaps the two static `generate_masked_with` decode sites for the dynamic per-step loop. **Every existing safety surface is preserved unchanged**: the input spine (injection / secret / PII screen), the output-side `StreamGuard` (secret/PII redaction, cross-chunk-safe), and the toxicity flag wrap the constrained path identically. `anthropic_message` parses `token_law`, **refuses on a proxy backend (422)**, drives the constrained local decode, and reports which laws bit on the reply (`token_law.enforced` + `layers_active`, parallel to the fuse route).

## What shipped

- **`sovereign-quant-model`** — `generate_dynamic_token_law_until` + `generate_dynamic_token_law_until_with` (+2 unit tests: every step confined to the allowed bitset; `None` stops before an all-masked row); `+ sovereign-token-law-mask` dep.
- **`sovereign-gatewayd`** — `ServingTokenLaw` (Deserialize; `is_unconstrained` / `compile` against the real vocab / `layers_active`); `token_law_step` per-step hook; `generate_chat_with_sampler_law` (the static `generate_chat_with_sampler` now delegates); `anthropic_message` parses + refuses-on-proxy + enforces + reports; `+ sovereign-json-schema-grammar` dep (the `Schema` type). +4 tests (malformed → 400, proxy + law → 422, local model enforces a `[a-z]+` law end-to-end + reports `enforced`/`layers_active`, absent law ⇒ unchanged reply).
- **`tests/lint/test_token_law_serving_contract.py`** — locks the decode primitive on the serving model, the request field + proxy-refuse boundary, the safety-spine preservation, and the honesty framing.

## Non-goals / roadmap

- **Streaming SSE** of the constrained output (the reply is assembled whole today, as the pre-CONNECT path was) and **request-level sampler control** under a law — deferred.
- **Per-step incremental decode** (the hook re-decodes the whole prefix each step — O(n²)); making it incremental is a **Deepen** perf item alongside SIMD.
- With CONNECT shipped, the fork continues with **Deepen** only: the route plane as a real source, a text→token safety projection for the entropy/checksum detectors, and SIMD to hit the 16 KB / AVX-512 target.

## References

- Milestone: `backlog/milestones/M010-deterministic-data-plane.md` (M00155).
- Arc: `docs/sdd/507-token-law-fusion-data-plane.md` (route — establishes the Connect boundary as its own SDD), `docs/sdd/510-token-law-mask-layer-selection.md` (layer selection), `docs/sdd/511-token-law-mask-coverage-heatmap.md` (dashboard).
- Engine: `crates/sovereign-token-law-fuse/src/lib.rs` (`CompiledFuse::fused_mask`); `crates/sovereign-llm/src/lib.rs` (`complete_with_token_law` — the `DecoderStack` twin of this serving path).
- Serving path: `crates/sovereign-gatewayd/src/http.rs` (`anthropic_message`), `crates/sovereign-gatewayd/src/lib.rs` (`generate_chat_with_sampler_law`), `crates/sovereign-quant-model/src/lib.rs` (the decode primitive).
