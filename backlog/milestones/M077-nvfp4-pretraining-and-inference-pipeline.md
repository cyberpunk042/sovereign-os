# M077 — NVFP4 pretraining + inference pipeline (Blackwell-native 4-bit, RHT + 2D quantization + stochastic rounding + selective high-precision)

**Parent**: sovereign-os runtime — low-precision training + inference paradigm (layered onto M073 ternary BitLinear)
**Source**: arXiv 2509.25149 — "Pretraining Large Language Models with NVFP4" — NVIDIA (Felix Abecassis + 87 authors), published 2025-09-29; surfaced by operator via marktechpost article 2026-05-18 (`https://www.marktechpost.com/2026/05/18/nvidia-introduces-a-4-bit-pretraining-methodology-using-nvfp4-validated-on-a-12b-hybrid-mamba-transformer-at-10t-token-horizon/`)
**Companion sources** (NVFP4 ecosystem): arXiv 2505.19115 (FP4 All The Way / Chmiel/Fishman/Banner/Soudry) + arXiv 2601.22813 (Quartet II / Panferov/Schultheis/Tabesh/Alistarh) + arXiv 2603.28765 (Adaptive Block-Scaled IF4 / Cook/Lee/Le/Guo/Traverso/Chandrakasan/Han) + arXiv 2512.02010 (Four Over Six) + arXiv 2605.06067 (nGPT-NVFP4 / Fishman/Chmiel/Banner/Soudry/Ginsburg) + arXiv 2509.17791 (Elucidating FP4 Design Space)
**Provenance**: Ingested via HF MCP `paper_search` (authenticated user jfortin) 2026-05-19; verbatim quotes preserved in `backlog/notes/external-research-ingestion-2026-05-19.md`

## Doctrinal anchors (verbatim from arXiv 2509.25149)

> "we introduce a novel approach for stable and accurate training of large language models (LLMs) using the NVFP4 format. Our method integrates Random Hadamard transforms (RHT) to bound block-level outliers, employs a two-dimensional quantization scheme for consistent representations across both the forward and backward passes, utilizes stochastic rounding for unbiased gradient estimation, and incorporates selective high-precision layers."

> "We validate our approach by training a 12-billion-parameter model on 10 trillion tokens -- the longest publicly documented training run in 4-bit precision to date."

> "the model trained with our NVFP4-based pretraining technique achieves training loss and downstream task accuracies comparable to an FP8 baseline."

**NVFP4 format spec** (verbatim from companion arXiv 2505.19115):

> "the NVFP4 format, where each block of 16 FP4 values (E2M1) shares a scale represented in E4M3, provides optimal results."

## Catalog positioning

NVFP4 is **NOT a replacement** for M073 BitNet ternary. M073 catalogs 1-bit (ternary) ≈1.58 bits/parameter for INFERENCE-FIRST workloads on CPU (Pulse Core). M077 catalogs 4-bit floating-point for **PRETRAINING + INFERENCE** on Blackwell GPU. The two are **complementary**: ternary for ultra-efficiency CPU inference (Profile 1), NVFP4 for Blackwell-native training + Oracle Core inference (M075 + Profile 3). Per operator standing direction "you cannot invent crap, you cannot re-invent" — this is hardware-fact-based capability addition derived from NVIDIA's published technique.

## Epics (E0738-E0747)

| epic | name | source |
|---|---|---|
| E0738 | NVFP4 format spec — block of 16 FP4 (E2M1) values shares E4M3 scale | arXiv 2505.19115 + 2509.25149 |
| E0739 | Random Hadamard Transforms (RHT) — bound block-level outliers | arXiv 2509.25149 |
| E0740 | Two-dimensional quantization scheme — consistent representations forward + backward passes | arXiv 2509.25149 |
| E0741 | Stochastic rounding — unbiased gradient estimation | arXiv 2509.25149 |
| E0742 | Selective high-precision layers — escape hatch for sensitivity-bound layers | arXiv 2509.25149 |
| E0743 | Hardware target — NVIDIA Blackwell GPUs (PRO 6000 96GB per M044 substrate) | arXiv 2509.25149 + cross-ref M044 |
| E0744 | Training pipeline — fully NVFP4 forward + backward pass | arXiv 2509.25149 |
| E0745 | Inference pipeline — NVFP4 weight + activation quantization at serving time | arXiv 2509.25149 + nGPT-NVFP4 |
| E0746 | LoRA Foundry NVFP4 path — adapter training in 4-bit (M046 extension) | arXiv 2601.22813 Quartet II + cross-ref M046 |
| E0747 | Ecosystem awareness — Quartet II / IF4 / Four Over Six / nGPT-NVFP4 as alternative recipes | arXiv 2601.22813 + 2603.28765 + 2512.02010 + 2605.06067 |

## Modules (M01275-M01291)

| module | name | source |
|---|---|---|
| M01275 | sovereign-nvfp4-format-encoder (E2M1 4-bit + E4M3 scale) | arXiv 2505.19115 |
| M01276 | sovereign-nvfp4-block-allocator (16-value blocks) | arXiv 2505.19115 |
| M01277 | sovereign-nvfp4-rht-applicator (Random Hadamard Transform) | arXiv 2509.25149 |
| M01278 | sovereign-nvfp4-2d-quantization-coordinator | arXiv 2509.25149 |
| M01279 | sovereign-nvfp4-stochastic-rounder | arXiv 2509.25149 |
| M01280 | sovereign-nvfp4-selective-high-precision-layer-selector | arXiv 2509.25149 |
| M01281 | sovereign-nvfp4-forward-pass-engine | arXiv 2509.25149 |
| M01282 | sovereign-nvfp4-backward-pass-engine | arXiv 2509.25149 |
| M01283 | sovereign-nvfp4-blackwell-cuda-bridge (sm_120 architecture flag) | arXiv 2509.25149 + cross-ref M067 |
| M01284 | sovereign-nvfp4-training-loss-validator (vs FP8 baseline) | arXiv 2509.25149 |
| M01285 | sovereign-nvfp4-inference-runtime | arXiv 2509.25149 + arXiv 2605.06067 |
| M01286 | sovereign-nvfp4-kv-cache-coordinator | arXiv 2605.06067 |
| M01287 | sovereign-nvfp4-lora-adapter-trainer (Quartet II integration) | arXiv 2601.22813 + cross-ref M046 |
| M01288 | sovereign-nvfp4-typed-mirror | cross-ref selfdef MS007 |
| M01289 | sovereign-nvfp4-event-emitter | cross-ref M049 + selfdef MS026 |
| M01290 | sovereign-nvfp4-replay-validator | cross-ref selfdef MS009 |
| M01291 | sovereign-nvfp4-cli-subcommand-set | cross-ref selfdef MS043 |

