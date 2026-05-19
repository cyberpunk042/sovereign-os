# M078 — HölderPO + GRPO post-training pipeline (Hölder-mean token aggregation + dynamic-p annealing)

**Parent**: sovereign-os runtime — RL post-training layer (layered onto M046 LoRA Foundry + M048 Eval-Value module + M057 step 11 Learn)
**Source**: arXiv 2605.12058 — "Hölder Policy Optimisation" — Yuxiang Chen, Dingli Liang, Yihang Chen, Ziqin Gong, Chenyang Le, Zhaokai Wang, Jiachen Zhu, Lingyu Yang, et al. (2026-05-12)
**Companion source**: GRPO baseline (Group Relative Policy Optimisation) per DeepSeek-Math / DeepSeek-R1 papers
**Provenance**: Ingested via HF MCP `paper_search` 2026-05-19 (`hf.co/papers/2605.12058`)

## Doctrinal anchors (verbatim from arXiv 2605.12058)

> "Group Relative Policy Optimisation (GRPO) enhances large language models by estimating advantages across a group of sampled trajectories. However, mapping these trajectory-level advantages to policy updates requires aggregating token-level probabilities within each sequence. Relying on a fixed aggregation mechanism for this step fundamentally limits the algorithm's adaptability."

> "We propose HölderPO, a generalised policy optimisation framework unifying token-level probability aggregation via the Hölder mean. By explicitly modulating the parameter p, our framework provides continuous control over the trade-off between gradient concentration and variance bounds."

> "Theoretically, we prove that a larger p concentrates the gradient to amplify sparse learning signals, whereas a smaller p strictly bounds gradient variance."

> "we instantiate the framework with a dynamic annealing algorithm that progressively schedules p across the training lifecycle."

> "achieves a state-of-the-art average accuracy of 54.9% across multiple mathematical benchmarks, yielding a substantial 7.2% relative gain over standard GRPO and secures an exceptional 93.8% success rate on ALFWorld."

## Catalog positioning

M046 LoRA Foundry + M048 Eval-Value mention RL lightly. M078 adds two concrete published RL post-training algorithms — GRPO (baseline) + HölderPO (Hölder-mean generalised) — as operator-selectable adapter promotion paths. NOT inventing RL; cataloging peer-reviewed published algorithms per operator standing direction "you cannot invent crap."

## Epics (E0748-E0757)

| epic | name | source |
|---|---|---|
| E0748 | GRPO baseline — Group Relative Policy Optimisation (trajectory advantage estimation) | arXiv 2605.12058 (introduces GRPO context) |
| E0749 | HölderPO framework — token-level probability aggregation via Hölder mean | arXiv 2605.12058 |
| E0750 | Hölder parameter p — continuous control trade-off (gradient concentration vs variance bounds) | arXiv 2605.12058 |
| E0751 | Theoretical proof — larger p concentrates gradient; smaller p bounds variance | arXiv 2605.12058 |
| E0752 | Dynamic annealing algorithm — progressive scheduling of p across training lifecycle | arXiv 2605.12058 |
| E0753 | Benchmark — 54.9% avg math accuracy (+7.2% vs GRPO) | arXiv 2605.12058 |
| E0754 | Benchmark — 93.8% ALFWorld success rate | arXiv 2605.12058 |
| E0755 | Integration with M046 LoRA Foundry — RL fine-tune adapter via HölderPO | cross-ref M046 + arXiv 2605.12058 |
| E0756 | Integration with M048 Eval-Value module — reward signal per trajectory | cross-ref M048 + arXiv 2605.12058 |
| E0757 | Integration with M057 step 11 Learn — HölderPO as one of multiple Learn paths | cross-ref M057 + arXiv 2605.12058 |

## Modules (M01292-M01308)

| module | name | source |
|---|---|---|
| M01292 | sovereign-grpo-trajectory-sampler | arXiv 2605.12058 |
| M01293 | sovereign-grpo-advantage-estimator | arXiv 2605.12058 |
| M01294 | sovereign-holderpo-hoelder-mean-aggregator | arXiv 2605.12058 |
| M01295 | sovereign-holderpo-p-parameter-controller | arXiv 2605.12058 |
| M01296 | sovereign-holderpo-gradient-concentrator (large-p path) | arXiv 2605.12058 |
| M01297 | sovereign-holderpo-variance-bounder (small-p path) | arXiv 2605.12058 |
| M01298 | sovereign-holderpo-annealing-scheduler | arXiv 2605.12058 |
| M01299 | sovereign-holderpo-training-loop | arXiv 2605.12058 |
| M01300 | sovereign-holderpo-math-benchmark-runner | arXiv 2605.12058 |
| M01301 | sovereign-holderpo-alfworld-benchmark-runner | arXiv 2605.12058 |
| M01302 | sovereign-holderpo-lora-foundry-bridge | cross-ref M046 |
| M01303 | sovereign-holderpo-eval-value-bridge | cross-ref M048 |
| M01304 | sovereign-holderpo-typed-mirror | cross-ref selfdef MS007 |
| M01305 | sovereign-holderpo-event-emitter | cross-ref M049 + selfdef MS026 |
| M01306 | sovereign-holderpo-replay-validator | cross-ref selfdef MS009 |
| M01307 | sovereign-holderpo-cli-subcommand-set | cross-ref selfdef MS043 |
| M01308 | sovereign-holderpo-dashboard-binding (D-10 + D-11) | cross-ref M060 |

