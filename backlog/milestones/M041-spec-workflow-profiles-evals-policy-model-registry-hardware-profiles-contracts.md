# M041 — Spec / WORKFLOW / PROFILES / EVALS / POLICY / MODEL_REGISTRY / HARDWARE_PROFILES contracts

> Parent: `backlog/milestones/INDEX.md` row M041 (dump 11790–12094).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 11790–12094. Operator directive 12094: "great continue did we extract all we could from the research I gave you ? and whatever you followed and also researched after and whatnot ?".
> All entries below extract verbatim. No invention.

## Epics (E0388–E0397)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0388 | Primary-source sweep status — "We extracted the main architecture signal, but not every implementation-grade detail yet"; one more sweep around papers/tools to separate: already absorbed / still worth mining / likely noise | 11790–11792 |
| E0389 | Agent Harness Engineering survey (openreview.net/pdf/f358711a95aaaf61fdeffd4ef3fc60fba9b8da57.pdf) — 7-layer thesis: "production reliability depends less on the raw model and more on the agent harness around it" — Execution environment / Tool interface / Context management / Lifecycle-orchestration / Observability / Verification / Governance | 11804–11814 |
| E0390 | 7-layer → station mapping — Execution→sandboxes-VM-REPL-ZFS-workspaces / Tool→MCP-Claude-Code-OpenCode-Cline-gateway / Context→memory-OS-KV-cache-RLM-MAP / Lifecycle→workflows-Symphony-like-orchestration-profiles / Observability→traces-cost-DCGM-eBPF-evals / Verification→tests-TDD-PRM-RM-oracle-formal-checks / Governance→policy-bits-capabilities-secrets-human-gates; "we independently converged on what current research calls the harness layer" | 11816–11826 + 11828 |
| E0391 | MAP paradigm (arxiv.org/abs/2605.13037) — "Do not act before understanding the environment" → "MAP phase before ACT phase" → methodology: MAP → SPEC → TEST → ACT → EVAL → COMMIT → LEARN; "MAP is especially important for long-horizon coding, GUI use, repo work, and agent autonomy" | 11832–11848 |
| E0392 | OpenAI Symphony SPEC (github.com/openai/symphony/blob/main/SPEC.md) — 6 takeaways: WORKFLOW.md as repo-owned contract / per-issue isolated workspaces / bounded concurrency / retry-reconciliation / structured observability / dynamic workflow reload; "Symphony is narrower than your vision — it is issue-to-agent orchestration; your system should generalize it into workflow contracts for any intelligence run"; big takeaway: "Workflow policy belongs in the repo/environment, versioned beside the work"; "That fits your Spec/TDD/SDLC world beautifully" | 11850–11864 |
| E0393 | LiteLLM Agent Platform (docs.litellm-agent-platform.ai/introduction) — sandboxed agent sessions / persistent environments / vault proxy with stub credentials / Claude Code-Codex-OpenCode harness support; "vault sidecar idea: agent sees fake-stub key + sidecar swaps real key at wire boundary + real secret never enters agent process"; station translation: Claude-first gateway / real keys protected / cost ledger central / model routing central / sandbox session observable | 11866–11881 |
| E0394 | Fast BLT (arxiv.org/abs/2605.08044) — memory bandwidth is a frontier bottleneck / byte-level models can become practical through diffusion-speculative generation / parallel byte generation matters; "not immediate station infrastructure unless serving code matures"; deeper principle: reduce forward passes / reduce memory bandwidth waste / speculate cheaply / verify carefully — "exactly the Blackwell + 4090 + AVX-512 architecture" | 11883–11900 |
| E0395 | Model portfolio + routing — LLM compression-llmcompressor lesson "model portfolio must be measured, not guessed" → station model lab (BF16 baseline / FP8 / GPTQ / SmoothQuant / AWQ / NVFP4-MXFP4 when stable / KV quantization) "every model earns a profile slot through evals"; NadirClaw routing lesson "cheap local classification before expensive model routing" → adaptive Goldilocks router (prompt classifier / privacy classifier / risk classifier / difficulty estimator / domain classifier / profile selector) | 11902–11921 |
| E0396 | What we have NOT fully mined yet (deferred passes) — MAP PDF (exact map representation + benchmark setup + what "map" should contain) / Fast BLT PDF (BLT-D-BLT-S-BLT-DV practical serving target) / LiteLLM docs (sandbox architecture + vault proxy details + compatibility boundaries) / Symphony SPEC (exact WORKFLOW.md schema we could adapt into PROFILE/SPEC contract) / Agent Harness survey (full taxonomy + project list) / Claude Code integration (exact Anthropic-compatible gateway behavior + hooks + MCP + subagents) / Hardware stack (MIG behavior on RTX PRO 6000 + VFIO topology + ZFS layout + AVX-512 prototype); "we extracted the architecture, not yet the full implementation bill of materials" | 11923–11991 |
| E0397 | The Strong Synthesis — 7 canonical contracts (SPEC.md "what should be true" / WORKFLOW.md "how agents should behave in this repo-environment" / PROFILES.yaml "how much intelligence-risk-cost-autonomy-verification to spend" / EVALS.yaml "how success is measured" / MAP.json "what the system knows about the environment before acting" / MODEL_REGISTRY.yaml "which models exist where they run what they are good at" / POLICY.yaml "what actions are allowed-gated-sandboxed-or-forbidden") + Runtime compile pipeline (Task → MAP → SPEC/TDD plan → workflow DAG → model/tool routing → sandbox execution → tests/evals → oracle/human review → commit → memory update) + Hardware overlay (Ryzen-9900X-AVX512 / RTX-PRO-6000-Blackwell / RTX-4090 / 256GB-RAM / NVMe-ZFS / 10GbE-2.5GbE) + North Star "programmable intelligence harness" with 9 properties (SMART routing / adaptive profiles / spec+TDD contracts / agent evals / model portfolio / hardware-aware scheduling / safe sandboxes / cost tracking / memory and replay); next artifact: Jean Station Architecture Spec v0.1 | 11993–12081 |

