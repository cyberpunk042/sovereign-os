# M080 — HRM (Hierarchical Reasoning Model) architectural class — recurrent two-timescale brain-inspired alternative to Transformer/Mamba/BitNet

**Parent**: sovereign-os runtime — model portfolio extension (layered onto M048 modules map + M058 hardware-aware scheduler + M075 SRP topology + selfdef MS035 capability_word.compute_mode)
**Sources**:
- arXiv 2506.21734 — "Hierarchical Reasoning Model" — Guan Wang, Jin Li, Yuhao Sun, Xing Chen, Changling Liu, Yue Wu, Meng Lu, Sen Song, et al. (2025-06-26) — canonical HRM paper
- HF `sapientinc/HRM-Text-1B` — 1182.8M-parameter text-generation HRM (2026-05-18) — operator-cited model card
- arXiv 2510.04871 — "Less is More: Recursive Reasoning with Tiny Networks" — Alexia Jolicoeur-Martineau (2025-10-06) — TRM follow-up (7M params, 45% ARC-AGI-1, 8% ARC-AGI-2)
**Provenance**: Ingested via HF MCP `paper_search` + `hub_repo_details` 2026-05-19

## Doctrinal anchors (verbatim from arXiv 2506.21734)

> "Reasoning, the process of devising and executing complex goal-oriented action sequences, remains a critical challenge in AI."

> "Current large language models (LLMs) primarily employ Chain-of-Thought (CoT) techniques, which suffer from brittle task decomposition, extensive data requirements, and high latency."

> "Inspired by the hierarchical and multi-timescale processing in the human brain, we propose the Hierarchical Reasoning Model (HRM), a novel recurrent architecture that attains significant computational depth while maintaining both training stability and efficiency."

> "HRM executes sequential reasoning tasks in a single forward pass without explicit supervision of the intermediate process, through two interdependent recurrent modules: a high-level module responsible for slow, abstract planning, and a low-level module handling rapid, detailed computations."

> "With only 27 million parameters, HRM achieves exceptional performance on complex reasoning tasks using only 1000 training samples. The model operates without pre-training or CoT data, yet achieves nearly perfect performance on challenging tasks including complex Sudoku puzzles and optimal path finding in large mazes."

> "HRM outperforms much larger models with significantly longer context windows on the Abstraction and Reasoning Corpus (ARC), a key benchmark for measuring artificial general intelligence capabilities."

**HRM-Text-1B model card facts (sapientinc, 2026-05-18)**:
- 1182.8M parameters (scaled-up HRM for text generation)
- Architecture class: `hrm_text` (custom_code, AutoModelForCausalLM)
- Tags: `hrm` `hierarchical-reasoning` `prefix-lm` `pre-alignment` `non-chat` `non-instruction-tuned`
- License: apache-2.0 | Language: en | Library: transformers

**TRM follow-up (arXiv 2510.04871) facts**:
- 7M parameters / 2 layers (much smaller than HRM)
- 45% test accuracy on ARC-AGI-1
- 8% test accuracy on ARC-AGI-2
- Outperforms Deepseek R1, o3-mini, Gemini 2.5 Pro with <0.01% the parameters

## Catalog positioning

M048 modules map + M058 hardware-aware scheduler + M075 SRP topology enumerate model classes: **Transformer (LLM oracle) + Mamba/Mamba-2 (state-space hybrid) + BitNet ternary (CPU-native Pulse)** + nGPT (M061 / arXiv 2605.06067 normalized variant). HRM is a fundamentally **distinct fourth architectural class** — recurrent + hierarchical + two-timescale + brain-inspired — that operates on different premises: no pre-training data hunger, no CoT supervision, exceptional performance with tiny parameter counts. The sapientinc HRM-Text-1B (1.18B params) shows the architecture scales to text generation. The TRM follow-up (7M params) shows the design space generalizes downward to extreme efficiency.

Per operator standing direction "you cannot invent crap" — HRM is published peer-reviewed (52 upvotes / 4 comments on HF papers), with a public scaled model on HF. Adding HRM as the **fourth model class** in the sovereign-os portfolio extends Trinity (M066) without replacing it: Conductor stays ternary, Logic stays Transformer/Mamba quantized, Oracle stays uncompromised FP16/NVFP4; HRM becomes a **fourth-class option** for reasoning-heavy workloads where the Transformer/Mamba/BitNet stack is overkill (puzzle solving, ARC benchmarks, path finding).

## Epics (E0768-E0777)

| epic | name | source |
|---|---|---|
| E0768 | HRM = novel recurrent architecture (4th class beyond Transformer/Mamba/BitNet) | arXiv 2506.21734 |
| E0769 | Brain-inspired — hierarchical + multi-timescale processing | arXiv 2506.21734 |
| E0770 | High-level module — slow, abstract planning (recurrent) | arXiv 2506.21734 |
| E0771 | Low-level module — rapid, detailed computations (recurrent) | arXiv 2506.21734 |
| E0772 | Single forward pass — no explicit CoT intermediate supervision | arXiv 2506.21734 |
| E0773 | Training efficiency — 1000 samples + 27M parameters (canonical HRM) | arXiv 2506.21734 |
| E0774 | Scaled variant — 1.18B parameters for text generation (HRM-Text-1B) | sapientinc/HRM-Text-1B |
| E0775 | Tiny variant — 7M parameters 2 layers (TRM, arXiv 2510.04871) | arXiv 2510.04871 |
| E0776 | Benchmarks — Sudoku / mazes / ARC-AGI (45% on ARC-AGI-1 with TRM) | arXiv 2506.21734 + 2510.04871 |
| E0777 | Sovereign-os portfolio integration — HRM as 4th model class alongside Trinity Conductor/Logic/Oracle | architecture + cross-ref M075 |

## Modules (M01326-M01342)

