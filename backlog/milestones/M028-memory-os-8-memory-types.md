# M028 — Memory OS — 8 memory types

> Parent: `backlog/milestones/INDEX.md` row M028 (dump 8121–8475).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 8121–8475.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0258–E0267)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0258 | Memory as intelligence — not storage; living structure; SLM/RLM/PRM/workflow all stronger when memory is not just "retrieve similar chunks" | 8136–8138 |
| E0259 | Research substrate — MemGPT/Letta virtual memory paging / Zep Graphiti temporal knowledge graphs / A-MEM Zettelkasten-like agentic memory / D-Mem dual-process quality gating / MemMachine ground-truth-preserving episodes / Value-Driven Memory-Augmented Generation | 8140–8147 |
| E0260 | The Memory Plane — do not build one memory; build multiple memory types (Working / Episodic / Semantic / Procedural / Temporal Graph / Value / KV Memory; each type has different rules) | 8151–8180 |
| E0261 | Key principle — "Do not summarize away truth"; summaries are useful but lossy; keep ground truth (raw episode / derived facts / summary / graph edges / embeddings / bitset metadata / trust score / freshness) | 8182–8201 |
| E0262 | Memory Records — typed MemoryItem struct (id / type / source_ref / time_range / trust / freshness / topic_sketch / entity_sketch / value_score / flags); cold blobs / hot metadata; AVX-512 scans hot metadata first | 8203–8236 |
| E0263 | Temporal Memory — what-was-true-then / what-is-true-now / what-changed / who-contradicted / when-last-verified; many facts change (preferred model / repo test command / current branch / API version / user preference / project architecture / dependency behavior) | 8238–8264 |
| E0264 | Memory Admission + Lifecycle — value-driven admission (store-if / ignore-if rules) + 11-stage lifecycle (observe → classify → quarantine → link → score → store raw → extract facts → verify → promote → decay/archive); plugs into Value Plane | 8266–8308 |
| E0265 | RLM + SLM + Reward memory roles — RLM memory navigator (queries/scripts/child calls); SLM cheap maintenance (extract / tag / dedup / topic / edges / classify-failure / summarize); Reward memory = local experience base; memory = compressed experience (skill = crystallized memory / profile = crystallized preference / routing policy = crystallized performance) | 8310–8385 |
| E0266 | On-workstation hardware mapping + Memory Query Pipeline — RAM hot / NVMe-ZFS cold / Blackwell deep synthesis / 3090 extraction-reranking-SLM-tagging-edges / AVX-512 metadata-bitset-freshness-trust-candidate-packing; 8-step query (intent → AVX bitset → sketch popcount → embed/rerank → graph expand → temporal validate → RLM recursive → oracle synthesis); smarter than top-k vectors | 8387–8422 |
| E0267 | Profiles Affect Memory + new architecture component "Memory Operating System" + key line "Intelligence improves when memory stops being recall and becomes adaptive state" | 8423–8474 |

## Modules (M00459–M00475)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00459 | Memory type 1 — Working Memory (current task / active branches / local facts / tool outputs) | 8158–8159 | E0260 |
| M00460 | Memory type 2 — Episodic Memory (full traces / conversations / task attempts / failures / user corrections) | 8161–8162 | E0260 |
| M00461 | Memory type 3 — Semantic Memory (distilled facts / concepts / summaries / project knowledge) | 8164–8165 | E0260 |
| M00462 | Memory type 4 — Procedural Memory (skills / workflows / command recipes / successful tool sequences) | 8167–8168 | E0260 |
| M00463 | Memory type 5 — Temporal Graph Memory (entities / relationships / timestamps / changing facts) | 8170–8171 | E0260 + E0263 |
| M00464 | Memory type 6 — Value Memory (what worked / what failed / which model/tool/profile succeeded) | 8173–8174 | E0260 + E0265 |
| M00465 | Memory type 7 — KV Memory (cached model prefixes / reusable prompt blocks / context blocks) | 8176–8177 | E0260 |
| M00466 | Ground-truth preservation layer — raw episode / derived facts / summary / graph edges / embeddings / bitset metadata / trust score / freshness | 8190–8200 | E0261 |
| M00467 | MemoryItem struct — 10 uint64_t fields (id / type / source_ref / time_range / trust / freshness / topic_sketch / entity_sketch / value_score / flags) | 8208–8220 | E0262 |
| M00468 | Hot/cold split — text/blob lives cold; metadata stays hot; AVX-512 scans hot first (project / topic / freshness / trust / permission / user-scope / failure relevance) | 8222–8236 | E0262 |
| M00469 | Temporal-memory query verbs — 5 questions (true-then / true-now / changed / contradicted-by / last-verified) | 8254–8262 | E0263 |
| M00470 | Admission rules — store-if 8 triggers / ignore-if 5 triggers (transient / low-trust / duplicate / noisy / unverified) | 8272–8289 | E0264 |
| M00471 | Memory lifecycle — 11-stage pipeline (observe / classify / quarantine / link / score / store raw / extract facts / verify / promote / decay / archive) | 8295–8308 | E0264 |
| M00472 | RLM memory navigator — gets memory environment; writes queries/scripts; spawns child calls over slices; returns composed answer | 8312–8331 | E0265 |
| M00473 | SLM memory janitor — 7 cheap maintenance jobs (extract / tag / dedup / topic-label / graph-edge propose / classify-failure / summarize) | 8336–8345 | E0265 |
| M00474 | Memory hardware mapping — RAM hot / NVMe-ZFS cold / Blackwell deep synthesis / 3090 extraction-rerank-tag-edges / AVX-512 metadata-bitset-filter | 8389–8406 | E0266 |
| M00475 | 8-step Memory Query Pipeline — intent / AVX bitset filter / sketch popcount / embedding rerank / graph expansion / temporal validation / RLM recursive / oracle synthesis | 8408–8421 | E0266 |