## Modules (M00680–M00696)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00680 | Harness Layer 1 — Execution environment (sandboxes / VM / REPL / ZFS workspaces) | 11806 + 11818 | E0389 + E0390 |
| M00681 | Harness Layer 2 — Tool interface (MCP / Claude Code / OpenCode / Cline / gateway) | 11807 + 11819 | E0389 + E0390 |
| M00682 | Harness Layer 3 — Context management (memory OS / KV cache / RLM / MAP) | 11808 + 11820 | E0389 + E0390 |
| M00683 | Harness Layer 4 — Lifecycle / orchestration (workflows / Symphony-like orchestration / profiles) | 11809 + 11821 | E0389 + E0390 |
| M00684 | Harness Layer 5 — Observability (traces / cost / DCGM / eBPF / evals) | 11810 + 11822 | E0389 + E0390 |
| M00685 | Harness Layer 6 — Verification (tests / TDD / PRM-RM / oracle / formal checks) | 11811 + 11823 | E0389 + E0390 |
| M00686 | Harness Layer 7 — Governance (policy bits / capabilities / secrets / human gates) | 11812 + 11824 | E0389 + E0390 |
| M00687 | SPEC.md contract — "what should be true" | 11995 | E0397 |
| M00688 | WORKFLOW.md contract — "how agents should behave in this repo/environment" | 11998 | E0397 |
| M00689 | PROFILES.yaml contract — "how much intelligence, risk, cost, autonomy, and verification to spend" | 12001 | E0397 |
| M00690 | EVALS.yaml contract — "how success is measured" | 12004 | E0397 |
| M00691 | MAP.json contract — "what the system knows about the environment before acting" | 12007 | E0397 |
| M00692 | MODEL_REGISTRY.yaml contract — "which models exist, where they run, what they are good at" | 12010 | E0397 |
| M00693 | POLICY.yaml contract — "what actions are allowed, gated, sandboxed, or forbidden" | 12013 | E0397 |
| M00694 | Runtime compile pipeline — Task → MAP → SPEC/TDD plan → workflow DAG → model/tool routing → sandbox execution → tests/evals → oracle/human review → commit → memory update | 12016–12027 | E0397 |
| M00695 | Hardware overlay — Ryzen-9900X-AVX512 / RTX-PRO-6000-Blackwell / RTX-4090 / 256GB-RAM / NVMe-ZFS / 10GbE-2.5GbE | 12031–12053 | E0397 |
| M00696 | North-Star "programmable intelligence harness" — 9 properties (SMART routing / adaptive profiles / spec+TDD contracts / agent evals / model portfolio / hardware-aware scheduling / safe sandboxes / cost tracking / memory and replay) | 12060–12079 | E0397 |