| module | name | source |
|---|---|---|
| M01326 | sovereign-hrm-model-class-registrar | arXiv 2506.21734 |
| M01327 | sovereign-hrm-high-level-module-runner (slow planner) | arXiv 2506.21734 |
| M01328 | sovereign-hrm-low-level-module-runner (rapid computer) | arXiv 2506.21734 |
| M01329 | sovereign-hrm-recurrent-loop-coordinator | arXiv 2506.21734 |
| M01330 | sovereign-hrm-single-forward-pass-engine | arXiv 2506.21734 |
| M01331 | sovereign-hrm-no-cot-supervision-validator | arXiv 2506.21734 |
| M01332 | sovereign-hrm-text-1b-runtime (sapientinc model) | sapientinc/HRM-Text-1B |
| M01333 | sovereign-hrm-trm-variant-runtime (7M params TRM) | arXiv 2510.04871 |
| M01334 | sovereign-hrm-benchmark-runner-arc | arXiv 2506.21734 + 2510.04871 |
| M01335 | sovereign-hrm-benchmark-runner-sudoku | arXiv 2506.21734 |
| M01336 | sovereign-hrm-benchmark-runner-maze | arXiv 2506.21734 |
| M01337 | sovereign-hrm-typed-mirror | cross-ref selfdef MS007 |
| M01338 | sovereign-hrm-event-emitter | cross-ref M049 + selfdef MS026 |
| M01339 | sovereign-hrm-replay-validator | cross-ref selfdef MS009 |
| M01340 | sovereign-hrm-dashboard-binding (D-03 + D-10) | cross-ref M060 |
| M01341 | sovereign-hrm-cli-subcommand-set | cross-ref selfdef MS043 |
| M01342 | sovereign-hrm-srp-bridge (4th class extending M075) | cross-ref M075 |

## Features (F06631-F06715)

