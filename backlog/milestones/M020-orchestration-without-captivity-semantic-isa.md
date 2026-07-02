# M020 — Orchestration without captivity — semantic ISA

> Parent: `backlog/milestones/INDEX.md` row M020 (dump 5369–5730).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 5369–5730.
> All entries below are extracted from the dump line range. No invention.

> **AVX++ canon update — 2026-05-19**: this milestone is affected by backward-sweep redefinition(s) — Core Law (CLARIFYING). See sovereign-os M061 for canonical pinning (commit 6f07dca). R-rows below are interpreted under the canonical later definitions per operator standing direction "layered: new direction ON TOP OF prior direction — never discarded".


## Epics (E0178–E0187)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0178 | Orchestration without captivity — learn from frameworks, do not become trapped | 5384–5395 |
| E0179 | Research substrate — Semantic Kernel / CrewAI Flows / AutoGen / OpenAI Swarm / Arbiter-K | 5388–5395 |
| E0180 | LLMs do not own the control loop | 5396–5400 |
| E0181 | Own primitives — 10-primitive contract (Agent / Tool / Branch / Message / MemoryRef / Capability / Policy / Checkpoint / Commit / Trace) | 5402–5432 |
| E0182 | Orchestration patterns as operators — sequential / concurrent / handoff / debate / cascade / tree-search / swarm / human-gate | 5434–5464 |
| E0183 | Runtime chooses shape — simple / hard-coding / ambiguous-research / UI / risky-file-edit recipes | 5466–5498 |
| E0184 | Creating intelligence — 8-axis combination (diverse-generation / selection-pressure / memory / tools / verification / feedback / constraint / search) + 7-step basic intelligence loop | 5500–5557 |
| E0185 | Agent Governance — 5 named failure modes + execution rings + kill switch + saga transactions + memory quarantine + identity gates | 5559–5587 |
| E0186 | Semantic ISA — 15-instruction set + per-instruction 6-field contract + AVX-512 bitfields | 5589–5637 |
| E0187 | No single profile — recipe bundles (careful_code_change / fast_answer) + 6 intelligence forms + Key Design Law ("Frameworks are plugins. Models are plugins. Backends are plugins. The deterministic runtime is the product.") | 5639–5728 |

## Modules (M00320–M00336)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00320 | Semantic Kernel adapter — sequential / concurrent / handoff / group-chat / Magentic orchestration patterns | 5390 | E0179 |
| M00321 | CrewAI Flows adapter — Crews (autonomous) vs Flows (controlled event-driven) | 5391 | E0179 |
| M00322 | AutoGen adapter — multi-agent conversation framework | 5392 | E0179 |
| M00323 | OpenAI Swarm conceptual reference — agents / tools / routines / handoffs (educational, not production) | 5393 | E0179 |
| M00324 | Arbiter-K substrate — wrap probabilistic models inside deterministic kernel | 5394 | E0180 |
| M00325 | Own-primitive contract — 10 primitives (Agent / Tool / Branch / Message / MemoryRef / Capability / Policy / Checkpoint / Commit / Trace) | 5408–5419 | E0181 |
| M00326 | Adapter surface — LangGraph / CrewAI / AutoGen / Semantic Kernel / OpenAI-compatible gateway / NIM-vLLM-SGLang-TensorRT-LLM backends | 5424–5430 | E0181 |
| M00327 | Orchestration operator — sequential (A → B → C) | 5439–5440 | E0182 |
| M00328 | Orchestration operator — concurrent (A, B, C in parallel) | 5442–5443 | E0182 |
| M00329 | Orchestration operator — handoff (A delegates to B by rule) | 5445–5446 | E0182 |
| M00330 | Orchestration operator — debate (A and B disagree, C judges) | 5448–5449 | E0182 |
| M00331 | Orchestration operator — cascade (small → medium → oracle if needed) | 5451–5452 | E0182 |
| M00332 | Orchestration operator — tree-search (expand → score → prune → verify) | 5454–5455 | E0182 |
| M00333 | Orchestration operator — swarm (many specialists, manager routes) | 5457–5458 | E0182 |
| M00334 | Orchestration operator — human-gate (pause → inspect → resume) | 5460–5461 | E0182 |
| M00335 | Semantic ISA instruction set — OBSERVE / RETRIEVE / DRAFT / VERIFY / CRITIQUE / PLAN / CALL_TOOL / WRITE_MEMORY / REQUEST_APPROVAL / COMMIT / ROLLBACK / HANDOFF / SPAWN_BRANCH / MERGE_BRANCH / KILL_BRANCH | 5595–5611 | E0186 |
| M00336 | Per-instruction contract — required_capabilities / input_schema / output_schema / side_effect_level / checkpoint_behavior / risk_class | 5615–5622 | E0186 |

