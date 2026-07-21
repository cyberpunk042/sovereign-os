# SDD-507 — The token-law fusion data plane: expose the engine's decision as a checkpoint-free surface

> Status: active · Mandate: **E11.M507** (control-bits band 500–599)
>
> Cross-link: opens the **M00155 operator surface** (`backlog/milestones/M010-deterministic-data-plane.md`, F00792/F00797/F00798) over the M00117 engine that SDD-500…506 built. The eighth SDD in the control-bits band, and the first of the **Expose** arc (see § Roadmap).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-21** — operator-directed (*"what the progress and what next? I want vision"* → chose all of Expose · Connect · Deepen). The token-law engine was complete but **sealed** — `complete_with_token_law` had zero callers outside its own tests. This ships the first real way to drive it: a data-plane route that returns the **fused allow-mask** for a given prefix, backed by a new transformer-free crate.

## Mission

SDD-500…506 built the five-plane M00117 engine and folded it into
`sovereign-llm::complete_with_token_law`. But the only way to reach it was to
*run the transformer* — no operator surface, no HTTP path, no inspection. The
M00155 milestone specifies exactly that surface (F00792 mask-fusion engine,
F00795 `--token-law-mask-layers` CLI, F00797 `POST /v1/data-plane/token-law/fuse`,
F00798 metric). This SDD opens it, starting with the engine core and the API.

The insight that makes the surface **honest**: the engine's per-step **decision**
— the fused allow-mask — is a pure function of the layer *sources* (a schema, a
regex, a denylist) and the **vocabulary strings**. It never touches embeddings,
attention, or logits. So the mask is *exact regardless of which checkpoint is
loaded, or whether any is* — a trained model, the untrained in-repo fixture
(`crates/sovereign-gatewayd/src/model_fixture.rs`), and "no model, just a
tokenizer" all produce the identical mask. **You can inspect and drive the law
engine without a trained model behind it.** That is what the data plane exposes.

## The crux — separate the decision from the generation

`complete_with_token_law` interleaves two concerns: (1) *fuse* the active laws at
the current prefix into an allow-mask, and (2) *sample* the transformer's logits
under that mask. Only (2) needs the model. This SDD extracts (1) into a crate
that depends on the constraint sources **only** — no `sovereign-decoder-stack`,
no transformer-block — so a light consumer (the gateway daemon, `/metrics`, a
future CLI) can compute masks without linking a decode stack.

Because generation and inspection now call the **same** `fused_mask`, they can
never diverge: the mask the data plane returns is bit-for-bit the mask the
decoder applies.

## What was real vs the gap (grounded 2026-07-21)

- **Real — the engine.** `TokenLawSpec` + `complete_with_token_law` (`crates/sovereign-llm/src/lib.rs`), composing grammar/regex/denylist/negated-regex/policy per step via the real `token_law_combine` kernel.
- **Real — a raw-bitset inspection route.** `POST /v1/token-law/allowed-mask` (`crates/sovereign-gatewayd/src/http.rs`) AND-combines *pre-packed* `Vec<u64>` bitsets (F00623). It takes bitsets, not sources — the caller must already know each plane's mask.
- **The gap.** No way to fuse **named layers derived from real sources** (schema/regex/denylist) at a prefix; no data-plane route; and the fusion logic was welded inside the decode loop, reachable only with a transformer linked.

## Design

### 1. `sovereign-token-law-fuse` — the checkpoint-free fusion crate (NEW)

Deps: the constraint sources only (`sovereign-token-law-mask`,
`sovereign-json-schema-grammar`, `sovereign-token-grammar-mask`,
`sovereign-regex-constrain`, `sovereign-token-law-deny`) — **no transformer**.
`forbid(unsafe_code)`.

