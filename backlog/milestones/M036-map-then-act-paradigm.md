# M036 — MAP — map-then-act paradigm

> Parent: `backlog/milestones/INDEX.md` row M036 (dump 10378–10712).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 10378–10712 (operator-presented 7-link substrate + 9-bucket synthesis + 10-step methodology).
> All entries below are extracted from the dump line range. No invention.

## Epics (E0338–E0347)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0338 | Operator-presented 8-link reading list — Fast Byte Latent Transformer (Meta+Stanford) / agent evals (Cameron Wolfe) / 21 domain-tuned LLMs (InfoWorld) / MAP arXiv 2605.13037 / LLM compression FP8+GPTQ+SmoothQuant (llmcompressor + vLLM docs) / NadirClaw cost-aware routing / OpenAI Symphony / LiteLLM Agent Platform; "I want to think about whether and how these inform Spec Driven + TDD + multiprofile + adaptive Goldilocks AIDLC/SDLC + super-model + models + high standards" | 10378–10389 |
| E0339 | MAP (Map-then-Act paradigm) — strongest link; agents fail when they only understand environment reactively while executing; MAP does Global exploration → task-specific map → knowledge-augmented execution; "plugs directly into your vision"; 4 pre-act maps (repo+tests+deps+risks+ownership+architecture before coding / environment+available-actions+failure-states before GUI/tool action / task-graph+blockers+verification-points before workflow / rollback+permissions+expected-transitions before autonomy); formal SDLC = SPEC → MAP → PLAN → ACT → TEST → EVAL → COMMIT → LEARN | 10419–10455 |
| E0340 | Symphony (OpenAI) — directly relevant to Spec-Driven Development; treats project-management issues as the control plane; explicit SPEC.md / per-issue isolated workspaces / WORKFLOW.md / bounded concurrency / retries / observability / human review; maps to "Spec Driven + TDD + multiprofile"; subtle lesson "Spec is not a cage. Spec is the contract"; agent still needs objectives + tools + judgment + room to discover new work; Symphony's own lesson — rigid state-machine boxes become too small; use specs as "governed freedom" (SPEC.md=product/architecture intent / WORKFLOW.md=local agent policy / TESTS=executable truth / EVALS=quality envelope / PROFILES=adaptive behavior modes) | 10457–10478 |
| E0341 | Agent evals (Cameron Wolfe) — MANDATORY; not just final text checks; need tasks / trials / traces-trajectories / tool calls / environmental outcomes / graders; every workflow produces (trace / trajectory / tool calls / environment before+after / test results / cost / latency / model route / human interventions / pass-fail reason) — "spine of adaptive intelligence"; without evals, Goldilocks becomes vibes; with evals, Goldilocks = "not too cheap / not too slow / not too risky / not too overpowered / just enough intelligence for this task" | 10480–10509 |
| E0342 | LiteLLM Agent Platform — relevant for sandbox/session architecture (Kubernetes sandboxes / persistent sessions / harnesses for agents / vault-secrets patterns / separate gateway routing+cost+rate-limits) but NOT the kernel; useful pattern (per-session sandbox / harness abstraction / persistent session state / model gateway separation / cost tracking); caution (OpenAI-format bias / Kubernetes complexity / may be too heavy for workstation-first architecture); "use it as inspiration or optional module. Your Anthropic-first gateway and deterministic runtime should remain the kernel" | 10511–10533 |
| E0343 | NadirClaw — good router prototype; minimal local-classification-before-model-dispatch (local embeddings/centroids / confidence thresholds / proxying / cost reporting); for your system becomes (local classifier + task-difficulty estimator + privacy classifier + risk classifier + modality classifier + cost-latency policy + model registry = adaptive router); "NadirClaw is not the final router. It is the baby version of your router." | 10535–10552 |
| E0344 | LLM Compressor — very relevant for the model lab; workstation needs model qualification pipeline (NOT random downloaded models); benchmark BF16/FP16 baseline / FP8 / GPTQ W4A16 / SmoothQuant W8A8 / KV-cache quantization / NVFP4-MXFP4 when Blackwell stack ready; score by profile (coding quality / tool-call reliability / JSON-schema validity / latency / VRAM / tokens-per-sec / energy / eval pass rate) — "how you build a serious local model portfolio" | 10554–10584 |
| E0345 | Fast BLT (Byte Latent Transformer) — frontier-relevant, not immediate infrastructure; reduces inference memory-bandwidth pressure in byte-level models with diffusion/speculation-style decoding; estimated memory-bandwidth cost reductions over 50%; conceptually matters because architecture is memory-bandwidth aware (avoid wasted decoding / batch verification / speculate cheaply / verify deterministically / reduce tokenizer fragility); "not anchor the station on BLT today unless there is mature serving support. Put it in the watch and prototype bucket" | 10586–10600 |
| E0346 | Domain LLMs — strategically relevant for model registry; specialization across medical / legal / finance / security / climate / code / reasoning; supports super-model idea — "Super-model != one giant model. Super-model = routed ecology of specialists"; registry should know (model role / domain / precision / hardware fit / tool-use score / eval score / privacy class / cost / latency / failure modes) | 10602–10626 |
| E0347 | Combined Architecture (9-layer stack) + Methodology (10-step adaptive Goldilocks AIDLC/SDLC) — SPEC Layer / MAP Layer / Compiler Layer / Execution Layer / Model Layer / Router Layer / Test+Eval Layer / Memory Layer / Commit Layer; 10-step (Specify / Map / Decompose / Route / Implement / Test / Evaluate / Review / Commit / Learn); 8-source synthesis closing (MAP=situational intelligence / Symphony=orchestration / agent-evals=measurement / LiteLLM=sandbox-session patterns / NadirClaw=router seed / LLM Compressor=model lab discipline / Domain LLMs=specialist ecology / Fast BLT=frontier decoding direction); priority — "strongest immediate pillars are MAP, Symphony, agent evals, model compression lab, and routing. Fast BLT is frontier-watch. LiteLLM is useful inspiration. Domain LLMs support model-registry/super-model" | 10628–10712 |

