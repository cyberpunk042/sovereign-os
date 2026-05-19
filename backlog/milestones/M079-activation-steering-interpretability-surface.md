# M079 — Activation steering interpretability surface (white-box vs black-box intervention class)

**Parent**: sovereign-os runtime — interpretability + safety surface (layered onto M049 observability + M048 Eval-Value + selfdef MS039 authority levels + MS042 tool authority + MS044 Guardian)
**Source**: arXiv 2604.09839 — "Steered LLM Activations are Non-Surjective" — Aayush Mishra, Daniel Khashabi, Anqi Liu (2026-05-07)
**Provenance**: Ingested via HF MCP `paper_search` 2026-05-19 (`hf.co/papers/2604.09839`)

## Doctrinal anchors (verbatim from arXiv 2604.09839)

> "Activation steering is a popular white-box control technique that modifies model activations to elicit an abstract change in its behavior. It has also become a standard tool in interpretability (e.g., probing truthfulness, or translating activations into human-readable explanations) and safety research (e.g., jailbreakability)."

> "However, it is unclear whether steered behavior is realizable by any textual prompt. In this work, we cast this question as a surjectivity problem: for a fixed model, does every steered activation admit a preimage under the model's natural forward pass?"

> "Under practical assumptions, we prove that activation steering pushes the residual stream off the manifold of states reachable from discrete prompts. Almost surely, no prompt can reproduce the same internal behavior induced by steering."

> "We also illustrate this finding empirically across three widely used LLMs."

> "Our results establish a formal separation between white-box steerability and black-box prompting. We therefore caution against interpreting the ease and success of activation steering as evidence of prompt-based interpretability or vulnerability, and argue for evaluation protocols that explicitly decouple white-box and black-box interventions."

## Catalog positioning

M049 observability + M048 Eval-Value + selfdef MS039 authority levels + MS042 tool authority describe runtime behavior, evaluation, authority gates, and tool-call declarations — but **NO explicit interpretability/intervention-class surface**. M079 adds a formal **intervention-class taxonomy** (black-box prompt / white-box activation-steer / white-box weight-edit) that the runtime tracks per interaction. The arXiv 2604.09839 formal proof anchors **eval-protocol separation** as non-negotiable: a benchmark that proves a model is jailbreakable via activation steering proves NOTHING about prompt-based vulnerability.

## Epics (E0758-E0767)

| epic | name | source |
|---|---|---|
| E0758 | Intervention class taxonomy — black-box prompt vs white-box activation-steer vs white-box weight-edit | arXiv 2604.09839 |
| E0759 | Surjectivity formalism — activation steering pushes residual stream off prompt-reachable manifold | arXiv 2604.09839 |
| E0760 | Formal proof preservation — "almost surely, no prompt can reproduce" | arXiv 2604.09839 |
| E0761 | Empirical validation — across 3 widely-used LLMs | arXiv 2604.09839 |
| E0762 | Eval-protocol separation — decouple white-box and black-box benchmarks | arXiv 2604.09839 |
| E0763 | Interpretability use-case bound — probing truthfulness via steering ≠ prompt-based interpretability | arXiv 2604.09839 |
| E0764 | Safety use-case bound — activation-steering jailbreak ≠ prompt-based vulnerability | arXiv 2604.09839 |
| E0765 | Guardian (selfdef MS044) integration — distinguish WB-attack vs BB-attack in policy YAML | cross-ref selfdef MS044 |
| E0766 | Tool authority (selfdef MS042) integration — new declaration field `interpretability_intervention_class` | cross-ref selfdef MS042 |
| E0767 | Authority levels (selfdef MS039) integration — WB activation-steer = L4-tier authority (bounded execution) | cross-ref selfdef MS039 |

## Modules (M01309-M01325)

| module | name | source |
|---|---|---|
| M01309 | sovereign-intervention-class-taxonomy | arXiv 2604.09839 |
| M01310 | sovereign-surjectivity-formal-proof-recorder | arXiv 2604.09839 |
| M01311 | sovereign-residual-stream-manifold-tracker | arXiv 2604.09839 |
| M01312 | sovereign-prompt-reachable-set-bounder | arXiv 2604.09839 |
| M01313 | sovereign-activation-steer-detector | arXiv 2604.09839 |
| M01314 | sovereign-weight-edit-detector | arXiv 2604.09839 + architecture |
| M01315 | sovereign-eval-protocol-wb-bb-separator | arXiv 2604.09839 |
| M01316 | sovereign-interpretability-claim-validator | arXiv 2604.09839 |
| M01317 | sovereign-jailbreak-classifier (WB vs BB) | arXiv 2604.09839 |
| M01318 | sovereign-intervention-class-typed-mirror | cross-ref selfdef MS007 |
| M01319 | sovereign-intervention-class-event-emitter | cross-ref M049 + selfdef MS026 |
| M01320 | sovereign-intervention-class-replay-validator | cross-ref selfdef MS009 |
| M01321 | sovereign-intervention-class-cli-subcommand-set | cross-ref selfdef MS043 |
| M01322 | sovereign-intervention-class-dashboard-binding | cross-ref M060 |
| M01323 | sovereign-intervention-class-guardian-policy-bridge | cross-ref selfdef MS044 |
| M01324 | sovereign-intervention-class-tool-authority-bridge | cross-ref selfdef MS042 |
| M01325 | sovereign-intervention-class-authority-fsm-bridge | cross-ref selfdef MS039 |

## Features (F06546-F06630)

