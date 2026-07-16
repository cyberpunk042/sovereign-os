# SDD-714 — dual-Turing workstation serving profile + Bonsai catalog (IMPLEMENTATION)

> Status: draft (implementation — Slice 1 of the personal-workstation LoRA-serving plan)
> Owner: operator-directed 2026-07-16 (verbatim): *"I might wanna re-use those later with LORA customization
> for my personal (2080 + 2080 Ti workstation)"* → decisions: box role = **serve base + my LoRAs** (training
> offloaded), base = **both, tiered** (8B scout + 27B oracle) → *"yes. pull the latest main and start"*.
> Addresses: makes the operator's dual-Turing workstation a real, catalogued serving target. No finding
> re-opens; this is new operator-scoped work adjacent to **M046** (LoRA foundry) + **M018** (serving fabric).
> Mandate module: **E11.M714**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## What this delivers (Slice 1: "make the box a real target")

A llama.cpp-primary, two-tier **serving** node for the operator's personal dual-Turing workstation
(RTX 2080 Ti 11 GB + RTX 2080 8 GB), so the Prism-Ternary-Bonsai models are selectable there — with hot-swap
LoRA adapters trained elsewhere (SAIN-01's big GPU per M046 E0446). The box **adapts by serving, not training**
(operator-chosen).

- **NEW runtime profile** `profiles/runtime/dual-turing-serving.yaml` — an operator-additive § 18 profile.
  Two llama.cpp allocations, one model per card: `Ternary-Bonsai-27B` (Q2_0, oracle tier) on the 11 GB
  2080 Ti (`cuda:0`), `Prism-Ternary-Bonsai-8B` (scout tier) on the 8 GB 2080 (`cuda:1`). Schema-valid
  (`runtime-profile.schema.yaml`); id matches filename; header cites § 18.
- **Catalog** (`models/catalog.yaml`): adds `Ternary-Bonsai-27B` (HF-verified `prism-ml/Ternary-Bonsai-27B-gguf`,
  released 2026-07-04, base Qwen3.6-27B, ternary/GGUF, `engine: llama.cpp`), binds both Bonsai entries to the
  new profile, and **corrects the stale 2026-07-02 note** that said "largest is 8B" (the 27B post-dates it by
  two days). Regenerated `docs/src/model-catalog.md`.
- **llama.cpp backend** (`scripts/inference/backends/llama_cpp.py`): adds `--tensor-split` + a
  `for_dual_turing()` constructor (both cards visible, `tensor_split="11,8"` for a model too large for one
  card / long context). This is the concrete reason llama.cpp — not vLLM — serves this box: it handles
  **uneven** VRAM by ratio, where vLLM's tensor-parallel assumes symmetric cards.

## Why this hardware picks llama.cpp (grounding the engine choice)

Turing (SM 7.5) has **no native BF16/FP8** (Ampere+/Blackwell only), and the two cards are **uneven** (8 + 11
GB). vLLM's fast quant kernels (Marlin/AWQ/FP8) are mostly Ampere+, and its tensor-parallel bounds to the
smaller card — so vLLM stays a SAIN-01 concern. llama.cpp runs ternary GGUF on Turing and splits layers across
uneven cards by ratio. The Bonsai-27B Q2_0 (~9–10 GB packed) fits the 11 GB card alone at modest context; the
8B rides the 8 GB card. This mirrors the fabric's existing Scout/Oracle tiering (M018), instantiated on Turing.

Ternary is **not** an engine constraint: `models/catalog.yaml` already serves `ternary-1.58bit` on `vllm`
(Deepseek-V3-Ternary), `llama.cpp` (Bonsai-8B), and `bitnet.cpp` (the BitNet family) — the choice here is
about Turing + uneven VRAM, not about "vLLM can't do ternary."

## Contract lockstep (what moved together)

- `schemas/model-catalog.schema.yaml` — the `runtime_profile_bindings` enum (previously the 3 master-spec §18
  profiles) gains `dual-turing-serving`, so the Bonsai entries can bind to it (L1-cross-checked).
- `tests/lint/test_runtime_profiles_verbatim.py` — `test_runtime_profile_count_matches` pinned **exactly** the
  3 master-spec profiles; it now tracks an `OPERATOR_ADDITIVE_PROFILES` allowlist (drift on any *untracked*
  profile still fails), plus a new generic-invariants test (id/engine/tier/compat) for additive profiles. The
  schema-conformance test already treated extra profiles as operator-additive; this reconciles the two.
- `tests/lint/test_backend_adapters_verbatim.py` — a new assertion pins `--tensor-split` + `for_dual_turing`
  in the llama.cpp adapter.
- `profiles/old-workstation.yaml` — the GPU stub (which explicitly invited operator hardware details) is
  filled with the real dual-Turing pair, so the runtime profile's `hardware_profile_compat: [old-workstation]`
  is honest. Still schema-valid; no test pins its GPU shape.

## Verification

- `python3 -m pytest` on the touched contracts — runtime-profile schema-conformance + verbatim, catalog schema
  + content, backend-adapters verbatim, profile schema-conformance, module-recommendations — all green.
- Functional: `LlamaCppBackend.for_dual_turing(..., tensor_split="11,8")` emits `CUDA_VISIBLE_DEVICES=0,1` +
  `--tensor-split 11,8`; single-GPU constructors emit no split.
- `docs/src/model-catalog.md` regenerated; `context.md` sdd count 196→197.
- Full `tests/` + 5 profiles (`validate-profiles.sh`) + ruff real-bug gate green.
- **Not hardware-verified** (no Turing GPUs / weights in CI): a real Bonsai GGUF actually serving on a 2080 Ti
  + 2080 pair. The profile, catalog, schema, and argv construction are proven; the physical bring-up is a
  runtime step.

## Sovereignty / scope posture

- **Serve-only, training offloaded** (operator-chosen). No training code lands here.
- The **BF16** assets the operator listed (`mmproj-BF16` vision, `dspark-bf16` draft) need F16 conversion on
  Turing and a multimodal / speculative-decode serving path we don't have — **deferred to Slice 3**.
- **M046 E0446** LoRA hardware mapping (verbatim/sacrosanct spec, "4090 trains / Blackwell serves") is **left
  untouched** — the Turing *serving* role is encoded only in the profile + catalog, not by editing sacrosanct
  spec (operator's default choice (a) from the plan). Extending E0446 additively is a separate operator-directive.

## Non-goals (the rest of the plan)

- **Slice 2** — the adapter transport loop (LoRA trained on SAIN-01 → versioned on ZFS per M046 "Adapter
  Memory" → served on the 2×2080), and LoRA-as-profiles serving on llama.cpp. Own SDD.
- **Slice 3** — vision (`mmproj`, needs F16 conversion + a multimodal serving path) and the `dspark`
  speculative-decode draft. Own SDDs.
- Extending M046 E0446 with a Turing role (needs an operator directive — sacrosanct spec).
