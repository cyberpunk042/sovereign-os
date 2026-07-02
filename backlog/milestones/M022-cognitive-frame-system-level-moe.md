# M022 — Cognitive Frame — system-level MoE

> Parent: `backlog/milestones/INDEX.md` row M022 (dump 6046–6366).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 6046–6366.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0198–E0207)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0198 | Industry convergence on event-driven / durable / model-agnostic workflows | 6063–6068 |
| E0199 | Research substrate — LlamaIndex Workflows (event-driven) + Temporal (durable execution) + Ray Serve LLM (engine-agnostic + prefill-decode disaggregation) + production-agent pain (state drift / schema drift / mid-run failure / tool misuse / orchestration chaos) | 6065–6068 |
| E0200 | Intelligence needs a spine — Models = nervous tissue / Workflows = spine / Logic = immune system / REPL+tools = hands / Memory = body | 6070–6076 |
| E0201 | Unified execution model — `CognitiveFrame` is the universal cognition/work unit (8-field struct) | 6078–6111 |
| E0202 | The Frame Loop — 6-step generalized REPL (READ / ROUTE / EVALUATE / OBSERVE / COMMIT / LOOP) | 6113–6135 |
| E0203 | Where each concept fits — REPL / CoT / ToT-GoT / MoE / Workflow / Logic / Intelligence | 6137–6160 |
| E0204 | The Big Move — System-Level MoE routes Frames to 11 named experts | 6162–6192 |
| E0205 | AVX-512 router — bulk frame evaluation + 7 named masks + 6 named queues | 6194–6219 |
| E0206 | CoT becomes data, not authority — model CoT converts to typed Frames (ToolIntentFrame / HypothesisFrame) | 6221–6247 |
| E0207 | Holding it properly — 9 system artifacts (Frame / Event / Expert / Router / Workflow / Policy / Replay / Memory / Eval) + closing sentence | 6249–6364 |

## Modules (M00354–M00370)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00354 | LlamaIndex Workflows substrate — event-driven steps handle and emit events | 6065 | E0199 |
| M00355 | Temporal substrate — durable execution resumes after crashes / network failures / long delays | 6066 | E0199 |
| M00356 | Ray Serve LLM substrate — engine-agnostic LLM serving (vLLM/SGLang) + OpenAI-compatible APIs + prefill-decode disaggregation | 6067 | E0199 |
| M00357 | `CognitiveFrame` struct — id / parent / workflow_node / control / capability / evidence / memory_ref / trace_ref | 6084–6094 | E0201 |
| M00358 | Frame variant catalog — thought / branch / tool-call / model-request / workflow-step / memory-write / verification-task / REPL-execution / candidate-answer | 6097–6109 | E0201 |
| M00359 | Frame loop step — READ (ingest user/task/tool observation/memory event) | 6116–6117 | E0202 |
| M00360 | Frame loop step — ROUTE (choose expert: oracle / scout / REPL / memory / human / tool) | 6119–6120 | E0202 |
| M00361 | Frame loop step — EVALUATE (model inference / deterministic logic / parser / test / retrieval) | 6122–6123 | E0202 |
| M00362 | Frame loop step — OBSERVE (capture result / metrics / side effects) | 6125–6126 | E0202 |
| M00363 | Frame loop step — COMMIT (accept/reject/update state under policy) | 6128–6129 | E0202 |
| M00364 | Frame loop step — LOOP (emit next frames) | 6131–6132 | E0202 |
| M00365 | System-MoE expert registry — Blackwell oracle / 4090 scout / Nano perception / embedding / reranker / Python REPL / shell sandbox / simdjson validator / Hyperscan policy scanner / ZFS replay store / human approval | 6178–6190 | E0204 |
| M00366 | AVX-512 router 7 named masks — alive_mask / tool_mask / oracle_mask / scout_mask / repl_mask / memory_mask / human_mask | 6199–6206 | E0205 |
| M00367 | AVX-512 router 6 named queues — oracle_queue / scout_queue / repl_queue / tool_queue / human_queue / memory_queue | 6211–6217 | E0205 |
| M00368 | CoT-to-Frame conversion — model prose → ToolIntentFrame / HypothesisFrame | 6225–6245 | E0206 |
| M00369 | REPL-attaches-language-to-reality — can-execute / can-parse / can-test / can-measure routing decision | 6255–6263 | E0203 |
| M00370 | 9-artifact system primitives — Frame / Event / Expert / Router / Workflow / Policy / Replay / Memory / Eval | 6326–6354 | E0207 |