## Modules (M00595–M00611)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00595 | MAP — Global exploration step | 10426 | E0339 |
| M00596 | MAP — task-specific map step | 10427 | E0339 |
| M00597 | MAP — knowledge-augmented execution step | 10428 | E0339 |
| M00598 | SDLC formal sequence — SPEC → MAP → PLAN → ACT → TEST → EVAL → COMMIT → LEARN | 10452 | E0339 |
| M00599 | Symphony spec governance — SPEC.md (product/architecture intent) | 10473 | E0340 |
| M00600 | Symphony spec governance — WORKFLOW.md (local agent policy) | 10474 | E0340 |
| M00601 | Symphony spec governance — TESTS (executable truth) | 10475 | E0340 |
| M00602 | Symphony spec governance — EVALS (quality envelope) | 10476 | E0340 |
| M00603 | Symphony spec governance — PROFILES (adaptive behavior modes) | 10477 | E0340 |
| M00604 | Agent eval signal catalog — trace / trajectory / tool calls / env-before+after / test results / cost / latency / model route / human interventions / pass-fail reason | 10487–10497 | E0341 |
| M00605 | Goldilocks-with-evals — not too cheap / slow / risky / overpowered; just enough intelligence for task | 10504–10508 | E0341 |
| M00606 | Adaptive Router builder — local classifier + task-difficulty estimator + privacy classifier + risk classifier + modality classifier + cost-latency policy + model registry | 10542–10550 | E0343 |
| M00607 | Model Lab benchmark catalog — BF16/FP16 baseline / FP8 / GPTQ W4A16 / SmoothQuant W8A8 / KV-cache quantization / NVFP4-MXFP4 (Blackwell-ready) | 10562–10568 | E0344 |
| M00608 | Model Lab score-by-profile catalog — coding quality / tool-call reliability / JSON-schema validity / latency / VRAM / tokens-per-sec / energy / eval pass rate | 10574–10582 | E0344 |
| M00609 | Model Registry schema — role / domain / precision / hardware fit / tool-use score / eval score / privacy class / cost / latency / failure modes | 10615–10625 | E0346 |
| M00610 | 9-layer Combined Architecture — SPEC / MAP / Compiler / Execution / Model / Router / Test+Eval / Memory / Commit | 10633–10659 | E0347 |
| M00611 | 10-step adaptive Goldilocks AIDLC/SDLC methodology — Specify / Map / Decompose / Route / Implement / Test / Evaluate / Review / Commit / Learn | 10666–10695 | E0347 |

