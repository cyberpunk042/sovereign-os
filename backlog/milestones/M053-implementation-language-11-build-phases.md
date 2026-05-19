# M053 — Implementation language — 11 build phases (Phase 0..10)

> Parent: `backlog/milestones/INDEX.md` row M053 (dump 15915–16493).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 15915–16493. Operator directive 15915: "Great. now lets start talking more in language to transpose all this in a future implementation conversation. making sure we output enough details and reasonings. we are about to do complex things" + continuation 16493: "continue".
> All entries below extract verbatim. No invention.

## Epics (E0508–E0517)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0508 | Vision → implementation shift + framing — "We should now shift from vision into implementation language: precise enough that a future coding session can pick it up, but still architectural enough that we don't prematurely freeze the system"; framing — "We are building a user-sovereign AI workstation runtime. It is not a single agent, model server, or UI. It is a hardware-aware intelligence substrate that routes work across local GPUs, CPU AVX-512 logic, tools, sandboxes, memory, and optional cloud providers under explicit user profiles and policies" | 15920–15952 |
| E0509 | Implementation Thesis — 3 intelligence organs: 1) Blackwell Oracle (High-quality, high-cost, high-context reasoning) / 2) 3090 Scout (Cheap, fast, speculative, sandboxable intelligence) / 3) AVX-512 Cortex (Deterministic scheduling, policy, masks, memory filtering, and workflow state); + 7 enabling subsystems: Gateway (lets external tools call the system) / Policy (decides what is allowed) / Memory (gives continuity) / Workflow (gives structure) / Sandbox (makes action safe) / Observability (makes behavior legible) / Evals (make improvement measurable) | 15956–16008 |
| E0510 | Core Runtime Sentence — "Models propose; the runtime commits"; meaning — "A model may propose text, code, tool calls, memory writes, file edits, cloud calls, or workflow transitions. The deterministic runtime decides whether those proposals are allowed, routed, verified, sandboxed, escalated, committed, or rejected" | 16014–16030 |
| E0511 | First Implementation Boundary — "Do not begin by building every feature. Begin with a thin vertical slice"; 7-step vertical slice: Client request → local gateway → profile resolution → model route → tool/policy trace → response → replay record; later additions (5): memory + sandboxes + evals + AVX hot path + LoRA/model lab | 16034–16066 |
| E0512 | Shared Vocabulary — 10 canonical terms with definitions: Profile (user-facing operating mode, e.g. fast/private/careful/autonomous) / Policy (hard authorization and safety rules) / Route (selected execution path across models/tools/hardware) / Frame (unit of cognitive work or state transition) / Trace (observed execution history) / Commit (accepted state change or side effect) / Memory (governed persistent knowledge, not raw chat history) / Oracle (expensive high-quality model route) / Scout (cheap speculative model route) / Cortex (deterministic CPU-side scheduler/policy engine) | 16070–16108 |
| E0513 | Core Data Objects — 9 canonical schemas: Request (client input + metadata + requested profile) / Profile (weights and defaults for cost/risk/quality/privacy/autonomy) / PolicyDecision (allow / deny / ask / sandbox / escalate) / ModelRoute (provider, model, hardware target, precision, adapter, budget) / Frame (branch state, workflow node, risk, budget, refs) / ToolIntent (requested action, capabilities, side effects, rollback) / TraceEvent (what happened, when, by whom, cost, result) / MemoryRef (pointer to governed memory with trust/privacy/freshness) / EvalResult (quality/cost/risk/outcome score); North Star — "Every module should expose: state / configuration / events / policy hooks / observability / fallback behavior. If a module cannot explain what it did, it is not ready for autonomy" | 16112–16170 |
| E0514 | Phase 0 + Phase 1 + Phase 2 — Phase 0 Platform Truth (Know what the machine actually is; validate CPU flags + GPU topology + Driver stack + Storage + OS security; output = hardware capability report; "This prevents fantasy architecture") / Phase 1 Gateway Spine (Make existing tools talk to the station; Anthropic-first /v1/messages /v1/models basic streaming + model aliases + profile selection + trace id per request; then OpenAI-compatible shim + embeddings + cost ledger + cloud toggle + redaction hooks; routing model = jean/local-fast + jean/oracle + jean/private; "The important part is owning the front door") / Phase 2 Model Fabric (Run multiple local model roles; Blackwell oracle server + 3090 scout server + embedding/rerank service + model registry + health checks; registry tracks model role + hardware target + precision + context + latency + VRAM + quality notes + eval scores + adapter support; "Do not chase too many models at first. Establish the pattern") | 16174–16252 |
| E0515 | Phase 3 + Phase 4 + Phase 5 — Phase 3 Policy And Trace (Every action becomes observable and governed; 5-element Add list + 7-step model-call trace template + 5-step tool-call trace template + "Even before sophisticated policy, the shape matters") / Phase 4 Sandbox Execution (Let agents act without trusting them blindly; 5 starter tiers + 4 future tiers + runtime rule "tool intent is not execution") / Phase 5 Memory And MAP (Make the station situated; project map + repo map + tool map + test map + memory refs + trace search; then episodic + semantic + procedural + temporal graph + RLM navigation; first useful memory not fancy — What tests exist? What commands worked? What failed last time? Which files matter? What did the user prefer?) | 16256–16324 |
| E0516 | Phase 6 + Phase 7 — Phase 6 Evals And Goldilocks (Make adaptation measurable; 8-element scoring catalog: correctness + test pass + schema validity + latency + cost + risk + human intervention + rollback needed; profiles become weighted policies — fast latency-high verification-lower / careful correctness-test-evidence high / private locality-privacy absolute / autonomous reversibility-trace-completeness high; "This is where 'adaptive' stops being a slogan") / Phase 7 AVX-512 Cortex (Move hot deterministic work into optimized CPU paths; "Do not start here. Start after data shapes stabilize"; 6 targets: branch table filtering + memory bitset intersection + policy mask fusion + candidate compression + reward-vector scoring + token/schema mask operations; implementation style — portable baseline first + benchmarks + AVX2 + AVX-512 Zen5 path; "This phase turns architecture into performance") | 16328–16382 |
| E0517 | Phase 8 + Phase 9 + Phase 10 + Critical Build Order + final guiding question — Phase 8 Model Lab And LoRA Foundry (Make the station evolve; compression benchmarks + FP8/GPTQ/SmoothQuant/AWQ/NVFP4 experiments + trace curation + dataset generation + LoRA training + multi-LoRA serving + adapter eval gates; rule "No adapter becomes a profile default until evals prove it") / Phase 9 Continuity (Let work survive time; workflow hibernation + ZFS snapshot per risky action + sandbox checkpoints + warm model sessions + resume tokens + long-running task state; "This makes the system feel alive") / Phase 10 Full Cockpit (Let the user see and steer everything; UI surfaces 11: active sessions + profile choices + model health + costs + traces + pending approvals + memory changes + rollback points + hardware pressure + eval history + adapter status; "This is fullstack, but serious fullstack: the cockpit of an intelligence machine") / Critical Build Order 10-step: know hardware → own gateway → route models → trace everything → gate tools → add memory → add evals → optimize with AVX → adapt with LoRA → deepen continuity; "That order keeps the system useful at every stage" / final guiding question: "What is the smallest vertical slice that increases sovereignty, intelligence, or continuity?" | 16386–16493 |

