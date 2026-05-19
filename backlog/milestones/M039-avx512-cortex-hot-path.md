# M039 — AVX-512 cortex hot path

> Parent: `backlog/milestones/INDEX.md` row M039 (dump 11169–11410).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 11169–11410.
> All entries below extract verbatim. No invention.

## Epics (E0368–E0377)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0368 | Operator directive — hardware physics must keep architecture tied (verbatim 11169: "do not forget the hardware and the tech. continue. do resaerchs online too") | 11169 |
| E0369 | "The CPU is not just 'general purpose'" — Ryzen 9 9900X / Zen 5 AVX-512 = wide deterministic control engine right next to GPUs; Phoronix Zen 5 AVX-512 benchmarks healthy + Chips and Cheese describes adaptive clocking (NOT crude fixed AVX-512 offsets); runtime doing BURSTS not one giant burn forever (scan branches / compress queues / merge bitsets / validate masks / rank candidates / dispatch GPU work) — "good AVX-512 workload shape" | 11187–11202 |
| E0370 | CPU Hot Path — Structure-of-Arrays (SoA) form for hot state — 9 arrays (branch_id[] / control_u64[] / budget_u16[] / risk_u8[] / score_q16[] / route_u8[] / model_id_u16[] / memory_ref_u64[] / kv_ref_u64[]); Zen 5 eats this as 8 x u64 lanes / 16 x u32 lanes / 32 x u16 lanes / 64 x u8 lanes / 512 boolean flags | 11204–11228 |
| E0371 | Scheduler bulk questions — Zen 5 AVX-512 answers in bulk (which branches alive / which need oracle / which can stay on scout / which need tests / which violated policy / which memories match / which actions reversible); "CPU is the goldilocks brainstem" | 11230–11242 |
| E0372 | AVX-512 tricks that actually matter — simdjson AVX-512 path (meaningful JSON parsing uplift; Phoronix) + VP2INTERSECT for extremely fast phrase-search style set intersection (Gabriel Menezes blog); pattern is "AVX-512 is not only HPC math; accelerates parsing, masks, search, bitsets, and set operations"; mapping to station: simdjson=fast parsing of traces+tool calls+API payloads / VP2INTERSECT=memory ID intersections+repo symbol search+phrase/context matching / VPOPCNTDQ=semantic sketch scoring / VPTERNLOG=policy fusion / VPCOMPRESS=pack sparse branches into dense GPU batches; "exactly the kind of glue agent systems drown in" | 11244–11267 |
| E0373 | GPU Roles Stay Separate — RTX PRO 6000 Blackwell protected from garbage work (oracle / final synthesis / large model / long context / verifier / high-value RLM parent); 3090 (SLM swarm / draft+speculation / embeddings+reranking / perception / sandboxed experiments / cheap branch expansion); CPU job = keep Blackwell fed with dense+valuable batches + keep 3090 busy exploring | 11269–11291 |
| E0374 | PCIe Discipline — Send compact symbols (tokens / scores / candidate refs / memory ids / tool intents / patch summaries / branch states); AVOID KV tensors + activations + layer-split traffic + constant sync; "Avoid tiny chatty cross-GPU exchanges" | 11293–11310 |
| E0375 | Blackwell FP4 frontier lever, qualify it — NVIDIA RTX PRO 6000 FP4 support real; TensorRT/Torch-TensorRT/vLLM/llm-compressor ecosystems moving toward NVFP4/MXFP4; local RTX Blackwell support moving fast and sometimes unevenly (especially MoE/SM120 kernels); "FP4 a model-lab track, not a blind default"; 4-tier quantization (Baseline BF16/FP16 quality / Production-fast FP8 if evals hold / Big-local NVFP4/MXFP4 when backend proven / Scout INT4/GPTQ/AWQ acceptable if task eval passes); "every quantized model must earn a slot through your evals" | 11312–11332 |
| E0376 | Hardware-Aware AIDLC (extends M038) — 6-phase per-hardware assignment (Map: CPU scans repo+metadata / 3090 summarizes-classifies / Blackwell resolves architecture uncertainty; Spec: Blackwell drafts-refines high-level contracts / CPU validates structure+links to tests; Test: CPU+sandbox executes deterministic checks / 3090 classifies failures / Blackwell diagnoses hard failures; Implement: 3090 drafts patches / CPU gates diffs+paths / Blackwell reviews high-risk changes; Evaluate: CPU computes metrics / 3090 tags trajectories / Blackwell writes lessons+spec updates; Commit: ZFS snapshot + policy gate + human/oracle review); "that is how hardware becomes methodology" | 11334–11369 |
| E0377 | Next Concrete Frontier — first prototype worth building is NOT a giant model server; it is the AVX-aware metadata core (5 tables: branch / memory-ref / model-registry / capability / eval-result; 6 operations: filter / score / intersect / compress / route / log); once exists, every higher-level idea becomes runnable (MAP / SPEC / TDD / RLM / SLM swarm / router / cost tracking / agent evals / Claude-compatible gateway); closing — "the metal tells us the shape: dense neural work on GPUs, deterministic sparse law on AVX-512, durable truth on ZFS, and adaptive routing over all of it" | 11371–11408 |

