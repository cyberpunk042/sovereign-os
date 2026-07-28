# Upstream issue drafts

Bugs found in third-party projects while running them here, written up as ready-to-file
issue text. Kept in-repo so the reproduction and measurements survive the session that
found them, and so the same bug is not re-discovered later.

**These are drafts, not filed issues.** Filing goes through the operator's own account:

```sh
gh auth login                                            # interactive, once
gh issue create --repo <upstream> --title "<title line>" \
                --body-file docs/upstream/<file>.md      # strip the Title: line first
```

| draft | upstream | status |
|---|---|---|
| [colibri-omp-cuda-gate.md](colibri-omp-cuda-gate.md) | [JustVugg/colibri](https://github.com/JustVugg/colibri) | **not filed** |

## colibri-omp-cuda-gate

Colibri skips its OpenMP hot-thread tuning whenever `COLI_CUDA` is set
(`colibri.c:6282`), on the assumption that a CUDA build runs its expert matmuls on the
GPU. That assumption holds only when the expert bank fits VRAM. Measured here on
GLM-5.2 (383.7 GB int4) against 130.8 GB of VRAM: only **7,094 of 19,456 experts** are
resident, and `PROF=1` shows **routed CPU 10.793s of a 30.7s decode** — running untuned,
because `COLI_CUDA=1` was set.

The draft is deliberately honest about its weak point: applying the tuning by hand did
**not** produce a clear win in this configuration (the apparent 1.17× was disk-wait
variance, and `expert-matmul` itself got slightly worse). So it is reported as a **wrong
gating condition** — the premise is measurably false above VRAM size — rather than as a
proven regression. Full context:
[`docs/evaluations/chromofold-fold-measurement-glm52-2026-07-27.md`](../evaluations/chromofold-fold-measurement-glm52-2026-07-27.md).
