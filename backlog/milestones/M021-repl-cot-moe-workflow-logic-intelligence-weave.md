# M021 — REPL / CoT / MoE / workflow / logic / intelligence weave

> Parent: `backlog/milestones/INDEX.md` row M021 (dump 5730–6046).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 5730–6046.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0188–E0197)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0188 | Convergence point — REPL / CoT / MoE / workflow / logic / intelligence share `state → proposal → evaluation → action → observation → updated state` primitive | 5749–5757 |
| E0189 | Common core — 7 named expressions of the same skeleton (REPL / CoT / ReAct / Workflow / MoE / Logic / Intelligence) | 5759–5784 |
| E0190 | Research substrate — ReAct / ToT / GoT / PAL / PoT / MoE / DSPy + "Intelligence is controlled conditional computation over state" | 5786–5799 |
| E0191 | Where they connect — REPL = execution loop / CoT = candidate state / Tree-Graph = topology / Workflow = deterministic shell / MoE = routing | 5801–5859 |
| E0192 | System-level MoE — whole workstation is mixture-of-experts; CPU router decides which expert activates (Blackwell oracle / 3090 scout / AVX-512 logic engine / REPL+tool sandboxes / memory retrieval / human gate / ZFS replay) | 5860–5874 |
| E0193 | The Handhold — 13-instruction semantic ISA + 8-field per-instruction contract | 5876–5911 |
| E0194 | The Architecture — 6-layer weave (REPL / Thought / Workflow / MoE / Logic / Intelligence) + full-loop integration | 5913–5952 |
| E0195 | Why AVX-512 is special — CPU owns hot deterministic state with 8-field branch SoA + 7-question bulk-law operation + 9-field branch control word | 5954–5996 |
| E0196 | The Proper Exploit — CoT as raw material / REPL as reality engine / Whole-station MoE | 5999–6037 |
| E0197 | The One Sentence — "REPL gives reality, CoT gives candidate structure, MoE gives conditional expertise, workflow gives durable order, logic gives law, and intelligence emerges from closing that loop with memory and feedback" | 6038–6044 |

## Modules (M00337–M00353)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00337 | Primitive loop — `state → proposal → evaluation → action → observation → updated state` | 5752–5754 | E0188 |
| M00338 | Common core — REPL (read / evaluate / print / loop) | 5762–5763 | E0189 |
| M00339 | Common core — CoT (problem / intermediate reasoning / answer) | 5765–5766 | E0189 |
| M00340 | Common core — ReAct (thought / action / observation / updated thought) | 5768–5769 | E0189 |
| M00341 | Common core — Workflow (node / transition / node / commit) | 5771–5772 | E0189 |
| M00342 | Common core — MoE (token-state / router / experts / combined output) | 5774–5775 | E0189 |
| M00343 | Common core — Logic (premise-state / rule / consequence) | 5777–5778 | E0189 |
| M00344 | Common core — Intelligence (perceive / model / choose / act / learn) | 5780–5781 | E0189 |
| M00345 | Typed-thought externalization — Plan / Hypothesis / ToolIntent / PatchProposal / VerificationResult / MemoryWrite | 5821–5829 | E0191 |
| M00346 | Topology — chain / tree / graph of thoughts | 5833–5837 | E0191 |
| M00347 | Workflow deterministic shell — node-may-run / output-schema-required / side-effect-forbidden / branch-needs-oracle | 5839–5846 | E0191 |
| M00348 | System-level MoE expert registry — Blackwell oracle / 3090 scout / AVX-512 logic engine / REPL-tool sandboxes / memory retrieval / human gate / ZFS replay | 5862–5874 | E0192 |
| M00349 | Semantic ISA (this milestone) — OBSERVE / RETRIEVE / DRAFT / REASON / EXECUTE_REPL / VERIFY / CRITIQUE / ROUTE / MERGE / COMMIT / ROLLBACK / WRITE_MEMORY / ASK_HUMAN | 5881–5894 | E0193 |
| M00350 | Per-instruction contract — input_schema / output_schema / capability_mask / risk_class / budget / model_route / cache_policy / commit_rule | 5898–5907 | E0193 |
| M00351 | 6-layer architecture — REPL / Thought / Workflow / MoE / Logic / Intelligence | 5915–5935 | E0194 |
| M00352 | Hot deterministic state SoA — `branch_id[]` / `control_word[]` / `budget[]` / `risk[]` / `route[]` / `grammar_state[]` / `memory_ref[]` / `score[]` | 5959–5967 | E0195 |
| M00353 | 64-bit branch word encoding — route / workflow node / expert choice / tool permission / risk / budget / grammar / memory policy / flags | 5985–5995 | E0195 |