## Modules (M00646–M00662)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00646 | Zen 5 adaptive clocking — NOT crude fixed AVX-512 offsets (per Chips and Cheese) | 11191 | E0369 |
| M00647 | AVX-512 workload shape — bursts (NOT one giant burn forever) | 11192–11202 | E0369 |
| M00648 | Hot-path SoA array — branch_id[] | 11209 | E0370 |
| M00649 | Hot-path SoA array — control_u64[] | 11210 | E0370 |
| M00650 | Hot-path SoA array — budget_u16[] | 11211 | E0370 |
| M00651 | Hot-path SoA array — risk_u8[] | 11212 | E0370 |
| M00652 | Hot-path SoA array — score_q16[] | 11213 | E0370 |
| M00653 | Hot-path SoA array — route_u8[] | 11214 | E0370 |
| M00654 | Hot-path SoA array — model_id_u16[] | 11215 | E0370 |
| M00655 | Hot-path SoA array — memory_ref_u64[] | 11216 | E0370 |
| M00656 | Hot-path SoA array — kv_ref_u64[] | 11217 | E0370 |
| M00657 | Zen 5 lane counts — 8 x u64 / 16 x u32 / 32 x u16 / 64 x u8 / 512 boolean flags | 11222–11227 | E0370 |
| M00658 | "CPU is the goldilocks brainstem" | 11242 | E0371 |
| M00659 | AVX-512 ops mapped to station roles — simdjson (parsing) / VP2INTERSECT (intersections) / VPOPCNTDQ (sketch scoring) / VPTERNLOG (policy fusion) / VPCOMPRESS (sparse-to-dense pack) | 11251–11265 | E0372 |
| M00660 | Quantization tier (4-tier) — Baseline BF16/FP16 / Production-fast FP8 / Big-local NVFP4-MXFP4 / Scout INT4/GPTQ/AWQ | 11319–11329 | E0375 |
| M00661 | Hardware-aware AIDLC phase-to-hardware mapping — 6 phases (Map / Spec / Test / Implement / Evaluate / Commit) | 11338–11367 | E0376 |
| M00662 | AVX-aware metadata core — 5 tables + 6 operations | 11375–11392 | E0377 |