## Features (F02976–F03060)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F02976 | Operator reading list — Fast BLT (Meta+Stanford) | 10379 | E0338 | composite | true |
| F02977 | Operator reading list — agent evals (Cameron Wolfe) | 10380 | E0338 | composite | true |
| F02978 | Operator reading list — 21 domain-tuned LLMs (InfoWorld) | 10381 | E0338 | composite | true |
| F02979 | Operator reading list — MAP arXiv 2605.13037 | 10382 | E0338 | composite | true |
| F02980 | Operator reading list — LLM compression FP8+GPTQ+SmoothQuant (llmcompressor) | 10383 | E0338 | composite | true |
| F02981 | Operator reading list — NadirClaw cost-aware routing | 10384 | E0338 | composite | true |
| F02982 | Operator reading list — OpenAI Symphony | 10385 | E0338 | composite | true |
| F02983 | Operator reading list — LiteLLM Agent Platform (Kubernetes-based) | 10386 | E0338 | composite | true |
| F02984 | Operator request — "not that I want to lock my in my Spec idea" + connect to Spec Driven + TDD + multiprofile + adaptive Goldilocks + AIDLC/SDLC + super-model + high standards | 10388 | E0338 | composite | false |
| F02985 | Operator request — "we can do this in multiple iterations" | 10389 | E0338 | composite | false |
| F02986 | Synthesis prefix — these links point at "spec-driven agentic SDLC with adaptive routing, sandboxed execution, evaluation harnesses, quantized model portfolios, and map-before-act intelligence" | 10415 | E0338 | composite | false |
| F02987 | MAP — "extremely relevant" | 10419 | E0339 | composite | false |
| F02988 | MAP core point — agents fail when only reactive | 10423 | E0339 | composite | false |
| F02989 | MAP step 1 — Global exploration | 10426 | M00595 | composite | true |
| F02990 | MAP step 2 — task-specific map | 10427 | M00596 | composite | true |
| F02991 | MAP step 3 — knowledge-augmented execution | 10428 | M00597 | composite | true |
| F02992 | "Plugs directly into your vision" | 10432 | E0339 | composite | false |
| F02993 | Pre-coding MAP — repo / tests / dependencies / risks / ownership / architecture | 10436–10437 | E0339 | composite | true |
| F02994 | Pre-GUI/tool MAP — environment / available actions / failure states | 10439–10440 | E0339 | composite | true |
| F02995 | Pre-workflow MAP — task graph / blockers / verification points | 10442–10443 | E0339 | composite | true |
| F02996 | Pre-autonomy MAP — rollback / permissions / expected transitions | 10445–10446 | E0339 | composite | true |
| F02997 | Formal SDLC step — SPEC | 10452 | M00598 | composite | true |
| F02998 | Formal SDLC step — MAP | 10452 | M00598 | composite | true |
| F02999 | Formal SDLC step — PLAN | 10452 | M00598 | composite | true |
| F03000 | Formal SDLC step — ACT | 10452 | M00598 | composite | true |
| F03001 | Formal SDLC step — TEST | 10452 | M00598 | composite | true |
| F03002 | Formal SDLC step — EVAL | 10452 | M00598 | composite | true |
| F03003 | Formal SDLC step — COMMIT | 10452 | M00598 | composite | true |
| F03004 | Formal SDLC step — LEARN | 10452 | M00598 | composite | true |
| F03005 | "That is gold" | 10455 | E0339 | composite | false |
| F03006 | Symphony — "directly relevant to Spec-Driven Development" | 10458 | E0340 | composite | false |
| F03007 | Symphony — project-management issues as control plane | 10459 | E0340 | composite | false |
| F03008 | Symphony explicit artifact — SPEC.md | 10459 | E0340 | composite | true |
| F03009 | Symphony explicit artifact — per-issue isolated workspaces | 10459 | E0340 | composite | true |
| F03010 | Symphony explicit artifact — WORKFLOW.md | 10459 | E0340 | composite | true |
| F03011 | Symphony explicit artifact — bounded concurrency | 10459 | E0340 | composite | true |
| F03012 | Symphony explicit artifact — retries | 10459 | E0340 | composite | true |
| F03013 | Symphony explicit artifact — observability | 10459 | E0340 | composite | true |
| F03014 | Symphony explicit artifact — human review | 10459 | E0340 | composite | true |
| F03015 | Symphony subtle lesson — "Spec is not a cage. Spec is the contract." | 10467–10468 | E0340 | composite | false |
| F03016 | Symphony subtle lesson — agent still needs objectives + tools + judgment + room to discover new work | 10470 | E0340 | composite | false |
| F03017 | Symphony lesson — rigid state-machine boxes become too small | 10470 | E0340 | composite | false |
| F03018 | Governed-freedom artifact — SPEC.md = product/architecture intent | 10473 | M00599 | composite | true |
| F03019 | Governed-freedom artifact — WORKFLOW.md = local agent policy | 10474 | M00600 | composite | true |
| F03020 | Governed-freedom artifact — TESTS = executable truth | 10475 | M00601 | composite | true |
| F03021 | Governed-freedom artifact — EVALS = quality envelope | 10476 | M00602 | composite | true |
| F03022 | Governed-freedom artifact — PROFILES = adaptive behavior modes | 10477 | M00603 | composite | true |
| F03023 | Agent evals — "mandatory" | 10480 | E0341 | composite | false |
| F03024 | Agent evals — not just final text checks | 10482 | E0341 | composite | false |
| F03025 | Agent evals signal — task | 10482 | E0341 | composite | true |
| F03026 | Agent evals signal — trials | 10482 | E0341 | composite | true |
| F03027 | Agent evals signal — traces/trajectories | 10482 | E0341 | composite | true |
| F03028 | Agent evals signal — tool calls | 10482 | E0341 | composite | true |
| F03029 | Agent evals signal — environmental outcomes | 10482 | E0341 | composite | true |
| F03030 | Agent evals signal — graders | 10482 | E0341 | composite | true |
| F03031 | Workflow produces — trace | 10487 | M00604 | composite | true |
| F03032 | Workflow produces — trajectory | 10488 | M00604 | composite | true |
| F03033 | Workflow produces — tool calls | 10489 | M00604 | composite | true |
| F03034 | Workflow produces — environment before/after | 10490 | M00604 | composite | true |
| F03035 | Workflow produces — test results | 10491 | M00604 | composite | true |
| F03036 | Workflow produces — cost | 10492 | M00604 | composite | true |
| F03037 | Workflow produces — latency | 10493 | M00604 | composite | true |
| F03038 | Workflow produces — model route | 10494 | M00604 | composite | true |
| F03039 | Workflow produces — human interventions | 10495 | M00604 | composite | true |
| F03040 | Workflow produces — pass/fail reason | 10496 | M00604 | composite | true |
| F03041 | "This is the spine of adaptive intelligence" | 10499 | E0341 | composite | false |
| F03042 | Without evals, Goldilocks becomes vibes | 10501 | E0341 | composite | false |
| F03043 | Goldilocks-with-evals — not too cheap | 10504 | M00605 | composite | false |
| F03044 | Goldilocks-with-evals — not too slow | 10505 | M00605 | composite | false |
| F03045 | Goldilocks-with-evals — not too risky | 10506 | M00605 | composite | false |
| F03046 | Goldilocks-with-evals — not too overpowered | 10507 | M00605 | composite | false |
| F03047 | Goldilocks-with-evals — just enough intelligence for this task | 10508 | M00605 | composite | false |
| F03048 | LiteLLM Agent Platform — "useful pattern but NOT the kernel" | 10511 | E0342 | composite | false |
| F03049 | LiteLLM caution — OpenAI-format bias | 10528 | E0342 | composite | false |
| F03050 | LiteLLM caution — Kubernetes complexity | 10529 | E0342 | composite | false |
| F03051 | LiteLLM caution — may be too heavy for workstation-first architecture | 10530 | E0342 | composite | false |
| F03052 | LiteLLM placement — "use it as an inspiration or optional module. Your Anthropic-first gateway and deterministic runtime should remain the kernel" | 10533 | E0342 | composite | false |
| F03053 | NadirClaw router — "baby version of your router" | 10552 | E0343 | composite | false |
| F03054 | Adaptive router ingredient — local classifier | 10542 | M00606 | composite | true |
| F03055 | Adaptive router ingredient — task-difficulty estimator | 10543 | M00606 | composite | true |
| F03056 | Adaptive router ingredient — privacy classifier | 10544 | M00606 | composite | true |
| F03057 | Adaptive router ingredient — risk classifier | 10545 | M00606 | composite | true |
| F03058 | Adaptive router ingredient — modality classifier | 10546 | M00606 | composite | true |
| F03059 | Adaptive router ingredient — cost/latency policy | 10547 | M00606 | composite | true |
| F03060 | Composite — MAP-then-Act paradigm + 8-link synthesis + 9-layer Combined Architecture (SPEC / MAP / Compiler / Execution / Model / Router / Test+Eval / Memory / Commit) + 10-step adaptive Goldilocks AIDLC/SDLC (Specify / Map / Decompose / Route / Implement / Test / Evaluate / Review / Commit / Learn); strongest immediate pillars = MAP + Symphony + agent evals + model compression lab + routing; "Fast BLT is frontier-watch / LiteLLM is useful inspiration / Domain LLMs support model-registry/super-model" | 10628–10712 | E0347 | composite | false |