## Features (F01786–F01870)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01786 | Toggle workflow backend (native / llamaindex-bridge / temporal-bridge / ray-serve-bridge) | 6065–6067 | E0199 | mode | true |
| F01787 | Profile knob — `workflow_backend = native \| llamaindex \| temporal \| ray_serve` | 6065–6067 | E0199 | profile | true |
| F01788 | Env var `SOVEREIGN_WORKFLOW_BACKEND` | 6065–6067 | E0199 | env_var | true |
| F01789 | CLI `--workflow-backend <name>` | 6065–6067 | E0199 | cli_verb | true |
| F01790 | Production-agent failure mode — state drift catalog | 6068 | E0199 | composite | false |
| F01791 | Production-agent failure mode — schema drift catalog | 6068 | E0199 | composite | false |
| F01792 | Production-agent failure mode — mid-run failure catalog | 6068 | E0199 | composite | false |
| F01793 | Production-agent failure mode — tool misuse catalog | 6068 | E0199 | composite | false |
| F01794 | Production-agent failure mode — orchestration chaos catalog | 6068 | E0199 | composite | false |
| F01795 | Spine analogy — Models = nervous tissue | 6076 | E0200 | composite | false |
| F01796 | Spine analogy — Workflows = spine | 6076 | E0200 | composite | false |
| F01797 | Spine analogy — Logic = immune system | 6076 | E0200 | composite | false |
| F01798 | Spine analogy — REPL+tools = hands | 6076 | E0200 | composite | false |
| F01799 | Spine analogy — Memory = body | 6076 | E0200 | composite | false |
| F01800 | `CognitiveFrame` field — `id` (u64) | 6086 | M00357 | data_model | false |
| F01801 | `CognitiveFrame` field — `parent` (u64) | 6087 | M00357 | data_model | false |
| F01802 | `CognitiveFrame` field — `workflow_node` (u64) | 6088 | M00357 | data_model | false |
| F01803 | `CognitiveFrame` field — `control` (u64) | 6089 | M00357 | data_model | false |
| F01804 | `CognitiveFrame` field — `capability` (u64) | 6090 | M00357 | data_model | false |
| F01805 | `CognitiveFrame` field — `evidence` (u64) | 6091 | M00357 | data_model | false |
| F01806 | `CognitiveFrame` field — `memory_ref` (u64) | 6092 | M00357 | data_model | false |
| F01807 | `CognitiveFrame` field — `trace_ref` (u64) | 6093 | M00357 | data_model | false |
| F01808 | Frame variant — thought | 6100 | M00358 | composite | false |
| F01809 | Frame variant — branch | 6101 | M00358 | composite | false |
| F01810 | Frame variant — tool call | 6102 | M00358 | composite | false |
| F01811 | Frame variant — model request | 6103 | M00358 | composite | false |
| F01812 | Frame variant — workflow step | 6104 | M00358 | composite | false |
| F01813 | Frame variant — memory write | 6105 | M00358 | composite | false |
| F01814 | Frame variant — verification task | 6106 | M00358 | composite | false |
| F01815 | Frame variant — REPL execution | 6107 | M00358 | composite | false |
| F01816 | Frame variant — candidate answer | 6108 | M00358 | composite | false |
| F01817 | Frame-loop step 1 — READ | 6116 | M00359 | composite | false |
| F01818 | Frame-loop step 2 — ROUTE | 6119 | M00360 | composite | false |
| F01819 | Frame-loop step 3 — EVALUATE | 6122 | M00361 | composite | false |
| F01820 | Frame-loop step 4 — OBSERVE | 6125 | M00362 | composite | false |
| F01821 | Frame-loop step 5 — COMMIT | 6128 | M00363 | composite | false |
| F01822 | Frame-loop step 6 — LOOP | 6131 | M00364 | composite | false |
| F01823 | System-MoE expert — Blackwell oracle | 6179 | M00365 | composite | false |
| F01824 | System-MoE expert — 4090 scout | 6180 | M00365 | composite | false |
| F01825 | System-MoE expert — Nano perception model | 6181 | M00365 | composite | false |
| F01826 | System-MoE expert — embedding model | 6182 | M00365 | composite | false |
| F01827 | System-MoE expert — reranker | 6183 | M00365 | composite | false |
| F01828 | System-MoE expert — Python REPL | 6184 | M00365 | composite | false |
| F01829 | System-MoE expert — shell sandbox | 6185 | M00365 | composite | false |
| F01830 | System-MoE expert — simdjson validator | 6186 | M00365 | composite | false |
| F01831 | System-MoE expert — Hyperscan policy scanner | 6187 | M00365 | composite | false |
| F01832 | System-MoE expert — ZFS replay store | 6188 | M00365 | composite | false |
| F01833 | System-MoE expert — human approval | 6189 | M00365 | composite | false |
| F01834 | AVX-512 router mask — `alive_mask = budget > 0` | 6199 | M00366 | composite | false |
| F01835 | AVX-512 router mask — `tool_mask = capability & requested_tool` | 6200 | M00366 | composite | false |
| F01836 | AVX-512 router mask — `oracle_mask = risk_high \| final_commit` | 6201 | M00366 | composite | false |
| F01837 | AVX-512 router mask — `scout_mask = low_risk & needs_draft` | 6202 | M00366 | composite | false |
| F01838 | AVX-512 router mask — `repl_mask = executable_check_needed` | 6203 | M00366 | composite | false |
| F01839 | AVX-512 router mask — `memory_mask = retrieval_needed` | 6204 | M00366 | composite | false |
| F01840 | AVX-512 router mask — `human_mask = side_effect_high` | 6205 | M00366 | composite | false |
| F01841 | AVX-512 dense queue — oracle_queue | 6212 | M00367 | data_model | false |
| F01842 | AVX-512 dense queue — scout_queue | 6213 | M00367 | data_model | false |
| F01843 | AVX-512 dense queue — repl_queue | 6214 | M00367 | data_model | false |
| F01844 | AVX-512 dense queue — tool_queue | 6215 | M00367 | data_model | false |
| F01845 | AVX-512 dense queue — human_queue | 6216 | M00367 | data_model | false |
| F01846 | AVX-512 dense queue — memory_queue | 6217 | M00367 | data_model | false |
| F01847 | CoT-to-Frame example — "I should inspect package.json" → `ToolIntentFrame { tool: read_file, path: package.json, side_effect: none }` | 6226–6230 | M00368 | composite | true |
| F01848 | CoT-to-Frame example — "The bug may be in parser.ts" → `HypothesisFrame { target: parser.ts, confidence: 0.62 }` | 6232–6236 | M00368 | composite | true |
| F01849 | CoT-to-Frame example — "Run tests" → `ToolIntentFrame { command: npm test, risk: low/medium, requires_policy: true }` | 6238–6244 | M00368 | composite | true |
| F01850 | REPL-as-reality decision — can-this-be-executed | 6256 | M00369 | composite | false |
| F01851 | REPL-as-reality decision — can-this-be-parsed | 6257 | M00369 | composite | false |
| F01852 | REPL-as-reality decision — can-this-be-tested | 6258 | M00369 | composite | false |
| F01853 | REPL-as-reality decision — can-this-be-measured | 6259 | M00369 | composite | false |
| F01854 | Workflow durability invariant — every frame is persisted | 6273 | E0203 | composite | false |
| F01855 | Workflow durability invariant — every step has schema | 6274 | E0203 | composite | false |
| F01856 | Workflow durability invariant — every side effect has a commit record | 6275 | E0203 | composite | false |
| F01857 | Workflow durability invariant — every retry is idempotent or compensated | 6276 | E0203 | composite | false |
| F01858 | Workflow durability invariant — every human gate can pause/resume | 6277 | E0203 | composite | false |
| F01859 | Deterministic kernel surface — schemas | 6287 | E0203 | composite | false |
| F01860 | Deterministic kernel surface — grammars / permissions / budgets / risk states / token masks / tool policies / branch lifecycle / memory quarantine / commit rules | 6288–6296 | E0203 | composite | false |
| F01861 | System artifact 1 — Frame (universal unit of cognition/work) | 6328–6329 | M00370 | composite | false |
| F01862 | System artifact 2 — Event (observed input or emitted transition) | 6331–6332 | M00370 | composite | false |
| F01863 | System artifact 3 — Expert (model/tool/human/runtime component) | 6334–6335 | M00370 | composite | false |
| F01864 | System artifact 4 — Router (AVX-512 deterministic dispatcher) | 6337–6338 | M00370 | composite | false |
| F01865 | System artifact 5 — Workflow (durable graph of valid transitions) | 6340–6341 | M00370 | composite | false |
| F01866 | System artifact 6 — Policy (bitfields, schemas, permissions, risk) | 6343–6344 | M00370 | composite | false |
| F01867 | System artifact 7 — Replay (append-only record of committed frames) | 6346–6347 | M00370 | composite | false |
| F01868 | System artifact 8 — Memory (typed, indexed, cache-aware experience) | 6349–6350 | M00370 | composite | false |
| F01869 | System artifact 9 — Eval (measurement that updates routing and recipes) | 6352–6353 | M00370 | composite | false |
| F01870 | Composite — closing sentence "REPL is the loop, CoT is candidate state, MoE is routing, workflow is durable order, logic is law, and intelligence is the adaptive system that emerges when those are closed over memory and action" | 6360–6362 | E0207 | composite | false |