## Modules (M00884–M00900)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00884 | Vision → implementation shift — "shift from vision into implementation language" | 15920 | E0508 |
| M00885 | Implementation framing — "user-sovereign AI workstation runtime" | 15948 | E0508 |
| M00886 | 3 intelligence organs — Blackwell Oracle / 3090 Scout / AVX-512 Cortex | 15960–15980 | E0509 |
| M00887 | 7 enabling subsystems — Gateway / Policy / Memory / Workflow / Sandbox / Observability / Evals | 15986–16006 | E0509 |
| M00888 | Core Runtime Sentence — "Models propose; the runtime commits" | 16016 | E0510 |
| M00889 | 7-step thin vertical slice — Client request / local gateway / profile resolution / model route / tool-policy trace / response / replay record | 16040–16054 | E0511 |
| M00890 | 5 later additions — memory / sandboxes / evals / AVX hot path / LoRA-model lab | 16060–16066 | E0511 |
| M00891 | 10-term Shared Vocabulary — Profile / Policy / Route / Frame / Trace / Commit / Memory / Oracle / Scout / Cortex | 16074–16106 | E0512 |
| M00892 | 9 Core Data Objects — Request / Profile / PolicyDecision / ModelRoute / Frame / ToolIntent / TraceEvent / MemoryRef / EvalResult | 16114–16158 | E0513 |
| M00893 | 6-property module exposure standard — state / configuration / events / policy hooks / observability / fallback behavior | 16164–16168 | E0513 |
| M00894 | Phase 0 — Platform Truth (5-validate / output hardware capability report) | 16176–16208 | E0514 |
| M00895 | Phase 1 — Gateway Spine (Anthropic-first 6 items + 5 then-items + 3-model-alias routing) | 16212–16234 | E0514 |
| M00896 | Phase 2 — Model Fabric (5-service minimum + 9-field registry tracking + "Do not chase too many models at first") | 16238–16252 | E0514 |
| M00897 | Phase 3-4-5 (Policy & Trace / Sandbox Execution / Memory & MAP) — directly cite MS033 + MS032 + future Memory plane milestones | 16256–16324 | E0515 |
| M00898 | Phase 6-7 (Evals & Goldilocks / AVX-512 Cortex) — 8-element scoring + 4 profile-weighted policies + 6 AVX-512 targets + 4-step implementation style | 16328–16382 | E0516 |
| M00899 | Phase 8-9-10 (Model Lab & LoRA / Continuity / Full Cockpit) — 7-element LoRA pipeline + 6-element continuity + 11-element UI surface | 16386–16454 | E0517 |
| M00900 | 10-step Critical Build Order + final guiding question — "What is the smallest vertical slice that increases sovereignty, intelligence, or continuity?" | 16458–16493 | E0517 |