## Requirements (R05951–R06120)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R05951 | Operator-presented reading list includes Fast Byte Latent Transformer | 10379 | F02976 | non-negotiable | true | 10 |
| R05952 | Operator-presented reading list includes agent evals (Cameron Wolfe) | 10380 | F02977 | non-negotiable | true | 10 |
| R05953 | Operator-presented reading list includes 21 domain-tuned LLMs | 10381 | F02978 | non-negotiable | true | 10 |
| R05954 | Operator-presented reading list includes MAP paper arXiv 2605.13037 | 10382 | F02979 | non-negotiable | true | 10 |
| R05955 | Operator-presented reading list includes LLM compression FP8+GPTQ+SmoothQuant (llmcompressor) | 10383 | F02980 | non-negotiable | true | 10 |
| R05956 | Operator-presented reading list includes NadirClaw cost-aware routing | 10384 | F02981 | non-negotiable | true | 10 |
| R05957 | Operator-presented reading list includes OpenAI Symphony | 10385 | F02982 | non-negotiable | true | 10 |
| R05958 | Operator-presented reading list includes LiteLLM Agent Platform | 10386 | F02983 | non-negotiable | true | 10 |
| R05959 | Operator request — connect substrate to Spec Driven + TDD + multiprofile + adaptive Goldilocks + AIDLC/SDLC + super-model + high standards | 10388 | F02984 | non-negotiable | false | 10 |
| R05960 | Operator request — "we can do this in multiple iterations" | 10389 | F02985 | non-negotiable | false | 10 |
| R05961 | Synthesis — links point at "spec-driven agentic SDLC with adaptive routing, sandboxed execution, evaluation harnesses, quantized model portfolios, and map-before-act intelligence" | 10415 | F02986 | non-negotiable | false | 10 |
| R05962 | MAP is "extremely relevant" | 10419 | E0339 | non-negotiable | false | 10 |
| R05963 | MAP core insight — agents fail when they only understand environment reactively while executing | 10423 | F02988 | non-negotiable | false | 10 |
| R05964 | MAP step 1 — Global exploration | 10426 | F02989 | non-negotiable | true | 10 |
| R05965 | MAP step 2 — task-specific map | 10427 | F02990 | non-negotiable | true | 10 |
| R05966 | MAP step 3 — knowledge-augmented execution | 10428 | F02991 | non-negotiable | true | 10 |
| R05967 | MAP plugs directly into the station's vision | 10432 | F02992 | non-negotiable | false | 10 |
| R05968 | Pre-coding MAP — map repo / tests / dependencies / risks / ownership / architecture | 10436–10437 | F02993 | non-negotiable | true | 10 |
| R05969 | Pre-GUI/tool-action MAP — map environment / available actions / failure states | 10439–10440 | F02994 | non-negotiable | true | 10 |
| R05970 | Pre-workflow MAP — map task graph / blockers / verification points | 10442–10443 | F02995 | non-negotiable | true | 10 |
| R05971 | Pre-autonomy MAP — map rollback / permissions / expected transitions | 10445–10446 | F02996 | non-negotiable | true | 10 |
| R05972 | Formal SDLC step 1 — SPEC | 10452 | F02997 | non-negotiable | true | 10 |
| R05973 | Formal SDLC step 2 — MAP | 10452 | F02998 | non-negotiable | true | 10 |
| R05974 | Formal SDLC step 3 — PLAN | 10452 | F02999 | non-negotiable | true | 10 |
| R05975 | Formal SDLC step 4 — ACT | 10452 | F03000 | non-negotiable | true | 10 |
| R05976 | Formal SDLC step 5 — TEST | 10452 | F03001 | non-negotiable | true | 10 |
| R05977 | Formal SDLC step 6 — EVAL | 10452 | F03002 | non-negotiable | true | 10 |
| R05978 | Formal SDLC step 7 — COMMIT | 10452 | F03003 | non-negotiable | true | 10 |
| R05979 | Formal SDLC step 8 — LEARN | 10452 | F03004 | non-negotiable | true | 10 |
| R05980 | "That is gold" | 10455 | F03005 | non-negotiable | false | 10 |
| R05981 | Symphony — "directly relevant to Spec-Driven Development" | 10458 | F03006 | non-negotiable | false | 10 |
| R05982 | Symphony — treats project-management issues as the control plane | 10459 | F03007 | non-negotiable | false | 10 |
| R05983 | Symphony explicit artifact — SPEC.md | 10459 | F03008 | non-negotiable | true | 10 |
| R05984 | Symphony explicit artifact — per-issue isolated workspaces | 10459 | F03009 | non-negotiable | true | 10 |
| R05985 | Symphony explicit artifact — WORKFLOW.md | 10459 | F03010 | non-negotiable | true | 10 |
| R05986 | Symphony explicit artifact — bounded concurrency | 10459 | F03011 | non-negotiable | true | 10 |
| R05987 | Symphony explicit artifact — retries | 10459 | F03012 | non-negotiable | true | 10 |
| R05988 | Symphony explicit artifact — observability | 10459 | F03013 | non-negotiable | true | 10 |
| R05989 | Symphony explicit artifact — human review | 10459 | F03014 | non-negotiable | true | 10 |
| R05990 | Symphony lesson — "Spec is not a cage. Spec is the contract." | 10467–10468 | F03015 | non-negotiable | false | 10 |
| R05991 | Symphony lesson — agent still needs objectives + tools + judgment + room to discover new work | 10470 | F03016 | non-negotiable | false | 10 |
| R05992 | Symphony lesson — rigid state-machine boxes become too small | 10470 | F03017 | non-negotiable | false | 10 |
| R05993 | Governed-freedom artifact SPEC.md — product/architecture intent | 10473 | F03018 | non-negotiable | true | 10 |
| R05994 | Governed-freedom artifact WORKFLOW.md — local agent policy | 10474 | F03019 | non-negotiable | true | 10 |
| R05995 | Governed-freedom artifact TESTS — executable truth | 10475 | F03020 | non-negotiable | true | 10 |
| R05996 | Governed-freedom artifact EVALS — quality envelope | 10476 | F03021 | non-negotiable | true | 10 |
| R05997 | Governed-freedom artifact PROFILES — adaptive behavior modes | 10477 | F03022 | non-negotiable | true | 10 |
| R05998 | Agent evals are mandatory | 10480 | F03023 | non-negotiable | false | 10 |
| R05999 | Agent evals are NOT just final text checks | 10482 | F03024 | non-negotiable | false | 10 |
| R06000 | Agent eval includes — task | 10482 | F03025 | non-negotiable | true | 10 |
| R06001 | Agent eval includes — trials | 10482 | F03026 | non-negotiable | true | 10 |
| R06002 | Agent eval includes — traces/trajectories | 10482 | F03027 | non-negotiable | true | 10 |
| R06003 | Agent eval includes — tool calls | 10482 | F03028 | non-negotiable | true | 10 |
| R06004 | Agent eval includes — environmental outcomes | 10482 | F03029 | non-negotiable | true | 10 |
| R06005 | Agent eval includes — graders | 10482 | F03030 | non-negotiable | true | 10 |
| R06006 | Workflow produces — trace | 10487 | F03031 | non-negotiable | true | 10 |
| R06007 | Workflow produces — trajectory | 10488 | F03032 | non-negotiable | true | 10 |
| R06008 | Workflow produces — tool calls | 10489 | F03033 | non-negotiable | true | 10 |
| R06009 | Workflow produces — environment before/after | 10490 | F03034 | non-negotiable | true | 10 |
| R06010 | Workflow produces — test results | 10491 | F03035 | non-negotiable | true | 10 |
| R06011 | Workflow produces — cost | 10492 | F03036 | non-negotiable | true | 10 |
| R06012 | Workflow produces — latency | 10493 | F03037 | non-negotiable | true | 10 |
| R06013 | Workflow produces — model route | 10494 | F03038 | non-negotiable | true | 10 |
| R06014 | Workflow produces — human interventions | 10495 | F03039 | non-negotiable | true | 10 |
| R06015 | Workflow produces — pass/fail reason | 10496 | F03040 | non-negotiable | true | 10 |
| R06016 | "Spine of adaptive intelligence" | 10499 | F03041 | non-negotiable | false | 10 |
| R06017 | Without evals, Goldilocks becomes vibes | 10501 | F03042 | non-negotiable | false | 10 |
| R06018 | Goldilocks-with-evals — not too cheap | 10504 | F03043 | non-negotiable | false | 10 |
| R06019 | Goldilocks-with-evals — not too slow | 10505 | F03044 | non-negotiable | false | 10 |
| R06020 | Goldilocks-with-evals — not too risky | 10506 | F03045 | non-negotiable | false | 10 |
| R06021 | Goldilocks-with-evals — not too overpowered | 10507 | F03046 | non-negotiable | false | 10 |
| R06022 | Goldilocks-with-evals — just enough intelligence for this task | 10508 | F03047 | non-negotiable | false | 10 |
| R06023 | LiteLLM Agent Platform — relevant for sandbox/session architecture (NOT the kernel) | 10511–10516 | F03048 | non-negotiable | false | 10 |
| R06024 | LiteLLM useful pattern — per-session sandbox | 10520 | E0342 | non-negotiable | true | 10 |
| R06025 | LiteLLM useful pattern — harness abstraction | 10521 | E0342 | non-negotiable | true | 10 |
| R06026 | LiteLLM useful pattern — persistent session state | 10522 | E0342 | non-negotiable | true | 10 |
| R06027 | LiteLLM useful pattern — model gateway separation | 10523 | E0342 | non-negotiable | true | 10 |
| R06028 | LiteLLM useful pattern — cost tracking | 10524 | E0342 | non-negotiable | true | 10 |
| R06029 | LiteLLM caution — OpenAI-format bias | 10528 | F03049 | non-negotiable | false | 10 |
| R06030 | LiteLLM caution — Kubernetes complexity | 10529 | F03050 | non-negotiable | false | 10 |
| R06031 | LiteLLM caution — may be too heavy for workstation-first architecture | 10530 | F03051 | non-negotiable | false | 10 |
| R06032 | LiteLLM placement — use as inspiration or optional module; Anthropic-first gateway + deterministic runtime remain the kernel | 10533 | F03052 | non-negotiable | false | 10 |
| R06033 | NadirClaw — minimal example of local classification before model dispatch | 10537 | E0343 | non-negotiable | false | 10 |
| R06034 | NadirClaw mechanism — local embeddings/centroids + confidence thresholds + proxying + cost reporting | 10537 | E0343 | non-negotiable | false | 10 |
| R06035 | Adaptive router ingredient — local classifier | 10542 | F03054 | non-negotiable | true | 10 |
| R06036 | Adaptive router ingredient — task-difficulty estimator | 10543 | F03055 | non-negotiable | true | 10 |
| R06037 | Adaptive router ingredient — privacy classifier | 10544 | F03056 | non-negotiable | true | 10 |
| R06038 | Adaptive router ingredient — risk classifier | 10545 | F03057 | non-negotiable | true | 10 |
| R06039 | Adaptive router ingredient — modality classifier | 10546 | F03058 | non-negotiable | true | 10 |
| R06040 | Adaptive router ingredient — cost/latency policy | 10547 | F03059 | non-negotiable | true | 10 |
| R06041 | Adaptive router ingredient — model registry | 10548 | M00606 | non-negotiable | true | 10 |
| R06042 | NadirClaw — "not the final router. It is the baby version of your router." | 10552 | F03053 | non-negotiable | false | 10 |
| R06043 | LLM Compressor — very relevant for the model lab | 10554 | E0344 | non-negotiable | false | 10 |
| R06044 | Workstation needs model qualification pipeline (NOT random downloaded models) | 10556 | E0344 | non-negotiable | false | 10 |
| R06045 | Use LLM Compressor docs as more primary technical reference | 10558 | E0344 | non-negotiable | true | 10 |
| R06046 | Model lab benchmark — BF16 / FP16 baseline | 10562 | M00607 | non-negotiable | true | 10 |
| R06047 | Model lab benchmark — FP8 | 10563 | M00607 | non-negotiable | true | 10 |
| R06048 | Model lab benchmark — GPTQ W4A16 | 10564 | M00607 | non-negotiable | true | 10 |
| R06049 | Model lab benchmark — SmoothQuant W8A8 | 10565 | M00607 | non-negotiable | true | 10 |
| R06050 | Model lab benchmark — KV-cache quantization | 10566 | M00607 | non-negotiable | true | 10 |
| R06051 | Model lab benchmark — NVFP4/MXFP4 (Blackwell-ready) | 10567 | M00607 | non-negotiable | true | 10 |
| R06052 | Model lab score-by-profile — coding quality | 10574 | M00608 | non-negotiable | true | 10 |
| R06053 | Model lab score-by-profile — tool-call reliability | 10575 | M00608 | non-negotiable | true | 10 |
| R06054 | Model lab score-by-profile — JSON/schema validity | 10576 | M00608 | non-negotiable | true | 10 |
| R06055 | Model lab score-by-profile — latency | 10577 | M00608 | non-negotiable | true | 10 |
| R06056 | Model lab score-by-profile — VRAM | 10578 | M00608 | non-negotiable | true | 10 |
| R06057 | Model lab score-by-profile — tokens/sec | 10579 | M00608 | non-negotiable | true | 10 |
| R06058 | Model lab score-by-profile — energy | 10580 | M00608 | non-negotiable | true | 10 |
| R06059 | Model lab score-by-profile — eval pass rate | 10581 | M00608 | non-negotiable | true | 10 |
| R06060 | "How you build a serious local model portfolio" | 10584 | E0344 | non-negotiable | false | 10 |
| R06061 | Fast BLT — frontier-relevant, not immediate infrastructure | 10586–10588 | E0345 | non-negotiable | false | 10 |
| R06062 | Fast BLT — reduces inference memory-bandwidth pressure in byte-level models via diffusion/speculation-style decoding | 10588 | E0345 | non-negotiable | true | 10 |
| R06063 | Fast BLT — estimated memory-bandwidth cost reductions over 50% | 10588 | E0345 | non-negotiable | false | 10 |
| R06064 | Memory-bandwidth-aware architecture — avoid wasted decoding | 10593 | E0345 | non-negotiable | true | 10 |
| R06065 | Memory-bandwidth-aware architecture — batch verification | 10594 | E0345 | non-negotiable | true | 10 |
| R06066 | Memory-bandwidth-aware architecture — speculate cheaply | 10595 | E0345 | non-negotiable | true | 10 |
| R06067 | Memory-bandwidth-aware architecture — verify deterministically | 10596 | E0345 | non-negotiable | true | 10 |
| R06068 | Memory-bandwidth-aware architecture — reduce tokenizer fragility | 10597 | E0345 | non-negotiable | true | 10 |
| R06069 | Fast BLT placement — "watch and prototype bucket" (not anchor station today) | 10600 | E0345 | non-negotiable | false | 10 |
| R06070 | Domain LLMs — strategically relevant for model registry | 10602 | E0346 | non-negotiable | false | 10 |
| R06071 | Domain specialization — medical | 10604 | E0346 | non-negotiable | true | 10 |
| R06072 | Domain specialization — legal | 10604 | E0346 | non-negotiable | true | 10 |
| R06073 | Domain specialization — finance | 10604 | E0346 | non-negotiable | true | 10 |
| R06074 | Domain specialization — security | 10604 | E0346 | non-negotiable | true | 10 |
| R06075 | Domain specialization — climate | 10604 | E0346 | non-negotiable | true | 10 |
| R06076 | Domain specialization — code | 10604 | E0346 | non-negotiable | true | 10 |
| R06077 | Domain specialization — reasoning | 10604 | E0346 | non-negotiable | true | 10 |
| R06078 | Super-model definition — "Super-model != one giant model. Super-model = routed ecology of specialists." | 10610–10611 | E0346 | non-negotiable | false | 10 |
| R06079 | Model registry knows — model role | 10615 | M00609 | non-negotiable | true | 10 |
| R06080 | Model registry knows — domain | 10616 | M00609 | non-negotiable | true | 10 |
| R06081 | Model registry knows — precision | 10617 | M00609 | non-negotiable | true | 10 |
| R06082 | Model registry knows — hardware fit | 10618 | M00609 | non-negotiable | true | 10 |
| R06083 | Model registry knows — tool-use score | 10619 | M00609 | non-negotiable | true | 10 |
| R06084 | Model registry knows — eval score | 10620 | M00609 | non-negotiable | true | 10 |
| R06085 | Model registry knows — privacy class | 10621 | M00609 | non-negotiable | true | 10 |
| R06086 | Model registry knows — cost | 10622 | M00609 | non-negotiable | true | 10 |
| R06087 | Model registry knows — latency | 10623 | M00609 | non-negotiable | true | 10 |
| R06088 | Model registry knows — failure modes | 10624 | M00609 | non-negotiable | true | 10 |
| R06089 | Combined Architecture — SPEC Layer (SPEC.md / WORKFLOW.md / PROFILES.yaml / EVALS.yaml) | 10633–10634 | M00610 | non-negotiable | true | 10 |
| R06090 | Combined Architecture — MAP Layer (repo map / environment map / task map / dependency map) | 10636–10637 | M00610 | non-negotiable | true | 10 |
| R06091 | Combined Architecture — Compiler Layer (spec → workflow DAG → tool/model/action plan) | 10639–10640 | M00610 | non-negotiable | true | 10 |
| R06092 | Combined Architecture — Execution Layer (sandboxes / REPLs / Claude Code-OpenCode-Cline clients) | 10642–10643 | M00610 | non-negotiable | true | 10 |
| R06093 | Combined Architecture — Model Layer (local oracle / SLM scouts / RLM-map agents / specialists / optional cloud) | 10645–10646 | M00610 | non-negotiable | true | 10 |
| R06094 | Combined Architecture — Router Layer (cost-aware / risk-aware / profile-aware / eval-aware) | 10648–10649 | M00610 | non-negotiable | true | 10 |
| R06095 | Combined Architecture — Test/Eval Layer (TDD / outcome checks / trajectory evals / regression suites) | 10651–10652 | M00610 | non-negotiable | true | 10 |
| R06096 | Combined Architecture — Memory Layer (traces / lessons / skills / model performance / project maps) | 10654–10655 | M00610 | non-negotiable | true | 10 |
| R06097 | Combined Architecture — Commit Layer (human review / policy gates / rollback / promotion) | 10657–10658 | M00610 | non-negotiable | true | 10 |
| R06098 | Methodology step 1 — Specify (Define intent / constraints / non-goals / acceptance criteria) | 10666–10667 | M00611 | non-negotiable | true | 10 |
| R06099 | Methodology step 2 — Map (Inspect environment before acting) | 10669–10670 | M00611 | non-negotiable | true | 10 |
| R06100 | Methodology step 3 — Decompose (Build task graph + dependency tree) | 10672–10673 | M00611 | non-negotiable | true | 10 |
| R06101 | Methodology step 4 — Route (Choose profile / model / sandbox / budget) | 10675–10676 | M00611 | non-negotiable | true | 10 |
| R06102 | Methodology step 5 — Implement (Agent branches work in isolated spaces) | 10678–10679 | M00611 | non-negotiable | true | 10 |
| R06103 | Methodology step 6 — Test (TDD / unit / integration / e2e / property checks) | 10681–10682 | M00611 | non-negotiable | true | 10 |
| R06104 | Methodology step 7 — Evaluate (Agent trajectory + outcome + cost + risk) | 10684–10685 | M00611 | non-negotiable | true | 10 |
| R06105 | Methodology step 8 — Review (Oracle / human / code review depending on risk) | 10687–10688 | M00611 | non-negotiable | true | 10 |
| R06106 | Methodology step 9 — Commit (Merge / promote only after gates pass) | 10690–10691 | M00611 | non-negotiable | true | 10 |
| R06107 | Methodology step 10 — Learn (Store traces / update skills / adjust profiles) | 10693–10694 | M00611 | non-negotiable | true | 10 |
| R06108 | Synthesis — MAP gives situational intelligence | 10700 | E0347 | non-negotiable | false | 10 |
| R06109 | Synthesis — Symphony gives orchestration | 10701 | E0347 | non-negotiable | false | 10 |
| R06110 | Synthesis — agent evals give measurement | 10702 | E0347 | non-negotiable | false | 10 |
| R06111 | Synthesis — LiteLLM Agent Platform gives sandbox/session patterns | 10703 | E0347 | non-negotiable | false | 10 |
| R06112 | Synthesis — NadirClaw gives router seed | 10704 | E0347 | non-negotiable | false | 10 |
| R06113 | Synthesis — LLM Compressor gives model lab discipline | 10705 | E0347 | non-negotiable | false | 10 |
| R06114 | Synthesis — Domain LLMs give specialist ecology | 10706 | E0347 | non-negotiable | false | 10 |
| R06115 | Synthesis — Fast BLT gives frontier decoding direction | 10707 | E0347 | non-negotiable | false | 10 |
| R06116 | Priority — strongest immediate pillars = MAP + Symphony + agent evals + model compression lab + routing | 10710 | E0347 | non-negotiable | false | 10 |
| R06117 | Priority — Fast BLT is frontier-watch | 10710 | E0347 | non-negotiable | false | 10 |
| R06118 | Priority — LiteLLM Agent Platform is useful infrastructure inspiration | 10710 | E0347 | non-negotiable | false | 10 |
| R06119 | Priority — Domain LLMs support model-registry/super-model philosophy | 10710 | E0347 | non-negotiable | false | 10 |
| R06120 | Composite — MAP-then-act paradigm is the 16th plane (extending M027 + M028 + M029 + M030 + M031 + M032 + M033 + M034 + M035); 8-link operator-presented substrate; 9-layer Combined Architecture (SPEC / MAP / Compiler / Execution / Model / Router / Test+Eval / Memory / Commit); 10-step adaptive Goldilocks AIDLC/SDLC (Specify / Map / Decompose / Route / Implement / Test / Evaluate / Review / Commit / Learn); formal SDLC sequence SPEC → MAP → PLAN → ACT → TEST → EVAL → COMMIT → LEARN; Symphony governed-freedom (SPEC.md / WORKFLOW.md / TESTS / EVALS / PROFILES); 10-signal agent-eval catalog; 7-ingredient adaptive router; 6-tier model lab benchmark + 8-profile score; 7-domain specialist registry; integrates with M025-M035 | 10378–10712 | E0338 + E0339 + E0340 + E0341 + E0342 + E0343 + E0344 + E0345 + E0346 + E0347 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M035 Frontier inference-time intelligence (10109–10378) / M037 (next; dump 10712–…)
- Plane integration: M025 cognitive compiler (Compiler Layer + step 3 Decompose) / M026 SLM swarm + RLM engine (Model Layer SLM scouts + RLM-map agents) / M027 Value Plane (eval pass rate scoring) / M028 Memory OS (Memory Layer traces+lessons+skills+model-performance+project-maps) / M029 Computer-Use Plane (Execution Layer GUI actions + Pre-GUI MAP) / M030 World Model Plane (Pre-autonomy MAP rollback+permissions+expected-transitions) / M031 Symbolic Planning Plane (TEST+EVAL Layer property checks) / M032 Cloud Expert Plane (Router Layer cost-aware) / M033 Compatibility Gateway + M034 Anthropic-first Gateway (Execution Layer Claude Code/OpenCode/Cline clients) / M035 Frontier (Combined Architecture is the operationalization of M035 9-layer Runtime Shape)
- Operator methodology — adaptive Goldilocks AIDLC/SDLC; 10 steps; SPEC.md + WORKFLOW.md + TESTS + EVALS + PROFILES as governed-freedom artifacts
- Source links: arXiv:2605.13037 (MAP) / OpenAI Symphony / Cameron Wolfe agent evals / LiteLLM Agent Platform / NadirClaw / llmcompressor + vLLM compression docs / arXiv:2605.08044 (Fast BLT) / InfoWorld 21 domain LLMs