## Requirements (R03571–R03740)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R03571 | Industry converges on event-driven / durable / model-agnostic workflows | 6063 | E0198 | non-negotiable | false | 10 |
| R03572 | LlamaIndex Workflows are event-driven — steps handle events and emit new events | 6065 | M00354 | non-negotiable | false | 10 |
| R03573 | LlamaIndex Workflows useful for RAG / agents / extraction / custom flows | 6065 | M00354 | non-negotiable | false | 10 |
| R03574 | Temporal's core promise is durable execution | 6066 | M00355 | non-negotiable | false | 10 |
| R03575 | Temporal workflows resume after crashes / network failures / long delays | 6066 | M00355 | non-negotiable | false | 10 |
| R03576 | Ray Serve LLM supports engine-agnostic serving (vLLM/SGLang-style) | 6067 | M00356 | non-negotiable | false | 10 |
| R03577 | Ray Serve LLM supports OpenAI-compatible APIs | 6067 | M00356 | non-negotiable | false | 10 |
| R03578 | Ray Serve LLM supports custom routing + metrics + advanced serving patterns | 6067 | M00356 | non-negotiable | false | 10 |
| R03579 | Ray Serve LLM supports prefill-decode disaggregation | 6067 | M00356 | non-negotiable | false | 10 |
| R03580 | Production-agent pain is NOT "model not smart enough" | 6068 | E0199 | non-negotiable | false | 10 |
| R03581 | Production-agent pain — state drift | 6068 | F01790 | non-negotiable | false | 10 |
| R03582 | Production-agent pain — schema drift | 6068 | F01791 | non-negotiable | false | 10 |
| R03583 | Production-agent pain — mid-run failure | 6068 | F01792 | non-negotiable | false | 10 |
| R03584 | Production-agent pain — tool misuse | 6068 | F01793 | non-negotiable | false | 10 |
| R03585 | Production-agent pain — orchestration chaos | 6068 | F01794 | non-negotiable | false | 10 |
| R03586 | Intelligence needs a spine | 6073 | E0200 | non-negotiable | false | 10 |
| R03587 | Spine analogy — Models are the nervous tissue | 6076 | F01795 | non-negotiable | false | 10 |
| R03588 | Spine analogy — Workflows are the spine | 6076 | F01796 | non-negotiable | false | 10 |
| R03589 | Spine analogy — Logic is the immune system | 6076 | F01797 | non-negotiable | false | 10 |
| R03590 | Spine analogy — REPL/tools are the hands | 6076 | F01798 | non-negotiable | false | 10 |
| R03591 | Spine analogy — Memory is the body | 6076 | F01799 | non-negotiable | false | 10 |
| R03592 | Need one object that represents REPL / CoT / MoE routing / workflow steps / logic checks / intelligence | 6080 | E0201 | non-negotiable | false | 10 |
| R03593 | The object is called `CognitiveFrame` | 6082 | E0201 | non-negotiable | false | 10 |
| R03594 | `CognitiveFrame` carries `id` (u64) | 6086 | M00357 | non-negotiable | false | 10 |
| R03595 | `CognitiveFrame` carries `parent` (u64) | 6087 | M00357 | non-negotiable | false | 10 |
| R03596 | `CognitiveFrame` carries `workflow_node` (u64) | 6088 | M00357 | non-negotiable | false | 10 |
| R03597 | `CognitiveFrame` carries `control` (u64) | 6089 | M00357 | non-negotiable | false | 10 |
| R03598 | `CognitiveFrame` carries `capability` (u64) | 6090 | M00357 | non-negotiable | false | 10 |
| R03599 | `CognitiveFrame` carries `evidence` (u64) | 6091 | M00357 | non-negotiable | false | 10 |
| R03600 | `CognitiveFrame` carries `memory_ref` (u64) | 6092 | M00357 | non-negotiable | false | 10 |
| R03601 | `CognitiveFrame` carries `trace_ref` (u64) | 6093 | M00357 | non-negotiable | false | 10 |
| R03602 | `CognitiveFrame` is 64 bytes (8 × u64) — fits in one cache line | 6084–6094 | M00357 | non-negotiable | false | 10 |
| R03603 | Frame can be — a thought | 6100 | M00358 | non-negotiable | false | 10 |
| R03604 | Frame can be — a branch | 6101 | M00358 | non-negotiable | false | 10 |
| R03605 | Frame can be — a tool call | 6102 | M00358 | non-negotiable | false | 10 |
| R03606 | Frame can be — a model request | 6103 | M00358 | non-negotiable | false | 10 |
| R03607 | Frame can be — a workflow step | 6104 | M00358 | non-negotiable | false | 10 |
| R03608 | Frame can be — a memory write | 6105 | M00358 | non-negotiable | false | 10 |
| R03609 | Frame can be — a verification task | 6106 | M00358 | non-negotiable | false | 10 |
| R03610 | Frame can be — a REPL execution | 6107 | M00358 | non-negotiable | false | 10 |
| R03611 | Frame can be — a candidate answer | 6108 | M00358 | non-negotiable | false | 10 |
| R03612 | Everything becomes a frame | 6111 | E0201 | non-negotiable | false | 10 |
| R03613 | Frame Loop step — READ (ingest user/task/tool observation/memory event) | 6116–6117 | M00359 | non-negotiable | false | 10 |
| R03614 | Frame Loop step — ROUTE (choose expert: oracle / scout / REPL / memory / human / tool) | 6119–6120 | M00360 | non-negotiable | false | 10 |
| R03615 | Frame Loop step — EVALUATE (model inference / deterministic logic / parser / test / retrieval) | 6122–6123 | M00361 | non-negotiable | false | 10 |
| R03616 | Frame Loop step — OBSERVE (capture result / metrics / side effects) | 6125–6126 | M00362 | non-negotiable | false | 10 |
| R03617 | Frame Loop step — COMMIT (accept/reject/update state under policy) | 6128–6129 | M00363 | non-negotiable | false | 10 |
| R03618 | Frame Loop step — LOOP (emit next frames) | 6131–6132 | M00364 | non-negotiable | false | 10 |
| R03619 | The Frame Loop IS REPL generalized into an intelligence runtime | 6135 | E0202 | non-negotiable | false | 10 |
| R03620 | REPL is the runtime loop and tool execution reality check | 6140–6141 | E0203 | non-negotiable | false | 10 |
| R03621 | CoT is model-generated candidate intermediate state | 6143–6144 | E0203 | non-negotiable | false | 10 |
| R03622 | ToT/GoT is topology of many cognitive frames | 6146–6147 | E0203 | non-negotiable | false | 10 |
| R03623 | MoE is conditional routing to experts, both inside models and across system components | 6149–6150 | E0203 | non-negotiable | false | 10 |
| R03624 | Workflow is durable ordering of frames and events | 6152–6153 | E0203 | non-negotiable | false | 10 |
| R03625 | Logic is deterministic legality, constraints, masks, schemas, permissions | 6155–6156 | E0203 | non-negotiable | false | 10 |
| R03626 | Intelligence is the closed loop of search / action / observation / memory / adaptation | 6158–6159 | E0203 | non-negotiable | false | 10 |
| R03627 | A MoE model routes tokens to experts | 6164 | E0204 | non-negotiable | false | 10 |
| R03628 | The workstation routes frames to experts | 6166 | E0204 | non-negotiable | false | 10 |
| R03629 | Token MoE — `token → router → expert layer` | 6169–6170 | E0204 | non-negotiable | false | 10 |
| R03630 | System MoE — `frame → AVX-512 router → GPU/model/tool/human/memory expert` | 6172–6173 | E0204 | non-negotiable | false | 10 |
| R03631 | System-MoE expert — Blackwell oracle | 6179 | M00365 | non-negotiable | false | 10 |
| R03632 | System-MoE expert — 4090 scout | 6180 | M00365 | non-negotiable | false | 10 |
| R03633 | System-MoE expert — Nano perception model | 6181 | M00365 | non-negotiable | false | 10 |
| R03634 | System-MoE expert — embedding model | 6182 | M00365 | non-negotiable | false | 10 |
| R03635 | System-MoE expert — reranker | 6183 | M00365 | non-negotiable | false | 10 |
| R03636 | System-MoE expert — Python REPL | 6184 | M00365 | non-negotiable | false | 10 |
| R03637 | System-MoE expert — shell sandbox | 6185 | M00365 | non-negotiable | false | 10 |
| R03638 | System-MoE expert — simdjson validator | 6186 | M00365 | non-negotiable | false | 10 |
| R03639 | System-MoE expert — Hyperscan policy scanner | 6187 | M00365 | non-negotiable | false | 10 |
| R03640 | System-MoE expert — ZFS replay store | 6188 | M00365 | non-negotiable | false | 10 |
| R03641 | System-MoE expert — human approval | 6189 | M00365 | non-negotiable | false | 10 |
| R03642 | System MoE is not metaphor — it is architecture | 6192 | E0204 | non-negotiable | false | 10 |
| R03643 | CPU evaluates many frames at once | 6196 | E0205 | non-negotiable | false | 10 |
| R03644 | AVX-512 router mask — `alive_mask = budget > 0` | 6199 | M00366 | non-negotiable | false | 10 |
| R03645 | AVX-512 router mask — `tool_mask = capability & requested_tool` | 6200 | M00366 | non-negotiable | false | 10 |
| R03646 | AVX-512 router mask — `oracle_mask = risk_high \| final_commit` | 6201 | M00366 | non-negotiable | false | 10 |
| R03647 | AVX-512 router mask — `scout_mask = low_risk & needs_draft` | 6202 | M00366 | non-negotiable | false | 10 |
| R03648 | AVX-512 router mask — `repl_mask = executable_check_needed` | 6203 | M00366 | non-negotiable | false | 10 |
| R03649 | AVX-512 router mask — `memory_mask = retrieval_needed` | 6204 | M00366 | non-negotiable | false | 10 |
| R03650 | AVX-512 router mask — `human_mask = side_effect_high` | 6205 | M00366 | non-negotiable | false | 10 |
| R03651 | AVX-512 router compresses frames into dense queues | 6208 | E0205 | non-negotiable | false | 10 |
| R03652 | AVX-512 dense queue — `oracle_queue` | 6212 | M00367 | non-negotiable | false | 10 |
| R03653 | AVX-512 dense queue — `scout_queue` | 6213 | M00367 | non-negotiable | false | 10 |
| R03654 | AVX-512 dense queue — `repl_queue` | 6214 | M00367 | non-negotiable | false | 10 |
| R03655 | AVX-512 dense queue — `tool_queue` | 6215 | M00367 | non-negotiable | false | 10 |
| R03656 | AVX-512 dense queue — `human_queue` | 6216 | M00367 | non-negotiable | false | 10 |
| R03657 | AVX-512 dense queue — `memory_queue` | 6217 | M00367 | non-negotiable | false | 10 |
| R03658 | This is MoE routing at the system level | 6219 | E0205 | non-negotiable | false | 10 |
| R03659 | A model's chain of thought should NOT directly steer the system | 6223 | E0206 | non-negotiable | false | 10 |
| R03660 | Model CoT must be converted into Frames | 6224 | E0206 | non-negotiable | false | 10 |
| R03661 | "I should inspect package.json" → `ToolIntentFrame { tool: read_file, path: package.json, side_effect: none }` | 6226–6230 | M00368 | non-negotiable | true | 10 |
| R03662 | "The bug may be in parser.ts" → `HypothesisFrame { target: parser.ts, confidence: 0.62 }` | 6232–6236 | M00368 | non-negotiable | true | 10 |
| R03663 | "Run tests" → `ToolIntentFrame { command: npm test, risk: low/medium, requires_policy: true }` | 6238–6244 | M00368 | non-negotiable | true | 10 |
| R03664 | Now logic can handle it | 6247 | E0206 | non-negotiable | false | 10 |
| R03665 | PAL and Program-of-Thoughts matter because they separate language from computation | 6251 | E0203 | non-negotiable | false | 10 |
| R03666 | Model writes code or executable plan; interpreter computes | 6251 | E0203 | non-negotiable | false | 10 |
| R03667 | Runtime asks — can this be executed instead of guessed? | 6256 | M00369 | non-negotiable | false | 10 |
| R03668 | Runtime asks — can this be parsed instead of trusted? | 6257 | M00369 | non-negotiable | false | 10 |
| R03669 | Runtime asks — can this be tested instead of debated? | 6258 | M00369 | non-negotiable | false | 10 |
| R03670 | Runtime asks — can this be measured instead of reasoned about? | 6259 | M00369 | non-negotiable | false | 10 |
| R03671 | If yes — route to REPL/tool | 6262 | M00369 | non-negotiable | false | 10 |
| R03672 | Intelligence is created by attaching language to reality | 6264 | M00369 | non-negotiable | false | 10 |
| R03673 | A multi-step agent without durable workflow is a fragile chat loop | 6268 | E0203 | non-negotiable | false | 10 |
| R03674 | Durability invariant — every frame is persisted | 6273 | F01854 | non-negotiable | false | 10 |
| R03675 | Durability invariant — every step has schema | 6274 | F01855 | non-negotiable | false | 10 |
| R03676 | Durability invariant — every side effect has a commit record | 6275 | F01856 | non-negotiable | false | 10 |
| R03677 | Durability invariant — every retry is idempotent or compensated | 6276 | F01857 | non-negotiable | false | 10 |
| R03678 | Durability invariant — every human gate can pause/resume | 6277 | F01858 | non-negotiable | false | 10 |
| R03679 | Temporal-style durability is the right mental model | 6280 | M00355 | non-negotiable | false | 10 |
| R03680 | Local lightweight implementation acceptable first | 6280 | M00355 | non-negotiable | true | 10 |
| R03681 | Logic is the kernel | 6282 | E0203 | non-negotiable | false | 10 |
| R03682 | Logic is where the CPU matters most | 6284 | E0203 | non-negotiable | false | 10 |
| R03683 | Deterministic kernel surface — schemas | 6287 | F01859 | non-negotiable | false | 10 |
| R03684 | Deterministic kernel surface — grammars | 6288 | F01860 | non-negotiable | false | 10 |
| R03685 | Deterministic kernel surface — permissions | 6289 | F01860 | non-negotiable | false | 10 |
| R03686 | Deterministic kernel surface — budgets | 6290 | F01860 | non-negotiable | false | 10 |
| R03687 | Deterministic kernel surface — risk states | 6291 | F01860 | non-negotiable | false | 10 |
| R03688 | Deterministic kernel surface — token masks | 6292 | F01860 | non-negotiable | false | 10 |
| R03689 | Deterministic kernel surface — tool policies | 6293 | F01860 | non-negotiable | false | 10 |
| R03690 | Deterministic kernel surface — branch lifecycle | 6294 | F01860 | non-negotiable | false | 10 |
| R03691 | Deterministic kernel surface — memory quarantine | 6295 | F01860 | non-negotiable | false | 10 |
| R03692 | Deterministic kernel surface — commit rules | 6296 | F01860 | non-negotiable | false | 10 |
| R03693 | The kernel does not "think" — it enforces | 6301 | E0203 | non-negotiable | false | 10 |
| R03694 | A single model has intelligence | 6305 | E0203 | non-negotiable | false | 10 |
| R03695 | The station creates more intelligence by composition | 6307 | E0203 | non-negotiable | false | 10 |
| R03696 | Composition — model prior | 6310 | E0203 | non-negotiable | false | 10 |
| R03697 | Composition — search topology | 6311 | E0203 | non-negotiable | false | 10 |
| R03698 | Composition — tool reality | 6312 | E0203 | non-negotiable | false | 10 |
| R03699 | Composition — memory | 6313 | E0203 | non-negotiable | false | 10 |
| R03700 | Composition — verification | 6314 | E0203 | non-negotiable | false | 10 |
| R03701 | Composition — routing | 6315 | E0203 | non-negotiable | false | 10 |
| R03702 | Composition — deterministic law | 6316 | E0203 | non-negotiable | false | 10 |
| R03703 | Composition — feedback | 6317 | E0203 | non-negotiable | false | 10 |
| R03704 | Composition sum — system intelligence | 6318 | E0203 | non-negotiable | false | 10 |
| R03705 | That is the weave | 6321 | E0203 | non-negotiable | false | 10 |
| R03706 | System artifact 1 — Frame: universal unit of cognition/work | 6328–6329 | M00370 | non-negotiable | false | 10 |
| R03707 | System artifact 2 — Event: observed input or emitted transition | 6331–6332 | M00370 | non-negotiable | false | 10 |
| R03708 | System artifact 3 — Expert: model/tool/human/runtime component | 6334–6335 | M00370 | non-negotiable | false | 10 |
| R03709 | System artifact 4 — Router: AVX-512 deterministic dispatcher | 6337–6338 | M00370 | non-negotiable | false | 10 |
| R03710 | System artifact 5 — Workflow: durable graph of valid transitions | 6340–6341 | M00370 | non-negotiable | false | 10 |
| R03711 | System artifact 6 — Policy: bitfields, schemas, permissions, risk | 6343–6344 | M00370 | non-negotiable | false | 10 |
| R03712 | System artifact 7 — Replay: append-only record of committed frames | 6346–6347 | M00370 | non-negotiable | false | 10 |
| R03713 | System artifact 8 — Memory: typed, indexed, cache-aware experience | 6349–6350 | M00370 | non-negotiable | false | 10 |
| R03714 | System artifact 9 — Eval: measurement that updates routing and recipes | 6352–6353 | M00370 | non-negotiable | false | 10 |
| R03715 | If those primitives are clean, everything else can evolve | 6356 | E0207 | non-negotiable | false | 10 |
| R03716 | The closing sentence — REPL is the loop, CoT is candidate state, MoE is routing, workflow is durable order, logic is law, and intelligence is the adaptive system that emerges when those are closed over memory and action | 6360–6362 | E0207 | non-negotiable | false | 10 |
| R03717 | Not a profile, not a framework — a controllable substrate | 6364 | E0207 | non-negotiable | false | 10 |
| R03718 | Workflow backend operator-overrideable (native / llamaindex / temporal / ray_serve) | 6065–6067 | F01786 | non-negotiable | true | 10 |
| R03719 | Env var `SOVEREIGN_WORKFLOW_BACKEND` | 6065–6067 | F01788 | non-negotiable | true | 10 |
| R03720 | CLI `--workflow-backend <name>` | 6065–6067 | F01789 | non-negotiable | true | 10 |
| R03721 | API `POST /v1/frame/spawn` — spawn a new CognitiveFrame | 6082–6094 | M00357 | non-negotiable | true | 10 |
| R03722 | API `POST /v1/frame/route` — submit a frame to the AVX-512 router | 6194–6219 | M00366 | non-negotiable | true | 10 |
| R03723 | API `GET /v1/frame/{id}` — fetch frame state | 6082–6094 | M00357 | non-negotiable | true | 10 |
| R03724 | API `GET /v1/frames?parent=<id>` — list child frames | 6087 | M00357 | non-negotiable | true | 10 |
| R03725 | API `GET /v1/experts` — list 11 system-MoE experts with health | 6178–6190 | M00365 | non-negotiable | true | 10 |
| R03726 | API `GET /v1/queues` — list 6 dense queues with depth | 6211–6217 | M00367 | non-negotiable | true | 10 |
| R03727 | Dashboard — frame-lifecycle timeline (READ→ROUTE→EVALUATE→OBSERVE→COMMIT→LOOP) per branch | 6113–6135 | M00357 | non-negotiable | true | 10 |
| R03728 | Dashboard — System-MoE expert occupancy (11 experts: live state + frames in flight) | 6178–6190 | M00365 | non-negotiable | true | 10 |
| R03729 | Dashboard — AVX-512 router mask hits (7 masks: per-mask hit-rate) | 6199–6206 | M00366 | non-negotiable | true | 10 |
| R03730 | Dashboard — dense queue depth (6 queues: oracle/scout/repl/tool/human/memory) | 6211–6217 | M00367 | non-negotiable | true | 10 |
| R03731 | Test — `CognitiveFrame` 8-field round-trip preserves all fields | 6084–6094 | M00357 | non-negotiable | false | 10 |
| R03732 | Test — Frame Loop 6-step pipeline runs end-to-end on synthetic input | 6113–6135 | E0202 | non-negotiable | false | 10 |
| R03733 | Test — each of 9 Frame variants round-trips through API | 6097–6109 | M00358 | non-negotiable | false | 10 |
| R03734 | Test — each of 11 system-MoE experts receives Frame when its routing mask is set | 6178–6190 | M00365 | non-negotiable | false | 10 |
| R03735 | Test — each of 7 AVX-512 router masks evaluates correctly on synthetic frame corpus | 6199–6206 | M00366 | non-negotiable | false | 10 |
| R03736 | Test — each of 6 dense queues drains in correct priority order | 6211–6217 | M00367 | non-negotiable | false | 10 |
| R03737 | Test — CoT-to-Frame conversion produces typed Frame from each of 3 example prose inputs | 6226–6244 | M00368 | non-negotiable | false | 10 |
| R03738 | Test — REPL-as-reality 4-question gate routes executable claims to REPL | 6256–6262 | M00369 | non-negotiable | false | 10 |
| R03739 | Composite — Cognitive Frame milestone is the unified-execution model behind all prior milestones; integrates with M020 semantic ISA + M021 6-layer weave + M019 cognitive operators + M015 programming plane + M016 learning plane | 6080–6111 | E0207 | non-negotiable | false | 10 |
| R03740 | Composite — System-Level MoE is the meta-architecture: every prior milestone's primitives flow through the AVX-512 router as Frames + dense queues + 11 experts | 6162–6219 | M00370 | non-negotiable | false | 10 |

— End of M022 milestone file.