## Features (F04421–F04505)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F04421 | Operator directive — "start talking more in language to transpose all this in a future implementation conversation" | 15915 | E0508 |
| F04422 | Operator directive — "making sure we output enough details and reasonings. we are about to do complex things" | 15915 | E0508 |
| F04423 | Vision → implementation shift — "shift from vision into implementation language" | 15920 | M00884 |
| F04424 | Shift goal — "precise enough that a future coding session can pick it up" | 15921 | M00884 |
| F04425 | Shift goal — "still architectural enough that we don't prematurely freeze the system" | 15923 | M00884 |
| F04426 | Framing — "We are building a user-sovereign AI workstation runtime" | 15948 | M00885 |
| F04427 | Framing — "It is not a single agent, model server, or UI" | 15950 | M00885 |
| F04428 | Framing — "It is a hardware-aware intelligence substrate that routes work across local GPUs, CPU AVX-512 logic, tools, sandboxes, memory, and optional cloud providers under explicit user profiles and policies" | 15952 | M00885 |
| F04429 | Intelligence organ 1 — Blackwell Oracle (High-quality, high-cost, high-context reasoning) | 15962–15966 | M00886 |
| F04430 | Intelligence organ 2 — 3090 Scout (Cheap, fast, speculative, sandboxable intelligence) | 15970–15974 | M00886 |
| F04431 | Intelligence organ 3 — AVX-512 Cortex (Deterministic scheduling, policy, masks, memory filtering, and workflow state) | 15978–15982 | M00886 |
| F04432 | Enabling — Gateway (lets external tools call the system) | 15986 | M00887 |
| F04433 | Enabling — Policy (decides what is allowed) | 15990 | M00887 |
| F04434 | Enabling — Memory (gives continuity) | 15994 | M00887 |
| F04435 | Enabling — Workflow (gives structure) | 15996 | M00887 |
| F04436 | Enabling — Sandbox (makes action safe) | 15998 | M00887 |
| F04437 | Enabling — Observability (makes behavior legible) | 16002 | M00887 |
| F04438 | Enabling — Evals (make improvement measurable) | 16006 | M00887 |
| F04439 | Core Runtime Sentence — "Models propose; the runtime commits" | 16016 | M00888 |
| F04440 | Meaning — model may propose text | 16020 | E0510 |
| F04441 | Meaning — model may propose code | 16020 | E0510 |
| F04442 | Meaning — model may propose tool calls | 16021 | E0510 |
| F04443 | Meaning — model may propose memory writes | 16021 | E0510 |
| F04444 | Meaning — model may propose file edits | 16021 | E0510 |
| F04445 | Meaning — model may propose cloud calls | 16022 | E0510 |
| F04446 | Meaning — model may propose workflow transitions | 16022 | E0510 |
| F04447 | Meaning — runtime decides allowed | 16026 | E0510 |
| F04448 | Meaning — runtime decides routed | 16026 | E0510 |
| F04449 | Meaning — runtime decides verified | 16027 | E0510 |
| F04450 | Meaning — runtime decides sandboxed | 16027 | E0510 |
| F04451 | Meaning — runtime decides escalated | 16028 | E0510 |
| F04452 | Meaning — runtime decides committed | 16028 | E0510 |
| F04453 | Meaning — runtime decides rejected | 16029 | E0510 |
| F04454 | "Do not begin by building every feature. Begin with a thin vertical slice" | 16034–16036 | M00889 |
| F04455 | Vertical slice step 1 — Client request | 16040 | M00889 |
| F04456 | Vertical slice step 2 — local gateway | 16042 | M00889 |
| F04457 | Vertical slice step 3 — profile resolution | 16044 | M00889 |
| F04458 | Vertical slice step 4 — model route | 16046 | M00889 |
| F04459 | Vertical slice step 5 — tool/policy trace | 16048 | M00889 |
| F04460 | Vertical slice step 6 — response | 16050 | M00889 |
| F04461 | Vertical slice step 7 — replay record | 16054 | M00889 |
| F04462 | Later addition — memory | 16060 | M00890 |
| F04463 | Later addition — sandboxes | 16061 | M00890 |
| F04464 | Later addition — evals | 16062 | M00890 |
| F04465 | Later addition — AVX hot path | 16064 | M00890 |
| F04466 | Later addition — LoRA/model lab | 16066 | M00890 |
| F04467 | Shared Vocabulary — Profile (user-facing operating mode, e.g. fast/private/careful/autonomous) | 16076–16078 | M00891 |
| F04468 | Shared Vocabulary — Policy (hard authorization and safety rules) | 16080–16082 | M00891 |
| F04469 | Shared Vocabulary — Route (selected execution path across models/tools/hardware) | 16084–16086 | M00891 |
| F04470 | Shared Vocabulary — Frame (unit of cognitive work or state transition) | 16088–16090 | M00891 |
| F04471 | Shared Vocabulary — Trace (observed execution history) | 16092–16094 | M00891 |
| F04472 | Shared Vocabulary — Commit (accepted state change or side effect) | 16096–16098 | M00891 |
| F04473 | Shared Vocabulary — Memory (governed persistent knowledge, not raw chat history) | 16100–16102 | M00891 |
| F04474 | Shared Vocabulary — Oracle (expensive high-quality model route) | 16104 | M00891 |
| F04475 | Shared Vocabulary — Scout (cheap speculative model route) | 16105 | M00891 |
| F04476 | Shared Vocabulary — Cortex (deterministic CPU-side scheduler/policy engine) | 16106 | M00891 |
| F04477 | Core Data Object — Request (client input + metadata + requested profile) | 16114–16116 | M00892 |
| F04478 | Core Data Object — Profile (weights and defaults for cost/risk/quality/privacy/autonomy) | 16118–16120 | M00892 |
| F04479 | Core Data Object — PolicyDecision (allow / deny / ask / sandbox / escalate) | 16122–16124 | M00892 |
| F04480 | Core Data Object — ModelRoute (provider, model, hardware target, precision, adapter, budget) | 16126–16128 | M00892 |
| F04481 | Core Data Object — Frame (branch state, workflow node, risk, budget, refs) | 16130–16132 | M00892 |
| F04482 | Core Data Object — ToolIntent (requested action, capabilities, side effects, rollback) | 16134–16136 | M00892 |
| F04483 | Core Data Object — TraceEvent (what happened, when, by whom, cost, result) | 16138–16140 | M00892 |
| F04484 | Core Data Object — MemoryRef (pointer to governed memory with trust/privacy/freshness) | 16142–16144 | M00892 |
| F04485 | Core Data Object — EvalResult (quality/cost/risk/outcome score) | 16146–16148 | M00892 |
| F04486 | Module North Star — state + configuration + events + policy hooks + observability + fallback behavior + "If a module cannot explain what it did, it is not ready for autonomy" | 16162–16170 | M00893 |
| F04487 | Phase 0 — Platform Truth (CPU flags + GPU topology + Driver stack + Storage + OS security → hardware capability report → "prevents fantasy architecture") | 16176–16208 | M00894 |
| F04488 | Phase 1 — Gateway Spine (Anthropic-first /v1/messages /v1/models + streaming + model aliases + profile + trace_id; then OpenAI shim + embeddings + cost ledger + cloud toggle + redaction hooks; jean/local-fast / jean/oracle / jean/private; "important part is owning the front door") | 16212–16234 | M00895 |
| F04489 | Phase 2 — Model Fabric (Blackwell oracle + 3090 scout + embedding/rerank service + model registry + health checks; 9-field registry; "Do not chase too many models at first. Establish the pattern") | 16238–16252 | M00896 |
| F04490 | Phase 3 — Policy And Trace (5-element Add list + 7-step model-call trace + 5-step tool-call trace + "shape matters") cross-ref MS033 | 16256–16286 | M00897 |
| F04491 | Phase 4 — Sandbox Execution (5 starter tiers + 4 future tiers + "tool intent is not execution") cross-ref MS032 | 16290–16308 | M00897 |
| F04492 | Phase 5 — Memory And MAP (project map + repo map + tool map + test map + memory refs + trace search; then episodic + semantic + procedural + temporal graph + RLM nav; first useful memory not fancy) | 16312–16324 | M00897 |
| F04493 | Phase 6 — Evals And Goldilocks (8-element scoring + 4 profile-weighted policies + "adaptive stops being a slogan") | 16328–16356 | M00898 |
| F04494 | Phase 7 — AVX-512 Cortex (do not start here; start after data shapes stabilize; 6 targets + 4-step impl style + "turns architecture into performance") | 16360–16382 | M00898 |
| F04495 | Phase 8 — Model Lab And LoRA Foundry (compression benchmarks + FP8/GPTQ/SmoothQuant/AWQ/NVFP4 + trace curation + dataset gen + LoRA training + multi-LoRA serving + adapter eval gates + "No adapter becomes a profile default until evals prove it") | 16386–16410 | M00899 |
| F04496 | Phase 9 — Continuity (workflow hibernation + ZFS snapshot per risky action + sandbox checkpoints + warm model sessions + resume tokens + long-running task state + "makes the system feel alive") | 16414–16432 | M00899 |
| F04497 | Phase 10 — Full Cockpit (11 UI surfaces + "cockpit of an intelligence machine") | 16436–16454 | M00899 |
| F04498 | Critical Build Order — step 1 know hardware | 16462 | M00900 |
| F04499 | Critical Build Order — step 2 own gateway | 16464 | M00900 |
| F04500 | Critical Build Order — step 3 route models | 16465 | M00900 |
| F04501 | Critical Build Order — step 4 trace everything | 16466 | M00900 |
| F04502 | Critical Build Order — step 5 gate tools + step 6 add memory + step 7 add evals + step 8 optimize with AVX + step 9 adapt with LoRA + step 10 deepen continuity | 16467–16472 | M00900 |
| F04503 | Critical Build Order — "That order keeps the system useful at every stage" | 16476 | M00900 |
| F04504 | Final guiding question — "What is the smallest vertical slice that increases sovereignty, intelligence, or continuity?" | 16482 | M00900 |
| F04505 | "The future implementation conversation should stay disciplined around this question" | 16480 | M00900 |