## Features (F01701–F01785)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01701 | Primitive loop — `state` slot | 5752 | M00337 | data_model | false |
| F01702 | Primitive loop — `proposal` slot | 5752 | M00337 | data_model | false |
| F01703 | Primitive loop — `evaluation` slot | 5753 | M00337 | data_model | false |
| F01704 | Primitive loop — `action` slot | 5753 | M00337 | data_model | false |
| F01705 | Primitive loop — `observation` slot | 5754 | M00337 | data_model | false |
| F01706 | Primitive loop — `updated state` slot | 5754 | M00337 | data_model | false |
| F01707 | Common-core — REPL substrate (Python / shell / browser / code-tests / simulators per E0194 layer 1) | 5762, 5919–5920 | M00338 | composite | false |
| F01708 | Common-core — CoT substrate (intermediate-reasoning typed-objects) | 5765 | M00339 | composite | false |
| F01709 | Common-core — ReAct substrate (thought-action-observation interleave) | 5768 | M00340 | composite | false |
| F01710 | Common-core — Workflow substrate (durable graph of typed nodes/transitions) | 5771 | M00341 | composite | false |
| F01711 | Common-core — MoE substrate (router + experts conditional computation) | 5774 | M00342 | composite | false |
| F01712 | Common-core — Logic substrate (premise → rule → consequence) | 5777 | M00343 | composite | false |
| F01713 | Common-core — Intelligence substrate (perceive-model-choose-act-learn) | 5780 | M00344 | composite | false |
| F01714 | Typed envelope — Plan | 5823 | M00345 | data_model | false |
| F01715 | Typed envelope — Hypothesis | 5824 | M00345 | data_model | false |
| F01716 | Typed envelope — ToolIntent | 5825 | M00345 | data_model | false |
| F01717 | Typed envelope — PatchProposal | 5826 | M00345 | data_model | false |
| F01718 | Typed envelope — VerificationResult | 5827 | M00345 | data_model | false |
| F01719 | Typed envelope — MemoryWrite | 5828 | M00345 | data_model | false |
| F01720 | Topology — chain (one path) | 5834 | M00346 | mode | true |
| F01721 | Topology — tree (many paths) | 5835 | M00346 | mode | true |
| F01722 | Topology — graph (paths can merge/reuse) | 5836 | M00346 | mode | true |
| F01723 | Profile knob — `thought_topology = chain \| tree \| graph` | 5833–5837 | M00346 | profile | true |
| F01724 | Env var `SOVEREIGN_THOUGHT_TOPOLOGY` | 5833–5837 | M00346 | env_var | true |
| F01725 | CLI `--thought-topology <mode>` | 5833–5837 | M00346 | cli_verb | true |
| F01726 | Workflow constraint — node-may-run gate | 5842 | M00347 | composite | false |
| F01727 | Workflow constraint — output-schema-required gate | 5843 | M00347 | composite | false |
| F01728 | Workflow constraint — side-effect-forbidden gate | 5844 | M00347 | composite | false |
| F01729 | Workflow constraint — branch-needs-oracle gate | 5845 | M00347 | composite | false |
| F01730 | MoE distinction — token-level MoE (model routes tokens to experts) | 5853–5854 | M00342 | composite | false |
| F01731 | MoE distinction — system-level MoE (runtime routes tasks to models/tools/workflows) | 5856–5857 | M00342 | composite | false |
| F01732 | System-level MoE expert — Blackwell oracle | 5865 | M00348 | composite | false |
| F01733 | System-level MoE expert — 3090 scout | 5866 | M00348 | composite | false |
| F01734 | System-level MoE expert — AVX-512 logic engine | 5867 | M00348 | composite | false |
| F01735 | System-level MoE expert — REPL/tool sandboxes | 5868 | M00348 | composite | false |
| F01736 | System-level MoE expert — memory retrieval | 5869 | M00348 | composite | false |
| F01737 | System-level MoE expert — human gate | 5870 | M00348 | composite | false |
| F01738 | System-level MoE expert — ZFS replay | 5871 | M00348 | composite | false |
| F01739 | CPU router — decides which expert activates per task | 5874 | M00348 | composite | false |
| F01740 | Semantic ISA — OBSERVE | 5882 | M00349 | composite | false |
| F01741 | Semantic ISA — RETRIEVE | 5883 | M00349 | composite | false |
| F01742 | Semantic ISA — DRAFT | 5884 | M00349 | composite | false |
| F01743 | Semantic ISA — REASON | 5885 | M00349 | composite | false |
| F01744 | Semantic ISA — EXECUTE_REPL | 5886 | M00349 | composite | false |
| F01745 | Semantic ISA — VERIFY | 5887 | M00349 | composite | false |
| F01746 | Semantic ISA — CRITIQUE | 5888 | M00349 | composite | false |
| F01747 | Semantic ISA — ROUTE | 5889 | M00349 | composite | false |
| F01748 | Semantic ISA — MERGE | 5890 | M00349 | composite | false |
| F01749 | Semantic ISA — COMMIT | 5891 | M00349 | composite | false |
| F01750 | Semantic ISA — ROLLBACK | 5892 | M00349 | composite | false |
| F01751 | Semantic ISA — WRITE_MEMORY | 5893 | M00349 | composite | false |
| F01752 | Semantic ISA — ASK_HUMAN | 5894 | M00349 | composite | false |
| F01753 | Per-instruction field — `input_schema` | 5899 | M00350 | data_model | false |
| F01754 | Per-instruction field — `output_schema` | 5900 | M00350 | data_model | false |
| F01755 | Per-instruction field — `capability_mask` | 5901 | M00350 | data_model | false |
| F01756 | Per-instruction field — `risk_class` | 5902 | M00350 | data_model | false |
| F01757 | Per-instruction field — `budget` | 5903 | M00350 | data_model | false |
| F01758 | Per-instruction field — `model_route` | 5904 | M00350 | data_model | false |
| F01759 | Per-instruction field — `cache_policy` | 5905 | M00350 | data_model | false |
| F01760 | Per-instruction field — `commit_rule` | 5906 | M00350 | data_model | false |
| F01761 | 6-layer architecture — Layer 1 REPL Layer (Python / shell / browser / code-tests / simulators) | 5916–5920 | M00351 | composite | false |
| F01762 | 6-layer architecture — Layer 2 Thought Layer (candidate plans / hypotheses / branches / critiques) | 5922–5924 | M00351 | composite | false |
| F01763 | 6-layer architecture — Layer 3 Workflow Layer (durable graph of typed nodes + transitions) | 5926–5928 | M00351 | composite | false |
| F01764 | 6-layer architecture — Layer 4 MoE Layer (model+tool+hardware router; Blackwell / 3090 / CPU / sandbox / memory / human) | 5930–5932 | M00351 | composite | false |
| F01765 | 6-layer architecture — Layer 5 Logic Layer (AVX-512 masks / permissions / grammar / budgets / automata) | 5934–5936 | M00351 | composite | false |
| F01766 | 6-layer architecture — Layer 6 Intelligence Layer (search + memory + tools + verification + feedback) | 5938–5940 | M00351 | composite | false |
| F01767 | Hot SoA field — `branch_id[]` | 5959 | M00352 | data_model | false |
| F01768 | Hot SoA field — `control_word[]` | 5960 | M00352 | data_model | false |
| F01769 | Hot SoA field — `budget[]` | 5961 | M00352 | data_model | false |
| F01770 | Hot SoA field — `risk[]` | 5962 | M00352 | data_model | false |
| F01771 | Hot SoA field — `route[]` | 5963 | M00352 | data_model | false |
| F01772 | Hot SoA field — `grammar_state[]` | 5964 | M00352 | data_model | false |
| F01773 | Hot SoA field — `memory_ref[]` | 5965 | M00352 | data_model | false |
| F01774 | Hot SoA field — `score[]` | 5966 | M00352 | data_model | false |
| F01775 | AVX-512 bulk-law question — which branches are alive? | 5971 | M00352 | composite | false |
| F01776 | AVX-512 bulk-law question — which need oracle? | 5972 | M00352 | composite | false |
| F01777 | AVX-512 bulk-law question — which can use tools? | 5973 | M00352 | composite | false |
| F01778 | AVX-512 bulk-law question — which violate grammar? | 5974 | M00352 | composite | false |
| F01779 | AVX-512 bulk-law question — which share memory? | 5975 | M00352 | composite | false |
| F01780 | AVX-512 bulk-law question — which should merge? | 5976 | M00352 | composite | false |
| F01781 | AVX-512 bulk-law question — which should execute REPL? | 5977 | M00352 | composite | false |
| F01782 | 64-bit branch word — 9-field encoding (route / workflow node / expert choice / tool permission / risk / budget / grammar / memory policy / flags) | 5985–5995 | M00353 | composite | false |
| F01783 | API `POST /v1/isa/execute` (executes one ISA instruction; honors capability_mask + commit_rule; emits trace) | 5895–5911 | M00349 | api_endpoint | true |
| F01784 | Dashboard — 6-layer weave overview (REPL active / Thought topology / Workflow nodes live / MoE router decisions / Logic mask hits / Intelligence loop telemetry) | 5915–5935 | M00351 | dashboard | true |
| F01785 | Composite — "REPL gives reality, CoT gives candidate structure, MoE gives conditional expertise, workflow gives durable order, logic gives law, and intelligence emerges from closing that loop with memory and feedback" | 6038–6044 | E0197 | composite | false |