## Features (F02296–F02380)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F02296 | Memory is not storage — memory is intelligence | 8136 | E0258 | composite | false |
| F02297 | Memory must be living structure (not retrieve-similar-chunks) | 8138 | E0258 | composite | false |
| F02298 | SLM/RLM/PRM/workflow stronger when memory is living | 8138 | E0258 | composite | false |
| F02299 | MemGPT/Letta — LLM context as virtual memory; page-in/page-out | 8142 | E0259 | composite | true |
| F02300 | Zep/Graphiti — temporal knowledge graphs for agent memory + Graph RAG | 8143 | E0259 | composite | true |
| F02301 | A-MEM — agentic memory via Zettelkasten-like dynamic organization + link generation + agent-driven memory management | 8144 | E0259 | composite | true |
| F02302 | D-Mem — dual-process memory with quality gating | 8145 | E0259 | composite | true |
| F02303 | MemMachine — ground-truth-preserving memory; store whole episodes; reduce lossy extraction | 8146 | E0259 | composite | true |
| F02304 | Value-Driven Memory-Augmented Generation — memory connected to value-aligned decisions + adaptive knowledge utilization | 8147 | E0259 | composite | true |
| F02305 | "Memory needs its own plane" | 8149 | E0260 | composite | false |
| F02306 | "Do not build one memory" | 8153 | E0260 | composite | false |
| F02307 | "Build multiple memory types" | 8155 | E0260 | composite | false |
| F02308 | Working Memory definition | 8158–8159 | M00459 | composite | false |
| F02309 | Episodic Memory definition | 8161–8162 | M00460 | composite | false |
| F02310 | Semantic Memory definition | 8164–8165 | M00461 | composite | false |
| F02311 | Procedural Memory definition | 8167–8168 | M00462 | composite | false |
| F02312 | Temporal Graph Memory definition | 8170–8171 | M00463 | composite | false |
| F02313 | Value Memory definition | 8173–8174 | M00464 | composite | false |
| F02314 | KV Memory definition | 8176–8177 | M00465 | composite | false |
| F02315 | "Each type has different rules" | 8180 | E0260 | composite | false |
| F02316 | The Key Principle — "Do not summarize away truth" | 8184–8186 | E0261 | composite | false |
| F02317 | Summaries useful but lossy; keep ground truth | 8188 | E0261 | composite | false |
| F02318 | Ground-truth layer field — raw episode | 8191 | M00466 | composite | false |
| F02319 | Ground-truth layer field — derived facts | 8192 | M00466 | composite | false |
| F02320 | Ground-truth layer field — summary | 8193 | M00466 | composite | false |
| F02321 | Ground-truth layer field — graph edges | 8194 | M00466 | composite | false |
| F02322 | Ground-truth layer field — embeddings | 8195 | M00466 | composite | false |
| F02323 | Ground-truth layer field — bitset metadata | 8196 | M00466 | composite | false |
| F02324 | Ground-truth layer field — trust score | 8197 | M00466 | composite | false |
| F02325 | Ground-truth layer field — freshness | 8198 | M00466 | composite | false |
| F02326 | System can recover if summary was wrong | 8201 | E0261 | composite | false |
| F02327 | MemoryItem.id (uint64_t) | 8209 | M00467 | composite | false |
| F02328 | MemoryItem.type (uint64_t) | 8210 | M00467 | composite | false |
| F02329 | MemoryItem.source_ref (uint64_t) | 8211 | M00467 | composite | false |
| F02330 | MemoryItem.time_range (uint64_t) | 8212 | M00467 | composite | false |
| F02331 | MemoryItem.trust (uint64_t) | 8213 | M00467 | composite | false |
| F02332 | MemoryItem.freshness (uint64_t) | 8214 | M00467 | composite | false |
| F02333 | MemoryItem.topic_sketch (uint64_t) | 8215 | M00467 | composite | false |
| F02334 | MemoryItem.entity_sketch (uint64_t) | 8216 | M00467 | composite | false |
| F02335 | MemoryItem.value_score (uint64_t) | 8217 | M00467 | composite | false |
| F02336 | MemoryItem.flags (uint64_t) | 8218 | M00467 | composite | false |
| F02337 | Actual text/blob lives cold | 8222 | M00468 | composite | false |
| F02338 | Metadata stays hot | 8222 | M00468 | composite | false |
| F02339 | AVX-512 hot metadata scan — project match | 8227 | M00468 | composite | false |
| F02340 | AVX-512 hot metadata scan — topic overlap | 8228 | M00468 | composite | false |
| F02341 | AVX-512 hot metadata scan — freshness | 8229 | M00468 | composite | false |
| F02342 | AVX-512 hot metadata scan — trust | 8230 | M00468 | composite | false |
| F02343 | AVX-512 hot metadata scan — permission | 8231 | M00468 | composite | false |
| F02344 | AVX-512 hot metadata scan — user scope | 8232 | M00468 | composite | false |
| F02345 | AVX-512 hot metadata scan — failure relevance | 8233 | M00468 | composite | false |
| F02346 | Only then do embeddings/rerankers/model calls happen | 8236 | M00468 | composite | false |
| F02347 | Temporal-memory list — preferred model / repo test command / current branch / API version / user preference / project architecture / dependency behavior | 8244–8252 | E0263 | composite | false |
| F02348 | Temporal-query verb — what was true then? | 8256 | M00469 | composite | false |
| F02349 | Temporal-query verb — what is true now? | 8257 | M00469 | composite | false |
| F02350 | Temporal-query verb — what changed? | 8258 | M00469 | composite | false |
| F02351 | Temporal-query verb — who/what contradicted it? | 8260 | M00469 | composite | false |
| F02352 | Temporal-query verb — when was it last verified? | 8261 | M00469 | composite | false |
| F02353 | "Memory must be temporal graph memory" — that is why temporal graph memory is powerful | 8264 | E0263 | composite | false |
| F02354 | Not every observation becomes memory | 8268 | M00470 | composite | false |
| F02355 | Admission store-if — user corrected it | 8274 | M00470 | composite | false |
| F02356 | Admission store-if — task succeeded/failed meaningfully | 8275 | M00470 | composite | false |
| F02357 | Admission store-if — repeated pattern detected | 8276 | M00470 | composite | false |
| F02358 | Admission store-if — new project fact found | 8277 | M00470 | composite | false |
| F02359 | Admission store-if — tool command worked | 8278 | M00470 | composite | false |
| F02360 | Admission store-if — model made a notable mistake | 8279 | M00470 | composite | false |
| F02361 | Admission store-if — high-value context reused | 8280 | M00470 | composite | false |
| F02362 | Admission store-if — preference expressed | 8281 | M00470 | composite | false |
| F02363 | Admission ignore-if — transient / low trust / duplicate / noisy / unverified | 8283–8289 | M00470 | composite | false |
| F02364 | "This is where the Value Plane plugs in" | 8291 | E0264 | composite | false |
| F02365 | Lifecycle stage — observe | 8296 | M00471 | composite | false |
| F02366 | Lifecycle stage — classify | 8297 | M00471 | composite | false |
| F02367 | Lifecycle stage — quarantine if untrusted | 8298 | M00471 | composite | false |
| F02368 | Lifecycle stage — link to existing memories | 8299 | M00471 | composite | false |
| F02369 | Lifecycle stage — score value | 8300 | M00471 | composite | false |
| F02370 | Lifecycle stage — store raw episode | 8301 | M00471 | composite | false |
| F02371 | Lifecycle stage — extract candidate facts | 8302 | M00471 | composite | false |
| F02372 | Lifecycle stage — verify important facts | 8303 | M00471 | composite | false |
| F02373 | Lifecycle stage — promote to semantic/procedural | 8304 | M00471 | composite | false |
| F02374 | Lifecycle stage — decay or archive stale | 8305 | M00471 | composite | false |
| F02375 | "The memory is not passive. It evolves." | 8308 | E0264 | composite | false |
| F02376 | RLM is the perfect memory navigator | 8312 | M00472 | composite | false |
| F02377 | RLM gets memory environment / writes queries-scripts / spawns child calls / returns composed answer | 8316–8321 | M00472 | composite | false |
| F02378 | RLM example — find prior repo test failures after dependency changes; compare fixes; suggest current action | 8325–8331 | M00472 | composite | false |
| F02379 | SLMs maintain memory cheaply — extract facts / tag episodes / detect duplicates / assign topic labels / generate graph edges / classify failure modes / summarize small chunks | 8337–8345 | M00473 | composite | false |
| F02380 | Composite — "Intelligence improves when memory stops being recall and becomes adaptive state" + Memory OS architecture component (8-item: episodic / semantic / temporal graph / procedural skill library / value memory / KV cache registry / admission-promotion-decay / RLM navigator) + station should know "true / stale / useful / risky / personal / reusable / worth acting on" + Memory Plane plugs into Value Plane (M027) | 8453–8474 | E0267 | composite | false |