## Requirements (R08841–R09010)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R08841 | Operator directive — "start talking more in language to transpose all this in a future implementation conversation" | 15915 | F04421 | non-negotiable | false | 10 |
| R08842 | Operator directive — "making sure we output enough details and reasonings. we are about to do complex things" | 15915 | F04422 | non-negotiable | false | 10 |
| R08843 | Shift goal — "shift from vision into implementation language" | 15920 | F04423 | non-negotiable | false | 10 |
| R08844 | Shift goal — "precise enough that a future coding session can pick it up" | 15921 | F04424 | non-negotiable | false | 10 |
| R08845 | Shift goal — "still architectural enough that we don't prematurely freeze the system" | 15923 | F04425 | non-negotiable | false | 10 |
| R08846 | Framing — "We are building a user-sovereign AI workstation runtime" | 15948 | F04426 | non-negotiable | false | 10 |
| R08847 | Framing — "It is not a single agent, model server, or UI" | 15950 | F04427 | non-negotiable | false | 10 |
| R08848 | Framing — "hardware-aware intelligence substrate that routes work across local GPUs, CPU AVX-512 logic, tools, sandboxes, memory, and optional cloud providers under explicit user profiles and policies" | 15952 | F04428 | non-negotiable | false | 10 |
| R08849 | Organ 1 — Blackwell Oracle | 15962 | F04429 | non-negotiable | false | 10 |
| R08850 | Organ 1 role — "High-quality, high-cost, high-context reasoning" | 15966 | F04429 | non-negotiable | false | 10 |
| R08851 | Organ 2 — 3090 Scout | 15970 | F04430 | non-negotiable | false | 10 |
| R08852 | Organ 2 role — "Cheap, fast, speculative, sandboxable intelligence" | 15974 | F04430 | non-negotiable | false | 10 |
| R08853 | Organ 3 — AVX-512 Cortex | 15978 | F04431 | non-negotiable | false | 10 |
| R08854 | Organ 3 role — "Deterministic scheduling, policy, masks, memory filtering, and workflow state" | 15982 | F04431 | non-negotiable | false | 10 |
| R08855 | Enabling — Gateway (lets external tools call the system) | 15986 | F04432 | non-negotiable | false | 10 |
| R08856 | Enabling — Policy (decides what is allowed) | 15990 | F04433 | non-negotiable | false | 10 |
| R08857 | Enabling — Memory (gives continuity) | 15994 | F04434 | non-negotiable | false | 10 |
| R08858 | Enabling — Workflow (gives structure) | 15996 | F04435 | non-negotiable | false | 10 |
| R08859 | Enabling — Sandbox (makes action safe) | 15998 | F04436 | non-negotiable | false | 10 |
| R08860 | Enabling — Observability (makes behavior legible) | 16002 | F04437 | non-negotiable | false | 10 |
| R08861 | Enabling — Evals (make improvement measurable) | 16006 | F04438 | non-negotiable | false | 10 |
| R08862 | Core Runtime Sentence — "Models propose; the runtime commits" | 16016 | F04439 | non-negotiable | false | 10 |
| R08863 | Meaning — proposes text | 16020 | F04440 | non-negotiable | false | 10 |
| R08864 | Meaning — proposes code | 16020 | F04441 | non-negotiable | false | 10 |
| R08865 | Meaning — proposes tool calls | 16021 | F04442 | non-negotiable | false | 10 |
| R08866 | Meaning — proposes memory writes | 16021 | F04443 | non-negotiable | false | 10 |
| R08867 | Meaning — proposes file edits | 16021 | F04444 | non-negotiable | false | 10 |
| R08868 | Meaning — proposes cloud calls | 16022 | F04445 | non-negotiable | false | 10 |
| R08869 | Meaning — proposes workflow transitions | 16022 | F04446 | non-negotiable | false | 10 |
| R08870 | Meaning — runtime decides allowed | 16026 | F04447 | non-negotiable | false | 10 |
| R08871 | Meaning — runtime decides routed | 16026 | F04448 | non-negotiable | false | 10 |
| R08872 | Meaning — runtime decides verified | 16027 | F04449 | non-negotiable | false | 10 |
| R08873 | Meaning — runtime decides sandboxed | 16027 | F04450 | non-negotiable | false | 10 |
| R08874 | Meaning — runtime decides escalated | 16028 | F04451 | non-negotiable | false | 10 |
| R08875 | Meaning — runtime decides committed | 16028 | F04452 | non-negotiable | false | 10 |
| R08876 | Meaning — runtime decides rejected | 16029 | F04453 | non-negotiable | false | 10 |
| R08877 | "Do not begin by building every feature" | 16034 | F04454 | non-negotiable | false | 10 |
| R08878 | "Begin with a thin vertical slice" | 16036 | F04454 | non-negotiable | false | 10 |
| R08879 | Vertical slice — Client request | 16040 | F04455 | non-negotiable | false | 10 |
| R08880 | Vertical slice — local gateway | 16042 | F04456 | non-negotiable | false | 10 |
| R08881 | Vertical slice — profile resolution | 16044 | F04457 | non-negotiable | false | 10 |
| R08882 | Vertical slice — model route | 16046 | F04458 | non-negotiable | false | 10 |
| R08883 | Vertical slice — tool/policy trace | 16048 | F04459 | non-negotiable | false | 10 |
| R08884 | Vertical slice — response | 16050 | F04460 | non-negotiable | false | 10 |
| R08885 | Vertical slice — replay record | 16054 | F04461 | non-negotiable | false | 10 |
| R08886 | Later addition — memory | 16060 | F04462 | non-negotiable | false | 10 |
| R08887 | Later addition — sandboxes | 16061 | F04463 | non-negotiable | false | 10 |
| R08888 | Later addition — evals | 16062 | F04464 | non-negotiable | false | 10 |
| R08889 | Later addition — AVX hot path | 16064 | F04465 | non-negotiable | false | 10 |
| R08890 | Later addition — LoRA/model lab | 16066 | F04466 | non-negotiable | false | 10 |
| R08891 | Vocab — Profile (user-facing operating mode) | 16076 | F04467 | non-negotiable | false | 10 |
| R08892 | Vocab — Profile examples (fast/private/careful/autonomous) | 16078 | F04467 | non-negotiable | false | 10 |
| R08893 | Vocab — Policy (hard authorization and safety rules) | 16080–16082 | F04468 | non-negotiable | false | 10 |
| R08894 | Vocab — Route (selected execution path across models/tools/hardware) | 16084–16086 | F04469 | non-negotiable | false | 10 |
| R08895 | Vocab — Frame (unit of cognitive work or state transition) | 16088–16090 | F04470 | non-negotiable | false | 10 |
| R08896 | Vocab — Trace (observed execution history) | 16092–16094 | F04471 | non-negotiable | false | 10 |
| R08897 | Vocab — Commit (accepted state change or side effect) | 16096–16098 | F04472 | non-negotiable | false | 10 |
| R08898 | Vocab — Memory (governed persistent knowledge, not raw chat history) | 16100–16102 | F04473 | non-negotiable | false | 10 |
| R08899 | Vocab — Oracle (expensive high-quality model route) | 16104 | F04474 | non-negotiable | false | 10 |
| R08900 | Vocab — Scout (cheap speculative model route) | 16105 | F04475 | non-negotiable | false | 10 |
| R08901 | Vocab — Cortex (deterministic CPU-side scheduler/policy engine) | 16106 | F04476 | non-negotiable | false | 10 |
| R08902 | Data object — Request (client input + metadata + requested profile) | 16114–16116 | F04477 | non-negotiable | false | 10 |
| R08903 | Data object — Profile (weights and defaults for cost/risk/quality/privacy/autonomy) | 16118–16120 | F04478 | non-negotiable | false | 10 |
| R08904 | Data object — PolicyDecision outcomes (allow/deny/ask/sandbox/escalate) | 16124 | F04479 | non-negotiable | false | 10 |
| R08905 | Data object — ModelRoute (provider/model/hardware target/precision/adapter/budget) | 16128 | F04480 | non-negotiable | false | 10 |
| R08906 | Data object — Frame (branch state/workflow node/risk/budget/refs) | 16132 | F04481 | non-negotiable | false | 10 |
| R08907 | Data object — ToolIntent (requested action/capabilities/side effects/rollback) | 16136 | F04482 | non-negotiable | false | 10 |
| R08908 | Data object — TraceEvent (what happened/when/by whom/cost/result) | 16140 | F04483 | non-negotiable | false | 10 |
| R08909 | Data object — MemoryRef (pointer to governed memory with trust/privacy/freshness) | 16144 | F04484 | non-negotiable | false | 10 |
| R08910 | Data object — EvalResult (quality/cost/risk/outcome score) | 16148 | F04485 | non-negotiable | false | 10 |
| R08911 | Module exposure — state | 16164 | F04486 | non-negotiable | false | 10 |
| R08912 | Module exposure — configuration | 16164 | F04486 | non-negotiable | false | 10 |
| R08913 | Module exposure — events | 16165 | F04486 | non-negotiable | false | 10 |
| R08914 | Module exposure — policy hooks | 16165 | F04486 | non-negotiable | false | 10 |
| R08915 | Module exposure — observability | 16166 | F04486 | non-negotiable | false | 10 |
| R08916 | Module exposure — fallback behavior | 16167 | F04486 | non-negotiable | false | 10 |
| R08917 | "If a module cannot explain what it did, it is not ready for autonomy" | 16170 | F04486 | non-negotiable | false | 10 |
| R08918 | Phase 0 — Platform Truth header | 16176 | F04487 | non-negotiable | false | 10 |
| R08919 | Phase 0 goal — "Know what the machine actually is" | 16180 | F04487 | non-negotiable | false | 10 |
| R08920 | Phase 0 validate — CPU flags (AVX-512 subsets, VNNI, BF16, VPOPCNTDQ, VP2INTERSECT) | 16184–16186 | F04487 | non-negotiable | false | 10 |
| R08921 | Phase 0 validate — GPU topology (Blackwell visible, 3090 visible, PCIe width, NUMA/IOMMU groups) | 16188–16190 | F04487 | non-negotiable | false | 10 |
| R08922 | Phase 0 validate — Driver stack (NVIDIA driver, CUDA, container toolkit, vLLM/SGLang/TRT-LLM viability) | 16192–16194 | F04487 | non-negotiable | false | 10 |
| R08923 | Phase 0 validate — Storage (ZFS pool layout, snapshot/rollback behavior, NVMe thermal behavior) | 16196–16198 | F04487 | non-negotiable | false | 10 |
| R08924 | Phase 0 validate — OS security (AppArmor, cgroup v2, Podman, VFIO, user namespaces, LUKS) | 16200–16202 | F04487 | non-negotiable | false | 10 |
| R08925 | Phase 0 output — hardware capability report | 16206 | F04487 | non-negotiable | false | 10 |
| R08926 | Phase 0 — "This prevents fantasy architecture" | 16208 | F04487 | non-negotiable | false | 10 |
| R08927 | Phase 1 — Gateway Spine header | 16212 | F04488 | non-negotiable | false | 10 |
| R08928 | Phase 1 goal — "Make existing tools talk to the station" | 16216 | F04488 | non-negotiable | false | 10 |
| R08929 | Phase 1 endpoint — /v1/messages | 16220 | F04488 | non-negotiable | false | 10 |
| R08930 | Phase 1 endpoint — /v1/models | 16221 | F04488 | non-negotiable | false | 10 |
| R08931 | Phase 1 — basic streaming | 16222 | F04488 | non-negotiable | false | 10 |
| R08932 | Phase 1 — model aliases | 16223 | F04488 | non-negotiable | false | 10 |
| R08933 | Phase 1 — profile selection | 16224 | F04488 | non-negotiable | false | 10 |
| R08934 | Phase 1 — trace id per request | 16225 | F04488 | non-negotiable | false | 10 |
| R08935 | Phase 1 then — OpenAI-compatible shim | 16229 | F04488 | non-negotiable | false | 10 |
| R08936 | Phase 1 then — embeddings endpoint | 16230 | F04488 | non-negotiable | false | 10 |
| R08937 | Phase 1 then — cost ledger | 16231 | F04488 | non-negotiable | false | 10 |
| R08938 | Phase 1 then — cloud toggle | 16232 | F04488 | non-negotiable | false | 10 |
| R08939 | Phase 1 then — redaction hooks | 16233 | F04488 | non-negotiable | false | 10 |
| R08940 | Phase 1 model alias — jean/local-fast | 16237 | F04488 | non-negotiable | false | 10 |
| R08941 | Phase 1 model alias — jean/oracle | 16238 | F04488 | non-negotiable | false | 10 |
| R08942 | Phase 1 model alias — jean/private | 16239 | F04488 | non-negotiable | false | 10 |
| R08943 | Phase 1 — "The important part is owning the front door" | 16234 | F04488 | non-negotiable | false | 10 |
| R08944 | Phase 2 — Model Fabric header | 16238 | F04489 | non-negotiable | false | 10 |
| R08945 | Phase 2 goal — "Run multiple local model roles" | 16242 | F04489 | non-negotiable | false | 10 |
| R08946 | Phase 2 minimum — Blackwell oracle server | 16246 | F04489 | non-negotiable | false | 10 |
| R08947 | Phase 2 minimum — 3090 scout server | 16247 | F04489 | non-negotiable | false | 10 |
| R08948 | Phase 2 minimum — embedding/rerank service | 16248 | F04489 | non-negotiable | false | 10 |
| R08949 | Phase 2 minimum — model registry | 16249 | F04489 | non-negotiable | false | 10 |
| R08950 | Phase 2 minimum — health checks | 16250 | F04489 | non-negotiable | false | 10 |
| R08951 | Phase 2 registry tracks — model role | 16254 | F04489 | non-negotiable | false | 10 |
| R08952 | Phase 2 registry tracks — hardware target | 16255 | F04489 | non-negotiable | false | 10 |
| R08953 | Phase 2 registry tracks — precision | 16256 | F04489 | non-negotiable | false | 10 |
| R08954 | Phase 2 registry tracks — context | 16257 | F04489 | non-negotiable | false | 10 |
| R08955 | Phase 2 registry tracks — latency | 16258 | F04489 | non-negotiable | false | 10 |
| R08956 | Phase 2 registry tracks — VRAM | 16259 | F04489 | non-negotiable | false | 10 |
| R08957 | Phase 2 registry tracks — quality notes | 16260 | F04489 | non-negotiable | false | 10 |
| R08958 | Phase 2 registry tracks — eval scores | 16261 | F04489 | non-negotiable | false | 10 |
| R08959 | Phase 2 registry tracks — adapter support | 16262 | F04489 | non-negotiable | false | 10 |
| R08960 | Phase 2 — "Do not chase too many models at first. Establish the pattern" | 16252 | F04489 | non-negotiable | false | 10 |
| R08961 | Phase 3 — see MS033 (Policy And Trace) | 16256 | F04490 | non-negotiable | false | 10 |
| R08962 | Phase 4 — see MS032 (Sandbox Execution) | 16290 | F04491 | non-negotiable | false | 10 |
| R08963 | Phase 5 — Memory And MAP header | 16312 | F04492 | non-negotiable | false | 10 |
| R08964 | Phase 5 goal — "Make the station situated" | 16314 | F04492 | non-negotiable | false | 10 |
| R08965 | Phase 5 first — project map | 16318 | F04492 | non-negotiable | false | 10 |
| R08966 | Phase 5 first — repo map | 16319 | F04492 | non-negotiable | false | 10 |
| R08967 | Phase 5 first — tool map | 16320 | F04492 | non-negotiable | false | 10 |
| R08968 | Phase 5 first — test map | 16320 | F04492 | non-negotiable | false | 10 |
| R08969 | Phase 5 first — memory refs | 16321 | F04492 | non-negotiable | false | 10 |
| R08970 | Phase 5 first — trace search | 16322 | F04492 | non-negotiable | false | 10 |
| R08971 | Phase 5 then — episodic + semantic + procedural + temporal graph + RLM navigation | 16326–16330 | F04492 | non-negotiable | false | 10 |
| R08972 | Phase 5 useful memory — What tests exist? | 16334 | F04492 | non-negotiable | false | 10 |
| R08973 | Phase 5 useful memory — What commands worked? | 16335 | F04492 | non-negotiable | false | 10 |
| R08974 | Phase 5 useful memory — What failed last time? | 16336 | F04492 | non-negotiable | false | 10 |
| R08975 | Phase 5 useful memory — Which files matter? | 16337 | F04492 | non-negotiable | false | 10 |
| R08976 | Phase 5 useful memory — What did the user prefer? | 16338 | F04492 | non-negotiable | false | 10 |
| R08977 | Phase 6 — Evals And Goldilocks header | 16328 | F04493 | non-negotiable | false | 10 |
| R08978 | Phase 6 goal — "Make adaptation measurable" | 16332 | F04493 | non-negotiable | false | 10 |
| R08979 | Phase 6 scoring — correctness | 16336 | F04493 | non-negotiable | false | 10 |
| R08980 | Phase 6 scoring — test pass | 16337 | F04493 | non-negotiable | false | 10 |
| R08981 | Phase 6 scoring — schema validity | 16338 | F04493 | non-negotiable | false | 10 |
| R08982 | Phase 6 scoring — latency | 16339 | F04493 | non-negotiable | false | 10 |
| R08983 | Phase 6 scoring — cost | 16340 | F04493 | non-negotiable | false | 10 |
| R08984 | Phase 6 scoring — risk | 16341 | F04493 | non-negotiable | false | 10 |
| R08985 | Phase 6 scoring — human intervention | 16342 | F04493 | non-negotiable | false | 10 |
| R08986 | Phase 6 scoring — rollback needed | 16343 | F04493 | non-negotiable | false | 10 |
| R08987 | Phase 6 weighted policy — fast (latency high, verification lower) | 16347–16349 | F04493 | non-negotiable | false | 10 |
| R08988 | Phase 6 weighted policy — careful (correctness/test/evidence high) | 16350–16352 | F04493 | non-negotiable | false | 10 |
| R08989 | Phase 6 weighted policy — private (locality/privacy absolute) | 16353–16355 | F04493 | non-negotiable | false | 10 |
| R08990 | Phase 6 weighted policy — autonomous (reversibility and trace completeness high) | 16356–16358 | F04493 | non-negotiable | false | 10 |
| R08991 | Phase 6 — "This is where 'adaptive' stops being a slogan" | 16356 | F04493 | non-negotiable | false | 10 |
| R08992 | Phase 7 — AVX-512 Cortex header | 16360 | F04494 | non-negotiable | false | 10 |
| R08993 | Phase 7 goal — "Move hot deterministic work into optimized CPU paths" | 16364 | F04494 | non-negotiable | false | 10 |
| R08994 | Phase 7 advice — "Do not start here. Start after data shapes stabilize" | 16368 | F04494 | non-negotiable | false | 10 |
| R08995 | Phase 7 target — branch table filtering + memory bitset intersection + policy mask fusion + candidate compression + reward-vector scoring + token/schema mask operations | 16372–16378 | F04494 | non-negotiable | false | 10 |
| R08996 | Phase 7 implementation style — portable baseline first + benchmarks + AVX2 + AVX-512 Zen5 path | 16380–16382 | F04494 | non-negotiable | false | 10 |
| R08997 | Phase 7 — "This phase turns architecture into performance" | 16382 | F04494 | non-negotiable | false | 10 |
| R08998 | Phase 8 — Model Lab And LoRA Foundry header + 7-step pipeline (compression benchmarks + FP8/GPTQ/SmoothQuant/AWQ/NVFP4 + trace curation + dataset gen + LoRA training + multi-LoRA serving + adapter eval gates) + "No adapter becomes a profile default until evals prove it" | 16386–16410 | F04495 | non-negotiable | false | 10 |
| R08999 | Phase 9 — Continuity header + 6-step (workflow hibernation + ZFS snapshot per risky action + sandbox checkpoints + warm model sessions + resume tokens + long-running task state) + "makes the system feel alive" | 16414–16432 | F04496 | non-negotiable | false | 10 |
| R09000 | Phase 10 — Full Cockpit header + 11 UI surfaces (active sessions + profile choices + model health + costs + traces + pending approvals + memory changes + rollback points + hardware pressure + eval history + adapter status) + "cockpit of an intelligence machine" | 16436–16454 | F04497 | non-negotiable | false | 10 |
| R09001 | Critical Build Order — step 1 know hardware | 16462 | F04498 | non-negotiable | false | 10 |
| R09002 | Critical Build Order — step 2 own gateway | 16464 | F04499 | non-negotiable | false | 10 |
| R09003 | Critical Build Order — step 3 route models | 16465 | F04500 | non-negotiable | false | 10 |
| R09004 | Critical Build Order — step 4 trace everything | 16466 | F04501 | non-negotiable | false | 10 |
| R09005 | Critical Build Order — step 5 gate tools | 16467 | F04502 | non-negotiable | false | 10 |
| R09006 | Critical Build Order — step 6 add memory + step 7 add evals + step 8 optimize with AVX + step 9 adapt with LoRA + step 10 deepen continuity | 16468–16472 | F04502 | non-negotiable | false | 10 |
| R09007 | Critical Build Order — "That order keeps the system useful at every stage" | 16476 | F04503 | non-negotiable | false | 10 |
| R09008 | Final question — "What is the smallest vertical slice that increases sovereignty, intelligence, or continuity?" | 16482 | F04504 | non-negotiable | false | 10 |
| R09009 | Implementation discipline — "The future implementation conversation should stay disciplined around this question" | 16480 | F04505 | non-negotiable | false | 10 |
| R09010 | Composite — M053 (10 epics / 17 modules / 85 features / 170 reqs) catalogs Implementation language + 11 build phases (Phase 0..10): operator vision-to-implementation shift + framing "user-sovereign AI workstation runtime" + 3 intelligence organs (Blackwell Oracle / 3090 Scout / AVX-512 Cortex) + 7 enabling subsystems + Core Runtime Sentence "Models propose; the runtime commits" + 7-step thin vertical slice + 5 later additions + 10-term Shared Vocabulary + 9 Core Data Objects + 6-property module exposure standard "if a module cannot explain what it did, it is not ready for autonomy" + Phase 0 Platform Truth (5-validate + hardware capability report + "prevents fantasy architecture") + Phase 1 Gateway Spine (Anthropic-first + 6-initial + 5-then + 3-model-alias + "owning the front door") + Phase 2 Model Fabric (5-service minimum + 9-field registry + "establish the pattern") + Phase 3 Policy And Trace (cross-ref MS033) + Phase 4 Sandbox Execution (cross-ref MS032) + Phase 5 Memory And MAP (6-first-step + 5-then-step + 5 useful-memory questions) + Phase 6 Evals And Goldilocks (8-element scoring + 4 weighted policies + "adaptive stops being a slogan") + Phase 7 AVX-512 Cortex (6 targets + 4-step impl style + "turns architecture into performance" + "do not start here") + Phase 8 Model Lab And LoRA Foundry (7-step + "no adapter becomes a default until evals prove it") + Phase 9 Continuity (6-step + "makes the system feel alive") + Phase 10 Full Cockpit (11 UI surfaces + "cockpit of an intelligence machine") + 10-step Critical Build Order + final guiding question "What is the smallest vertical slice that increases sovereignty, intelligence, or continuity?" | dump 15915–16493 | E0508-E0517 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: operator directives (R08841–R08842) + vision-to-implementation shift (R08843–R08848) + 3 intelligence organs (R08849–R08854) + 7 enabling subsystems (R08855–R08861) + Core Runtime Sentence + meaning (R08862–R08876) + 7-step vertical slice + 5 later additions (R08877–R08890) + 10-term Shared Vocabulary (R08891–R08901) + 9 Core Data Objects (R08902–R08910) + 6-property module exposure + "not ready for autonomy" (R08911–R08917) + Phase 0 Platform Truth full transcription (R08918–R08926) + Phase 1 Gateway Spine full transcription (R08927–R08943) + Phase 2 Model Fabric full transcription (R08944–R08960) + Phase 3+4 cross-refs (R08961–R08962) + Phase 5 Memory And MAP (R08963–R08976) + Phase 6 Evals And Goldilocks (R08977–R08991) + Phase 7 AVX-512 Cortex (R08992–R08997) + Phase 8+9+10 (R08998–R09000) + 10-step Critical Build Order (R09001–R09007) + final guiding question + discipline (R09008–R09009) + composite (R09010)
- Source range 578 lines (15915–16493) yields 170 R-rows representing ~29% line-coverage at the verbatim-citation level (the dump segment is the dense implementation language; many phase-internal details delegated to per-phase cross-ref milestones MS032/MS033 etc.)
- Project boundary — M053 is sovereign-os implementation-language + 11-build-phase blueprint scope; cross-repo binding to selfdef via MS007 doc-manifest typed-mirror crate; phase-internal details realized in adjacent milestones (Phase 3 = MS033, Phase 4 = MS032, Phase 5 = MS034 + future Memory plane, etc.)