## Features (F01616–F01700)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01616 | Toggle orchestration backend (native / langgraph / crewai / autogen / semantic_kernel) | 5424–5429 | M00326 | mode | true |
| F01617 | Profile knob — `orchestration_backend = native \| langgraph \| crewai \| autogen \| semantic_kernel` | 5424–5429 | M00326 | profile | true |
| F01618 | Env var `SOVEREIGN_ORCHESTRATION_BACKEND` | 5424–5429 | M00326 | env_var | true |
| F01619 | CLI `--orchestration-backend <name>` | 5424–5429 | M00326 | cli_verb | true |
| F01620 | Own-primitive contract — `Agent` primitive | 5409 | M00325 | data_model | false |
| F01621 | Own-primitive contract — `Tool` primitive | 5410 | M00325 | data_model | false |
| F01622 | Own-primitive contract — `Branch` primitive | 5411 | M00325 | data_model | false |
| F01623 | Own-primitive contract — `Message` primitive | 5412 | M00325 | data_model | false |
| F01624 | Own-primitive contract — `MemoryRef` primitive | 5413 | M00325 | data_model | false |
| F01625 | Own-primitive contract — `Capability` primitive | 5414 | M00325 | data_model | false |
| F01626 | Own-primitive contract — `Policy` primitive | 5415 | M00325 | data_model | false |
| F01627 | Own-primitive contract — `Checkpoint` primitive | 5416 | M00325 | data_model | false |
| F01628 | Own-primitive contract — `Commit` primitive | 5417 | M00325 | data_model | false |
| F01629 | Own-primitive contract — `Trace` primitive | 5418 | M00325 | data_model | false |
| F01630 | Adapter — LangGraph | 5424 | M00326 | composite | true |
| F01631 | Adapter — CrewAI | 5425 | M00326 | composite | true |
| F01632 | Adapter — AutoGen | 5426 | M00326 | composite | true |
| F01633 | Adapter — Semantic Kernel | 5427 | M00326 | composite | true |
| F01634 | Adapter — OpenAI-compatible model gateway | 5428 | M00326 | composite | true |
| F01635 | Adapter — NIM / vLLM / SGLang / TensorRT-LLM backend | 5429 | M00326 | composite | true |
| F01636 | Orchestration operator — sequential | 5439–5440 | M00327 | composite | true |
| F01637 | Orchestration operator — concurrent | 5442–5443 | M00328 | composite | true |
| F01638 | Orchestration operator — handoff | 5445–5446 | M00329 | composite | true |
| F01639 | Orchestration operator — debate | 5448–5449 | M00330 | composite | true |
| F01640 | Orchestration operator — cascade | 5451–5452 | M00331 | composite | true |
| F01641 | Orchestration operator — tree-search | 5454–5455 | M00332 | composite | true |
| F01642 | Orchestration operator — swarm | 5457–5458 | M00333 | composite | true |
| F01643 | Orchestration operator — human-gate | 5460–5461 | M00334 | composite | true |
| F01644 | Runtime task shape — simple → `sequential + small model` | 5471 | E0183 | composite | true |
| F01645 | Runtime task shape — hard coding → `retrieve → concurrent scout patches → oracle review → tool/test → commit` | 5476–5477 | E0183 | composite | true |
| F01646 | Runtime task shape — ambiguous research → `decompose → concurrent retrieval → debate → source verification → synthesis` | 5482–5483 | E0183 | composite | true |
| F01647 | Runtime task shape — UI/computer use → `perception loop → action proposal → policy gate → sandbox execute → observe` | 5488–5489 | E0183 | composite | true |
| F01648 | Runtime task shape — risky file edits → `scout proposal → deterministic diff validation → oracle review → human gate → apply` | 5494–5495 | E0183 | composite | true |
| F01649 | Intelligence-combination axis — diverse generation | 5507 | E0184 | composite | false |
| F01650 | Intelligence-combination axis — selection pressure | 5508 | E0184 | composite | false |
| F01651 | Intelligence-combination axis — memory | 5509 | E0184 | composite | false |
| F01652 | Intelligence-combination axis — tools | 5510 | E0184 | composite | false |
| F01653 | Intelligence-combination axis — verification | 5511 | E0184 | composite | false |
| F01654 | Intelligence-combination axis — feedback | 5512 | E0184 | composite | false |
| F01655 | Intelligence-combination axis — constraint | 5513 | E0184 | composite | false |
| F01656 | Intelligence-combination axis — search | 5514 | E0184 | composite | false |
| F01657 | Basic intelligence loop step 1 — Generate alternatives | 5524 | E0184 | composite | false |
| F01658 | Basic intelligence loop step 2 — Evaluate alternatives | 5525 | E0184 | composite | false |
| F01659 | Basic intelligence loop step 3 — Preserve useful state | 5526 | E0184 | composite | false |
| F01660 | Basic intelligence loop step 4 — Act in the world | 5527 | E0184 | composite | false |
| F01661 | Basic intelligence loop step 5 — Observe consequences | 5528 | E0184 | composite | false |
| F01662 | Basic intelligence loop step 6 — Update policy/memory | 5529 | E0184 | composite | false |
| F01663 | Basic intelligence loop step 7 — Repeat under constraints | 5530 | E0184 | composite | false |
| F01664 | Agent governance failure mode — goal hijacking | 5561 | E0185 | composite | false |
| F01665 | Agent governance failure mode — tool misuse | 5561 | E0185 | composite | false |
| F01666 | Agent governance failure mode — identity abuse | 5561 | E0185 | composite | false |
| F01667 | Agent governance failure mode — memory poisoning | 5561 | E0185 | composite | false |
| F01668 | Agent governance failure mode — cascading failures | 5561 | E0185 | composite | false |
| F01669 | Agent governance failure mode — rogue agents | 5561 | E0185 | composite | false |
| F01670 | Execution rings — ring 0 host deterministic kernel | 5567 | E0185 | composite | false |
| F01671 | Execution rings — ring 1 trusted model services | 5568 | E0185 | composite | false |
| F01672 | Execution rings — ring 2 sandboxed agents | 5569 | E0185 | composite | false |
| F01673 | Execution rings — ring 3 untrusted tools/web | 5570 | E0185 | composite | false |
| F01674 | Kill switch — stop all tool execution + freeze commits + preserve traces | 5573–5575 | E0185 | composite | false |
| F01675 | Saga transactions — multi-step tool actions with rollback/compensation | 5578 | E0185 | composite | true |
| F01676 | Memory quarantine — untrusted memory cannot poison policy until verified | 5580–5581 | E0185 | composite | false |
| F01677 | Identity gates — agents do not inherit user authority automatically | 5583–5584 | E0185 | composite | false |
| F01678 | Semantic ISA instruction — OBSERVE | 5596 | M00335 | composite | false |
| F01679 | Semantic ISA instruction — RETRIEVE | 5597 | M00335 | composite | false |
| F01680 | Semantic ISA instruction — DRAFT | 5598 | M00335 | composite | false |
| F01681 | Semantic ISA instruction — VERIFY | 5599 | M00335 | composite | false |
| F01682 | Semantic ISA instruction — CRITIQUE | 5600 | M00335 | composite | false |
| F01683 | Semantic ISA instruction — PLAN | 5601 | M00335 | composite | false |
| F01684 | Semantic ISA instruction — CALL_TOOL | 5602 | M00335 | composite | false |
| F01685 | Semantic ISA instruction — WRITE_MEMORY | 5603 | M00335 | composite | false |
| F01686 | Semantic ISA instruction — REQUEST_APPROVAL | 5604 | M00335 | composite | false |
| F01687 | Semantic ISA instruction — COMMIT | 5605 | M00335 | composite | false |
| F01688 | Semantic ISA instruction — ROLLBACK | 5606 | M00335 | composite | false |
| F01689 | Semantic ISA instruction — HANDOFF | 5607 | M00335 | composite | false |
| F01690 | Semantic ISA instruction — SPAWN_BRANCH | 5608 | M00335 | composite | false |
| F01691 | Semantic ISA instruction — MERGE_BRANCH | 5609 | M00335 | composite | false |
| F01692 | Semantic ISA instruction — KILL_BRANCH | 5610 | M00335 | composite | false |
| F01693 | ISA contract field — required_capabilities | 5616 | M00336 | data_model | false |
| F01694 | ISA contract field — input_schema | 5617 | M00336 | data_model | false |
| F01695 | ISA contract field — output_schema | 5618 | M00336 | data_model | false |
| F01696 | ISA contract field — side_effect_level | 5619 | M00336 | data_model | false |
| F01697 | ISA contract field — checkpoint_behavior | 5620 | M00336 | data_model | false |
| F01698 | ISA contract field — risk_class | 5621 | M00336 | data_model | false |
| F01699 | Recipe bundle example — `careful_code_change` (5 operators + write_files gated + network deny-by-default + oracle_required) | 5643–5657 | E0187 | composite | true |
| F01700 | Composite — Key Design Law "Frameworks are plugins. Models are plugins. Backends are plugins. The deterministic runtime is the product." | 5705–5708 | E0187 | composite | false |

