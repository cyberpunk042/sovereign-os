# M054 — 11 typed interfaces — Gateway / Profile Resolver / Router / Model Adapter / Policy / Tool / Memory / Workflow / Eval / Observability / AVX Cortex

> Parent: `backlog/milestones/INDEX.md` row M054 (dump 16493–16896).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 16493–16896. Operator directive 16493: "continue" + closing 16896: "continue".
> All entries below extract verbatim. No invention.

## Epics (E0518–E0527)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0518 | Interfaces-keep-system-flexible framing — "Next we define interfaces, because interfaces are what keep the system flexible. The implementation should avoid one giant agent blob. It should be a set of services that communicate through typed contracts" | 16497–16502 |
| E0519 | Interface 1 Gateway — "The gateway receives external requests"; 5 inputs (Anthropic Messages + OpenAI-compatible + CLI + UI + MCP/tool); internal output = RuntimeRequest with 9 fields (request_id / client_id / profile_hint / model_alias / messages / attachments / tools / privacy_context / budget / streaming); "The gateway should not do deep reasoning. It should normalize, authenticate, rate-limit, trace, and hand off" | 16506–16544 |
| E0520 | Interface 2 Profile Resolver — 5 inputs (RuntimeRequest + project context + user defaults + hardware state + policy state); output = ResolvedProfile with 10 fields (privacy_mode + quality_target + latency_target + cost_limit + autonomy_level + sandbox_level + cloud_permission + oracle_requirement + memory_depth + eval_level); "This is the first place user sovereignty becomes executable" | 16548–16580 |
| E0521 | Interface 3 Router + Interface 4 Model Adapter — Router input (ResolvedProfile + task classification + model registry + hardware telemetry + cache/KV state + cost ledger) → output ExecutionRoute with 11 fields (primary_model + fallback_model + scout_model + oracle_model + embedding_model + hardware_target + precision + adapter + max_tokens + reasoning_budget + verification_required) + route_reason explanation field example "local-only profile; chose 3090 scout for draft and Blackwell oracle for final verification"; Model Adapter 5 verbs (generate / embed / rerank / verify / perceive) → 7 backends (vLLM + SGLang + TensorRT-LLM + llama.cpp + Anthropic cloud + OpenAI cloud + custom local server); "No workflow should depend directly on a vendor SDK" | 16584–16648 |
| E0522 | Interface 5 Policy + Interface 6 Tool — Policy input (actor + intent + action + resource + profile + risk + context_sensitivity + side_effect_class) → output PolicyDecision (7 values: allow / deny / ask_user / sandbox / escalate_to_oracle / require_snapshot / require_test); 7 call sites (cloud call + tool call + file write + memory write + network access + adapter activation + commit); Tool 4-state pipeline (ToolIntent → PolicyDecision → ToolExecution → ToolObservation); tool metadata 9 fields (tool_id + input_schema + output_schema + capabilities_required + side_effects + risk_class + sandbox_required + timeout + rollback_strategy); supports 10 substrates (shell / browser / filesystem / Python / Deno / WASM / database / API / GUI / future) | 16652–16708 |
| E0523 | Interface 7 Memory + Interface 8 Workflow — Memory 5 verbs (search + read + write + promote + forget); MemoryItem 8 fields (trust + freshness + privacy + source + type + value_score + raw_ref + derived_refs); Workflow = "durable graph" with WorkflowRun 6-element scope (nodes + edges + frames + checkpoints + evals + pending gates); 8 Node types (model / tool / memory / policy / eval / human_gate / checkpoint / commit); 7 supported operations (pause / resume / cancel / fork / merge / rollback / recompile) | 16712–16766 |
| E0524 | Interface 9 Eval + Interface 10 Observability — Eval 6 inputs (trace + task goal + outputs + tool observations + tests + profile) → EvalResult 10 scores (success + correctness + evidence + risk + cost + latency + test_pass + schema_valid + human_burden + learning_value); "Evals feed the router and model registry"; Observability 9 required fields (trace_id + span_id + parent_span_id + event_type + module + timestamp + profile + cost + risk + status); 6 enablement targets (debugging + cost tracking + replay + learning + auditing + user trust) | 16770–16812 |
| E0525 | Interface 11 AVX Cortex — "This is an internal acceleration module, not the whole runtime"; 5 inputs (BranchTable + MemoryMetaTable + PolicyMaskTable + CandidateTable + RewardTable); 6 operations (filter_alive + score_candidates + intersect_memory + merge_policy_masks + compress_ready + route_batches); 4-element output (dense queues + masks + scores + selected ids); "The rest of the system should work without AVX, just slower. That keeps it portable and testable" | 16816–16856 |
| E0526 | Architectural Rule — "Each module should be replaceable"; 6 replacement examples: Replace vLLM with SGLang / Replace local model with cloud / Replace OPA with Cedar / Replace Langfuse with Phoenix / Replace Podman with VM / Replace scalar scheduler with AVX scheduler; "The contracts remain" | 16860–16886 |
| E0527 | Doctrine + cross-cycle composition — "That is how the system stays sovereign and future-proof"; cross-cycle binding — 11 typed interfaces enable the 11-build-phase blueprint (M053); cross-repo composition with selfdef MS001-MS035 + cross-repo binding via MS007 surface-manifest typed-mirror crate | 16894–16896 + architecture |