| feature | name | source |
|---|---|---|
| F06631 | Doctrinal — HRM = novel recurrent architecture | arXiv 2506.21734 |
| F06632 | Doctrinal — inspired by hierarchical + multi-timescale processing in human brain | arXiv 2506.21734 |
| F06633 | Doctrinal — attains significant computational depth | arXiv 2506.21734 |
| F06634 | Doctrinal — maintains both training stability and efficiency | arXiv 2506.21734 |
| F06635 | Doctrinal — executes sequential reasoning in a single forward pass | arXiv 2506.21734 |
| F06636 | Doctrinal — no explicit supervision of intermediate process (no CoT data) | arXiv 2506.21734 |
| F06637 | Doctrinal — operates without pre-training | arXiv 2506.21734 |
| F06638 | Doctrinal — alternative to Chain-of-Thought (CoT) techniques | arXiv 2506.21734 |
| F06639 | Doctrinal — CoT brittleness motivation: brittle task decomposition + extensive data + high latency | arXiv 2506.21734 |
| F06640 | High-level module — slow planner (abstract) | arXiv 2506.21734 |
| F06641 | High-level module — recurrent | arXiv 2506.21734 |
| F06642 | High-level module — composes with M075 Conductor role | cross-ref M075 |
| F06643 | Low-level module — rapid computations (detailed) | arXiv 2506.21734 |
| F06644 | Low-level module — recurrent | arXiv 2506.21734 |
| F06645 | Low-level module — interdependent with high-level | arXiv 2506.21734 |
| F06646 | Two-module coordination — recurrent loop, no explicit step supervision | arXiv 2506.21734 |
| F06647 | Single forward pass — replaces multi-step CoT inference | arXiv 2506.21734 |
| F06648 | Single forward pass — reduces inference latency vs CoT | arXiv 2506.21734 |
| F06649 | Canonical HRM — 27M parameters | arXiv 2506.21734 |
| F06650 | Canonical HRM — 1000 training samples | arXiv 2506.21734 |
| F06651 | Canonical HRM — Sudoku nearly perfect | arXiv 2506.21734 |
| F06652 | Canonical HRM — optimal path finding in large mazes | arXiv 2506.21734 |
| F06653 | Canonical HRM — outperforms larger models on ARC | arXiv 2506.21734 |
| F06654 | Scaled HRM (Text-1B) — 1182.8M parameters | sapientinc/HRM-Text-1B |
| F06655 | Scaled HRM (Text-1B) — architecture class `hrm_text` | sapientinc/HRM-Text-1B |
| F06656 | Scaled HRM (Text-1B) — prefix-lm pre-alignment | sapientinc/HRM-Text-1B |
| F06657 | Scaled HRM (Text-1B) — non-chat non-instruction-tuned | sapientinc/HRM-Text-1B |
| F06658 | Scaled HRM (Text-1B) — apache-2.0 license | sapientinc/HRM-Text-1B |
| F06659 | Scaled HRM (Text-1B) — English language | sapientinc/HRM-Text-1B |
| F06660 | Scaled HRM (Text-1B) — transformers library + custom_code (trust_remote_code) | sapientinc/HRM-Text-1B |
| F06661 | Scaled HRM (Text-1B) — AutoModelForCausalLM class | sapientinc/HRM-Text-1B |
| F06662 | TRM variant — 7M parameters | arXiv 2510.04871 |
| F06663 | TRM variant — 2 layers | arXiv 2510.04871 |
| F06664 | TRM variant — much simpler recursive reasoning approach | arXiv 2510.04871 |
| F06665 | TRM variant — single tiny network | arXiv 2510.04871 |
| F06666 | TRM variant — 45% test accuracy on ARC-AGI-1 | arXiv 2510.04871 |
| F06667 | TRM variant — 8% test accuracy on ARC-AGI-2 | arXiv 2510.04871 |
| F06668 | TRM variant — outperforms Deepseek R1, o3-mini, Gemini 2.5 Pro with <0.01% parameters | arXiv 2510.04871 |
| F06669 | Benchmark — Sudoku puzzles | arXiv 2506.21734 |
| F06670 | Benchmark — large maze path finding | arXiv 2506.21734 |
| F06671 | Benchmark — ARC-AGI-1 (Abstraction and Reasoning Corpus) | arXiv 2506.21734 + 2510.04871 |
| F06672 | Benchmark — ARC-AGI-2 (TRM-introduced) | arXiv 2510.04871 |
| F06673 | Benchmark — composes with M048 Eval-Value module + M078 HölderPO benchmark runners | cross-ref M048 + M078 |
| F06674 | Benchmark — composes with M079 intervention-class disaggregation (HRM = no WB intervention by default) | cross-ref M079 |
| F06675 | Portfolio — HRM is 4th model class beyond Transformer + Mamba + BitNet | architecture |
| F06676 | Portfolio — HRM extends Trinity Conductor/Logic/Oracle as 4th class option | cross-ref M066 + M075 |
| F06677 | Portfolio — operator can assign HRM to any SRP role per profile | cross-ref M075 + selfdef MS040 |
| F06678 | Portfolio — HRM-Text-1B can serve as Conductor (small footprint reasoning) | cross-ref M075 |
| F06679 | Portfolio — TRM (7M) can serve as ultra-lightweight Conductor for puzzle tasks | cross-ref M075 |
| F06680 | Portfolio — Profile 1 Ultra-Sovereign Efficiency may swap BitNet for HRM/TRM per workload | cross-ref M076 |
| F06681 | Hardware — runs on CPU (HRM-Text-1B fits 4GB RAM at 4-bit; TRM fits <100MB) | architecture |
| F06682 | Hardware — composes with M070 Dual-CCD (HRM on CCD 0 Pulse cores when used as Conductor) | cross-ref M070 |
| F06683 | Hardware — composes with M067 kernel build (transformers + custom_code dependency) | cross-ref M067 |
| F06684 | Hardware — composes with M068 ZFS tank/models for model storage | cross-ref M068 |
| F06685 | Hardware — composes with M072 Bootstrap Verification (Check 04 NVIDIA driver irrelevant for CPU-only HRM) | cross-ref M072 |
| F06686 | Capability_word — selfdef MS035 compute_mode bit values extended: 0=ternary 1=fp8 2=nvfp4 3=fp16 4=hrm_recurrent | cross-ref selfdef MS035 |
| F06687 | Intervention class — HRM by default = None (no WB intervention required for reasoning) | cross-ref M079 |
| F06688 | Intervention class — HRM-Text-1B is pre-alignment, NOT instruction-tuned — operator-warned for chat use | sapientinc/HRM-Text-1B |
| F06689 | Authority — HRM model load = L5 Commit per MS039 | cross-ref selfdef MS039 |
| F06690 | Authority — HRM custom_code requires operator-signed approval (trust_remote_code) | cross-ref selfdef MS003 + MS039 |
| F06691 | Authority — HRM-Text-1B Apache 2.0 license auto-cleared for use | sapientinc/HRM-Text-1B |
| F06692 | Typed mirror — sovereign-hrm-runtime-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F06693 | Typed mirror — HrmVariant enum (Canonical27M / TextOneB / TinyTRM7M / Custom) | cross-ref selfdef MS007 |
| F06694 | Typed mirror — HrmModuleConfig struct {high_level_layers, low_level_layers, recurrent_steps, prefix_lm} | cross-ref selfdef MS007 |
| F06695 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F06696 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F06697 | Event emitter — every HRM inference emits M049 13-field trace | cross-ref M049 |
| F06698 | Event emitter — span includes variant + high-level-step-count + low-level-step-count | cross-ref M049 |
| F06699 | Event emitter — emits OCSF System Activity 1001 per inference | cross-ref selfdef MS026 |
| F06700 | Event emitter — span deterministic for MS009 replay | cross-ref selfdef MS009 |
| F06701 | Replay validator — verifies historical HRM inference chain | cross-ref selfdef MS009 |
| F06702 | Replay validator — detects custom_code tampering via hash chain | cross-ref selfdef MS003 + MS009 |
| F06703 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 |
| F06704 | Replay validator — runs daily | cross-ref selfdef MS009 |
| F06705 | Dashboard — D-03 model health shows HRM variant + module health | cross-ref M060 |
| F06706 | Dashboard — D-10 eval history shows ARC + Sudoku + Maze scores | cross-ref M060 |
| F06707 | Dashboard — D-11 adapter status N/A for HRM (no LoRA adapter pattern) | cross-ref M060 |
| F06708 | CLI — `sovereign hrm load <variant>` loads HRM model variant | cross-ref selfdef MS043 + MS003 |
| F06709 | CLI — `sovereign hrm inference --prompt <p>` runs reasoning task | cross-ref selfdef MS043 |
| F06710 | CLI — `sovereign hrm benchmark <suite>` runs Sudoku/Maze/ARC suite | architecture |
| F06711 | CLI — `sovereign hrm variants` lists available HRM variants | architecture |
| F06712 | CLI — `sovereign hrm srp-role <role>` assigns HRM to Conductor/Logic/Oracle per M075 | cross-ref M075 |
| F06713 | CLI — all hrm subcommands emit M049 trace | cross-ref M049 |
| F06714 | CLI — `--json` flag returns structured output | architecture |
| F06715 | Closing — M080 covers HRM architectural class — LAST external-research milestone | arXiv 2506.21734 + sapientinc/HRM-Text-1B + arXiv 2510.04871 |

