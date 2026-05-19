# M010 — Deterministic data plane — simdjson + Hyperscan + CRoaring

> Parent: `backlog/milestones/INDEX.md` row M010 (dump 2249–2459).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 2249–2459.
> All entries below are extracted from the dump line range. No invention.

> **AVX++ canon update — 2026-05-19**: this milestone is affected by backward-sweep redefinition(s) — Commit Authority deterministic-vs-earned (BREAKING-FOR-LAYERING). See sovereign-os M061 for canonical pinning (commit 6f07dca). R-rows below are interpreted under the canonical later definitions per operator standing direction "layered: new direction ON TOP OF prior direction — never discarded".


## Epics (E0078–E0086)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0078 | Deterministic Data Plane — CPU owns high-speed data plane | 2268–2281 |
| E0079 | The Trick — bits are law, text is payload | 2289–2310 |
| E0080 | AVX-512 Features As AI Infrastructure — VPTERNLOG / VPCOMPRESS / VPEXPAND / VPOPCNTDQ / VP2INTERSECT / VPCONFLICT / VBMI / VBMI2 / k-masks | 2312–2342 |
| E0081 | Concrete Design Upgrade — six data-plane services | 2344–2373 |
| E0082 | Memory Retrieval Gets Smarter — layered filters | 2375–2406 |
| E0083 | Tool Calls Become Transactions — 8-stage commit pipeline | 2408–2425 |
| E0084 | The Revolutionary Shape — CPU-pipeline runtime (Fetch / Decode / Execute / Validate / Retire / Commit) | 2427–2449 |
| E0085 | Speculative AI execution with deterministic commit — organ assignment law | 2451–2457 |
| E0086 | External-library validation — simdjson + Hyperscan + CRoaring + XGrammar + LLGuidance | 2285, 2423 |

## Modules (M00147–M00163)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00147 | JSON/tool-call validation — gigabytes/sec via simdjson AVX-512 path | 2273, 2285 | E0078 |
| M00148 | Regex/policy matching — SIMD automata via Hyperscan AVX-512 runtime | 2274, 2285 | E0078 |
| M00149 | Memory-set intersection — compressed bitmaps via CRoaring AVX2/AVX-512 | 2275, 2285 | E0078 |
| M00150 | Token mask fusion — vocab bitset over grammar/schema/tool/safety masks | 2276, 2349–2351 | E0081 |
| M00151 | Duplicate detection — VPCONFLICT inside vectorized hash/table updates | 2277, 2330–2331 | E0080 |
| M00152 | Branch compaction — VPCOMPRESS/VPEXPAND packs active branches into dense GPU batches | 2278, 2321–2323 | E0080 |
| M00153 | Context filtering — deterministic bitset filters precede embedding search | 2279, 2378–2380 | E0082 |
| M00154 | Trace/replay indexing — bitset/searchable trace log for debugging + self-improvement | 2280, 2365–2366 | E0081 |
| M00155 | Token Law Engine — grammar/schema/tool/safety masks composed over vocab bitsets | 2349–2351 | E0081 |
| M00156 | Policy Scanner — Hyperscan-style multi-pattern matching over tool intents + outputs | 2352–2353 | E0081 |
| M00157 | JSON Commit Validator — simdjson-style validation before any structured output is accepted | 2355–2356 | E0081 |
| M00158 | Memory Bitmap Index — CRoaring-style memory sets (project ∩ topic ∩ freshness ∩ trust ∩ permissions) | 2358–2360 | E0081 |
| M00159 | Branch Compactor — AVX-512 compresses surviving branches into dense oracle/scout batches | 2362–2363 | E0081 |
| M00160 | Replay Index — bitset/searchable trace log | 2365–2366 | E0081 |
| M00161 | Memory-item six-sketch row — u64 topic / entity / tool / trust_flags / freshness / permissions | 2398–2404 | E0082 |
| M00162 | Tool-call 8-stage transaction — parse JSON / validate schema / scan policy / check permission bits / check workspace bounds / check branch budget / classify risk / commit-or-reject | 2412–2421 | E0083 |
| M00163 | CPU-pipeline runtime — Fetch / Decode / Execute / Validate / Retire / Commit stages | 2431–2449 | E0084 |

