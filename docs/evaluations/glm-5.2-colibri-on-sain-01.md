# Evaluation — GLM-5.2 (+ Colibri expert-streaming) on SAIN-01

> Operator ask (verbatim, 2026-07-19): *"Lets evaluate the possibility for GLM,
> like GLM 5.2+ Colibri on the SAIN, on sovereign-os"*
>
> Status: **evaluation — operator-must-confirm**. Companion catalog entry:
> `GLM-5.2-colibri-int4` in [`models/catalog.yaml`](../../models/catalog.yaml).
> All facts below HF-/web-verified 2026-07-19; every performance number for
> SAIN-01 itself is an **agent estimate flagged as such** — no bench has run
> on the physical box.

## Verdict (TL;DR)

**Possible — as a new deep-synthesis/batch tier, not as the interactive
Oracle Core.** GLM-5.2 cannot fit any SAIN-01 GPU (or all three together)
under vLLM at any published precision. The Colibri engine changes the
equation: it runs the full 744B MoE from a ~370 GB int4 NVMe checkpoint with
~9.9 GB dense weights resident, streaming routed experts on demand — and
SAIN-01's spec (256 GB DDR5 + 152 GB total VRAM + dual PCIe 5.0 NVMe RAID 0 +
Zen 5 AVX-512) is close to a best-case consumer host for exactly this
pattern. Expected throughput is single-digit tok/s warm (estimate) — fine
for long-horizon batch reasoning/coding runs, unacceptable as the
interactive Oracle. Nemotron-3-Nano-Omni stays the Oracle default.

## What GLM-5.2 is (verified)

| Fact | Value | Source |
|---|---|---|
| Vendor | Zhipu AI / Z.ai (`zai-org`) | HF |
| Released | 2026-06-13 (weights public, HF repos created 2026-06-16) | press + HF |
| Architecture | `glm_moe_dsa` — MoE + DSA sparse attention | HF config |
| Parameters | 753.3B total, ~40B active per token; 21,504 routed experts | HF + Colibri docs |
| Context | 1M tokens; High/Max selectable thinking effort | press |
| License | **MIT** — no gating, no HF token needed | HF |
| Checkpoints | `zai-org/GLM-5.2` (BF16, ~1.5 TB) · `zai-org/GLM-5.2-FP8` (~753 GB) | HF |
| Standing | Intelligence Index v4.1: 51 — above MiniMax-M3 (44), DeepSeek V4 Pro (44), Kimi K2.6 (43), Gemini 3.1 Pro Preview (46) | trade press |
| Family | GLM-5 (2026-02) → GLM-5.1 (2026-04) → GLM-5.2 (2026-06), all ~753B `glm_moe_dsa` | HF `zai-org` listing |
| Smaller variant | **None.** No GLM-5.x-Air exists; community is requesting one (HF discussion). Previous-gen GLM-4.5-Air is 106B-A12B. | HF |

## What Colibri is (verified)

