# SDD-402 — ChromoFold weight decode-in-GEMM C ABI export contract (Q-401-A) (DESIGN)

> Status: **design — export-contract specification** (no binding code this session; this SDD pins the *target* ChromoFold must hit so SDD-401 phase 5 becomes bindable).
> Owner: operator-directed 2026-07-25 (verbatim: *"go"* → then chose **"Spec the Q-401-A export contract"** from the offered next-moves). Resolves the **Q-401-A** open question SDD-401 left as the phase-5 blocker.
> Mandate module: **E11.M402**.
> Number band: **400–499** per SDD-100 (the `chromofold-integration` session band; extends SDD-401's Q-401-A). Authored from the `control-bits` branch (`claude/glm-colibri-sovereign-os-*`) as an operator-directed cross-session extension — recorded per the parallel-session protocol (SDD-981/982).
> Stage: **design** (a contract spec + verification plan; no sovereign code and no ChromoFold code lands here — the ChromoFold-side implementation + the SAIN GPU run are downstream).
> Opt-in: **true — OFF BY DEFAULT.** This spec inherits SDD-401's posture end to end: the CPU Rust engine stays the default + the bit-exact oracle; the weight-fold GPU path is a hotswap behind the `linked` feature + a runtime GPU-mode flag; a box with no ChromoFold checkout / no GPU behaves exactly as today.

## Mission

SDD-401 landed the CPU-verifiable arc of the GPU-fold hotswap (phases 1–4: the top-level exec-mode seam, the compressed-KV compute C-ABI binding, and the folded-KV attention seam in `sovereign-mha-block`). Its **phase 5 — the headline *"fold the model itself"*, weight decode-in-GEMM (10.6× weight VRAM)** — is blocked on **Q-401-A**: the sovereign workspace binds only ChromoFold's **stable, versioned C ABI** (`include/chromofold/chromofold.h`), and the weight-decode GEMM is **not in it**.

This SDD **specifies the exact export contract** ChromoFold must add to `chromofold.h` so `sovereign-chromofold-sys` can bind the weight fold the same disciplined way it already binds the KV/embedding folds — a precise, verifiable target, not a vague "expose a kernel". It is the sovereign-side half of a cross-repo contract; the ChromoFold-side implementation (promoting the entries to the header + the SAIN GPU qualification) is downstream and hardware-gated.

## The gap, verified (research-first, 2026-07-25)

The decode-in-GEMM kernels **already exist and already have C linkage** — in `src/cuda/fused_matmul.cu`, not in the stable header:

```c
// src/cuda/fused_matmul.cu — present today, C-linkage, but NOT in chromofold.h
extern "C" cf_status cf_fused_matmul_async(
    const uint32_t *words, const int32_t *block_off, const int32_t *lut,
    int maxlen, int block, const float *x, float *y, int B, int M, int K,
    float scale, int zero, void *stream);              // decode-in-register → GEMM (the 10.6× thesis op)

extern "C" cf_status cf_dense_matmul_async(
    const uint32_t *words, const int32_t *block_off, const int32_t *lut,
    int maxlen, int block, const float *x, float *W, float *y, int B,
    int M, int K, float scale, int zero, void *stream); // decode → dense W buffer → plain GEMM (reference)
```

`include/chromofold/chromofold.h` (ABI v0) exports `cf_access_async`, `cf_rank_async`, `cf_embedding_gather_async`, `cf_kv_attn_fused_async`, `cf_kv_attn_dense_async` — **no `*_matmul_async`**. So the weight fold is a *benchmark* entry, not a *contract* entry. `grep -n "matmul" include/chromofold/*.h` → empty; the functions are reachable only by linking the object directly, which the sovereign rule (bind the stable header only) forbids.

**Q-401-A is therefore small and concrete:** promote these two already-shaped, already-`cf_status`, already-`stream`-taking functions into `chromofold.h` under the versioned ABI — exactly mirroring the **fused + dense-reference pair** pattern the header already uses for KV (`cf_kv_attn_fused_async` production / `cf_kv_attn_dense_async` verification). No new kernel work; a header + ABI-version step + a null-arg conformance entry.

## The export contract (what ChromoFold must add to `chromofold.h`)

1. **Two entries, the fused/dense pair** (mirroring the KV precedent):
   - `cf_fused_matmul_async(...)` — the production **decode-in-GEMM**: int4 block-Huffman weights decoded in-register during the multiply; **no dense `W` ever materialized** (the VRAM win, P3 decode-in-consumer).
   - `cf_dense_matmul_async(...)` — the **bit-exact verification reference**: decode to a dense `W` buffer, then a plain GEMM. Same float ops in the same k-order → agrees with the fused path **bit-for-bit** ("fusion is numerically free", per the kernel's own contract comment). This is the on-device oracle the fused path is checked against.
2. **Stable argument semantics** (the block-Huffman int4 weight format — already the kernel's ABI):
   - `words` / `block_off` / `lut` / `maxlen` / `block` — the compressed weight tensor: packed code `words`, per-block bit offsets `block_off`, the Huffman `lut`, max code length `maxlen`, elements-per-block `block`. Decoded via `cf_bh_decode_at`.
   - `scale` / `zero` — the affine dequant params: `w = (decoded_symbol - zero) * scale`.
   - `x` (`[B×K]`) input activations, `y` (`[B×M]`) output, `B`/`M`/`K` the GEMM dims, `stream` the CUDA stream (`void *`, `nullptr` = default). `cf_dense_matmul_async` additionally takes `W` (`[M×K]` scratch) for the reference decode.
   - Return `cf_status` (the header's existing status enum; non-zero = failure, never a partial write).
3. **ABI versioning**: adding entries is **additive** — bump `CHROMOFOLD_ABI_VERSION` 0 → 1 (sovereign reads it at bind time; `sovereign-chromofold`'s `CapabilityDescriptor.abi_version` mirrors it, and the two new capabilities join the descriptor exactly as the KV pair did in SDD-401 phase 3).
4. **Capability metadata**: `packaging/chromofold_capability.json` gains two entries (`weight_gemm_fused` / `weight_gemm_dense_reference`, header `chromofold.h`) so the sovereign-side mirror (10 caps today → 12) stays a faithful reflection of the native source-of-truth.
5. **No-GPU conformance**: a null-arg contract entry (the SDD-400 / SDD-724 pattern) so the real `.so` ABI is validatable without a GPU — the same way `sovereign-chromofold-sys`'s `linked`-feature check already type-checks the KV FFI in CI.

## What sovereign-os does once the contract lands (SDD-401 phase 5 preview — NOT this SDD)

- `sovereign-chromofold-sys`: add the two `extern "C"` decls + safe `unsafe fn` wrappers behind the OFF-by-default `linked` feature (mirrors phase-3's KV binding exactly; `#[allow(clippy::too_many_arguments)]` for the C-dictated 13/14-arg shape).
- `sovereign-chromofold`: `CapabilityDescriptor` mirrors the two new caps (12 total); `abi_version` tracks the v1 bump.
- `sovereign-linear::Linear`: a `WeightFoldBackend`-style seam (mirroring SDD-401 phase-2 `FoldBackend` / phase-4 `KvFoldBackend`) so GPU-mode matmul routes through the folded-weight kernel, with the **CPU dequant→matmul path as the bit-exact oracle** and honest-degrade (`GpuFoldUnavailable`) when no backend/GPU.
- Bit-exact verification: `cf_dense_matmul_async` vs `sovereign-linear`'s CPU `QuantMatrix` dequant→matmul, then `cf_fused_matmul_async` vs `cf_dense_matmul_async` — the two-hop oracle chain, the live run **SAIN-gated** on Blackwell.

## Honest scope, gates, risks

- **This SDD writes no code** — sovereign or ChromoFold. It is the contract other work targets. The sovereign phase-5 binding is CPU-verifiable once the header exists; the kernel promotion is ChromoFold's; the GPU qualification is SAIN-01's.
- **The contract is minimal by design.** The kernels exist and are battle-tested as benchmarks; Q-401-A is a *promotion to the stable ABI* (header + version + capability.json + conformance), not new CUDA. This keeps the cross-repo ask small and reviewable.
- **Bit-exactness is the acceptance gate**, not throughput. The fused path MUST equal the dense reference bit-for-bit (weights are lossless-over-quantizer, P4) before any tok/s number is trusted (PROJECT_SYNC). Throughput is SDD-401 phase 6.
- **Off-by-default end to end** — inherited from SDD-401; a box without ChromoFold / GPU / `libchromofold` behaves byte-identically to today, and `unsafe` stays quarantined in `sovereign-chromofold-sys` behind `linked`.
- **Naming**: the spec recommends **promoting the existing names** (`cf_fused_matmul_async` / `cf_dense_matmul_async`) rather than the placeholder `cf_gemm_decode_async` SDD-401 Q-401-A sketched — they already carry the right shape, `cf_status` return, and `stream` arg, so promotion is lower-churn than a rename. (Open sub-question Q-402-A below.)

## Open questions (ChromoFold-side / cross-repo)

| Q | Question | Recommendation |
|---|---|---|
| Q-402-A | Promote the existing `cf_fused_matmul_async` / `cf_dense_matmul_async` names, or rename to the `cf_gemm_decode_async` family SDD-401 sketched? | **Promote existing** — right shape already; a rename is churn for no ABI benefit. sovereign binds whatever name the header ships. |
| Q-402-B | ABI-version bump (0→1) additive, or a parallel `chromofold_compute.h` split like `chromofold_search.h`? | **Additive bump in `chromofold.h`** — the KV compute entries already live there; keep the compute surface together. |
| Q-402-C | Block-Huffman format stability: is the `words/block_off/lut/maxlen/block` layout frozen, or still moving? A moving format can't be a stable ABI. | ChromoFold to confirm the format is frozen at ABI v1 (the sovereign `QuantMatrix` producer must emit exactly this layout — a phase-5 marshalling concern, Q-401-D). |
| Q-402-D | Does the fused kernel accept the same `QuantMatrix` block layout sovereign already produces, or is a transcode needed at upload? | Determine at phase-5 marshalling; if a transcode is needed it is upload-once (resident), per SDD-401 Q-401-D. |

## Cross-references

- **SDD-401** (`docs/sdd/401-chromofold-gpu-hotswap-fold-the-model.md`) — the GPU-fold hotswap this unblocks; **Q-401-A** is the open question this SDD resolves into a concrete contract; phase 5 is the consumer.
- **SDD-400** (`docs/sdd/400-chromofold-compressed-domain-integration.md`) — the `-sys`/wrapper/stable-header-only binding rule + honest-degrade pattern this contract is designed to fit.
- **ChromoFold (source-of-truth):** `../chromoFold/src/cuda/fused_matmul.cu` (`cf_fused_matmul_async` / `cf_dense_matmul_async` / `cf_bh_decode_at` — the kernels to promote); `../chromoFold/include/chromofold/chromofold.h` (ABI v0 — the header to extend); `../chromoFold/packaging/chromofold_capability.json` (the capability manifest to grow); constitution P3 decode-in-consumer / P4 lossless-over-quant / P7 measured-not-asserted.
- **Sovereign hooks (phase-5 consumers):** `crates/sovereign-linear` (the matmul seam), `crates/sovereign-chromofold-sys` (the FFI binding), `crates/sovereign-chromofold` (the safe wrapper + descriptor), `crates/sovereign-nvfp4-runtime::QuantMatrix` (the weight producer).
