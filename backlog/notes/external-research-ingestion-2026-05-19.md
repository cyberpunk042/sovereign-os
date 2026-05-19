# External research ingestion — 2026-05-19

Operator-directed ingestion of 4 external sources (post-catalog-completion). Per operator standing direction: *"Find what they define and redine or improve / add. Take time to follow the important links. e.g. PDF added or update any Epic or Modules or Tasks"* + *"layered: new direction ON TOP OF prior direction — never discarded"*.

## Sources

| # | source | identifier | date | one-line definition |
|---|---|---|---|---|
| 1 | NVIDIA NVFP4 pretraining paper (canonical paper behind marktechpost 2026-05-18 article) | arXiv 2509.25149 | 2025-09-29 | NVFP4 4-bit pretraining via RHT + 2D quantization + stochastic rounding + selective high-precision; validated on 12B / 10T tokens matching FP8 baseline |
| 2 | "Steered LLM Activations are Non-Surjective" | arXiv 2604.09839 | 2026-05-07 | Formal proof activation steering pushes residual stream off prompt-reachable manifold (white-box ≠ black-box) |
| 3 | "HölderPO: Hölder Policy Optimisation" | arXiv 2605.12058 | 2026-05-12 | Generalised GRPO via Hölder-mean token aggregation + dynamic annealing parameter p |
| 4 | sapientinc/HRM-Text-1B model | huggingface.co/sapientinc/HRM-Text-1B | 2026-05-18 | 1.18B-param Hierarchical Reasoning Model (NOT Transformer, NOT Mamba); prefix-lm pre-alignment non-chat |

## Verbatim quotes preserved

### Source 1 — NVFP4 (arXiv 2509.25149)

> "we introduce a novel approach for stable and accurate training of large language models (LLMs) using the NVFP4 format. Our method integrates Random Hadamard transforms (RHT) to bound block-level outliers, employs a two-dimensional quantization scheme for consistent representations across both the forward and backward passes, utilizes stochastic rounding for unbiased gradient estimation, and incorporates selective high-precision layers."

> "We validate our approach by training a 12-billion-parameter model on 10 trillion tokens -- the longest publicly documented training run in 4-bit precision to date."

> "the model trained with our NVFP4-based pretraining technique achieves training loss and downstream task accuracies comparable to an FP8 baseline."

**NVFP4 format spec (from companion paper "FP4 All The Way" arXiv 2505.19115, Chmiel/Fishman/Banner/Soudry)**:
> "the NVFP4 format, where each block of 16 FP4 values (E2M1) shares a scale represented in E4M3, provides optimal results."

**Companion papers (NVFP4 ecosystem)**:
- arXiv 2601.22813 — Quartet II (Panferov/Schultheis/Tabesh/Alistarh) — MS-EDEN unbiased quantization 2x lower error than SR, 1.9B params / 38B tokens, 4.2x speedup over BF16 on Blackwell
- arXiv 2603.28765 — Adaptive Block-Scaled Data Types (Cook/Lee/Le/Guo/Traverso/Chandrakasan/Han) — IF4 = FP4 ⊕ INT4 per-group selection via unused E4M3 sign bit
- arXiv 2512.02010 — Four Over Six (Cook/Guo/Xiao/Lin/Han) — adaptive block-scaling reduces near-maximal value quantization error
- arXiv 2605.06067 — nGPT-NVFP4 (Fishman/Chmiel/Banner/Soudry/Ginsburg) — normalized architectures are natively 4-bit; validated 1.2B + 3B/30B MoE
- arXiv 2509.17791 — Elucidating FP4 Design Space (Hu/Luschi/Balanca, Graphcore) — Hadamard + tensor scaling + SR + UE5M3 scaling factor

### Source 2 — Steered LLM Activations Non-Surjective (arXiv 2604.09839)

> "Under practical assumptions, we prove that activation steering pushes the residual stream off the manifold of states reachable from discrete prompts. Almost surely, no prompt can reproduce the same internal behavior induced by steering."

> "We therefore caution against interpreting the ease and success of activation steering as evidence of prompt-based interpretability or vulnerability, and argue for evaluation protocols that explicitly decouple white-box and black-box interventions."

### Source 3 — HölderPO (arXiv 2605.12058)