## Features (F06376-F06460)

| feature | name | source |
|---|---|---|
| F06376 | Format — NVFP4 = 4-bit floating-point per parameter | arXiv 2509.25149 + 2505.19115 |
| F06377 | Format — E2M1 mantissa-exponent layout per element | arXiv 2505.19115 |
| F06378 | Format — block size = 16 values per scale group | arXiv 2505.19115 |
| F06379 | Format — block scale represented in E4M3 (FP8) | arXiv 2505.19115 |
| F06380 | Format — supported in hardware by NVIDIA Blackwell GPUs | arXiv 2601.22813 |
| F06381 | Format — 4.2x speedup over BF16 on Blackwell (Quartet II benchmark) | arXiv 2601.22813 |
| F06382 | Format — IF4 (Int/Float 4) variant: FP4 ⊕ INT4 per-block via unused E4M3 sign bit | arXiv 2603.28765 |
| F06383 | Format — 4/6 (Four Over Six) variant: adaptive block scaling to smaller FP4 values | arXiv 2512.02010 |
| F06384 | RHT — Random Hadamard Transforms applied pre-quantization | arXiv 2509.25149 |
| F06385 | RHT — purpose: bound block-level outliers | arXiv 2509.25149 |
| F06386 | RHT — composes with nGPT normalized-architecture path (alternate stability mechanism) | arXiv 2605.06067 |
| F06387 | RHT — operator-toggleable per model | architecture + operator standing direction |
| F06388 | 2D quantization — consistent representations forward + backward | arXiv 2509.25149 |
| F06389 | 2D quantization — per-row + per-column scale (vs 1D per-row only) | arXiv 2509.25149 |
| F06390 | 2D quantization — reduces gradient estimation error | arXiv 2509.25149 + 2601.22813 |
| F06391 | Stochastic rounding — unbiased estimator for forward + backward + update | arXiv 2509.25149 |
| F06392 | Stochastic rounding — MS-EDEN variant 2x lower error than SR (Quartet II) | arXiv 2601.22813 |
| F06393 | Stochastic rounding — operator can select SR vs MS-EDEN per profile | architecture + operator standing direction |
| F06394 | Selective high-precision — layers that need BF16 retain BF16 | arXiv 2509.25149 |
| F06395 | Selective high-precision — typically embedding + final projection + norm layers | arXiv 2509.25149 + 2505.19115 |
| F06396 | Selective high-precision — operator can extend list per model | architecture |
| F06397 | Forward pass — round-to-nearest (RTN) per Chmiel et al. | arXiv 2505.19115 |
| F06398 | Backward pass — stochastic rounding for gradient unbiasedness | arXiv 2505.19115 + 2509.25149 |
| F06399 | Update pass — stochastic rounding for unbiased weight updates | arXiv 2505.19115 |
| F06400 | Threshold — gradient norm < 3x quantization noise → quantized training ineffective | arXiv 2505.19115 |
| F06401 | Validation — 12B model on 10T tokens matches FP8 baseline | arXiv 2509.25149 |
| F06402 | Validation — 7B model on 200B tokens (FP4 All The Way) | arXiv 2505.19115 |
| F06403 | Validation — 1.9B model on 38B tokens with 4.2x BF16 speedup (Quartet II) | arXiv 2601.22813 |
| F06404 | Validation — nGPT 1.2B + 3B/30B MoE with hyperspherical constraint | arXiv 2605.06067 |
| F06405 | Hardware — NVIDIA Blackwell GPU required (PRO 6000 in M044 substrate) | arXiv 2509.25149 + cross-ref M044 |
| F06406 | Hardware — CUDA toolkit ≥ 13.0 for NVFP4 native support | architecture + arXiv 2509.25149 |
| F06407 | Hardware — sm_120 (Blackwell) architecture flag in nvcc | architecture |
| F06408 | Hardware — composes with M067 kernel build (NVIDIA driver + CUDA install paths) | cross-ref M067 |
| F06409 | Inference — NVFP4 weight quantization at serving | arXiv 2605.06067 |
| F06410 | Inference — NVFP4 activation quantization at serving | arXiv 2605.06067 |
| F06411 | Inference — KV cache fp4 option (extends M076 Profile 3 fp8) | arXiv 2605.06067 + cross-ref M076 |
| F06412 | Inference — Oracle Core (M075) gains NVFP4 model class alongside FP16 | cross-ref M075 |
| F06413 | LoRA — Quartet II Blackwell kernels integrate with M046 LoRA Foundry | arXiv 2601.22813 + cross-ref M046 |
| F06414 | LoRA — adapter promotion = L6 Persist requires NVFP4 retraining eval per arXiv 2601.22813 | cross-ref selfdef MS039 + MS041 |
| F06415 | LoRA — adapter trainable in 4-bit reduces VRAM footprint 4x vs BF16 | arXiv 2601.22813 |
| F06416 | LoRA — adapter portable across NVFP4 / FP8 / BF16 base models with rescale | architecture + arXiv 2601.22813 |
| F06417 | Ecosystem — Quartet II GitHub: github.com/IST-DASLab/Quartet-II | arXiv 2601.22813 |
| F06418 | Ecosystem — Four Over Six GitHub: github.com/mit-han-lab/fouroversix | arXiv 2512.02010 |
| F06419 | Ecosystem — nGPT-NVFP4 reference: github.com/anonymous452026/ngpt-nvfp4 | arXiv 2605.06067 |
| F06420 | Ecosystem — Elucidating FP4 Design Space (Graphcore): unified simulator framework | arXiv 2509.17791 |
| F06421 | Ecosystem — UE5M3 scaling factor (Graphcore variant) operator-pickable | arXiv 2509.17791 |
| F06422 | Doctrinal — NOT a replacement for M073 ternary | architecture + operator standing direction |
| F06423 | Doctrinal — complementary: ternary for CPU inference, NVFP4 for Blackwell training+inference | architecture |
| F06424 | Doctrinal — Profile 1 Ultra-Sovereign Efficiency stays on M073 ternary | cross-ref M076 |
| F06425 | Doctrinal — Profile 2/3 Burst + Deep Context can use NVFP4 base models | cross-ref M076 |
| F06426 | Doctrinal — Conductor (M075) stays ternary; Logic + Oracle gain NVFP4 option | cross-ref M075 |
| F06427 | Doctrinal — selfdef MS035 capability_word.compute_mode bit expanded for NVFP4 | cross-ref selfdef MS035 |
| F06428 | Format encoder — packs E2M1 + E4M3 scale per spec | arXiv 2505.19115 |
| F06429 | Format encoder — validates 16-value block boundary | arXiv 2505.19115 |
| F06430 | Format encoder — emits OCSF System Activity 1001 on encode | cross-ref selfdef MS026 |
| F06431 | Format encoder — signed via MS003 | cross-ref selfdef MS003 |
| F06432 | Block allocator — 16-value blocks per tensor row + column | arXiv 2509.25149 |
| F06433 | Block allocator — alignment validator (rejects non-16-aligned dims) | architecture |
| F06434 | RHT applicator — random orthogonal Hadamard matrix per block | arXiv 2509.25149 + 2505.19115 |
| F06435 | RHT applicator — seed-deterministic (replay-safe per MS009) | cross-ref selfdef MS009 |
| F06436 | 2D quantization coordinator — per-row scale | arXiv 2509.25149 |
| F06437 | 2D quantization coordinator — per-column scale | arXiv 2509.25149 |
| F06438 | 2D quantization coordinator — scale storage in E4M3 | arXiv 2505.19115 |
| F06439 | Stochastic rounder — uses cryptographic PRNG for unbiasedness | architecture + arXiv 2509.25149 |
| F06440 | Stochastic rounder — seed recorded per batch for MS009 replay | cross-ref selfdef MS009 |
| F06441 | High-precision selector — config file at /etc/sovereign-os/nvfp4-high-precision-layers.toml | architecture |
| F06442 | High-precision selector — signed via MS003 | cross-ref selfdef MS003 |
| F06443 | Forward engine — invoked via Cranelift/LLVM target sm_120 | architecture + cross-ref M067 |
| F06444 | Backward engine — gradient checkpointing composes with forward | architecture |
| F06445 | Blackwell CUDA bridge — links against libcudnn + libcublas NVFP4 ops | architecture |
| F06446 | Training loss validator — diff vs FP8 baseline within 0.01 nats per token | arXiv 2509.25149 |
| F06447 | Training loss validator — alerts on divergence (OCSF Detection 2004) | cross-ref selfdef MS026 |
| F06448 | Inference runtime — vLLM + Triton NVFP4 kernels | arXiv 2601.22813 |
| F06449 | Inference runtime — composes with M076 Profile 3 podman command | cross-ref M076 |
| F06450 | KV cache coordinator — `--kv-cache-dtype nvfp4` option (extends M076 fp8) | arXiv 2605.06067 + cross-ref M076 |
| F06451 | LoRA adapter trainer — wraps Quartet II Blackwell kernels | arXiv 2601.22813 |
| F06452 | Typed mirror — sovereign-nvfp4-runtime-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F06453 | Typed mirror — NvFp4Mode enum (ForwardOnly / FullTraining / InferenceOnly / LoRAOnly) | cross-ref selfdef MS007 |
| F06454 | Typed mirror — NvFp4Recipe enum (NvidiaCanonical / QuartetII / FourOverSix / nGPT / Custom) | cross-ref selfdef MS007 |
| F06455 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F06456 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F06457 | Event emitter — every NVFP4 op emits M049 trace | cross-ref M049 |
| F06458 | Event emitter — emits OCSF System Activity 1001 per training step | cross-ref selfdef MS026 |
| F06459 | Replay validator — verifies historical NVFP4 training chain | cross-ref selfdef MS009 |
| F06460 | CLI — `sovereign nvfp4` subcommand set + ext into operator UX | cross-ref selfdef MS043 |