## Features (F00766–F00850)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00766 | Toggle JSON validator backend (simdjson vs serde_json vs jq) | 2273 | M00147 | mode | true |
| F00767 | Profile knob — `json_validator = simdjson \| serde \| jq` | 2273 | M00147 | profile | true |
| F00768 | Env var `SOVEREIGN_JSON_VALIDATOR_BACKEND` | 2273 | M00147 | env_var | true |
| F00769 | CLI `--json-validator <backend>` | 2273 | M00147 | cli_verb | true |
| F00770 | Dashboard surface — JSON validator throughput (GB/sec) | 2273, 2285 | M00147 | dashboard | true |
| F00771 | API `GET /v1/data-plane/json/throughput` | 2273 | M00147 | api_endpoint | true |
| F00772 | Metric `sovereign_data_plane_json_bytes_validated_total` | 2273 | M00147 | observability_metric | true |
| F00773 | Test — simdjson round-trip on synthetic + real tool-call corpus | 2273, 2355 | M00157 | test | true |
| F00774 | Test — JSON throughput ≥ 1 GB/sec on Zen 5 AVX-512 path | 2285 | M00147 | test | true |
| F00775 | Toggle regex backend (Hyperscan vs RE2 vs `regex` crate) | 2274 | M00148 | mode | true |
| F00776 | Profile knob — `regex_backend = hyperscan \| re2 \| regex` | 2274 | M00148 | profile | true |
| F00777 | Env var `SOVEREIGN_REGEX_BACKEND` | 2274 | M00148 | env_var | true |
| F00778 | CLI `--regex-backend <name>` | 2274 | M00148 | cli_verb | true |
| F00779 | Dashboard surface — regex match-rate + active-patterns count | 2274 | M00148 | dashboard | true |
| F00780 | API `POST /v1/data-plane/regex/compile` (returns pattern handle) | 2274 | M00156 | api_endpoint | true |
| F00781 | API `POST /v1/data-plane/regex/scan` (returns match-set) | 2274 | M00156 | api_endpoint | true |
| F00782 | Metric `sovereign_data_plane_regex_bytes_scanned_total` | 2274 | M00148 | observability_metric | true |
| F00783 | Test — Hyperscan AVX-512 path enables on Zen 5 + falls back on Zen 4 | 2274, 2285 | M00148 | test | true |
| F00784 | Toggle memory-bitmap backend (CRoaring vs `roaring` crate vs FixedBitSet) | 2275 | M00149 | mode | true |
| F00785 | Profile knob — `memory_bitmap_backend = croaring \| roaring_rs \| fixed` | 2275 | M00149 | profile | true |
| F00786 | Env var `SOVEREIGN_MEMORY_BITMAP_BACKEND` | 2275 | M00149 | env_var | true |
| F00787 | CLI `--memory-bitmap-backend <name>` | 2275 | M00149 | cli_verb | true |
| F00788 | Dashboard surface — bitmap density + AND/OR/XOR throughput | 2275, 2285 | M00149 | dashboard | true |
| F00789 | API `GET /v1/data-plane/memory-bitmap/stats` | 2275 | M00149 | api_endpoint | true |
| F00790 | Metric `sovereign_data_plane_bitmap_set_ops_total{op}` | 2275 | M00149 | observability_metric | true |
| F00791 | Test — CRoaring 5-set intersection on memory rows (project ∩ topic ∩ freshness ∩ trust ∩ permissions) | 2358–2360 | M00158 | test | true |
| F00792 | Token-mask fusion engine — combine grammar + schema + tool + safety masks over vocab | 2276, 2349–2351 | M00155 | composite | true |
| F00793 | Profile knob — `token_law_engine_mask_layers = grammar,schema,tool,safety` | 2349–2351 | M00155 | profile | true |
| F00794 | Env var `SOVEREIGN_TOKEN_LAW_MASK_LAYERS` | 2349–2351 | M00155 | env_var | true |
| F00795 | CLI `--token-law-mask-layers <csv>` | 2349–2351 | M00155 | cli_verb | true |
| F00796 | Dashboard surface — token-law mask coverage heatmap | 2349–2351 | M00155 | dashboard | true |
| F00797 | API `POST /v1/data-plane/token-law/fuse` | 2349–2351 | M00155 | api_endpoint | true |
| F00798 | Metric `sovereign_data_plane_token_law_mask_layers` | 2349–2351 | M00155 | observability_metric | true |
| F00799 | Test — XGrammar mask compatibility (binary mask over vocab) | 2423 | M00155 | test | true |
| F00800 | Test — LLGuidance mask compatibility (CPU mask for large tokenizers) | 2423 | M00155 | test | true |
| F00801 | VPCONFLICT-based duplicate detector for hash/table updates | 2277, 2330–2331 | M00151 | mode | true |
| F00802 | Profile knob — `duplicate_detect_backend = vpconflict \| scalar` | 2330–2331 | M00151 | profile | true |
| F00803 | Env var `SOVEREIGN_DUPLICATE_DETECT_BACKEND` | 2330–2331 | M00151 | env_var | true |
| F00804 | CLI `--duplicate-detect <backend>` | 2330–2331 | M00151 | cli_verb | true |
| F00805 | Dashboard surface — duplicate-detection collisions per second | 2330–2331 | M00151 | dashboard | true |
| F00806 | Metric `sovereign_data_plane_duplicate_collisions_total` | 2330–2331 | M00151 | observability_metric | true |
| F00807 | Test — VPCONFLICT correctness on full-collision + no-collision + partial inputs | 2330–2331 | M00151 | test | true |
| F00808 | Branch compactor — VPCOMPRESS packs alive branches into dense oracle batch | 2278, 2321–2323 | M00152 | composite | true |
| F00809 | Branch compactor — VPEXPAND restores compacted branches to original lanes | 2321–2323 | M00152 | composite | true |
| F00810 | Profile knob — `branch_compactor = vpcompress \| scalar` | 2321–2323 | M00152 | profile | true |
| F00811 | Env var `SOVEREIGN_BRANCH_COMPACTOR_BACKEND` | 2321–2323 | M00152 | env_var | true |
| F00812 | Dashboard surface — branch survival ratio per tick | 2321–2323, 2362–2363 | M00159 | dashboard | true |
| F00813 | Metric `sovereign_data_plane_branch_compact_in_lanes` | 2321–2323 | M00152 | observability_metric | true |
| F00814 | Metric `sovereign_data_plane_branch_compact_out_lanes` | 2321–2323 | M00152 | observability_metric | true |
| F00815 | Bitset-filter cascade — project / file / date / trust / tool / topic | 2279, 2378–2380 | M00153 | composite | true |
| F00816 | Profile knob — `bitset_filter_axes = project,file,date,trust,tool,topic` | 2378–2380 | M00153 | profile | true |
| F00817 | Env var `SOVEREIGN_BITSET_FILTER_AXES` | 2378–2380 | M00153 | env_var | true |
| F00818 | CLI `--bitset-filter-axes <csv>` | 2378–2380 | M00153 | cli_verb | true |
| F00819 | Sketch-overlap scorer — `popcount(query_sketch & memory_sketch)` | 2382–2384 | M00161 | composite | true |
| F00820 | 3090 reranker stage — cheap neural judgment on sketch survivors | 2386–2388 | M00153 | composite | true |
| F00821 | Blackwell oracle stage — only for hard synthesis | 2389–2391 | M00153 | composite | true |
| F00822 | Memory-item row — `u64 topic_sketch` field | 2398 | M00161 | data_model | false |
| F00823 | Memory-item row — `u64 entity_sketch` field | 2399 | M00161 | data_model | false |
| F00824 | Memory-item row — `u64 tool_sketch` field | 2400 | M00161 | data_model | false |
| F00825 | Memory-item row — `u64 trust_flags` field | 2401 | M00161 | data_model | false |
| F00826 | Memory-item row — `u64 freshness` field | 2402 | M00161 | data_model | false |
| F00827 | Memory-item row — `u64 permissions` field | 2403 | M00161 | data_model | false |
| F00828 | Tool-call stage 1 — parse JSON (simdjson) | 2413 | M00162 | composite | false |
| F00829 | Tool-call stage 2 — validate schema | 2414 | M00162 | composite | false |
| F00830 | Tool-call stage 3 — scan policy (Hyperscan) | 2415 | M00162 | composite | false |
| F00831 | Tool-call stage 4 — check permission bits (VPTERNLOG) | 2416, 2317–2319 | M00162 | composite | false |
| F00832 | Tool-call stage 5 — check workspace bounds | 2417 | M00162 | composite | false |
| F00833 | Tool-call stage 6 — check branch budget | 2418 | M00162 | composite | false |
| F00834 | Tool-call stage 7 — classify risk | 2419 | M00162 | composite | false |
| F00835 | Tool-call stage 8 — commit or reject | 2420 | M00162 | composite | false |
| F00836 | Dashboard surface — tool-call stage drop-off histogram (which stage rejected the call) | 2412–2421 | M00162 | dashboard | true |
| F00837 | Metric `sovereign_tool_call_stage_reject_total{stage}` | 2412–2421 | M00162 | observability_metric | true |
| F00838 | CPU-pipeline runtime stage — Fetch (user task + memory refs + branch state) | 2433–2434 | M00163 | composite | false |
| F00839 | CPU-pipeline runtime stage — Decode (classify intent + grammar + route + permissions) | 2436–2437 | M00163 | composite | false |
| F00840 | CPU-pipeline runtime stage — Execute (scout GPU drafts + tools prepare + memory retrieves) | 2439–2440 | M00163 | composite | false |
| F00841 | CPU-pipeline runtime stage — Validate (CPU masks + parses + scans + checks) | 2442–2443 | M00163 | composite | false |
| F00842 | CPU-pipeline runtime stage — Retire (Blackwell verifies high-value transitions) | 2445–2446 | M00163 | composite | false |
| F00843 | CPU-pipeline runtime stage — Commit (deterministic log writes accepted state) | 2448–2449 | M00163 | composite | false |
| F00844 | Dashboard surface — CPU-pipeline stage latencies (6-row gantt per request) | 2431–2449 | M00163 | dashboard | true |
| F00845 | Profile knob — `cpu_pipeline_retire_threshold` (when Blackwell engaged for retirement) | 2445–2446 | M00163 | profile | true |
| F00846 | Env var `SOVEREIGN_CPU_PIPELINE_RETIRE_THRESHOLD` | 2445–2446 | M00163 | env_var | true |
| F00847 | Metric `sovereign_cpu_pipeline_stage_latency_us{stage}` | 2431–2449 | M00163 | observability_metric | true |
| F00848 | Composite F00848 — six data-plane services compose into ONE runtime data-plane crate | 2344–2367 | E0081 | composite | true |
| F00849 | Composite F00849 — speculative AI execution with deterministic commit law enforced by API | 2451–2457 | E0085 | composite | false |
| F00850 | Composite F00850 — `The CPU should transform language into constrained sets before GPUs reason over it` runtime invariant | 2371–2372 | E0078 | composite | false |

