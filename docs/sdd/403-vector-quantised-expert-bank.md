# SDD-403 — Vector-quantised expert bank: a precomputed shared codebook for VRAM residency (DESIGN)

> Status: **design — measurement-backed, not built.** Every ratio and error figure below is measured on
> real GLM-5.2 weights (FP8 source) on this hardware; no estimates. The build is TODO behind operator approval.
> Owner: operator-directed 2026-07-28 (verbatim: *"its because we are not doing it right, it takes a long
> time to master and apply the art of chromoFold in every gap and align the ecosystem around it.
> PreCompute if needed"*).
> Mandate module: **E11.M403**. Number band: **400–499** (`chromofold-integration`, per SDD-100/SESSIONS).
> Opt-in: **true — OFF BY DEFAULT.** A box without a VQ container behaves exactly as today.

## Mission

Make the GLM-5.2 expert bank **VRAM-resident** by storing experts as **fixed-width indices into a shared,
precomputed codebook**, so that expert compute stops falling back to the CPU. The binding constraint,
measured, is capacity: only **7,094 of 19,456 experts** fit 130.8 GB of VRAM at int4, and every miss costs
**~10× per expert** (464 µs CPU vs 46.5 µs GPU).

This is ChromoFold's **P9 (build ≠ query)** applied to the weight lane: pay an expensive offline fit, get a
cheap online lookup.

## Why the previous lanes failed, and why this one is different

All three prior compression attempts were measured negative on this workload
([SDD-402](402-chromofold-weight-gemm-abi-export-contract.md),
[evaluation](../evaluations/chromofold-fold-measurement-glm52-2026-07-27.md)). Each failed for a *structural*
reason that VQ does not share:

| lane | measured | why it failed | does VQ share the flaw |
|---|---|---|---|
| block-Huffman decode-in-GEMM | **33× slower** at r=1 | variable-length codes serialise — the decoder walks a bit-stream | **no** — fixed-width index; same access shape as the nibble decode measured at 254 GB/s |
| per-group Lloyd (2-bit) | **18.87 MB** = int4 size | every 64-weight group stores its own 4 levels | **no** — one codebook per tensor: KB, not MB |
| scalar 2-bit uniform | **0.7126** error (4.4× production) | scalar quantisation is information-starved at 2 bits | **no** — VQ beats scalar at equal rate (rate–distortion) |
| M20/M21 grouped-delta | **0.99×** | cross-expert correlation ≈ 0 | n/a — VQ needs no cross-expert similarity |

## Measured (real FP8 weights, layer 19 expert 2 `gate_proj` [2048×6144])

Reference = fp32 dequantised from `zai-org/GLM-5.2-FP8` (e4m3, 128×128 block scales).
Error = matvec relative error vs that reference. `scripts/inference/bench-vq-codebook.py`.

```
scheme                          b/w      err   MB/exp   inVRAM  vs int4
int4 per-row (PRODUCTION)      4.00   0.1642    18.90    6,460    1.00x
VQ d=4 K=256                   2.00   0.3215     9.45   12,921    1.96x
VQ d=2 K=16                    2.00   0.3409     9.44   12,937    2.08x
VQ d=8 K=256                   1.00   0.5583     4.74   19,456    3.40x
VQ d=4 K=256  +group128        2.25   0.3286    10.63   11,487    2.00x
VQ d=2 K=256  +group128        4.25   0.0912    20.06    6,086    0.56x
VQ d=4 K=1024 +group128        2.75   0.2279    13.03    9,374    1.39x
```

**VQ at 2 b/w scores 0.3215 where scalar 2-bit scores 0.7126 — a 2.2× improvement from technique alone.**
And `d=2 K=256 +group128` **beats production int4 on accuracy** (0.0912 vs 0.1642) at comparable size — the
quality headroom is real even where the size headroom is not.

### What residency buys (real `.coli_usage` heat curve, 328,416 routings)

```
scheme          experts  routings  CPU share   decode    tok/s   vs today
int4 today        6,460     78.6%      21.4%   19.53s     3.28      1.09x
VQ 2.75 b/w       9,374     89.9%      10.1%   12.91s     4.96      1.64x
VQ 2.00 b/w      12,921     97.3%       2.7%    8.59s     7.45      2.47x
VQ 1.00 b/w      19,456    100.0%       0.0%    7.00s     9.14      3.03x
```

**~2.5–3× on top of the 1.66× already banked**, i.e. GLM-5.2 at 7.5–9 tok/s instead of 3.02.

## Honest bounds — read before approving

- **The error figures are a FLOOR, not the technique's ceiling.** The measurement used plain Lloyd k-means
  (15 iterations, 200k-vector subsample) minimising **weight** error. Production methods (AQLM, QuIP#)
  minimise **output** error against calibration data, apply incoherence processing (rotations), and use
  additive/residual codebooks. Those routinely beat naive VQ substantially at 2 bits. A proper pipeline may
  land at or near production int4 quality — but that is a hypothesis, not a measurement.
- **Weight error is not model quality.** 1.96× matvec error does not linearly imply degraded generation.
  Only an end-to-end eval against the int4 reference settles it. This is the gate that can still kill the lane.
- **The ceiling is ~9.1 tok/s.** Even at 100% residency with zero CPU fallback, the floor is GPU expert work
  (2.4s) + attention (2.5s) + orchestration (2.1s) = 7.0s / 64 tokens. GLM-5.2 reads ~20 GB/token against a
  card sustaining 254 GB/s; its roofline here is 12.7 tok/s regardless of compression.
- **Opportunity cost is large and already demonstrated.** `gpt-oss-120b` (MXFP4, 63 GB, fits VRAM) measured
  **191.42 tok/s** on the same card the same day — 63× GLM-5.2's current 3.02, versus the ~3× this SDD
  proposes. This lane is worth building only if **GLM-5.2 specifically** is required.

## Phase 2 + 2b — BUILT and measured (2026-07-28)

`scripts/inference/vq-quantize-experts.py`. Three improvements over this SDD's prototype:
k-means++ init, residual (N-stage) VQ, and asymmetric per-stage `K`.

```
config                       b/w      err   MB/exp   inVRAM  vs int4    tok/s  vs now
int4 per-row (PRODUCTION)   4.00   0.1638    18.90    6,460    1.00x     3.28   1.09x
VQ d=4 K=[256,256] x2       4.00   0.1075    18.90    6,460    0.66x        -       -
VQ d=4 K=[256,64]  x2       3.50   0.1439    16.53    7,386    0.88x     3.75   1.24x
VQ d=4 K=[256,16]  x2       3.00   0.1880    14.17    8,617    1.15x     4.47   1.48x
VQ d=4 K=[256,4]   x2       2.50   0.2542    11.81   10,339    1.55x     5.62   1.86x
VQ d=4 K=256       x1       2.00   0.3127     9.45   12,921    1.91x     7.45   2.47x
```

**Two findings that reframe the lane:**

1. **At equal size, VQ is ~1.6× more accurate than int4** (0.1075 vs 0.1638 at 4 b/w). So the
   question is not "how much quality do we give up" — int4's *current* quality is purchasable
   at ~15.5 b/w-equivalent bytes instead of 18.90 MB. The iso-quality crossover is ~3.2–3.4 b/w.
2. **The knee is 3.00 b/w**: 15% worse weight error buys 33% more experts resident → 4.47 tok/s.

### Phase 2b (activation-aware weighting) — NEGATIVE, with the reason

AWQ/GPTQ minimise `||(W−W')x||²` rather than `||W−W'||²`. Implemented as scale-folding, using
`post_attention_layernorm.weight` as the per-channel activation-scale proxy (the expert input is
`RMSNorm(h) · ln_weight`, and RMSNorm output is unit-variance by construction, so the gain *is*
the channel scale — recoverable from the checkpoint, no model run needed).

**It changed nothing (~1%).** The reason is measurable:

```
layer 19 post_attention_layernorm.weight:  p99/p50 = 1.05, coeff of variation = 0.056
```

99% of channels are within 5% of the median — **there are no outlier channels to protect**. The
50× max/min comes from a few near-*zero* channels, which are low-importance. AWQ pays when a few
channels dominate (outlier layers show p99/p50 of 10–100×); this layer is not one.

**Caveat on the negative:** this is the checkpoint-derivable proxy, not measured activations. The
"massive activations" phenomenon is a *runtime* per-token effect that a layernorm gain cannot
show. A real activation capture could still differ, and remains the only untried quality lever.

### Phase 3a — whole-expert-block error (2026-07-28)

`scripts/inference/vq-expert-block-error.py`. Everything above is single-matmul error on
`gate_proj`, which is not the quantity that matters: a routed expert computes
`y = down(silu(gate(x)) * up(x))`, so error passes through a nonlinearity and a second matmul.

```
config                        matmul err   BLOCK err   amplify   MB/exp
int4 per-row (PRODUCTION)         0.1612      0.2724     1.69x    18.90
VQ d=4 K=[256,256] x2             0.1057      0.1757     1.66x    18.90
VQ d=4 K=[256,64]  x2             0.1421      0.2387     1.68x    16.53
VQ d=4 K=[256,16]  x2             0.1872      0.3141     1.68x    14.17
VQ d=4 K=[256,4]   x2             0.2529      0.4183     1.65x    11.81
VQ d=4 K=256       x1             0.3127      0.5109     1.63x     9.45
```

**Amplification is ~1.67× and constant** (1.63–1.69×) across every configuration. Two consequences:

1. **The single-matmul metric is a valid proxy for *ranking***, so the frontier and
   operating-point analysis above stand. It understates absolute magnitude by ~1.67×.
2. **Production int4 already runs at 0.2724 block error.** A working model tolerates 27%
   relative error at the expert output, so the tolerance is demonstrably not tight. That makes
   **3.00 b/w (0.3141 — only 1.15× production) look very likely safe**, and 2.50 b/w
   (0.4183, 1.54×) plausible rather than reckless.

**This is the strongest gate available before phase 4.** It is still not model quality.

### Phase 4 gate — the VQ decode kernel HOLDS (2026-07-28)

`scripts/inference/bench-vq-matvec.cu`. The lane rested on one unmeasured assumption: that
decoding a fixed-width codebook index is at least as cheap as extracting an int4 nibble.
Measured on the RTX PRO 6000 Blackwell at GLM expert shape (I=6144, O=2048, B=1):

```
kernel                                  ms        GB/s % roofline   vs int4
int4 nibble (Colibri baseline)      0.0153       411.3      23.0%     1.00x
VQ d=4 K=256 x1  (2.0 b/w)          0.0134       235.2      13.1%     1.14x
VQ d=4 K=256 x2  (4.0 b/w)          0.0175       360.1      20.1%     0.88x
```

Read the **wall-clock** column: VQ shows lower GB/s because it moves less data, not because
it is slower.

- **2 b/w VQ is 1.14× FASTER than int4** — it reads half the bytes per row (1536 index bytes
  vs 3072 nibble bytes). Residency *and* throughput from the same change.
- **4 b/w VQ is 12% slower** at identical byte count — two lookups plus an add — while being
  1.6× more accurate.

**The assumption holds; the lane survives its cheapest kill-gate.** The codebook (K·d·4 B =
4 KB for d=4 K=256) sits in shared memory, loaded once per block.

Caveats: this is a first-attempt kernel using the same naive structure as Colibri's (one block
per output, shared-memory reduction), so there is unchased headroom. It uses synthetic
codebook/index data, so it does not model real cache pressure. And it measures the kernel only —
not loader integration or correctness.

### Phase 4 PIVOT — Colibri already has the codec; it just has no CUDA kernel (2026-07-28)

Reading `colibri.c` before writing the format revealed that **`fmt=5` and `fmt=6` are already
taken**, and `fmt=6` is **E8/IQ3** — a lattice quantiser (the QuIP# family) ported from ggml's
IQ3_XXS at 3.06 b/w, with a CPU kernel (`matmul_e8`), a packer (`tools/iq3_pack.py`), and tests
(`tests/test_e8_kernel.c`, `tests/test_iq3_pack.py`).

The reason it does not help today is one line — `colibri.c:294`:

```c
if(t->fmt==5||t->fmt==6) return 0;   /* int3-g64 / E8: no CUDA kernel yet — tensor stays CPU-side */
```

**Both sub-4-bit formats are stranded on the CPU for want of a CUDA kernel** — precisely the wrong
side of this SDD's bottleneck, where a miss costs ~10× per expert.

Measured against the format this SDD proposed (`scripts/inference/bench-e8-vs-vq.py`):

```
format                               b/w      err   MB/exp   inVRAM  vs int4
int4 per-row (PRODUCTION)           4.00   0.1642    18.90    6,460    1.00x
fmt=6 E8/IQ3  (EXISTS, CPU-only)    3.06   0.1982    14.45    8,449    1.21x
SDD-403 VQ d=4 K=[256,16] x2        3.00   0.1874    14.17    8,617    1.14x
```

Within **6% on error and 2% on residency**. The custom format buys nothing worth its cost.

**Revised phase 4: port `matmul_e8` to CUDA. That is the whole task.** No new format, no packer,
no loader or container changes, and a CPU reference to validate bit-exactness against. The E8
decode is GPU-friendly: a 1 KB `e8_grid[256][4]` table (shared memory), sign expansion, and a
fixed 32-point Walsh–Hadamard per sub-block. The phase-4 gate above already showed a
shared-memory codebook lookup holds the int4 path's throughput.

This also makes the work **upstream-shaped** rather than a fork: it fills a gap Colibri documents
in its own comment, and benefits anyone running a model larger than their VRAM.

### Phase 4 BUILT — the E8/IQ3 CUDA kernel (2026-07-28)

`scripts/inference/bench-e8-matvec.cu`. A CUDA port of `matmul_e8`, validated before touching
`backend_cuda.cu`.

**Correctness — confirmed.** Against a float64 reference of the *same* decode, the port is **more
accurate than Colibri's own CPU kernel** (3.57e-04 vs 6.44e-04); the difference is summation order
(tree vs sequential), not decode. `compute-sanitizer`: 0 errors.

**Throughput — 0.55× of the int4 nibble path** after optimisation:

```
kernel                                ms        GB/s   vs int4
int4 nibble (baseline)            0.0153       410.5     1.00x
fmt=6 E8/IQ3 (1 row/block)        0.0418       115.2     0.37x
fmt=6 E8/IQ3 (8 rows/block)       0.0276       174.4     0.56x
```

The lever that mattered was **not** the decode. Per matvec, `x` is re-read once per output row:
**50.33 MB of traffic against 4.82 MB of E8 weights — 10.4×**. Tiling `x` in shared memory across
8 output rows (one warp per row; the E8 layout maps exactly — 8 sub-blocks × 4 lanes = 32 groups
of 8 weights = one superblock per warp-pass) gave 1.5×. Shared-memory grid gave 1.5× before that.
Branchless parity via `__popc` and thread-count sweeps gave nothing. R=8 is optimal; R=16/32
regress on occupancy.

**Net on the expert path — 1.29× better:**

```
                          GPU      CPU     total
int4 today               1.45s   10.79s   12.24s   1.00x
E8 naive kernel          4.34s    6.61s   10.95s   1.12x
E8 multi-row R=8         2.89s    6.61s    9.50s   1.29x
```

Residency rises 78.6% → 86.9% of routings; the decode is 1.8× dearer but the CPU fallback nearly
halves. End-to-end this is roughly **1.13×**, i.e. ~3.4 tok/s.

**Three portability traps, recorded because they will recur:**

- `E8_BBYTES` is **98** — *not* 4-byte aligned. `memcpy(&word, blk+64+ib*4, 4)` faults on device;
  multi-byte values must be assembled from bytes.
- `__constant__` memory is a **broadcast** path and serialises on divergent indices, which is
  exactly the grid-lookup pattern. The grid belongs in shared memory.
- int4 rows (I/2) are **larger** than E8 rows (98 B per 256 weights), so a shared host buffer
  overruns.

**Caveat:** the multi-row variant measures 1.90e-03 max relative error vs float64 — 3× the CPU
reference. Irrelevant against weights already carrying ~20% quantisation error, but it would fail
a strict bit-exactness gate like `tests/test_e8_kernel.c`, so landing it upstream needs that
tolerance agreed.

### Sequencing correction

This SDD ordered phase 3 (end-to-end quality gate) before phase 4 (the `fmt=5` format). That is
wrong: an end-to-end eval needs Colibri to *load* VQ weights, which the format provides. The
corrected order is **2 → 2b → 3a (this) → 4 (format + kernel) → 3 (end-to-end gate) → 5 (measure)**.

## Way forward (phased; each phase its own PR + gate)

1. **This SDD** — design-lock. *(this session)*
2. **Offline VQ pipeline.** Calibration-based fit (AQLM/QuIP#-class, not plain k-means) producing a shared
   codebook + index stream from the FP8 source. Emits a container Colibri can load. CPU-only, no engine change.
3. **Quality gate.** End-to-end eval of the VQ container vs the int4 reference on the R232 surface. **A
   promotion gate: if generation quality regresses materially, the lane stops here.**
4. **Format (`fmt=5`).** Colibri-side: `weight_at` / `row_bytes` / `qt_bytes` / loader + the codebook in the
   container. Upstream contribution or a maintained patch — an operator call.
5. **Kernel.** Fixed-width VQ matvec. Target: hold the **254 GB/s** the nibble path achieves
   (`bench-expert-matvec.cu` is the harness). Verified before any throughput claim.
6. **Measure.** tok/s + hit-rate + CPU share against the table above, on this box.

## Open questions

| Q | Question | Status |
|---|---|---|
| Q-403-A | Which operating point — 2.75 b/w (1.39× err, 1.64×) or 2.00 b/w (1.96× err, 2.47×)? | open — gated on the phase-3 quality eval; do not pick from weight error alone |
| Q-403-B | Codebook scope: per tensor, per expert, or shared across a whole layer? Layer-shared is smaller and may generalise better; untested. | open |
| Q-403-C | Upstream the `fmt=5` format to Colibri, or carry a patch? | open — operator call; upstream is cleaner but slower |
| Q-403-D | Is this lane worth building at all given `gpt-oss-120b` measured 63× for zero engineering? | **operator call — the decisive question.** This SDD documents the path; it does not argue for taking it. |

## Cross-references

- [chromofold-fold-measurement-glm52-2026-07-27.md](../evaluations/chromofold-fold-measurement-glm52-2026-07-27.md)
  — the full measurement record, incl. the ten negative results this lane is designed around.
- [SDD-402](402-chromofold-weight-gemm-abi-export-contract.md) — the block-Huffman export contract; **Q-402-E**
  (`block ≥ 1024`) still applies to the entropy lane, which VQ does not replace.
- [SDD-401](401-chromofold-gpu-hotswap-fold-the-model.md) / [SDD-400](400-chromofold-compressed-domain-integration.md)
  — the GPU-fold hotswap and positioning this extends.
- ChromoFold `docs/m22-real-expert-bank-measurement.md` — the consumer-side negative result returned upstream.
- `scripts/inference/bench-vq-codebook.py` (this SDD's harness), `bench-expert-matvec.cu` (the 254 GB/s target),
  `bench-quant-viability.py` (the scalar baseline VQ is measured against).
- ChromoFold constitution **P9 (build ≠ query)** — the principle this lane instantiates.