## Requirements (R03401–R03570)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R03401 | REPL / CoT / MoE / workflow / logic / intelligence share `state → proposal → evaluation → action → observation → updated state` primitive | 5752–5757 | E0188 | non-negotiable | false | 10 |
| R03402 | The loop is the primitive | 5757 | E0188 | non-negotiable | false | 10 |
| R03403 | Same skeleton, different substrate (REPL / CoT / ReAct / Workflow / MoE / Logic / Intelligence) | 5784 | E0189 | non-negotiable | false | 10 |
| R03404 | Common-core — REPL: read → evaluate → print → loop | 5762–5763 | M00338 | non-negotiable | false | 10 |
| R03405 | Common-core — CoT: problem → intermediate reasoning → answer | 5765–5766 | M00339 | non-negotiable | false | 10 |
| R03406 | Common-core — ReAct: thought → action → observation → updated thought | 5768–5769 | M00340 | non-negotiable | false | 10 |
| R03407 | Common-core — Workflow: node → transition → node → commit | 5771–5772 | M00341 | non-negotiable | false | 10 |
| R03408 | Common-core — MoE: token/state → router → expert(s) → combined output | 5774–5775 | M00342 | non-negotiable | false | 10 |
| R03409 | Common-core — Logic: premise/state → rule → consequence | 5777–5778 | M00343 | non-negotiable | false | 10 |
| R03410 | Common-core — Intelligence: perceive → model → choose → act → learn | 5780–5781 | M00344 | non-negotiable | false | 10 |
| R03411 | ReAct interleaves reasoning and action; actions gather observations that update future reasoning | 5788 | E0190 | non-negotiable | false | 10 |
| R03412 | Tree of Thoughts generalizes CoT into search over multiple reasoning paths with lookahead/backtracking | 5789 | E0190 | non-negotiable | false | 10 |
| R03413 | Graph of Thoughts allows thoughts to branch, merge, refine, aggregate | 5790 | E0190 | non-negotiable | false | 10 |
| R03414 | Program-Aided Language Models and Program of Thoughts offload computation to executable runtimes | 5791 | E0190 | non-negotiable | false | 10 |
| R03415 | MoE uses routers to activate only selected experts per token (conditional computation) | 5792 | E0190 | non-negotiable | false | 10 |
| R03416 | DSPy treats LM systems as programs that can be optimized | 5793 | E0190 | non-negotiable | false | 10 |
| R03417 | Weaving point — Intelligence is controlled conditional computation over state | 5797–5799 | E0190 | non-negotiable | false | 10 |
| R03418 | REPL is the simplest execution loop (input / evaluate / observe result / continue) | 5803–5811 | M00338 | non-negotiable | false | 10 |
| R03419 | REPL becomes the agent runtime | 5812 | M00338 | non-negotiable | false | 10 |
| R03420 | CoT is internal candidate state | 5814 | M00339 | non-negotiable | false | 10 |
| R03421 | Raw CoT as prose is weak | 5820 | M00339 | non-negotiable | false | 10 |
| R03422 | Stronger move — externalize CoT into typed objects | 5820 | M00345 | non-negotiable | false | 10 |
| R03423 | Typed object — Plan | 5823 | M00345 | non-negotiable | false | 10 |
| R03424 | Typed object — Hypothesis | 5824 | M00345 | non-negotiable | false | 10 |
| R03425 | Typed object — ToolIntent | 5825 | M00345 | non-negotiable | false | 10 |
| R03426 | Typed object — PatchProposal | 5826 | M00345 | non-negotiable | false | 10 |
| R03427 | Typed object — VerificationResult | 5827 | M00345 | non-negotiable | false | 10 |
| R03428 | Typed object — MemoryWrite | 5828 | M00345 | non-negotiable | false | 10 |
| R03429 | Tree/Graph of Thoughts are topology | 5831 | M00346 | non-negotiable | false | 10 |
| R03430 | Topology — chain (one path) | 5834 | M00346 | non-negotiable | true | 10 |
| R03431 | Topology — tree (many paths) | 5835 | M00346 | non-negotiable | true | 10 |
| R03432 | Topology — graph (paths can merge/reuse) | 5836 | M00346 | non-negotiable | true | 10 |
| R03433 | Workflow is the deterministic shell around that topology | 5839 | M00347 | non-negotiable | false | 10 |
| R03434 | Workflow constraint — `this node may run` | 5842 | M00347 | non-negotiable | false | 10 |
| R03435 | Workflow constraint — `this output schema is required` | 5843 | M00347 | non-negotiable | false | 10 |
| R03436 | Workflow constraint — `this side effect is forbidden` | 5844 | M00347 | non-negotiable | false | 10 |
| R03437 | Workflow constraint — `this branch needs oracle` | 5845 | M00347 | non-negotiable | false | 10 |
| R03438 | MoE is routing inside the model | 5848 | M00342 | non-negotiable | false | 10 |
| R03439 | Runtime can mirror MoE outside the model | 5850 | M00342 | non-negotiable | false | 10 |
| R03440 | Token-level MoE — model routes tokens to experts | 5853–5854 | M00342 | non-negotiable | false | 10 |
| R03441 | System-level MoE — runtime routes tasks to models/tools/workflows | 5856–5857 | M00342 | non-negotiable | false | 10 |
| R03442 | Whole workstation becomes a mixture-of-experts system | 5862 | E0192 | non-negotiable | false | 10 |
| R03443 | System-level MoE expert — Blackwell oracle | 5865 | M00348 | non-negotiable | false | 10 |
| R03444 | System-level MoE expert — 3090 scout | 5866 | M00348 | non-negotiable | false | 10 |
| R03445 | System-level MoE expert — AVX-512 logic engine | 5867 | M00348 | non-negotiable | false | 10 |
| R03446 | System-level MoE expert — REPL/tool sandboxes | 5868 | M00348 | non-negotiable | false | 10 |
| R03447 | System-level MoE expert — memory retrieval | 5869 | M00348 | non-negotiable | false | 10 |
| R03448 | System-level MoE expert — human gate | 5870 | M00348 | non-negotiable | false | 10 |
| R03449 | System-level MoE expert — ZFS replay | 5871 | M00348 | non-negotiable | false | 10 |
| R03450 | The CPU router decides which expert activates | 5874 | M00348 | non-negotiable | false | 10 |
| R03451 | To have your hands on it properly, define a small semantic instruction set | 5878 | E0193 | non-negotiable | false | 10 |
| R03452 | Semantic ISA instruction — OBSERVE | 5882 | M00349 | non-negotiable | false | 10 |
| R03453 | Semantic ISA instruction — RETRIEVE | 5883 | M00349 | non-negotiable | false | 10 |
| R03454 | Semantic ISA instruction — DRAFT | 5884 | M00349 | non-negotiable | false | 10 |
| R03455 | Semantic ISA instruction — REASON | 5885 | M00349 | non-negotiable | false | 10 |
| R03456 | Semantic ISA instruction — EXECUTE_REPL | 5886 | M00349 | non-negotiable | false | 10 |
| R03457 | Semantic ISA instruction — VERIFY | 5887 | M00349 | non-negotiable | false | 10 |
| R03458 | Semantic ISA instruction — CRITIQUE | 5888 | M00349 | non-negotiable | false | 10 |
| R03459 | Semantic ISA instruction — ROUTE | 5889 | M00349 | non-negotiable | false | 10 |
| R03460 | Semantic ISA instruction — MERGE | 5890 | M00349 | non-negotiable | false | 10 |
| R03461 | Semantic ISA instruction — COMMIT | 5891 | M00349 | non-negotiable | false | 10 |
| R03462 | Semantic ISA instruction — ROLLBACK | 5892 | M00349 | non-negotiable | false | 10 |
| R03463 | Semantic ISA instruction — WRITE_MEMORY | 5893 | M00349 | non-negotiable | false | 10 |
| R03464 | Semantic ISA instruction — ASK_HUMAN | 5894 | M00349 | non-negotiable | false | 10 |
| R03465 | Per-instruction contract — input_schema | 5899 | M00350 | non-negotiable | false | 10 |
| R03466 | Per-instruction contract — output_schema | 5900 | M00350 | non-negotiable | false | 10 |
| R03467 | Per-instruction contract — capability_mask | 5901 | M00350 | non-negotiable | false | 10 |
| R03468 | Per-instruction contract — risk_class | 5902 | M00350 | non-negotiable | false | 10 |
| R03469 | Per-instruction contract — budget | 5903 | M00350 | non-negotiable | false | 10 |
| R03470 | Per-instruction contract — model_route | 5904 | M00350 | non-negotiable | false | 10 |
| R03471 | Per-instruction contract — cache_policy | 5905 | M00350 | non-negotiable | false | 10 |
| R03472 | Per-instruction contract — commit_rule | 5906 | M00350 | non-negotiable | false | 10 |
| R03473 | Model is not "free talking" — proposes instructions | 5909 | E0193 | non-negotiable | false | 10 |
| R03474 | Deterministic runtime accepts, rejects, routes, or commits | 5911 | E0193 | non-negotiable | false | 10 |
| R03475 | Layer 1 — REPL Layer (Python / shell / browser / code tests / simulators) | 5916–5920 | M00351 | non-negotiable | false | 10 |
| R03476 | Layer 2 — Thought Layer (candidate plans / hypotheses / branches / critiques) | 5922–5924 | M00351 | non-negotiable | false | 10 |
| R03477 | Layer 3 — Workflow Layer (durable graph of typed nodes and transitions) | 5926–5928 | M00351 | non-negotiable | false | 10 |
| R03478 | Layer 4 — MoE Layer (model/tool/hardware router — Blackwell / 3090 / CPU / sandbox / memory / human) | 5930–5932 | M00351 | non-negotiable | false | 10 |
| R03479 | Layer 5 — Logic Layer (AVX-512 masks / permissions / grammar / budgets / automata) | 5934–5936 | M00351 | non-negotiable | false | 10 |
| R03480 | Layer 6 — Intelligence Layer (search + memory + tools + verification + feedback) | 5938–5940 | M00351 | non-negotiable | false | 10 |
| R03481 | Weave step 1 — Model proposes thought | 5942 | E0194 | non-negotiable | false | 10 |
| R03482 | Weave step 2 — Workflow turns thought into typed node | 5943 | E0194 | non-negotiable | false | 10 |
| R03483 | Weave step 3 — Logic checks legality | 5944 | E0194 | non-negotiable | false | 10 |
| R03484 | Weave step 4 — Router selects expert | 5945 | E0194 | non-negotiable | false | 10 |
| R03485 | Weave step 5 — REPL/tool executes if needed | 5946 | E0194 | non-negotiable | false | 10 |
| R03486 | Weave step 6 — Observation returns | 5947 | E0194 | non-negotiable | false | 10 |
| R03487 | Weave step 7 — Memory records | 5948 | E0194 | non-negotiable | false | 10 |
| R03488 | Weave step 8 — Graph updates | 5949 | E0194 | non-negotiable | false | 10 |
| R03489 | Weave step 9 — Oracle verifies | 5950 | E0194 | non-negotiable | false | 10 |
| R03490 | Weave step 10 — Runtime commits | 5951 | E0194 | non-negotiable | false | 10 |
| R03491 | That is the full loop | 5952 | E0194 | non-negotiable | false | 10 |
| R03492 | CPU owns the hot deterministic state | 5956 | M00352 | non-negotiable | false | 10 |
| R03493 | Hot state field — `branch_id[]` | 5959 | M00352 | non-negotiable | false | 10 |
| R03494 | Hot state field — `control_word[]` | 5960 | M00352 | non-negotiable | false | 10 |
| R03495 | Hot state field — `budget[]` | 5961 | M00352 | non-negotiable | false | 10 |
| R03496 | Hot state field — `risk[]` | 5962 | M00352 | non-negotiable | false | 10 |
| R03497 | Hot state field — `route[]` | 5963 | M00352 | non-negotiable | false | 10 |
| R03498 | Hot state field — `grammar_state[]` | 5964 | M00352 | non-negotiable | false | 10 |
| R03499 | Hot state field — `memory_ref[]` | 5965 | M00352 | non-negotiable | false | 10 |
| R03500 | Hot state field — `score[]` | 5966 | M00352 | non-negotiable | false | 10 |
| R03501 | AVX-512 bulk law — "which branches are alive?" | 5971 | M00352 | non-negotiable | false | 10 |
| R03502 | AVX-512 bulk law — "which need oracle?" | 5972 | M00352 | non-negotiable | false | 10 |
| R03503 | AVX-512 bulk law — "which can use tools?" | 5973 | M00352 | non-negotiable | false | 10 |
| R03504 | AVX-512 bulk law — "which violate grammar?" | 5974 | M00352 | non-negotiable | false | 10 |
| R03505 | AVX-512 bulk law — "which share memory?" | 5975 | M00352 | non-negotiable | false | 10 |
| R03506 | AVX-512 bulk law — "which should merge?" | 5976 | M00352 | non-negotiable | false | 10 |
| R03507 | AVX-512 bulk law — "which should execute REPL?" | 5977 | M00352 | non-negotiable | false | 10 |
| R03508 | The bits become the control surface of intelligence | 5981 | M00352 | non-negotiable | false | 10 |
| R03509 | 64-bit branch word encodes — route | 5986 | M00353 | non-negotiable | false | 10 |
| R03510 | 64-bit branch word encodes — workflow node | 5987 | M00353 | non-negotiable | false | 10 |
| R03511 | 64-bit branch word encodes — expert choice | 5988 | M00353 | non-negotiable | false | 10 |
| R03512 | 64-bit branch word encodes — tool permission | 5989 | M00353 | non-negotiable | false | 10 |
| R03513 | 64-bit branch word encodes — risk | 5990 | M00353 | non-negotiable | false | 10 |
| R03514 | 64-bit branch word encodes — budget | 5991 | M00353 | non-negotiable | false | 10 |
| R03515 | 64-bit branch word encodes — grammar | 5992 | M00353 | non-negotiable | false | 10 |
| R03516 | 64-bit branch word encodes — memory policy | 5993 | M00353 | non-negotiable | false | 10 |
| R03517 | 64-bit branch word encodes — flags | 5994 | M00353 | non-negotiable | false | 10 |
| R03518 | Intelligence is no longer just "inside the model" — it is in the system's ability to route, constrain, execute, observe, and learn | 5997 | E0195 | non-negotiable | false | 10 |
| R03519 | Do not use CoT as sacred text — use as raw material | 6001–6003 | E0196 | non-negotiable | false | 10 |
| R03520 | CoT → typed plan | 6006 | E0196 | non-negotiable | false | 10 |
| R03521 | typed plan → workflow graph | 6007 | E0196 | non-negotiable | false | 10 |
| R03522 | workflow graph → deterministic policy | 6008 | E0196 | non-negotiable | false | 10 |
| R03523 | policy → routed experts | 6009 | E0196 | non-negotiable | false | 10 |
| R03524 | experts → observations | 6010 | E0196 | non-negotiable | false | 10 |
| R03525 | observations → replay/memory | 6011 | E0196 | non-negotiable | false | 10 |
| R03526 | memory → better future routing | 6012 | E0196 | non-negotiable | false | 10 |
| R03527 | Do not use REPL as a side toy — use as the reality engine | 6015–6017 | E0196 | non-negotiable | false | 10 |
| R03528 | When calculation matters — execute | 6020 | E0196 | non-negotiable | false | 10 |
| R03529 | When code matters — test | 6021 | E0196 | non-negotiable | false | 10 |
| R03530 | When files matter — inspect | 6022 | E0196 | non-negotiable | false | 10 |
| R03531 | When claims matter — verify | 6023 | E0196 | non-negotiable | false | 10 |
| R03532 | Do not use MoE only because models are MoE — make the whole station MoE | 6026–6028 | E0196 | non-negotiable | false | 10 |
| R03533 | Different experts, different costs, different risks, different modalities, one deterministic router | 6031–6035 | E0196 | non-negotiable | false | 10 |
| R03534 | The one sentence — REPL gives reality | 6040 | E0197 | non-negotiable | false | 10 |
| R03535 | The one sentence — CoT gives candidate structure | 6040 | E0197 | non-negotiable | false | 10 |
| R03536 | The one sentence — MoE gives conditional expertise | 6040 | E0197 | non-negotiable | false | 10 |
| R03537 | The one sentence — workflow gives durable order | 6041 | E0197 | non-negotiable | false | 10 |
| R03538 | The one sentence — logic gives law | 6041 | E0197 | non-negotiable | false | 10 |
| R03539 | The one sentence — intelligence emerges from closing the loop with memory and feedback | 6041 | E0197 | non-negotiable | false | 10 |
| R03540 | That is the architecture we can actually build around the hardware | 6044 | E0197 | non-negotiable | false | 10 |
| R03541 | Thought topology operator-overrideable (chain / tree / graph) | 5833–5837 | F01723 | non-negotiable | true | 10 |
| R03542 | Env var `SOVEREIGN_THOUGHT_TOPOLOGY` | 5833–5837 | F01724 | non-negotiable | true | 10 |
| R03543 | CLI `--thought-topology <mode>` | 5833–5837 | F01725 | non-negotiable | true | 10 |
| R03544 | API `POST /v1/isa/execute` executes one ISA instruction honoring capability_mask + commit_rule + emits trace | 5895–5911 | F01783 | non-negotiable | true | 10 |
| R03545 | Dashboard — 6-layer weave overview live | 5915–5935 | F01784 | non-negotiable | true | 10 |
| R03546 | Test — primitive 6-slot loop round-trips through one full cycle on synthetic input | 5752–5754 | M00337 | non-negotiable | false | 10 |
| R03547 | Test — each of 7 common-core expressions runs end-to-end on sample task | 5762–5781 | E0189 | non-negotiable | false | 10 |
| R03548 | Test — each of 6 typed-thought envelopes round-trips via API | 5821–5829 | M00345 | non-negotiable | false | 10 |
| R03549 | Test — each of 3 thought topologies (chain / tree / graph) supported by runtime | 5833–5837 | M00346 | non-negotiable | false | 10 |
| R03550 | Test — Workflow gate `node-may-run` enforced | 5842 | M00347 | non-negotiable | false | 10 |
| R03551 | Test — Workflow gate `output-schema-required` enforced | 5843 | M00347 | non-negotiable | false | 10 |
| R03552 | Test — Workflow gate `side-effect-forbidden` enforced | 5844 | M00347 | non-negotiable | false | 10 |
| R03553 | Test — Workflow gate `branch-needs-oracle` enforced | 5845 | M00347 | non-negotiable | false | 10 |
| R03554 | Test — System-level MoE router activates correct expert for each of 7 named experts | 5862–5874 | M00348 | non-negotiable | false | 10 |
| R03555 | Test — 13-instruction Semantic ISA round-trips via encode/decode | 5881–5894 | M00349 | non-negotiable | false | 10 |
| R03556 | Test — Per-instruction 8-field contract present for every shipped instruction | 5898–5907 | M00350 | non-negotiable | false | 10 |
| R03557 | Test — Runtime accepts / rejects / routes / commits ISA instructions per declared rules | 5911 | E0193 | non-negotiable | false | 10 |
| R03558 | Test — 10-step weave loop runs end-to-end for sample input (Model-propose → Runtime-commit) | 5942–5951 | E0194 | non-negotiable | false | 10 |
| R03559 | Test — hot SoA 8-field round-trip preserves all fields | 5959–5967 | M00352 | non-negotiable | false | 10 |
| R03560 | Test — AVX-512 7-question bulk-law matches scalar reference on synthetic branch corpus | 5970–5978 | M00352 | non-negotiable | false | 10 |
| R03561 | Test — 64-bit branch word 9-field encoding round-trips via encode/decode | 5985–5995 | M00353 | non-negotiable | false | 10 |
| R03562 | Test — CoT-as-raw-material pipeline (CoT → typed plan → workflow → policy → experts → observations → memory) end-to-end on sample task | 6005–6012 | E0196 | non-negotiable | false | 10 |
| R03563 | Test — REPL-as-reality-engine — verify-on-claim integration test | 6019–6023 | E0196 | non-negotiable | false | 10 |
| R03564 | Composite — Layer 1 REPL Layer integrates with M015 programming plane (Tool Node implementations live here) | 5916–5920 | M00351 | non-negotiable | false | 10 |
| R03565 | Composite — Layer 2 Thought Layer integrates with M019 cognitive operators (12 operators populate the thought layer's candidate stream) | 5922–5924 | M00351 | non-negotiable | false | 10 |
| R03566 | Composite — Layer 3 Workflow Layer integrates with M020 semantic ISA (workflow nodes ARE typed instructions) | 5926–5928 | M00351 | non-negotiable | false | 10 |
| R03567 | Composite — Layer 4 MoE Layer integrates with M017 model registry + M018 serving fabric (per-role models are the MoE's experts) | 5930–5932 | M00351 | non-negotiable | false | 10 |
| R03568 | Composite — Layer 5 Logic Layer integrates with M006 deterministic AI control substrate + M008 AVX-512 features (bit-level law primitives) | 5934–5936 | M00351 | non-negotiable | false | 10 |
| R03569 | Composite — Layer 6 Intelligence Layer integrates with M016 learning plane (memory + feedback close the loop) | 5938–5940 | M00351 | non-negotiable | false | 10 |
| R03570 | Composite — The one sentence "REPL gives reality, CoT gives candidate structure, MoE gives conditional expertise, workflow gives durable order, logic gives law, and intelligence emerges from closing that loop with memory and feedback" is the architecture's north star | 6038–6044 | E0197 | non-negotiable | false | 10 |

— End of M021 milestone file.
