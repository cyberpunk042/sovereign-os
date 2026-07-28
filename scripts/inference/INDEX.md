# Inference stack

Direct-stack architecture per SDD-011 (Q-017 resolution path).

## Per-tier mapping (sain-01 default)

| Tier | Backend | Hardware | Start script |
|---|---|---|---|
| **Pulse** | `bitnet.cpp` | CCD 0 cores 0-5 (CPU) | [`start-pulse.sh`](start-pulse.sh) |
| **Logic Engine** | `vLLM` (primary) + `llama.cpp` (fallback) | RTX 5090 32 GB (host-resident, D-022) | [`start-logic-engine.sh`](start-logic-engine.sh) |
| **Oracle Core** | `vLLM` + DFlash drafts | RTX PRO 6000 Blackwell 96 GB | [`start-oracle-core.sh`](start-oracle-core.sh) |

## Router

[`router.py`](router.py) — thin OpenAI-compatible HTTP front for clients that want a single endpoint. Deterministic routing by model-id + request shape; no black-box dispatch.

## Scheduler bridge (cross-repo, MS048)

[`scheduler-bridge.py`](scheduler-bridge.py) — READ-ONLY consumer of the selfdef IPS-side Goldilocks Scheduler (Solution 2). Builds a task descriptor (profile + 4 model-estimated axes), invokes the `selfdef-scheduler-decide` producer binary, and maps the returned route → backend tier (`blackwell`→oracle / `rtx4090`→scout / `cpu`→cortex / `hybrid` / `hibernate`→defer), honoring the integration contract (`cyberpunk042/selfdef/docs/operator/ms048-scheduler-integration-contract.md`): **honor Hibernate · map route→tier · read-only**. Graceful-offline — binary absent/errored → `scheduler_available=False` so the gateway falls back to its own SDD-011 routing; never crashes, never fabricates a route. Binary path via `SELFDEF_SCHEDULER_DECIDE_BIN`. Usable standalone (`scheduler-bridge.py --profile careful --risk 0.2 --json`) or importable (`consult(task) -> verdict`). Maps route → runtime service (blackwell→Oracle Core / rtx4090→Logic Engine / cpu→Pulse). Tests: `tests/unit/test_scheduler_bridge.py` (10 cases).

**Router integration (opt-in, MS048):** `router.py` consults the bridge when `SOVEREIGN_OS_CONSULT_SCHEDULER=1` (default OFF — routing then completely unchanged) and surfaces the scheduler's hardware-tier advisory as the `X-Sovereign-Scheduler-Advisory` response header **without changing the routed tier** (the runtime's `classify()` stays authoritative). Profile via `SOVEREIGN_OS_SCHEDULER_PROFILE` (default `production`). Fail-safe — a missing/broken scheduler never affects routing. Tests: `tests/unit/test_router_scheduler_advisory.py` (5 cases). Making the advisory **authoritative** (router defers routing to the scheduler) remains a separate, explicit operator step.

## Backends

[`backends/bitnet.py`](backends/bitnet.py) · [`backends/vllm.py`](backends/vllm.py) · [`backends/llama_cpp.py`](backends/llama_cpp.py)

Each implements a small adapter contract (`lib/backend.py`).

## ChromoFold fold measurement (SDD-400/401/402)

