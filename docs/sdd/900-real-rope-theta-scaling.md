# SDD-900 — Real RoPE: `rope_theta` + `rope_scaling` from the model config (make modern models decode coherently)

> Status: draft
> Owner: operator-directed ("we continue" — Arc 1 of the Phase-1 audit); agent-authored
> Last updated: 2026-07-12
> Number band: **900–999 (general / audit session)** per SDD-100 — this session claims its own band so it can never collide with the recover / header-sidemenu / science-tools sessions.
> Closes findings: **F-2026-080** (the RoPE frequency base was hardcoded to 10000, so Llama-3 / Qwen2 / Mistral decoded as garbage). From `docs/review/phase-1/99-findings-ledger.md` (Arc 1 — "make the real model real").
> Derived from / extends: the safetensors loader (`sovereign-safetensors-loader`), `sovereign-mha-block`, `sovereign-rope` (which already carried `with_base` / `ntk_aware_base` / `with_yarn` — unplumbed), and the Anthropic Messages API (SDD-205) + safety spine (SDD-206), which serve/guard whatever this decodes.

## Mission

Make the box generate **coherent** text from a real model. The inference stack already assembles a runnable
`QuantModel` from HuggingFace safetensors, but every block was built with `Rope::new(head_dim)` — a **hardcoded
frequency base of 10000**. Modern models train with a different base (Llama-3 = 500000, Qwen2 = 1000000,
Mistral variants likewise); decoding them at 10000 rotates every position wrong and produces incoherent output.
This was the single biggest blocker to "point it at a real model" — and directly undercut SDD-205 (an
Anthropic-compatible endpoint that returns garbage is not usable from VS Code / Claude Code). The fix is pure
plumbing: `sovereign-rope` already has the primitives; they were never fed the config's real values.

## Problem

- `sovereign-mha-block` built `rope: Rope::new(hd)` (base 10000), with no way to set the base.
- `sovereign-safetensors-loader`'s `Config` never parsed `rope_theta` or `rope_scaling` — its own doc-comment
  listed "non-default `rope_theta`" as an unfixed **Out** limitation.
- Long-context models additionally ship a `rope_scaling` block (linear / dynamic-NTK / YaRN / llama3) that was
  entirely ignored.

## What this SDD builds

### 1. `sovereign-mha-block`: a `with_rope` builder

`MhaDecoderBlock::with_rope(theta_base, scaling: Option<&RopeScaling>)` rebuilds the block's RoPE head from the
model's real base + scaling family, mirroring the existing `with_context_extension` / `with_yarn_context`
builders (must be called before any `step`; additive, backward-compatible — the 8 `MhaBlockWeights` construction
sites and all existing tests are untouched). Two new public types — `RopeScalingKind`
(`Linear` / `Dynamic` / `Yarn` / `Llama3`) and `RopeScaling` (kind + factor + `original_ctx` + YaRN betas) —
map to `sovereign-rope`:

| Scaling | Mapping |
|---|---|
| none | `Rope::with_base(hd, theta)` — the core fix |
| `linear` | base = theta, `position_scale = 1/factor` (position interpolation) |
| `dynamic` / `ntk` | base = `ntk_aware_base(hd, theta, factor)` |
| `yarn` | `Rope::with_yarn(hd, theta, orig_ctx, orig_ctx·factor, β_slow, β_fast)` when `original_ctx` is known; else base-only |
| `llama3` | base = theta (exact); the low/high-freq ramp is a noted follow-up — short-context is coherent |

Honest partial support: YaRN without a known `original_ctx`, and the llama3 frequency ramp, fall back to the
**correct base theta** (the dominant correctness factor) rather than fabricating a scaling — per SB-077.

### 2. `sovereign-safetensors-loader`: parse + thread the config