## Features (F06461-F06545)

| feature | name | source |
|---|---|---|
| F06461 | GRPO — Group Relative Policy Optimisation baseline algorithm | arXiv 2605.12058 (intro) |
| F06462 | GRPO — estimates advantages across group of sampled trajectories | arXiv 2605.12058 |
| F06463 | GRPO — maps trajectory-level advantages to policy updates | arXiv 2605.12058 |
| F06464 | GRPO — token-level probability aggregation required | arXiv 2605.12058 |
| F06465 | GRPO — fixed aggregation mechanism limits adaptability (motivation for HölderPO) | arXiv 2605.12058 |
| F06466 | GRPO — empirical observation: fixed aggregations suffer training collapse OR fail to yield satisfactory performance | arXiv 2605.12058 |
| F06467 | HölderPO — generalised policy optimisation framework | arXiv 2605.12058 |
| F06468 | HölderPO — unifies token-level probability aggregation via Hölder mean | arXiv 2605.12058 |
| F06469 | HölderPO — parameter p explicitly modulates aggregation | arXiv 2605.12058 |
| F06470 | HölderPO — continuous control over gradient-concentration vs variance-bounds trade-off | arXiv 2605.12058 |
| F06471 | Hölder mean — mathematical operator generalising arithmetic (p=1), geometric (p→0), harmonic (p=-1), max (p→∞), min (p→-∞) | mathematical definition |
| F06472 | Theoretical — larger p amplifies sparse learning signals via gradient concentration | arXiv 2605.12058 |
| F06473 | Theoretical — smaller p strictly bounds gradient variance | arXiv 2605.12058 |
| F06474 | Theoretical — no single static p universally optimal | arXiv 2605.12058 |
| F06475 | Dynamic annealing — progressively schedules p across training lifecycle | arXiv 2605.12058 |
| F06476 | Dynamic annealing — operator-configurable schedule (linear / exponential / cosine / custom) | architecture + arXiv 2605.12058 |
| F06477 | Dynamic annealing — schedule signed via MS003 per training run | cross-ref selfdef MS003 |
| F06478 | Benchmark — math accuracy 54.9% avg across multiple benchmarks | arXiv 2605.12058 |
| F06479 | Benchmark — 7.2% relative gain over standard GRPO | arXiv 2605.12058 |
| F06480 | Benchmark — 93.8% success on ALFWorld | arXiv 2605.12058 |
| F06481 | Benchmark — stability + convergence superior to GRPO baseline | arXiv 2605.12058 |
| F06482 | Implementation — Hölder mean computed per token sequence | arXiv 2605.12058 |
| F06483 | Implementation — gradient aggregation respects p value at current step | arXiv 2605.12058 |
| F06484 | Implementation — Adam or AdamW optimizer compatible | architecture |
| F06485 | Implementation — composes with NVFP4 training (M077) for 4-bit RL | cross-ref M077 |
| F06486 | LoRA Foundry bridge — HölderPO trains LoRA adapter on top of base model | cross-ref M046 |
| F06487 | LoRA Foundry bridge — adapter promotion gates per MS041 high-risk triple-gate | cross-ref selfdef MS041 |
| F06488 | LoRA Foundry bridge — HölderPO-trained adapters tagged "rl-holderpo" in adapter registry | architecture + cross-ref M046 |
| F06489 | LoRA Foundry bridge — operator can promote/demote per profile (MS040) | cross-ref selfdef MS040 |
| F06490 | Eval-Value bridge — reward signal supplied per trajectory | cross-ref M048 |
| F06491 | Eval-Value bridge — reward composable with operator-defined eval function | cross-ref M048 + M057 |
| F06492 | Eval-Value bridge — reward signed via MS003 + recorded in MS009 audit chain | cross-ref selfdef MS003 + MS009 |
| F06493 | M057 step 11 Learn integration — HölderPO as one Learn-path option | cross-ref M057 |
| F06494 | M057 step 11 Learn integration — operator selects HölderPO vs GRPO vs no-RL-update | cross-ref M057 + operator standing direction |
| F06495 | Math benchmark runner — GSM8K / MATH / AIME suite | arXiv 2605.12058 + benchmark standard |
| F06496 | Math benchmark runner — emits per-benchmark + aggregate score via M049 | cross-ref M049 |
| F06497 | Math benchmark runner — composes with M048 Eval-Value module | cross-ref M048 |
| F06498 | ALFWorld benchmark runner — text-based interactive task env | arXiv 2605.12058 |
| F06499 | ALFWorld benchmark runner — 93.8% target accuracy per arXiv 2605.12058 | arXiv 2605.12058 |
| F06500 | ALFWorld benchmark runner — emits success rate via M049 | cross-ref M049 |
| F06501 | Trajectory sampler — group of N sampled trajectories per training step | arXiv 2605.12058 |
| F06502 | Trajectory sampler — N = operator-configurable (default 8 per GRPO standard) | architecture |
| F06503 | Trajectory sampler — sandboxed per MS036 Tier B/C/D | cross-ref selfdef MS036 |
| F06504 | Advantage estimator — relative advantage per trajectory in group | arXiv 2605.12058 |
| F06505 | Advantage estimator — normalised by group mean + std | arXiv 2605.12058 |
| F06506 | p-parameter controller — float in (-∞, ∞), operator-clamped [-10, 10] default | architecture + arXiv 2605.12058 |
| F06507 | p-parameter controller — p schedule retained per training run + signed | cross-ref selfdef MS003 |
| F06508 | Gradient concentrator — large-p amplifies sparse signals | arXiv 2605.12058 |
| F06509 | Gradient concentrator — alerts on gradient norm spike (M055 failure mode) | cross-ref M055 |
| F06510 | Variance bounder — small-p strictly bounds gradient variance | arXiv 2605.12058 |
| F06511 | Variance bounder — emits variance histogram via M049 | cross-ref M049 |
| F06512 | Annealing scheduler — operator-selectable curve (linear / exp / cosine / step / custom) | architecture |
| F06513 | Annealing scheduler — schedule visualizable in D-10 eval history dashboard | cross-ref M060 |
| F06514 | Training loop — composes with M063 SFIF Features phase | cross-ref M063 |
| F06515 | Training loop — composes with M077 NVFP4 backward pass for 4-bit RL | cross-ref M077 |
| F06516 | Training loop — composes with M058 hardware-aware scheduler (Blackwell oracle) | cross-ref M058 |
| F06517 | Training loop — composes with M075 SRP topology (Oracle Core for HölderPO training) | cross-ref M075 |
| F06518 | Training loop — checkpointed per M063 IaC quality bar | cross-ref M063 |
| F06519 | Typed mirror — sovereign-holderpo-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F06520 | Typed mirror — HolderPoConfig struct {p_schedule, group_size, reward_fn_ref, base_model_id, adapter_id} | cross-ref selfdef MS007 |
| F06521 | Typed mirror — PScheduleType enum (Static / Linear / Exponential / Cosine / Step / Custom) | cross-ref selfdef MS007 |
| F06522 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F06523 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F06524 | Event emitter — every training step emits M049 13-field trace | cross-ref M049 |
| F06525 | Event emitter — span includes p-value + group-size + reward-mean + advantage-variance | cross-ref M049 + arXiv 2605.12058 |
| F06526 | Event emitter — emits OCSF System Activity 1001 per training step | cross-ref selfdef MS026 |
| F06527 | Event emitter — divergence (gradient collapse / variance explosion) emits OCSF Detection 2004 | cross-ref selfdef MS026 + M055 |
| F06528 | Event emitter — span deterministic for MS009 replay | cross-ref selfdef MS009 |
| F06529 | Replay validator — verifies historical HölderPO training chain | cross-ref selfdef MS009 |
| F06530 | Replay validator — detects unauthorized p-schedule modification | cross-ref selfdef MS009 + MS003 |
| F06531 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 |
| F06532 | Replay validator — runs daily | cross-ref selfdef MS009 |
| F06533 | Dashboard — D-10 eval history surfaces math + ALFWorld scores over training | cross-ref M060 |
| F06534 | Dashboard — D-10 shows p-schedule curve overlay | cross-ref M060 |
| F06535 | Dashboard — D-11 adapter status surfaces HölderPO-trained adapters | cross-ref M060 |
| F06536 | Dashboard — D-04 costs surfaces RL training cost per adapter | cross-ref M060 |
| F06537 | Dashboard — D-01 active sessions surfaces in-flight HölderPO runs | cross-ref M060 |
| F06538 | CLI — `sovereign holderpo train --base <model> --schedule <p-curve>` invokes training | cross-ref selfdef MS043 |
| F06539 | CLI — `sovereign holderpo status` returns active training state | cross-ref selfdef MS043 |
| F06540 | CLI — `sovereign holderpo benchmark <suite>` runs math or ALFWorld benchmark | cross-ref selfdef MS043 |
| F06541 | CLI — `sovereign holderpo p-schedule show` returns current p schedule | architecture |
| F06542 | CLI — `sovereign holderpo p-schedule set <curve>` updates schedule (operator-signed) | cross-ref selfdef MS003 |
| F06543 | CLI — all holderpo subcommands emit M049 trace | cross-ref M049 |
| F06544 | CLI — `--json` flag returns structured output | architecture |
| F06545 | Closing — M078 covers arXiv 2605.12058 verbatim; M079 Activation Steering Surface next | arXiv 2605.12058 |