## Features (F03401–F03485)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F03401 | Primary-source sweep — separates absorbed / still-worth-mining / likely-noise | 11791 | E0388 |
| F03402 | Sweep input — Fast Byte Latent Transformer (Meta Stanford 2605.08044) | 11796 | E0388 |
| F03403 | Sweep input — MAP arxiv 2605.13037 | 11797 | E0388 |
| F03404 | Sweep input — OpenAI Symphony SPEC | 11798 | E0388 |
| F03405 | Sweep input — Agent Harness Engineering survey (openreview pdf) | 11800 | E0388 |
| F03406 | Survey thesis — production reliability depends less on raw model + more on harness around it | 11804 | E0389 |
| F03407 | 7-layer harness — Execution environment | 11806 | M00680 |
| F03408 | 7-layer harness — Tool interface | 11807 | M00681 |
| F03409 | 7-layer harness — Context management | 11808 | M00682 |
| F03410 | 7-layer harness — Lifecycle / orchestration | 11809 | M00683 |
| F03411 | 7-layer harness — Observability | 11810 | M00684 |
| F03412 | 7-layer harness — Verification | 11811 | M00685 |
| F03413 | 7-layer harness — Governance | 11812 | M00686 |
| F03414 | Mapping — Execution → sandboxes, VM, REPL, ZFS workspaces | 11818 | M00680 |
| F03415 | Mapping — Tool interface → MCP, Claude Code, OpenCode, Cline, gateway | 11819 | M00681 |
| F03416 | Mapping — Context → memory OS, KV cache, RLM, MAP | 11820 | M00682 |
| F03417 | Mapping — Lifecycle → workflows, Symphony-like orchestration, profiles | 11821 | M00683 |
| F03418 | Mapping — Observability → traces, cost, DCGM, eBPF, evals | 11822 | M00684 |
| F03419 | Mapping — Verification → tests, TDD, PRM/RM, oracle, formal checks | 11823 | M00685 |
| F03420 | Mapping — Governance → policy bits, capabilities, secrets, human gates | 11824 | M00686 |
| F03421 | Convergence claim — "we independently converged on what current research calls the harness layer" | 11828 | E0390 |
| F03422 | MAP doctrine — "Do not act before understanding the environment" | 11836 | E0391 |
| F03423 | MAP rule — "MAP phase before ACT phase" | 11840 | E0391 |
| F03424 | Methodology — MAP → SPEC → TEST → ACT → EVAL → COMMIT → LEARN | 11844 | E0391 |
| F03425 | MAP importance — long-horizon coding | 11848 | E0391 |
| F03426 | MAP importance — GUI use | 11848 | E0391 |
| F03427 | MAP importance — repo work | 11848 | E0391 |
| F03428 | MAP importance — agent autonomy | 11848 | E0391 |
| F03429 | Symphony takeaway — WORKFLOW.md as repo-owned contract | 11853 | M00688 |
| F03430 | Symphony takeaway — per-issue isolated workspaces | 11854 | M00683 |
| F03431 | Symphony takeaway — bounded concurrency | 11855 | M00683 |
| F03432 | Symphony takeaway — retry/reconciliation | 11856 | M00683 |
| F03433 | Symphony takeaway — structured observability | 11857 | M00684 |
| F03434 | Symphony takeaway — dynamic workflow reload | 11858 | M00683 |
| F03435 | Symphony scope — narrower than vision (issue-to-agent orchestration) | 11860 | E0392 |
| F03436 | Generalization — "workflow contracts for any intelligence run" | 11862 | E0392 |
| F03437 | Symphony big takeaway — "Workflow policy belongs in the repo/environment, versioned beside the work" | 11864 | M00688 |
| F03438 | Fit claim — fits Spec/TDD/SDLC world beautifully | 11864 | E0392 |
| F03439 | LiteLLM input — sandboxed agent sessions | 11868 | M00680 |
| F03440 | LiteLLM input — persistent environments | 11869 | M00680 |
| F03441 | LiteLLM input — vault proxy with stub credentials | 11870 | M00686 |
| F03442 | LiteLLM input — Claude Code / Codex / OpenCode harness support | 11871 | M00681 |
| F03443 | Vault sidecar — agent sees fake/stub key | 11874 | M00686 |
| F03444 | Vault sidecar — sidecar swaps real key at wire boundary | 11875 | M00686 |
| F03445 | Vault sidecar — real secret never enters agent process | 11876 | M00686 |
| F03446 | Station translation — Claude-first gateway | 11879 | M00681 |
| F03447 | Station translation — real keys protected | 11879 | M00686 |
| F03448 | Station translation — cost ledger central | 11880 | M00684 |
| F03449 | Station translation — model routing central | 11880 | M00681 |
| F03450 | Station translation — sandbox session observable | 11881 | M00684 |
| F03451 | Fast BLT lesson — memory bandwidth is a frontier bottleneck | 11885 | E0394 |
| F03452 | Fast BLT lesson — byte-level models can become practical via diffusion/speculative generation | 11886 | E0394 |
| F03453 | Fast BLT lesson — parallel byte generation matters | 11887 | E0394 |
| F03454 | Deeper principle — reduce forward passes | 11893 | E0394 |
| F03455 | Deeper principle — reduce memory bandwidth waste | 11894 | E0394 |
| F03456 | Deeper principle — speculate cheaply | 11895 | E0394 |
| F03457 | Deeper principle — verify carefully | 11896 | E0394 |
| F03458 | Architecture confirmation — "exactly the Blackwell + 4090 + AVX-512 architecture" | 11900 | E0394 |
| F03459 | LLM-compressor lesson — model portfolio must be measured, not guessed | 11904 | E0395 |
| F03460 | Model-lab roster — BF16 baseline | 11908 | E0395 |
| F03461 | Model-lab roster — FP8 | 11909 | E0395 |
| F03462 | Model-lab roster — GPTQ | 11910 | E0395 |
| F03463 | Model-lab roster — SmoothQuant | 11911 | E0395 |
| F03464 | Model-lab roster — AWQ | 11912 | E0395 |
| F03465 | Model-lab roster — NVFP4/MXFP4 when stable | 11913 | E0395 |
| F03466 | Model-lab roster — KV quantization | 11914 | E0395 |
| F03467 | Profile-slot rule — every model earns slot through evals | 11916 | E0395 |
| F03468 | Router classifier — prompt classifier | 11918 | E0395 |
| F03469 | Router classifier — privacy classifier | 11918 | E0395 |
| F03470 | Router classifier — risk classifier | 11918 | E0395 |
| F03471 | Router classifier — difficulty estimator | 11919 | E0395 |
| F03472 | Router classifier — domain classifier | 11919 | E0395 |
| F03473 | Router classifier — profile selector | 11919 | E0395 |
| F03474 | Adaptive Goldilocks router — composite of 6 classifiers above | 11921 | E0395 |
| F03475 | Deferred pass — MAP PDF (map representation + benchmark setup + what map should contain) | 11929 | E0396 |
| F03476 | Deferred pass — Fast BLT PDF (BLT-D / BLT-S / BLT-DV practical serving target) | 11932 | E0396 |
| F03477 | Deferred pass — LiteLLM docs (sandbox arch + vault proxy details + compatibility boundaries) | 11935 | E0396 |
| F03478 | Deferred pass — Symphony SPEC (WORKFLOW.md schema → PROFILE/SPEC contract) | 11938 | E0396 |
| F03479 | Deferred pass — Agent Harness survey (full taxonomy + project list) | 11941 | E0396 |
| F03480 | Deferred pass — Claude Code integration (Anthropic-compatible gateway behavior + hooks + MCP + subagents) | 11944 | E0396 |
| F03481 | Deferred pass — Hardware stack (MIG behavior on RTX PRO 6000 + VFIO topology + ZFS layout + AVX-512 prototype) | 11990 | E0396 |
| F03482 | Synthesis claim — "we extracted the architecture, not yet the full implementation bill of materials" | 11991 | E0396 |
| F03483 | Contract 1 — SPEC.md | 11995 | M00687 |
| F03484 | Contract 1 phrase — "What should be true" | 11996 | M00687 |
| F03485 | Contract 2 — WORKFLOW.md + Contract 3 PROFILES.yaml + Contract 4 EVALS.yaml + Contract 5 MAP.json + Contract 6 MODEL_REGISTRY.yaml + Contract 7 POLICY.yaml + Runtime-compile-pipeline 10-step + Hardware-overlay 6-tier + North-Star programmable-intelligence-harness 9-property + next artifact "Jean Station Architecture Spec v0.1" | 11998–12081 | M00688..M00696 |

