# Evaluation — ChromoFold fold techniques measured against a real GLM-5.2 expert bank

> Operator ask (verbatim, 2026-07-27): *"if we could 'only' push that to 10x at every
> level with chromoFold technique and Super-Elastic toggle too"* → after a first
> negative pass: *"that's not enough. I know we can do something with those tensors...
> we can fold them, we can compress them with chromoFold techniques"*.
>
> Status: **MEASURED — first ChromoFold fold measurement on real model weights.**
> Every number below is measured on `ai-workstation` against the resident
> `/nvme/glm52_i4` container. Nothing here is an estimate. Reproduce with
> [`scripts/inference/chromofold-fold-bench.py`](../../scripts/inference/chromofold-fold-bench.py).
>
> The operator was right: the tensors do compress. The first pass measured it with the
> wrong tool (zlib over byte-expanded nibbles) and understated the result by 16%.

## Verdict (TL;DR)

**One of ChromoFold's two weight-fold lanes pays, and it pays enough to matter.**

| Lane | Technique | Verdict | Measured |
|---|---|---|---|
| **M6 block-Huffman** (`cf_bh_decode_at` / `cf_fused_matmul_async`) | entropy-code the int4 symbol stream, decode in-register during GEMM | **WORKS — build it** | **1.35× lossless**, 358 GB → **266 GB** |
| M20 grouped-delta / M21 super-elastic | shared reference + factored residual across a group of experts | does not pay | **0.99×** vs coding each expert alone |

The M6 lane is what turns GLM-5.2 from "does not fit" into "fully resident": 358 GB
exceeds this box's ~328 GB of VRAM+RAM; 266 GB does not. **That takes NVMe out of the
decode path**, which per Colibri's own ladder is the difference between the ~1.8 tok/s
CPU-streaming rung and the 5.8–6.8 tok/s full-residency rung.