## Requirements (R12921-R13090)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R12921 | Doctrinal — GRPO baseline preserved verbatim from arXiv 2605.12058 | arXiv 2605.12058 | F06461 | non-negotiable | false | 10 |
| R12922 | Doctrinal — HölderPO generalised policy optimisation framework | arXiv 2605.12058 | F06467 | non-negotiable | false | 10 |
| R12923 | Doctrinal — unifies token-level probability aggregation via Hölder mean | arXiv 2605.12058 | F06468 | non-negotiable | false | 10 |
| R12924 | Doctrinal — parameter p modulates gradient-concentration vs variance-bounds trade-off | arXiv 2605.12058 | F06470 | non-negotiable | false | 10 |
| R12925 | Doctrinal — larger p concentrates gradient (amplifies sparse signals) | arXiv 2605.12058 | F06472 | non-negotiable | false | 10 |
| R12926 | Doctrinal — smaller p strictly bounds gradient variance | arXiv 2605.12058 | F06473 | non-negotiable | false | 10 |
| R12927 | Doctrinal — no static p universally optimal | arXiv 2605.12058 | F06474 | non-negotiable | false | 10 |
| R12928 | Doctrinal — dynamic annealing progressively schedules p across training lifecycle | arXiv 2605.12058 | F06475 | non-negotiable | false | 10 |
| R12929 | Doctrinal — math accuracy 54.9% avg | arXiv 2605.12058 | F06478 | non-negotiable | false | 10 |
| R12930 | Doctrinal — 7.2% relative gain over standard GRPO | arXiv 2605.12058 | F06479 | non-negotiable | false | 10 |
| R12931 | Doctrinal — 93.8% ALFWorld success | arXiv 2605.12058 | F06480 | non-negotiable | false | 10 |
| R12932 | Doctrinal — operator standing direction "you cannot invent crap" upheld (HölderPO is published peer-reviewed) | operator standing direction | F06467 | non-negotiable | false | 10 |
| R12933 | GRPO — estimates advantages across group of sampled trajectories | arXiv 2605.12058 | F06462 | non-negotiable | false | 10 |
| R12934 | GRPO — maps trajectory-level advantages to policy updates | arXiv 2605.12058 | F06463 | non-negotiable | false | 10 |
| R12935 | GRPO — token-level probability aggregation required | arXiv 2605.12058 | F06464 | non-negotiable | false | 10 |
| R12936 | GRPO — fixed aggregation limits adaptability (HölderPO motivation) | arXiv 2605.12058 | F06465 | non-negotiable | false | 10 |
| R12937 | GRPO — empirically suffers training collapse OR fails to converge with fixed aggregation | arXiv 2605.12058 | F06466 | non-negotiable | false | 10 |
| R12938 | GRPO — available as baseline alongside HölderPO | arXiv 2605.12058 | F06461 | non-negotiable | false | 10 |
| R12939 | Hölder mean — generalises arithmetic (p=1) | mathematical definition | F06471 | non-negotiable | false | 10 |
| R12940 | Hölder mean — generalises geometric mean (p→0) | mathematical definition | F06471 | non-negotiable | false | 10 |
| R12941 | Hölder mean — generalises harmonic mean (p=-1) | mathematical definition | F06471 | non-negotiable | false | 10 |
| R12942 | Hölder mean — generalises max operator (p→∞) | mathematical definition | F06471 | non-negotiable | false | 10 |
| R12943 | Hölder mean — generalises min operator (p→-∞) | mathematical definition | F06471 | non-negotiable | false | 10 |
| R12944 | Hölder mean — computed per token sequence | arXiv 2605.12058 | F06482 | non-negotiable | false | 10 |
| R12945 | Hölder mean — gradient aggregation respects p at current step | arXiv 2605.12058 | F06483 | non-negotiable | false | 10 |
| R12946 | p-parameter controller — float (operator-clamped default [-10, 10]) | architecture + arXiv 2605.12058 | F06506 | non-negotiable | false | 10 |
| R12947 | p-parameter controller — schedule retained per training run | architecture | F06507 | non-negotiable | false | 10 |
| R12948 | p-parameter controller — schedule signed via MS003 | cross-ref selfdef MS003 | F06507 | non-negotiable | false | 10 |
| R12949 | Gradient concentrator — large-p amplifies sparse signals | arXiv 2605.12058 | F06508 | non-negotiable | false | 10 |
| R12950 | Gradient concentrator — alerts on gradient norm spike | cross-ref M055 | F06509 | non-negotiable | false | 10 |
| R12951 | Variance bounder — small-p strictly bounds gradient variance | arXiv 2605.12058 | F06510 | non-negotiable | false | 10 |
| R12952 | Variance bounder — emits variance histogram via M049 | cross-ref M049 | F06511 | non-negotiable | false | 10 |
| R12953 | Annealing — operator-selectable curve type (linear / exp / cosine / step / custom) | architecture | F06512 | non-negotiable | false | 10 |
| R12954 | Annealing — schedule visualizable in D-10 eval history | cross-ref M060 | F06513 | non-negotiable | false | 10 |
| R12955 | Annealing — schedule operator-customizable per training run | operator standing direction | F06512 | non-negotiable | false | 10 |
| R12956 | Annealing — schedule signed via MS003 | cross-ref selfdef MS003 | F06477 | non-negotiable | false | 10 |
| R12957 | Annealing — schedule changes mid-training emit OCSF Configuration Change 5001 | cross-ref selfdef MS026 | F06477 | non-negotiable | false | 10 |
| R12958 | Training loop — group size N = operator-configurable (default 8) | architecture | F06502 | non-negotiable | false | 10 |
| R12959 | Training loop — sandboxed per MS036 Tier B/C/D | cross-ref selfdef MS036 | F06503 | non-negotiable | false | 10 |
| R12960 | Training loop — composes with M063 SFIF Features phase | cross-ref M063 | F06514 | non-negotiable | false | 10 |
| R12961 | Training loop — composes with M077 NVFP4 for 4-bit RL training | cross-ref M077 | F06515 | non-negotiable | false | 10 |
| R12962 | Training loop — composes with M058 hardware-aware scheduler (Blackwell oracle) | cross-ref M058 | F06516 | non-negotiable | false | 10 |
| R12963 | Training loop — composes with M075 SRP topology (Oracle Core training) | cross-ref M075 | F06517 | non-negotiable | false | 10 |
| R12964 | Training loop — checkpointed per M063 IaC quality bar (resumable) | cross-ref M063 | F06518 | non-negotiable | false | 10 |
| R12965 | Training loop — checkpoint signed via MS003 | cross-ref selfdef MS003 | F06518 | non-negotiable | false | 10 |
| R12966 | Training loop — emit M049 trace per step | cross-ref M049 | F06524 | non-negotiable | false | 10 |
| R12967 | LoRA bridge — HölderPO trains LoRA adapter on top of base model | cross-ref M046 | F06486 | non-negotiable | false | 10 |
| R12968 | LoRA bridge — adapter promotion = L6 Persist + MS041 triple-gate | cross-ref selfdef MS039 + MS041 | F06487 | non-negotiable | false | 10 |
| R12969 | LoRA bridge — HölderPO-trained adapters tagged "rl-holderpo" | architecture + cross-ref M046 | F06488 | non-negotiable | false | 10 |
| R12970 | LoRA bridge — GRPO-trained adapters tagged "rl-grpo" | architecture + cross-ref M046 | F06488 | non-negotiable | false | 10 |
| R12971 | LoRA bridge — operator can promote/demote per profile | cross-ref selfdef MS040 | F06489 | non-negotiable | false | 10 |
| R12972 | Eval-Value bridge — reward signal supplied per trajectory | cross-ref M048 | F06490 | non-negotiable | false | 10 |
| R12973 | Eval-Value bridge — reward composable with operator-defined eval function | cross-ref M048 + M057 | F06491 | non-negotiable | false | 10 |
| R12974 | Eval-Value bridge — reward signed via MS003 | cross-ref selfdef MS003 | F06492 | non-negotiable | false | 10 |
| R12975 | Eval-Value bridge — reward recorded in MS009 audit chain | cross-ref selfdef MS009 | F06492 | non-negotiable | false | 10 |
| R12976 | M057 step 11 Learn — HölderPO as one Learn-path option | cross-ref M057 | F06493 | non-negotiable | false | 10 |
| R12977 | M057 step 11 Learn — operator selects HölderPO vs GRPO vs no-RL | operator standing direction | F06494 | non-negotiable | false | 10 |
| R12978 | Benchmark — math suite GSM8K + MATH + AIME | arXiv 2605.12058 + standard | F06495 | non-negotiable | false | 10 |
| R12979 | Benchmark — emits per-benchmark + aggregate score via M049 | cross-ref M049 | F06496 | non-negotiable | false | 10 |
| R12980 | Benchmark — composes with M048 Eval-Value module | cross-ref M048 | F06497 | non-negotiable | false | 10 |
| R12981 | Benchmark — ALFWorld text-interactive task env | arXiv 2605.12058 | F06498 | non-negotiable | false | 10 |
| R12982 | Benchmark — ALFWorld 93.8% target accuracy | arXiv 2605.12058 | F06499 | non-negotiable | false | 10 |
| R12983 | Benchmark — ALFWorld emits success rate via M049 | cross-ref M049 | F06500 | non-negotiable | false | 10 |
| R12984 | Benchmark — benchmark runs signed via MS003 | cross-ref selfdef MS003 | F06495 | non-negotiable | false | 10 |
| R12985 | Benchmark — benchmark results retained 365 days | cross-ref selfdef MS037 | F06495 | non-negotiable | false | 10 |
| R12986 | Trajectory sampler — N=8 default group size (GRPO standard) | architecture | F06502 | non-negotiable | false | 10 |
| R12987 | Trajectory sampler — emits sample-id + parent-step + reward via M049 | cross-ref M049 | F06501 | non-negotiable | false | 10 |
| R12988 | Advantage estimator — relative advantage per trajectory in group | arXiv 2605.12058 | F06504 | non-negotiable | false | 10 |
| R12989 | Advantage estimator — normalised by group mean + std | arXiv 2605.12058 | F06505 | non-negotiable | false | 10 |
| R12990 | Advantage estimator — emits advantage tensor digest via M049 | cross-ref M049 | F06504 | non-negotiable | false | 10 |
| R12991 | Typed mirror — sovereign-holderpo-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F06519 | non-negotiable | false | 10 |
| R12992 | Typed mirror — HolderPoConfig struct fields {p_schedule, group_size, reward_fn_ref, base_model_id, adapter_id} | cross-ref selfdef MS007 | F06520 | non-negotiable | false | 10 |
| R12993 | Typed mirror — PScheduleType enum (Static / Linear / Exponential / Cosine / Step / Custom) | cross-ref selfdef MS007 | F06521 | non-negotiable | false | 10 |
| R12994 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F06522 | non-negotiable | false | 10 |
| R12995 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F06523 | non-negotiable | false | 10 |
| R12996 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F06519 | non-negotiable | false | 10 |
| R12997 | Typed mirror — no_std friendly | architecture | F06519 | non-negotiable | false | 10 |
| R12998 | Typed mirror — serde + bincode derives present | architecture | F06519 | non-negotiable | false | 10 |
| R12999 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F06522 | non-negotiable | false | 10 |
| R13000 | Event — every training step emits M049 13-field trace | cross-ref M049 | F06524 | non-negotiable | false | 10 |
| R13001 | Event — span includes p-value + group-size + reward-mean + advantage-variance | cross-ref M049 + arXiv 2605.12058 | F06525 | non-negotiable | false | 10 |
| R13002 | Event — emits OCSF System Activity 1001 per training step | cross-ref selfdef MS026 | F06526 | non-negotiable | false | 10 |
| R13003 | Event — divergence emits OCSF Detection 2004 | cross-ref selfdef MS026 + M055 | F06527 | non-negotiable | false | 10 |
| R13004 | Event — span deterministic for MS009 replay | cross-ref selfdef MS009 | F06528 | non-negotiable | false | 10 |
| R13005 | Replay validator — verifies historical HölderPO chain | cross-ref selfdef MS009 | F06529 | non-negotiable | false | 10 |
| R13006 | Replay validator — detects unauthorized p-schedule modification | cross-ref selfdef MS009 + MS003 | F06530 | non-negotiable | false | 10 |
| R13007 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 | F06531 | non-negotiable | false | 10 |
| R13008 | Replay validator — runs daily | cross-ref selfdef MS009 | F06532 | non-negotiable | false | 10 |
| R13009 | Replay validator — failures halt new HölderPO runs | architecture | F06529 | non-negotiable | false | 10 |
| R13010 | Dashboard — D-10 eval history surfaces math + ALFWorld scores over training | cross-ref M060 | F06533 | non-negotiable | false | 10 |
| R13011 | Dashboard — D-10 shows p-schedule curve overlay | cross-ref M060 | F06534 | non-negotiable | false | 10 |
| R13012 | Dashboard — D-11 adapter status shows HölderPO-trained adapters | cross-ref M060 | F06535 | non-negotiable | false | 10 |
| R13013 | Dashboard — D-04 costs shows RL training cost per adapter | cross-ref M060 | F06536 | non-negotiable | false | 10 |
| R13014 | Dashboard — D-01 active sessions shows in-flight HölderPO runs | cross-ref M060 | F06537 | non-negotiable | false | 10 |
| R13015 | CLI — `sovereign holderpo train --base <model> --schedule <p-curve>` | cross-ref selfdef MS043 | F06538 | non-negotiable | false | 10 |
| R13016 | CLI — `sovereign holderpo status` returns active training state | cross-ref selfdef MS043 | F06539 | non-negotiable | false | 10 |
| R13017 | CLI — `sovereign holderpo benchmark <suite>` runs math or ALFWorld | cross-ref selfdef MS043 | F06540 | non-negotiable | false | 10 |
| R13018 | CLI — `sovereign holderpo p-schedule show` returns schedule | architecture | F06541 | non-negotiable | false | 10 |
| R13019 | CLI — `sovereign holderpo p-schedule set <curve>` updates schedule (operator-signed) | cross-ref selfdef MS003 | F06542 | non-negotiable | false | 10 |
| R13020 | CLI — all holderpo subcommands emit M049 trace | cross-ref M049 | F06543 | non-negotiable | false | 10 |
| R13021 | CLI — `--json` flag returns structured output | architecture | F06544 | non-negotiable | false | 10 |
| R13022 | CLI — exit codes follow sysexits.h | architecture | F06538 | non-negotiable | false | 10 |
| R13023 | CLI — `sovereign holderpo abort` cleanly stops + checkpoints | architecture | F06539 | non-negotiable | false | 10 |
| R13024 | CLI — `sovereign holderpo resume <checkpoint>` resumes training | architecture + M063 | F06518 | non-negotiable | false | 10 |
| R13025 | CLI — `sovereign holderpo history` returns prior runs | architecture | F06539 | non-negotiable | false | 10 |
| R13026 | Composition — composes with M046 LoRA Foundry | cross-ref M046 | F06486 | non-negotiable | false | 10 |
| R13027 | Composition — composes with M048 Eval-Value module | cross-ref M048 | F06490 | non-negotiable | false | 10 |
| R13028 | Composition — composes with M049 observability + trace pipeline | cross-ref M049 | F06524 | non-negotiable | false | 10 |
| R13029 | Composition — composes with M057 12-step task lifecycle (Step 11 Learn) | cross-ref M057 | F06493 | non-negotiable | false | 10 |
| R13030 | Composition — composes with M058 hardware-aware scheduler | cross-ref M058 | F06516 | non-negotiable | false | 10 |
| R13031 | Composition — composes with M060 cockpit dashboards | cross-ref M060 | F06533 | non-negotiable | false | 10 |
| R13032 | Composition — composes with M063 SFIF Features phase | cross-ref M063 | F06514 | non-negotiable | false | 10 |
| R13033 | Composition — composes with M075 SRP Oracle Core | cross-ref M075 | F06517 | non-negotiable | false | 10 |
| R13034 | Composition — composes with M077 NVFP4 (4-bit RL training path) | cross-ref M077 | F06515 | non-negotiable | false | 10 |
| R13035 | Composition — composes with selfdef MS003 chain-of-trust | cross-ref selfdef MS003 | F06492 | non-negotiable | false | 10 |
| R13036 | Composition — composes with selfdef MS007 typed-mirror | cross-ref selfdef MS007 | F06519 | non-negotiable | false | 10 |
| R13037 | Composition — composes with selfdef MS009 replay validator | cross-ref selfdef MS009 | F06529 | non-negotiable | false | 10 |
| R13038 | Composition — composes with selfdef MS026 observability + OCSF | cross-ref selfdef MS026 | F06526 | non-negotiable | false | 10 |
| R13039 | Composition — composes with selfdef MS036 sandbox tiers (trajectory sandboxing) | cross-ref selfdef MS036 | F06503 | non-negotiable | false | 10 |
| R13040 | Composition — composes with selfdef MS039 authority (training = L5 Commit) | cross-ref selfdef MS039 | F06487 | non-negotiable | false | 10 |
| R13041 | Composition — composes with selfdef MS040 profile envelopes | cross-ref selfdef MS040 | F06489 | non-negotiable | false | 10 |
| R13042 | Composition — composes with selfdef MS041 commit authority (L6 adapter promotion) | cross-ref selfdef MS041 | F06487 | non-negotiable | false | 10 |
| R13043 | Composition — composes with selfdef MS043 IPS operator surface | cross-ref selfdef MS043 | F06538 | non-negotiable | false | 10 |
| R13044 | Boundary — RL training = sovereign-os runtime | architecture + operator standing direction | F06467 | non-negotiable | false | 10 |
| R13045 | Boundary — selfdef IPS sandboxes trajectory sampling per MS036 | cross-ref selfdef MS036 | F06503 | non-negotiable | false | 10 |
| R13046 | Boundary — info-hub indexes HölderPO paper lineage as second-brain entry | operator standing direction | F06467 | non-negotiable | false | 10 |
| R13047 | Boundary — info-hub never mutated by HölderPO training | operator standing direction | F06467 | non-negotiable | false | 10 |
| R13048 | Doctrinal preservation — arXiv 2605.12058 abstract preserved verbatim in `backlog/notes/external-research-ingestion-2026-05-19.md` | operator standing direction | F06467 | non-negotiable | false | 10 |
| R13049 | Doctrinal preservation — "54.9% average accuracy" verbatim | arXiv 2605.12058 | F06478 | non-negotiable | false | 10 |
| R13050 | Doctrinal preservation — "7.2% relative gain over standard GRPO" verbatim | arXiv 2605.12058 | F06479 | non-negotiable | false | 10 |
| R13051 | Doctrinal preservation — "93.8% success rate on ALFWorld" verbatim | arXiv 2605.12058 | F06480 | non-negotiable | false | 10 |
| R13052 | Doctrinal preservation — "Hölder mean" verbatim with accent preserved | arXiv 2605.12058 | F06468 | non-negotiable | false | 10 |
| R13053 | Doctrinal preservation — operator standing direction "you cannot invent crap" upheld | operator standing direction | F06467 | non-negotiable | false | 10 |
| R13054 | Doctrinal preservation — operator standing direction "Respect the projects" upheld (RL training = sovereign-os; IPS enforces) | operator standing direction | F06044 | non-negotiable | false | 10 |
| R13055 | Doctrinal preservation — operator standing direction "second-brain" upheld | operator standing direction | F06046 | non-negotiable | false | 10 |
| R13056 | Doctrinal preservation — operator standing direction "layered ON TOP" upheld (M046 LoRA Foundry not discarded) | operator standing direction | F06486 | non-negotiable | false | 10 |
| R13057 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F06467 | non-negotiable | false | 10 |
| R13058 | Operator UX — operator may toggle HölderPO on/off per profile | operator standing direction "everything can be turned on and off" | F06539 | non-negotiable | false | 10 |
| R13059 | Operator UX — operator may select GRPO vs HölderPO per training run | operator standing direction "modes and profiles" | F06494 | non-negotiable | false | 10 |
| R13060 | Operator UX — operator may visualize p-schedule curve in D-10 dashboard | cross-ref M060 | F06534 | non-negotiable | false | 10 |
| R13061 | Operator UX — operator may compare HölderPO vs GRPO benchmark scores | cross-ref M060 | F06533 | non-negotiable | false | 10 |
| R13062 | Operator UX — operator may promote HölderPO-trained adapters via D-11 (signed) | cross-ref M060 + selfdef MS003 | F06535 | non-negotiable | false | 10 |
| R13063 | Performance — HölderPO training step latency `<=` 1.5x GRPO step latency on Blackwell | architecture | F06467 | non-negotiable | false | 10 |
| R13064 | Performance — convergence ≤ GRPO step count to reach equal benchmark score | arXiv 2605.12058 + architecture | F06481 | non-negotiable | false | 10 |
| R13065 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F06519 | non-negotiable | false | 10 |
| R13066 | Performance — replay validator daily run `<` 120s | cross-ref selfdef MS009 | F06529 | non-negotiable | false | 10 |
| R13067 | Performance — math benchmark suite full run `<` 30min on Blackwell | architecture | F06495 | non-negotiable | false | 10 |
| R13068 | Performance — ALFWorld benchmark full run `<` 60min | architecture | F06498 | non-negotiable | false | 10 |
| R13069 | Telemetry — training step count emitted via M049 | cross-ref M049 | F06524 | non-negotiable | false | 10 |
| R13070 | Telemetry — p-value over time emitted via M049 | cross-ref M049 | F06525 | non-negotiable | false | 10 |
| R13071 | Telemetry — gradient variance histogram emitted via M049 | cross-ref M049 | F06511 | non-negotiable | false | 10 |
| R13072 | Telemetry — reward-mean per group emitted via M049 | cross-ref M049 | F06504 | non-negotiable | false | 10 |
| R13073 | Telemetry — benchmark scores (math + ALFWorld) emitted via M049 | cross-ref M049 | F06496 | non-negotiable | false | 10 |
| R13074 | Operational — sovereign-holderpo.service systemd unit | architecture | F06499 | non-negotiable | false | 10 |
| R13075 | Operational — service pinned to CCD 1 (Blackwell IRQ adjacency per M070) | architecture + cross-ref M070 | F06517 | non-negotiable | false | 10 |
| R13076 | Operational — service honors SIGTERM (graceful drain + checkpoint) | architecture | F06518 | non-negotiable | false | 10 |
| R13077 | Operational — service refuses to start with chain-break in MS009 | cross-ref selfdef MS009 | F06529 | non-negotiable | false | 10 |
| R13078 | Operational — service refuses to start with missing MS003 keys | cross-ref selfdef MS003 | F06495 | non-negotiable | false | 10 |
| R13079 | Operational — service readiness probe at /run/sovereign-holderpo/ready | architecture | F06539 | non-negotiable | false | 10 |
| R13080 | Operational — service Wants=sovereign-os.target | architecture | F06539 | non-negotiable | false | 10 |
| R13081 | Operational — service After=sovereign-nvfp4-runtime.service (M077 ordering) | architecture + cross-ref M077 | F06515 | non-negotiable | false | 10 |
| R13082 | Operational — service emits start/stop via M049 | cross-ref M049 | F06524 | non-negotiable | false | 10 |
| R13083 | Operational — service tracks active runs in /var/lib/sovereign-os/holderpo-runs/ | architecture | F06539 | non-negotiable | false | 10 |
| R13084 | Closing — HölderPO covers arXiv 2605.12058 verbatim | arXiv 2605.12058 | F06467 | non-negotiable | false | 10 |
| R13085 | Closing — sovereign-os catalog at 77/77 milestones | architecture | F06545 | non-negotiable | false | 10 |
| R13086 | Closing — combined ecosystem 121 milestones | architecture | F06545 | non-negotiable | false | 10 |
| R13087 | Closing — combined R-rows ~23650 | architecture | F06545 | non-negotiable | false | 10 |
| R13088 | Closing — combined enforced sub-reqs ~236500 | architecture | F06545 | non-negotiable | false | 10 |
| R13089 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F06467 | non-negotiable | false | 10 |
| R13090 | Closing — M078 covers HölderPO + GRPO scope verbatim; M079 Activation Steering Surface next | arXiv 2605.12058 + operator standing direction | F06545 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M078.