## Modules (M00901–M00917)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00901 | Interfaces doctrine — "interfaces are what keep the system flexible" | 16498 | E0518 |
| M00902 | Anti-pattern — "avoid one giant agent blob" | 16500 | E0518 |
| M00903 | Pattern — "set of services that communicate through typed contracts" | 16502 | E0518 |
| M00904 | Interface 1 Gateway — 5 inputs + RuntimeRequest 9-field output + normalize/authenticate/rate-limit/trace/hand-off responsibility | 16506–16544 | E0519 |
| M00905 | Interface 2 Profile Resolver — 5 inputs + ResolvedProfile 10-field output + "first place user sovereignty becomes executable" | 16548–16580 | E0520 |
| M00906 | Interface 3 Router — 6 inputs + ExecutionRoute 11-field output + route_reason field with example | 16584–16618 | E0521 |
| M00907 | Interface 4 Model Adapter — 5 verbs + 7 backends + "No workflow should depend directly on a vendor SDK" | 16622–16648 | E0521 |
| M00908 | Interface 5 Policy — 8 inputs + PolicyDecision 7 values + 7 call sites | 16652–16684 | E0522 |
| M00909 | Interface 6 Tool — 4-state pipeline + 9-field metadata + 10 substrates | 16688–16708 | E0522 |
| M00910 | Interface 7 Memory — 5 verbs + MemoryItem 8 fields | 16712–16738 | E0523 |
| M00911 | Interface 8 Workflow — "durable graph" + WorkflowRun 6-element + 8 node types + 7 operations | 16742–16766 | E0523 |
| M00912 | Interface 9 Eval — 6 inputs + EvalResult 10 scores + "feeds router and model registry" | 16770–16792 | E0524 |
| M00913 | Interface 10 Observability — 9 required fields + 6 enablement targets | 16796–16812 | E0524 |
| M00914 | Interface 11 AVX Cortex — "internal acceleration module, not the whole runtime" + 5 inputs + 6 operations + 4-element output + portability doctrine | 16816–16856 | E0525 |
| M00915 | Architectural Rule — "Each module should be replaceable" + 6 replacement examples | 16860–16884 | E0526 |
| M00916 | "The contracts remain" — typed interfaces are the substitution surface | 16886 | E0526 |
| M00917 | "That is how the system stays sovereign and future-proof" | 16894 | E0527 |