## Requirements (R12751-R12920)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R12751 | Doctrinal — NVFP4 4-bit pretraining recipe verbatim per arXiv 2509.25149 | arXiv 2509.25149 | F06376 | non-negotiable | false | 10 |
| R12752 | Doctrinal — Random Hadamard transforms (RHT) bound block-level outliers | arXiv 2509.25149 | F06384 | non-negotiable | false | 10 |
| R12753 | Doctrinal — two-dimensional quantization scheme for forward + backward consistency | arXiv 2509.25149 | F06388 | non-negotiable | false | 10 |
| R12754 | Doctrinal — stochastic rounding for unbiased gradient estimation | arXiv 2509.25149 | F06391 | non-negotiable | false | 10 |
| R12755 | Doctrinal — selective high-precision layers retained | arXiv 2509.25149 | F06394 | non-negotiable | false | 10 |
| R12756 | Doctrinal — validated 12B model on 10T tokens (longest 4-bit run documented) | arXiv 2509.25149 | F06401 | non-negotiable | false | 10 |
| R12757 | Doctrinal — training loss + downstream accuracies comparable to FP8 baseline | arXiv 2509.25149 | F06446 | non-negotiable | false | 10 |
| R12758 | Doctrinal — NVFP4 is hardware-supported on NVIDIA Blackwell GPUs | arXiv 2601.22813 | F06380 | non-negotiable | false | 10 |
| R12759 | Doctrinal — NOT a replacement for M073 ternary; complementary 4-bit FP path | operator standing direction + cross-ref M073 | F06422 | non-negotiable | false | 10 |
| R12760 | Doctrinal — operator standing direction "you cannot invent crap" upheld (NVIDIA-published hardware-fact) | operator standing direction | F06376 | non-negotiable | false | 10 |
| R12761 | Format — block size = 16 FP4 values per scale group | arXiv 2505.19115 | F06378 | non-negotiable | false | 10 |
| R12762 | Format — element layout E2M1 (1 sign + 2 exponent + 1 mantissa) | arXiv 2505.19115 | F06377 | non-negotiable | false | 10 |
| R12763 | Format — block scale layout E4M3 (1 sign + 4 exponent + 3 mantissa = FP8) | arXiv 2505.19115 | F06379 | non-negotiable | false | 10 |
| R12764 | Format — encoder validates 16-value block boundary | architecture | F06429 | non-negotiable | false | 10 |
| R12765 | Format — encoder signed via MS003 | cross-ref selfdef MS003 | F06431 | non-negotiable | false | 10 |
| R12766 | Format — encoder emits OCSF System Activity 1001 | cross-ref selfdef MS026 | F06430 | non-negotiable | false | 10 |
| R12767 | Format — encoder composes with M067 kernel CUDA stack | cross-ref M067 | F06408 | non-negotiable | false | 10 |
| R12768 | Format — Blackwell hardware target enforced (PRO 6000 96GB per M044) | arXiv 2509.25149 + cross-ref M044 | F06405 | non-negotiable | false | 10 |
| R12769 | Format — IF4 variant (FP4 ⊕ INT4 per-group) operator-pickable | arXiv 2603.28765 | F06382 | non-negotiable | false | 10 |
| R12770 | Format — 4/6 variant (adaptive block scaling) operator-pickable | arXiv 2512.02010 | F06383 | non-negotiable | false | 10 |
| R12771 | RHT — Random Hadamard Transform applied pre-quantization | arXiv 2509.25149 | F06384 | non-negotiable | false | 10 |
| R12772 | RHT — orthogonal random matrix per block | arXiv 2505.19115 | F06434 | non-negotiable | false | 10 |
| R12773 | RHT — seed-deterministic for MS009 replay | cross-ref selfdef MS009 | F06435 | non-negotiable | false | 10 |
| R12774 | RHT — operator can toggle on/off per model | operator standing direction | F06387 | non-negotiable | false | 10 |
| R12775 | RHT — alternative: nGPT hyperspherical constraint (no RHT needed) | arXiv 2605.06067 | F06386 | non-negotiable | false | 10 |
| R12776 | 2D quant — per-row scale | arXiv 2509.25149 | F06436 | non-negotiable | false | 10 |
| R12777 | 2D quant — per-column scale | arXiv 2509.25149 | F06437 | non-negotiable | false | 10 |
| R12778 | 2D quant — scales stored in E4M3 | arXiv 2505.19115 | F06438 | non-negotiable | false | 10 |
| R12779 | 2D quant — reduces gradient estimation error vs 1D | arXiv 2509.25149 + 2601.22813 | F06390 | non-negotiable | false | 10 |
| R12780 | 2D quant — operator can fall back to 1D for compatibility | architecture | F06436 | non-negotiable | false | 10 |
| R12781 | SR — cryptographic PRNG (not deterministic LCG) | architecture + arXiv 2509.25149 | F06439 | non-negotiable | false | 10 |
| R12782 | SR — seed recorded per batch in MS009 audit chain | cross-ref selfdef MS009 | F06440 | non-negotiable | false | 10 |
| R12783 | SR — applied to backward pass | arXiv 2509.25149 | F06398 | non-negotiable | false | 10 |
| R12784 | SR — applied to update pass | arXiv 2505.19115 | F06399 | non-negotiable | false | 10 |
| R12785 | SR — forward pass uses round-to-nearest (RTN) | arXiv 2505.19115 | F06397 | non-negotiable | false | 10 |
| R12786 | SR — MS-EDEN variant 2x lower error available | arXiv 2601.22813 | F06392 | non-negotiable | false | 10 |
| R12787 | SR — operator selects SR vs MS-EDEN per profile | operator standing direction | F06393 | non-negotiable | false | 10 |
| R12788 | Selective HP — embeddings retained in BF16 by default | arXiv 2505.19115 | F06395 | non-negotiable | false | 10 |
| R12789 | Selective HP — final projection layer retained in BF16 by default | arXiv 2505.19115 | F06395 | non-negotiable | false | 10 |
| R12790 | Selective HP — norm layers retained in BF16 by default | arXiv 2505.19115 | F06395 | non-negotiable | false | 10 |
| R12791 | Selective HP — config at /etc/sovereign-os/nvfp4-high-precision-layers.toml | architecture | F06441 | non-negotiable | false | 10 |
| R12792 | Selective HP — config signed via MS003 | cross-ref selfdef MS003 | F06442 | non-negotiable | false | 10 |
| R12793 | Selective HP — operator can extend per-model | architecture | F06396 | non-negotiable | false | 10 |
| R12794 | Threshold — gradient norm < 3x quantization noise → halt + revert to FP8 | arXiv 2505.19115 | F06400 | non-negotiable | false | 10 |
| R12795 | Threshold — emits OCSF Detection 2004 on threshold breach | cross-ref selfdef MS026 | F06447 | non-negotiable | false | 10 |
| R12796 | Hardware — Blackwell PRO 6000 96GB (per M044 substrate) | cross-ref M044 | F06405 | non-negotiable | false | 10 |
| R12797 | Hardware — CUDA toolkit ≥ 13.0 | architecture | F06406 | non-negotiable | false | 10 |
| R12798 | Hardware — sm_120 architecture flag in nvcc | architecture | F06407 | non-negotiable | false | 10 |
| R12799 | Hardware — Bootstrap Check 04 (M072) must verify Blackwell driver license + version | cross-ref M072 | F06408 | non-negotiable | false | 10 |
| R12800 | Hardware — composes with M067 kernel build (CUDA stack present) | cross-ref M067 | F06408 | non-negotiable | false | 10 |
| R12801 | Training — 4.2x speedup over BF16 measured (Quartet II) | arXiv 2601.22813 | F06381 | non-negotiable | false | 10 |
| R12802 | Training — training loss validator diff < 0.01 nats/token vs FP8 | arXiv 2509.25149 | F06446 | non-negotiable | false | 10 |
| R12803 | Training — divergence triggers M055 failure-mode taxonomy entry | cross-ref M055 | F06447 | non-negotiable | false | 10 |
| R12804 | Training — composes with M063 SFIF Features phase (advanced runtime layer) | cross-ref M063 | F06376 | non-negotiable | false | 10 |
| R12805 | Training — every step emits M049 13-field trace | cross-ref M049 | F06457 | non-negotiable | false | 10 |
| R12806 | Inference — NVFP4 weight quantization at serving | arXiv 2605.06067 | F06409 | non-negotiable | false | 10 |
| R12807 | Inference — NVFP4 activation quantization at serving | arXiv 2605.06067 | F06410 | non-negotiable | false | 10 |
| R12808 | Inference — Oracle Core (M075) gains NVFP4 model class | cross-ref M075 | F06412 | non-negotiable | false | 10 |
| R12809 | Inference — `--kv-cache-dtype nvfp4` extends M076 Profile 3 fp8 option | cross-ref M076 | F06411 | non-negotiable | false | 10 |
| R12810 | Inference — vLLM Triton NVFP4 kernels integrated per Quartet II | arXiv 2601.22813 | F06448 | non-negotiable | false | 10 |
| R12811 | Inference — composes with M076 Profile 3 Deep Context Synthesis (podman + vllm) | cross-ref M076 | F06449 | non-negotiable | false | 10 |
| R12812 | LoRA — Quartet II Blackwell kernels integrated with M046 LoRA Foundry | arXiv 2601.22813 + cross-ref M046 | F06413 | non-negotiable | false | 10 |
| R12813 | LoRA — adapter trainable in 4-bit reduces VRAM 4x vs BF16 | arXiv 2601.22813 | F06415 | non-negotiable | false | 10 |
| R12814 | LoRA — adapter promotion = L6 Persist + NVFP4 eval pass per MS041 | cross-ref selfdef MS039 + MS041 | F06414 | non-negotiable | false | 10 |
| R12815 | LoRA — adapter portable across NVFP4 / FP8 / BF16 base models | arXiv 2601.22813 + architecture | F06416 | non-negotiable | false | 10 |
| R12816 | LoRA — adapter rescale validator verifies cross-precision portability | architecture | F06416 | non-negotiable | false | 10 |
| R12817 | Ecosystem — Quartet II github.com/IST-DASLab/Quartet-II clone path /opt/sovereign-os/quartet-ii/ | arXiv 2601.22813 | F06417 | non-negotiable | false | 10 |
| R12818 | Ecosystem — Four Over Six github.com/mit-han-lab/fouroversix clone path /opt/sovereign-os/fouroversix/ | arXiv 2512.02010 | F06418 | non-negotiable | false | 10 |
| R12819 | Ecosystem — nGPT-NVFP4 reference cloned to /opt/sovereign-os/ngpt-nvfp4/ | arXiv 2605.06067 | F06419 | non-negotiable | false | 10 |
| R12820 | Ecosystem — Elucidating FP4 Design Space (Graphcore) simulator framework cataloged | arXiv 2509.17791 | F06420 | non-negotiable | false | 10 |
| R12821 | Ecosystem — UE5M3 scaling factor (Graphcore) operator-pickable alternative | arXiv 2509.17791 | F06421 | non-negotiable | false | 10 |
| R12822 | Ecosystem — Adaptive Block-Scaled IF4 (MIT-HanLab) operator-pickable alternative | arXiv 2603.28765 | F06382 | non-negotiable | false | 10 |
| R12823 | Ecosystem — every ecosystem clone signed via MS003 + checksum-validated | cross-ref selfdef MS003 | F06417 | non-negotiable | false | 10 |
| R12824 | Ecosystem — clones updated daily via MS009 audit cycle | cross-ref selfdef MS009 | F06417 | non-negotiable | false | 10 |
| R12825 | Composition — composes with M044 substrate (Blackwell PRO 6000) | cross-ref M044 | F06405 | non-negotiable | false | 10 |
| R12826 | Composition — composes with M046 LoRA Foundry (Quartet II path) | cross-ref M046 | F06413 | non-negotiable | false | 10 |
| R12827 | Composition — composes with M048 modules map (Compute Fabric extension) | cross-ref M048 | F06448 | non-negotiable | false | 10 |
| R12828 | Composition — composes with M058 hardware-aware scheduler (Blackwell oracle NVFP4 throughput tier) | cross-ref M058 | F06412 | non-negotiable | false | 10 |
| R12829 | Composition — composes with M067 kernel build (CUDA + driver stack) | cross-ref M067 | F06408 | non-negotiable | false | 10 |
| R12830 | Composition — composes with M068 ZFS tank/models (NVFP4 variant dir) | cross-ref M068 | F06376 | non-negotiable | false | 10 |
| R12831 | Composition — composes with M073 ternary (complementary not replacement) | cross-ref M073 | F06422 | non-negotiable | false | 10 |
| R12832 | Composition — composes with M074 VNNI (orthogonal: NVFP4 on GPU, VNNI on CPU) | cross-ref M074 | F06376 | non-negotiable | false | 10 |
| R12833 | Composition — composes with M075 SRP topology (Oracle Core NVFP4 mode) | cross-ref M075 | F06412 | non-negotiable | false | 10 |
| R12834 | Composition — composes with M076 Profile 3 Deep Context (NVFP4 KV cache) | cross-ref M076 | F06411 | non-negotiable | false | 10 |
| R12835 | Composition — composes with M072 Bootstrap Verification (Check 04 driver verify) | cross-ref M072 | F06408 | non-negotiable | false | 10 |
| R12836 | Composition — composes with selfdef MS003 chain-of-trust (every NVFP4 op signed) | cross-ref selfdef MS003 | F06431 | non-negotiable | false | 10 |
| R12837 | Composition — composes with selfdef MS035 capability_word.compute_mode (NVFP4 bit) | cross-ref selfdef MS035 | F06427 | non-negotiable | false | 10 |
| R12838 | Composition — composes with selfdef MS039 authority (NVFP4 training = L5 Commit per L6 adapter promotion) | cross-ref selfdef MS039 | F06414 | non-negotiable | false | 10 |
| R12839 | Composition — composes with selfdef MS041 commit authority (triple-gate for NVFP4 adapter promotion) | cross-ref selfdef MS041 | F06414 | non-negotiable | false | 10 |
| R12840 | Composition — composes with selfdef MS043 IPS operator surface (CLI integration) | cross-ref selfdef MS043 | F06460 | non-negotiable | false | 10 |
| R12841 | Boundary — NVFP4 runtime = sovereign-os | architecture + operator standing direction | F06376 | non-negotiable | false | 10 |
| R12842 | Boundary — selfdef IPS enforces sandbox per MS036 + network per MS038 | operator standing direction | F06376 | non-negotiable | false | 10 |
| R12843 | Boundary — selfdef reads NVFP4 state via MS007 mirror only | cross-ref selfdef MS007 | F06452 | non-negotiable | false | 10 |
| R12844 | Boundary — info-hub indexes NVFP4 paper lineage as second-brain entry | operator standing direction | F06376 | non-negotiable | false | 10 |
| R12845 | Boundary — info-hub never mutated by NVFP4 training pipeline | operator standing direction | F06376 | non-negotiable | false | 10 |
| R12846 | Typed mirror — sovereign-nvfp4-runtime-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F06452 | non-negotiable | false | 10 |
| R12847 | Typed mirror — NvFp4Mode enum 4 variants | cross-ref selfdef MS007 | F06453 | non-negotiable | false | 10 |
| R12848 | Typed mirror — NvFp4Recipe enum 5 variants (NvidiaCanonical / QuartetII / FourOverSix / nGPT / Custom) | cross-ref selfdef MS007 | F06454 | non-negotiable | false | 10 |
| R12849 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F06455 | non-negotiable | false | 10 |
| R12850 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F06456 | non-negotiable | false | 10 |
| R12851 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F06452 | non-negotiable | false | 10 |
| R12852 | Typed mirror — no_std friendly | architecture | F06452 | non-negotiable | false | 10 |
| R12853 | Typed mirror — serde + bincode derives present | architecture | F06452 | non-negotiable | false | 10 |
| R12854 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F06455 | non-negotiable | false | 10 |
| R12855 | Event — every NVFP4 training step emits M049 13-field span | cross-ref M049 | F06457 | non-negotiable | false | 10 |
| R12856 | Event — span includes recipe-variant + RHT-seed + SR-seed + 2D-scale-digest | architecture + arXiv 2509.25149 | F06457 | non-negotiable | false | 10 |
| R12857 | Event — emits OCSF System Activity 1001 per training step | cross-ref selfdef MS026 | F06458 | non-negotiable | false | 10 |
| R12858 | Event — divergence emits OCSF Detection 2004 (high-priority) | cross-ref selfdef MS026 | F06447 | non-negotiable | false | 10 |
| R12859 | Event — span deterministic for MS009 replay | cross-ref selfdef MS009 | F06459 | non-negotiable | false | 10 |
| R12860 | Replay validator — verifies historical NVFP4 training chain | cross-ref selfdef MS009 | F06459 | non-negotiable | false | 10 |
| R12861 | Replay validator — detects unauthorized recipe variant change | cross-ref selfdef MS009 + MS003 | F06459 | non-negotiable | false | 10 |
| R12862 | Replay validator — detects RHT-seed forgery | cross-ref selfdef MS003 | F06459 | non-negotiable | false | 10 |
| R12863 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 | F06459 | non-negotiable | false | 10 |
| R12864 | Replay validator — runs daily as systemd timer | cross-ref selfdef MS009 | F06459 | non-negotiable | false | 10 |
| R12865 | Dashboard — D-03 model health shows NVFP4 model status alongside ternary + FP8 + BF16 | cross-ref M060 | F06409 | non-negotiable | false | 10 |
| R12866 | Dashboard — D-10 eval history shows NVFP4 vs FP8 training-loss diff over time | cross-ref M060 + arXiv 2509.25149 | F06446 | non-negotiable | false | 10 |
| R12867 | Dashboard — D-11 adapter status shows NVFP4-trained adapters | cross-ref M060 | F06413 | non-negotiable | false | 10 |
| R12868 | Dashboard — D-09 hardware pressure shows Blackwell NVFP4 throughput (TOPS) | cross-ref M060 | F06381 | non-negotiable | false | 10 |
| R12869 | Dashboard — D-04 costs shows NVFP4 vs FP8 energy + time savings | cross-ref M060 | F06381 | non-negotiable | false | 10 |
| R12870 | CLI — `sovereign nvfp4 status` returns current NVFP4 runtime state | cross-ref selfdef MS043 | F06460 | non-negotiable | false | 10 |
| R12871 | CLI — `sovereign nvfp4 recipe <name>` selects recipe variant | cross-ref selfdef MS003 + MS043 | F06454 | non-negotiable | false | 10 |
| R12872 | CLI — `sovereign nvfp4 train <config>` invokes training pipeline | architecture + cross-ref selfdef MS003 | F06444 | non-negotiable | false | 10 |
| R12873 | CLI — `sovereign nvfp4 inference <model>` invokes inference runtime | architecture | F06448 | non-negotiable | false | 10 |
| R12874 | CLI — `sovereign nvfp4 verify <model-id>` verifies model is NVFP4-quantized | architecture | F06452 | non-negotiable | false | 10 |
| R12875 | CLI — `sovereign nvfp4 throughput` returns sustained TOPS on Blackwell | architecture + arXiv 2601.22813 | F06381 | non-negotiable | false | 10 |
| R12876 | CLI — `sovereign nvfp4 lora train <base>` trains adapter via Quartet II path | cross-ref M046 + arXiv 2601.22813 | F06413 | non-negotiable | false | 10 |
| R12877 | CLI — all nvfp4 subcommands emit M049 trace | cross-ref M049 | F06457 | non-negotiable | false | 10 |
| R12878 | CLI — `--json` flag returns structured output | architecture | F06460 | non-negotiable | false | 10 |
| R12879 | CLI — exit codes follow sysexits.h | architecture | F06460 | non-negotiable | false | 10 |
| R12880 | Operator UX — operator can toggle NVFP4 on/off per profile | operator standing direction "everything can be turned on and off" | F06424 | non-negotiable | false | 10 |
| R12881 | Operator UX — operator can select NVFP4 vs FP8 vs BF16 per training run | operator standing direction "modes and profiles" | F06453 | non-negotiable | false | 10 |
| R12882 | Operator UX — operator can compare NVFP4 vs FP8 training-loss curves in D-10 | cross-ref M060 | F06446 | non-negotiable | false | 10 |
| R12883 | Operator UX — operator can view NVFP4 speedup over BF16 in D-09 | cross-ref M060 + arXiv 2601.22813 | F06381 | non-negotiable | false | 10 |
| R12884 | Operator UX — operator can promote NVFP4-trained adapters via D-11 (signed) | cross-ref M060 + selfdef MS003 | F06413 | non-negotiable | false | 10 |
| R12885 | Performance — NVFP4 training step latency `<` 2x FP8 step latency on Blackwell | arXiv 2601.22813 + architecture | F06381 | non-negotiable | false | 10 |
| R12886 | Performance — inference token throughput ≥ 1.5x FP8 on Blackwell | arXiv 2509.25149 | F06409 | non-negotiable | false | 10 |
| R12887 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F06452 | non-negotiable | false | 10 |
| R12888 | Performance — replay validator daily run `<` 120s for 10T-token chain | cross-ref selfdef MS009 | F06459 | non-negotiable | false | 10 |
| R12889 | Performance — kv-cache fp4 reduces VRAM 2x vs fp8 (per Quartet II) | arXiv 2601.22813 + cross-ref M076 | F06411 | non-negotiable | false | 10 |
| R12890 | Performance — training memory footprint reduces 4x vs BF16 (4-bit weights + activations) | arXiv 2509.25149 | F06415 | non-negotiable | false | 10 |
| R12891 | Telemetry — NVFP4 training step count emitted via M049 | cross-ref M049 | F06457 | non-negotiable | false | 10 |
| R12892 | Telemetry — NVFP4 vs FP8 training-loss-diff emitted via M049 | cross-ref M049 | F06446 | non-negotiable | false | 10 |
| R12893 | Telemetry — NVFP4 throughput TOPS emitted via M049 | cross-ref M049 | F06381 | non-negotiable | false | 10 |
| R12894 | Telemetry — recipe-variant in use emitted via M049 | cross-ref M049 | F06454 | non-negotiable | false | 10 |
| R12895 | Telemetry — gradient-norm-vs-quant-noise ratio emitted via M049 (threshold alert) | cross-ref M049 + arXiv 2505.19115 | F06400 | non-negotiable | false | 10 |
| R12896 | Operational — sovereign-nvfp4-runtime.service systemd unit | architecture | F06460 | non-negotiable | false | 10 |
| R12897 | Operational — service pinned to CCD 1 cores via CPUAffinity (Blackwell IRQ adjacency) | architecture + cross-ref M070 | F06460 | non-negotiable | false | 10 |
| R12898 | Operational — service honors SIGTERM (graceful drain — checkpoint mid-training) | architecture + cross-ref M063 IaC checkpoint | F06460 | non-negotiable | false | 10 |
| R12899 | Operational — service refuses to start if Blackwell driver missing per M072 Check 04 | cross-ref M072 | F06408 | non-negotiable | false | 10 |
| R12900 | Operational — service refuses to start if CUDA toolkit < 13.0 | architecture | F06406 | non-negotiable | false | 10 |
| R12901 | Operational — service refuses to start with chain-break in MS009 audit | cross-ref selfdef MS009 | F06459 | non-negotiable | false | 10 |
| R12902 | Operational — service refuses to start with missing MS003 keys | cross-ref selfdef MS003 | F06431 | non-negotiable | false | 10 |
| R12903 | Operational — service readiness probe at /run/sovereign-nvfp4/ready | architecture | F06460 | non-negotiable | false | 10 |
| R12904 | Operational — service Wants=sovereign-os.target | architecture | F06460 | non-negotiable | false | 10 |
| R12905 | Operational — service After=sovereign-ternary-runtime.service (M073 ordering) | architecture + cross-ref M073 | F06422 | non-negotiable | false | 10 |
| R12906 | Doctrinal preservation — arXiv 2509.25149 abstract preserved verbatim in `backlog/notes/external-research-ingestion-2026-05-19.md` | operator standing direction | F06376 | non-negotiable | false | 10 |
| R12907 | Doctrinal preservation — "12-billion-parameter model on 10 trillion tokens" verbatim | arXiv 2509.25149 | F06401 | non-negotiable | false | 10 |
| R12908 | Doctrinal preservation — "longest publicly documented training run in 4-bit precision to date" verbatim | arXiv 2509.25149 | F06401 | non-negotiable | false | 10 |
| R12909 | Doctrinal preservation — companion NVFP4 ecosystem papers cited verbatim (Quartet II / Four Over Six / nGPT / IF4 / Elucidating FP4) | arXiv 2601.22813 + 2603.28765 + 2512.02010 + 2605.06067 + 2509.17791 | F06420 | non-negotiable | false | 10 |
| R12910 | Doctrinal preservation — operator standing direction "you cannot invent crap" upheld (every recipe sourced from published paper) | operator standing direction | F06376 | non-negotiable | false | 10 |
| R12911 | Doctrinal preservation — operator standing direction "Respect the projects" upheld (NVFP4 = sovereign-os; selfdef enforces) | operator standing direction | F06841 | non-negotiable | false | 10 |
| R12912 | Doctrinal preservation — operator standing direction "second-brain" upheld (info-hub indexes lineage) | operator standing direction | F06844 | non-negotiable | false | 10 |
| R12913 | Doctrinal preservation — operator standing direction "layered ON TOP" upheld (M073 ternary not discarded) | operator standing direction | F06422 | non-negotiable | false | 10 |
| R12914 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F06906 | non-negotiable | false | 10 |
| R12915 | Closing — NVFP4 doctrine covers arXiv 2509.25149 + 2505.19115 verbatim | arXiv 2509.25149 + 2505.19115 | F06376 | non-negotiable | false | 10 |
| R12916 | Closing — sovereign-os catalog at 76/76 milestones | architecture | F06460 | non-negotiable | false | 10 |
| R12917 | Closing — combined ecosystem 120 milestones (selfdef 44 + sovereign-os 76) | architecture | F06460 | non-negotiable | false | 10 |
| R12918 | Closing — combined R-rows ~23480 | architecture | F06460 | non-negotiable | false | 10 |
| R12919 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F06376 | non-negotiable | false | 10 |
| R12920 | Closing — M077 covers NVFP4 scope verbatim; M078 GRPO + HölderPO next | arXiv 2509.25149 + operator standing direction | F06460 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M077.