## Requirements (R06801–R06970)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R06801 | One more primary-source sweep around papers/tools | 11791 | F03401 | non-negotiable | false | 10 |
| R06802 | Sweep separates: already absorbed | 11791 | F03401 | non-negotiable | false | 10 |
| R06803 | Sweep separates: still worth mining | 11791 | F03401 | non-negotiable | false | 10 |
| R06804 | Sweep separates: likely noise | 11791 | F03401 | non-negotiable | false | 10 |
| R06805 | Sweep input — Fast Byte Latent Transformer (Meta Stanford 2605.08044 PDF BLT inference memory bandwidth) | 11796 | F03402 | non-negotiable | false | 10 |
| R06806 | Sweep input — MAP arxiv 2605.13037 | 11797 | F03403 | non-negotiable | false | 10 |
| R06807 | Sweep input — OpenAI Symphony SPEC (github.com/openai/symphony/blob/main/SPEC.md) | 11798 | F03404 | non-negotiable | false | 10 |
| R06808 | Sweep input — Agent Harness Engineering survey (openreview.net/pdf/f358711a95aaaf61fdeffd4ef3fc60fba9b8da57.pdf) | 11800 | F03405 | non-negotiable | false | 10 |
| R06809 | Strongest new confirmation came from Agent Harness Engineering survey PDF | 11804 | F03406 | non-negotiable | false | 10 |
| R06810 | Survey thesis — production reliability depends less on the raw model | 11804 | F03406 | non-negotiable | false | 10 |
| R06811 | Survey thesis — production reliability depends more on the agent harness around it | 11804 | F03406 | non-negotiable | false | 10 |
| R06812 | Survey defines 7 layers | 11804 | E0389 | non-negotiable | false | 10 |
| R06813 | Layer 1 — Execution environment | 11806 | F03407 | non-negotiable | false | 10 |
| R06814 | Layer 2 — Tool interface | 11807 | F03408 | non-negotiable | false | 10 |
| R06815 | Layer 3 — Context management | 11808 | F03409 | non-negotiable | false | 10 |
| R06816 | Layer 4 — Lifecycle / orchestration | 11809 | F03410 | non-negotiable | false | 10 |
| R06817 | Layer 5 — Observability | 11810 | F03411 | non-negotiable | false | 10 |
| R06818 | Layer 6 — Verification | 11811 | F03412 | non-negotiable | false | 10 |
| R06819 | Layer 7 — Governance | 11812 | F03413 | non-negotiable | false | 10 |
| R06820 | Maps almost one-to-one to our station | 11816 | E0390 | non-negotiable | false | 10 |
| R06821 | Execution → sandboxes | 11818 | F03414 | non-negotiable | false | 10 |
| R06822 | Execution → VM | 11818 | F03414 | non-negotiable | false | 10 |
| R06823 | Execution → REPL | 11818 | F03414 | non-negotiable | false | 10 |
| R06824 | Execution → ZFS workspaces | 11818 | F03414 | non-negotiable | false | 10 |
| R06825 | Tool interface → MCP | 11819 | F03415 | non-negotiable | false | 10 |
| R06826 | Tool interface → Claude Code | 11819 | F03415 | non-negotiable | false | 10 |
| R06827 | Tool interface → OpenCode | 11819 | F03415 | non-negotiable | false | 10 |
| R06828 | Tool interface → Cline | 11819 | F03415 | non-negotiable | false | 10 |
| R06829 | Tool interface → gateway | 11819 | F03415 | non-negotiable | false | 10 |
| R06830 | Context → memory OS | 11820 | F03416 | non-negotiable | false | 10 |
| R06831 | Context → KV cache | 11820 | F03416 | non-negotiable | false | 10 |
| R06832 | Context → RLM | 11820 | F03416 | non-negotiable | false | 10 |
| R06833 | Context → MAP | 11820 | F03416 | non-negotiable | false | 10 |
| R06834 | Lifecycle → workflows | 11821 | F03417 | non-negotiable | false | 10 |
| R06835 | Lifecycle → Symphony-like orchestration | 11821 | F03417 | non-negotiable | false | 10 |
| R06836 | Lifecycle → profiles | 11821 | F03417 | non-negotiable | false | 10 |
| R06837 | Observability → traces | 11822 | F03418 | non-negotiable | false | 10 |
| R06838 | Observability → cost | 11822 | F03418 | non-negotiable | false | 10 |
| R06839 | Observability → DCGM | 11822 | F03418 | non-negotiable | false | 10 |
| R06840 | Observability → eBPF | 11822 | F03418 | non-negotiable | false | 10 |
| R06841 | Observability → evals | 11822 | F03418 | non-negotiable | false | 10 |
| R06842 | Verification → tests | 11823 | F03419 | non-negotiable | false | 10 |
| R06843 | Verification → TDD | 11823 | F03419 | non-negotiable | false | 10 |
| R06844 | Verification → PRM/RM | 11823 | F03419 | non-negotiable | false | 10 |
| R06845 | Verification → oracle | 11823 | F03419 | non-negotiable | false | 10 |
| R06846 | Verification → formal checks | 11823 | F03419 | non-negotiable | false | 10 |
| R06847 | Governance → policy bits | 11824 | F03420 | non-negotiable | false | 10 |
| R06848 | Governance → capabilities | 11824 | F03420 | non-negotiable | false | 10 |
| R06849 | Governance → secrets | 11824 | F03420 | non-negotiable | false | 10 |
| R06850 | Governance → human gates | 11824 | F03420 | non-negotiable | false | 10 |
| R06851 | "We were not wandering" | 11826 | F03421 | non-negotiable | false | 10 |
| R06852 | "Independently converged on what current research calls the harness layer" | 11828 | F03421 | non-negotiable | false | 10 |
| R06853 | MAP doctrine — "Do not act before understanding the environment" | 11836 | F03422 | non-negotiable | false | 10 |
| R06854 | MAP becomes — "MAP phase before ACT phase" | 11840 | F03423 | non-negotiable | false | 10 |
| R06855 | Methodology step — MAP | 11844 | F03424 | non-negotiable | false | 10 |
| R06856 | Methodology step — SPEC | 11844 | F03424 | non-negotiable | false | 10 |
| R06857 | Methodology step — TEST | 11844 | F03424 | non-negotiable | false | 10 |
| R06858 | Methodology step — ACT | 11844 | F03424 | non-negotiable | false | 10 |
| R06859 | Methodology step — EVAL | 11844 | F03424 | non-negotiable | false | 10 |
| R06860 | Methodology step — COMMIT | 11844 | F03424 | non-negotiable | false | 10 |
| R06861 | Methodology step — LEARN | 11844 | F03424 | non-negotiable | false | 10 |
| R06862 | MAP especially important for long-horizon coding | 11848 | F03425 | non-negotiable | false | 10 |
| R06863 | MAP especially important for GUI use | 11848 | F03426 | non-negotiable | false | 10 |
| R06864 | MAP especially important for repo work | 11848 | F03427 | non-negotiable | false | 10 |
| R06865 | MAP especially important for agent autonomy | 11848 | F03428 | non-negotiable | false | 10 |
| R06866 | Symphony — WORKFLOW.md as repo-owned contract | 11853 | F03429 | non-negotiable | false | 10 |
| R06867 | Symphony — per-issue isolated workspaces | 11854 | F03430 | non-negotiable | false | 10 |
| R06868 | Symphony — bounded concurrency | 11855 | F03431 | non-negotiable | false | 10 |
| R06869 | Symphony — retry/reconciliation | 11856 | F03432 | non-negotiable | false | 10 |
| R06870 | Symphony — structured observability | 11857 | F03433 | non-negotiable | false | 10 |
| R06871 | Symphony — dynamic workflow reload | 11858 | F03434 | non-negotiable | false | 10 |
| R06872 | Symphony is narrower than your vision | 11860 | F03435 | non-negotiable | false | 10 |
| R06873 | Symphony is issue-to-agent orchestration | 11860 | F03435 | non-negotiable | false | 10 |
| R06874 | System should generalize it into "workflow contracts for any intelligence run" | 11862 | F03436 | non-negotiable | false | 10 |
| R06875 | Big takeaway — "Workflow policy belongs in the repo/environment, versioned beside the work" | 11864 | F03437 | non-negotiable | false | 10 |
| R06876 | "That fits your Spec/TDD/SDLC world beautifully" | 11864 | F03438 | non-negotiable | false | 10 |
| R06877 | LiteLLM Agent Platform — sandboxed agent sessions | 11868 | F03439 | non-negotiable | false | 10 |
| R06878 | LiteLLM — persistent environments | 11869 | F03440 | non-negotiable | false | 10 |
| R06879 | LiteLLM — vault proxy with stub credentials | 11870 | F03441 | non-negotiable | false | 10 |
| R06880 | LiteLLM — Claude Code harness support | 11871 | F03442 | non-negotiable | false | 10 |
| R06881 | LiteLLM — Codex harness support | 11871 | F03442 | non-negotiable | false | 10 |
| R06882 | LiteLLM — OpenCode harness support | 11871 | F03442 | non-negotiable | false | 10 |
| R06883 | Vault sidecar — agent sees fake/stub key | 11874 | F03443 | non-negotiable | false | 10 |
| R06884 | Vault sidecar — sidecar swaps real key at wire boundary | 11875 | F03444 | non-negotiable | false | 10 |
| R06885 | Vault sidecar — real secret never enters agent process | 11876 | F03445 | non-negotiable | false | 10 |
| R06886 | Station — Claude-first gateway | 11879 | F03446 | non-negotiable | false | 10 |
| R06887 | Station — real keys protected | 11879 | F03447 | non-negotiable | false | 10 |
| R06888 | Station — cost ledger central | 11880 | F03448 | non-negotiable | false | 10 |
| R06889 | Station — model routing central | 11880 | F03449 | non-negotiable | false | 10 |
| R06890 | Station — sandbox session observable | 11881 | F03450 | non-negotiable | false | 10 |
| R06891 | Fast BLT — memory bandwidth is a frontier bottleneck | 11885 | F03451 | non-negotiable | false | 10 |
| R06892 | Fast BLT — byte-level models can become practical through diffusion/speculative generation | 11886 | F03452 | non-negotiable | false | 10 |
| R06893 | Fast BLT — parallel byte generation matters | 11887 | F03453 | non-negotiable | false | 10 |
| R06894 | Fast BLT not immediate station infrastructure unless serving code matures | 11890 | E0394 | non-negotiable | false | 10 |
| R06895 | Deeper principle — reduce forward passes | 11893 | F03454 | non-negotiable | false | 10 |
| R06896 | Deeper principle — reduce memory bandwidth waste | 11894 | F03455 | non-negotiable | false | 10 |
| R06897 | Deeper principle — speculate cheaply | 11895 | F03456 | non-negotiable | false | 10 |
| R06898 | Deeper principle — verify carefully | 11896 | F03457 | non-negotiable | false | 10 |
| R06899 | "Exactly the Blackwell + 4090 + AVX-512 architecture" | 11900 | F03458 | non-negotiable | false | 10 |
| R06900 | LLM compression — "model portfolio must be measured, not guessed" | 11904 | F03459 | non-negotiable | false | 10 |
| R06901 | Model-lab slot — BF16 baseline | 11908 | F03460 | non-negotiable | false | 10 |
| R06902 | Model-lab slot — FP8 | 11909 | F03461 | non-negotiable | false | 10 |
| R06903 | Model-lab slot — GPTQ | 11910 | F03462 | non-negotiable | false | 10 |
| R06904 | Model-lab slot — SmoothQuant | 11911 | F03463 | non-negotiable | false | 10 |
| R06905 | Model-lab slot — AWQ | 11912 | F03464 | non-negotiable | false | 10 |
| R06906 | Model-lab slot — NVFP4/MXFP4 when stable | 11913 | F03465 | non-negotiable | false | 10 |
| R06907 | Model-lab slot — KV quantization | 11914 | F03466 | non-negotiable | false | 10 |
| R06908 | Every model earns a profile slot through evals | 11916 | F03467 | non-negotiable | false | 10 |
| R06909 | Routing — cheap local classification before expensive model routing (NadirClaw lesson) | 11918 | E0395 | non-negotiable | false | 10 |
| R06910 | Router — prompt classifier | 11918 | F03468 | non-negotiable | false | 10 |
| R06911 | Router — privacy classifier | 11918 | F03469 | non-negotiable | false | 10 |
| R06912 | Router — risk classifier | 11918 | F03470 | non-negotiable | false | 10 |
| R06913 | Router — difficulty estimator | 11919 | F03471 | non-negotiable | false | 10 |
| R06914 | Router — domain classifier | 11919 | F03472 | non-negotiable | false | 10 |
| R06915 | Router — profile selector | 11919 | F03473 | non-negotiable | false | 10 |
| R06916 | This becomes the adaptive Goldilocks router | 11921 | F03474 | non-negotiable | false | 10 |
| R06917 | Deferred pass — MAP PDF (exact map representation) | 11929 | F03475 | non-negotiable | false | 10 |
| R06918 | Deferred pass — MAP PDF (benchmark setup) | 11929 | F03475 | non-negotiable | false | 10 |
| R06919 | Deferred pass — MAP PDF (what "map" should contain) | 11929 | F03475 | non-negotiable | false | 10 |
| R06920 | Deferred pass — Fast BLT PDF (BLT-D / BLT-S / BLT-DV practical serving target) | 11932 | F03476 | non-negotiable | false | 10 |
| R06921 | Deferred pass — LiteLLM docs (sandbox architecture) | 11935 | F03477 | non-negotiable | false | 10 |
| R06922 | Deferred pass — LiteLLM docs (vault proxy details) | 11935 | F03477 | non-negotiable | false | 10 |
| R06923 | Deferred pass — LiteLLM docs (compatibility boundaries) | 11935 | F03477 | non-negotiable | false | 10 |
| R06924 | Deferred pass — Symphony SPEC (exact WORKFLOW.md schema we could adapt) | 11938 | F03478 | non-negotiable | false | 10 |
| R06925 | Deferred pass — Symphony SPEC → PROFILE/SPEC contract | 11938 | F03478 | non-negotiable | false | 10 |
| R06926 | Deferred pass — Agent Harness survey (full taxonomy) | 11941 | F03479 | non-negotiable | false | 10 |
| R06927 | Deferred pass — Agent Harness survey (project list) | 11941 | F03479 | non-negotiable | false | 10 |
| R06928 | Deferred pass — Claude Code integration (Anthropic-compatible gateway behavior) | 11944 | F03480 | non-negotiable | false | 10 |
| R06929 | Deferred pass — Claude Code integration (hooks) | 11944 | F03480 | non-negotiable | false | 10 |
| R06930 | Deferred pass — Claude Code integration (MCP) | 11944 | F03480 | non-negotiable | false | 10 |
| R06931 | Deferred pass — Claude Code integration (subagents) | 11944 | F03480 | non-negotiable | false | 10 |
| R06932 | Deferred pass — Hardware stack (MIG profile behavior on RTX PRO 6000) | 11990 | F03481 | non-negotiable | false | 10 |
| R06933 | Deferred pass — Hardware stack (VFIO topology) | 11990 | F03481 | non-negotiable | false | 10 |
| R06934 | Deferred pass — Hardware stack (ZFS layout) | 11990 | F03481 | non-negotiable | false | 10 |
| R06935 | Deferred pass — Hardware stack (AVX-512 prototype) | 11990 | F03481 | non-negotiable | false | 10 |
| R06936 | "We extracted the architecture, not yet the full implementation bill of materials" | 11991 | F03482 | non-negotiable | false | 10 |
| R06937 | Contract — SPEC.md | 11995 | F03483 | non-negotiable | false | 10 |
| R06938 | SPEC.md says "What should be true" | 11996 | F03484 | non-negotiable | false | 10 |
| R06939 | Contract — WORKFLOW.md | 11998 | M00688 | non-negotiable | false | 10 |
| R06940 | WORKFLOW.md says "How agents should behave in this repo/environment" | 11999 | M00688 | non-negotiable | false | 10 |
| R06941 | Contract — PROFILES.yaml | 12001 | M00689 | non-negotiable | false | 10 |
| R06942 | PROFILES.yaml says "How much intelligence, risk, cost, autonomy, and verification to spend" | 12002 | M00689 | non-negotiable | false | 10 |
| R06943 | Contract — EVALS.yaml | 12004 | M00690 | non-negotiable | false | 10 |
| R06944 | EVALS.yaml says "How success is measured" | 12005 | M00690 | non-negotiable | false | 10 |
| R06945 | Contract — MAP.json | 12007 | M00691 | non-negotiable | false | 10 |
| R06946 | MAP.json says "What the system knows about the environment before acting" | 12008 | M00691 | non-negotiable | false | 10 |
| R06947 | Contract — MODEL_REGISTRY.yaml | 12010 | M00692 | non-negotiable | false | 10 |
| R06948 | MODEL_REGISTRY.yaml says "Which models exist, where they run, what they are good at" | 12011 | M00692 | non-negotiable | false | 10 |
| R06949 | Contract — POLICY.yaml | 12013 | M00693 | non-negotiable | false | 10 |
| R06950 | POLICY.yaml says "What actions are allowed, gated, sandboxed, or forbidden" | 12014 | M00693 | non-negotiable | false | 10 |
| R06951 | Runtime compile pipeline — Task | 12017 | M00694 | non-negotiable | false | 10 |
| R06952 | Runtime compile pipeline — MAP | 12018 | M00694 | non-negotiable | false | 10 |
| R06953 | Runtime compile pipeline — SPEC/TDD plan | 12019 | M00694 | non-negotiable | false | 10 |
| R06954 | Runtime compile pipeline — workflow DAG | 12020 | M00694 | non-negotiable | false | 10 |
| R06955 | Runtime compile pipeline — model/tool routing | 12021 | M00694 | non-negotiable | false | 10 |
| R06956 | Runtime compile pipeline — sandbox execution | 12022 | M00694 | non-negotiable | false | 10 |
| R06957 | Runtime compile pipeline — tests/evals | 12023 | M00694 | non-negotiable | false | 10 |
| R06958 | Runtime compile pipeline — oracle/human review | 12024 | M00694 | non-negotiable | false | 10 |
| R06959 | Runtime compile pipeline — commit | 12025 | M00694 | non-negotiable | false | 10 |
| R06960 | Runtime compile pipeline — memory update | 12026 | M00694 | non-negotiable | false | 10 |
| R06961 | Hardware overlay — Ryzen 9900X AVX-512 (policy masks / branch routing / memory bitsets / workflow scheduling) | 12031–12033 | M00695 | non-negotiable | false | 10 |
| R06962 | Hardware overlay — RTX PRO 6000 Blackwell (oracle / final synthesis / long-context verifier / large model lab) | 12035–12037 | M00695 | non-negotiable | false | 10 |
| R06963 | Hardware overlay — RTX 4090 (scout / SLM swarm / draft-speculation / embeddings / perception / sandbox model) | 12039–12041 | M00695 | non-negotiable | false | 10 |
| R06964 | Hardware overlay — 256GB RAM (memory graph / hot indexes / context arenas / ZFS ARC) | 12043–12045 | M00695 | non-negotiable | false | 10 |
| R06965 | Hardware overlay — NVMe/ZFS (replay / snapshots / workspaces / eval artifacts / model cache) | 12047–12049 | M00695 | non-negotiable | false | 10 |
| R06966 | Hardware overlay — 10GbE / 2.5GbE (data plane vs management plane) | 12051–12053 | M00695 | non-negotiable | false | 10 |
| R06967 | North Star NOT — "one best model / one best workflow / one best agent framework" | 12057–12059 | M00696 | non-negotiable | false | 10 |
| R06968 | North Star IS — "a programmable intelligence harness" | 12063 | M00696 | non-negotiable | false | 10 |
| R06969 | Programmable intelligence harness — SMART routing / adaptive profiles / spec+TDD contracts / agent evals / model portfolio / hardware-aware scheduling / safe sandboxes / cost tracking / memory and replay | 12067–12079 | M00696 | non-negotiable | false | 10 |
| R06970 | Composite — M041 (10 epics / 17 modules / 85 features / 170 reqs) catalogs the 7-layer agent harness + 7 canonical contracts (SPEC/WORKFLOW/PROFILES/EVALS/MAP/MODEL_REGISTRY/POLICY) + 10-step runtime compile pipeline + 6-tier hardware overlay + 9-property programmable intelligence harness; next artifact is Jean Station Architecture Spec v0.1 | 11790–12081 | E0388-E0397 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: 7 harness layers + 7 station-mappings + 6-step MAP methodology + 7-step ACT-onward methodology + 6 Symphony takeaways + 4 LiteLLM inputs + 3 vault-sidecar steps + 5 station-translation properties + 7 model-lab slots + 6 router classifiers + 7 deferred passes + 7 canonical contracts + 10 runtime-pipeline steps + 6-tier hardware overlay + 9-property programmable harness
- Source range 11790–12094 yields 304 lines; 170 R-rows represent ~56% line-coverage at the verbatim-citation level (commentary lines + web-search log lines excluded)
- Project boundary — M041 is sovereign-os runtime/contracts/harness scope; IPS-specific contract enforcement (selfdef) addressed in MS019 + MS013 charter (27-SDD ledger maps to SPEC.md-equivalent doctrine)