## Cross-references

- **M046** — LoRA Foundry (HölderPO + GRPO trained adapters)
- **M048** — modules map (Eval-Value module reward signal)
- **M049** — observability + trace pipeline
- **M055** — failure modes (gradient collapse / variance explosion)
- **M057** — 12-step task lifecycle (Step 11 Learn integration)
- **M058** — hardware-aware scheduler (Blackwell oracle for training)
- **M060** — cockpit dashboards (D-01 / D-04 / D-10 / D-11)
- **M063** — SFIF Features phase
- **M070** — Dual-CCD topology (Blackwell IRQ adjacency)
- **M075** — SRP Oracle Core
- **M077** — NVFP4 (4-bit RL training path)
- **selfdef MS003** — selfdef-signing
- **selfdef MS007** — typed-mirror (sovereign-holderpo-mirror)
- **selfdef MS009** — replay validator
- **selfdef MS026** — OCSF event emission
- **selfdef MS036** — sandbox tiers (trajectory sandboxing)
- **selfdef MS039** — authority levels (training = L5 Commit)
- **selfdef MS040** — profile envelopes
- **selfdef MS041** — commit authority (L6 adapter promotion)
- **selfdef MS043** — IPS operator surface

## Schema

```
schema_version: "1.0.0"
milestone_id: M078
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
canonical_source: "arXiv 2605.12058 — Hölder Policy Optimisation (Chen et al., 2026-05-12)"
algorithms_cataloged:
  - GRPO (baseline)
  - HölderPO (Hölder-mean generalisation)
benchmark_targets:
  math_avg: "54.9% (+7.2% relative vs GRPO)"
  alfworld: "93.8%"
hoelder_parameter_p:
  domain: "float, operator-clamped default [-10, 10]"
  schedule_types: [Static, Linear, Exponential, Cosine, Step, Custom]
  dynamic_annealing: "progressively schedules p across training lifecycle"
trade_off:
  large_p: "amplifies sparse learning signals (gradient concentration)"
  small_p: "strictly bounds gradient variance"
typed_mirror_crate: sovereign-holderpo-mirror
catalog_status:
  sovereign_os: 77/77 milestones
  selfdef: 44/44 milestones
  combined: 121 milestones
```