## Cross-references

- **M044** — substrate (Blackwell PRO 6000 96GB)
- **M046** — LoRA Foundry (Quartet II integration path)
- **M048** — modules map (Compute Fabric extension)
- **M049** — observability + trace pipeline
- **M055** — failure modes (training divergence alert)
- **M058** — hardware-aware scheduler (Blackwell oracle NVFP4 throughput tier)
- **M060** — cockpit dashboards (D-03 / D-04 / D-09 / D-10 / D-11)
- **M063** — SFIF Features phase
- **M067** — Custom Kernel Build (CUDA + driver stack)
- **M068** — ZFS tank/models (NVFP4 variant dir)
- **M070** — Dual-CCD topology (CCD 1 IRQ adjacency to Blackwell)
- **M072** — Bootstrap Verification (Check 04)
- **M073** — 1-bit ternary BitLinear (COMPLEMENTARY, not replacement)
- **M075** — SRP hardware topology (Oracle Core NVFP4 mode)
- **M076** — 3 load-balancing profiles (Profile 3 KV cache extension)
- **selfdef MS003** — selfdef-signing
- **selfdef MS007** — typed-mirror crate scheme (sovereign-nvfp4-runtime-mirror)
- **selfdef MS009** — replay validator
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS035** — capability_word.compute_mode (NVFP4 bit)
- **selfdef MS036** — sandbox tiers
- **selfdef MS038** — network boundary
- **selfdef MS039** — authority levels (NVFP4 training = L5 Commit)
- **selfdef MS041** — commit authority (L6 Persist for adapter promotion)
- **selfdef MS043** — IPS operator surface