| feature | name | source |
|---|---|---|
| F06546 | Doctrinal — activation steering is white-box control technique | arXiv 2604.09839 |
| F06547 | Doctrinal — modifies model activations to elicit abstract behavior change | arXiv 2604.09839 |
| F06548 | Doctrinal — standard tool in interpretability research | arXiv 2604.09839 |
| F06549 | Doctrinal — interpretability use cases: probing truthfulness | arXiv 2604.09839 |
| F06550 | Doctrinal — interpretability use cases: translating activations to human-readable explanations | arXiv 2604.09839 |
| F06551 | Doctrinal — standard tool in safety research | arXiv 2604.09839 |
| F06552 | Doctrinal — safety use cases: jailbreakability | arXiv 2604.09839 |
| F06553 | Surjectivity question — does every steered activation admit a preimage under forward pass? | arXiv 2604.09839 |
| F06554 | Surjectivity formalism — for fixed model, does prompt P exist such that forward(P) reaches activation a*? | arXiv 2604.09839 |
| F06555 | Formal proof — under practical assumptions, activation steering pushes residual stream off manifold | arXiv 2604.09839 |
| F06556 | Formal proof — "almost surely, no prompt can reproduce the same internal behavior induced by steering" | arXiv 2604.09839 |
| F06557 | Empirical proof — illustrated across 3 widely-used LLMs | arXiv 2604.09839 |
| F06558 | Implication — formal separation between white-box steerability and black-box prompting | arXiv 2604.09839 |
| F06559 | Implication — eval protocols must explicitly decouple WB and BB interventions | arXiv 2604.09839 |
| F06560 | Caution — ease of activation steering ≠ prompt-based interpretability | arXiv 2604.09839 |
| F06561 | Caution — success of activation steering ≠ prompt-based vulnerability | arXiv 2604.09839 |
| F06562 | Intervention class taxonomy — 4 classes (None / BB-prompt / WB-activation-steer / WB-weight-edit) | arXiv 2604.09839 + architecture |
| F06563 | Intervention class — None: standard inference, no intervention | architecture |
| F06564 | Intervention class — BB-prompt: prompt-engineered behavior change (black-box) | arXiv 2604.09839 |
| F06565 | Intervention class — WB-activation-steer: residual-stream modification at inference time | arXiv 2604.09839 |
| F06566 | Intervention class — WB-weight-edit: model weights modified (e.g. LoRA, ROME, KE) | architecture + arXiv 2604.09839 |
| F06567 | Intervention class — every model invocation carries class tag | architecture |
| F06568 | Intervention class — class tag emitted in M049 trace span | cross-ref M049 |
| F06569 | Intervention class — class tag included in OCSF event | cross-ref selfdef MS026 |
| F06570 | Intervention class — class tag signed via MS003 | cross-ref selfdef MS003 |
| F06571 | Residual stream tracker — captures per-layer activation digests | arXiv 2604.09839 |
| F06572 | Residual stream tracker — detects out-of-manifold drift | arXiv 2604.09839 |
| F06573 | Residual stream tracker — emits warning when drift exceeds threshold (potential undetected steering) | architecture + arXiv 2604.09839 |
| F06574 | Prompt-reachable set bounder — estimates manifold boundary via sampled-prompt forward passes | arXiv 2604.09839 + architecture |
| F06575 | Prompt-reachable set bounder — emits manifold-digest per model checkpoint | architecture |
| F06576 | Activation-steer detector — hook on residual stream intervention sites | arXiv 2604.09839 |
| F06577 | Activation-steer detector — emits OCSF Audit Activity 1003 per detection | cross-ref selfdef MS026 |
| F06578 | Activation-steer detector — composes with M058 hardware-aware scheduler (Blackwell oracle) | cross-ref M058 |
| F06579 | Weight-edit detector — hash chain over model weights at load + checkpoint | architecture + cross-ref selfdef MS003 |
| F06580 | Weight-edit detector — detects unauthorized weight modification | cross-ref selfdef MS003 + MS041 |
| F06581 | Weight-edit detector — composes with M046 LoRA Foundry (legitimate adapter promotion) | cross-ref M046 |
| F06582 | Eval-protocol separator — benchmark tagged with intervention class at run time | arXiv 2604.09839 |
| F06583 | Eval-protocol separator — WB benchmarks NOT averaged with BB benchmarks | arXiv 2604.09839 |
| F06584 | Eval-protocol separator — refuses to certify model "safe vs jailbreak" without class-disaggregation | arXiv 2604.09839 |
| F06585 | Eval-protocol separator — composes with M048 Eval-Value module + M078 HölderPO benchmark runners | cross-ref M048 + M078 |
| F06586 | Interpretability claim validator — checks WB-steering-derived claims do NOT generalize to BB prompts | arXiv 2604.09839 |
| F06587 | Interpretability claim validator — emits OCSF Detection 2004 on category-confused claim | cross-ref selfdef MS026 |
| F06588 | Jailbreak classifier — distinguishes WB vs BB jailbreak attempts | arXiv 2604.09839 + cross-ref selfdef MS044 |
| F06589 | Jailbreak classifier — WB jailbreak ≠ prompt-based vulnerability (per arXiv 2604.09839) | arXiv 2604.09839 |
| F06590 | Jailbreak classifier — emits OCSF Detection 2004 on either class (severity differs) | cross-ref selfdef MS026 |
| F06591 | Jailbreak classifier — composes with selfdef MS044 Guardian Tetragon eBPF policies | cross-ref selfdef MS044 |
| F06592 | Guardian policy bridge — `/etc/tetragon/tracing-policies/intervention-class.yaml` | cross-ref selfdef MS044 |
| F06593 | Guardian policy bridge — policy detects unauthorized activation-steer hooks | cross-ref selfdef MS044 |
| F06594 | Guardian policy bridge — policy detects unauthorized weight-edit syscalls | cross-ref selfdef MS044 |
| F06595 | Tool authority bridge — new declaration field `interpretability_intervention_class` | cross-ref selfdef MS042 |
| F06596 | Tool authority bridge — tools that perform WB steering MUST declare class WB-activation-steer | arXiv 2604.09839 |
| F06597 | Tool authority bridge — declaration-vs-observed mismatch (declared BB, observed WB) triggers MS042 block+quarantine+trace | cross-ref selfdef MS042 |
| F06598 | Tool authority bridge — composes with selfdef MS042 4-severity classifier | cross-ref selfdef MS042 |
| F06599 | Authority FSM bridge — WB activation-steer = L4 Execute-bounded with operator approval | cross-ref selfdef MS039 |
| F06600 | Authority FSM bridge — WB weight-edit = L5 Commit (durable change) | cross-ref selfdef MS039 + MS041 |
| F06601 | Authority FSM bridge — BB prompt = L0 Observe / L1 Suggest depending on policy | cross-ref selfdef MS039 |
| F06602 | Authority FSM bridge — class transitions emit M049 trace | cross-ref M049 |
| F06603 | Authority FSM bridge — operator can promote BB-prompt-only model to allow WB steering via signed promotion | cross-ref selfdef MS003 + MS039 |
| F06604 | Typed mirror — sovereign-intervention-class-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F06605 | Typed mirror — InterventionClass enum (None / BlackBoxPrompt / WhiteBoxActivationSteer / WhiteBoxWeightEdit) | cross-ref selfdef MS007 |
| F06606 | Typed mirror — InterventionContext struct {class, hook_layers, magnitude_digest, signed_authorization} | cross-ref selfdef MS007 |
| F06607 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F06608 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F06609 | Event emitter — every intervention emits M049 13-field trace | cross-ref M049 |
| F06610 | Event emitter — span includes intervention class + hook sites + magnitude digest | cross-ref M049 |
| F06611 | Event emitter — emits OCSF Audit Activity 1003 per intervention | cross-ref selfdef MS026 |
| F06612 | Event emitter — unauthorized intervention emits OCSF Detection 2004 | cross-ref selfdef MS026 |
| F06613 | Event emitter — span deterministic for MS009 replay | cross-ref selfdef MS009 |
| F06614 | Replay validator — verifies historical intervention chain | cross-ref selfdef MS009 |
| F06615 | Replay validator — detects category-confused eval claims | cross-ref selfdef MS009 + arXiv 2604.09839 |
| F06616 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 |
| F06617 | Replay validator — runs daily | cross-ref selfdef MS009 |
| F06618 | Dashboard — D-05 traces surfaces intervention class per trace | cross-ref M060 |
| F06619 | Dashboard — D-06 pending approvals surfaces WB steering approval requests | cross-ref M060 |
| F06620 | Dashboard — D-10 eval history shows WB vs BB benchmark disaggregation | cross-ref M060 |
| F06621 | Dashboard — D-17 quarantine surfaces declaration-vs-observed intervention mismatches | cross-ref M060 + selfdef MS042 |
| F06622 | Dashboard — D-18 trust scores incorporates intervention class history | cross-ref M060 + selfdef MS042 |
| F06623 | CLI — `sovereign intervention status` returns current intervention class taxonomy state | cross-ref selfdef MS043 |
| F06624 | CLI — `sovereign intervention scan <model>` checks for unauthorized WB modifications | architecture + cross-ref selfdef MS003 |
| F06625 | CLI — `sovereign intervention authorize <class> --ttl <sec>` operator-grants intervention authority | cross-ref selfdef MS003 + MS038 |
| F06626 | CLI — `sovereign intervention history --class <name>` returns prior interventions | architecture |
| F06627 | CLI — `sovereign intervention verify-eval <result>` verifies WB vs BB disaggregation | architecture + arXiv 2604.09839 |
| F06628 | CLI — all intervention subcommands emit M049 trace | cross-ref M049 |
| F06629 | CLI — `--json` flag returns structured output | architecture |
| F06630 | Closing — M079 covers arXiv 2604.09839 verbatim; M080 HRM architectural class next | arXiv 2604.09839 |