## Features (F03231–F03315)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F03231 | Operator directive — "do not forget the hardware and the tech" (continued) | 11169 | E0368 | composite | false |
| F03232 | "Keep architecture tied to actual hardware physics" | 11185 | E0368 | composite | false |
| F03233 | CPU is NOT just "general purpose" | 11187 | E0369 | composite | false |
| F03234 | Ryzen 9 9900X / Zen 5 AVX-512 = wide deterministic control engine | 11189 | E0369 | composite | false |
| F03235 | Right next to the GPUs | 11189 | E0369 | composite | false |
| F03236 | Phoronix Zen 5 AVX-512 benchmarks healthy (NOT old Intel-era folklore) | 11191 | E0369 | composite | true |
| F03237 | Chips and Cheese — Zen 5 adaptive clocking (NOT crude fixed AVX-512 offsets) | 11191 | M00646 | composite | true |
| F03238 | Runtime does BURSTS, not one giant burn forever | 11192 | E0369 | composite | false |
| F03239 | Burst — scan branches | 11194 | E0369 | composite | true |
| F03240 | Burst — compress queues | 11195 | E0369 | composite | true |
| F03241 | Burst — merge bitsets | 11196 | E0369 | composite | true |
| F03242 | Burst — validate masks | 11197 | E0369 | composite | true |
| F03243 | Burst — rank candidates | 11198 | E0369 | composite | true |
| F03244 | Burst — dispatch GPU work | 11199 | E0369 | composite | true |
| F03245 | "That is a good AVX-512 workload shape" | 11202 | E0369 | composite | false |
| F03246 | Runtime keeps hot state in SoA form | 11206 | E0370 | composite | false |
| F03247 | SoA array — branch_id[] | 11209 | M00648 | composite | true |
| F03248 | SoA array — control_u64[] | 11210 | M00649 | composite | true |
| F03249 | SoA array — budget_u16[] | 11211 | M00650 | composite | true |
| F03250 | SoA array — risk_u8[] | 11212 | M00651 | composite | true |
| F03251 | SoA array — score_q16[] | 11213 | M00652 | composite | true |
| F03252 | SoA array — route_u8[] | 11214 | M00653 | composite | true |
| F03253 | SoA array — model_id_u16[] | 11215 | M00654 | composite | true |
| F03254 | SoA array — memory_ref_u64[] | 11216 | M00655 | composite | true |
| F03255 | SoA array — kv_ref_u64[] | 11217 | M00656 | composite | true |
| F03256 | Zen 5 lane count — 8 x u64 lanes | 11223 | M00657 | composite | false |
| F03257 | Zen 5 lane count — 16 x u32 lanes | 11224 | M00657 | composite | false |
| F03258 | Zen 5 lane count — 32 x u16 lanes | 11225 | M00657 | composite | false |
| F03259 | Zen 5 lane count — 64 x u8 lanes | 11226 | M00657 | composite | false |
| F03260 | Zen 5 lane count — 512 boolean flags | 11227 | M00657 | composite | false |
| F03261 | Scheduler bulk question — which branches are alive? | 11233 | E0371 | composite | true |
| F03262 | Scheduler bulk question — which need oracle? | 11234 | E0371 | composite | true |
| F03263 | Scheduler bulk question — which can stay on scout? | 11235 | E0371 | composite | true |
| F03264 | Scheduler bulk question — which need tests? | 11236 | E0371 | composite | true |
| F03265 | Scheduler bulk question — which violated policy? | 11237 | E0371 | composite | true |
| F03266 | Scheduler bulk question — which memories match? | 11238 | E0371 | composite | true |
| F03267 | Scheduler bulk question — which actions are reversible? | 11239 | E0371 | composite | true |
| F03268 | "The CPU is the goldilocks brainstem" | 11242 | M00658 | composite | false |
| F03269 | simdjson AVX-512 path reports meaningful JSON parsing uplift (Phoronix) | 11246 | E0372 | composite | true |
| F03270 | VP2INTERSECT used for extremely fast phrase-search style set intersection (Gabriel Menezes blog) | 11246 | E0372 | composite | true |
| F03271 | Pattern — AVX-512 is not only HPC math; accelerates parsing, masks, search, bitsets, set operations | 11246 | E0372 | composite | false |
| F03272 | Station use — simdjson for fast parsing of traces, tool calls, API payloads | 11252 | M00659 | composite | true |
| F03273 | Station use — VP2INTERSECT for memory ID intersections, repo symbol search, phrase/context matching | 11255 | M00659 | composite | true |
| F03274 | Station use — VPOPCNTDQ for semantic sketch scoring | 11258 | M00659 | composite | true |
| F03275 | Station use — VPTERNLOG for policy fusion | 11261 | M00659 | composite | true |
| F03276 | Station use — VPCOMPRESS to pack sparse branches into dense GPU batches | 11264 | M00659 | composite | true |
| F03277 | "Exactly the kind of glue agent systems drown in" | 11267 | E0372 | composite | false |
| F03278 | RTX PRO 6000 Blackwell — oracle role | 11274 | E0373 | composite | true |
| F03279 | RTX PRO 6000 Blackwell — final synthesis role | 11275 | E0373 | composite | true |
| F03280 | RTX PRO 6000 Blackwell — large model role | 11276 | E0373 | composite | true |
| F03281 | RTX PRO 6000 Blackwell — long context role | 11277 | E0373 | composite | true |
| F03282 | RTX PRO 6000 Blackwell — verifier role | 11278 | E0373 | composite | true |
| F03283 | RTX PRO 6000 Blackwell — high-value RLM parent role | 11279 | E0373 | composite | true |
| F03284 | RTX 3090 — SLM swarm role | 11282 | E0373 | composite | true |
| F03285 | RTX 3090 — draft/speculation role | 11283 | E0373 | composite | true |
| F03286 | RTX 3090 — embeddings/reranking role | 11284 | E0373 | composite | true |
| F03287 | RTX 3090 — perception role | 11285 | E0373 | composite | true |
| F03288 | RTX 3090 — sandboxed experiments role | 11286 | E0373 | composite | true |
| F03289 | RTX 3090 — cheap branch expansion role | 11287 | E0373 | composite | true |
| F03290 | CPU job — keep Blackwell fed with dense + valuable batches | 11291 | E0373 | composite | false |
| F03291 | CPU job — keep 3090 busy exploring | 11291 | E0373 | composite | false |
| F03292 | Avoid tiny chatty cross-GPU exchanges | 11291 | E0374 | composite | false |
| F03293 | PCIe — send compact symbols (tokens) | 11294 | E0374 | composite | true |
| F03294 | PCIe — send compact symbols (scores) | 11295 | E0374 | composite | true |
| F03295 | PCIe — send compact symbols (candidate refs) | 11296 | E0374 | composite | true |
| F03296 | PCIe — send compact symbols (memory ids) | 11297 | E0374 | composite | true |
| F03297 | PCIe — send compact symbols (tool intents) | 11298 | E0374 | composite | true |
| F03298 | PCIe — send compact symbols (patch summaries) | 11299 | E0374 | composite | true |
| F03299 | PCIe — send compact symbols (branch states) | 11300 | E0374 | composite | true |
| F03300 | PCIe — AVOID KV tensors | 11305 | E0374 | composite | false |
| F03301 | PCIe — AVOID activations | 11306 | E0374 | composite | false |
| F03302 | PCIe — AVOID layer-split traffic | 11307 | E0374 | composite | false |
| F03303 | PCIe — AVOID constant sync | 11308 | E0374 | composite | false |
| F03304 | "RTX PRO 6000 FP4 support is real" (NVIDIA cited) | 11313 | E0375 | composite | false |
| F03305 | TensorRT/Torch-TensorRT/vLLM/llm-compressor ecosystems moving toward NVFP4/MXFP4 support | 11314 | E0375 | composite | true |
| F03306 | Local RTX Blackwell support moving fast and sometimes unevenly (especially MoE/SM120 kernels) | 11314 | E0375 | composite | false |
| F03307 | "Make FP4 a model-lab track, not a blind default" | 11316 | E0375 | composite | false |
| F03308 | Quantization tier — Baseline BF16/FP16 quality | 11319–11320 | M00660 | composite | true |
| F03309 | Quantization tier — Production fast FP8 if evals hold | 11322–11323 | M00660 | composite | true |
| F03310 | Quantization tier — Big local NVFP4/MXFP4 when backend is proven | 11325–11326 | M00660 | composite | true |
| F03311 | Quantization tier — Scout INT4/GPTQ/AWQ acceptable if task eval passes | 11328–11329 | M00660 | composite | true |
| F03312 | "Every quantized model must earn a slot through your evals" | 11332 | E0375 | composite | false |
| F03313 | Hardware-Aware AIDLC — 6 phases each with hardware executor mapping | 11336 + 11338–11367 | M00661 | composite | false |
| F03314 | "That is how hardware becomes methodology" | 11369 | E0376 | composite | false |
| F03315 | Composite — Next Concrete Frontier = AVX-aware metadata core (5 tables: branch / memory-ref / model-registry / capability / eval-result; 6 ops: filter / score / intersect / compress / route / log); once exists, every higher-level idea becomes runnable (MAP / SPEC / TDD / RLM / SLM swarm / router / cost tracking / agent evals / Claude-compatible gateway); closing "the metal tells us the shape: dense neural work on GPUs, deterministic sparse law on AVX-512, durable truth on ZFS, and adaptive routing over all of it" | 11371–11408 | E0377 | composite | false |

