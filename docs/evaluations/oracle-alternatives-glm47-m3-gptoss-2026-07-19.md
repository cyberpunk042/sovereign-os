# Evaluation — Oracle-tier alternatives that actually fit SAIN-01 (GLM-4.7 · MiniMax-M3 · gpt-oss-120b · GLM-4.7-Flash)

> Follow-up to [glm-5.2-colibri-on-sain-01.md](glm-5.2-colibri-on-sain-01.md)
> (verdict: no — model 8× too big, streaming hack too slow). Operator ask
> (2026-07-19): *"is there some other model that would play better in that
> competitive range that we dont have yet.. AirLLM technique style I guess !?"*
> → *"alright, lets explore those then"*.
>
> All specs HF-/web-verified 2026-07-19. SAIN-01 perf numbers are
> **agent estimates flagged as such** — no bench has run on the box.

## The sizing rule that drives everything

SAIN-01's two deployment envelopes (per `profiles/sain-01.yaml`, SDD-993):

1. **Pure-VRAM vLLM** (full speed): weights ≤ ~90 GB → RTX PRO 6000 96 GB,
   with KV headroom.
2. **RAM+VRAM hybrid via llama.cpp `--n-cpu-moe`** (no disk streaming):
   int4/GGUF total ≤ ~350 GB → 256 GB DDR5 (experts) + 128 GB usable VRAM
   (dense layers + hot experts + KV). The 4090 eGPU (OcuLink x4) adds cache,
   not tensor-parallel.

Everything in GLM-5.2's exact score band except MiniMax-M3 fails envelope 2
(GLM-5.2 744B · Kimi K2.6 1T · DeepSeek V4 Pro 1.6T). The candidates below
all pass one of the two envelopes.

## The four candidates

### 1. GLM-4.7 — max local intelligence (hybrid envelope)

| Fact | Value |
|---|---|
| Repo | `zai-org/GLM-4.7` (HF-verified; + `-FP8`; unsloth GGUF line per unsloth docs) |
| Shape | 358.3B total / ~32B active MoE (`glm4_moe`), Dec 2025 |
| Context | 200K · License **MIT** |
| Standing | Same lineage as GLM-5.2; reported 73.8% SWE-bench; the strongest open coder that fits the box |
| Fit | GGUF Q4 ≈ 180–200 GB → hybrid envelope, comfortable. Unsloth reports UD-Q2_K_XL (135 GB) works on 1×24 GB + 128 GB RAM; ≥205 GB combined RAM+VRAM → 5+ tok/s |
| SAIN estimate | **~8–15 tok/s** decode at Q4 (384 GB combined, large VRAM fraction) — AGENT ESTIMATE |
| Engine | llama.cpp (`--n-cpu-moe`); vLLM impossible (weights > VRAM) |
| Risk | Speed is RAM-bandwidth-bound (dual-channel DDR5); borderline interactive |

### 2. MiniMax-M3 — the only score-band peer that fits (hybrid envelope)