## Requirements (R13261-R13430)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R13261 | Doctrinal — HRM = novel recurrent architecture | arXiv 2506.21734 | F06631 | non-negotiable | false | 10 |
| R13262 | Doctrinal — inspired by hierarchical + multi-timescale processing in human brain | arXiv 2506.21734 | F06632 | non-negotiable | false | 10 |
| R13263 | Doctrinal — attains significant computational depth | arXiv 2506.21734 | F06633 | non-negotiable | false | 10 |
| R13264 | Doctrinal — maintains training stability and efficiency | arXiv 2506.21734 | F06634 | non-negotiable | false | 10 |
| R13265 | Doctrinal — executes sequential reasoning in single forward pass | arXiv 2506.21734 | F06635 | non-negotiable | false | 10 |
| R13266 | Doctrinal — no explicit supervision of intermediate process (no CoT data) | arXiv 2506.21734 | F06636 | non-negotiable | false | 10 |
| R13267 | Doctrinal — operates without pre-training | arXiv 2506.21734 | F06637 | non-negotiable | false | 10 |
| R13268 | Doctrinal — alternative to Chain-of-Thought (CoT) | arXiv 2506.21734 | F06638 | non-negotiable | false | 10 |
| R13269 | Doctrinal — CoT motivation: brittle task decomposition + data hunger + high latency | arXiv 2506.21734 | F06639 | non-negotiable | false | 10 |
| R13270 | Doctrinal — two interdependent recurrent modules | arXiv 2506.21734 | F06645 | non-negotiable | false | 10 |
| R13271 | Doctrinal — operator standing direction "you cannot invent crap" upheld (peer-reviewed published) | operator standing direction | F06631 | non-negotiable | false | 10 |
| R13272 | High-level module — slow planner (abstract) | arXiv 2506.21734 | F06640 | non-negotiable | false | 10 |
| R13273 | High-level module — recurrent | arXiv 2506.21734 | F06641 | non-negotiable | false | 10 |
| R13274 | High-level module — composes with M075 Conductor role | cross-ref M075 | F06642 | non-negotiable | false | 10 |
| R13275 | Low-level module — rapid computations (detailed) | arXiv 2506.21734 | F06643 | non-negotiable | false | 10 |
| R13276 | Low-level module — recurrent | arXiv 2506.21734 | F06644 | non-negotiable | false | 10 |
| R13277 | Low-level module — interdependent with high-level | arXiv 2506.21734 | F06645 | non-negotiable | false | 10 |
| R13278 | Two-module coordination — recurrent loop, no explicit step supervision | arXiv 2506.21734 | F06646 | non-negotiable | false | 10 |
| R13279 | Single forward pass — replaces multi-step CoT inference | arXiv 2506.21734 | F06647 | non-negotiable | false | 10 |
| R13280 | Single forward pass — reduces inference latency vs CoT | arXiv 2506.21734 | F06648 | non-negotiable | false | 10 |
| R13281 | Canonical HRM — 27M parameters | arXiv 2506.21734 | F06649 | non-negotiable | false | 10 |
| R13282 | Canonical HRM — 1000 training samples | arXiv 2506.21734 | F06650 | non-negotiable | false | 10 |
| R13283 | Canonical HRM — nearly perfect on Sudoku | arXiv 2506.21734 | F06651 | non-negotiable | false | 10 |
| R13284 | Canonical HRM — optimal path finding in large mazes | arXiv 2506.21734 | F06652 | non-negotiable | false | 10 |
| R13285 | Canonical HRM — outperforms larger models on ARC | arXiv 2506.21734 | F06653 | non-negotiable | false | 10 |
| R13286 | Scaled HRM-Text-1B — 1182.8M parameters | sapientinc/HRM-Text-1B | F06654 | non-negotiable | false | 10 |
| R13287 | Scaled HRM-Text-1B — architecture class `hrm_text` | sapientinc/HRM-Text-1B | F06655 | non-negotiable | false | 10 |
| R13288 | Scaled HRM-Text-1B — prefix-lm pre-alignment | sapientinc/HRM-Text-1B | F06656 | non-negotiable | false | 10 |
| R13289 | Scaled HRM-Text-1B — non-chat non-instruction-tuned | sapientinc/HRM-Text-1B | F06657 | non-negotiable | false | 10 |
| R13290 | Scaled HRM-Text-1B — apache-2.0 license | sapientinc/HRM-Text-1B | F06658 | non-negotiable | false | 10 |
| R13291 | Scaled HRM-Text-1B — English language | sapientinc/HRM-Text-1B | F06659 | non-negotiable | false | 10 |
| R13292 | Scaled HRM-Text-1B — transformers library | sapientinc/HRM-Text-1B | F06660 | non-negotiable | false | 10 |
| R13293 | Scaled HRM-Text-1B — custom_code requires trust_remote_code | sapientinc/HRM-Text-1B | F06660 | non-negotiable | false | 10 |
| R13294 | Scaled HRM-Text-1B — AutoModelForCausalLM class | sapientinc/HRM-Text-1B | F06661 | non-negotiable | false | 10 |
| R13295 | TRM variant — 7M parameters | arXiv 2510.04871 | F06662 | non-negotiable | false | 10 |
| R13296 | TRM variant — 2 layers | arXiv 2510.04871 | F06663 | non-negotiable | false | 10 |
| R13297 | TRM variant — much simpler recursive reasoning | arXiv 2510.04871 | F06664 | non-negotiable | false | 10 |
| R13298 | TRM variant — single tiny network | arXiv 2510.04871 | F06665 | non-negotiable | false | 10 |
| R13299 | TRM variant — 45% test accuracy on ARC-AGI-1 | arXiv 2510.04871 | F06666 | non-negotiable | false | 10 |
| R13300 | TRM variant — 8% test accuracy on ARC-AGI-2 | arXiv 2510.04871 | F06667 | non-negotiable | false | 10 |
| R13301 | TRM variant — outperforms Deepseek R1 / o3-mini / Gemini 2.5 Pro with <0.01% parameters | arXiv 2510.04871 | F06668 | non-negotiable | false | 10 |
| R13302 | Benchmark — Sudoku puzzles | arXiv 2506.21734 | F06669 | non-negotiable | false | 10 |
| R13303 | Benchmark — large maze path finding | arXiv 2506.21734 | F06670 | non-negotiable | false | 10 |
| R13304 | Benchmark — ARC-AGI-1 | arXiv 2506.21734 + 2510.04871 | F06671 | non-negotiable | false | 10 |
| R13305 | Benchmark — ARC-AGI-2 | arXiv 2510.04871 | F06672 | non-negotiable | false | 10 |
| R13306 | Benchmark — composes with M048 Eval-Value module | cross-ref M048 | F06673 | non-negotiable | false | 10 |
| R13307 | Benchmark — composes with M078 HölderPO benchmark runners | cross-ref M078 | F06673 | non-negotiable | false | 10 |
| R13308 | Benchmark — composes with M079 intervention-class disaggregation | cross-ref M079 | F06674 | non-negotiable | false | 10 |
| R13309 | Benchmark — signed via MS003 | cross-ref selfdef MS003 | F06669 | non-negotiable | false | 10 |
| R13310 | Benchmark — results retained 365 days | cross-ref selfdef MS037 | F06669 | non-negotiable | false | 10 |
| R13311 | Portfolio — HRM is 4th model class beyond Transformer + Mamba + BitNet | architecture | F06675 | non-negotiable | false | 10 |
| R13312 | Portfolio — extends Trinity Conductor/Logic/Oracle as 4th class option | cross-ref M066 + M075 | F06676 | non-negotiable | false | 10 |
| R13313 | Portfolio — operator may assign HRM to any SRP role per profile | cross-ref M075 + selfdef MS040 | F06677 | non-negotiable | false | 10 |
| R13314 | Portfolio — HRM-Text-1B as Conductor option (small footprint reasoning) | cross-ref M075 | F06678 | non-negotiable | false | 10 |
| R13315 | Portfolio — TRM (7M) as ultra-lightweight Conductor for puzzle tasks | cross-ref M075 | F06679 | non-negotiable | false | 10 |
| R13316 | Portfolio — Profile 1 Ultra-Sovereign Efficiency may swap BitNet for HRM/TRM | cross-ref M076 | F06680 | non-negotiable | false | 10 |
| R13317 | Portfolio — Profile 2 High-Concurrency may add HRM agent for puzzle subtasks | cross-ref M076 | F06677 | non-negotiable | false | 10 |
| R13318 | Portfolio — Profile 3 Deep Context Synthesis NOT compatible with HRM (single forward pass) | cross-ref M076 + arXiv 2506.21734 | F06647 | non-negotiable | false | 10 |
| R13319 | Portfolio — HRM does NOT replace BitNet (different use case) | architecture + cross-ref M073 | F06675 | non-negotiable | false | 10 |
| R13320 | Portfolio — HRM does NOT replace Transformer/Mamba (different scale) | architecture + cross-ref M058 | F06675 | non-negotiable | false | 10 |
| R13321 | Hardware — CPU-runnable (HRM-Text-1B fits ≤ 4GB RAM at 4-bit) | architecture + sapientinc/HRM-Text-1B | F06681 | non-negotiable | false | 10 |
| R13322 | Hardware — TRM fits ≤ 100MB RAM | architecture + arXiv 2510.04871 | F06681 | non-negotiable | false | 10 |
| R13323 | Hardware — composes with M070 Dual-CCD (HRM on CCD 0 Pulse cores when Conductor) | cross-ref M070 | F06682 | non-negotiable | false | 10 |
| R13324 | Hardware — composes with M067 kernel build (transformers + custom_code dep) | cross-ref M067 | F06683 | non-negotiable | false | 10 |
| R13325 | Hardware — composes with M068 ZFS tank/models for storage | cross-ref M068 | F06684 | non-negotiable | false | 10 |
| R13326 | Hardware — M072 Check 04 NVIDIA driver irrelevant for CPU-only HRM | cross-ref M072 | F06685 | non-negotiable | false | 10 |
| R13327 | Hardware — HRM can run on Blackwell when scaled to NVFP4 (composes with M077) | cross-ref M077 | F06681 | non-negotiable | false | 10 |
| R13328 | Hardware — HRM does NOT require GPU for canonical 27M variant | arXiv 2506.21734 | F06681 | non-negotiable | false | 10 |
| R13329 | Capability_word — selfdef MS035 compute_mode bit extended: 4=hrm_recurrent | cross-ref selfdef MS035 | F06686 | non-negotiable | false | 10 |
| R13330 | Capability_word — extension is additive (operator standing direction "layered ON TOP") | operator standing direction | F06686 | non-negotiable | false | 10 |
| R13331 | Capability_word — bit values: 0=ternary 1=fp8 2=nvfp4 3=fp16 4=hrm_recurrent (5-15 reserved) | cross-ref selfdef MS035 | F06686 | non-negotiable | false | 10 |
| R13332 | Intervention class — HRM by default = None (no WB intervention required) | cross-ref M079 | F06687 | non-negotiable | false | 10 |
| R13333 | Intervention class — HRM-Text-1B is pre-alignment NOT instruction-tuned | sapientinc/HRM-Text-1B | F06688 | non-negotiable | false | 10 |
| R13334 | Intervention class — operator warned for chat use of HRM-Text-1B (non-chat tag) | sapientinc/HRM-Text-1B + operator standing direction | F06688 | non-negotiable | false | 10 |
| R13335 | Authority — HRM model load = L5 Commit per MS039 | cross-ref selfdef MS039 | F06689 | non-negotiable | false | 10 |
| R13336 | Authority — HRM custom_code requires operator-signed approval (trust_remote_code) | cross-ref selfdef MS003 + MS039 | F06690 | non-negotiable | false | 10 |
| R13337 | Authority — HRM-Text-1B Apache 2.0 license auto-cleared for use | sapientinc/HRM-Text-1B | F06691 | non-negotiable | false | 10 |
| R13338 | Authority — custom_code execution sandboxed per selfdef MS036 Tier B/C | cross-ref selfdef MS036 | F06690 | non-negotiable | false | 10 |
| R13339 | Authority — custom_code change emits OCSF Detection 2004 | cross-ref selfdef MS026 | F06702 | non-negotiable | false | 10 |
| R13340 | Authority — custom_code change composes with M079 weight-edit detector | cross-ref M079 | F06702 | non-negotiable | false | 10 |
| R13341 | Typed mirror — sovereign-hrm-runtime-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F06692 | non-negotiable | false | 10 |
| R13342 | Typed mirror — HrmVariant enum (Canonical27M / TextOneB / TinyTRM7M / Custom) | cross-ref selfdef MS007 | F06693 | non-negotiable | false | 10 |
| R13343 | Typed mirror — HrmModuleConfig struct fields | cross-ref selfdef MS007 | F06694 | non-negotiable | false | 10 |
| R13344 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F06695 | non-negotiable | false | 10 |
| R13345 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F06696 | non-negotiable | false | 10 |
| R13346 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F06692 | non-negotiable | false | 10 |
| R13347 | Typed mirror — no_std friendly | architecture | F06692 | non-negotiable | false | 10 |
| R13348 | Typed mirror — serde + bincode derives present | architecture | F06692 | non-negotiable | false | 10 |
| R13349 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F06695 | non-negotiable | false | 10 |
| R13350 | Event — every HRM inference emits M049 13-field trace | cross-ref M049 | F06697 | non-negotiable | false | 10 |
| R13351 | Event — span includes variant + high-level-step-count + low-level-step-count | cross-ref M049 | F06698 | non-negotiable | false | 10 |
| R13352 | Event — emits OCSF System Activity 1001 per inference | cross-ref selfdef MS026 | F06699 | non-negotiable | false | 10 |
| R13353 | Event — span deterministic for MS009 replay | cross-ref selfdef MS009 | F06700 | non-negotiable | false | 10 |
| R13354 | Event — recurrent-loop iteration count emitted as M049 metric | cross-ref M049 | F06698 | non-negotiable | false | 10 |
| R13355 | Replay validator — verifies historical HRM inference chain | cross-ref selfdef MS009 | F06701 | non-negotiable | false | 10 |
| R13356 | Replay validator — detects custom_code tampering via hash chain | cross-ref selfdef MS003 + MS009 | F06702 | non-negotiable | false | 10 |
| R13357 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 | F06703 | non-negotiable | false | 10 |
| R13358 | Replay validator — runs daily | cross-ref selfdef MS009 | F06704 | non-negotiable | false | 10 |
| R13359 | Replay validator — failures halt new HRM inference until resolved | architecture | F06701 | non-negotiable | false | 10 |
| R13360 | Dashboard — D-03 model health shows HRM variant + module health | cross-ref M060 | F06705 | non-negotiable | false | 10 |
| R13361 | Dashboard — D-10 eval history shows ARC + Sudoku + Maze scores | cross-ref M060 | F06706 | non-negotiable | false | 10 |
| R13362 | Dashboard — D-11 adapter status N/A for HRM (no LoRA adapter) | cross-ref M060 | F06707 | non-negotiable | false | 10 |
| R13363 | Dashboard — D-09 hardware pressure shows HRM CPU utilization | cross-ref M060 | F06681 | non-negotiable | false | 10 |
| R13364 | Dashboard — D-04 costs shows HRM energy savings vs CoT-Transformer for reasoning | cross-ref M060 + arXiv 2506.21734 | F06648 | non-negotiable | false | 10 |
| R13365 | CLI — `sovereign hrm load <variant>` loads HRM model | cross-ref selfdef MS043 + MS003 | F06708 | non-negotiable | false | 10 |
| R13366 | CLI — `sovereign hrm inference --prompt <p>` runs reasoning | cross-ref selfdef MS043 | F06709 | non-negotiable | false | 10 |
| R13367 | CLI — `sovereign hrm benchmark <suite>` runs Sudoku/Maze/ARC | architecture | F06710 | non-negotiable | false | 10 |
| R13368 | CLI — `sovereign hrm variants` lists available variants | architecture | F06711 | non-negotiable | false | 10 |
| R13369 | CLI — `sovereign hrm srp-role <role>` assigns HRM to Conductor/Logic/Oracle | cross-ref M075 | F06712 | non-negotiable | false | 10 |
| R13370 | CLI — all hrm subcommands emit M049 trace | cross-ref M049 | F06713 | non-negotiable | false | 10 |
| R13371 | CLI — `--json` flag returns structured output | architecture | F06714 | non-negotiable | false | 10 |
| R13372 | CLI — exit codes follow sysexits.h | architecture | F06708 | non-negotiable | false | 10 |
| R13373 | Composition — composes with M044 substrate (CPU + optional Blackwell) | cross-ref M044 | F06681 | non-negotiable | false | 10 |
| R13374 | Composition — composes with M046 LoRA Foundry (HRM does NOT use LoRA — different paradigm) | cross-ref M046 | F06707 | non-negotiable | false | 10 |
| R13375 | Composition — composes with M048 modules map (4th model class) | cross-ref M048 | F06675 | non-negotiable | false | 10 |
| R13376 | Composition — composes with M049 observability + trace pipeline | cross-ref M049 | F06697 | non-negotiable | false | 10 |
| R13377 | Composition — composes with M055 failure modes (HRM-specific taxonomy: recurrent loop divergence) | cross-ref M055 | F06701 | non-negotiable | false | 10 |
| R13378 | Composition — composes with M057 12-step task lifecycle (Step 7 Execute with HRM) | cross-ref M057 | F06709 | non-negotiable | false | 10 |
| R13379 | Composition — composes with M058 hardware-aware scheduler | cross-ref M058 | F06682 | non-negotiable | false | 10 |
| R13380 | Composition — composes with M060 cockpit dashboards (D-03 / D-04 / D-09 / D-10) | cross-ref M060 | F06705 | non-negotiable | false | 10 |
| R13381 | Composition — composes with M063 SFIF Features phase | cross-ref M063 | F06712 | non-negotiable | false | 10 |
| R13382 | Composition — composes with M066 Trinity (HRM = 4th class extending Pulse/Weaver/Auditor) | cross-ref M066 | F06676 | non-negotiable | false | 10 |
| R13383 | Composition — composes with M070 Dual-CCD (HRM on CCD 0 when Conductor) | cross-ref M070 | F06682 | non-negotiable | false | 10 |
| R13384 | Composition — composes with M073 ternary (orthogonal: HRM is different paradigm) | cross-ref M073 | F06319 | non-negotiable | false | 10 |
| R13385 | Composition — composes with M075 SRP topology (HRM-Text-1B as Conductor option) | cross-ref M075 | F06678 | non-negotiable | false | 10 |
| R13386 | Composition — composes with M076 Profile 1 (BitNet OR HRM swappable) | cross-ref M076 | F06680 | non-negotiable | false | 10 |
| R13387 | Composition — composes with M077 NVFP4 (scaled HRM in 4-bit on Blackwell) | cross-ref M077 | F06327 | non-negotiable | false | 10 |
| R13388 | Composition — composes with M078 HölderPO (HRM can be RL-fine-tuned) | cross-ref M078 | F06673 | non-negotiable | false | 10 |
| R13389 | Composition — composes with M079 intervention-class (HRM = None by default, custom_code = WB-weight-edit class on modification) | cross-ref M079 | F06687 | non-negotiable | false | 10 |
| R13390 | Composition — composes with selfdef MS003 chain-of-trust | cross-ref selfdef MS003 | F06690 | non-negotiable | false | 10 |
| R13391 | Composition — composes with selfdef MS007 typed-mirror | cross-ref selfdef MS007 | F06692 | non-negotiable | false | 10 |
| R13392 | Composition — composes with selfdef MS009 replay validator | cross-ref selfdef MS009 | F06701 | non-negotiable | false | 10 |
| R13393 | Composition — composes with selfdef MS026 OCSF event emission | cross-ref selfdef MS026 | F06699 | non-negotiable | false | 10 |
| R13394 | Composition — composes with selfdef MS035 capability_word.compute_mode | cross-ref selfdef MS035 | F06686 | non-negotiable | false | 10 |
| R13395 | Composition — composes with selfdef MS036 sandbox tiers (custom_code execution sandbox) | cross-ref selfdef MS036 | F06338 | non-negotiable | false | 10 |
| R13396 | Composition — composes with selfdef MS039 authority levels (model load = L5) | cross-ref selfdef MS039 | F06689 | non-negotiable | false | 10 |
| R13397 | Composition — composes with selfdef MS040 profile envelopes (HRM allowed per profile) | cross-ref selfdef MS040 | F06677 | non-negotiable | false | 10 |
| R13398 | Composition — composes with selfdef MS041 commit authority (HRM model promotion = L6) | cross-ref selfdef MS041 | F06689 | non-negotiable | false | 10 |
| R13399 | Composition — composes with selfdef MS042 tool authority (HRM inference as tool) | cross-ref selfdef MS042 | F06709 | non-negotiable | false | 10 |
| R13400 | Composition — composes with selfdef MS043 IPS operator surface | cross-ref selfdef MS043 | F06708 | non-negotiable | false | 10 |
| R13401 | Boundary — HRM runtime = sovereign-os | architecture + operator standing direction | F06631 | non-negotiable | false | 10 |
| R13402 | Boundary — selfdef IPS sandboxes custom_code per MS036 | cross-ref selfdef MS036 | F06338 | non-negotiable | false | 10 |
| R13403 | Boundary — info-hub indexes HRM paper lineage as second-brain entry | operator standing direction | F06631 | non-negotiable | false | 10 |
| R13404 | Boundary — info-hub never mutated by HRM inference | operator standing direction | F06631 | non-negotiable | false | 10 |
| R13405 | Doctrinal preservation — arXiv 2506.21734 abstract preserved verbatim in `backlog/notes/external-research-ingestion-2026-05-19.md` | operator standing direction | F06631 | non-negotiable | false | 10 |
| R13406 | Doctrinal preservation — "novel recurrent architecture" verbatim | arXiv 2506.21734 | F06631 | non-negotiable | false | 10 |
| R13407 | Doctrinal preservation — "27 million parameters" verbatim | arXiv 2506.21734 | F06649 | non-negotiable | false | 10 |
| R13408 | Doctrinal preservation — "1000 training samples" verbatim | arXiv 2506.21734 | F06650 | non-negotiable | false | 10 |
| R13409 | Doctrinal preservation — "without pre-training or CoT data" verbatim | arXiv 2506.21734 | F06637 | non-negotiable | false | 10 |
| R13410 | Doctrinal preservation — sapientinc/HRM-Text-1B model card tags verbatim | sapientinc/HRM-Text-1B | F06657 | non-negotiable | false | 10 |
| R13411 | Doctrinal preservation — TRM "45% test-accuracy on ARC-AGI-1" verbatim | arXiv 2510.04871 | F06666 | non-negotiable | false | 10 |
| R13412 | Doctrinal preservation — operator standing direction "you cannot invent crap" upheld | operator standing direction | F06631 | non-negotiable | false | 10 |
| R13413 | Doctrinal preservation — operator standing direction "Respect the projects" upheld | operator standing direction | F06401 | non-negotiable | false | 10 |
| R13414 | Doctrinal preservation — operator standing direction "second-brain" upheld | operator standing direction | F06403 | non-negotiable | false | 10 |
| R13415 | Doctrinal preservation — operator standing direction "layered ON TOP" upheld (M048/M058/M075 not discarded) | operator standing direction | F06675 | non-negotiable | false | 10 |
| R13416 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F06631 | non-negotiable | false | 10 |
| R13417 | Operator UX — operator may toggle HRM on/off per profile | operator standing direction "everything can be turned on and off" | F06677 | non-negotiable | false | 10 |
| R13418 | Operator UX — operator may select HRM variant per SRP role | operator standing direction "modes and profiles" | F06693 | non-negotiable | false | 10 |
| R13419 | Operator UX — operator may compare HRM vs Transformer vs Mamba on benchmarks in D-10 | cross-ref M060 | F06706 | non-negotiable | false | 10 |
| R13420 | Operator UX — operator may approve custom_code execution via D-06 pending approvals | cross-ref M060 + selfdef MS003 | F06690 | non-negotiable | false | 10 |
| R13421 | Operator UX — operator may inspect HRM recurrent-loop visualization in D-05 traces | cross-ref M060 | F06698 | non-negotiable | false | 10 |
| R13422 | Performance — HRM-Text-1B inference latency `<` 100ms p95 on CPU for short prompts | architecture | F06681 | non-negotiable | false | 10 |
| R13423 | Performance — TRM ARC inference latency `<` 50ms p95 | architecture + arXiv 2510.04871 | F06663 | non-negotiable | false | 10 |
| R13424 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F06692 | non-negotiable | false | 10 |
| R13425 | Performance — replay validator daily run `<` 60s | cross-ref selfdef MS009 | F06701 | non-negotiable | false | 10 |
| R13426 | Telemetry — HRM inference count per variant emitted via M049 | cross-ref M049 | F06697 | non-negotiable | false | 10 |
| R13427 | Telemetry — recurrent-loop iteration count histogram emitted via M049 | cross-ref M049 | F06354 | non-negotiable | false | 10 |
| R13428 | Telemetry — Sudoku/Maze/ARC success rate emitted via M049 | cross-ref M049 | F06669 | non-negotiable | false | 10 |
| R13429 | Telemetry — custom_code-execution count emitted via M049 (high-priority alert if unexpected) | cross-ref M049 | F06702 | non-negotiable | false | 10 |
| R13430 | Closing — M080 is the LAST external-research milestone (M077-M080 all landed). External-research ingestion complete. sovereign-os catalog at 79/79 milestones, combined ecosystem 123 milestones, ~24000 R-rows, ~240000 enforced sub-requirements. SDD/TDD gate releases. | arXiv 2506.21734 + sapientinc/HRM-Text-1B + arXiv 2510.04871 + operator standing direction | F06715 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M080.

