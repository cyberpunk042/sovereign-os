# SDD-717 — vision + speculative-draft serving on the dual-Turing node (Slice 3) (IMPLEMENTATION)

> Status: draft (implementation — Slice 3: the vision + speculative companions)
> Owner: operator-directed 2026-07-16 (verbatim): *"2b and 3 now, one PR. take your time"* — landing the two
> BF16 files the operator originally named (`…-mmproj-BF16.gguf`, `…-dspark-bf16.gguf`).
> Addresses: makes the 27B oracle image-capable and decode-accelerated on the dual-Turing node. No finding
> re-opens; adjacent to **M083** (DFlash/DSpark speculative decoding).
> Mandate module: **E11.M717**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## What this delivers

The last two of the operator's originally-named Bonsai-27B files, served on the dual-Turing node (SDD-714/715):

- **Vision (`--mmproj`)** — `LlamaCppBackend` gains `mmproj_path` → `--mmproj`, plumbed through
  `for_dual_turing()`. A multimodal projector makes the 27B oracle image-capable (the operator's
  `Ternary-Bonsai-27B-mmproj-BF16.gguf`; prism-ml ships image-text-to-text Bonsai-27B variants, Qwen3-VL
  lineage). Catalog: `Ternary-Bonsai-27B-vision` (`class: multimodal`, `base_model: Ternary-Bonsai-27B`,
  `engine: llama.cpp`), bound to `dual-turing-serving`.
- **Speculative draft (`--model-draft`)** — `draft_model_path` → `--model-draft`, plumbed through
  `for_dual_turing()`. A small draft model drafts tokens the 27B oracle verifies, accelerating decode (the
  operator's `Ternary-Bonsai-27B-dspark-bf16.gguf`). Catalog: `Ternary-Bonsai-27B-dspark` (`class: speculative`,
  `base_model: Ternary-Bonsai-27B`), bound to `dual-turing-serving`.

Both entries are `status: operator-must-confirm` (real weights + a serving smoke pending), and both are **BF16
→ F16** on Turing (SM 7.5 has no native BF16 — the one hardware caveat the operator flagged from the start).

## Relationship to SAIN-01's DFlash/DSpark (M083) — not a reinvention

SAIN-01 already runs speculative decoding as **DFlash/DSpark** (M083): a lossless rejection-sampling draft
through vLLM `--speculative-config` on the OcuLink eGPU, toggled by `dspark-ctl.py` /
`sovereign-osctl dspark {status,enable,disable}`. That path is **vLLM + big-GPU**. The dual-Turing node can't
run it (llama.cpp, uneven Turing), so this adds the **llama.cpp `--model-draft` analogue** — the same idea
(draft-then-verify) on the box that can actually run it. The M083 config + toggle are untouched; this is the
Turing serving path beside it.

## Verification

- `cargo`/argv: `LlamaCppBackend.for_dual_turing(mmproj_path=…, draft_model_path=…)` emits `--mmproj` +
  `--model-draft`; non-vision/non-draft constructors emit neither (backend verbatim test pins both).
- Catalog: the two entries validate (schema `class` enum has `multimodal` + `speculative`; `base_model` is
  optional for both but declared, and the extended serving-coherence lint now checks **any** base_model-carrying
  entry — lora / speculative / vision — resolves to a real base AND its bound profile serves that base).
- `adapter-foundry.py` inventory is unchanged (it tracks `class: lora-adapter` only; multimodal/speculative are
  separate classes).
- Full `tests/` + 5 profiles + ruff green.
- **Not hardware-verified** (no Turing GPUs / no real projector or draft weights in CI): a real image query or a
  real accept-rate. The argv + catalog graph + coherence are proven; the serving smokes are runtime steps.

## Scope / posture

- **Serve-only** — no conversion tooling here; BF16→F16 is a documented runtime step per entry.
- **M083 (DFlash/DSpark) spec + `dspark-ctl` untouched** — this is the parallel llama.cpp path, not an edit to
  the vLLM one.
- The base 27B stays the shared model; the projector and draft are companions loaded alongside it.

## Non-goals

- **Conversion tooling** (BF16 → F16 GGUF for Turing) — a documented manual step; a helper is a follow-up.
- **A vision serving smoke / accept-rate benchmark** — needs real weights + GPUs.
- **Wiring the draft into `dspark-ctl` / control-systems** (a unified on/off across both the vLLM and llama.cpp
  draft paths) — a later consolidation.