## Requirements (R04591–R04760)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R04591 | Memory must be modelled as intelligence, not storage | 8136 | E0258 | non-negotiable | false | 10 |
| R04592 | Memory must be a living structure, not retrieve-similar-chunks | 8138 | E0258 | non-negotiable | false | 10 |
| R04593 | Memory layer must strengthen SLM / RLM / PRM / workflow modules | 8138 | E0258 | non-negotiable | false | 10 |
| R04594 | MemGPT/Letta virtual memory pattern cited as research substrate | 8142 | F02299 | non-negotiable | true | 10 |
| R04595 | Zep/Graphiti temporal knowledge graph pattern cited as research substrate | 8143 | F02300 | non-negotiable | true | 10 |
| R04596 | A-MEM Zettelkasten-like agentic memory pattern cited as research substrate | 8144 | F02301 | non-negotiable | true | 10 |
| R04597 | D-Mem dual-process memory + quality gating cited as research substrate | 8145 | F02302 | non-negotiable | true | 10 |
| R04598 | MemMachine ground-truth-preserving episodes cited as research substrate | 8146 | F02303 | non-negotiable | true | 10 |
| R04599 | Value-Driven MAG cited as research substrate | 8147 | F02304 | non-negotiable | true | 10 |
| R04600 | Memory needs its own plane (architecturally separate) | 8149 | E0260 | non-negotiable | false | 10 |
| R04601 | "Do not build one memory" — must build multiple types | 8153–8155 | E0260 | non-negotiable | false | 10 |
| R04602 | Memory type — Working Memory | 8158–8159 | M00459 | non-negotiable | false | 10 |
| R04603 | Working Memory carries — current task | 8158 | M00459 | non-negotiable | true | 10 |
| R04604 | Working Memory carries — active branches | 8159 | M00459 | non-negotiable | true | 10 |
| R04605 | Working Memory carries — local facts | 8159 | M00459 | non-negotiable | true | 10 |
| R04606 | Working Memory carries — tool outputs | 8159 | M00459 | non-negotiable | true | 10 |
| R04607 | Memory type — Episodic Memory | 8161–8162 | M00460 | non-negotiable | false | 10 |
| R04608 | Episodic Memory carries — full traces | 8162 | M00460 | non-negotiable | true | 10 |
| R04609 | Episodic Memory carries — conversations | 8162 | M00460 | non-negotiable | true | 10 |
| R04610 | Episodic Memory carries — task attempts | 8162 | M00460 | non-negotiable | true | 10 |
| R04611 | Episodic Memory carries — failures | 8162 | M00460 | non-negotiable | true | 10 |
| R04612 | Episodic Memory carries — user corrections | 8162 | M00460 | non-negotiable | true | 10 |
| R04613 | Memory type — Semantic Memory | 8164–8165 | M00461 | non-negotiable | false | 10 |
| R04614 | Semantic Memory carries — distilled facts / concepts / summaries / project knowledge | 8165 | M00461 | non-negotiable | true | 10 |
| R04615 | Memory type — Procedural Memory | 8167–8168 | M00462 | non-negotiable | false | 10 |
| R04616 | Procedural Memory carries — skills / workflows / command recipes / successful tool sequences | 8168 | M00462 | non-negotiable | true | 10 |
| R04617 | Memory type — Temporal Graph Memory | 8170–8171 | M00463 | non-negotiable | false | 10 |
| R04618 | Temporal Graph Memory carries — entities / relationships / timestamps / changing facts | 8171 | M00463 | non-negotiable | true | 10 |
| R04619 | Memory type — Value Memory | 8173–8174 | M00464 | non-negotiable | false | 10 |
| R04620 | Value Memory carries — what worked / what failed / which model-tool-profile succeeded | 8174 | M00464 | non-negotiable | true | 10 |
| R04621 | Memory type — KV Memory | 8176–8177 | M00465 | non-negotiable | false | 10 |
| R04622 | KV Memory carries — cached model prefixes / reusable prompt blocks / context blocks | 8177 | M00465 | non-negotiable | true | 10 |
| R04623 | Each memory type has different rules | 8180 | E0260 | non-negotiable | false | 10 |
| R04624 | Key Principle — "Do not summarize away truth" | 8184–8186 | E0261 | non-negotiable | false | 10 |
| R04625 | Summaries are useful but lossy | 8188 | E0261 | non-negotiable | false | 10 |
| R04626 | Ground-truth must be kept alongside derived layers | 8188 | E0261 | non-negotiable | false | 10 |
| R04627 | Ground-truth layer — raw episode stored | 8191 | M00466 | non-negotiable | false | 10 |
| R04628 | Ground-truth layer — derived facts stored | 8192 | M00466 | non-negotiable | false | 10 |
| R04629 | Ground-truth layer — summary stored | 8193 | M00466 | non-negotiable | false | 10 |
| R04630 | Ground-truth layer — graph edges stored | 8194 | M00466 | non-negotiable | false | 10 |
| R04631 | Ground-truth layer — embeddings stored | 8195 | M00466 | non-negotiable | false | 10 |
| R04632 | Ground-truth layer — bitset metadata stored | 8196 | M00466 | non-negotiable | false | 10 |
| R04633 | Ground-truth layer — trust score stored | 8197 | M00466 | non-negotiable | false | 10 |
| R04634 | Ground-truth layer — freshness stored | 8198 | M00466 | non-negotiable | false | 10 |
| R04635 | System must recover if a summary was wrong | 8201 | E0261 | non-negotiable | false | 10 |
| R04636 | A memory item must be typed | 8205 | M00467 | non-negotiable | false | 10 |
| R04637 | MemoryItem field — id (uint64_t) | 8209 | F02327 | non-negotiable | true | 10 |
| R04638 | MemoryItem field — type (uint64_t) | 8210 | F02328 | non-negotiable | true | 10 |
| R04639 | MemoryItem field — source_ref (uint64_t) | 8211 | F02329 | non-negotiable | true | 10 |
| R04640 | MemoryItem field — time_range (uint64_t) | 8212 | F02330 | non-negotiable | true | 10 |
| R04641 | MemoryItem field — trust (uint64_t) | 8213 | F02331 | non-negotiable | true | 10 |
| R04642 | MemoryItem field — freshness (uint64_t) | 8214 | F02332 | non-negotiable | true | 10 |
| R04643 | MemoryItem field — topic_sketch (uint64_t) | 8215 | F02333 | non-negotiable | true | 10 |
| R04644 | MemoryItem field — entity_sketch (uint64_t) | 8216 | F02334 | non-negotiable | true | 10 |
| R04645 | MemoryItem field — value_score (uint64_t) | 8217 | F02335 | non-negotiable | true | 10 |
| R04646 | MemoryItem field — flags (uint64_t) | 8218 | F02336 | non-negotiable | true | 10 |
| R04647 | Actual text/blob lives cold | 8222 | M00468 | non-negotiable | false | 10 |
| R04648 | Metadata stays hot | 8222 | M00468 | non-negotiable | false | 10 |
| R04649 | AVX-512 scans hot metadata | 8224 | M00468 | non-negotiable | false | 10 |
| R04650 | AVX-512 hot scan — project match | 8227 | F02339 | non-negotiable | true | 10 |
| R04651 | AVX-512 hot scan — topic overlap | 8228 | F02340 | non-negotiable | true | 10 |
| R04652 | AVX-512 hot scan — freshness | 8229 | F02341 | non-negotiable | true | 10 |
| R04653 | AVX-512 hot scan — trust | 8230 | F02342 | non-negotiable | true | 10 |
| R04654 | AVX-512 hot scan — permission | 8231 | F02343 | non-negotiable | true | 10 |
| R04655 | AVX-512 hot scan — user scope | 8232 | F02344 | non-negotiable | true | 10 |
| R04656 | AVX-512 hot scan — failure relevance | 8233 | F02345 | non-negotiable | true | 10 |
| R04657 | Only after AVX-512 hot scan do embeddings / rerankers / model calls happen | 8236 | M00468 | non-negotiable | false | 10 |
| R04658 | Temporal Memory is crucial | 8240 | E0263 | non-negotiable | false | 10 |
| R04659 | Temporal-changing fact — preferred model | 8245 | F02347 | non-negotiable | true | 10 |
| R04660 | Temporal-changing fact — repo test command | 8246 | F02347 | non-negotiable | true | 10 |
| R04661 | Temporal-changing fact — current branch | 8247 | F02347 | non-negotiable | true | 10 |
| R04662 | Temporal-changing fact — API version | 8248 | F02347 | non-negotiable | true | 10 |
| R04663 | Temporal-changing fact — user preference | 8249 | F02347 | non-negotiable | true | 10 |
| R04664 | Temporal-changing fact — project architecture | 8250 | F02347 | non-negotiable | true | 10 |
| R04665 | Temporal-changing fact — dependency behavior | 8251 | F02347 | non-negotiable | true | 10 |
| R04666 | Temporal-memory query — what was true then? | 8256 | F02348 | non-negotiable | true | 10 |
| R04667 | Temporal-memory query — what is true now? | 8257 | F02349 | non-negotiable | true | 10 |
| R04668 | Temporal-memory query — what changed? | 8258 | F02350 | non-negotiable | true | 10 |
| R04669 | Temporal-memory query — who/what contradicted it? | 8260 | F02351 | non-negotiable | true | 10 |
| R04670 | Temporal-memory query — when was it last verified? | 8261 | F02352 | non-negotiable | true | 10 |
| R04671 | Temporal graph memory is powerful — the reason: ability to answer the 5 queries | 8264 | E0263 | non-negotiable | false | 10 |
| R04672 | Memory Admission — not every observation becomes memory | 8268 | M00470 | non-negotiable | false | 10 |
| R04673 | Admission must be value-driven | 8270 | M00470 | non-negotiable | false | 10 |
| R04674 | Admission store-if — user corrected it | 8274 | F02355 | non-negotiable | true | 10 |
| R04675 | Admission store-if — task succeeded/failed meaningfully | 8275 | F02356 | non-negotiable | true | 10 |
| R04676 | Admission store-if — repeated pattern detected | 8276 | F02357 | non-negotiable | true | 10 |
| R04677 | Admission store-if — new project fact found | 8277 | F02358 | non-negotiable | true | 10 |
| R04678 | Admission store-if — tool command worked | 8278 | F02359 | non-negotiable | true | 10 |
| R04679 | Admission store-if — model made a notable mistake | 8279 | F02360 | non-negotiable | true | 10 |
| R04680 | Admission store-if — high-value context reused | 8280 | F02361 | non-negotiable | true | 10 |
| R04681 | Admission store-if — preference expressed | 8281 | F02362 | non-negotiable | true | 10 |
| R04682 | Admission ignore-if — transient | 8284 | F02363 | non-negotiable | true | 10 |
| R04683 | Admission ignore-if — low trust | 8285 | F02363 | non-negotiable | true | 10 |
| R04684 | Admission ignore-if — duplicate | 8286 | F02363 | non-negotiable | true | 10 |
| R04685 | Admission ignore-if — noisy | 8287 | F02363 | non-negotiable | true | 10 |
| R04686 | Admission ignore-if — unverified | 8288 | F02363 | non-negotiable | true | 10 |
| R04687 | Value Plane plugs into Memory Admission | 8291 | E0264 | non-negotiable | false | 10 |
| R04688 | Memory Lifecycle stage — observe | 8296 | F02365 | non-negotiable | true | 10 |
| R04689 | Memory Lifecycle stage — classify | 8297 | F02366 | non-negotiable | true | 10 |
| R04690 | Memory Lifecycle stage — quarantine if untrusted | 8298 | F02367 | non-negotiable | true | 10 |
| R04691 | Memory Lifecycle stage — link to existing memories | 8299 | F02368 | non-negotiable | true | 10 |
| R04692 | Memory Lifecycle stage — score value | 8300 | F02369 | non-negotiable | true | 10 |
| R04693 | Memory Lifecycle stage — store raw episode | 8301 | F02370 | non-negotiable | true | 10 |
| R04694 | Memory Lifecycle stage — extract candidate facts | 8302 | F02371 | non-negotiable | true | 10 |
| R04695 | Memory Lifecycle stage — verify important facts | 8303 | F02372 | non-negotiable | true | 10 |
| R04696 | Memory Lifecycle stage — promote to semantic/procedural memory | 8304 | F02373 | non-negotiable | true | 10 |
| R04697 | Memory Lifecycle stage — decay or archive stale memories | 8305 | F02374 | non-negotiable | true | 10 |
| R04698 | "The memory is not passive. It evolves." | 8308 | E0264 | non-negotiable | false | 10 |
| R04699 | RLM is the perfect memory navigator | 8312 | M00472 | non-negotiable | false | 10 |
| R04700 | RLM does NOT dump memory into prompt | 8314 | M00472 | non-negotiable | false | 10 |
| R04701 | RLM gets memory environment | 8317 | M00472 | non-negotiable | true | 10 |
| R04702 | RLM writes queries/scripts | 8318 | M00472 | non-negotiable | true | 10 |
| R04703 | RLM spawns child calls over slices | 8319 | M00472 | non-negotiable | true | 10 |
| R04704 | RLM returns composed answer | 8320 | M00472 | non-negotiable | true | 10 |
| R04705 | RLM example — find all prior times repo tests failed after dependency changes | 8326 | F02378 | non-negotiable | true | 10 |
| R04706 | RLM example — compare fixes | 8327 | F02378 | non-negotiable | true | 10 |
| R04707 | RLM example — suggest current action | 8328 | F02378 | non-negotiable | true | 10 |
| R04708 | RLM can inspect traces / diffs / test logs / memories recursively | 8331 | M00472 | non-negotiable | false | 10 |
| R04709 | SLM memory job — extract facts | 8338 | M00473 | non-negotiable | true | 10 |
| R04710 | SLM memory job — tag episodes | 8339 | M00473 | non-negotiable | true | 10 |
| R04711 | SLM memory job — detect duplicates | 8340 | M00473 | non-negotiable | true | 10 |
| R04712 | SLM memory job — assign topic labels | 8341 | M00473 | non-negotiable | true | 10 |
| R04713 | SLM memory job — generate graph edges | 8342 | M00473 | non-negotiable | true | 10 |
| R04714 | SLM memory job — classify failure modes | 8343 | M00473 | non-negotiable | true | 10 |
| R04715 | SLM memory job — summarize small chunks | 8344 | M00473 | non-negotiable | true | 10 |
| R04716 | "Oracle should not do janitorial memory work unless the stakes are high" | 8347 | M00473 | non-negotiable | false | 10 |
| R04717 | Reward + Memory — memory should include outcome value | 8351 | E0265 | non-negotiable | false | 10 |
| R04718 | Outcome value — this workflow succeeded | 8354 | E0265 | non-negotiable | true | 10 |
| R04719 | Outcome value — this model failed on this tool type | 8355 | E0265 | non-negotiable | true | 10 |
| R04720 | Outcome value — this command fixed the issue | 8356 | E0265 | non-negotiable | true | 10 |
| R04721 | Outcome value — this retrieved chunk was useful | 8357 | E0265 | non-negotiable | true | 10 |
| R04722 | Outcome value — this memory caused a hallucination | 8358 | E0265 | non-negotiable | true | 10 |
| R04723 | Reward+Memory creates a local experience base | 8361 | E0265 | non-negotiable | false | 10 |
| R04724 | Future routing improves from reward-memory | 8363 | E0265 | non-negotiable | false | 10 |
| R04725 | Memory as cache of intelligence — a skill is crystallized memory | 8367 | E0265 | non-negotiable | false | 10 |
| R04726 | Skill formation — raw attempts → successful trace → generalized procedure → skill | 8370 | E0265 | non-negotiable | true | 10 |
| R04727 | A profile is crystallized preference memory | 8373 | E0265 | non-negotiable | false | 10 |
| R04728 | Profile formation — user choices → reward weights → default behavior | 8376 | E0265 | non-negotiable | true | 10 |
| R04729 | A routing policy is crystallized performance memory | 8379 | E0265 | non-negotiable | false | 10 |
| R04730 | Routing-policy formation — model/tool outcomes → adaptive router | 8382 | E0265 | non-negotiable | true | 10 |
| R04731 | Memory is not "facts" — memory is compressed experience | 8385 | E0265 | non-negotiable | false | 10 |
| R04732 | Hardware mapping — RAM stores hot memory metadata / active graph / indexes / embeddings cache | 8392–8393 | M00474 | non-negotiable | true | 10 |
| R04733 | Hardware mapping — NVMe/ZFS stores raw episodes / replay logs / documents / model artifacts / snapshots | 8395–8396 | M00474 | non-negotiable | true | 10 |
| R04734 | Hardware mapping — Blackwell does deep synthesis / conflict resolution / high-value memory promotion | 8398–8399 | M00474 | non-negotiable | true | 10 |
| R04735 | Hardware mapping — 3090 does memory extraction / reranking / SLM tagging / graph edge proposals | 8401–8402 | M00474 | non-negotiable | true | 10 |
| R04736 | Hardware mapping — AVX-512 CPU does metadata scans / bitset intersections / freshness-trust filters / candidate packing | 8404–8405 | M00474 | non-negotiable | true | 10 |
| R04737 | Memory Query Pipeline step 1 — Intent → memory need | 8411 | M00475 | non-negotiable | true | 10 |
| R04738 | Memory Query Pipeline step 2 — AVX-512 bitset filter | 8412 | M00475 | non-negotiable | true | 10 |
| R04739 | Memory Query Pipeline step 3 — sketch/popcount relevance | 8413 | M00475 | non-negotiable | true | 10 |
| R04740 | Memory Query Pipeline step 4 — embedding/rerank | 8414 | M00475 | non-negotiable | true | 10 |
| R04741 | Memory Query Pipeline step 5 — graph expansion | 8415 | M00475 | non-negotiable | true | 10 |
| R04742 | Memory Query Pipeline step 6 — temporal validation | 8416 | M00475 | non-negotiable | true | 10 |
| R04743 | Memory Query Pipeline step 7 — RLM recursive inspection if large | 8417 | M00475 | non-negotiable | true | 10 |
| R04744 | Memory Query Pipeline step 8 — oracle synthesis if high-value | 8418 | M00475 | non-negotiable | true | 10 |
| R04745 | "This is much smarter than top-k vectors" | 8421 | M00475 | non-negotiable | false | 10 |
| R04746 | Profile-affected memory — fast: shallow memory, high-confidence only | 8427–8428 | E0267 | non-negotiable | true | 10 |
| R04747 | Profile-affected memory — careful: temporal validation + graph expansion | 8430–8431 | E0267 | non-negotiable | true | 10 |
| R04748 | Profile-affected memory — private: local-only, no external augmentation | 8433–8434 | E0267 | non-negotiable | true | 10 |
| R04749 | Profile-affected memory — creative: broader associative memory | 8436–8437 | E0267 | non-negotiable | true | 10 |
| R04750 | Profile-affected memory — coding: procedural/project memory prioritized | 8439–8440 | E0267 | non-negotiable | true | 10 |
| R04751 | Profile-affected memory — research: evidence + citation memory prioritized | 8442–8443 | E0267 | non-negotiable | true | 10 |
| R04752 | Profile-affected memory — autonomous: value/failure memory prioritized | 8445–8446 | E0267 | non-negotiable | true | 10 |
| R04753 | "choices, profiles, flexibility" — operator-facing memory shaping | 8448 | E0267 | non-negotiable | false | 10 |
| R04754 | New architecture component — Memory Operating System | 8454–8455 | E0267 | non-negotiable | false | 10 |
| R04755 | Memory OS components — episodic store / semantic store / temporal graph / procedural skill library / value memory / KV cache registry / memory admission-promotion-decay / RLM memory navigator | 8457–8464 | E0267 | non-negotiable | false | 10 |
| R04756 | Key line — "Intelligence improves when memory stops being recall and becomes adaptive state" | 8468–8470 | E0267 | non-negotiable | false | 10 |
| R04757 | The station must not merely remember | 8472 | E0267 | non-negotiable | false | 10 |
| R04758 | The station must know — true / stale / useful / risky / personal / reusable / worth acting on | 8473 | E0267 | non-negotiable | false | 10 |
| R04759 | Memory Plane integrates with Value Plane (M027) — admission gating + outcome value | 8291 + 8351 | E0264 + E0265 | non-negotiable | false | 10 |
| R04760 | Composite — Memory OS is the 5th plane of the 8-plane full stack (M027 R04590); integrates with M025 cognitive compiler + M026 SLM swarm / RLM engine / RM-PRM judges + M027 Value Plane | 8121–8474 | E0267 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M027 Value plane (7731–8121) / M029 Computer-Use plane (8475–8804)
- 8-plane full stack: M027 E0257 R04590
- Memory OS architecture component: M00474 + M00475 + R04754–R04755
- Selfdef boundary: any IPS-side memory enforcement (admission control / quarantine) flows via MS006 functional modules + MS007 typed-mirror crates, NOT direct sovereign-os crate import