> "Group Relative Policy Optimisation (GRPO) enhances large language models by estimating advantages across a group of sampled trajectories. However, mapping these trajectory-level advantages to policy updates requires aggregating token-level probabilities within each sequence."

> "We propose HölderPO, a generalised policy optimisation framework unifying token-level probability aggregation via the Hölder mean. By explicitly modulating the parameter p, our framework provides continuous control over the trade-off between gradient concentration and variance bounds."

> "Theoretically, we prove that a larger p concentrates the gradient to amplify sparse learning signals, whereas a smaller p strictly bounds gradient variance."

> "we instantiate the framework with a dynamic annealing algorithm that progressively schedules p across the training lifecycle"

> "Our approach achieves a state-of-the-art average accuracy of 54.9% across multiple mathematical benchmarks, yielding a substantial 7.2% relative gain over standard GRPO and secures an exceptional 93.8% success rate on ALFWorld."

### Source 4 — HRM-Text-1B (sapientinc, HuggingFace)

- Model class: AutoModelForCausalLM
- Parameters: 1182.8M
- Architecture: `hrm_text`
- Tags: `hrm` `hierarchical-reasoning` `prefix-lm` `pre-alignment` `non-chat` `non-instruction-tuned` `custom_code`
- License: apache-2.0
- Language: en
- Hierarchical Reasoning Model — distinct architectural class beyond Transformer + Mamba

## Catalog impact map

| target | nature of change | layered onto |
|---|---|---|
| **New M077** — NVFP4 pretraining + inference pipeline | ADD | M044 substrate (Blackwell PRO 6000) + M067 kernel build + M073 ternary + M046 LoRA Foundry |
| **New M078** — GRPO + HölderPO post-training pipeline | ADD | M046 LoRA Foundry + M048 Eval-Value module + M057 step 11 Learn |
| **New M079** — Interpretability surface (activation steering boundary) | ADD | M049 observability + selfdef MS039 authority levels + MS042 tool authority |
| **New M080** — HRM architectural class (Hierarchical Reasoning Model) | ADD | M048 modules map + M058 hardware-aware scheduler + selfdef MS035 capability_word.compute_mode |
| **M067** kernel build | annotate | add NVFP4 CUDA enablement path (sm_120 Blackwell architecture flag) |
| **M068** ZFS tank/models | annotate | tank/models needs NVFP4 variant directory + checksum spec |
| **M058** hardware-aware scheduler | annotate | Blackwell oracle role gains NVFP4 throughput tier + KV-cache fp4 option |
| **M073** ternary BitLinear | annotate | NOT the only low-bit option — NVFP4 complements ternary, especially for training (M073 was inference-only) |
| **M075** SRP hardware topology | annotate | Oracle Core can run NVFP4-pretrained models in 96GB Blackwell pool — extends "uncompromised FP16" to "uncompromised FP16 OR NVFP4-pretrained" |
| **M076** Profile 3 Deep Context Synthesis | annotate | `--kv-cache-dtype fp8` extended to `fp8`/`nvfp4` option |
| **selfdef MS035** capability_word.compute_mode | annotate | bit values expanded: 0=ternary 1=fp8 2=nvfp4 3=fp16 (operator-extensible) |
| **selfdef MS039** authority levels | annotate | activation steering = L4-tier white-box intervention, distinct from L0-L3 black-box (per arXiv 2604.09839) |
| **selfdef MS042** tool authority | annotate | new declaration field: `interpretability_intervention_class` (none / black-box prompt / white-box activation-steer / white-box weight-edit) |
| **M046** LoRA Foundry | annotate | adapter promotion gains 2 RL paths: GRPO baseline + HölderPO dynamic-p annealing per arXiv 2605.12058 |

## SDD/TDD implementation gate

Per operator standing direction, SDD/TDD implementation phase remains gated behind: (1) catalog complete ✓, (2) backward-sweep patches applied ✓, (3) prior-dump milestones complete ✓, (4) **external-research ingestion canon-updates applied** (this document + M077-M080). M077-M080 authoring in-progress. Gate releases once last annotation lands.

## Provenance

Ingested via Hugging Face MCP `paper_search` + `hub_repo_details` tools (authenticated user `jfortin`). WebFetch against marktechpost.com / huggingface.co returned HTTP 403; HF MCP returned full canonical metadata.