## Requirements (R06461–R06630)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R06461 | "Keep architecture tied to actual hardware physics" | 11185 | F03232 | non-negotiable | false | 10 |
| R06462 | CPU is NOT just "general purpose" | 11187 | F03233 | non-negotiable | false | 10 |
| R06463 | Ryzen 9 9900X / Zen 5 AVX-512 is a wide deterministic control engine | 11189 | F03234 | non-negotiable | false | 10 |
| R06464 | CPU sits right next to GPUs | 11189 | F03235 | non-negotiable | false | 10 |
| R06465 | Zen 5 AVX-512 healthier than old Intel-era folklore (Phoronix) | 11191 | F03236 | non-negotiable | true | 10 |
| R06466 | Zen 5 adaptive clocking (NOT crude fixed AVX-512 offsets) per Chips and Cheese | 11191 | M00646 | non-negotiable | false | 10 |
| R06467 | Runtime does BURSTS, not one giant burn forever | 11192 | F03238 | non-negotiable | false | 10 |
| R06468 | Burst — scan branches | 11194 | F03239 | non-negotiable | true | 10 |
| R06469 | Burst — compress queues | 11195 | F03240 | non-negotiable | true | 10 |
| R06470 | Burst — merge bitsets | 11196 | F03241 | non-negotiable | true | 10 |
| R06471 | Burst — validate masks | 11197 | F03242 | non-negotiable | true | 10 |
| R06472 | Burst — rank candidates | 11198 | F03243 | non-negotiable | true | 10 |
| R06473 | Burst — dispatch GPU work | 11199 | F03244 | non-negotiable | true | 10 |
| R06474 | "Good AVX-512 workload shape" | 11202 | F03245 | non-negotiable | false | 10 |
| R06475 | Runtime keeps hot state in SoA form (Structure-of-Arrays) | 11206 | F03246 | non-negotiable | false | 10 |
| R06476 | SoA array — branch_id[] | 11209 | F03247 | non-negotiable | true | 10 |
| R06477 | SoA array — control_u64[] | 11210 | F03248 | non-negotiable | true | 10 |
| R06478 | SoA array — budget_u16[] | 11211 | F03249 | non-negotiable | true | 10 |
| R06479 | SoA array — risk_u8[] | 11212 | F03250 | non-negotiable | true | 10 |
| R06480 | SoA array — score_q16[] | 11213 | F03251 | non-negotiable | true | 10 |
| R06481 | SoA array — route_u8[] | 11214 | F03252 | non-negotiable | true | 10 |
| R06482 | SoA array — model_id_u16[] | 11215 | F03253 | non-negotiable | true | 10 |
| R06483 | SoA array — memory_ref_u64[] | 11216 | F03254 | non-negotiable | true | 10 |
| R06484 | SoA array — kv_ref_u64[] | 11217 | F03255 | non-negotiable | true | 10 |
| R06485 | Zen 5 — 8 x u64 lanes | 11223 | F03256 | non-negotiable | false | 10 |
| R06486 | Zen 5 — 16 x u32 lanes | 11224 | F03257 | non-negotiable | false | 10 |
| R06487 | Zen 5 — 32 x u16 lanes | 11225 | F03258 | non-negotiable | false | 10 |
| R06488 | Zen 5 — 64 x u8 lanes | 11226 | F03259 | non-negotiable | false | 10 |
| R06489 | Zen 5 — 512 boolean flags | 11227 | F03260 | non-negotiable | false | 10 |
| R06490 | Scheduler asks in bulk — which branches are alive | 11233 | F03261 | non-negotiable | true | 10 |
| R06491 | Scheduler asks in bulk — which need oracle | 11234 | F03262 | non-negotiable | true | 10 |
| R06492 | Scheduler asks in bulk — which can stay on scout | 11235 | F03263 | non-negotiable | true | 10 |
| R06493 | Scheduler asks in bulk — which need tests | 11236 | F03264 | non-negotiable | true | 10 |
| R06494 | Scheduler asks in bulk — which violated policy | 11237 | F03265 | non-negotiable | true | 10 |
| R06495 | Scheduler asks in bulk — which memories match | 11238 | F03266 | non-negotiable | true | 10 |
| R06496 | Scheduler asks in bulk — which actions are reversible | 11239 | F03267 | non-negotiable | true | 10 |
| R06497 | "CPU is the goldilocks brainstem" | 11242 | F03268 | non-negotiable | false | 10 |
| R06498 | simdjson AVX-512 path reports meaningful JSON parsing uplift | 11246 | F03269 | non-negotiable | true | 10 |
| R06499 | VP2INTERSECT enables extremely fast phrase-search style set intersection | 11246 | F03270 | non-negotiable | true | 10 |
| R06500 | AVX-512 is not only HPC math; accelerates parsing / masks / search / bitsets / set operations | 11246 | F03271 | non-negotiable | false | 10 |
| R06501 | Station use — simdjson for fast parsing of traces, tool calls, API payloads | 11252 | F03272 | non-negotiable | true | 10 |
| R06502 | Station use — VP2INTERSECT for memory ID intersections | 11255 | F03273 | non-negotiable | true | 10 |
| R06503 | Station use — VP2INTERSECT for repo symbol search | 11255 | F03273 | non-negotiable | true | 10 |
| R06504 | Station use — VP2INTERSECT for phrase/context matching | 11255 | F03273 | non-negotiable | true | 10 |
| R06505 | Station use — VPOPCNTDQ for semantic sketch scoring | 11258 | F03274 | non-negotiable | true | 10 |
| R06506 | Station use — VPTERNLOG for policy fusion | 11261 | F03275 | non-negotiable | true | 10 |
| R06507 | Station use — VPCOMPRESS to pack sparse branches into dense GPU batches | 11264 | F03276 | non-negotiable | true | 10 |
| R06508 | "Exactly the kind of glue agent systems drown in" | 11267 | F03277 | non-negotiable | false | 10 |
| R06509 | RTX PRO 6000 Blackwell — oracle role | 11274 | F03278 | non-negotiable | true | 10 |
| R06510 | RTX PRO 6000 Blackwell — final synthesis role | 11275 | F03279 | non-negotiable | true | 10 |
| R06511 | RTX PRO 6000 Blackwell — large model role | 11276 | F03280 | non-negotiable | true | 10 |
| R06512 | RTX PRO 6000 Blackwell — long context role | 11277 | F03281 | non-negotiable | true | 10 |
| R06513 | RTX PRO 6000 Blackwell — verifier role | 11278 | F03282 | non-negotiable | true | 10 |
| R06514 | RTX PRO 6000 Blackwell — high-value RLM parent role | 11279 | F03283 | non-negotiable | true | 10 |
| R06515 | RTX 3090 — SLM swarm role | 11282 | F03284 | non-negotiable | true | 10 |
| R06516 | RTX 3090 — draft/speculation role | 11283 | F03285 | non-negotiable | true | 10 |
| R06517 | RTX 3090 — embeddings/reranking role | 11284 | F03286 | non-negotiable | true | 10 |
| R06518 | RTX 3090 — perception role | 11285 | F03287 | non-negotiable | true | 10 |
| R06519 | RTX 3090 — sandboxed experiments role | 11286 | F03288 | non-negotiable | true | 10 |
| R06520 | RTX 3090 — cheap branch expansion role | 11287 | F03289 | non-negotiable | true | 10 |
| R06521 | CPU job — keep Blackwell fed with dense + valuable batches | 11291 | F03290 | non-negotiable | false | 10 |
| R06522 | CPU job — keep 3090 busy exploring | 11291 | F03291 | non-negotiable | false | 10 |
| R06523 | Avoid tiny chatty cross-GPU exchanges | 11291 | F03292 | non-negotiable | false | 10 |
| R06524 | PCIe — send compact symbol (tokens) | 11294 | F03293 | non-negotiable | true | 10 |
| R06525 | PCIe — send compact symbol (scores) | 11295 | F03294 | non-negotiable | true | 10 |
| R06526 | PCIe — send compact symbol (candidate refs) | 11296 | F03295 | non-negotiable | true | 10 |
| R06527 | PCIe — send compact symbol (memory ids) | 11297 | F03296 | non-negotiable | true | 10 |
| R06528 | PCIe — send compact symbol (tool intents) | 11298 | F03297 | non-negotiable | true | 10 |
| R06529 | PCIe — send compact symbol (patch summaries) | 11299 | F03298 | non-negotiable | true | 10 |
| R06530 | PCIe — send compact symbol (branch states) | 11300 | F03299 | non-negotiable | true | 10 |
| R06531 | PCIe — AVOID KV tensors | 11305 | F03300 | non-negotiable | false | 10 |
| R06532 | PCIe — AVOID activations | 11306 | F03301 | non-negotiable | false | 10 |
| R06533 | PCIe — AVOID layer-split traffic | 11307 | F03302 | non-negotiable | false | 10 |
| R06534 | PCIe — AVOID constant sync | 11308 | F03303 | non-negotiable | false | 10 |
| R06535 | RTX PRO 6000 FP4 support is real | 11313 | F03304 | non-negotiable | false | 10 |
| R06536 | TensorRT moving toward NVFP4/MXFP4 support | 11314 | F03305 | non-negotiable | true | 10 |
| R06537 | Torch-TensorRT moving toward NVFP4/MXFP4 support | 11314 | F03305 | non-negotiable | true | 10 |
| R06538 | vLLM moving toward NVFP4/MXFP4 support | 11314 | F03305 | non-negotiable | true | 10 |
| R06539 | llm-compressor moving toward NVFP4/MXFP4 support | 11314 | F03305 | non-negotiable | true | 10 |
| R06540 | Local RTX Blackwell support moving fast + sometimes unevenly (especially MoE/SM120 kernels) | 11314 | F03306 | non-negotiable | false | 10 |
| R06541 | "Make FP4 a model-lab track, not a blind default" | 11316 | F03307 | non-negotiable | false | 10 |
| R06542 | Quantization tier — Baseline BF16/FP16 quality | 11319 | F03308 | non-negotiable | true | 10 |
| R06543 | Quantization tier — Production fast FP8 if evals hold | 11322–11323 | F03309 | non-negotiable | true | 10 |
| R06544 | Quantization tier — Big local NVFP4/MXFP4 when backend is proven | 11325–11326 | F03310 | non-negotiable | true | 10 |
| R06545 | Quantization tier — Scout INT4/GPTQ/AWQ acceptable if task eval passes | 11328–11329 | F03311 | non-negotiable | true | 10 |
| R06546 | "Every quantized model must earn a slot through your evals" | 11332 | F03312 | non-negotiable | false | 10 |
| R06547 | Hardware-aware AIDLC — Map phase: CPU scans repo and metadata | 11339–11340 | M00661 | non-negotiable | true | 10 |
| R06548 | Hardware-aware AIDLC — Map phase: 3090 summarizes/classifies | 11341 | M00661 | non-negotiable | true | 10 |
| R06549 | Hardware-aware AIDLC — Map phase: Blackwell resolves architecture uncertainty | 11342 | M00661 | non-negotiable | true | 10 |
| R06550 | Hardware-aware AIDLC — Spec phase: Blackwell drafts/refines high-level contracts | 11345 | M00661 | non-negotiable | true | 10 |
| R06551 | Hardware-aware AIDLC — Spec phase: CPU validates structure and links to tests | 11346 | M00661 | non-negotiable | true | 10 |
| R06552 | Hardware-aware AIDLC — Test phase: CPU/sandbox executes deterministic checks | 11349 | M00661 | non-negotiable | true | 10 |
| R06553 | Hardware-aware AIDLC — Test phase: 3090 classifies failures | 11350 | M00661 | non-negotiable | true | 10 |
| R06554 | Hardware-aware AIDLC — Test phase: Blackwell diagnoses hard failures | 11351 | M00661 | non-negotiable | true | 10 |
| R06555 | Hardware-aware AIDLC — Implement phase: 3090 drafts patches | 11354 | M00661 | non-negotiable | true | 10 |
| R06556 | Hardware-aware AIDLC — Implement phase: CPU gates diffs and paths | 11355 | M00661 | non-negotiable | true | 10 |
| R06557 | Hardware-aware AIDLC — Implement phase: Blackwell reviews high-risk changes | 11356 | M00661 | non-negotiable | true | 10 |
| R06558 | Hardware-aware AIDLC — Evaluate phase: CPU computes metrics | 11359 | M00661 | non-negotiable | true | 10 |
| R06559 | Hardware-aware AIDLC — Evaluate phase: 3090 tags trajectories | 11360 | M00661 | non-negotiable | true | 10 |
| R06560 | Hardware-aware AIDLC — Evaluate phase: Blackwell writes lessons/spec updates | 11361 | M00661 | non-negotiable | true | 10 |
| R06561 | Hardware-aware AIDLC — Commit phase: ZFS snapshot | 11364 | M00661 | non-negotiable | true | 10 |
| R06562 | Hardware-aware AIDLC — Commit phase: policy gate | 11365 | M00661 | non-negotiable | true | 10 |
| R06563 | Hardware-aware AIDLC — Commit phase: human/oracle review | 11366 | M00661 | non-negotiable | true | 10 |
| R06564 | "That is how hardware becomes methodology" | 11369 | F03314 | non-negotiable | false | 10 |
| R06565 | First prototype worth building is NOT a giant model server | 11373 | E0377 | non-negotiable | false | 10 |
| R06566 | First prototype = AVX-aware metadata core | 11373 | M00662 | non-negotiable | false | 10 |
| R06567 | AVX-aware metadata core table — branch table | 11376 | M00662 | non-negotiable | true | 10 |
| R06568 | AVX-aware metadata core table — memory ref table | 11377 | M00662 | non-negotiable | true | 10 |
| R06569 | AVX-aware metadata core table — model registry table | 11378 | M00662 | non-negotiable | true | 10 |
| R06570 | AVX-aware metadata core table — capability table | 11379 | M00662 | non-negotiable | true | 10 |
| R06571 | AVX-aware metadata core table — eval result table | 11380 | M00662 | non-negotiable | true | 10 |
| R06572 | AVX-aware metadata core operation — filter | 11385 | M00662 | non-negotiable | true | 10 |
| R06573 | AVX-aware metadata core operation — score | 11386 | M00662 | non-negotiable | true | 10 |
| R06574 | AVX-aware metadata core operation — intersect | 11387 | M00662 | non-negotiable | true | 10 |
| R06575 | AVX-aware metadata core operation — compress | 11388 | M00662 | non-negotiable | true | 10 |
| R06576 | AVX-aware metadata core operation — route | 11389 | M00662 | non-negotiable | true | 10 |
| R06577 | AVX-aware metadata core operation — log | 11390 | M00662 | non-negotiable | true | 10 |
| R06578 | Once metadata core exists, MAP becomes runnable | 11397 | E0377 | non-negotiable | false | 10 |
| R06579 | Once metadata core exists, SPEC becomes runnable | 11398 | E0377 | non-negotiable | false | 10 |
| R06580 | Once metadata core exists, TDD becomes runnable | 11399 | E0377 | non-negotiable | false | 10 |
| R06581 | Once metadata core exists, RLM becomes runnable | 11400 | E0377 | non-negotiable | false | 10 |
| R06582 | Once metadata core exists, SLM swarm becomes runnable | 11401 | E0377 | non-negotiable | false | 10 |
| R06583 | Once metadata core exists, router becomes runnable | 11402 | E0377 | non-negotiable | false | 10 |
| R06584 | Once metadata core exists, cost tracking becomes runnable | 11403 | E0377 | non-negotiable | false | 10 |
| R06585 | Once metadata core exists, agent evals becomes runnable | 11404 | E0377 | non-negotiable | false | 10 |
| R06586 | Once metadata core exists, Claude-compatible gateway becomes runnable | 11405 | E0377 | non-negotiable | false | 10 |
| R06587 | Closing — "the metal tells us the shape: dense neural work on GPUs" | 11408 | E0377 | non-negotiable | false | 10 |
| R06588 | Closing — "deterministic sparse law on AVX-512" | 11408 | E0377 | non-negotiable | false | 10 |
| R06589 | Closing — "durable truth on ZFS" | 11408 | E0377 | non-negotiable | false | 10 |
| R06590 | Closing — "adaptive routing over all of it" | 11408 | E0377 | non-negotiable | false | 10 |
| R06591 | M039 integrates with M027 Value Plane — VPCOMPRESS packs sparse branches per reward-vector scoring | 11264 + cross-ref M027 | F03276 | non-negotiable | false | 10 |
| R06592 | M039 integrates with M028 Memory OS — VP2INTERSECT computes memory ID intersections + memory_ref_u64[] field | 11216 + 11255 + cross-ref M028 | M00655 + F03273 | non-negotiable | false | 10 |
| R06593 | M039 integrates with M029 Computer-Use Plane — risk_u8[] + budget_u16[] are Action Policy Bits projections | 11212 + 11211 + cross-ref M029 | M00650 + M00651 | non-negotiable | false | 10 |
| R06594 | M039 integrates with M030 World Model Plane — score_q16[] is reward+predicted-transition scoring | 11213 + cross-ref M030 | M00652 | non-negotiable | false | 10 |
| R06595 | M039 integrates with M031 Symbolic Planning Plane — VPTERNLOG fuses policy logic + control_u64[] is policy bitset | 11210 + 11261 + cross-ref M031 | F03275 + M00649 | non-negotiable | false | 10 |
| R06596 | M039 integrates with M032 Cloud Expert Plane + M033 Compatibility Gateway — route_u8[] encodes per-request routing decision | 11214 + cross-ref M032 + M033 | M00653 | non-negotiable | false | 10 |
| R06597 | M039 integrates with M034 Anthropic-first Gateway — model_id_u16[] maps Claude-jean-* aliases per route | 11215 + cross-ref M034 | M00654 | non-negotiable | false | 10 |
| R06598 | M039 integrates with M035 Frontier — AVX-512 Cortex is Layer 3 of Frontier 9-layer Runtime Shape | 11242 + cross-ref M035 R05844 | M00658 | non-negotiable | false | 10 |
| R06599 | M039 integrates with M036 MAP-then-act — VP2INTERSECT enables MAP-phase repo+symbol+memory search | 11255 + cross-ref M036 | F03273 | non-negotiable | false | 10 |
| R06600 | M039 integrates with M037 evidence-driven autonomy — score_q16[] is multi-axis evidence score | 11213 + cross-ref M037 | M00652 | non-negotiable | false | 10 |
| R06601 | M039 integrates with M038 Hardware-aware AIDLC — phase-to-hardware mapping (6 phases × 3 executors) extends M038's 5-phase methodology | 11338–11367 + cross-ref M038 | M00661 | non-negotiable | false | 10 |
| R06602 | Project boundary — M039 is sovereign-os runtime concern; selfdef MS010 [requires_hardware] gates align with AVX-512 subset detection | architecture + MS010 | E0369 | non-negotiable | false | 10 |
| R06603 | Project boundary — selfdef SDD-022 hardware exploit doctrine codifies same AVX-512 instruction catalog | cross-ref selfdef SDD-022 | E0372 | non-negotiable | false | 10 |
| R06604 | Project boundary — selfdef MS007 typed-mirror crates may carry SoA-array schema for cross-repo audit | MS007 + SDD-038 | E0370 | non-negotiable | false | 10 |
| R06605 | Quantization tier mapping — Baseline used for Blackwell oracle role | 11319 + 11274–11279 | F03308 + F03278 | non-negotiable | false | 10 |
| R06606 | Quantization tier mapping — Production-fast FP8 used for Blackwell large-model role | 11322 + 11276 | F03309 + F03280 | non-negotiable | false | 10 |
| R06607 | Quantization tier mapping — Big-local NVFP4/MXFP4 used for Blackwell when backend proven | 11325–11326 + 11274 | F03310 + F03278 | non-negotiable | false | 10 |
| R06608 | Quantization tier mapping — Scout INT4/GPTQ/AWQ used for 3090 SLM-swarm / draft / embedding roles | 11328–11329 + 11282–11284 | F03311 + F03284 + F03285 + F03286 | non-negotiable | false | 10 |
| R06609 | Quantization tier gating — "every quantized model must earn a slot through your evals" (operator-set bar) | 11332 | F03312 | non-negotiable | false | 10 |
| R06610 | AVX-512 doctrine — bursts not sustained burn (Zen 5 adaptive clocking strategy) | 11192 + 11191 | F03238 + M00646 | non-negotiable | false | 10 |
| R06611 | AVX-512 doctrine — SoA hot path (NOT AoS) for vectorization | 11206 | F03246 | non-negotiable | false | 10 |
| R06612 | AVX-512 doctrine — "CPU runs law" (paired with M038 R06339 "GPU runs probability") | 11242 + cross-ref M038 R06339 | F03268 | non-negotiable | false | 10 |
| R06613 | AVX-512 instruction discovery via runtime CPUID (per selfdef MS010 R02236 selfdef-hardware crate) | cross-ref selfdef MS010 | E0372 | non-negotiable | false | 10 |
| R06614 | AVX-512 instruction fallback when subset absent — scalar code path (no fail) | architecture + cross-ref MS010 | E0372 | non-negotiable | false | 10 |
| R06615 | Compiler convention — workstation build uses `-march=znver5` + `-mprefer-vector-width=512` | 11189 + cross-ref selfdef MS010 R02240-R02243 | E0369 | non-negotiable | false | 10 |
| R06616 | GPU separation invariant — Blackwell + 3090 are SEPARATE EXPERTS, not unified pool | 11271 + cross-ref M038 R06311 | E0373 | non-negotiable | false | 10 |
| R06617 | CPU job invariant — keep Blackwell fed dense+valuable batches; keep 3090 busy exploring | 11291 | F03290 + F03291 | non-negotiable | false | 10 |
| R06618 | PCIe traffic invariant — compact symbols ONLY (NOT tensors / activations / layer-split / sync) | 11291 + 11294–11308 | E0374 | non-negotiable | false | 10 |
| R06619 | "Avoid tiny chatty cross-GPU exchanges" | 11291 | F03292 | non-negotiable | false | 10 |
| R06620 | Layer-B metric (implied) — `sovereign_os_cortex_burst_total{op}` (scan/compress/merge/validate/rank/dispatch) | architecture + 11194–11199 | E0369 | non-negotiable | true | 10 |
| R06621 | Layer-B metric (implied) — `sovereign_os_cortex_soa_array_capacity{array}` per of 9 SoA arrays | architecture + 11209–11217 | M00648-M00656 | non-negotiable | true | 10 |
| R06622 | Layer-B metric (implied) — `sovereign_os_cortex_avx512_op_total{instruction}` (simdjson/VP2INTERSECT/VPOPCNTDQ/VPTERNLOG/VPCOMPRESS) | architecture + 11251–11265 | M00659 | non-negotiable | true | 10 |
| R06623 | Layer-B metric (implied) — `sovereign_os_cortex_gpu_role_current{gpu, role}` (Blackwell/3090) | architecture + 11271–11289 | E0373 | non-negotiable | true | 10 |
| R06624 | Layer-B metric (implied) — `sovereign_os_cortex_quantization_tier_in_use{model_id, tier}` | architecture + 11319–11329 | M00660 | non-negotiable | true | 10 |
| R06625 | M039 doctrine — first build is NOT giant model server; build AVX-aware metadata core first | 11373 | E0377 | non-negotiable | false | 10 |
| R06626 | M039 doctrine — once metadata core exists, all higher-level ideas become runnable | 11394 | E0377 | non-negotiable | false | 10 |
| R06627 | M039 closing law — "metal tells us the shape: dense neural work on GPUs, deterministic sparse law on AVX-512, durable truth on ZFS, and adaptive routing over all of it" | 11408 | E0377 | non-negotiable | false | 10 |
| R06628 | AVX-aware metadata core is the SECOND-NAMED foundational implementation target (per closing) | 11371 + 11373 + 11394 | E0377 | non-negotiable | false | 10 |
| R06629 | AVX-aware metadata core is the bridge between M038 hardware-aware AIDLC + M037 evidence-driven autonomy + M025 cognitive compiler | 11375–11405 + cross-refs | E0377 | non-negotiable | false | 10 |
| R06630 | Composite — M039 AVX-512 cortex hot path operationalizes M038's "CPU = deterministic router" via SoA hot state (9 arrays) + Zen 5 lane counts (8/16/32/64/512) + 7 scheduler bulk questions + 5 AVX-512 instructions mapped to station roles (simdjson/VP2INTERSECT/VPOPCNTDQ/VPTERNLOG/VPCOMPRESS); GPU roles separated (Blackwell oracle / 3090 scout); PCIe compact symbols only (NOT tensors); 4-tier quantization with eval-earned slot ("every quantized model must earn a slot"); 6-phase hardware-aware AIDLC; AVX-aware metadata core (5 tables + 6 ops) is first concrete prototype; closing "the metal tells us the shape" | 11169–11408 | E0368 + E0369 + E0370 + E0371 + E0372 + E0373 + E0374 + E0375 + E0376 + E0377 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M038 Hardware-aware AIDLC (10964–11169) / M040 Hyper features MIG/FP4/VFIO/ZFS commit gate (11410–11790)
- Plane integration: M025-M038 all integrate with M039 (AVX-512 Cortex is the deterministic hot-path executor; SoA arrays carry M027 reward + M028 memory_ref + M029 risk + M030 score + M031 control + M033/M034 route + M034 model_id)
- AVX-aware metadata core (5 tables: branch / memory-ref / model-registry / capability / eval-result + 6 ops: filter / score / intersect / compress / route / log) is the first concrete implementation target for M025-M038 doctrine
- Selfdef boundary: SoA-array schema may be carried as MS007 typed-mirror crate / SDD-022 hardware exploit doctrine codifies same AVX-512 catalog / MS010 [requires_hardware] gates align with AVX-512 subset CPUID detection
- Operator references: Phoronix Zen 5 AVX-512 benchmarks + Chips and Cheese adaptive clocking + simdjson AVX-512 path + Gabriel Menezes VP2INTERSECT phrase-search blog + NVIDIA RTX PRO 6000 + TensorRT/Torch-TensorRT/vLLM/llm-compressor FP4 ecosystems