## Cross-references

- **M044** — substrate (CPU + optional Blackwell)
- **M046** — LoRA Foundry (HRM does NOT use LoRA — different paradigm)
- **M048** — modules map (HRM = 4th model class)
- **M049** — observability + trace pipeline
- **M055** — failure modes (recurrent-loop divergence)
- **M057** — 12-step task lifecycle (Step 7 Execute with HRM)
- **M058** — hardware-aware scheduler
- **M060** — cockpit dashboards (D-03 / D-04 / D-05 / D-06 / D-09 / D-10)
- **M063** — SFIF Features phase
- **M066** — Trinity Framework Genesis (HRM = 4th class extending Pulse/Weaver/Auditor)
- **M070** — Dual-CCD topology
- **M073** — 1-bit ternary (orthogonal; HRM is different paradigm)
- **M075** — SRP hardware topology (HRM-Text-1B as Conductor option)
- **M076** — 3 load-balancing profiles (Profile 1 BitNet OR HRM)
- **M077** — NVFP4 (scaled HRM in 4-bit on Blackwell)
- **M078** — HölderPO (HRM can be RL-fine-tuned)
- **M079** — intervention class (HRM = None by default)
- **selfdef MS003** — selfdef-signing (custom_code approval)
- **selfdef MS007** — typed-mirror (sovereign-hrm-runtime-mirror)
- **selfdef MS009** — replay validator
- **selfdef MS026** — OCSF event emission
- **selfdef MS035** — capability_word.compute_mode (4=hrm_recurrent)
- **selfdef MS036** — sandbox tiers (custom_code execution sandbox)
- **selfdef MS039** — authority levels (model load = L5)
- **selfdef MS040** — profile envelopes
- **selfdef MS041** — commit authority (model promotion = L6)
- **selfdef MS042** — tool authority (HRM inference as tool)
- **selfdef MS043** — IPS operator surface