## Cross-references

- Adjacent dump-range milestones: M040 hyper features (11410–11790) / M042 choice architecture (next; dump 12094–12614)
- Plane integration — M041 7-contract architecture overlays ALL prior planes (M025 Cognitive Compiler compiles SPEC+WORKFLOW+PROFILES+POLICY into DAG; M026 SLM swarm + M027 Value Plane consume MODEL_REGISTRY; M028 Memory OS implements Context layer; M029 Computer-Use Plane + M030 World Model implement MAP.json; M031 Symbolic Planning Plane consumes SPEC.md+POLICY.yaml; M032 Cloud Expert Plane reads MODEL_REGISTRY; M033 Compatibility Gateway + M034 Anthropic-first Gateway are the Tool-interface layer; M035 Frontier inference-time intelligence + M036 MAP-then-act + M037 Spec/TDD evidence-driven autonomy are the Verification+Lifecycle+Governance layers; M038 Hardware-aware AIDLC + M039 AVX-512 cortex hot path + M040 Hyper features all consume HARDWARE_PROFILES via PROFILES.yaml)
- 7 canonical contracts: SPEC.md / WORKFLOW.md / PROFILES.yaml / EVALS.yaml / MAP.json / MODEL_REGISTRY.yaml / POLICY.yaml
- 7 harness layers: Execution / Tool interface / Context / Lifecycle / Observability / Verification / Governance
- 10-step runtime compile pipeline: Task → MAP → SPEC/TDD plan → workflow DAG → model/tool routing → sandbox execution → tests/evals → oracle/human review → commit → memory update
- Selfdef integration — selfdef MS013 27-SDD ledger is the IPS-side SPEC.md / MS020 L1-L5 layered harness is the IPS-side WORKFLOW.md+EVALS.yaml / MS017 agent-guard is the IPS-side POLICY.yaml subset / MS019 threat model is the IPS-side adversary input to POLICY.yaml
- Operator references: openreview.net Agent Harness survey PDF / arxiv.org/abs/2605.13037 MAP / github.com/openai/symphony/blob/main/SPEC.md / docs.litellm-agent-platform.ai / arxiv.org/abs/2605.08044 Fast BLT / NadirClaw routing / llmcompressor
