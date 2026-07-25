# SDD-401 — ChromoFold GPU hotswap: fold-the-model decode-in-GEMM + folded KV (DESIGN)

> Status: **design — positioning + phased plan** (no binding code this session; each build phase is its own gated PR).
> Owner: operator-directed 2026-07-25 (verbatim: *"CPU is just the default but we can add an hotswap to GPU mode... this is the whole purpose of ChromoFold using the GPU to do magic. which is why I asked if we can fold the model itself"* → *"continue"*).
> Mandate module: **E11.M401**.
> Number band: **400–499** per SDD-100 (the `chromofold-integration` session band; this SDD **extends SDD-400** into the compute backend SDD-400 had scoped *out*). Authored from the `control-bits` branch (`claude/glm-colibri-sovereign-os-*`) as an operator-directed cross-session extension of SDD-400 — recorded here per the parallel-session protocol (SDD-981/982).
> Stage: **design** (positioning + phased plan; the CPU-verifiable scaffolding phases are agent-buildable, the GPU link is SAIN-gated).
> Opt-in: **true — OFF BY DEFAULT.** The CPU Rust engine stays the default + the correctness oracle; the GPU path is a hotswap enabled only under an explicit opt-in (the `linked` feature + a runtime GPU-mode flag). A box with no ChromoFold checkout / no GPU behaves exactly as today.

## Mission