| Fact | Value |
|---|---|
| Repo | `MiniMaxAI/MiniMax-M3` (HF-verified) + `unsloth/MiniMax-M3-GGUF` |
| Shape | 427.0B total / ~23B active MoE (`minimax_m3_vl`), June 2026, **natively multimodal**, 1M context |
| Standing | Intelligence Index 44 vs GLM-5.2's 51 — the closest fit-able peer |
| License | **custom minimax-community** (`other`) — review before adoption |
| Fit | UD-IQ3_XXS ≈ 159 GB (the practical quant) · Q4 ≈ 214 GB — both inside hybrid envelope |
| SAIN estimate | **~5–15 tok/s** (23B active < GLM-4.7's 32B; Apple-Silicon reports 10–30) — AGENT ESTIMATE |
| Engine | llama.cpp support **preliminary** (PR #24523, not in a released build; MiniMax Sparse Attention falls back to dense). vLLM day-one but needs ~500 GB VRAM |
| Risk | Immature llama.cpp path + license + dense-attention fallback at long context |

### 3. gpt-oss-120b — frontier-adjacent at full interactive speed (VRAM envelope)

| Fact | Value |
|---|---|
| Repo | `openai/gpt-oss-120b` |
| Shape | ~117B total / 5.1B active MoE, native **MXFP4** ≈ 63 GB, 131K context, Apache-2.0 |
| Fit | **Entire model on the PRO 6000 with ~30 GB KV/batch headroom — the only candidate needing zero compromise** |
| SAIN estimate | Fastest of the four by far (5.1B active, all-VRAM, vLLM) — comfortably interactive |
| Engine | vLLM (mature support); harmony chat format quirk to wire |
| Risk | Below GLM-5.2/4.7 class on raw capability; reasoning-focused rather than code-specialist |

### 4. GLM-4.7-Flash — GLM flavor at the interactive tier (VRAM envelope, secondary GPU)

| Fact | Value |
|---|---|
| Repo | `zai-org/GLM-4.7-Flash` (HF-verified, 9.5M downloads) |
| Shape | 31.2B total / ~3B active MoE (`glm4_moe_lite`), Jan 2026, 200K context, **MIT** |
| Standing | 59.2 SWE-bench Verified — roughly **3× Qwen3-30B-A3B**; open SOTA in the 30B class |
| Fit | BF16 ≈ 62 GB → PRO 6000; **FP8 ≈ 32 GB → fits the RTX 5090 secondary**, freeing the primary |
| Engine | vLLM (guides exist for 24 GB-GPU deploys) |
| Role | Direct Nemotron-30B-class competitor for Logic/coder tier; not an Oracle |

## Verdict ladder

1. **gpt-oss-120b** — adopt-ready shape: full speed, no serving compromise,
   Apache-2.0, biggest capability-per-effort jump over the current defaults.
2. **GLM-4.7** — the real "GLM on the SAIN": near-frontier coding at
   ~8–15 tok/s hybrid. Worth a bench; usable for agentic coding if the
   number lands double-digit.
3. **GLM-4.7-Flash** — cheap win at the Logic tier (5090-resident FP8),
   SWE-bench triple of the Qwen 30B class, MIT.
4. **MiniMax-M3** — watch: re-evaluate when llama.cpp support merges +
   license reviewed. The only 1M-ctx multimodal near-frontier that fits.

No change proposed to serving defaults; all four land in the catalog as
`operator-must-confirm` candidates. Bench gates before any promotion.

## Sources

- [unsloth — GLM-4.7 local guide](https://unsloth.ai/docs/models/tutorials/glm-4.7) · [DataCamp — run GLM-4.7 locally](https://www.datacamp.com/tutorial/run-glm-4-7-locally)
- [unsloth/MiniMax-M3-GGUF](https://huggingface.co/unsloth/MiniMax-M3-GGUF) · [unsloth — MiniMax M3 guide](https://unsloth.ai/docs/models/minimax-m3) · [Kaitchup — M3 GGUF 852→150 GB](https://kaitchup.substack.com/p/minimax-m3-gguf-quantization-from)
- [MiniMax M3 hardware guide](https://www.runaihome.com/blog/minimax-m3-local-ai-vram-hardware-guide-2026/) · [morphllm — M3 architecture](https://www.morphllm.com/minimax-m3)
- [MarkTechPost — GLM-4.7-Flash 30B-A3B release](https://www.marktechpost.com/2026/01/20/zhipu-ai-releases-glm-4-7-flash-a-30b-a3b-moe-model-for-efficient-local-coding-and-agents/) · [llm-stats — GLM-4.7-Flash](https://llm-stats.com/posts/d9649b05-087d-4cbf-a45a-166ce2451e78) · [z.ai docs — GLM-4.7](https://docs.z.ai/guides/llm/glm-4.7)
- [Agent Native — GLM-4.7-Flash on 24 GB GPU](https://www.agentnative.dev/blog/glm-4-7-flash-on-24gb-gpu-llama-ccp-vllm-sglang-transformers)
- HF repos verified via Hub API 2026-07-19: `zai-org/GLM-4.7` (358,337.8M params) · `zai-org/GLM-4.7-Flash` (31,221.5M) · `MiniMaxAI/MiniMax-M3` (427,040.1M) · `openai/gpt-oss-120b`
