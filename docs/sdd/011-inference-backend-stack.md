# SDD-011 — Inference backend stack (resolves Q-017)

> Status: **review** — research-grade SDD + concrete scaffold; operator locks at a later gate
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none
> Resolves: **Q-017** (inference-backend stack — operator-flagged LocalAI concern)
> Derived from: info-hub L1 syntheses (BitNet b1.58 / DFlash / Zen 5 / SAIN-01 spec); SDD-005 (sain-01 profile hardware target); operator limit-continuation directive (info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening-limit-continuation.md`)

## Problem

The operator's overnight directive (verbatim):

> "I dont even know if we can stick with LocalAI I think would limite us, but you will find the answers and the solutions."

LocalAI is a unifying abstraction (single OpenAI-compatible API, multi-backend dispatch). For a general-purpose deployment this is excellent ergonomics. For SAIN-01 — where the architectural value comes from **directly exploiting hardware-native idioms** (Zen 5 single-cycle 512-bit AVX-512 + VNNI for ternary inference on CPU; Blackwell + 4090 for GPU; VFIO sandbox; DFlash block-diffusion drafts on code/math) — an abstraction layer can become friction:

- LocalAI's backend matrix may not expose `bitnet.cpp`'s I2_S/TL2 kernels with Zen-5-specific tuning
- vLLM's DFlash integration uses substrate-specific spec-dec plumbing that LocalAI may flatten
- The Pulse/Weaver/Auditor SRP Trinity wants explicit, observable backend routing — not a black-box dispatcher

This SDD surveys backend candidates, then **proposes a direct-stack architecture** for the `sain-01` profile (no unifying abstraction by default) with an OpenAI-compatible router on top for clients that need it.

## Candidate survey (5 backends + LocalAI baseline)

Each: what it is · best fit · weaknesses for SAIN-01 · score on SAIN-01-specific criteria.

### Baseline — LocalAI (the operator's incumbent concern)

**What.** Multi-backend gateway with OpenAI-compatible API. Routes to llama.cpp / vLLM / etc. under the hood.

**Best fit.** General-purpose dev workstations where backend uniformity > raw exploitation.

**Weakness for SAIN-01.**
- Abstraction can hide bitnet.cpp's specific I2_S/TL2 kernel choice on Zen 5
- DFlash integration is vLLM-native; LocalAI may not expose the draft-model wiring
- The SRP Trinity wants explicit per-tier routing (Pulse=CPU/bitnet, Logic Engine=4090/quantized, Oracle Core=Blackwell/full-precision); LocalAI flattens this

**Verdict.** Acceptable for the `old-workstation` profile (uniformity helps). Not recommended for `sain-01` (loses the architectural advantage).

### Candidate 1 — vLLM (Blackwell + 4090 GPU path)

**What.** Datacenter-grade GPU inference server. Native OpenAI-compatible API. First-class speculative decoding (EAGLE/MEDUSA/DFlash). Tensor-parallel + pipeline-parallel. PagedAttention.

**Best fit.** SAIN-01's **Oracle Core** (Blackwell 96 GB resident; Ling/Nemotron at BF16) and **Logic Engine** (4090 24 GB; quantized mid-scale + DFlash drafts).

**Weakness.** Heavy (Python + CUDA + many deps). Not for CPU-only path. Boot time non-trivial.

**Verdict.** **Primary GPU backend for sain-01**. Required for DFlash integration per E109.

### Candidate 2 — bitnet.cpp (Pulse CCD-0 ternary path)

**What.** Microsoft's official ternary inference framework. TL2 (x86) + I2_S kernels. AVX-512 VNNI accelerated. 5-7 tok/sec at 100B-scale on CPU.

**Best fit.** SAIN-01's **Pulse** module — Zen 5 CCD 0 cores 0-5; `microsoft/bitnet-b1.58-2B-4T` or `microsoft/bitnet_b1_58-3B`.

**Weakness.** Limited model set (Microsoft canon + Falcon3/E variants). No DFlash. No multi-GPU (CPU-native).

**Verdict.** **Required for Pulse** per the SRP Trinity. CPU-only by design.

### Candidate 3 — llama.cpp (GGUF general path)

**What.** Mature CPU + GPU inference for GGUF-quantized models. Wide model support. Vulkan + CUDA + Metal backends. Embedded-friendly.

**Best fit.** Fallback for any model where vLLM+DFlash or bitnet.cpp don't apply. `old-workstation` primary backend.

**Weakness.** Spec-dec less mature than vLLM. No DFlash. Vulkan backend exists but operator has flagged complications.

**Verdict.** **Secondary backend** — recommended on the 4090 for non-DFlash Q4 workloads; **primary for old-workstation**.

### Candidate 4 — SGLang (structured-output / agentic path)

**What.** Newer GPU inference framework. Strong constrained-generation (grammar / JSON-mode / regex). RadixAttention KV-cache sharing.

**Best fit.** Logic Engine's structured-output workloads (parsing + JSON-mode + tool-call extraction).

**Weakness.** Younger ecosystem. DFlash support per Z-Lab docs covers SGLang but less battle-tested than vLLM-DFlash.

**Verdict.** **Conditional secondary** — useful when Logic Engine's workload is parse-heavy. Defer until profile usage data justifies.

### Candidate 5 — Ollama (developer-experience path)

**What.** Go-based, simple CLI. Wraps llama.cpp under the hood. OpenAI-compatible API. Trivial model pulls.

**Best fit.** Developer workstation profiles (`developer` reserved slot).

**Weakness.** Wraps llama.cpp — no advantage over llama.cpp direct on sain-01.

**Verdict.** **Defer** unless `developer` profile substantively lands and operator wants Ollama ergonomics there.

## Decision matrix

| Criterion (sain-01 lens) | LocalAI | vLLM | bitnet.cpp | llama.cpp | SGLang | Ollama |
|---|---|---|---|---|---|---|
| AVX-512 VNNI ternary | ✗ (abstracted) | ✗ | ★★★★★ | ★★ | ✗ | ✗ |
| DFlash block-diffusion | ★ (uncertain) | ★★★★★ | ✗ | ✗ | ★★★ | ✗ |
| Tensor-parallel Blackwell+4090 | ★★★ | ★★★★★ | ✗ | ★★★ | ★★★★ | ★★ |
| Constrained / structured output | ★★★ | ★★★ | ✗ | ★★ | ★★★★★ | ★★ |
| VFIO sandbox compat (4090 isolated) | ★★★★ | ★★★★★ | n/a (CPU) | ★★★★ | ★★★★ | ★★★★ |
| Pulse latency (sub-ms branching) | ✗ | ✗ | ★★★★★ | ★★★ | ✗ | ✗ |
| Operator-direct observability | ★ | ★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★ |
| Sovereignty (no phone-home) | ★★★ | ★★★★ | ★★★★★ | ★★★★★ | ★★★★ | ★★★★ |
| Q-017 alignment | poor fit | strong | strong | strong | conditional | defer |

## Recommendation — direct stack, no unifying abstraction (for `sain-01`)

```
                            sovereign-os router (thin)
                            scripts/inference/router.py
                            (OpenAI-compatible client surface)
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
     ┌──────────────────┐  ┌──────────────────┐    ┌──────────────────┐
     │  Pulse (CCD 0)   │  │ Logic Engine     │    │  Oracle Core     │
     │  bitnet.cpp      │  │  vLLM on 4090    │    │  vLLM on Blackwell│
     │  cores 0-5 pin   │  │  (VFIO bind 8GB+)│    │  (BF16 full)     │
     │  TL2 kernels     │  │  + llama.cpp     │    │  + DFlash drafts │
     │                  │  │   fallback (Q4) │    │  for code/math   │
     └──────────────────┘  └──────────────────┘    └──────────────────┘
            CPU                   4090 VFIO              Blackwell host
            sub-ms                3-6× DFlash             1M ctx Nemotron
            branching             on code/math            (or Ling MoE)
```

### Why no unifying abstraction by default

- The architectural value of SAIN-01 is **per-tier hardware exploitation**. Hiding the per-tier choice behind LocalAI's dispatcher erases it.
- The thin router we author (`scripts/inference/router.py`) speaks OpenAI-compatible on the client side but routes **deterministically** by request shape (model id, presence of code/math markers, context length) — no black-box backend selection.
- Each backend exposes its own observability surface; the router doesn't hide it.
- A client that wants LocalAI-style uniformity points at the router; clients that want direct backend access bypass it.

### Profile-conditional backend selection

| Profile | Pulse | Logic Engine | Oracle Core | Notes |
|---|---|---|---|---|
| `sain-01` (default) | bitnet.cpp | vLLM (4090 VFIO) + llama.cpp fallback | vLLM (Blackwell) + DFlash | Per Trinity SRP |
| `old-workstation` | n/a (no AVX-512) | llama.cpp (8 GB GPU) | n/a | LocalAI acceptable here for uniformity |
| `minimal` / `headless` (reserved) | n/a | none | none | inference disabled by default |
| `developer` (reserved) | optional | llama.cpp or Ollama | none | dev convenience |

### When LocalAI re-enters

If operator wants a single OpenAI endpoint for non-sovereign-os clients (Cursor / Continue.dev / etc.), LocalAI can run alongside the direct stack as a translation layer — but its own backends are disabled in favor of proxying to vLLM / bitnet.cpp / llama.cpp directly. Trade-off: extra hop, but uniform client API.

## Goals

1. **Honest per-tier backend selection** — each SAIN-01 tier uses the backend that best exploits its hardware.
2. **No hidden dispatch** — the router script is operator-readable; backend selection is deterministic + introspectable.
3. **Substrate-agnostic packaging** — backends install as systemd services or podman containers per substrate decision; the wiring is the same.
4. **Sovereignty preserved** — every backend is operator-pulled (no phone-home; no telemetry to vendor).
5. **DFlash-ready** — vLLM v0.20.1+ pinned; profile lets the operator enable DFlash drafts per Z-Lab's pre-trained checkpoints on resident models.
6. **Old-workstation pragmatism** — for the constrained profile, llama.cpp or optional-LocalAI is fine; no Trinity pretense.

## Non-goals

- Does NOT install or configure model weights; that's E110 + the `models pull` command on `sovereign-osctl`.
- Does NOT decide brand identity for the router (`sovereign-os-router` is the working name; rename optional).
- Does NOT pre-commit to FP4 / FP8 quantization for Blackwell — operator picks per E110 (per Ling vs Nemotron comparison).
- Does NOT replace `sovereign-osctl` for ops; the CLI wraps the inference backends as additional `sovereign-osctl inference ...` subcommands (post-Stage-2 enrichment).

## Open sub-questions

- **Q11-A** — Should the router be Python (fast iteration) or Go (single binary)? Default: Python; revisit if startup-time matters.
- **Q11-B** — Should the router speak the full OpenAI API or just chat-completions? Default: chat + embeddings minimum.
- **Q11-C** — How does the router authenticate? Local-only (`localhost:8080`) vs token-gated for remote? Default local-only.
- **Q11-D** — vLLM in podman vs systemd-native? Podman for VFIO isolation on the 4090; systemd-native for Blackwell host. Default: hybrid.
- **Q11-E** — Should the router emit Prometheus metrics for per-backend selection counts? Yes (Q-013 observability tier).

## Concrete scaffold shipped with this SDD

This PR lands a working scaffold for the direct-stack architecture:

- `scripts/inference/router.py` — thin OpenAI-compatible HTTP router; deterministic backend selection by model-id + request shape
- `scripts/inference/lib/backend.py` — backend interface
- `scripts/inference/backends/bitnet.py` — bitnet.cpp adapter (CPU pin to CCD 0)
- `scripts/inference/backends/vllm.py` — vLLM adapter (CUDA_VISIBLE_DEVICES per tier)
- `scripts/inference/backends/llama_cpp.py` — llama.cpp adapter (GGUF fallback)
- `scripts/inference/start-pulse.sh` — start the Pulse module (bitnet.cpp pinned to CCD 0)
- `scripts/inference/start-logic-engine.sh` — start Logic Engine (vLLM on 4090 via podman + VFIO)
- `scripts/inference/start-oracle-core.sh` — start Oracle Core (vLLM on Blackwell)
- `scripts/inference/INDEX.md` — overview

These scripts are skeletons (configurable; env-var-driven; restart-from-state) — model weights, ports, and quantization knobs come from `sovereign-osctl` config or env vars. Substantive deployment defaults land at Stage 2+.

## Way forward

1. **PR (this commit on main)** — SDD + scaffold.
2. **Operator review** — confirm direct-stack approach OR ask for LocalAI-on-top.
3. **Q-017 closure** — D-NNN entry in `docs/decisions.md` once locked.
4. **Stage 2+** — fill in real model paths + ports + quantization choices; wire `sovereign-osctl inference` subcommand surface; integrate with first-login assistant's "pull a default model" flow.

## Cross-references

- Info-hub `wiki/sources/src-bitnet-b158-ternary-llm.md` — bitnet.cpp foundation
- Info-hub `wiki/sources/src-dflash-block-diffusion-spec-dec.md` — DFlash backend support matrix
- Info-hub `wiki/sources/src-zen5-avx512-single-cycle.md` — Zen 5 substrate enabling Pulse
- Info-hub `wiki/comparisons/cmp-ling-26-flash-vs-nemotron-3-nano-omni.md` — Oracle Core model picks
- SDD-005 `profiles/sain-01.yaml` — hardware target + CCD partition + GPU roles
- SDD-007 `whitelabel/default.yaml` — whitelabel binding (router has its own surfaces if branding matters)
- `sovereign-osctl models` command — model catalog management (Q-019)
- `info-hub raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening-limit-continuation.md` — operator LocalAI concern verbatim