`Config` gains `rope_theta: f32` (serde default 10000) and `rope_scaling: Option<RopeScalingCfg>` (accepts both
the newer `rope_type` and older `type` key; parses factor / `original_max_position_embeddings` / `beta_fast` /
`beta_slow`). `Config::rope_scaling_resolved()` translates it to a runtime `RopeScaling` (an unrecognized
`rope_type` ⇒ `None`, base-theta only — never a parse failure, never a fabricated scaling). Every block is now
built `.with_rope(config.rope_theta, config.rope_scaling_resolved().as_ref())`. The stale "Out: non-default
rope_theta" doc-limitation is replaced with the "In" note.

## Goals

- A real Llama-3 / Qwen2 / Mistral config decodes at its trained base, not 10000.
- Additive + backward-compatible: no change to existing block/loader callers or the downstream
  `QuantModel` / `QuantLlm` / `gatewayd` path (verified they build unchanged).
- Honest scaling: apply what `sovereign-rope` models exactly; fall back to base-theta (never a fabricated
  scaling) for the parts it doesn't yet model, and say so.

## Non-goals

- **Sampling parameters** (temperature / top_p / stop) — the other half of F-2026-086. Threading them touches
  the gateway generation signature (`QuantModel::generate` + `gatewayd`), which the parallel Anthropic-compat
  session is actively editing; scoped as the next arc to avoid a collision.
- **A real tokenizer bridge / chat template** (the runtime tokenizer is byte-BPE; the hf-tokenizer pretokenizer
  is a hand-rolled GPT-2 approximation) — F-2026-086 tail, separate follow-up.
- **The llama3 low/high-freq ramp** and **GGUF/quantized weight loading** (F-2026-085) — tracked follow-ups.
- **Real-model coherence verification** — cannot be exercised in this environment (no network to model hosts,
  no weights on disk). This SDD lands + unit-tests the *machinery*; a real Llama-3 config now threads the right
  base end-to-end.

## Open questions

| Q | Question | Status |
|---|---|---|
| Q-900-001 | Model the llama3 low/high-freq ramp in `sovereign-rope` (a `with_llama3` constructor), or leave base-only? | open — base-only for now (short-context exact) |
| Q-900-002 | Should `max_position_embeddings` also be parsed to auto-derive a default context-extension when `rope_scaling` is absent? | open |

## Verification

- `cargo test -p sovereign-mha-block` — 28 (8 new: default base 10000; `with_rope` sets base; linear ⇒
  position_scale = 1/factor; dynamic ⇒ base raised; YaRN engages with known ctx / honest fallback without;
  llama3 base-only; **a distinct base yields distinct decode output** — proving the head is wired, not a no-op).
- `cargo test -p sovereign-safetensors-loader` — 13 (6 new: theta default 10000; theta parsed; linear via `type`;
  llama3 via `rope_type` + original_ctx; yarn betas; unknown type ⇒ no-scaling-not-error).
- `cargo clippy -p sovereign-mha-block -p sovereign-safetensors-loader --all-targets -- -D warnings` — clean.
- Downstream `sovereign-quant-llm` / `sovereign-gatewayd` / `sovereign-decoder-layer` / `sovereign-inference-demo`
  build unchanged. `cargo fmt --all --check` clean.

## Way forward

With the base correct, the next Arc-1 chunk is **sampling params + chat template** (F-2026-086), coordinated with
the gateway session, then **quantized weight loading** (F-2026-085). Together those three complete "the real model
is real" and make SDD-205's Anthropic endpoint genuinely usable from an editor.

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — F-2026-080 (source finding), F-2026-085/086 (the rest of Arc 1)
- `crates/sovereign-mha-block/src/lib.rs` — `RopeScaling`, `RopeScalingKind`, `MhaDecoderBlock::with_rope`, `rope_theta_base`
- `crates/sovereign-safetensors-loader/src/lib.rs` — `Config::{rope_theta, rope_scaling}`, `rope_scaling_resolved`
- `crates/sovereign-rope/src/lib.rs` — `with_base`, `ntk_aware_base`, `with_yarn` (the primitives now plumbed)
- SDD-205 — the Anthropic Messages API surface that serves what this decodes
- SDD-206 — the safety spine that guards whatever is generated
- SDD-100 — the per-session number-band convention this SDD's 900-band placement follows
- MS003 `unsigned-pending-MS003`