## Requirements (R13091-R13260)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R13091 | Doctrinal — activation steering is white-box control technique | arXiv 2604.09839 | F06546 | non-negotiable | false | 10 |
| R13092 | Doctrinal — modifies model activations to elicit abstract behavior change | arXiv 2604.09839 | F06547 | non-negotiable | false | 10 |
| R13093 | Doctrinal — standard interpretability tool (probing truthfulness, translating activations) | arXiv 2604.09839 | F06548 | non-negotiable | false | 10 |
| R13094 | Doctrinal — standard safety research tool (jailbreakability) | arXiv 2604.09839 | F06551 | non-negotiable | false | 10 |
| R13095 | Doctrinal — surjectivity question: does every steered activation admit a prompt preimage? | arXiv 2604.09839 | F06553 | non-negotiable | false | 10 |
| R13096 | Doctrinal — FORMAL PROOF: activation steering pushes residual stream off manifold of states reachable from discrete prompts | arXiv 2604.09839 | F06555 | non-negotiable | false | 10 |
| R13097 | Doctrinal — "almost surely, no prompt can reproduce the same internal behavior induced by steering" verbatim | arXiv 2604.09839 | F06556 | non-negotiable | false | 10 |
| R13098 | Doctrinal — empirical validation across 3 widely-used LLMs | arXiv 2604.09839 | F06557 | non-negotiable | false | 10 |
| R13099 | Doctrinal — formal separation between white-box steerability and black-box prompting | arXiv 2604.09839 | F06558 | non-negotiable | false | 10 |
| R13100 | Doctrinal — eval protocols must explicitly decouple WB and BB interventions | arXiv 2604.09839 | F06559 | non-negotiable | false | 10 |
| R13101 | Doctrinal — ease of activation steering ≠ prompt-based interpretability | arXiv 2604.09839 | F06560 | non-negotiable | false | 10 |
| R13102 | Doctrinal — success of activation steering ≠ prompt-based vulnerability | arXiv 2604.09839 | F06561 | non-negotiable | false | 10 |
| R13103 | Doctrinal — operator standing direction "you cannot invent crap" upheld (paper formal-proof-based) | operator standing direction | F06555 | non-negotiable | false | 10 |
| R13104 | Taxonomy — 4 intervention classes total (None / BB-prompt / WB-activation-steer / WB-weight-edit) | arXiv 2604.09839 + architecture | F06562 | non-negotiable | false | 10 |
| R13105 | Taxonomy — None: standard inference, no intervention | architecture | F06563 | non-negotiable | false | 10 |
| R13106 | Taxonomy — BB-prompt: prompt-engineered behavior change | arXiv 2604.09839 | F06564 | non-negotiable | false | 10 |
| R13107 | Taxonomy — WB-activation-steer: residual-stream modification at inference | arXiv 2604.09839 | F06565 | non-negotiable | false | 10 |
| R13108 | Taxonomy — WB-weight-edit: model weights modified (LoRA / ROME / KE / direct edit) | architecture + arXiv 2604.09839 | F06566 | non-negotiable | false | 10 |
| R13109 | Taxonomy — every model invocation carries class tag | architecture | F06567 | non-negotiable | false | 10 |
| R13110 | Taxonomy — class tag emitted in M049 13-field span | cross-ref M049 | F06568 | non-negotiable | false | 10 |
| R13111 | Taxonomy — class tag included in OCSF event | cross-ref selfdef MS026 | F06569 | non-negotiable | false | 10 |
| R13112 | Taxonomy — class tag signed via MS003 | cross-ref selfdef MS003 | F06570 | non-negotiable | false | 10 |
| R13113 | Taxonomy — class never auto-promoted (operator decision only) | operator standing direction | F06603 | non-negotiable | false | 10 |
| R13114 | Residual stream — captures per-layer activation digests | arXiv 2604.09839 | F06571 | non-negotiable | false | 10 |
| R13115 | Residual stream — detects out-of-manifold drift | arXiv 2604.09839 | F06572 | non-negotiable | false | 10 |
| R13116 | Residual stream — emits warning when drift exceeds threshold | architecture + arXiv 2604.09839 | F06573 | non-negotiable | false | 10 |
| R13117 | Residual stream — drift signature signed via MS003 | cross-ref selfdef MS003 | F06571 | non-negotiable | false | 10 |
| R13118 | Residual stream — drift events retained in MS009 chain | cross-ref selfdef MS009 | F06571 | non-negotiable | false | 10 |
| R13119 | Prompt-reachable set — estimated via sampled-prompt forward passes per model checkpoint | arXiv 2604.09839 + architecture | F06574 | non-negotiable | false | 10 |
| R13120 | Prompt-reachable set — emits manifold digest signed via MS003 | cross-ref selfdef MS003 | F06575 | non-negotiable | false | 10 |
| R13121 | Prompt-reachable set — composes with M048 Eval-Value module sampling | cross-ref M048 | F06574 | non-negotiable | false | 10 |
| R13122 | Activation-steer detector — hooks residual stream intervention sites | arXiv 2604.09839 | F06576 | non-negotiable | false | 10 |
| R13123 | Activation-steer detector — emits OCSF Audit Activity 1003 per detection | cross-ref selfdef MS026 | F06577 | non-negotiable | false | 10 |
| R13124 | Activation-steer detector — composes with M058 hardware-aware scheduler | cross-ref M058 | F06578 | non-negotiable | false | 10 |
| R13125 | Activation-steer detector — magnitude digest signed via MS003 | cross-ref selfdef MS003 | F06576 | non-negotiable | false | 10 |
| R13126 | Weight-edit detector — hash chain over model weights at load | architecture + cross-ref selfdef MS003 | F06579 | non-negotiable | false | 10 |
| R13127 | Weight-edit detector — hash chain over model weights at every checkpoint | architecture + cross-ref selfdef MS003 | F06579 | non-negotiable | false | 10 |
| R13128 | Weight-edit detector — detects unauthorized weight modification | cross-ref selfdef MS003 + MS041 | F06580 | non-negotiable | false | 10 |
| R13129 | Weight-edit detector — composes with M046 LoRA Foundry (legitimate adapter promotion) | cross-ref M046 | F06581 | non-negotiable | false | 10 |
| R13130 | Weight-edit detector — composes with M077 NVFP4 (quantization-aware diff) | cross-ref M077 | F06579 | non-negotiable | false | 10 |
| R13131 | Eval-protocol separator — benchmark tagged with intervention class at run time | arXiv 2604.09839 | F06582 | non-negotiable | false | 10 |
| R13132 | Eval-protocol separator — WB benchmarks NEVER averaged with BB benchmarks | arXiv 2604.09839 | F06583 | non-negotiable | false | 10 |
| R13133 | Eval-protocol separator — refuses to certify "safe vs jailbreak" without disaggregation | arXiv 2604.09839 | F06584 | non-negotiable | false | 10 |
| R13134 | Eval-protocol separator — composes with M048 Eval-Value module | cross-ref M048 | F06585 | non-negotiable | false | 10 |
| R13135 | Eval-protocol separator — composes with M078 HölderPO benchmark runners | cross-ref M078 | F06585 | non-negotiable | false | 10 |
| R13136 | Eval-protocol separator — surfaces disaggregation in D-10 eval history | cross-ref M060 | F06620 | non-negotiable | false | 10 |
| R13137 | Interpretability claim validator — checks WB-derived claims do NOT generalize to BB | arXiv 2604.09839 | F06586 | non-negotiable | false | 10 |
| R13138 | Interpretability claim validator — emits OCSF Detection 2004 on category-confused claim | cross-ref selfdef MS026 | F06587 | non-negotiable | false | 10 |
| R13139 | Interpretability claim validator — composes with M049 trace pipeline | cross-ref M049 | F06586 | non-negotiable | false | 10 |
| R13140 | Jailbreak classifier — distinguishes WB vs BB jailbreak | arXiv 2604.09839 + cross-ref selfdef MS044 | F06588 | non-negotiable | false | 10 |
| R13141 | Jailbreak classifier — WB jailbreak ≠ prompt-based vulnerability | arXiv 2604.09839 | F06589 | non-negotiable | false | 10 |
| R13142 | Jailbreak classifier — emits OCSF Detection 2004 on either class | cross-ref selfdef MS026 | F06590 | non-negotiable | false | 10 |
| R13143 | Jailbreak classifier — severity differs per class (WB = high, BB = critical) | architecture + arXiv 2604.09839 | F06590 | non-negotiable | false | 10 |
| R13144 | Jailbreak classifier — composes with selfdef MS044 Guardian Tetragon eBPF | cross-ref selfdef MS044 | F06591 | non-negotiable | false | 10 |
| R13145 | Guardian policy — `/etc/tetragon/tracing-policies/intervention-class.yaml` | cross-ref selfdef MS044 | F06592 | non-negotiable | false | 10 |
| R13146 | Guardian policy — detects unauthorized activation-steer hooks | cross-ref selfdef MS044 | F06593 | non-negotiable | false | 10 |
| R13147 | Guardian policy — detects unauthorized weight-edit syscalls | cross-ref selfdef MS044 | F06594 | non-negotiable | false | 10 |
| R13148 | Guardian policy — signed via MS003 | cross-ref selfdef MS003 | F06592 | non-negotiable | false | 10 |
| R13149 | Guardian policy — reload via `selfdef guardian policy reload` per MS044 | cross-ref selfdef MS044 | F06592 | non-negotiable | false | 10 |
| R13150 | Tool authority — new declaration field `interpretability_intervention_class` | cross-ref selfdef MS042 | F06595 | non-negotiable | false | 10 |
| R13151 | Tool authority — tools performing WB steering MUST declare WB-activation-steer | arXiv 2604.09839 | F06596 | non-negotiable | false | 10 |
| R13152 | Tool authority — declaration-vs-observed mismatch (declared BB, observed WB) triggers block+quarantine+trace | cross-ref selfdef MS042 | F06597 | non-negotiable | false | 10 |
| R13153 | Tool authority — composes with selfdef MS042 4-severity classifier | cross-ref selfdef MS042 | F06598 | non-negotiable | false | 10 |
| R13154 | Tool authority — field added to MS042 typed-mirror schema_version 1.1.0 (additive) | cross-ref selfdef MS042 + MS007 | F06595 | non-negotiable | false | 10 |
| R13155 | Tool authority — declaration signed via MS003 | cross-ref selfdef MS003 | F06596 | non-negotiable | false | 10 |
| R13156 | Authority FSM — WB activation-steer = L4 Execute-bounded with operator approval | cross-ref selfdef MS039 | F06599 | non-negotiable | false | 10 |
| R13157 | Authority FSM — WB weight-edit = L5 Commit (durable change) | cross-ref selfdef MS039 + MS041 | F06600 | non-negotiable | false | 10 |
| R13158 | Authority FSM — BB prompt = L0 Observe / L1 Suggest depending on policy | cross-ref selfdef MS039 | F06601 | non-negotiable | false | 10 |
| R13159 | Authority FSM — class transitions emit M049 trace | cross-ref M049 | F06602 | non-negotiable | false | 10 |
| R13160 | Authority FSM — operator can promote BB-only model to allow WB via signed promotion (TTL-bounded) | cross-ref selfdef MS003 + MS039 | F06603 | non-negotiable | false | 10 |
| R13161 | Authority FSM — WB activation-steer authorization TTL `<=` 24h default | cross-ref selfdef MS038 | F06603 | non-negotiable | false | 10 |
| R13162 | Authority FSM — WB weight-edit requires MS041 triple-gate per L6 Persist | cross-ref selfdef MS041 | F06600 | non-negotiable | false | 10 |
| R13163 | Authority FSM — class violations halt active inference + emit OCSF Detection 2004 | cross-ref selfdef MS026 | F06602 | non-negotiable | false | 10 |
| R13164 | Authority FSM — operator override logged in MS009 audit chain | cross-ref selfdef MS009 | F06603 | non-negotiable | false | 10 |
| R13165 | Typed mirror — sovereign-intervention-class-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F06604 | non-negotiable | false | 10 |
| R13166 | Typed mirror — InterventionClass enum 4 variants | cross-ref selfdef MS007 | F06605 | non-negotiable | false | 10 |
| R13167 | Typed mirror — InterventionContext struct {class, hook_layers, magnitude_digest, signed_authorization} | cross-ref selfdef MS007 | F06606 | non-negotiable | false | 10 |
| R13168 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F06607 | non-negotiable | false | 10 |
| R13169 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F06608 | non-negotiable | false | 10 |
| R13170 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F06604 | non-negotiable | false | 10 |
| R13171 | Typed mirror — no_std friendly | architecture | F06604 | non-negotiable | false | 10 |
| R13172 | Typed mirror — serde + bincode derives present | architecture | F06604 | non-negotiable | false | 10 |
| R13173 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F06607 | non-negotiable | false | 10 |
| R13174 | Event — every intervention emits M049 13-field span | cross-ref M049 | F06609 | non-negotiable | false | 10 |
| R13175 | Event — span includes class + hook sites + magnitude digest | cross-ref M049 | F06610 | non-negotiable | false | 10 |
| R13176 | Event — emits OCSF Audit Activity 1003 per intervention | cross-ref selfdef MS026 | F06611 | non-negotiable | false | 10 |
| R13177 | Event — unauthorized intervention emits OCSF Detection 2004 | cross-ref selfdef MS026 | F06612 | non-negotiable | false | 10 |
| R13178 | Event — span deterministic for MS009 replay | cross-ref selfdef MS009 | F06613 | non-negotiable | false | 10 |
| R13179 | Replay validator — verifies historical intervention chain | cross-ref selfdef MS009 | F06614 | non-negotiable | false | 10 |
| R13180 | Replay validator — detects category-confused eval claims | cross-ref selfdef MS009 + arXiv 2604.09839 | F06615 | non-negotiable | false | 10 |
| R13181 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 | F06616 | non-negotiable | false | 10 |
| R13182 | Replay validator — runs daily | cross-ref selfdef MS009 | F06617 | non-negotiable | false | 10 |
| R13183 | Replay validator — failures halt new WB interventions | architecture | F06614 | non-negotiable | false | 10 |
| R13184 | Dashboard — D-05 traces surfaces intervention class per trace | cross-ref M060 | F06618 | non-negotiable | false | 10 |
| R13185 | Dashboard — D-06 pending approvals surfaces WB steering approval requests | cross-ref M060 | F06619 | non-negotiable | false | 10 |
| R13186 | Dashboard — D-10 eval history shows WB vs BB benchmark disaggregation | cross-ref M060 | F06620 | non-negotiable | false | 10 |
| R13187 | Dashboard — D-17 quarantine surfaces declaration-vs-observed intervention mismatches | cross-ref M060 + selfdef MS042 | F06621 | non-negotiable | false | 10 |
| R13188 | Dashboard — D-18 trust scores incorporates intervention class history | cross-ref M060 + selfdef MS042 | F06622 | non-negotiable | false | 10 |
| R13189 | Dashboard — operator can drill into per-intervention detail | cross-ref M060 | F06618 | non-negotiable | false | 10 |
| R13190 | CLI — `sovereign intervention status` returns taxonomy state | cross-ref selfdef MS043 | F06623 | non-negotiable | false | 10 |
| R13191 | CLI — `sovereign intervention scan <model>` checks for unauthorized WB modifications | architecture + cross-ref selfdef MS003 | F06624 | non-negotiable | false | 10 |
| R13192 | CLI — `sovereign intervention authorize <class> --ttl <sec>` operator-grants intervention authority | cross-ref selfdef MS003 + MS038 | F06625 | non-negotiable | false | 10 |
| R13193 | CLI — `sovereign intervention history --class <name>` returns prior interventions | architecture | F06626 | non-negotiable | false | 10 |
| R13194 | CLI — `sovereign intervention verify-eval <result>` verifies WB vs BB disaggregation | architecture + arXiv 2604.09839 | F06627 | non-negotiable | false | 10 |
| R13195 | CLI — all intervention subcommands emit M049 trace | cross-ref M049 | F06628 | non-negotiable | false | 10 |
| R13196 | CLI — `--json` flag returns structured output | architecture | F06629 | non-negotiable | false | 10 |
| R13197 | CLI — `sovereign intervention revoke <auth-id>` revokes active WB authorization | cross-ref selfdef MS003 + MS035 | F06625 | non-negotiable | false | 10 |
| R13198 | CLI — `sovereign intervention manifold-digest <model>` returns prompt-reachable manifold digest | architecture | F06575 | non-negotiable | false | 10 |
| R13199 | CLI — exit codes follow sysexits.h | architecture | F06623 | non-negotiable | false | 10 |
| R13200 | Composition — composes with M044 substrate (Blackwell oracle execution) | cross-ref M044 | F06578 | non-negotiable | false | 10 |
| R13201 | Composition — composes with M046 LoRA Foundry (legitimate weight-edit path) | cross-ref M046 | F06581 | non-negotiable | false | 10 |
| R13202 | Composition — composes with M048 Eval-Value module | cross-ref M048 | F06585 | non-negotiable | false | 10 |
| R13203 | Composition — composes with M049 observability + trace pipeline | cross-ref M049 | F06609 | non-negotiable | false | 10 |
| R13204 | Composition — composes with M055 failure modes (intervention-class violation taxonomy) | cross-ref M055 | F06163 | non-negotiable | false | 10 |
| R13205 | Composition — composes with M057 12-step task lifecycle (Step 9 Evaluate disaggregation) | cross-ref M057 | F06582 | non-negotiable | false | 10 |
| R13206 | Composition — composes with M058 hardware-aware scheduler | cross-ref M058 | F06578 | non-negotiable | false | 10 |
| R13207 | Composition — composes with M060 cockpit dashboards (D-05 / D-06 / D-10 / D-17 / D-18) | cross-ref M060 | F06618 | non-negotiable | false | 10 |
| R13208 | Composition — composes with M063 SFIF Features phase | cross-ref M063 | F06624 | non-negotiable | false | 10 |
| R13209 | Composition — composes with M077 NVFP4 (quantization-aware weight-edit diff) | cross-ref M077 | F06579 | non-negotiable | false | 10 |
| R13210 | Composition — composes with M078 HölderPO (RL training = WB weight-edit class) | cross-ref M078 | F06600 | non-negotiable | false | 10 |
| R13211 | Composition — composes with selfdef MS003 chain-of-trust | cross-ref selfdef MS003 | F06570 | non-negotiable | false | 10 |
| R13212 | Composition — composes with selfdef MS007 typed-mirror | cross-ref selfdef MS007 | F06604 | non-negotiable | false | 10 |
| R13213 | Composition — composes with selfdef MS009 replay validator | cross-ref selfdef MS009 | F06614 | non-negotiable | false | 10 |
| R13214 | Composition — composes with selfdef MS026 OCSF event emission | cross-ref selfdef MS026 | F06611 | non-negotiable | false | 10 |
| R13215 | Composition — composes with selfdef MS035 capability tokens (intervention authority bits) | cross-ref selfdef MS035 | F06625 | non-negotiable | false | 10 |
| R13216 | Composition — composes with selfdef MS038 network boundary (TTL bounds) | cross-ref selfdef MS038 | F06161 | non-negotiable | false | 10 |
| R13217 | Composition — composes with selfdef MS039 authority levels (FSM bridge) | cross-ref selfdef MS039 | F06599 | non-negotiable | false | 10 |
| R13218 | Composition — composes with selfdef MS040 profile envelopes (class permitted per profile) | cross-ref selfdef MS040 | F06603 | non-negotiable | false | 10 |
| R13219 | Composition — composes with selfdef MS041 commit authority (L6 weight-edit) | cross-ref selfdef MS041 | F06600 | non-negotiable | false | 10 |
| R13220 | Composition — composes with selfdef MS042 tool authority (declaration extension) | cross-ref selfdef MS042 | F06595 | non-negotiable | false | 10 |
| R13221 | Composition — composes with selfdef MS043 IPS operator surface | cross-ref selfdef MS043 | F06623 | non-negotiable | false | 10 |
| R13222 | Composition — composes with selfdef MS044 Guardian (Tetragon policy bridge) | cross-ref selfdef MS044 | F06591 | non-negotiable | false | 10 |
| R13223 | Boundary — intervention class taxonomy = sovereign-os runtime | architecture + operator standing direction | F06562 | non-negotiable | false | 10 |
| R13224 | Boundary — selfdef IPS enforces declaration-vs-observed per MS042 | operator standing direction | F06597 | non-negotiable | false | 10 |
| R13225 | Boundary — selfdef IPS enforces Guardian Tetragon policy per MS044 | operator standing direction | F06591 | non-negotiable | false | 10 |
| R13226 | Boundary — info-hub indexes arXiv 2604.09839 paper lineage as second-brain entry | operator standing direction | F06546 | non-negotiable | false | 10 |
| R13227 | Boundary — info-hub never mutated by intervention activity | operator standing direction | F06546 | non-negotiable | false | 10 |
| R13228 | Doctrinal preservation — arXiv 2604.09839 abstract preserved verbatim in `backlog/notes/external-research-ingestion-2026-05-19.md` | operator standing direction | F06546 | non-negotiable | false | 10 |
| R13229 | Doctrinal preservation — "pushes the residual stream off the manifold of states reachable from discrete prompts" verbatim | arXiv 2604.09839 | F06555 | non-negotiable | false | 10 |
| R13230 | Doctrinal preservation — "almost surely, no prompt can reproduce the same internal behavior" verbatim | arXiv 2604.09839 | F06556 | non-negotiable | false | 10 |
| R13231 | Doctrinal preservation — "formal separation between white-box steerability and black-box prompting" verbatim | arXiv 2604.09839 | F06558 | non-negotiable | false | 10 |
| R13232 | Doctrinal preservation — operator standing direction "you cannot invent crap" upheld (formal-proof-based paper) | operator standing direction | F06555 | non-negotiable | false | 10 |
| R13233 | Doctrinal preservation — operator standing direction "Respect the projects" upheld (sovereign-os runtime; selfdef enforces) | operator standing direction | F06223 | non-negotiable | false | 10 |
| R13234 | Doctrinal preservation — operator standing direction "second-brain" upheld (info-hub indexes paper) | operator standing direction | F06226 | non-negotiable | false | 10 |
| R13235 | Doctrinal preservation — operator standing direction "layered ON TOP" upheld (M049/M048/MS039/MS042/MS044 not discarded) | operator standing direction | F06104 | non-negotiable | false | 10 |
| R13236 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F06556 | non-negotiable | false | 10 |
| R13237 | Operator UX — operator may toggle each intervention class on/off per profile | operator standing direction "everything can be turned on and off" | F06603 | non-negotiable | false | 10 |
| R13238 | Operator UX — operator may set WB-steering TTL per profile | operator standing direction "modes and profiles" | F06161 | non-negotiable | false | 10 |
| R13239 | Operator UX — operator may view intervention history in D-05 dashboard | cross-ref M060 | F06618 | non-negotiable | false | 10 |
| R13240 | Operator UX — operator may approve/deny WB steering requests in D-06 | cross-ref M060 | F06619 | non-negotiable | false | 10 |
| R13241 | Operator UX — operator may inspect WB vs BB eval disaggregation in D-10 | cross-ref M060 | F06620 | non-negotiable | false | 10 |
| R13242 | Performance — intervention class tagging latency `<` 1ms p95 | architecture | F06567 | non-negotiable | false | 10 |
| R13243 | Performance — activation-steer detection latency `<` 5ms p95 | architecture | F06576 | non-negotiable | false | 10 |
| R13244 | Performance — weight-edit hash chain validation `<` 10s for typical 7B-param model | architecture | F06579 | non-negotiable | false | 10 |
| R13245 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F06604 | non-negotiable | false | 10 |
| R13246 | Performance — replay validator daily run `<` 60s | cross-ref selfdef MS009 | F06614 | non-negotiable | false | 10 |
| R13247 | Telemetry — intervention class distribution emitted via M049 | cross-ref M049 | F06568 | non-negotiable | false | 10 |
| R13248 | Telemetry — unauthorized intervention count emitted via M049 (high-priority alert) | cross-ref M049 | F06612 | non-negotiable | false | 10 |
| R13249 | Telemetry — WB authorization grants per profile emitted via M049 | cross-ref M049 | F06625 | non-negotiable | false | 10 |
| R13250 | Telemetry — manifold drift histogram emitted via M049 | cross-ref M049 | F06572 | non-negotiable | false | 10 |
| R13251 | Telemetry — eval-protocol disaggregation rate emitted via M049 | cross-ref M049 | F06583 | non-negotiable | false | 10 |
| R13252 | Operational — sovereign-intervention-class.service systemd unit | architecture | F06623 | non-negotiable | false | 10 |
| R13253 | Operational — service honors SIGHUP for taxonomy reload | architecture | F06623 | non-negotiable | false | 10 |
| R13254 | Operational — service refuses to start with chain-break in MS009 | cross-ref selfdef MS009 | F06614 | non-negotiable | false | 10 |
| R13255 | Operational — service refuses to start with missing MS003 keys | cross-ref selfdef MS003 | F06570 | non-negotiable | false | 10 |
| R13256 | Operational — service readiness probe at /run/sovereign-intervention-class/ready | architecture | F06623 | non-negotiable | false | 10 |
| R13257 | Closing — sovereign-os catalog at 78/78 milestones | architecture | F06630 | non-negotiable | false | 10 |
| R13258 | Closing — combined ecosystem 122 milestones | architecture | F06630 | non-negotiable | false | 10 |
| R13259 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F06546 | non-negotiable | false | 10 |
| R13260 | Closing — M079 covers arXiv 2604.09839 verbatim; M080 HRM Architectural Class is LAST external-research milestone | arXiv 2604.09839 + operator standing direction | F06630 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M079.