## Features (F04506–F04590)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F04506 | "Next we define interfaces" | 16496 | E0518 |
| F04507 | "Interfaces are what keep the system flexible" | 16498 | M00901 |
| F04508 | "Avoid one giant agent blob" | 16500 | M00902 |
| F04509 | "Set of services that communicate through typed contracts" | 16502 | M00903 |
| F04510 | Gateway header — "Gateway Interface" | 16506 | M00904 |
| F04511 | Gateway — receives Anthropic Messages request | 16512 | M00904 |
| F04512 | Gateway — receives OpenAI-compatible request | 16513 | M00904 |
| F04513 | Gateway — receives CLI request | 16514 | M00904 |
| F04514 | Gateway — receives UI request | 16515 | M00904 |
| F04515 | Gateway — receives MCP/tool request | 16516 | M00904 |
| F04516 | Gateway internal output — RuntimeRequest | 16520 | M00904 |
| F04517 | RuntimeRequest field — request_id | 16524 | M00904 |
| F04518 | RuntimeRequest field — client_id | 16525 | M00904 |
| F04519 | RuntimeRequest field — profile_hint | 16526 | M00904 |
| F04520 | RuntimeRequest field — model_alias | 16527 | M00904 |
| F04521 | RuntimeRequest field — messages | 16528 | M00904 |
| F04522 | RuntimeRequest field — attachments | 16529 | M00904 |
| F04523 | RuntimeRequest field — tools | 16530 | M00904 |
| F04524 | RuntimeRequest field — privacy_context | 16531 | M00904 |
| F04525 | RuntimeRequest field — budget | 16532 | M00904 |
| F04526 | RuntimeRequest field — streaming | 16533 | M00904 |
| F04527 | Gateway responsibility — "should not do deep reasoning" | 16538 | M00904 |
| F04528 | Gateway responsibility — normalize | 16540 | M00904 |
| F04529 | Gateway responsibility — authenticate | 16540 | M00904 |
| F04530 | Gateway responsibility — rate-limit | 16540 | M00904 |
| F04531 | Gateway responsibility — trace | 16542 | M00904 |
| F04532 | Gateway responsibility — hand off | 16542 | M00904 |
| F04533 | Profile Resolver header — "Profile Resolver Interface" | 16548 | M00905 |
| F04534 | Profile Resolver input — RuntimeRequest + project context + user defaults + hardware state + policy state | 16552–16558 | M00905 |
| F04535 | Profile Resolver output — ResolvedProfile | 16560 | M00905 |
| F04536 | ResolvedProfile fields — privacy_mode + quality_target + latency_target + cost_limit + autonomy_level + sandbox_level + cloud_permission + oracle_requirement + memory_depth + eval_level | 16564–16574 | M00905 |
| F04537 | "First place user sovereignty becomes executable" | 16580 | M00905 |
| F04538 | Router header — "Router Interface" | 16584 | M00906 |
| F04539 | Router input — ResolvedProfile + task classification + model registry + hardware telemetry + cache/KV state + cost ledger | 16588–16596 | M00906 |
| F04540 | Router output — ExecutionRoute | 16598 | M00906 |
| F04541 | ExecutionRoute field — primary_model | 16602 | M00906 |
| F04542 | ExecutionRoute field — fallback_model | 16603 | M00906 |
| F04543 | ExecutionRoute field — scout_model | 16604 | M00906 |
| F04544 | ExecutionRoute field — oracle_model | 16605 | M00906 |
| F04545 | ExecutionRoute field — embedding_model | 16606 | M00906 |
| F04546 | ExecutionRoute field — hardware_target | 16607 | M00906 |
| F04547 | ExecutionRoute field — precision | 16608 | M00906 |
| F04548 | ExecutionRoute field — adapter | 16609 | M00906 |
| F04549 | ExecutionRoute field — max_tokens | 16610 | M00906 |
| F04550 | ExecutionRoute field — reasoning_budget | 16611 | M00906 |
| F04551 | ExecutionRoute field — verification_required | 16612 | M00906 |
| F04552 | route_reason explanation field | 16616 | M00906 |
| F04553 | route_reason example — "local-only profile; chose 3090 scout for draft and Blackwell oracle for final verification" | 16618 | M00906 |
| F04554 | Model Adapter header — "Model Adapter Interface" | 16622 | M00907 |
| F04555 | Model Adapter — "Every model backend should look the same internally" | 16624 | M00907 |
| F04556 | Model Adapter verb — generate(request) -> ModelResult | 16628 | M00907 |
| F04557 | Model Adapter verb — embed(request) -> EmbeddingResult | 16629 | M00907 |
| F04558 | Model Adapter verb — rerank(request) -> RerankResult | 16630 | M00907 |
| F04559 | Model Adapter verb — verify(request) -> VerificationResult | 16631 | M00907 |
| F04560 | Model Adapter verb — perceive(request) -> PerceptionResult | 16632 | M00907 |
| F04561 | Model Adapter backend — vLLM + SGLang + TensorRT-LLM + llama.cpp + Anthropic cloud + OpenAI cloud + custom local server | 16638–16644 | M00907 |
| F04562 | "No workflow should depend directly on a vendor SDK" | 16648 | M00907 |
| F04563 | Policy + Tool interfaces — full schema (8 inputs + 7 PolicyDecision values + 7 call sites + 4-state ToolIntent→PolicyDecision→ToolExecution→ToolObservation pipeline + 9-field tool metadata + 10 substrates) | 16652–16708 | M00908 + M00909 |
| F04564 | Memory verb — search(query, filters, profile) -> MemoryRefs | 16716 | M00910 |
| F04565 | Memory verb — read(memory_ref, profile) -> MemoryItem | 16717 | M00910 |
| F04566 | Memory verb — write(memory_item, policy) -> MemoryWriteResult | 16718 | M00910 |
| F04567 | Memory verb — promote(memory_ref) -> PromotionResult | 16719 | M00910 |
| F04568 | Memory verb — forget(memory_ref) -> ForgetResult | 16720 | M00910 |
| F04569 | MemoryItem field — trust + freshness + privacy + source + type + value_score + raw_ref + derived_refs | 16724–16734 | M00910 |
| F04570 | Workflow doctrine — "A workflow is a durable graph" | 16742 | M00911 |
| F04571 | WorkflowRun element — nodes + edges + frames + checkpoints + evals + pending gates | 16746–16752 | M00911 |
| F04572 | Node type — model + tool + memory + policy + eval + human_gate + checkpoint + commit | 16756–16762 | M00911 |
| F04573 | Workflow operation — pause + resume + cancel + fork + merge + rollback + recompile | 16766–16770 | M00911 |
| F04574 | Eval input — trace + task goal + outputs + tool observations + tests + profile | 16774–16780 | M00912 |
| F04575 | EvalResult score — success + correctness + evidence + risk + cost + latency + test_pass + schema_valid + human_burden + learning_value | 16786–16796 | M00912 |
| F04576 | "Evals feed the router and model registry" | 16792 | M00912 |
| F04577 | Observability field — trace_id + span_id + parent_span_id + event_type + module + timestamp + profile + cost + risk + status | 16800–16808 | M00913 |
| F04578 | Observability enablement — debugging + cost tracking + replay + learning + auditing + user trust | 16812 | M00913 |
| F04579 | AVX Cortex doctrine — "internal acceleration module, not the whole runtime" | 16818 | M00914 |
| F04580 | AVX Cortex input — BranchTable + MemoryMetaTable + PolicyMaskTable + CandidateTable + RewardTable | 16822–16828 | M00914 |
| F04581 | AVX Cortex operation — filter_alive + score_candidates + intersect_memory + merge_policy_masks + compress_ready + route_batches | 16832–16838 | M00914 |
| F04582 | AVX Cortex output — dense queues + masks + scores + selected ids | 16842–16846 | M00914 |
| F04583 | AVX Cortex portability — "The rest of the system should work without AVX, just slower. That keeps it portable and testable" | 16852–16856 | M00914 |
| F04584 | Architectural Rule — "Each module should be replaceable" | 16860 | M00915 |
| F04585 | Replacement — Replace vLLM with SGLang | 16864 | M00915 |
| F04586 | Replacement — Replace local model with cloud | 16866 | M00915 |
| F04587 | Replacement — Replace OPA with Cedar | 16868 | M00915 |
| F04588 | Replacement — Replace Langfuse with Phoenix | 16870 | M00915 |
| F04589 | Replacement — Replace Podman with VM | 16872 + Replace scalar scheduler with AVX scheduler 16874 | M00915 |
| F04590 | "The contracts remain" + "That is how the system stays sovereign and future-proof" | 16886 + 16894 | M00916 + M00917 |