- `FuseLayers<'a>` — the borrowed named laws (mirrors `TokenLawSpec`'s fields).
- `CompiledFuse::compile(&FuseLayers, vocab) -> Result<_, FuseError>` — parse each
  source once against a fixed vocab.
- `CompiledFuse::fused_mask(generated) -> FusedMask { mask, allowed, per_layer, stop }`
  — the per-prefix decision: collect each active layer's allow-list, AND-compose
  through `TokenLawPlanes::combine_with_dynamics`. `allowed` counts only real
  vocab bits (the identity mask sets padding bits past the vocab — the mask is
  returned verbatim, the count is vocab-bounded). `stop` = a completed grammar
  (`eos`), a layer that permits nothing, or an empty intersection.
- `FuseRequest` — an owned, `Deserialize` wire shape (`{ schema?, regex?,
  denylist?, regex_denylist?, policy_planes?, generated?, vocab }`) + `fuse()` +
  `layers_active()`, so an HTTP route or CLI deserializes and fuses in two lines.

### 2. `sovereign-llm` consumes it (no behaviour change)

`complete_with_token_law` now builds a `CompiledFuse` once from its `TokenLawSpec`
and calls `fused_mask` per step (`stop → None`, else the mask). The five pairwise
`complete_*_with_laws` methods and every SDD-505/506 parity test are **unchanged**
— generation and the data plane share one mask definition.

### 3. `POST /v1/data-plane/token-law/fuse` — the operator surface (F00792/F00797)

On `sovereign-gatewayd` (a **light** dep — the fuse crate pulls no transformer).
Body = a `FuseRequest`; reply = `{ kind, mask, allowed_tokens, per_layer,
layers_active, stop }`. Unlike `/v1/token-law/allowed-mask` (pre-packed bitsets),
this **derives** each layer's bitset from a real source — the caller sends
sources, not masks. Metric `sovereign_data_plane_token_law_mask_layers` (F00798)
counts the laws fused.

## Roadmap — this SDD opens a three-fork arc (operator-directed 2026-07-21)

The operator chose to complete the whole token-law vision. The forks, sequenced:

1. **Expose** (this arc) — SDD-507 the fusion crate + data-plane route (here);
   then the `--token-law-mask-layers` osctl verb + profile knob + env var
   (F00793/4/5); then the dashboard mask-coverage heatmap (F00796).
2. **Connect** — close the `/v1/messages` boundary: the production serving path
   proxies out-of-process (no logit access), and gatewayd's own self-generation
   uses a *different* decode stack (`sovereign-quant-model`) than the engine
   (`sovereign-llm`/`DecoderStack`). Making the engine constrain real traffic is
   its own SDD.
3. **Deepen** — the "route" plane as a real source, a text→token projection for
   the entropy/checksum safety detectors, and SIMD to hit the 16 KB / AVX-512
   speed target (SDD-502's tracked follow-up).

## What shipped (2026-07-21)

- **`crates/sovereign-token-law-fuse`** (NEW) — `FuseLayers` / `CompiledFuse` / `FusedMask` / `LayerCoverage` / `FuseError` / `FuseRequest`. `forbid(unsafe_code)`. 8 tests (identity permits all; positive regex restricts; positive ∧ negated regex compose; denylist bans the cross-boundary completing token; policy plane AND-s in; empty intersection ⇒ `stop`; invalid regex errors; `FuseRequest` round-trips from JSON).
- **`crates/sovereign-llm`** — `complete_with_token_law` delegates to `CompiledFuse::fused_mask`; behaviour unchanged (92 lib + 28 runtime pass, incl. the SDD-505/506 parity tests).
- **`crates/sovereign-gatewayd`** — `POST /v1/data-plane/token-law/fuse` + the `sovereign_data_plane_token_law_mask_layers` metric (a `record_token_law_fuse` counter). +2 route tests (named layers derived + counted + surfaced on `/metrics`; empty-vocab and bad-regex ⇒ 400).

Verified: `cargo test -p sovereign-token-law-fuse -p sovereign-llm -p sovereign-gatewayd` (8 + 92 lib + 28 runtime + 119 + 25 + 21 pass); `cargo clippy -D warnings` + `cargo fmt --check` clean; `tests/lint/test_token_law_fusion_data_plane_contract.py` locks the checkpoint-free crate, the llm delegation, the route + metric, and the honest checkpoint-independence framing.

## Non-goals

- **Generation over the route.** This returns the *mask* (the decision), not sampled text — generation needs a model and belongs to `complete_with_token_law`. The mask is the honest, checkpoint-independent artifact.
- **The CLI + dashboard** (F00793/4/5/6) — the next two Expose SDDs.
- **Constraining the `/v1/messages` proxy path** (SDD-500 boundary — no logit access) — the Connect fork.
- Regex features beyond the NFA set (`* + ? | () . [] \d \w \s`); grammar features beyond `sovereign-json-schema-grammar`.

## References

- SDD-505 (the unified engine this exposes), SDD-506 (the negated-regex plane it fuses), SDD-500 § "honest scope caveat" (the `/v1/messages` boundary the Connect fork must cross).
- `backlog/milestones/M010-deterministic-data-plane.md` F00792/F00795/F00797/F00798 (the M00155 operator surface this opens).
- `crates/sovereign-token-law-fuse/src/lib.rs`, `crates/sovereign-llm/src/lib.rs` (`complete_with_token_law`), `crates/sovereign-gatewayd/src/http.rs` (`token_law_fuse`), `crates/sovereign-gatewayd/src/lib.rs` (`record_token_law_fuse` + the F00798 metric).