Give sovereign-os's **own** inference engine (`sovereign-quant-model` → `sovereign-decoder-stack` → `sovereign-mha-block`, today 100% CPU Rust) an **opt-in GPU execution mode** in which the model runs **GPU-resident on SAIN-01's Blackwell tier**, with its weights and KV **folded** — stored compressed and **decoded inside the consuming kernel** (ChromoFold's decode-and-consume thesis, P3), so no dense weight/KV buffer is ever materialized. This is the operator's *"fold the model itself"* — the sovereign path to a usable local model (10×+ tok/s from GPU residency; a bigger / less-quantized model fit via folding), on **our engine + our ChromoFold**, with **no external vLLM/llama.cpp serving dependency**.

The CPU path is not replaced — it becomes the always-available default and the **bit-exact reference oracle** the GPU path must reproduce (PROJECT_SYNC discipline, inherited from SDD-400).

## Why this is net-new here (and distinct from SDD-400)

SDD-400 positioned ChromoFold as an **opt-in complementary** capability and landed **Lane A — the *search* primitives** (`sovereign-chromofold-sys` binding `cf_access`/`cf_rank`/`cf_fm_*`, the CPU-native `FmIndex`, the osctl verb, the cockpit panel, the RAG `PhraseStore` consumer). SDD-400 **explicitly scoped the compute backend OUT** (its Non-goal #2: *"Replacing the existing kv/quant/compress/moe reference controllers with a ChromoFold backend — explicitly out of scope"*).

SDD-401 is the operator-directed **crossing of that boundary** — but as an **opt-in GPU *execution mode*, not a replacement** of the CPU reference controllers, which keep their contracts and remain the default + oracle. The two SDDs compose: SDD-400 = searchable compressed data (CPU, shipped); SDD-401 = the GPU compute path that folds the model for resident inference (design here, GPU build SAIN-gated).

## What "fold the model" means, precisely — and the honest ABI readiness

Folding = ChromoFold stores the already-quantized tensor in its compressed+addressable form and the **consuming CUDA kernel decodes each value in-register as it multiplies** (P3). Folding is **lossless over the quantizer** (P4) — it does not change model accuracy; it removes the dense intermediate from VRAM and lets a bigger/less-quantized model fit. Two folds, **different ABI readiness** (verified against `../chromoFold/include/chromofold/chromofold.h` v0, 2026-07-25):

| Fold | sovereign-os hook | ChromoFold C ABI | Readiness |
|---|---|---|---|
| **Folded KV attention** (8× KV VRAM) | `sovereign-mha-block` attention + `KvStore` | **`cf_kv_attn_fused_async`** (exported; `cf_kv_attn_dense_async` is the verification reference) | **ABI-ready** — bindable now |
| **Folded embedding gather** | `sovereign-quant-model` embedding lookup | **`cf_embedding_gather_async`** (exported) | **ABI-ready** |
| **Folded weights — decode-in-GEMM** (10.6× weight VRAM; *"fold the model itself"*) | `sovereign-linear::Linear` matmul over `QuantMatrix` | **not exported** — the 10.6× `fused_matmul`/`cf_bh_decode_at` is a benchmarked kernel, **not** a stable C ABI entry | **ChromoFold-side prerequisite**: export a `cf_gemm_decode_async`-class entry first (Q-401-A) |

Honest consequence: the **KV fold and embedding fold are wireable now**; the **weight fold — the headline "fold the model" — is gated on ChromoFold exposing a decode-in-GEMM C ABI**, because the sovereign workspace binds only the stable C ABI (SDD-400 rule; `#![forbid(unsafe_code)]` outside the one `-sys` crate). Until then the weight matmul stays on the CPU path even in GPU mode (honest-degrade), and GPU mode's first win is KV + embedding.

## The hotswap — where it hooks

- **`sovereign-linear::Linear`** (matmul over `sovereign_nvfp4_runtime::QuantMatrix`): today CPU, **transient dequant → matmul** (the exact dense intermediate decode-in-GEMM eliminates). The GPU-mode branch routes this through the folded-weight kernel (once Q-401-A lands).
- **`sovereign-mha-block`** attention + `KvStore { Full | Quant }`: the GPU-mode branch serves attention via `cf_kv_attn_fused_async` over folded pages instead of `materialize()`-then-dense-attention.
- **`sovereign-quant-model::forward`**: gains a mode selector (CPU default / GPU opt-in); the decode loop is otherwise unchanged.
- **`sovereign-chromofold-sys`**: extends the OFF-by-default `linked` FFI carve-out to mirror the **compute** headers (`cf_kv_attn_fused_async` + `cf_embedding_gather_async` now; the weight-GEMM entry when exported) — the search-only binding SDD-400 landed grows the compute entries, still `unsafe`-quarantined.
- **`sovereign-chromofold`**: the safe wrapper gains the GPU-mode surface + host→device marshalling, honest-degrade (`Unavailable` unlinked / `NotImplemented` until the marshalling + GPU link land, Q-401-D).

## Phased plan (each phase its own PR + gate; inherits opt-in/off-by-default + R10212/SB-077)

1. **This SDD (design)** — positioning + plan; no code. *(this session)*
2. **GPU-mode seam in the engine (CPU-verifiable).** Add the mode selector to `sovereign-quant-model`/`-mha-block` + a `GpuFold` trait the CPU path implements trivially (identity to today) — so the hotswap plumbing exists with the **CPU path as the verified default**, zero behaviour change off-mode. Unit-tested on CPU; no GPU, no `unsafe`.
3. **Bind the compute C ABI (CPU-verifiable seams).** Extend `sovereign-chromofold-sys` to the exported compute entries (`cf_kv_attn_fused_async`, `cf_embedding_gather_async`) behind `linked`; add the null-arg + header-seam conformance (the SDD-400 / SDD-724 pattern — real `.so` ABI validated without a GPU via the `null_arg_contract`).
4. **Folded-KV attention GPU path.** Wire `cf_kv_attn_fused_async` into `sovereign-mha-block`'s GPU-mode attention; verify **bit-exact vs the CPU `KvStore` oracle** (`cf_kv_attn_dense_async` as the cross-check) — SAIN-gated for the live GPU run; the seam + marshalling are CPU-testable.
5. **Folded weights — decode-in-GEMM.** *Gated on Q-401-A* (ChromoFold exports the GEMM C ABI). Wire it into `sovereign-linear::Linear`'s GPU-mode matmul; bit-exact vs the CPU dequant→matmul oracle; the 10.6× the operator asked for.
6. **Measure (P10/P7).** On SAIN-01: real device VRAM (`cudaMemGetInfo`) + **tok/s** dense-CPU vs folded-GPU on a real model, with the reproducibility envelope. This is the decisive proof ("10× tok/s and a bigger model fits at equal VRAM") — SAIN-gated.
7. **Surface.** osctl `chromofold gpu-mode …` (read-only status) + a cockpit tile; the exec-rail chain only if a mutating verb is added (CLAUDE.md "new osctl verb carries a chain").

## Honest scope, gates, risks

- **The 1→10+ tok/s comes from GPU residency, not folding.** Folding's job is to make a *good* model *fit* GPU-resident (and to enable deep context via the KV fold); the speed is the GPU. Both land together in GPU mode — stated so no one reads folding as a speed trick (it is compute-for-memory; on CPU it would be a net loss — P1).
- **Weight fold is prerequisite-gated** (Q-401-A) on ChromoFold's side; KV + embedding folds are ready. GPU mode ships useful before the weight fold lands.
- **CPU path is the oracle.** Every GPU kernel output MUST be bit-exact (KV/embedding) or within the measured quantizer tolerance vs the CPU reference before any timing is trusted (PROJECT_SYNC; the KV attention's int4 tolerance is the same one ChromoFold's own M9 frontier study measured — a tolerance gate, not `==`, for the lossy-quant path).
- **GPU verification is SAIN-gated.** The seam, FFI binding, marshalling, and dispatch are agent-buildable + CPU-verifiable here; the real `nvcc` link + host→device round-trip + bit-exact-vs-oracle + tok/s run on SAIN-01's Blackwell tier. No blind CUDA is shipped as "verified" (per the synthetic-tests-aren't-verification discipline).
- **Off-by-default end to end.** No default profile enables GPU mode; a box without a ChromoFold checkout / GPU / `libchromofold` (still pre-M1 on the device path, SDD-400 Q-400-G) behaves byte-identically to today.
- **`unsafe` stays quarantined** in `sovereign-chromofold-sys` behind `linked`; the rest of the 721-crate `#![forbid(unsafe_code)]` core never sees a raw pointer.

## Open questions (operator / cross-repo decisions before the gated phases)

| Q | Question | Status |
|---|---|---|
| Q-401-A | ChromoFold exports a **decode-in-GEMM C ABI** (`cf_gemm_decode_async`-class) so the weight fold — *"fold the model itself"* — is bindable, not just a benchmark kernel? | **open — ChromoFold-side prerequisite** (the KV/embedding folds are already exported; the 10.6× weight kernel is not). Blocks phase 5, not phases 2–4. |
| Q-401-B | GPU tier placement: which SAIN card backs GPU mode by default — Oracle (RTX PRO 6000 96 GB) for large models, or the 4090/5090 for smaller? A profile knob (`profiles/runtime/*`) or a runtime flag? | open — recommend a `profiles/runtime` binding mirroring `high-concurrency-burst` / `deep-context-synthesis`. |
| Q-401-C | Provenance for GPU mode: link `../chromoFold`'s CUDA (provenance-A) vs a native-Rust CUDA port (provenance-B extension)? Inherits SDD-400 Q-400-F (the config-card). | open — recommend provenance-A (bind the proven kernels) for GPU mode; the CPU `FmIndex` (provenance-B) already covers the search lane. |
| Q-401-D | Host→device marshalling ownership: does `sovereign-chromofold` own device buffers (weights/KV uploaded once, resident) or per-call? (P5 device-native — resident is correct; per-call defeats the fold.) | recommend resident (upload-once, decode-many) — the fold only pays if the compressed tensor stays on-device. |
| Q-401-E | Gate GPU mode on `libchromofold` reaching M1 on the device path (SDD-400 Q-400-G)? | recommend yes — de-facto already, via the OFF-by-default `linked` feature + `NotImplemented` host path until phase 4/5. |

## Build status (2026-07-25 — phase 2 landed)

**Phase 2 (GPU-mode seam) shipped** (operator: *"I want it. go"*). CPU-verifiable, no `unsafe`, CPU path untouched off-mode:

- **`sovereign-quant-model`** gains the seam: an `ExecMode { Cpu (default) | GpuFold }` selector, a `FoldBackend` plug-point trait (+ `FoldCaps { weights, kv, embedding }`), the `QuantModel.exec_mode` + `fold_backend` fields with `with_exec_mode`/`set_exec_mode`/`exec_mode()`/`set_fold_backend`/`fold_backend_status()` accessors, and a `QuantModelError::GpuFoldUnavailable` variant.
- **`forward()` honest-degrades**: selecting `GpuFold` returns `GpuFoldUnavailable` (with a precise reason — backend state + which later phase wires the routing) instead of silently running the CPU path under a GPU claim. The default `Cpu` path is **byte-identical** to before (proven by `cpu_mode_generation_is_unchanged_by_an_attached_backend` — attaching a backend while in `Cpu` mode yields identical generation).
- **Verified**: `cargo test -p sovereign-quant-model` (16 pass, incl. 4 new seam tests) + `cargo clippy -D warnings` + `cargo fmt --check` clean; dependents (`sovereign-gatewayd`, `sovereign-llm`) `cargo check` clean (additive API); `tests/lint/test_gpu_fold_seam_contract.py` (4) pins the seam + the honest-degrade property.

**Not built (later gated phases, per the plan above):** binding the compute C ABI into `sovereign-chromofold-sys` (phase 3), the folded-KV GPU attention path (phase 4), decode-in-GEMM (phase 5, gated on Q-401-A), and the SAIN measurement (phase 6). No GPU/`unsafe`/marshalling landed this phase — the seam is the plug-point those phases fill.

## Cross-references

- **SDD-400** (`docs/sdd/400-chromofold-compressed-domain-integration.md`) — the positioning + Lane A (search) this extends; the `-sys`/wrapper/root-env/honest-degrade pattern reused; SDD-400 Non-goal #2 is the boundary SDD-401 deliberately crosses (opt-in execution mode, not controller replacement).
- **Engine crates (the hotswap hooks):** `crates/sovereign-quant-model`, `sovereign-decoder-stack`, `sovereign-mha-block`, `sovereign-linear`, `sovereign-nvfp4-runtime`.
- **ChromoFold C ABI (the fold kernels):** `../chromoFold/include/chromofold/chromofold.h` (`cf_kv_attn_fused_async`, `cf_kv_attn_dense_async`, `cf_embedding_gather_async`); `include/chromofold/kv_cuda.h` (`cf_kv_paged_attention_async`); `../chromoFold/specs/` (constitution P1–P10 — esp. P3 decode-in-consumer, P4 lossless-over-quant, P10 workload-not-ratio); `docs/PROJECT_SYNC.md` (the bit-exact oracle discipline).
- **SAIN-01 hardware** (`profiles/runtime/high-concurrency-burst.yaml`, `deep-context-synthesis.yaml`): RTX PRO 6000 Blackwell 96 GB + RTX 5090 32 GB + RTX 4090 24 GB — the GPU tier this targets; `deep-context-synthesis` already calls for *"KV cache compressed"* (the folded-KV win's home).
- **SDD-724** — the "only the hardware step is gated; pure seams are CI-tested" split reused for the SAIN-gated phases.
- Hard rules: R10212 (web never arbitrarily mutates), SB-077 (never fabricate), the opt-in-off-by-default standing directive, PROJECT_SYNC bit-exact-vs-oracle.