## Requirements (R09011–R09180)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R09011 | "Next we define interfaces" | 16496 | F04506 | non-negotiable | false | 10 |
| R09012 | "interfaces are what keep the system flexible" | 16498 | F04507 | non-negotiable | false | 10 |
| R09013 | "avoid one giant agent blob" | 16500 | F04508 | non-negotiable | false | 10 |
| R09014 | "set of services that communicate through typed contracts" | 16502 | F04509 | non-negotiable | false | 10 |
| R09015 | Gateway header — "Gateway Interface" | 16506 | F04510 | non-negotiable | false | 10 |
| R09016 | Gateway input — Anthropic Messages request | 16512 | F04511 | non-negotiable | false | 10 |
| R09017 | Gateway input — OpenAI-compatible request | 16513 | F04512 | non-negotiable | false | 10 |
| R09018 | Gateway input — CLI request | 16514 | F04513 | non-negotiable | false | 10 |
| R09019 | Gateway input — UI request | 16515 | F04514 | non-negotiable | false | 10 |
| R09020 | Gateway input — MCP/tool request | 16516 | F04515 | non-negotiable | false | 10 |
| R09021 | Gateway output — RuntimeRequest | 16520 | F04516 | non-negotiable | false | 10 |
| R09022 | RuntimeRequest — request_id | 16524 | F04517 | non-negotiable | false | 10 |
| R09023 | RuntimeRequest — client_id | 16525 | F04518 | non-negotiable | false | 10 |
| R09024 | RuntimeRequest — profile_hint | 16526 | F04519 | non-negotiable | false | 10 |
| R09025 | RuntimeRequest — model_alias | 16527 | F04520 | non-negotiable | false | 10 |
| R09026 | RuntimeRequest — messages | 16528 | F04521 | non-negotiable | false | 10 |
| R09027 | RuntimeRequest — attachments | 16529 | F04522 | non-negotiable | false | 10 |
| R09028 | RuntimeRequest — tools | 16530 | F04523 | non-negotiable | false | 10 |
| R09029 | RuntimeRequest — privacy_context | 16531 | F04524 | non-negotiable | false | 10 |
| R09030 | RuntimeRequest — budget | 16532 | F04525 | non-negotiable | false | 10 |
| R09031 | RuntimeRequest — streaming | 16533 | F04526 | non-negotiable | false | 10 |
| R09032 | Gateway doctrine — "should not do deep reasoning" | 16538 | F04527 | non-negotiable | false | 10 |
| R09033 | Gateway responsibility — normalize | 16540 | F04528 | non-negotiable | false | 10 |
| R09034 | Gateway responsibility — authenticate | 16540 | F04529 | non-negotiable | false | 10 |
| R09035 | Gateway responsibility — rate-limit | 16540 | F04530 | non-negotiable | false | 10 |
| R09036 | Gateway responsibility — trace | 16542 | F04531 | non-negotiable | false | 10 |
| R09037 | Gateway responsibility — hand off | 16542 | F04532 | non-negotiable | false | 10 |
| R09038 | Profile Resolver header — "Profile Resolver Interface" | 16548 | F04533 | non-negotiable | false | 10 |
| R09039 | Profile Resolver input — RuntimeRequest | 16552 | F04534 | non-negotiable | false | 10 |
| R09040 | Profile Resolver input — project context | 16554 | F04534 | non-negotiable | false | 10 |
| R09041 | Profile Resolver input — user defaults | 16555 | F04534 | non-negotiable | false | 10 |
| R09042 | Profile Resolver input — hardware state | 16556 | F04534 | non-negotiable | false | 10 |
| R09043 | Profile Resolver input — policy state | 16557 | F04534 | non-negotiable | false | 10 |
| R09044 | Profile Resolver output — ResolvedProfile | 16560 | F04535 | non-negotiable | false | 10 |
| R09045 | ResolvedProfile — privacy_mode | 16564 | F04536 | non-negotiable | false | 10 |
| R09046 | ResolvedProfile — quality_target | 16565 | F04536 | non-negotiable | false | 10 |
| R09047 | ResolvedProfile — latency_target | 16566 | F04536 | non-negotiable | false | 10 |
| R09048 | ResolvedProfile — cost_limit | 16567 | F04536 | non-negotiable | false | 10 |
| R09049 | ResolvedProfile — autonomy_level | 16568 | F04536 | non-negotiable | false | 10 |
| R09050 | ResolvedProfile — sandbox_level | 16569 | F04536 | non-negotiable | false | 10 |
| R09051 | ResolvedProfile — cloud_permission | 16570 | F04536 | non-negotiable | false | 10 |
| R09052 | ResolvedProfile — oracle_requirement | 16571 | F04536 | non-negotiable | false | 10 |
| R09053 | ResolvedProfile — memory_depth | 16572 | F04536 | non-negotiable | false | 10 |
| R09054 | ResolvedProfile — eval_level | 16573 | F04536 | non-negotiable | false | 10 |
| R09055 | "first place user sovereignty becomes executable" | 16580 | F04537 | non-negotiable | false | 10 |
| R09056 | Router header — "Router Interface" | 16584 | F04538 | non-negotiable | false | 10 |
| R09057 | Router input — ResolvedProfile | 16588 | F04539 | non-negotiable | false | 10 |
| R09058 | Router input — task classification | 16590 | F04539 | non-negotiable | false | 10 |
| R09059 | Router input — model registry | 16591 | F04539 | non-negotiable | false | 10 |
| R09060 | Router input — hardware telemetry | 16592 | F04539 | non-negotiable | false | 10 |
| R09061 | Router input — cache/KV state | 16593 | F04539 | non-negotiable | false | 10 |
| R09062 | Router input — cost ledger | 16594 | F04539 | non-negotiable | false | 10 |
| R09063 | Router output — ExecutionRoute | 16598 | F04540 | non-negotiable | false | 10 |
| R09064 | ExecutionRoute — primary_model | 16602 | F04541 | non-negotiable | false | 10 |
| R09065 | ExecutionRoute — fallback_model | 16603 | F04542 | non-negotiable | false | 10 |
| R09066 | ExecutionRoute — scout_model | 16604 | F04543 | non-negotiable | false | 10 |
| R09067 | ExecutionRoute — oracle_model | 16605 | F04544 | non-negotiable | false | 10 |
| R09068 | ExecutionRoute — embedding_model | 16606 | F04545 | non-negotiable | false | 10 |
| R09069 | ExecutionRoute — hardware_target | 16607 | F04546 | non-negotiable | false | 10 |
| R09070 | ExecutionRoute — precision | 16608 | F04547 | non-negotiable | false | 10 |
| R09071 | ExecutionRoute — adapter | 16609 | F04548 | non-negotiable | false | 10 |
| R09072 | ExecutionRoute — max_tokens | 16610 | F04549 | non-negotiable | false | 10 |
| R09073 | ExecutionRoute — reasoning_budget | 16611 | F04550 | non-negotiable | false | 10 |
| R09074 | ExecutionRoute — verification_required | 16612 | F04551 | non-negotiable | false | 10 |
| R09075 | route_reason field — Router should explain itself | 16616 | F04552 | non-negotiable | false | 10 |
| R09076 | route_reason example — "local-only profile; chose 3090 scout for draft and Blackwell oracle for final verification" | 16618 | F04553 | non-negotiable | false | 10 |
| R09077 | Model Adapter header | 16622 | F04554 | non-negotiable | false | 10 |
| R09078 | Model Adapter doctrine — "Every model backend should look the same internally" | 16624 | F04555 | non-negotiable | false | 10 |
| R09079 | Model Adapter verb — generate(request) -> ModelResult | 16628 | F04556 | non-negotiable | false | 10 |
| R09080 | Model Adapter verb — embed(request) -> EmbeddingResult | 16629 | F04557 | non-negotiable | false | 10 |
| R09081 | Model Adapter verb — rerank(request) -> RerankResult | 16630 | F04558 | non-negotiable | false | 10 |
| R09082 | Model Adapter verb — verify(request) -> VerificationResult | 16631 | F04559 | non-negotiable | false | 10 |
| R09083 | Model Adapter verb — perceive(request) -> PerceptionResult | 16632 | F04560 | non-negotiable | false | 10 |
| R09084 | Model Adapter backend — vLLM | 16638 | F04561 | non-negotiable | false | 10 |
| R09085 | Model Adapter backend — SGLang | 16639 | F04561 | non-negotiable | false | 10 |
| R09086 | Model Adapter backend — TensorRT-LLM | 16640 | F04561 | non-negotiable | false | 10 |
| R09087 | Model Adapter backend — llama.cpp | 16641 | F04561 | non-negotiable | false | 10 |
| R09088 | Model Adapter backend — Anthropic cloud | 16642 | F04561 | non-negotiable | false | 10 |
| R09089 | Model Adapter backend — OpenAI cloud | 16643 | F04561 | non-negotiable | false | 10 |
| R09090 | Model Adapter backend — custom local server | 16644 | F04561 | non-negotiable | false | 10 |
| R09091 | "No workflow should depend directly on a vendor SDK" | 16648 | F04562 | non-negotiable | false | 10 |
| R09092 | Policy header — "Policy Interface" | 16652 | M00908 | non-negotiable | false | 10 |
| R09093 | Policy input — actor | 16656 | M00908 | non-negotiable | false | 10 |
| R09094 | Policy input — intent | 16657 | M00908 | non-negotiable | false | 10 |
| R09095 | Policy input — action | 16658 | M00908 | non-negotiable | false | 10 |
| R09096 | Policy input — resource | 16659 | M00908 | non-negotiable | false | 10 |
| R09097 | Policy input — profile | 16660 | M00908 | non-negotiable | false | 10 |
| R09098 | Policy input — risk | 16661 | M00908 | non-negotiable | false | 10 |
| R09099 | Policy input — context_sensitivity | 16662 | M00908 | non-negotiable | false | 10 |
| R09100 | Policy input — side_effect_class | 16663 | M00908 | non-negotiable | false | 10 |
| R09101 | Policy output — PolicyDecision | 16666 | M00908 | non-negotiable | false | 10 |
| R09102 | PolicyDecision value — allow | 16670 | M00908 | non-negotiable | false | 10 |
| R09103 | PolicyDecision value — deny | 16671 | M00908 | non-negotiable | false | 10 |
| R09104 | PolicyDecision value — ask_user | 16672 | M00908 | non-negotiable | false | 10 |
| R09105 | PolicyDecision value — sandbox | 16673 | M00908 | non-negotiable | false | 10 |
| R09106 | PolicyDecision value — escalate_to_oracle | 16674 | M00908 | non-negotiable | false | 10 |
| R09107 | PolicyDecision value — require_snapshot | 16675 | M00908 | non-negotiable | false | 10 |
| R09108 | PolicyDecision value — require_test | 16676 | M00908 | non-negotiable | false | 10 |
| R09109 | Policy call site — cloud call | 16680 | M00908 | non-negotiable | false | 10 |
| R09110 | Policy call site — tool call | 16681 | M00908 | non-negotiable | false | 10 |
| R09111 | Policy call site — file write | 16682 | M00908 | non-negotiable | false | 10 |
| R09112 | Policy call site — memory write | 16683 | M00908 | non-negotiable | false | 10 |
| R09113 | Policy call site — network access | 16684 | M00908 | non-negotiable | false | 10 |
| R09114 | Policy call site — adapter activation | 16685 | M00908 | non-negotiable | false | 10 |
| R09115 | Policy call site — commit | 16686 | M00908 | non-negotiable | false | 10 |
| R09116 | Tool header — "Tool Interface" | 16688 | M00909 | non-negotiable | false | 10 |
| R09117 | Tool doctrine — "A tool is not a command. It is a typed transition" | 16690 | M00909 | non-negotiable | false | 10 |
| R09118 | Tool pipeline — ToolIntent -> PolicyDecision -> ToolExecution -> ToolObservation | 16694 | M00909 | non-negotiable | false | 10 |
| R09119 | Tool metadata — tool_id | 16698 | M00909 | non-negotiable | false | 10 |
| R09120 | Tool metadata — input_schema | 16699 | M00909 | non-negotiable | false | 10 |
| R09121 | Tool metadata — output_schema | 16700 | M00909 | non-negotiable | false | 10 |
| R09122 | Tool metadata — capabilities_required | 16701 | M00909 | non-negotiable | false | 10 |
| R09123 | Tool metadata — side_effects | 16702 | M00909 | non-negotiable | false | 10 |
| R09124 | Tool metadata — risk_class | 16703 | M00909 | non-negotiable | false | 10 |
| R09125 | Tool metadata — sandbox_required | 16704 | M00909 | non-negotiable | false | 10 |
| R09126 | Tool metadata — timeout | 16705 | M00909 | non-negotiable | false | 10 |
| R09127 | Tool metadata — rollback_strategy | 16706 | M00909 | non-negotiable | false | 10 |
| R09128 | Tool substrates — shell + browser + filesystem + Python + Deno + WASM + database + API + GUI + future tools | 16708 | M00909 | non-negotiable | false | 10 |
| R09129 | Memory header — "Memory Interface" | 16712 | M00910 | non-negotiable | false | 10 |
| R09130 | Memory doctrine — "Memory is governed access" | 16714 | M00910 | non-negotiable | false | 10 |
| R09131 | Memory verb — search(query, filters, profile) -> MemoryRefs | 16716 | F04564 | non-negotiable | false | 10 |
| R09132 | Memory verb — read(memory_ref, profile) -> MemoryItem | 16717 | F04565 | non-negotiable | false | 10 |
| R09133 | Memory verb — write(memory_item, policy) -> MemoryWriteResult | 16718 | F04566 | non-negotiable | false | 10 |
| R09134 | Memory verb — promote(memory_ref) -> PromotionResult | 16719 | F04567 | non-negotiable | false | 10 |
| R09135 | Memory verb — forget(memory_ref) -> ForgetResult | 16720 | F04568 | non-negotiable | false | 10 |
| R09136 | MemoryItem — trust | 16724 | F04569 | non-negotiable | false | 10 |
| R09137 | MemoryItem — freshness | 16725 | F04569 | non-negotiable | false | 10 |
| R09138 | MemoryItem — privacy | 16726 | F04569 | non-negotiable | false | 10 |
| R09139 | MemoryItem — source | 16727 | F04569 | non-negotiable | false | 10 |
| R09140 | MemoryItem — type | 16728 | F04569 | non-negotiable | false | 10 |
| R09141 | MemoryItem — value_score | 16729 | F04569 | non-negotiable | false | 10 |
| R09142 | MemoryItem — raw_ref | 16730 | F04569 | non-negotiable | false | 10 |
| R09143 | MemoryItem — derived_refs | 16731 | F04569 | non-negotiable | false | 10 |
| R09144 | Workflow header — "Workflow Interface" | 16742 | M00911 | non-negotiable | false | 10 |
| R09145 | Workflow doctrine — "A workflow is a durable graph" | 16742 | F04570 | non-negotiable | false | 10 |
| R09146 | WorkflowRun element — nodes | 16746 | F04571 | non-negotiable | false | 10 |
| R09147 | WorkflowRun element — edges | 16747 | F04571 | non-negotiable | false | 10 |
| R09148 | WorkflowRun element — frames | 16748 | F04571 | non-negotiable | false | 10 |
| R09149 | WorkflowRun element — checkpoints | 16749 | F04571 | non-negotiable | false | 10 |
| R09150 | WorkflowRun element — evals | 16750 | F04571 | non-negotiable | false | 10 |
| R09151 | WorkflowRun element — pending gates | 16751 | F04571 | non-negotiable | false | 10 |
| R09152 | Node type — model | 16756 | F04572 | non-negotiable | false | 10 |
| R09153 | Node type — tool | 16757 | F04572 | non-negotiable | false | 10 |
| R09154 | Node type — memory | 16758 | F04572 | non-negotiable | false | 10 |
| R09155 | Node type — policy | 16759 | F04572 | non-negotiable | false | 10 |
| R09156 | Node type — eval | 16760 | F04572 | non-negotiable | false | 10 |
| R09157 | Node type — human_gate | 16761 | F04572 | non-negotiable | false | 10 |
| R09158 | Node type — checkpoint | 16762 | F04572 | non-negotiable | false | 10 |
| R09159 | Node type — commit | 16763 | F04572 | non-negotiable | false | 10 |
| R09160 | Workflow operation — pause + resume + cancel + fork + merge + rollback + recompile | 16766–16770 | F04573 | non-negotiable | false | 10 |
| R09161 | Eval header — "Eval Interface" | 16774 | M00912 | non-negotiable | false | 10 |
| R09162 | Eval input — trace + task goal + outputs + tool observations + tests + profile | 16778–16784 | F04574 | non-negotiable | false | 10 |
| R09163 | EvalResult score — success + correctness + evidence + risk + cost + latency + test_pass + schema_valid + human_burden + learning_value | 16788–16798 | F04575 | non-negotiable | false | 10 |
| R09164 | "Evals feed the router and model registry" | 16792 | F04576 | non-negotiable | false | 10 |
| R09165 | Observability header — "Observability Interface" | 16796 | M00913 | non-negotiable | false | 10 |
| R09166 | Observability — "Every module emits events" | 16798 | M00913 | non-negotiable | false | 10 |
| R09167 | Observability field — trace_id + span_id + parent_span_id + event_type + module + timestamp + profile + cost + risk + status | 16800–16810 | F04577 | non-negotiable | false | 10 |
| R09168 | Observability enablement — debugging + cost tracking + replay + learning + auditing + user trust | 16812 | F04578 | non-negotiable | false | 10 |
| R09169 | AVX Cortex header — "AVX Cortex Interface" | 16816 | M00914 | non-negotiable | false | 10 |
| R09170 | AVX Cortex doctrine — "internal acceleration module, not the whole runtime" | 16818 | F04579 | non-negotiable | false | 10 |
| R09171 | AVX Cortex input — BranchTable + MemoryMetaTable + PolicyMaskTable + CandidateTable + RewardTable | 16822–16828 | F04580 | non-negotiable | false | 10 |
| R09172 | AVX Cortex operation — filter_alive + score_candidates + intersect_memory + merge_policy_masks + compress_ready + route_batches | 16832–16838 | F04581 | non-negotiable | false | 10 |
| R09173 | AVX Cortex output — dense queues + masks + scores + selected ids | 16842–16846 | F04582 | non-negotiable | false | 10 |
| R09174 | AVX Cortex portability — "The rest of the system should work without AVX, just slower. That keeps it portable and testable" | 16852–16856 | F04583 | non-negotiable | false | 10 |
| R09175 | Architectural Rule — "Each module should be replaceable" | 16860 | F04584 | non-negotiable | false | 10 |
| R09176 | Replacement — vLLM with SGLang + local model with cloud + OPA with Cedar + Langfuse with Phoenix + Podman with VM + scalar scheduler with AVX scheduler | 16864–16874 | F04585–F04589 | non-negotiable | false | 10 |
| R09177 | "The contracts remain" | 16886 | F04590 | non-negotiable | false | 10 |
| R09178 | "That is how the system stays sovereign and future-proof" | 16894 | F04590 | non-negotiable | false | 10 |
| R09179 | Cross-repo binding — 11 typed interfaces published via MS007 surface-manifest typed-mirror crate; selfdef MS001-MS035 align with all 11 interfaces | cross-ref MS007 + MS001-MS035 + architecture | E0527 | non-negotiable | false | 10 |
| R09180 | Composite — M054 (10 epics / 17 modules / 85 features / 170 reqs) catalogs 11 typed interfaces (Gateway / Profile Resolver / Router / Model Adapter / Policy / Tool / Memory / Workflow / Eval / Observability / AVX Cortex) + Architectural Rule "Each module should be replaceable" + 6 replacement examples + "The contracts remain" + "sovereign and future-proof"; each interface defines explicit Inputs + Outputs + Fields + Operations + Substrates; ResolvedProfile is "first place user sovereignty becomes executable"; "No workflow should depend directly on a vendor SDK"; AVX Cortex is internal acceleration not whole runtime ("rest of system should work without AVX, just slower"); cross-repo binding via MS007 typed-mirror crate; selfdef MS001-MS035 align with all 11 typed interfaces | dump 16493–16896 + cross-ref MS007 + MS001-MS035 | E0518-E0527 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: framing (R09011–R09014) + Gateway 5 inputs + 9-field RuntimeRequest + 5 responsibilities (R09015–R09037) + Profile Resolver 5 inputs + 10-field ResolvedProfile + sovereignty-executable (R09038–R09055) + Router 6 inputs + 11-field ExecutionRoute + route_reason + example (R09056–R09076) + Model Adapter 5 verbs + 7 backends + no-vendor-SDK doctrine (R09077–R09091) + Policy 8 inputs + 7 PolicyDecision values + 7 call sites (R09092–R09115) + Tool 4-state pipeline + 9-field metadata + 10 substrates (R09116–R09128) + Memory 5 verbs + 8-field MemoryItem + governed-access doctrine (R09129–R09143) + Workflow durable-graph + 6-element WorkflowRun + 8 node types + 7 operations (R09144–R09160) + Eval 6 inputs + 10-field EvalResult + feeds-router (R09161–R09164) + Observability 10-field + 6 enablement (R09165–R09168) + AVX Cortex 5 inputs + 6 operations + 4-output + portability doctrine (R09169–R09174) + Architectural Rule + 6 replacements + contracts-remain + sovereign-future-proof (R09175–R09178) + cross-repo + composite (R09179–R09180)
- Source range 403 lines (16493–16896) yields 170 R-rows representing ~42% line-coverage at the verbatim-citation level
- Project boundary — M054 is sovereign-os 11-typed-interfaces blueprint; selfdef MS001-MS035 align with these contracts; cross-repo binding via MS007 surface-manifest typed-mirror crate