## Requirements (R03231–R03400)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R03231 | Learn from agent frameworks, do not become trapped inside one | 5386 | E0178 | non-negotiable | false | 10 |
| R03232 | Semantic Kernel supports concurrent / sequential / handoff / group chat / Magentic-style coordination | 5390 | M00320 | non-negotiable | false | 10 |
| R03233 | CrewAI splits Crews (autonomous) from Flows (controlled event-driven) | 5391 | M00321 | non-negotiable | false | 10 |
| R03234 | AutoGen is a multi-agent conversation framework | 5392 | M00322 | non-negotiable | false | 10 |
| R03235 | OpenAI Swarm is educational, not production substrate | 5393 | M00323 | non-negotiable | false | 10 |
| R03236 | Arbiter-K argues delegating control loop to LLMs is fragile; wraps probabilistic models in deterministic kernel | 5394 | M00324 | non-negotiable | false | 10 |
| R03237 | LLMs do not own the control loop | 5399 | E0180 | non-negotiable | false | 10 |
| R03238 | Frameworks are useful as adapters or inspiration, not the brain | 5404 | E0181 | non-negotiable | false | 10 |
| R03239 | Own primitive — Agent | 5409 | M00325 | non-negotiable | false | 10 |
| R03240 | Own primitive — Tool | 5410 | M00325 | non-negotiable | false | 10 |
| R03241 | Own primitive — Branch | 5411 | M00325 | non-negotiable | false | 10 |
| R03242 | Own primitive — Message | 5412 | M00325 | non-negotiable | false | 10 |
| R03243 | Own primitive — MemoryRef | 5413 | M00325 | non-negotiable | false | 10 |
| R03244 | Own primitive — Capability | 5414 | M00325 | non-negotiable | false | 10 |
| R03245 | Own primitive — Policy | 5415 | M00325 | non-negotiable | false | 10 |
| R03246 | Own primitive — Checkpoint | 5416 | M00325 | non-negotiable | false | 10 |
| R03247 | Own primitive — Commit | 5417 | M00325 | non-negotiable | false | 10 |
| R03248 | Own primitive — Trace | 5418 | M00325 | non-negotiable | false | 10 |
| R03249 | Adapter outward — LangGraph | 5424 | M00326 | non-negotiable | true | 10 |
| R03250 | Adapter outward — CrewAI | 5425 | M00326 | non-negotiable | true | 10 |
| R03251 | Adapter outward — AutoGen | 5426 | M00326 | non-negotiable | true | 10 |
| R03252 | Adapter outward — Semantic Kernel | 5427 | M00326 | non-negotiable | true | 10 |
| R03253 | Adapter outward — OpenAI-compatible model gateway | 5428 | M00326 | non-negotiable | true | 10 |
| R03254 | Adapter outward — NIM / vLLM / SGLang / TensorRT-LLM backend | 5429 | M00326 | non-negotiable | true | 10 |
| R03255 | Deterministic runtime remains the center | 5432 | E0181 | non-negotiable | false | 10 |
| R03256 | Expose orchestration operators instead of hardcoding one agent style | 5436 | E0182 | non-negotiable | false | 10 |
| R03257 | Orchestration operator — sequential `A -> B -> C` | 5439–5440 | M00327 | non-negotiable | false | 10 |
| R03258 | Orchestration operator — concurrent `A, B, C in parallel` | 5442–5443 | M00328 | non-negotiable | false | 10 |
| R03259 | Orchestration operator — handoff `A delegates to B by rule` | 5445–5446 | M00329 | non-negotiable | false | 10 |
| R03260 | Orchestration operator — debate `A and B disagree, C judges` | 5448–5449 | M00330 | non-negotiable | false | 10 |
| R03261 | Orchestration operator — cascade `small -> medium -> oracle if needed` | 5451–5452 | M00331 | non-negotiable | false | 10 |
| R03262 | Orchestration operator — tree-search `expand -> score -> prune -> verify` | 5454–5455 | M00332 | non-negotiable | false | 10 |
| R03263 | Orchestration operator — swarm `many specialists, manager routes` | 5457–5458 | M00333 | non-negotiable | false | 10 |
| R03264 | Orchestration operator — human-gate `pause -> inspect -> resume` | 5460–5461 | M00334 | non-negotiable | false | 10 |
| R03265 | Orchestration operators are composable execution shapes, not profiles | 5464 | E0182 | non-negotiable | false | 10 |
| R03266 | Runtime chooses shape — simple → sequential + small model | 5471 | E0183 | non-negotiable | true | 10 |
| R03267 | Runtime chooses shape — hard coding task → retrieve / concurrent scout patches / oracle review / tool+test / commit | 5476–5477 | E0183 | non-negotiable | true | 10 |
| R03268 | Runtime chooses shape — ambiguous research → decompose / concurrent retrieval / debate / source verification / synthesis | 5482–5483 | E0183 | non-negotiable | true | 10 |
| R03269 | Runtime chooses shape — UI/computer use → perception loop / action proposal / policy gate / sandbox execute / observe | 5488–5489 | E0183 | non-negotiable | true | 10 |
| R03270 | Runtime chooses shape — risky file edits → scout proposal / deterministic diff validation / oracle review / human gate / apply | 5494–5495 | E0183 | non-negotiable | true | 10 |
| R03271 | This is how we avoid locking into one "agent personality" | 5498 | E0183 | non-negotiable | false | 10 |
| R03272 | The phrase "create intelligence" is important | 5502 | E0184 | non-negotiable | false | 10 |
| R03273 | Intelligence created by combining — diverse generation | 5507 | E0184 | non-negotiable | false | 10 |
| R03274 | Intelligence created by combining — selection pressure | 5508 | E0184 | non-negotiable | false | 10 |
| R03275 | Intelligence created by combining — memory | 5509 | E0184 | non-negotiable | false | 10 |
| R03276 | Intelligence created by combining — tools | 5510 | E0184 | non-negotiable | false | 10 |
| R03277 | Intelligence created by combining — verification | 5511 | E0184 | non-negotiable | false | 10 |
| R03278 | Intelligence created by combining — feedback | 5512 | E0184 | non-negotiable | false | 10 |
| R03279 | Intelligence created by combining — constraint | 5513 | E0184 | non-negotiable | false | 10 |
| R03280 | Intelligence created by combining — search | 5514 | E0184 | non-negotiable | false | 10 |
| R03281 | A model alone is a learned prior | 5517 | E0184 | non-negotiable | false | 10 |
| R03282 | The runtime adds agency | 5519 | E0184 | non-negotiable | false | 10 |
| R03283 | Basic intelligence loop step 1 — Generate alternatives | 5524 | E0184 | non-negotiable | false | 10 |
| R03284 | Basic intelligence loop step 2 — Evaluate alternatives | 5525 | E0184 | non-negotiable | false | 10 |
| R03285 | Basic intelligence loop step 3 — Preserve useful state | 5526 | E0184 | non-negotiable | false | 10 |
| R03286 | Basic intelligence loop step 4 — Act in the world | 5527 | E0184 | non-negotiable | false | 10 |
| R03287 | Basic intelligence loop step 5 — Observe consequences | 5528 | E0184 | non-negotiable | false | 10 |
| R03288 | Basic intelligence loop step 6 — Update policy/memory | 5529 | E0184 | non-negotiable | false | 10 |
| R03289 | Basic intelligence loop step 7 — Repeat under constraints | 5530 | E0184 | non-negotiable | false | 10 |
| R03290 | This is the operating system of intelligence | 5533 | E0184 | non-negotiable | false | 10 |
| R03291 | Hardware mapping — Generate alternatives uses 4090 scout / small models / Ling-Nemotron executors | 5538–5539 | E0184 | non-negotiable | false | 10 |
| R03292 | Hardware mapping — Evaluate uses AVX-512 filters / oracle model / tests / tools | 5541–5542 | E0184 | non-negotiable | false | 10 |
| R03293 | Hardware mapping — Preserve state uses RAM/ZFS / replay logs / memory index / skill library | 5544–5545 | E0184 | non-negotiable | false | 10 |
| R03294 | Hardware mapping — Act uses sandboxed tools / shell / browser / code / APIs | 5547–5548 | E0184 | non-negotiable | false | 10 |
| R03295 | Hardware mapping — Observe uses eBPF / DCGM / test output / tool results / human feedback | 5550–5551 | E0184 | non-negotiable | false | 10 |
| R03296 | Hardware mapping — Update uses policy records / routing stats / reflections / skills | 5553–5554 | E0184 | non-negotiable | false | 10 |
| R03297 | Machine intelligence is not just in weights — it is in the loop | 5557 | E0184 | non-negotiable | false | 10 |
| R03298 | Agent governance — goal hijacking is a named failure mode | 5561 | E0185 | non-negotiable | false | 10 |
| R03299 | Agent governance — tool misuse is a named failure mode | 5561 | E0185 | non-negotiable | false | 10 |
| R03300 | Agent governance — identity abuse is a named failure mode | 5561 | E0185 | non-negotiable | false | 10 |
| R03301 | Agent governance — memory poisoning is a named failure mode | 5561 | E0185 | non-negotiable | false | 10 |
| R03302 | Agent governance — cascading failures is a named failure mode | 5561 | E0185 | non-negotiable | false | 10 |
| R03303 | Agent governance — rogue agents is a named failure mode | 5561 | E0185 | non-negotiable | false | 10 |
| R03304 | Execution rings — ring 0 host deterministic kernel | 5567 | E0185 | non-negotiable | false | 10 |
| R03305 | Execution rings — ring 1 trusted model services | 5568 | E0185 | non-negotiable | false | 10 |
| R03306 | Execution rings — ring 2 sandboxed agents | 5569 | E0185 | non-negotiable | false | 10 |
| R03307 | Execution rings — ring 3 untrusted tools/web | 5570 | E0185 | non-negotiable | false | 10 |
| R03308 | Kill switch — stop all tool execution | 5573 | E0185 | non-negotiable | false | 10 |
| R03309 | Kill switch — freeze commits | 5574 | E0185 | non-negotiable | false | 10 |
| R03310 | Kill switch — preserve traces | 5575 | E0185 | non-negotiable | false | 10 |
| R03311 | Saga transactions — multi-step tool actions with rollback/compensation | 5578 | E0185 | non-negotiable | true | 10 |
| R03312 | Memory quarantine — untrusted memory cannot poison policy until verified | 5580–5581 | E0185 | non-negotiable | false | 10 |
| R03313 | Identity gates — agents do not inherit user authority automatically | 5583–5584 | E0185 | non-negotiable | false | 10 |
| R03314 | These are what makes autonomy survivable | 5587 | E0185 | non-negotiable | false | 10 |
| R03315 | Semantic ISA — define a small instruction set for agent actions | 5593 | E0186 | non-negotiable | false | 10 |
| R03316 | Semantic ISA instruction — OBSERVE | 5596 | M00335 | non-negotiable | false | 10 |
| R03317 | Semantic ISA instruction — RETRIEVE | 5597 | M00335 | non-negotiable | false | 10 |
| R03318 | Semantic ISA instruction — DRAFT | 5598 | M00335 | non-negotiable | false | 10 |
| R03319 | Semantic ISA instruction — VERIFY | 5599 | M00335 | non-negotiable | false | 10 |
| R03320 | Semantic ISA instruction — CRITIQUE | 5600 | M00335 | non-negotiable | false | 10 |
| R03321 | Semantic ISA instruction — PLAN | 5601 | M00335 | non-negotiable | false | 10 |
| R03322 | Semantic ISA instruction — CALL_TOOL | 5602 | M00335 | non-negotiable | false | 10 |
| R03323 | Semantic ISA instruction — WRITE_MEMORY | 5603 | M00335 | non-negotiable | false | 10 |
| R03324 | Semantic ISA instruction — REQUEST_APPROVAL | 5604 | M00335 | non-negotiable | false | 10 |
| R03325 | Semantic ISA instruction — COMMIT | 5605 | M00335 | non-negotiable | false | 10 |
| R03326 | Semantic ISA instruction — ROLLBACK | 5606 | M00335 | non-negotiable | false | 10 |
| R03327 | Semantic ISA instruction — HANDOFF | 5607 | M00335 | non-negotiable | false | 10 |
| R03328 | Semantic ISA instruction — SPAWN_BRANCH | 5608 | M00335 | non-negotiable | false | 10 |
| R03329 | Semantic ISA instruction — MERGE_BRANCH | 5609 | M00335 | non-negotiable | false | 10 |
| R03330 | Semantic ISA instruction — KILL_BRANCH | 5610 | M00335 | non-negotiable | false | 10 |
| R03331 | Each instruction has required capabilities | 5616 | M00336 | non-negotiable | false | 10 |
| R03332 | Each instruction has input schema | 5617 | M00336 | non-negotiable | false | 10 |
| R03333 | Each instruction has output schema | 5618 | M00336 | non-negotiable | false | 10 |
| R03334 | Each instruction has side-effect level | 5619 | M00336 | non-negotiable | false | 10 |
| R03335 | Each instruction has checkpoint behavior | 5620 | M00336 | non-negotiable | false | 10 |
| R03336 | Each instruction has risk class | 5621 | M00336 | non-negotiable | false | 10 |
| R03337 | The LLM does not run free-form — it emits semantic instructions | 5624–5625 | E0186 | non-negotiable | false | 10 |
| R03338 | CPU/runtime executes or rejects semantic instructions | 5626 | E0186 | non-negotiable | false | 10 |
| R03339 | AVX-512 bitfields become structural — instruction_id | 5631 | E0186 | non-negotiable | false | 10 |
| R03340 | AVX-512 bitfields become structural — capability_mask | 5632 | E0186 | non-negotiable | false | 10 |
| R03341 | AVX-512 bitfields become structural — risk_mask | 5633 | E0186 | non-negotiable | false | 10 |
| R03342 | AVX-512 bitfields become structural — state_mask | 5634 | E0186 | non-negotiable | false | 10 |
| R03343 | AVX-512 bitfields become structural — route_mask | 5635 | E0186 | non-negotiable | false | 10 |
| R03344 | AVX-512 bitfields become structural — commit_mask | 5636 | E0186 | non-negotiable | false | 10 |
| R03345 | Define recipe bundles, not "research agent" or "coding agent" profiles | 5641 | E0187 | non-negotiable | false | 10 |
| R03346 | Recipe bundle — `careful_code_change` retrieve / draft_parallel / oracle_review / sandbox_test / human_gate_if_high_risk / commit | 5645–5651 | E0187 | non-negotiable | true | 10 |
| R03347 | Recipe bundle — `careful_code_change` policy write_files=gated | 5653 | E0187 | non-negotiable | true | 10 |
| R03348 | Recipe bundle — `careful_code_change` policy network=deny_by_default | 5654 | E0187 | non-negotiable | true | 10 |
| R03349 | Recipe bundle — `careful_code_change` policy oracle_required=true | 5655 | E0187 | non-negotiable | true | 10 |
| R03350 | Recipe bundle — `fast_answer` route / retrieve_light / generate / validate | 5662–5666 | E0187 | non-negotiable | true | 10 |
| R03351 | Recipe bundle — `fast_answer` policy oracle_required=false | 5668 | E0187 | non-negotiable | true | 10 |
| R03352 | Recipe bundle — `fast_answer` policy max_latency_ms=1500 | 5669 | E0187 | non-negotiable | true | 10 |
| R03353 | Router chooses or composes recipes | 5673 | E0187 | non-negotiable | false | 10 |
| R03354 | Intelligence form — fast reflex intelligence (small/scout model + policy) | 5680–5681 | E0187 | non-negotiable | false | 10 |
| R03355 | Intelligence form — deliberative intelligence (tree/debate + oracle) | 5683–5684 | E0187 | non-negotiable | false | 10 |
| R03356 | Intelligence form — embodied tool intelligence (observe-act loops in sandbox) | 5686–5687 | E0187 | non-negotiable | false | 10 |
| R03357 | Intelligence form — institutional intelligence (memory, skills, replay, policies) | 5689–5690 | E0187 | non-negotiable | false | 10 |
| R03358 | Intelligence form — scientific intelligence (hypothesis → experiment → result → reflection) | 5692–5693 | E0187 | non-negotiable | false | 10 |
| R03359 | Intelligence form — engineering intelligence (patch → test → diagnose → improve) | 5695–5696 | E0187 | non-negotiable | false | 10 |
| R03360 | Same station, different orchestration | 5699 | E0187 | non-negotiable | false | 10 |
| R03361 | Key Design Law — Frameworks are plugins | 5705 | E0187 | non-negotiable | false | 10 |
| R03362 | Key Design Law — Models are plugins | 5706 | E0187 | non-negotiable | false | 10 |
| R03363 | Key Design Law — Backends are plugins | 5707 | E0187 | non-negotiable | false | 10 |
| R03364 | Key Design Law — The deterministic runtime is the product | 5708 | E0187 | non-negotiable | false | 10 |
| R03365 | This is how the station stays future-proof | 5711 | E0187 | non-negotiable | false | 10 |
| R03366 | When new model arrives, do NOT redesign the system | 5713 | E0187 | non-negotiable | false | 10 |
| R03367 | When new model arrives, ADD — model card | 5717 | E0187 | non-negotiable | false | 10 |
| R03368 | When new model arrives, ADD — capability profile | 5718 | E0187 | non-negotiable | false | 10 |
| R03369 | When new model arrives, ADD — routing stats | 5719 | E0187 | non-negotiable | false | 10 |
| R03370 | When new model arrives, ADD — serving backend | 5720 | E0187 | non-negotiable | false | 10 |
| R03371 | When new model arrives, ADD — precision options | 5721 | E0187 | non-negotiable | false | 10 |
| R03372 | When new model arrives, ADD — trust score | 5722 | E0187 | non-negotiable | false | 10 |
| R03373 | Then the runtime learns where it belongs | 5724 | E0187 | non-negotiable | false | 10 |
| R03374 | Ultimate station — built as substrate that absorbs the future, not frozen present | 5728 | E0187 | non-negotiable | false | 10 |
| R03375 | Orchestration backend operator-overrideable (native / langgraph / crewai / autogen / semantic_kernel) | 5424–5429 | F01616 | non-negotiable | true | 10 |
| R03376 | Env var `SOVEREIGN_ORCHESTRATION_BACKEND` | 5424–5429 | F01618 | non-negotiable | true | 10 |
| R03377 | CLI `--orchestration-backend <name>` | 5424–5429 | F01619 | non-negotiable | true | 10 |
| R03378 | Test — 10-primitive contract round-trips through API | 5408–5419 | M00325 | non-negotiable | false | 10 |
| R03379 | Test — each of 8 orchestration operators executes its declared signature on sample task | 5439–5461 | E0182 | non-negotiable | false | 10 |
| R03380 | Test — each of 5 named runtime task shapes runs end-to-end on representative input | 5468–5495 | E0183 | non-negotiable | false | 10 |
| R03381 | Test — each of 6 named agent-governance failure modes detected by runtime invariant checks | 5561 | E0185 | non-negotiable | false | 10 |
| R03382 | Test — execution-ring boundaries enforced (ring-2 cannot escalate to ring-1) | 5567–5570 | E0185 | non-negotiable | false | 10 |
| R03383 | Test — kill switch halts all tool execution within bounded time | 5572–5575 | E0185 | non-negotiable | false | 10 |
| R03384 | Test — saga transaction rolls back on partial failure | 5578 | E0185 | non-negotiable | true | 10 |
| R03385 | Test — memory quarantine prevents unverified memory from feeding policy | 5580–5581 | E0185 | non-negotiable | false | 10 |
| R03386 | Test — identity gate refuses agent action that requires user-authority not granted | 5583–5584 | E0185 | non-negotiable | false | 10 |
| R03387 | Test — each of 15 Semantic ISA instructions round-trips through encode/decode | 5595–5611 | M00335 | non-negotiable | false | 10 |
| R03388 | Test — each ISA contract field present + non-empty for every shipped instruction | 5615–5622 | M00336 | non-negotiable | false | 10 |
| R03389 | Test — recipe loader rejects YAML missing required `policies` block | 5643–5657 | E0187 | non-negotiable | false | 10 |
| R03390 | API `POST /v1/isa/encode` (returns bitfield-packed instruction) | 5615–5637 | M00336 | non-negotiable | true | 10 |
| R03391 | API `POST /v1/isa/execute` (executes instruction; honors capabilities; emits trace) | 5615–5637 | M00336 | non-negotiable | true | 10 |
| R03392 | API `GET /v1/orchestrators` (lists 8 named operators with their signature) | 5439–5461 | E0182 | non-negotiable | true | 10 |
| R03393 | API `POST /v1/recipes/{name}/run` (executes recipe bundle) | 5643–5672 | E0187 | non-negotiable | true | 10 |
| R03394 | Dashboard — Semantic ISA instruction-flow timeline (15-row, per-branch) | 5589–5637 | M00335 | non-negotiable | true | 10 |
| R03395 | Dashboard — orchestration-operator usage histogram (which of 8 fires per task type) | 5439–5461 | E0182 | non-negotiable | true | 10 |
| R03396 | Dashboard — execution-ring occupancy + cross-ring transitions | 5567–5570 | E0185 | non-negotiable | true | 10 |
| R03397 | Dashboard — kill-switch status (armed / fired / cleared) | 5572–5575 | E0185 | non-negotiable | true | 10 |
| R03398 | Composite — Key Design Law enforced runtime-wide (frameworks/models/backends are plugins; deterministic runtime is the product) | 5705–5708 | E0187 | non-negotiable | false | 10 |
| R03399 | Composite — semantic ISA bitfields integrate with M008 AVX-512 features (VPTERNLOG / k-mask / VPCONFLICT) for batch validation | 5631–5637 | M00335 | non-negotiable | false | 10 |
| R03400 | Composite — Orchestration-without-captivity is the meta-product of M015 programming plane + M017 model portfolio + M018 serving fabric + M019 cognitive operators (all framework-agnostic, runtime-centric) | 5701–5728 | E0187 | non-negotiable | false | 10 |

— End of M020 milestone file.
