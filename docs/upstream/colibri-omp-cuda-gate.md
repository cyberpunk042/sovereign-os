**Title:** OMP hot-thread tuning is skipped whenever `COLI_CUDA` is set — but most experts still run on CPU when the model exceeds VRAM

---

### Summary

`colibri.c:6282` gates the OpenMP hot-thread tuning behind `!getenv("COLI_CUDA")`:

```c
if(!getenv("COLI_OMP_TUNED") && !getenv("COLI_NO_OMP_TUNE") &&
   !getenv("COLI_CUDA") && !getenv("COLI_METAL")){
    setenv("OMP_WAIT_POLICY","active",0);
    setenv("GOMP_SPINCOUNT","200000",0);
    ...
```

The implicit assumption is that a CUDA build runs its expert matmuls on the GPU, so the CPU
thread team doesn't matter. **That holds only when the expert bank fits VRAM.** For a model
larger than VRAM, the RAM-tier experts still run through the CPU path, and they run with
libgomp's default passive wait policy — the exact pathology the tuning exists to fix, and
which the code's own comment prices at **66.9s → 20.9s on a Zen 5 build**.

### Measured

GLM-5.2 int4 (383.7 GB), RTX PRO 6000 Blackwell 96 GB + RTX 5090 32 GB (130.8 GB VRAM),
Ryzen 9 9900X, 249 GB DDR5, driver 590.48.01 / CUDA 13.3, colibri v1.1.1 built `CUDA=1
CUDA_ARCH=native` (sm_120).

Only **7,094 of 19,456 experts** fit VRAM at int4, so a large share of expert work lands on
the CPU. With `PROF=1`:

```
P0-EXEC: routed CPU 10.793s / 40.68 GB/s (28103 row) | routed GPU critical 1.454s
         | router 0.691s | residual P2P 0.000s / 0 hop | orchestration 1.598s
```

**Routed CPU is 10.79s of a 30.7s decode — ~35%** — and it is running untuned, because
`COLI_CUDA=1` was set.

Config used:

```sh
COLI_MODEL=/nvme/glm52_i4 COLI_CUDA=1 CUDA_DENSE=1 COLI_CUDA_ATTN=1 \
COLI_CUDA_MTP=1 DIRECT=1 PIPE=1 PIN=auto PIN_GB=170 RAM_GB=205 PROF=1 \
./coli run --auto-tier --gpu auto --ngen 64 "<prompt>"
```

### Workaround

Setting the vars externally works, because the constructor reads them before `main()` and the
tuning block honours pre-set values (`overwrite=0`) — no re-exec happens, which is the intended
mechanism:

```sh
OMP_WAIT_POLICY=active GOMP_SPINCOUNT=200000 KMP_BLOCKTIME=200 \
OMP_PROC_BIND=close OMP_DYNAMIC=FALSE  <the same command>
```

### Honest caveat on the fix's value here

I could **not** demonstrate a clear win from applying the tuning in this configuration. A/B at
`PIN_GB=170`: 2.44 → 2.86 tok/s total, **but `expert-matmul` itself went 10.26s → 11.31s** and
the entire gain came from disk-wait (11.6 → 6.3s), which is page-cache state, not threading. So
the 1.17× is likely run-to-run variance. Plausible explanation: with `CUDA_DENSE=1` most of the
tiny back-to-back matmul regions are already on the GPU, leaving fewer CPU regions for
thread-parking to hurt.

So this is reported as a **gating-condition bug** rather than a proven regression: the gate's
premise ("CUDA ⇒ experts on GPU") is measurably false for models larger than VRAM, whatever the
size of the resulting effect. A more accurate condition might be to skip the tuning only when
the expert bank is known to be fully VRAM-resident, or simply to drop the `COLI_CUDA` term and
let `COLI_NO_OMP_TUNE=1` remain the kill-switch.

### Environment

- colibri v1.1.1, `make glm CUDA=1 CUDA_ARCH=native` (sm_120)
- Debian 13 trixie, kernel 6.12.96, gcc 14.2, libgomp
- CUDA 13.3, driver 590.48.01
- Model: `GLM-5.2 int4`, per-row scales, int8 MTP heads