## Requirements (R01531–R01700)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R01531 | The CPU owns a high-speed data plane for JSON/tool-call validation | 2273 | M00147 | non-negotiable | false | 10 |
| R01532 | The CPU owns a high-speed data plane for regex/policy matching | 2274 | M00148 | non-negotiable | false | 10 |
| R01533 | The CPU owns a high-speed data plane for memory-set intersection | 2275 | M00149 | non-negotiable | false | 10 |
| R01534 | The CPU owns a high-speed data plane for token mask fusion | 2276 | M00150 | non-negotiable | false | 10 |
| R01535 | The CPU owns a high-speed data plane for duplicate detection | 2277 | M00151 | non-negotiable | false | 10 |
| R01536 | The CPU owns a high-speed data plane for branch compaction | 2278 | M00152 | non-negotiable | false | 10 |
| R01537 | The CPU owns a high-speed data plane for context filtering | 2279 | M00153 | non-negotiable | false | 10 |
| R01538 | The CPU owns a high-speed data plane for trace/replay indexing | 2280 | M00154 | non-negotiable | false | 10 |
| R01539 | simdjson validates JSON at gigabytes/sec using SIMD with AVX-512 paths | 2285 | M00147 | non-negotiable | false | 10 |
| R01540 | Hyperscan matches many regexes/streams efficiently with AVX-512 support | 2285 | M00148 | non-negotiable | false | 10 |
| R01541 | CRoaring gives compressed bitmaps with AVX2/AVX-512 optimizations for fast set operations | 2285 | M00149 | non-negotiable | false | 10 |
| R01542 | The hot object is bitsets, not text | 2295–2298 | E0079 | non-negotiable | false | 10 |
| R01543 | The hot object is masks, not text | 2299 | E0079 | non-negotiable | false | 10 |
| R01544 | The hot object is branch ids, not text | 2300 | E0079 | non-negotiable | false | 10 |
| R01545 | The hot object is token classes, not text | 2301 | E0079 | non-negotiable | false | 10 |
| R01546 | The hot object is memory ids, not text | 2302 | E0079 | non-negotiable | false | 10 |
| R01547 | The hot object is permission flags, not text | 2303 | E0079 | non-negotiable | false | 10 |
| R01548 | The hot object is grammar states, not text | 2304 | E0079 | non-negotiable | false | 10 |
| R01549 | The hot object is routing states, not text | 2305 | E0079 | non-negotiable | false | 10 |
| R01550 | Text is payload; bits are law | 2308 | E0079 | non-negotiable | false | 10 |
| R01551 | The control plane is simultaneously a vector database | 2310 | E0079 | non-negotiable | false | 10 |
| R01552 | The control plane is simultaneously a parser | 2310 | E0079 | non-negotiable | false | 10 |
| R01553 | The control plane is simultaneously a policy engine | 2310 | E0079 | non-negotiable | false | 10 |
| R01554 | The control plane is simultaneously a grammar engine | 2310 | E0079 | non-negotiable | false | 10 |
| R01555 | The control plane is simultaneously a scheduler | 2310 | E0079 | non-negotiable | false | 10 |
| R01556 | VPTERNLOG fuses policy logic — `commit = verified & valid \| trusted_fast_path` | 2317–2319 | M00155 | non-negotiable | false | 10 |
| R01557 | VPCOMPRESS packs active branches into dense GPU batches | 2321–2322 | M00152 | non-negotiable | false | 10 |
| R01558 | VPEXPAND restores compacted branches to their original lanes | 2321–2323 | M00152 | non-negotiable | false | 10 |
| R01559 | VPOPCNTDQ counts overlap in memory sketches / permission masks | 2324–2325 | M00161 | non-negotiable | false | 10 |
| R01560 | VP2INTERSECT does fast candidate-id intersections on Zen 5, useful for memory/query sets | 2327–2328 | M00158 | non-negotiable | false | 10 |
| R01561 | VPCONFLICT detects duplicates/collisions inside vectorized hash/table updates | 2330–2331 | M00151 | non-negotiable | false | 10 |
| R01562 | VBMI does byte shuffles for token-class LUTs and compact parser tricks | 2333–2334 | M00148 | non-negotiable | false | 10 |
| R01563 | VBMI2 extends VBMI's byte-shuffle palette for parser tricks | 2333–2334 | M00148 | non-negotiable | false | 10 |
| R01564 | k-mask registers act as tiny hardware routing planes for branch validity | 2336–2337 | E0080 | non-negotiable | false | 10 |
| R01565 | VP2INTERSECT support reintroduced on Zen 5 where Intel walked away | 2340 | M00158 | non-negotiable | false | 10 |
| R01566 | Emulation of VP2INTERSECT may beat native if only one mask is needed — benchmark, do not worship | 2340 | M00158 | non-negotiable | true | 10 |
| R01567 | Token Law Engine combines grammar/schema/tool/safety masks over vocab bitsets | 2349–2351 | M00155 | non-negotiable | false | 10 |
| R01568 | Policy Scanner runs Hyperscan-style multi-pattern matching over tool intents and outputs | 2352–2353 | M00156 | non-negotiable | false | 10 |
| R01569 | JSON Commit Validator runs simdjson-style validation before any structured output is accepted | 2355–2356 | M00157 | non-negotiable | false | 10 |
| R01570 | Memory Bitmap Index runs CRoaring-style memory sets | 2358 | M00158 | non-negotiable | false | 10 |
| R01571 | Memory Bitmap Index intersects `project ∩ topic ∩ freshness ∩ trust ∩ permissions` | 2360 | M00158 | non-negotiable | false | 10 |
| R01572 | Branch Compactor uses AVX-512 to compress surviving branches into dense oracle/scout batches | 2362–2363 | M00159 | non-negotiable | false | 10 |
| R01573 | Replay Index is a bitset/searchable trace log for debugging | 2365–2366 | M00160 | non-negotiable | false | 10 |
| R01574 | Replay Index is a bitset/searchable trace log for self-improvement | 2365–2366 | M00160 | non-negotiable | false | 10 |
| R01575 | The CPU transforms language into constrained sets before GPUs reason over it | 2371–2372 | E0078 | non-negotiable | false | 10 |
| R01576 | Memory retrieval uses layered filters instead of immediate embedding search | 2377 | M00153 | non-negotiable | false | 10 |
| R01577 | Layer 1 — deterministic bitset filters (project) | 2380 | M00153 | non-negotiable | false | 10 |
| R01578 | Layer 1 — deterministic bitset filters (file) | 2380 | M00153 | non-negotiable | false | 10 |
| R01579 | Layer 1 — deterministic bitset filters (date) | 2380 | M00153 | non-negotiable | false | 10 |
| R01580 | Layer 1 — deterministic bitset filters (trust) | 2380 | M00153 | non-negotiable | false | 10 |
| R01581 | Layer 1 — deterministic bitset filters (tool) | 2380 | M00153 | non-negotiable | false | 10 |
| R01582 | Layer 1 — deterministic bitset filters (topic) | 2380 | M00153 | non-negotiable | false | 10 |
| R01583 | Layer 2 — sketch overlap `popcount(query_sketch & memory_sketch)` | 2382–2384 | M00161 | non-negotiable | false | 10 |
| R01584 | Layer 3 — 3090 reranker for cheap neural judgment on survivors | 2386–2388 | M00153 | non-negotiable | false | 10 |
| R01585 | Layer 4 — Blackwell oracle only for hard synthesis | 2389–2391 | M00153 | non-negotiable | false | 10 |
| R01586 | Layered-filter cascade saves enormous GPU waste | 2393 | M00153 | non-negotiable | false | 10 |
| R01587 | Memory-item row carries `u64 topic_sketch` | 2398 | M00161 | non-negotiable | false | 10 |
| R01588 | Memory-item row carries `u64 entity_sketch` | 2399 | M00161 | non-negotiable | false | 10 |
| R01589 | Memory-item row carries `u64 tool_sketch` | 2400 | M00161 | non-negotiable | false | 10 |
| R01590 | Memory-item row carries `u64 trust_flags` | 2401 | M00161 | non-negotiable | false | 10 |
| R01591 | Memory-item row carries `u64 freshness` | 2402 | M00161 | non-negotiable | false | 10 |
| R01592 | Memory-item row carries `u64 permissions` | 2403 | M00161 | non-negotiable | false | 10 |
| R01593 | AVX-512 can scan memory-item sketch rows fast | 2405 | M00161 | non-negotiable | false | 10 |
| R01594 | Only survivors of the layered cascade become text | 2406 | M00153 | non-negotiable | false | 10 |
| R01595 | Every tool call passes through deterministic stages | 2410–2411 | M00162 | non-negotiable | false | 10 |
| R01596 | Tool-call stage — parse JSON | 2413 | M00162 | non-negotiable | false | 10 |
| R01597 | Tool-call stage — validate schema | 2414 | M00162 | non-negotiable | false | 10 |
| R01598 | Tool-call stage — scan policy | 2415 | M00162 | non-negotiable | false | 10 |
| R01599 | Tool-call stage — check permission bits | 2416 | M00162 | non-negotiable | false | 10 |
| R01600 | Tool-call stage — check workspace bounds | 2417 | M00162 | non-negotiable | false | 10 |
| R01601 | Tool-call stage — check branch budget | 2418 | M00162 | non-negotiable | false | 10 |
| R01602 | Tool-call stage — classify risk | 2419 | M00162 | non-negotiable | false | 10 |
| R01603 | Tool-call stage — commit or reject | 2420 | M00162 | non-negotiable | false | 10 |
| R01604 | XGrammar generates a binary mask over the vocab so invalid tokens have zero probability after logits masking | 2423 | M00155 | non-negotiable | false | 10 |
| R01605 | LLGuidance reports practical CPU mask computation for large tokenizers | 2423 | M00155 | non-negotiable | false | 10 |
| R01606 | Do mask-based constraint everywhere, not just final JSON | 2425 | E0083 | non-negotiable | false | 10 |
| R01607 | Runtime is closer to a CPU pipeline | 2429 | M00163 | non-negotiable | false | 10 |
| R01608 | CPU-pipeline Fetch stage — user task + memory refs + branch state | 2433–2434 | M00163 | non-negotiable | false | 10 |
| R01609 | CPU-pipeline Decode stage — classify intent + grammar + route + permissions | 2436–2437 | M00163 | non-negotiable | false | 10 |
| R01610 | CPU-pipeline Execute stage — scout GPU drafts + tools prepare + memory retrieves | 2439–2440 | M00163 | non-negotiable | false | 10 |
| R01611 | CPU-pipeline Validate stage — CPU masks + parses + scans + checks | 2442–2443 | M00163 | non-negotiable | false | 10 |
| R01612 | CPU-pipeline Retire stage — Blackwell verifies high-value transitions | 2445–2446 | M00163 | non-negotiable | false | 10 |
| R01613 | CPU-pipeline Commit stage — deterministic log writes accepted state | 2448–2449 | M00163 | non-negotiable | false | 10 |
| R01614 | The 3090 speculates | 2453 | E0085 | non-negotiable | false | 10 |
| R01615 | The RTX PRO 6000 verifies | 2454 | E0085 | non-negotiable | false | 10 |
| R01616 | The AVX-512 CPU retires instructions of thought | 2455 | E0085 | non-negotiable | false | 10 |
| R01617 | Architecture is speculative AI execution with deterministic commit | 2457 | E0085 | non-negotiable | false | 10 |
| R01618 | JSON validator backend operator-overrideable (simdjson \| serde_json \| jq) | 2273, 2285 | F00766 | non-negotiable | true | 10 |
| R01619 | Regex backend operator-overrideable (Hyperscan \| RE2 \| `regex` crate) | 2274, 2285 | F00775 | non-negotiable | true | 10 |
| R01620 | Memory-bitmap backend operator-overrideable (CRoaring \| `roaring` crate \| FixedBitSet) | 2275, 2285 | F00784 | non-negotiable | true | 10 |
| R01621 | Duplicate-detect backend operator-overrideable (vpconflict \| scalar) | 2330–2331 | F00801 | non-negotiable | true | 10 |
| R01622 | Branch-compactor backend operator-overrideable (vpcompress \| scalar) | 2321–2323 | F00810 | non-negotiable | true | 10 |
| R01623 | Token-law mask layers operator-configurable (csv: grammar,schema,tool,safety,...) | 2349–2351 | F00793 | non-negotiable | true | 10 |
| R01624 | Bitset-filter axes operator-configurable (csv: project,file,date,trust,tool,topic,...) | 2378–2380 | F00816 | non-negotiable | true | 10 |
| R01625 | CPU-pipeline retire threshold operator-tunable (when Blackwell engaged) | 2445–2446 | F00845 | non-negotiable | true | 10 |
| R01626 | Speculative-execution organ-binding can be overridden by operator (e.g. dry-run 3090-only mode) | 2453–2455 | E0085 | preferable | true | 10 |
| R01627 | Dashboard — JSON validator throughput (GB/sec) | 2285 | F00770 | non-negotiable | true | 10 |
| R01628 | Dashboard — regex match-rate + active-patterns count | 2274 | F00779 | non-negotiable | true | 10 |
| R01629 | Dashboard — bitmap density + AND/OR/XOR throughput | 2275 | F00788 | non-negotiable | true | 10 |
| R01630 | Dashboard — token-law mask coverage heatmap | 2349–2351 | F00796 | non-negotiable | true | 10 |
| R01631 | Dashboard — duplicate-detection collisions per second | 2330–2331 | F00805 | non-negotiable | true | 10 |
| R01632 | Dashboard — branch survival ratio per tick | 2321–2323, 2362–2363 | F00812 | non-negotiable | true | 10 |
| R01633 | Dashboard — tool-call stage drop-off histogram | 2412–2421 | F00836 | non-negotiable | true | 10 |
| R01634 | Dashboard — CPU-pipeline 6-row gantt per request | 2431–2449 | F00844 | non-negotiable | true | 10 |
| R01635 | API `GET /v1/data-plane/json/throughput` | 2273 | F00771 | non-negotiable | true | 10 |
| R01636 | API `POST /v1/data-plane/regex/compile` | 2274 | F00780 | non-negotiable | true | 10 |
| R01637 | API `POST /v1/data-plane/regex/scan` | 2274 | F00781 | non-negotiable | true | 10 |
| R01638 | API `GET /v1/data-plane/memory-bitmap/stats` | 2275 | F00789 | non-negotiable | true | 10 |
| R01639 | API `POST /v1/data-plane/token-law/fuse` | 2349–2351 | F00797 | non-negotiable | true | 10 |
| R01640 | Metric `sovereign_data_plane_json_bytes_validated_total` | 2273 | F00772 | non-negotiable | true | 10 |
| R01641 | Metric `sovereign_data_plane_regex_bytes_scanned_total` | 2274 | F00782 | non-negotiable | true | 10 |
| R01642 | Metric `sovereign_data_plane_bitmap_set_ops_total{op}` | 2275 | F00790 | non-negotiable | true | 10 |
| R01643 | Metric `sovereign_data_plane_token_law_mask_layers` | 2349–2351 | F00798 | non-negotiable | true | 10 |
| R01644 | Metric `sovereign_data_plane_duplicate_collisions_total` | 2330–2331 | F00806 | non-negotiable | true | 10 |
| R01645 | Metric `sovereign_data_plane_branch_compact_in_lanes` | 2321–2323 | F00813 | non-negotiable | true | 10 |
| R01646 | Metric `sovereign_data_plane_branch_compact_out_lanes` | 2321–2323 | F00814 | non-negotiable | true | 10 |
| R01647 | Metric `sovereign_tool_call_stage_reject_total{stage}` | 2412–2421 | F00837 | non-negotiable | true | 10 |
| R01648 | Metric `sovereign_cpu_pipeline_stage_latency_us{stage}` | 2431–2449 | F00847 | non-negotiable | true | 10 |
| R01649 | Env var `SOVEREIGN_JSON_VALIDATOR_BACKEND` | 2273 | F00768 | non-negotiable | true | 10 |
| R01650 | Env var `SOVEREIGN_REGEX_BACKEND` | 2274 | F00777 | non-negotiable | true | 10 |
| R01651 | Env var `SOVEREIGN_MEMORY_BITMAP_BACKEND` | 2275 | F00786 | non-negotiable | true | 10 |
| R01652 | Env var `SOVEREIGN_TOKEN_LAW_MASK_LAYERS` | 2349–2351 | F00794 | non-negotiable | true | 10 |
| R01653 | Env var `SOVEREIGN_DUPLICATE_DETECT_BACKEND` | 2330–2331 | F00803 | non-negotiable | true | 10 |
| R01654 | Env var `SOVEREIGN_BRANCH_COMPACTOR_BACKEND` | 2321–2323 | F00811 | non-negotiable | true | 10 |
| R01655 | Env var `SOVEREIGN_BITSET_FILTER_AXES` | 2378–2380 | F00817 | non-negotiable | true | 10 |
| R01656 | Env var `SOVEREIGN_CPU_PIPELINE_RETIRE_THRESHOLD` | 2445–2446 | F00846 | non-negotiable | true | 10 |
| R01657 | CLI `--json-validator <backend>` | 2273 | F00769 | non-negotiable | true | 10 |
| R01658 | CLI `--regex-backend <name>` | 2274 | F00778 | non-negotiable | true | 10 |
| R01659 | CLI `--memory-bitmap-backend <name>` | 2275 | F00787 | non-negotiable | true | 10 |
| R01660 | CLI `--token-law-mask-layers <csv>` | 2349–2351 | F00795 | non-negotiable | true | 10 |
| R01661 | CLI `--duplicate-detect <backend>` | 2330–2331 | F00804 | non-negotiable | true | 10 |
| R01662 | CLI `--bitset-filter-axes <csv>` | 2378–2380 | F00818 | non-negotiable | true | 10 |
| R01663 | Test — simdjson AVX-512 path enables on Zen 5 | 2285 | F00773 | non-negotiable | false | 10 |
| R01664 | Test — simdjson throughput ≥ 1 GB/sec on Zen 5 path | 2285 | F00774 | preferable | false | 10 |
| R01665 | Test — Hyperscan AVX-512 path enables on Zen 5 + falls back on Zen 4 | 2285 | F00783 | non-negotiable | false | 10 |
| R01666 | Test — CRoaring 5-set intersection on memory rows | 2358–2360 | F00791 | non-negotiable | false | 10 |
| R01667 | Test — XGrammar mask compatibility | 2423 | F00799 | non-negotiable | false | 10 |
| R01668 | Test — LLGuidance mask compatibility | 2423 | F00800 | non-negotiable | false | 10 |
| R01669 | Test — VPCONFLICT correctness on full-collision + no-collision + partial inputs | 2330–2331 | F00807 | non-negotiable | false | 10 |
| R01670 | Test — VPCOMPRESS round-trip with VPEXPAND restores original lane assignment | 2321–2323 | F00808 | non-negotiable | false | 10 |
| R01671 | Test — VP2INTERSECT correctness vs scalar reference on random + corner-case inputs | 2327–2328 | M00158 | non-negotiable | false | 10 |
| R01672 | Test — VPTERNLOG fusion `commit = verified & valid \| trusted_fast_path` matches scalar | 2317–2319 | M00155 | non-negotiable | false | 10 |
| R01673 | Test — VPOPCNTDQ popcount correctness vs `u64::count_ones()` reference | 2324–2325 | M00161 | non-negotiable | false | 10 |
| R01674 | Test — VBMI byte-shuffle correctness vs scalar reference | 2333–2334 | M00148 | non-negotiable | false | 10 |
| R01675 | Test — k-mask register branch validity round-trip | 2336–2337 | E0080 | non-negotiable | false | 10 |
| R01676 | Test — layered filter cascade order is bitset → sketch → 3090 → Blackwell | 2378–2391 | M00153 | non-negotiable | false | 10 |
| R01677 | Test — memory-item six-sketch row layout fits in single 64-byte cache line | 2398–2403 | M00161 | preferable | false | 10 |
| R01678 | Test — tool-call 8-stage pipeline rejects at correct stage for each failure type | 2412–2421 | M00162 | non-negotiable | false | 10 |
| R01679 | Test — CPU-pipeline 6-stage runtime sequences stages in order on every request | 2431–2449 | M00163 | non-negotiable | false | 10 |
| R01680 | Test — control plane functions simultaneously as vector DB + parser + policy + grammar + scheduler | 2310 | E0079 | non-negotiable | false | 10 |
| R01681 | Test — `popcount(query_sketch & memory_sketch)` sketch-overlap scorer monotonic in true overlap | 2382–2384 | M00161 | non-negotiable | false | 10 |
| R01682 | Test — bitset-filter cascade rejects at first failing axis (project before file before date ...) | 2378–2380 | M00153 | non-negotiable | false | 10 |
| R01683 | Test — branch compactor compresses K alive branches into ceil(K/8) ZMM registers | 2321–2323, 2362–2363 | M00159 | non-negotiable | false | 10 |
| R01684 | Test — replay index search returns committed-states only (no rejected branches) | 2365–2366 | M00160 | non-negotiable | false | 10 |
| R01685 | Test — replay index search supports forward + backward seek by trace-id | 2365–2366 | M00160 | non-negotiable | false | 10 |
| R01686 | Test — replay index search supports filtering by branch-id + tool-id + risk-class | 2365–2366 | M00160 | non-negotiable | false | 10 |
| R01687 | Test — JSON commit validator rejects every non-conformant tool-call before any side effect | 2355–2356 | M00157 | non-negotiable | false | 10 |
| R01688 | Test — Policy Scanner Hyperscan multi-pattern match on tool intent corpus | 2352–2353 | M00156 | non-negotiable | false | 10 |
| R01689 | Test — Policy Scanner Hyperscan multi-pattern match on tool output corpus | 2352–2353 | M00156 | non-negotiable | false | 10 |
| R01690 | Test — speculative-organ binding (3090 speculates, RTX PRO verifies, Ryzen retires) enforced by API | 2453–2455 | E0085 | non-negotiable | false | 10 |
| R01691 | Mode `simdjson-disable` falls back to serde_json | 2273, 2285 | F00766 | non-negotiable | true | 10 |
| R01692 | Mode `hyperscan-disable` falls back to RE2 / `regex` crate | 2274, 2285 | F00775 | non-negotiable | true | 10 |
| R01693 | Mode `croaring-disable` falls back to `roaring` Rust crate | 2275, 2285 | F00784 | non-negotiable | true | 10 |
| R01694 | Mode `vpconflict-disable` falls back to scalar duplicate detection | 2330–2331 | F00801 | non-negotiable | true | 10 |
| R01695 | Mode `vpcompress-disable` falls back to scalar pack loop for branch compaction | 2321–2323 | F00810 | non-negotiable | true | 10 |
| R01696 | Mode `vp2intersect-disable` falls back to scalar set-intersection | 2327–2328 | M00158 | non-negotiable | true | 10 |
| R01697 | Mode `vbmi-disable` falls back to scalar byte shuffle | 2333–2334 | M00148 | non-negotiable | true | 10 |
| R01698 | Composite F00848 — six data-plane services compose into ONE runtime data-plane crate | 2344–2367 | F00848 | non-negotiable | false | 10 |
| R01699 | Composite F00849 — speculative AI execution with deterministic commit law enforced by API | 2451–2457 | F00849 | non-negotiable | false | 10 |
| R01700 | Composite F00850 — `The CPU should transform language into constrained sets before GPUs reason over it` runtime invariant | 2371–2372 | F00850 | non-negotiable | false | 10 |

— End of M010 milestone file.
