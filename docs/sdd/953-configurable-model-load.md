# SDD-953 — configurable model load: precision-selectable weights + a sampler builder (the loader stops hardcoding F32-greedy)

> Status: draft
> Owner: operator-directed ("we can continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-12
> Number band: **950–999 (general / audit session)** per SDD-100.
> Closes findings: **F-2026-085** (partial — the precision-selectable-load half) + **F-2026-086** (partial — the model-side sampler half). From `docs/review/phase-1/99-findings-ledger.md`.
> Derived from / extends: SDD-950 (real RoPE — same loader, same "stop hardcoding a model constant" shape).

## Mission

`sovereign-safetensors-loader::load` assembled every model two ways that a caller could never change:

1. **Precision hardcoded to `F32`.** Despite the crate's name, every decoder block was built at `Precision::F32`, so a 7B model needs ~28GB resident and runs slowly on CPU — undercutting the "local sovereign" premise, even though `MhaDecoderBlock::from_weights` and `LayerStack` are **already precision-heterogeneous** and the workspace already has real, tested Ternary / NVFP4 / INT8 / BF16 quantize-from-f32 machinery.
2. **Sampler hardcoded to `Sampler::greedy()`.** So `temperature` / `top_p` / `top_k` were unreachable at the model level even if a request asked for them — the 790-line `sovereign-sampler` (with a fully-built `SamplerConfig`) was unreachable from a loaded model.

This SDD makes both **caller-selectable, additively** — no existing signature or call site changes, no gateway edits — closing the self-contained halves of F-2026-085 and F-2026-086.

## Scope — and what is deliberately OUT

**In (this SDD):**
- Thread a caller-chosen `Precision` into the runtime blocks so a real checkpoint can load as Ternary / NVFP4 / INT8 / BF16 in-memory (quantized *down* from the parsed f32/f16/bf16 weights).
- Thread a caller-supplied `Sampler` into the assembled model, and add a `QuantModel::with_sampler` builder + `sampler()` getter so the sampler is configurable at the model level.

**Out (named follow-ups, tracked):**
- **GGUF / pre-quantized-checkpoint loading** (the *other* half of F-2026-085) — loading a file whose weights are *already* Q4_K/Q8_0/GPTQ/AWQ requires a from-scratch GGUF parser + superblock dequant kernels; **no such path exists anywhere in the workspace** (`load` only decodes F32/F16/BF16 dtypes → `LoaderError::UnsupportedDtype` otherwise). That is a milestone, not this chunk.
- **Threading per-request HTTP sampling params** (`temperature`/`top_p`/… from `/v1/chat/completions`) into `GatewayServer::generate_chat` — that changes the daemon's generation signature + its call sites in `sovereign-gatewayd/src/main.rs`, which a **parallel session owns** (the Anthropic-Messages-API work). This SDD stops at the model-side hook that work will plug into. GPU backends stay out (`unsafe_code = forbid` workspace-wide).

## What this SDD builds

### 1. `sovereign-safetensors-loader` — precision- and sampler-selectable entry points

The dense-f32-greedy `load` is refactored into a single configurable core plus delegating convenience wrappers (all additive; `load`'s signature is unchanged, so every existing call site — `sovereign-gatewayd`, `sovereign-serve`, `sovereign-feature-selftest` — is untouched):

| Entry point | Precision | Sampler |
|---|---|---|
| `load(bytes, config)` (unchanged) | F32 | greedy |
| `load_at_precision(bytes, config, precision)` | caller | greedy |
| `load_with_sampler(bytes, config, sampler)` | F32 | caller |
| `load_configured(bytes, config, precision, sampler)` | caller | caller |

`Precision` (from `sovereign-linear`) and `Sampler` (from `sovereign-sampler`) are re-exported from the loader crate so callers can name the knobs without adding direct dependencies. The single hardcode `MhaDecoderBlock::from_weights(&weights, Precision::F32)` becomes `(&weights, precision)`; the `let sampler = Sampler::greedy();` line is replaced by the passed-in `sampler`.

### 2. `sovereign-quant-model` — `with_sampler` builder + `sampler()` getter

`QuantModel` stored its sampler as a construct-only field with no way to change or read it. NEW `with_sampler(mut self, Sampler) -> Self` builder (mirrors the existing `with_logit_softcap` / `with_recent_window`) + `sampler(&self) -> &Sampler` getter, so a caller can re-point an already-assembled model at a warm sampler and introspect it. This is the exact hook the future gateway-side per-request wiring plugs into.

## Verification

- `cargo test -p sovereign-safetensors-loader` — 17 (4 new): `load_at_precision` builds a runnable model at each of Bf16/Int8/Nvfp4/Ternary with finite logits; `load` defaults to greedy; `load_with_sampler` threads a 0.7 temperature; `load_configured` sets both a non-f32 precision and a top-k sampler.
- `cargo test -p sovereign-quant-model` — 10 (1 new): `with_sampler` replaces the sampler and the getter observes the change (greedy → 0.8 / top_p 0.9).
- `cargo clippy -p sovereign-quant-model -p sovereign-safetensors-loader --all-targets -- -D warnings` clean; `cargo fmt --all --check` clean.
- Downstream `sovereign-gatewayd` / `sovereign-serve` / `sovereign-feature-selftest` / `sovereign-quant-llm` build unchanged (additive API).

**Not asserted:** semantic coherence of the quantized output — the fixture weights are synthetic; real-model coherence is the gated follow-up (needs weights + network, absent in this environment). The *machinery* lands and is unit-tested; a real checkpoint now has a path to load quantized and sample non-greedily.

## Way forward

- **GGUF / pre-quantized load** (F-2026-085 remainder): a real dequant-from-disk path — milestone-scoped (new format + kernels).
- **Per-request sampling** (F-2026-086 remainder): the parallel Anthropic-compat session threads request `temperature`/`top_p`/`top_k` → `generate_chat` → `QuantModel::with_sampler` (the hook this SDD adds).
- **A default-precision knob in `Config`** (read a `quantization_config` from `config.json`) so a checkpoint can declare its own runtime precision — small follow-up on top of `load_at_precision`.

## Safety invariants

Purely additive: `load`'s signature is unchanged and still defaults to F32/greedy, so every existing caller behaves identically. The new precision path quantizes *down* from the already-parsed f32 weights using machinery that is already unit-tested; it never fabricates weights and never changes the guard-free math path. No contract yaml change; no lifecycle/security change. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — F-2026-085 (precision/quant load), F-2026-086 (sampling + chat template)
- `docs/sdd/950-real-rope-theta-scaling.md` — sibling "stop hardcoding a model constant" fix on the same loader (Arc 1)
- `crates/sovereign-safetensors-loader/src/lib.rs` — `load_configured` + the convenience wrappers
- `crates/sovereign-quant-model/src/lib.rs` — `with_sampler` / `sampler()`
- `crates/sovereign-sampler/src/lib.rs` — `SamplerConfig` (the knobs) · `crates/sovereign-linear/src/lib.rs` — `Precision`
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