## Schema

```
schema_version: "1.0.0"
milestone_id: M077
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
canonical_source: "arXiv 2509.25149 — Pretraining Large Language Models with NVFP4 (NVIDIA, 2025-09-29)"
companion_sources:
  - "arXiv 2505.19115 — FP4 All The Way (Chmiel/Fishman/Banner/Soudry)"
  - "arXiv 2601.22813 — Quartet II (Panferov/Schultheis/Tabesh/Alistarh)"
  - "arXiv 2603.28765 — Adaptive Block-Scaled IF4 (Cook/Lee/Le/Guo/Traverso/Chandrakasan/Han)"
  - "arXiv 2512.02010 — Four Over Six (Cook/Guo/Xiao/Lin/Han)"
  - "arXiv 2605.06067 — nGPT-NVFP4 (Fishman/Chmiel/Banner/Soudry/Ginsburg)"
  - "arXiv 2509.17791 — Elucidating FP4 Design Space (Hu/Luschi/Balanca)"
operator_cited_article: "marktechpost.com/2026/05/18/nvidia-introduces-a-4-bit-pretraining-methodology-using-nvfp4-validated-on-a-12b-hybrid-mamba-transformer-at-10t-token-horizon/"
nvfp4_spec:
  element_format: "E2M1 (1 sign + 2 exponent + 1 mantissa = 4 bits)"
  block_size: 16
  block_scale_format: "E4M3 (1 sign + 4 exponent + 3 mantissa = FP8)"
training_recipe:
  outlier_bounding: "Random Hadamard Transforms (RHT)"
  quantization_scheme: "two-dimensional (per-row + per-column)"
  forward_pass: "round-to-nearest (RTN)"
  backward_pass: "stochastic rounding"
  update_pass: "stochastic rounding"
  high_precision_layers: "embeddings + final projection + norms (configurable)"
validation:
  largest_run: "12B model / 10T tokens (longest 4-bit documented)"
  baseline_match: "training loss + downstream accuracies comparable to FP8"
  speedup: "4.2x over BF16 (Quartet II benchmark on Blackwell)"
hardware_target: "NVIDIA Blackwell PRO 6000 96GB GDDR7 (M044 substrate)"
recipe_variants_available:
  - NvidiaCanonical (RHT + 2D + SR + selective-HP)
  - QuartetII (MS-EDEN 2x-lower-error SR)
  - FourOverSix (adaptive block scaling for near-maximal values)
  - nGPT (hyperspherical constraint, no RHT needed)
  - Custom (operator-defined)
typed_mirror_crate: sovereign-nvfp4-runtime-mirror
catalog_status:
  sovereign_os: 76/76 milestones
  selfdef: 44/44 milestones
  combined: 120 milestones
```