The grouping lane is dead for a trained MoE expert bank, and the reason is structural
rather than incidental — see [§3](#3-why-the-grouping-lane-cannot-work-here).

## 0. The box and the container (verified 2026-07-27)

| Fact | Value | Consequence |
|---|---|---|
| GPUs present | RTX PRO 6000 Blackwell 96 GB (`01:00.0`) + RTX 5090 32 GB (`03:00.0`) | 128 GB VRAM |
| GPU driver loaded | **`nouveau`** — no `/dev/nvidia*`, no `nvidia-smi`, no `nvcc` | **both cards unusable for compute**; the measured Colibri run was pure CPU |
| CPU / RAM | Ryzen 9 9900X (12c/24t, Zen 5 AVX-512) · 249 GB | ~200 GB pinnable |
| Model | `/nvme/glm52_i4`, 358 GB, 144 shards | on `nvme1n1` — also root + swap |
| Free NVMe | `nvme0n1p3`, 1.8 TB ext4, **unmounted** | Colibri dual-SSD mirror is free bandwidth |
| Quantization | **int4, one F32 scale per row of 6144** (`*.weight.qs` = 2048 scales for 12.58M weights) | **this is the deprecated per-row container, not gs64** |
| MTP heads | `3527131672 / 5366238584 / 1065950496` — exact int8 sizes | speculation works; not the int4-MTP 0%-acceptance trap |

**Container caveat.** Colibri's README warns the per-row int4 mirrors measure ~9pp worse
on quality and are the root cause of the think-mode loops and never-terminating
generations in upstream #455; the `gs64` build cured those. Switching to
`mastouri/GLM-5.2-colibri-int4-g64-with-int8-mtp` is a quality upgrade — but note it
costs some of the 1.35×, because per-row scaling is precisely what makes the symbol
histogram peaky. That is a real trade, not a free win.

## 1. Routing heat — capacity is the only strategy that works

From Colibri's `.coli_usage` (328,416 real routings over 76 layers):

```
experts touched   16,978 of 19,456  (87.3% of the bank ever routed)
top  1% of touched experts carry  12.1% of routings
top 10% of touched experts carry  42.1%
top 20% of touched experts carry  59.2%
80% of routings needs  6,747 experts (~124.5 GB int4)
90% of routings needs  9,400 experts (~173.5 GB int4)
```

**There is no small hot set.** Serving 80% of routings from VRAM would take 124.5 GB —
essentially the entire 128 GB. Colibri's learned pin set is fighting a distribution that
does not concentrate enough to be cached.

Per-layer top-8 share averages 0.237 but ranges from **0.086 at layer 7** (near-uniform)
to **0.481 at layer 19** (sharply concentrated) — so any placement policy should be
per-layer, not global. But the aggregate conclusion stands: **tiering cannot solve this;
only capacity can.** That places the entire burden on the fold ratio, which is why the
rest of this document matters.

## 2. The M6 entropy lane — 1.35× lossless, stable, and cheap to decode

Measured over **201M real weights**, 4 layers × 2 roles × 2 experts:

```
 layer        role  expert    H0 b/w    H1 b/w    ratio
     7   gate_proj       0    2.8765    2.8764   1.391x
     7   down_proj       0    3.0177    3.0176   1.326x
    19   gate_proj       0    2.9156    2.9155   1.372x
    30   gate_proj     128    2.9130    2.9129   1.373x
    60   down_proj     128    3.0157    3.0156   1.326x

AGGREGATE: 2.9619 b/w -> 1.350x lossless
```

Variance is tight — gate/up 1.37–1.39×, down 1.32–1.33×, holding from layer 7 to 60. The
int4 histogram is a clean bell curve over 15 symbols (value 0 never occurs), centred at 8.

**`H1 == H0` to four decimal places.** There is no sequential context to exploit, which
means a *static* canonical Huffman table reaches the entropy floor: no adaptive state, no
context modelling, no sequential dependency. That is the cheapest possible decoder and
maps exactly onto `cf_bh_decode_at` — a pure LUT decode, embarrassingly parallel, ideal
for decode-in-register inside a GEMM (ChromoFold's P3).

### 2a. Block size is a real contract parameter — and small blocks lose

`cf_fused_matmul_async` takes `block` (elements per block) and `block_off` (per-block bit
offsets). With one shared `lut` and a 32-bit offset per block:

```
   block       b/w    ratio   random-access granularity
      64    3.4619   1.155x   64 weights
     256    3.0869   1.296x   256 weights
    1024    2.9931   1.336x   1024 weights
    4096    2.9697   1.347x   4096 weights
   16384    2.9639   1.350x   16384 weights
```

At `block=64` more than 40% of the compression is lost to the offset index. If per-block
*tables* were used instead of a shared LUT (64 bits each), `block=64` measures **0.935× —
it expands the data.**

**Contract consequence for SDD-402:** `block` must be ≥ 1024, and the export contract
should explicitly decouple **coding granularity** (one shared LUT per tensor) from
**addressing granularity** (`block_off` for O(1) random access). This is invisible without
measuring on real weights and should be fed back to the ChromoFold side before the ABI is
frozen.

### 2b. What it buys

```
fixed int4 (today)      358.0 GB   over 328 GB VRAM+RAM  -> disk in the decode path
block-Huffman @4096     266.2 GB   FITS 328 GB           -> disk OUT of the decode path
```

~62 GB of headroom remains for KV, batch and the dense tier. Note it does **not** fit
128 GB VRAM alone — that needs 2.80×, which is out of reach (see §4).

## 3. Why the grouping lane cannot work here

M20/M21 were tested in their strongest available form. Every configuration returns the
same number:

```
configuration                                    mn|Δ|   entropy   M20/nat   M20/base
layer 30 gate_proj, experts 0..23 (by index)     1.399     1.18x     1.17x      0.99x
layer 30 down_proj, experts 0..23 (by index)     1.506     1.14x     1.13x      0.99x
layer  7 gate_proj, experts 0..23 (by index)     1.354     1.19x     1.18x      0.99x
layer 19 gate_proj, experts 0..23 (by index)     1.400     1.18x     1.17x      0.99x
layer 19 gate_proj, 24 HOTTEST (co-routed)       1.398     1.18x     1.17x      0.99x
layer 19 gate_proj, 24 COLDEST                   1.398     1.18x     1.17x      0.99x
```

**0.99× vs baseline everywhere** — marginally worse than coding each expert alone.

The cause is structural:

- **Cross-expert correlation is zero.** `corrcoef ≈ +0.0007`. Co-routed experts are no
  more similar than hot-vs-cold pairs (`mean|a−b|` 2.022 vs 2.025).
- **No permutation alignment.** MoE experts are permutation-symmetric in the intermediate
  dimension, so index-aligned correlation cannot see similarity hiding under a row
  permutation. Tested with 24-dim row signatures: mean best-match cosine **+0.6373**
  against a random-vector null of **+0.6391**. The apparent similarity is entirely the
  expected max-cosine over 2048 random vectors. There is no alignment.
- **Not low-rank within an expert either.** Effective rank for 95% energy is **1227 of
  2048** (a random gaussian needs ~1945). Structure exists but nowhere near enough — a
  rank-*r* fold costs `2nr` and only pays for `r ≪ n/2`.

Routed experts are trained to *differ*; specialization is the mechanism. They behave as
independent draws from a shared bell-shaped marginal. The shared centroid M20 constructs
captures only that marginal — which a per-expert coder already captures for free. Hence
0.99×, and the result is coder-independent: a better entropy coder lifts baseline and
fold equally.

**Where M20/M21 do belong:** LoRA adapter libraries and tied layers — genuinely
near-identical tensors. That is a real fit for sovereign-os's adapter work, just not for
a trained expert bank.

## 4. The ceiling, honestly

Lossless is close to exhausted at 1.35×. `H1 == H0`, cross-expert correlation 0,
permutation alignment at the null, within-expert rank 1227/2048 — every structural axis
probed comes back empty. **1.35× is near the information-theoretic floor for lossless on
this container.**

Going further means changing the *quantizer*, not the codec. The distribution is
bell-shaped and uniform int4 spends codes on tails it barely uses; a Lloyd-Max/companded
3-bit codebook could plausibly match int4's MSE. That is a re-conversion from the FP8
source and a quality question — a different project from binding ChromoFold, and one the
gs64 decision above interacts with.

## 5. What this means for the SDD chain

- **SDD-402's export contract is worth pursuing** — for `cf_fused_matmul_async` /
  `cf_bh_decode_at`, with the §2a block-size correction. SDD-401 phase 5 has a real target.
- **The "10.6× weight VRAM" framing should be retired.** It is an fp16 comparison; against
  an int4 container the measured lossless gain is 1.35×.
- **Drop the grouped-delta lane** from the weight-fold plan for MoE.
- **SDD-400/401 describe ChromoFold as "specified, pre-implementation (M0/M1 skeleton)".**
  That is stale: the checkout carries milestone makefiles through **m21** plus
  `multigpu_cuda_runtime.h`, `production_scheduler.h`, `device_kv_dataplane.h`,
  `disaggregated_serving.h`, `adaptive_compression.h`, `qualification.h`. An inventory pass
  is owed before any further design. Drift runs both ways: ChromoFold's M21 doc still says
  "SDD-401/402 are not yet written" (they were, 2026-07-25).
- **Q-401-A remains genuinely open.** `grep -n matmul include/chromofold/*.h` is still
  empty; `cf_fused_matmul_async` lives only in `src/cuda/fused_matmul.cu`, and the
  capability manifest is still `abi_version: 0` with 11 capabilities.

## 6. Where the throughput actually is

Folding buys *fit*, not speed. At Colibri's best published result (6.84 tok/s on 6× RTX
5090, full residency) the engine moves ~21 GB of weights per token ≈ 144 GB/s — against a
single 5090's ~1.79 TB/s. That is ~4–8% of the memory roofline of *one* card, across six.
The 10× the operator asked for is inside the roofline; it needs engineering, not new physics:

| Lever | Honest factor | State here |
|---|---|---|
| NVIDIA driver + CUDA (128 GB VRAM enters play) | 2–4× | **not done — the box is on nouveau** |
| Full residency (the M6 fold makes 266 GB fit 328 GB) | step-change | measured, buildable |
| CUDA Graphs + on-device residual (no per-layer host sync) | 1.5–3× | Colibri has `COLI_CUDA_PIPE=2` |
| Fused int4 decode-in-GEMM (M6) | 2–4× | the surviving ChromoFold lane |
| Expert-parallel placement across PRO 6000 + 5090 | 1.3–1.8× | no NVLink → exchange activations, not tensors |
| MTP speculation | 2–2.8× | int8 heads confirmed present |

## 7. What actually happened when we ran it (same day, driver installed)

Section 6's table was written **before** the NVIDIA driver was installed. Every factor in it
was an estimate; all of them were then measured, and most were wrong. Recorded here so the
estimates are not mistaken for results.

### Measured progression

| config | tok/s | cumulative |
|---|---|---|
| CPU-only baseline (nouveau) | 1.82 | 1.00× |
| driver + CUDA 13.3 on 2× Blackwell | 1.82 | precondition only — **0×** |
| `CUDA_DENSE=1 COLI_CUDA_ATTN=1` + `COLI_CUDA_MTP=1` | 2.57 | 1.41× |
| max expert residency (`PIN_GB=195`) | **3.02** | **1.66×** |
| `COLI_GROUP_ASYNC=1` (CPU/GPU expert overlap) | — | +1.04× |

### Everything else measured negative

| lever | §6 estimate | measured |
|---|---|---|
| driver alone | 2–4× | **0×** — it is a precondition, not a multiplier |
| CUDA Graphs | 1.5–3× | **1.05×** — empty launch is 2.05 µs; launch overhead is not the bottleneck |
| fused decode-in-GEMM (M6) | 2–4× | **33× SLOWER** — ChromoFold's own kernel, GLM shape, B=1, on sm_120 |
| expert-parallel placement | 1.3–1.8× | **1.00×** — `residual P2P 0.000s / 0 hop`; the topology costs nothing |
| MTP speculation | 2–2.8× | **~1.0×** — 2.13 tok/forward, but the S=4 expert union doubles expert work |

Two hand-written replacement matvec kernels also lost (0.79× and 0.33×), and forcing the int4
tensor-core path changed the kernel by **+1.2%** — it is gated off at r=1 by design.

### The real bottleneck (`PROF=1`)

```
P0-EXEC: routed CPU 10.793s / 40.68 GB/s | routed GPU critical 1.454s
         | router 0.691s | residual P2P 0.000s | orchestration 1.598s
```

The GPU expert kernel is **2.37s of a 30.7s decode** (H2D 168.6 ms + kernel 2007.6 ms + D2H
198.1 ms). The CPU path runs at **40.68 GB/s — near DDR5's ceiling**, so it is not inefficient.
**More than half of all expert work simply lands on the CPU**, because only **7,094 of 19,456
experts fit in 130.8 GB of VRAM at int4**, and each miss costs 464 µs against 46.5 µs on the GPU.

**The constraint is VRAM capacity and nothing else.**

### The number that should have come first

GLM-5.2 reads ~20 GB/token. This card sustains **254 GB/s** on quantised matvec (measured,
`bench-expert-matvec.cu`). So its ceiling here is **12.7 tok/s even with perfect residency,
zero disk and zero CPU fallback**. The 10× target (18.2 tok/s) was **above the model's roofline
from the start** — computable on day one, before any experiment.

### 2-bit was checked from the FP8 source and is dominated

`bench-quant-viability.py` against one `zai-org/GLM-5.2-FP8` shard (the int4 container
double-quantises, so it cannot answer this):

```
scheme                            MB/expert   vs int4   matvec err
int4 per-row (production)             18.90     1.00x       0.1631
2-bit per-row (fmt=3 today)            9.46     2.00x       0.9131
2-bit group-64 uniform                11.80     1.60x       0.7126
2-bit group-64 Lloyd-Max (K=4)        18.87     1.00x       0.3150
3-bit group-64 uniform                16.52     1.14x       0.2468
```

Coarse scales give the size win but destroy quality; a codebook good enough to keep quality
costs exactly what it saves (**18.87 MB — identical to int4**). There is no operating point
where 2-bit helps. Colibri's `fmt=3` is per-row only, so it could not express the grouped
variant anyway.

### Conclusion

**3.02 tok/s (1.66×) is the ceiling of available levers on this box for this model.** The
model is ~3× too large for the VRAM; that is not a tuning problem. GLM-5.2's role here is the
batch deep-synthesis tier its original evaluation called for. For interactive use, a model that
fits VRAM is worth ~30× what any optimisation here achieved — see
[oracle-alternatives-glm47-m3-gptoss-2026-07-19.md](oracle-alternatives-glm47-m3-gptoss-2026-07-19.md)
(gpt-oss-120b, 63 GB, ~94 tok/s projected at the measured 254 GB/s).

Best-known GLM-5.2 config:

```sh
COLI_CUDA=1 CUDA_DENSE=1 COLI_CUDA_ATTN=1 COLI_CUDA_MTP=1 \
COLI_GROUP_ASYNC=1 DIRECT=1 PIPE=1 PIN=auto PIN_GB=195 RAM_GB=230
```

**Upstream bug found:** Colibri skips its OpenMP hot-thread tuning whenever `COLI_CUDA` is set
(`colibri.c:6282`), assuming CUDA means experts run on GPU. Measured false here — only 32% fit
VRAM, so ~10 s of CPU expert work happens anyway, with the thread team parking between regions.
The code's own comment prices that at 66.9s → 20.9s on Zen 5. Not yet filed.

## Reproduce

```sh
scripts/inference/chromofold-fold-bench.py --model /nvme/glm52_i4 --mode all
scripts/inference/chromofold-fold-bench.py --model /nvme/glm52_i4 --mode entropy \
    --layers 7,19,30,60 --roles gate_proj,down_proj --experts 0,128
```

Read-only, pure numpy, no GPU. Honest-degrades (exit 3) when the container or the Warp
checkout is absent. The `group` mode needs the Warp prototype (`WARP_ROOT`).

## Cross-references

- [SDD-400](../sdd/400-chromofold-compressed-domain-integration.md) — positioning; Lane A
  (FM-index search) shipped and unaffected by this result.
- [SDD-401](../sdd/401-chromofold-gpu-hotswap-fold-the-model.md) — the GPU fold hotswap;
  phase 5 is the consumer of the M6 lane.
- [SDD-402](../sdd/402-chromofold-weight-gemm-abi-export-contract.md) — the export
  contract this measurement corrects (§2a) and validates (§2).
- [glm-5.2-colibri-on-sain-01.md](glm-5.2-colibri-on-sain-01.md) — the 2026-07-19
  evaluation closed as operator-rejected on estimated throughput. Its premise (single-digit
  tok/s) was an estimate against a box whose GPUs have never been driver-visible.
- ChromoFold: `docs/m20-grouped-delta-superposition.md`, `docs/m21-super-elastic-recursive-fold.md`,
  `src/cuda/fused_matmul.cu`, `packaging/chromofold_capability.json`.
- Warp prototype: `warp_compress/grouped_delta.py`, `super_elastic.py`,
  `docs/bench_fold_cost_results.md`, `docs/bench_weights_results.md`.
- Hard rules: SB-077 (never fabricate), P7 (measured, not asserted) — this document reports
  the negative results in full.