## Cross-references

- **M044** — substrate (Blackwell oracle execution)
- **M046** — LoRA Foundry (legitimate WB-weight-edit path)
- **M048** — Eval-Value module (eval-protocol separator integration)
- **M049** — observability + trace pipeline (intervention class spans)
- **M055** — failure modes (intervention-class violation taxonomy)
- **M057** — 12-step task lifecycle (Step 9 Evaluate disaggregation)
- **M058** — hardware-aware scheduler
- **M060** — cockpit dashboards (D-05 / D-06 / D-10 / D-17 / D-18)
- **M063** — SFIF Features phase
- **M077** — NVFP4 (quantization-aware weight-edit diff)
- **M078** — HölderPO (RL training is WB-weight-edit class)
- **selfdef MS003** — selfdef-signing
- **selfdef MS007** — typed-mirror (sovereign-intervention-class-mirror)
- **selfdef MS009** — replay validator
- **selfdef MS026** — OCSF event emission
- **selfdef MS035** — capability tokens (intervention authority bits)
- **selfdef MS038** — network boundary (TTL bounds)
- **selfdef MS039** — authority levels (FSM bridge)
- **selfdef MS040** — profile envelopes
- **selfdef MS041** — commit authority (L6 weight-edit)
- **selfdef MS042** — tool authority (declaration extension)
- **selfdef MS043** — IPS operator surface
- **selfdef MS044** — Guardian Daemon (Tetragon policy bridge)

## Schema

```
schema_version: "1.0.0"
milestone_id: M079
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
canonical_source: "arXiv 2604.09839 — Steered LLM Activations are Non-Surjective (Mishra/Khashabi/Liu, 2026-05-07)"
intervention_class_taxonomy:
  - None
  - BlackBoxPrompt
  - WhiteBoxActivationSteer
  - WhiteBoxWeightEdit
formal_proof:
  statement: "activation steering pushes the residual stream off the manifold of states reachable from discrete prompts"
  conclusion: "almost surely, no prompt can reproduce the same internal behavior induced by steering"
  implication: "formal separation between white-box steerability and black-box prompting"
empirical_validation: "3 widely-used LLMs"
typed_mirror_crate: sovereign-intervention-class-mirror
catalog_status:
  sovereign_os: 78/78 milestones
  selfdef: 44/44 milestones
  combined: 122 milestones
```