[github.com/JustVugg/colibri](https://github.com/JustVugg/colibri) — Apache-2.0,
v1.0.0 (July 2026), ~16k stars. Pure-C inference engine purpose-built for
GLM-5.2's MoE shape; optional CUDA and Metal backends. Not affiliated with
Zhipu.

- **Memory hierarchy**: dense parts (attention, shared experts, embeddings —
  ~17B params) resident in RAM at int4 (~9.9 GB); the 21,504 routed experts
  (~370 GB int4) stream from NVMe on demand. VRAM, RAM and disk form one
  tiered cache.
- **Learning cache**: hot experts get pinned by observed usage; router
  prefetch is ~71.6% predictable one layer ahead.
- **MTP speculative decoding**: GLM-5.2's native multi-token-prediction head
  gives 2.2–2.8 tokens/forward — but **int4 MTP heads fail; the int8-MTP
  checkpoint variant is required** for working speculation.
- **KV compression**: DSA attention state is 576 floats/token vs 32,768
  (57× smaller) — 1M-token context is storage-cheap.
- **Reference performance** (Colibri's published numbers, not ours):
  25 GB RAM cold ≈ 0.05–0.1 tok/s · 128 GB RAM CPU-only warm ≈ 1.8 tok/s ·
  1× RTX 5070 Ti ≈ 1.07 tok/s · 6× RTX 5090 (full VRAM residency) ≈
  5.8–6.8 tok/s decode, TTFT ~13 s.

Community checkpoints (all MIT, quantized from `zai-org/GLM-5.2-FP8`):

| Repo | Note |
|---|---|
| `jlnsrk/GLM-5.2-colibri-int4` | original Colibri int4 pack (135 likes) |
| `mateogrgic/GLM-5.2-colibri-int4-with-int8-mtp` | **int4 + int8 MTP heads — the candidate** (working speculation) |

## Fit against SAIN-01 (per `profiles/sain-01.yaml`, SDD-993)

| SAIN-01 resource | Spec | GLM-5.2/Colibri demand | Fit |
|---|---|---|---|
| RTX PRO 6000 (96 GB) + RTX 5090 (32 GB) + RTX 4090 eGPU (24 GB) = 152 GB VRAM | Oracle/Logic tiers | vLLM hosting: BF16 1.5 TB / FP8 753 GB / int4 ~380 GB — **none fit** | ❌ GPU-resident serving impossible |
| Same 152 GB VRAM as Colibri's top cache tier | CUDA backend | ~40% of the expert pool VRAM-resident (4090 on PCIe 4.0 x4 OcuLink is fine — expert *cache*, not tensor-parallel) | ✅ meaningful accelerator |
| 256 GB DDR5 | Colibri RAM tier | 9.9 GB dense + expert cache; 2× the 128 GB reference host | ✅ best consumer-class case |
| Dual PCIe 5.0 NVMe RAID 0 | expert streaming | cold token can read ~11 GB; RAID 0 seq reads ≫ the consumer NVMe in Colibri's numbers | ✅ (capacity: needs **~380 GB free** on `tank/models`) |
| Ryzen 9 9900X AVX-512 VNNI/BF16 | int4/int8 CPU matmuls | pure-C engine; SIMD dispatch level **unverified** — verify at bench | ⚠️ verify |
| ZFS `tank/models` (1M recordsize, lz4) | checkpoint dataset | large sequential expert reads match 1M records; int4 weights won't compress (lz4 no-op, harmless) | ✅ |
| ZFS ARC clamped at 128 GB (`arc-clamp-128gb` hook) | double-caching risk | Colibri's learning cache + ARC would cache the same expert blocks | ⚠️ consider `primarycache=metadata` on the checkpoint dataset, or accept double-cache |
| Tetragon execve allowlist (sovereign-kernel-fence) | new binary | `colibri` binary needs `provisioning.tetragon.extra_allowed_binaries` (absolute path) | ⚠️ integration step |
| Catalog schema engine enum | `[bitnet.cpp, vllm, vllm-vulkan, llama.cpp, transformers, custom]` | Colibri = `custom` today; adding a first-class `colibri` enum value is a schema 1.1.x bump | ✅ representable now |

**SAIN-01 throughput expectation (AGENT ESTIMATE — bench required):** with
256 GB RAM (2× the 1.8 tok/s reference host), ~152 GB VRAM as a partial-
residency CUDA tier (vs 192 GB on the 6×5090 host at 5.8–6.8 tok/s), PCIe 5.0
RAID 0 for misses, and int8-MTP speculation (2.2–2.8×) — plausibly **~2–6
tok/s warm decode**, with double-digit-second TTFT and slow cold starts.
Nothing in this paragraph is measured on the box.

## What this is and is not

- **Is**: the first genuinely *frontier-class* model SAIN-01 could run fully
  locally (MIT weights, Apache-2.0 engine, zero external providers) — the
  strongest possible expression of the sovereignty doctrine. Natural shape:
  a batch **deep-synthesis** companion (same spirit as the
  `deep-context-synthesis` runtime profile that names DeepSeek-V3), fed
  long-horizon reasoning/coding jobs where 2–6 tok/s is acceptable.
- **Is not**: an Oracle Core replacement. Interactive agent loops (OpenClaw,
  open-computer, dashboards) need the throughput the vLLM-served
  Nemotron-3-Nano-Omni default delivers. No change proposed to the Oracle
  default.
- **Alternative GLM path (if the operator wants GLM *on GPU*)**: no GLM-5.x
  fits. Previous-gen **GLM-4.5-Air (106B-A12B)** at int4/AWQ (~55-60 GB)
  fits the PRO 6000 with headroom under vLLM — a different evaluation if
  wanted. Watch for a future GLM-5.2-Air: community pressure is visible on
  the HF discussion, nothing announced.

## If the operator confirms — integration checklist

1. **Storage**: ~380 GB free on `tank/models` (pull via `sovereign-osctl
   models pull` once the entry is promoted; `min_free_gb` guard ≈ 400).
2. **Checkpoint**: `mateogrgic/GLM-5.2-colibri-int4-with-int8-mtp` (int8 MTP
   heads — int4 MTP breaks speculation).
3. **Engine**: build/install Colibri (pure C, zero deps; optional CUDA);
   pin a release + checksum, same pattern as `tetragon-install`.
4. **Tetragon**: append the colibri binary's absolute path to
   `provisioning.tetragon.extra_allowed_binaries`.
5. **ZFS**: decide ARC posture for the checkpoint dataset
   (`primarycache=metadata` vs default double-cache) — bench both.
6. **Bench gate**: measure warm/cold decode, TTFT, MTP accept-rate on the
   physical box; promote the catalog entry `operator-must-confirm →
   verified-real` binding only after numbers are real.
7. **Schema (optional)**: promote `engine: custom` → first-class `colibri`
   enum value in `schemas/model-catalog.schema.yaml` (1.1.x bump).

## Sources

- [zai-org/GLM-5.2](https://huggingface.co/zai-org/GLM-5.2) · [zai-org/GLM-5.2-FP8](https://huggingface.co/zai-org/GLM-5.2-FP8) (HF, verified 2026-07-19)
- [jlnsrk/GLM-5.2-colibri-int4](https://hf.co/jlnsrk/GLM-5.2-colibri-int4) · [mateogrgic/GLM-5.2-colibri-int4-with-int8-mtp](https://hf.co/mateogrgic/GLM-5.2-colibri-int4-with-int8-mtp)
- [JustVugg/colibri (GitHub)](https://github.com/JustVugg/colibri) — engine README (perf table, MTP int8 requirement, memory hierarchy)
- [SCMP — Zhipu AI releases harness for GLM-5.2](https://www.scmp.com/tech/tech-trends/article/3359170/zhipu-ai-releases-harness-glm-52-model-chinese-firm-takes-aim-anthropic)
- [trendingtopics.eu — GLM-5.2 vs Google top models](https://www.trendingtopics.eu/glm-5-2-chinas-zhipu-ai-beats-even-googles-top-models-with-its-new-open-llm/)
- [datanorth.ai — GLM-5.2 release](https://datanorth.ai/news/zhipu-ai-releases-glm-5-2) · [eigent.ai — GLM-5.2 1M-token coding model](https://www.eigent.ai/blog/glm-5-2)
- [HF discussion — "We need some Air or at least some Flash"](https://huggingface.co/zai-org/GLM-5.2/discussions/3)
- [Wavect — Colibri on consumer hardware, the catch](https://wavect.io/blog/colibri-glm-5-2-consumer-hardware/) · [Developers Digest — disk streaming + expert offloading](https://www.developersdigest.tech/blog/colibri-glm-52-slow-computer-local-inference)