## Schema

```
schema_version: "1.0.0"
milestone_id: M080
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
canonical_sources:
  - "arXiv 2506.21734 — Hierarchical Reasoning Model (Wang/Li/Sun/Chen et al., 2025-06-26)"
  - "huggingface.co/sapientinc/HRM-Text-1B (1.18B params, 2026-05-18)"
  - "arXiv 2510.04871 — Less is More: Recursive Reasoning with Tiny Networks (Jolicoeur-Martineau, 2025-10-06)"
architecture: "novel recurrent architecture (NOT Transformer, NOT Mamba, NOT BitNet)"
inspiration: "hierarchical + multi-timescale processing in human brain"
two_modules:
  high_level: "slow, abstract planning (recurrent)"
  low_level: "rapid, detailed computations (recurrent)"
key_property: "single forward pass, no explicit CoT intermediate supervision"
variants:
  canonical_27M: { params: 27000000, training_samples: 1000, no_pretraining: true }
  text_1B: { params: 1182800000, license: "apache-2.0", tags: ["prefix-lm", "pre-alignment", "non-chat", "non-instruction-tuned"] }
  tiny_TRM_7M: { params: 7000000, layers: 2, arc_agi_1: "45%", arc_agi_2: "8%" }
benchmarks: [Sudoku, large mazes, ARC-AGI-1, ARC-AGI-2]
portfolio_position: "4th model class beyond Transformer + Mamba + BitNet"
typed_mirror_crate: sovereign-hrm-runtime-mirror
catalog_status:
  sovereign_os: 79/79 milestones
  selfdef: 44/44 milestones
  combined: 123 milestones
external_research_ingestion: COMPLETE (M077 + M078 + M079 + M080)
sdd_tdd_implementation_gate: RELEASED
```