## Cross-references

- Adjacent dump-range milestones: M052 Vision recap (15705–15915) / M054 11 typed interfaces (next; dump 16493–16896)
- Phase 0 Platform Truth — realized by selfdef MS010 hardware-tune-cache + selfdef-on-sain01 hardware capability report + sovereign-os M044 Sovereign-OS substrate
- Phase 1 Gateway Spine — realized by sovereign-os M033 Compatibility Gateway + M034 Anthropic-first Gateway + M048 Module 4 Gateway + M050 Section 4 + M051 Section 10
- Phase 2 Model Fabric — realized by selfdef MS028 bitnet + MS029 slm-cpu-loop + MS030 tensor-parallel + MS031 wasm-aot-cache + sovereign-os M026 SLM swarm + M032 Cloud Expert Plane + M046 LoRA foundry
- Phase 3 Policy And Trace — DIRECT match to selfdef MS033 + sovereign-os M049 Continuity through observability and policy
- Phase 4 Sandbox Execution — DIRECT match to selfdef MS032 + sovereign-os M048 Module 3 Container/Sandbox Fabric
- Phase 5 Memory And MAP — realized by sovereign-os M028 Memory OS + M036 MAP + M048 Module 5 Memory OS + future selfdef MS035-MS038 boundary milestones
- Phase 6 Evals And Goldilocks — realized by sovereign-os M027 Value Plane + M037 Spec/TDD/agent-evals + M048 Module 7 Eval/Value
- Phase 7 AVX-512 Cortex — realized by sovereign-os M039 AVX-512 cortex hot path + M043 AVX-512 Routing Brain + M050 + M051 + selfdef MS010 hardware-tune-cache + MS028 + MS029 + MS030 + MS031
- Phase 8 Model Lab And LoRA Foundry — DIRECT match to sovereign-os M046 LoRA foundry
- Phase 9 Continuity — DIRECT match to sovereign-os M047 Continuity + M048 Module 8 Continuity Manager
- Phase 10 Full Cockpit — DIRECT match to sovereign-os M048 Configuration Surfaces + M050 Section 10 Fullstack Surface + M051 Section 10 Fullstack Layer + selfdef MS011 operator dashboard
- 10-step Critical Build Order — synthesizes all 11 phases into operator-executable order
- Final guiding question — operator-quotable axiom for every implementation milestone
- Selfdef integration — MS010-MS034 align with M053 11-phase blueprint; cross-repo binding via MS007 doc-manifest typed-mirror crate
- Operator references: dump 15915–16493 (vision-to-implementation transition + 11-phase blueprint + Critical Build Order)