## Cross-references

- Adjacent dump-range milestones: M053 Implementation language — 11 build phases (15915–16493) / M055 Failure modes — 10 taxonomies (next; dump 16896–17215)
- Each typed interface corresponds to multiple prior + future milestones (Gateway = M033 + M034 + M048 / Profile Resolver = M042 / Router = M043 / Model Adapter = M026 + M032 + M046 / Policy = M049 + MS017 + MS033 / Tool = MS032 + MS034 / Memory = M028 / Workflow = M025 / Eval = M027 + M037 / Observability = M045 + M048 + M049 / AVX Cortex = M039 + M043 + M050 + M051)
- Architectural Rule "Each module should be replaceable" — synthesizes M050 Design Law + M052 Vision invariants into substitution-grade contracts
- Selfdef integration — MS001 daemon core + MS017 agent-guard + MS027 observability + MS033 Phase 3 Policy + MS034 Communication Boundary + MS035 Capability Tokens all align with the 11 typed interfaces
- Cross-repo binding — MS007 surface-manifest + audit-manifest + dashboard-manifest + doc-manifest typed-mirror crates carry the 11 interface schemas across selfdef + sovereign-os
- Operator references: dump 16493–16896 (11 typed interfaces) + cross-ref to M053 11 build phases + M050 Design Law + M052 Vision Recap