[`chromofold-fold-bench.py`](chromofold-fold-bench.py) — READ-ONLY measurement of ChromoFold's weight-fold techniques against a **real** quantized MoE expert bank, answering the question SDD-401/402 sized from ChromoFold's *synthetic* benches (which disagree 3× between themselves). Modes: `heat` (routing concentration from Colibri's `.coli_usage`), `entropy` (the M6 block-Huffman lane — H0/H1 of the int4 symbol stream + the `block`-size trade), `group` (the M20/M21 grouped-delta lane, index- and permutation-aligned), `rank` (within-expert SVD spectrum). Pure numpy, no GPU/CUDA/`libchromofold`; honest-degrades exit-3 when the container or the Warp checkout is absent. Measured 2026-07-27 on GLM-5.2 int4: entropy lane **1.350× lossless** (358 GB → 266 GB, the fit that makes VRAM+RAM residency possible), grouping lane **0.99×** (does not pay). Full record: [`docs/evaluations/chromofold-fold-measurement-glm52-2026-07-27.md`](../../docs/evaluations/chromofold-fold-measurement-glm52-2026-07-27.md).

### Serving gpt-oss-120b on the Blackwell tier (measured 2026-07-28)

`start-oracle-core.sh` serves it with **no code change** — environment only. Measured on the
RTX PRO 6000 Blackwell: **199.76 tok/s decode, TTFT 0.036 s** (R232 throughput gate, 3/3 prompts),
85.8 GB VRAM, 288,679-token KV cache.

```sh
PYTHONPATH=/home/jfortin/vllm-env PATH=/home/jfortin/vllm-env/bin:$PATH \
ORACLE_MODEL=<models-dir>/gpt-oss-120b \
scripts/inference/start-oracle-core.sh
```

**Concurrency (measured 2026-07-28)** — continuous batching holds up well; per-stream degrades
gracefully rather than collapsing, and TTFT stays under 100 ms throughout:

```
 streams   agg tok/s  per-stream   TTFT p50
       1       182.0       182.0      0.057
       4       419.9       105.0      0.067
      16       918.2        57.4      0.085
```

16 agents sharing the endpoint still get 57 tok/s each. For contrast, GLM-5.2's MoE batch-union
means a batch of 4 touches 30.5 of 256 experts, so its expert reads barely amortise (~1.17x).

Four things that are easy to trip over, all hit during the first bring-up:

- **vLLM lives in a `pip --target` directory** (`/home/jfortin/vllm-env`) because PEP 668 blocks a
  system install and `python3-venv` isn't present. Both `PYTHONPATH` **and** `PATH` are required —
  torch shells out to `ninja` to JIT the Marlin MXFP4 kernels, and a `--target` install leaves
  `bin/ninja` off `PATH`. Without it the engine dies with `FileNotFoundError: 'ninja'`.
- **The HF repo ships 196 GB in three formats** (root safetensors 65 GB + `original/` 65 GB +
  `metal/` 65 GB). Only the root set is usable here; pull with `--exclude "metal/*" --exclude
  "original/*"` (one pattern per flag — two after a single `--exclude` makes the second a positional
  filename). `pull.sh` has no exclude support yet, so this needs a direct `hf download`.
- **`start-oracle-core.sh` doesn't pass `--served-model-name`**, so the served id is the full weights
  path. The R232 gate derives its model name from the catalog `hf_repo_id`, so it needs
  `SOVEREIGN_OS_BENCH_MODEL` to match, else vLLM 404s.
- **It sets `--kv-cache-dtype fp8`**, untested with MXFP4 weights. The measured run above used `auto`.

Requires NVIDIA driver ≥ 570 for Blackwell — see
[`post-install/nvidia-blackwell-driver-install.sh`](../hooks/post-install/nvidia-blackwell-driver-install.sh).
Catalog entry is still `operator-must-confirm`; the bench gate its evaluation names as the promotion
condition has now passed.

### Decode-path microbenchmarks (2026-07-27 investigation)

Three standalone benchmarks that isolated the GLM-5.2 decode bottleneck. All read-only; the `.cu` pair needs `nvcc -O3 -arch=sm_120`.

- [`bench-expert-matvec.cu`](bench-expert-matvec.cu) — Colibri's `quant_matmul` vs two optimised rewrites at GLM expert shape (int4, I=6144, O=2048, B=1). **Result: Colibri's kernel wins at 254 GB/s (14% of roofline); both rewrites lost (0.79×, 0.33×).**
- [`bench-launch-overhead.cu`](bench-launch-overhead.cu) — per-expert launch cost and CUDA Graph capture vs plain stream launches, at the real 4-launches-per-expert pattern. **Result: empty launch 2.05 µs; graph replay only 1.05×** — launch overhead is not the bottleneck.
- [`bench-quant-viability.py`](bench-quant-viability.py) — 2-bit/3-bit quantisation error measured from the **FP8 source** (not the int4 container, which double-quantises). **Result: 2-bit is dominated at every operating point** — uniform grouping is 4.4× worse than production int4, and a Lloyd-Max codebook that reaches acceptable error costs exactly what it saves (18.87 MB = int4 size).

Full record: [`docs/evaluations/chromofold-fold-measurement-glm52-2026-07-27.md`](../../docs/evaluations/chromofold-fold-measurement-glm52-2026-07-27.md).

## Why no unifying abstraction (vs LocalAI)

Per SDD-011: SAIN-01's value is per-tier hardware exploitation. The router speaks OpenAI but routes deterministically; backends remain operator-readable + observable.

## Per-profile differences

- `sain-01`: full Trinity (Pulse + Logic + Oracle).
- `old-workstation`: only `llama.cpp` (single 8 GB GPU). LocalAI acceptable as alternative.
- `minimal` / `headless`: inference disabled.
- `developer` (reserved): `llama.cpp` or operator-installed Ollama.
