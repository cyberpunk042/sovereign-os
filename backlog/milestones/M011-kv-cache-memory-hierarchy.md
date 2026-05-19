# M011 — KV cache as memory hierarchy

> Parent: `backlog/milestones/INDEX.md` row M011 (dump 2459–2728).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 2459–2728.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0087–E0095)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0087 | KV cache as memory hierarchy — new thesis | 2477–2497 |
| E0088 | The CPU As KV Cache Controller | 2499–2541 |
| E0089 | The Killer Optimization — Tool Schema KV | 2543–2572 |
| E0090 | Speculation Becomes Tree Execution — 3090 drafts / CPU packs / Blackwell verifies / CPU commits | 2574–2610 |
| E0091 | Branch + KV Cache Fusion — every branch carries its KV refs | 2612–2646 |
| E0092 | Memory Admission Policy — cache-yes / cache-no bitfield law | 2648–2680 |
| E0093 | Strong Runtime Shape — Deterministic Cortex Runtime + KV plane | 2682–2699 |
| E0094 | Golden Rule — four never-statements for the cortex memory hierarchy | 2701–2710 |
| E0095 | Sovereign workstation as local AI operating system — content-addressing / prefix-sharing / speculative trees / AVX-512 branch compaction / KV cache tiering / deterministic commit | 2712–2727 |

## Modules (M00164–M00180)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00164 | VRAM KV cache = L1/L2 cache | 2491 | E0087 |
| M00165 | System RAM = L3 / page cache | 2492 | E0087 |
| M00166 | NVMe ZFS = cold cache / replay / persisted context | 2493 | E0087 |
| M00167 | CPU AVX-512 = cache controller | 2494 | E0087 |
| M00168 | KV cache controller — which prefixes deserve hot / shared / prefetch / offload / evict / permanent | 2503–2511 | E0088 |
| M00169 | `KvBlockMeta` 64-byte SoA row — hash_hi / hash_lo / model_id / token_range / trust_flags / heat / last_used / owner_policy | 2517–2528 | E0088 |
| M00170 | SIMD scan questions over KvBlockMeta — same model / tokenizer / block-hash / allowed-for-session / hot-enough / stale-enough | 2530–2540 | E0088 |
| M00171 | Tool schema KV — system / tool / project / repo / user / grammar prefill caches | 2549–2556 | E0089 |
| M00172 | Cached-invariant-prefix + live-delta request shape | 2560–2562 | E0089 |
| M00173 | Content-addressing — `hash(model_id, tokenizer_id, prompt_bytes, schema_version)` | 2568–2572 | E0089 |
| M00174 | Speculative-tree organ pipeline — 3090 creates / CPU packs / Blackwell verifies / CPU commits | 2580–2585 | E0090 |
| M00175 | `TokenNode` compact tree row — token / parent / depth / child_mask / score / flags | 2589–2598 | E0090 |
| M00176 | AVX-512 tree maintenance — filter / merge / dedup / pack-verification-batches / track-accepted-subtree | 2600–2608 | E0090 |
| M00177 | Branch row carries KV refs — branch_id / parent_branch_id / kv_prefix_ref / kv_delta_ref / control_word / budget / score | 2618–2626 | E0091 |
| M00178 | Branch fork shares prefix KV; only delta changes | 2628–2642 | E0091 |
| M00179 | Memory-admission policy bitfield — cache-tier / trust / reuse-count / token-cost / owner-session / flags | 2673–2680 | E0092 |
| M00180 | Deterministic Cortex Runtime — Branch / Policy / Grammar / Memory-Router / Speculation / Tool-Gate / Replay-Log / KV-Cache-Controller | 2687–2697 | E0093 |

## Features (F00851–F00935)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00851 | Toggle KV-cache-controller backend (rust-native / vLLM-APC-compat / LMCache-bridge / Dynamo-bridge / SGLang-RadixAttention-compat) | 2483–2486 | M00168 | mode | true |
| F00852 | Profile knob — `kv_cache_controller = native \| vllm_apc \| lmcache \| dynamo \| sglang_radix` | 2483–2486 | M00168 | profile | true |
| F00853 | Env var `SOVEREIGN_KV_CACHE_CONTROLLER_BACKEND` | 2483–2486 | M00168 | env_var | true |
| F00854 | CLI `--kv-cache-controller <backend>` | 2483–2486 | M00168 | cli_verb | true |
| F00855 | Dashboard surface — KV hierarchy tier occupancy (VRAM/RAM/NVMe) | 2491–2494 | M00167 | dashboard | true |
| F00856 | Dashboard surface — KV block hit-rate per tier | 2491–2494 | M00167 | dashboard | true |
| F00857 | API `GET /v1/kv-cache/tiers` (returns per-tier capacity + occupancy) | 2491–2494 | M00167 | api_endpoint | true |
| F00858 | API `GET /v1/kv-cache/block/{hash}` | 2517–2528 | M00169 | api_endpoint | true |
| F00859 | API `POST /v1/kv-cache/scan` (returns SIMD-scan answers) | 2530–2540 | M00170 | api_endpoint | true |
| F00860 | Metric `sovereign_kv_block_count{tier}` | 2491–2494 | M00167 | observability_metric | true |
| F00861 | Metric `sovereign_kv_block_bytes{tier}` | 2491–2494 | M00167 | observability_metric | true |
| F00862 | Metric `sovereign_kv_block_hit_total{tier}` | 2503–2511 | M00168 | observability_metric | true |
| F00863 | Metric `sovereign_kv_block_evict_total{tier}` | 2503–2511 | M00168 | observability_metric | true |
| F00864 | Metric `sovereign_kv_block_offload_total{from,to}` | 2503–2511 | M00168 | observability_metric | true |
| F00865 | Test — KvBlockMeta layout fits in one 64-byte cache line | 2517–2528 | M00169 | test | false |
| F00866 | Test — SIMD scan `same_model` matches scalar reference | 2533 | M00170 | test | false |
| F00867 | Test — SIMD scan `same_tokenizer` matches scalar reference | 2534 | M00170 | test | false |
| F00868 | Test — SIMD scan `same_block_hash` matches scalar reference | 2535 | M00170 | test | false |
| F00869 | Test — SIMD scan `allowed_for_session` honors session permission bits | 2536 | M00170 | test | false |
| F00870 | Test — SIMD scan `hot_enough` matches policy threshold | 2537 | M00170 | test | false |
| F00871 | Test — SIMD scan `stale_enough` matches policy threshold | 2538 | M00170 | test | false |
| F00872 | Tool-schema-KV cache — system prompt prefill | 2550 | M00171 | composite | true |
| F00873 | Tool-schema-KV cache — tool schema prefill | 2551 | M00171 | composite | true |
| F00874 | Tool-schema-KV cache — project policy prefill | 2552 | M00171 | composite | true |
| F00875 | Tool-schema-KV cache — repo summary prefill | 2553 | M00171 | composite | true |
| F00876 | Tool-schema-KV cache — user preference prefill | 2554 | M00171 | composite | true |
| F00877 | Tool-schema-KV cache — grammar/task template prefill | 2555 | M00171 | composite | true |
| F00878 | Profile knob — `tool_schema_kv_prefill = system,tool,project,repo,user,grammar` | 2549–2556 | M00171 | profile | true |
| F00879 | Env var `SOVEREIGN_TOOL_SCHEMA_KV_PREFILL` | 2549–2556 | M00171 | env_var | true |
| F00880 | CLI `--tool-schema-kv-prefill <csv>` | 2549–2556 | M00171 | cli_verb | true |
| F00881 | Dashboard surface — TTFT reduction from tool-schema-KV prefill (before vs after) | 2560–2564 | M00172 | dashboard | true |
| F00882 | Metric `sovereign_kv_prefill_reuse_total{kind}` | 2549–2556 | M00171 | observability_metric | true |
| F00883 | Content-addressing hash function — `hash(model_id, tokenizer_id, prompt_bytes, schema_version)` | 2568–2572 | M00173 | composite | false |
| F00884 | API `POST /v1/kv-cache/content-address` (returns content hash) | 2568–2572 | M00173 | api_endpoint | true |
| F00885 | Test — content-addressing collision rate ≤ scalar reference | 2568–2572 | M00173 | test | false |
| F00886 | Test — content-addressing is deterministic across runs + boots | 2568–2572 | M00173 | test | false |
| F00887 | Speculative-tree pipeline — 3090 creates tree | 2581 | M00174 | composite | true |
| F00888 | Speculative-tree pipeline — CPU stores tree as bit-packed branch records | 2582 | M00174 | composite | true |
| F00889 | Speculative-tree pipeline — Blackwell verifies tree chunks | 2583 | M00174 | composite | true |
| F00890 | Speculative-tree pipeline — CPU commits accepted path | 2584 | M00174 | composite | true |
| F00891 | Profile knob — `speculative_tree_draft_organ = 3090 \| cpu_simulated \| disabled` | 2580–2585 | M00174 | profile | true |
| F00892 | Env var `SOVEREIGN_SPEC_TREE_DRAFT_ORGAN` | 2580–2585 | M00174 | env_var | true |
| F00893 | CLI `--spec-tree-draft-organ <name>` | 2580–2585 | M00174 | cli_verb | true |
| F00894 | Dashboard surface — speculative-tree depth × width × acceptance-rate | 2580–2608 | M00176 | dashboard | true |
| F00895 | Compatibility — SpecInfer-style speculative token trees verified in parallel | 2576 | M00174 | mode | true |
| F00896 | Compatibility — Medusa-style multiple decoding heads predicting future tokens in parallel | 2576 | M00174 | mode | true |
| F00897 | Compatibility — EAGLE-style speculative family with lossless generation claim | 2576 | M00174 | mode | true |
| F00898 | Test — TokenNode layout fits in expected 16-byte row | 2589–2598 | M00175 | test | false |
| F00899 | Test — AVX-512 tree filter removes invalid nodes vs scalar reference | 2603 | M00176 | test | false |
| F00900 | Test — AVX-512 tree merge identical prefixes vs scalar reference | 2604 | M00176 | test | false |
| F00901 | Test — AVX-512 tree dedup token paths vs scalar reference | 2605 | M00176 | test | false |
| F00902 | Test — AVX-512 tree pack verification batches matches batch-size policy | 2606 | M00176 | test | false |
| F00903 | Test — AVX-512 tree track accepted-subtree maintains parent invariant | 2607 | M00176 | test | false |
| F00904 | Test — "branch-predicted cognition" — speculative tree accept-rate > 0 in steady state | 2610 | M00176 | test | false |
| F00905 | Branch row carries `kv_prefix_ref` | 2621 | M00177 | data_model | false |
| F00906 | Branch row carries `kv_delta_ref` | 2622 | M00177 | data_model | false |
| F00907 | Branch fork shares prefix KV (CoW semantics; only delta changes) | 2628 | M00178 | composite | false |
| F00908 | Root KV = system + tools + project | 2631–2632 | M00178 | composite | false |
| F00909 | Branch A KV = root + plan A | 2634–2635 | M00178 | composite | false |
| F00910 | Branch B KV = root + plan B | 2637–2638 | M00178 | composite | false |
| F00911 | Branch C KV = root + retrieved docs + plan C | 2640–2641 | M00178 | composite | false |
| F00912 | CPU detects prefix sharing with hashes + bitsets before asking the GPU | 2644 | M00178 | composite | false |
| F00913 | Dashboard surface — branch-tree KV-share heatmap | 2628–2646 | M00178 | dashboard | true |
| F00914 | Metric `sovereign_branch_kv_prefix_share_ratio` | 2644 | M00178 | observability_metric | true |
| F00915 | Memory-admission rule — Cache if reused often | 2656 | M00179 | composite | true |
| F00916 | Memory-admission rule — Cache if expensive to prefill | 2657 | M00179 | composite | true |
| F00917 | Memory-admission rule — Cache if stable content | 2658 | M00179 | composite | true |
| F00918 | Memory-admission rule — Cache if high trust | 2659 | M00179 | composite | true |
| F00919 | Memory-admission rule — Cache if common across branches | 2660 | M00179 | composite | true |
| F00920 | Memory-admission rule — Cache if part of tool/system/project base | 2661 | M00179 | composite | true |
| F00921 | Memory-admission rule — Do NOT cache if one-off | 2664 | M00179 | composite | true |
| F00922 | Memory-admission rule — Do NOT cache if low trust | 2665 | M00179 | composite | true |
| F00923 | Memory-admission rule — Do NOT cache if user-private but cross-session forbidden | 2666 | M00179 | composite | true |
| F00924 | Memory-admission rule — Do NOT cache if likely to mutate | 2667 | M00179 | composite | true |
| F00925 | Memory-admission rule — Do NOT cache if branch-specific noise | 2668 | M00179 | composite | true |
| F00926 | Admission policy is a bitfield, not a prompt | 2671 | M00179 | mode | false |
| F00927 | Dashboard surface — admission decisions per minute (cache-yes / cache-no histogram) | 2648–2680 | M00179 | dashboard | true |
| F00928 | Profile knob — `memory_admission_policy_bits` (operator-tunable bitfield layout) | 2673–2680 | M00179 | profile | true |
| F00929 | Env var `SOVEREIGN_MEMORY_ADMISSION_POLICY_BITS` | 2673–2680 | M00179 | env_var | true |
| F00930 | Deterministic Cortex Runtime adds KV Cache Controller as 8th sub-plane | 2687–2697 | M00180 | composite | false |
| F00931 | Dashboard surface — Deterministic Cortex Runtime 8-plane overview | 2687–2697 | M00180 | dashboard | true |
| F00932 | Composite F00932 — Golden Rule #1 enforcement: never recompute stable context if content-addressed | 2704 | E0094 | composite | false |
| F00933 | Composite F00933 — Golden Rule #2 enforcement: never verify a branch that violates deterministic law | 2705 | E0094 | composite | false |
| F00934 | Composite F00934 — Golden Rule #3 enforcement: never keep KV hot just because it exists | 2706 | E0094 | composite | false |
| F00935 | Composite F00935 — Golden Rule #4 enforcement: never let the expensive GPU wait for context assembly | 2707 | E0094 | composite | false |

## Requirements (R01701–R01870)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R01701 | KV cache is the next major piece, not the model | 2477–2479 | E0087 | non-negotiable | false | 10 |
| R01702 | In long-context local AI, KV cache becomes the real working memory | 2481 | E0087 | non-negotiable | false | 10 |
| R01703 | vLLM Automatic Prefix Caching hashes KV blocks so prefix-sharing requests reuse memory/compute | 2483 | M00168 | non-negotiable | false | 10 |
| R01704 | LMCache pushes "prefill once, reuse everywhere" beyond simple prefix matching | 2484 | M00168 | non-negotiable | false | 10 |
| R01705 | LMCache stores KV across CPU RAM, disk, Redis, GDS, etc. | 2484 | M00168 | non-negotiable | false | 10 |
| R01706 | NVIDIA Dynamo supports KV cache offloading beyond GPU memory using CPU RAM and disk backends | 2485 | M00168 | non-negotiable | false | 10 |
| R01707 | SGLang RadixAttention provides efficient KV cache reuse for generation programs with loops and conditionals | 2486 | M00168 | non-negotiable | false | 10 |
| R01708 | VRAM KV cache = L1/L2 cache | 2491 | M00164 | non-negotiable | false | 10 |
| R01709 | System RAM = L3 / page cache | 2492 | M00165 | non-negotiable | false | 10 |
| R01710 | NVMe ZFS = cold cache / replay / persisted context | 2493 | M00166 | non-negotiable | false | 10 |
| R01711 | CPU AVX-512 = cache controller | 2494 | M00167 | non-negotiable | false | 10 |
| R01712 | The Blackwell card has 96 GB VRAM | 2501 | M00164 | non-negotiable | false | 10 |
| R01713 | Long-context + branches + tools + parallel agents can eat the 96 GB | 2501 | M00168 | non-negotiable | false | 10 |
| R01714 | The CPU decides which prefixes deserve hot KV | 2504 | M00168 | non-negotiable | false | 10 |
| R01715 | The CPU decides which branches share prefixes | 2505 | M00168 | non-negotiable | false | 10 |
| R01716 | The CPU decides which contexts should be prefetched | 2506 | M00168 | non-negotiable | false | 10 |
| R01717 | The CPU decides which KV blocks should be offloaded | 2507 | M00168 | non-negotiable | false | 10 |
| R01718 | The CPU decides which blocks should be evicted | 2508 | M00168 | non-negotiable | false | 10 |
| R01719 | The CPU decides which repeated tool schemas get permanent cache | 2509 | M00168 | non-negotiable | false | 10 |
| R01720 | The CPU decides which project docs are worth prefill-once reuse | 2510 | M00168 | non-negotiable | false | 10 |
| R01721 | KV admission is deterministic policy work, perfect for the AVX-512 control plane | 2513 | M00168 | non-negotiable | false | 10 |
| R01722 | KvBlockMeta carries `hash_hi` (u64) | 2519 | M00169 | non-negotiable | false | 10 |
| R01723 | KvBlockMeta carries `hash_lo` (u64) | 2520 | M00169 | non-negotiable | false | 10 |
| R01724 | KvBlockMeta carries `model_id` (u64) | 2521 | M00169 | non-negotiable | false | 10 |
| R01725 | KvBlockMeta carries `token_range` (u64) | 2522 | M00169 | non-negotiable | false | 10 |
| R01726 | KvBlockMeta carries `trust_flags` (u64) | 2523 | M00169 | non-negotiable | false | 10 |
| R01727 | KvBlockMeta carries `heat` (u64) | 2524 | M00169 | non-negotiable | false | 10 |
| R01728 | KvBlockMeta carries `last_used` (u64) | 2525 | M00169 | non-negotiable | false | 10 |
| R01729 | KvBlockMeta carries `owner_policy` (u64) | 2526 | M00169 | non-negotiable | false | 10 |
| R01730 | KvBlockMeta is 64 bytes (8 × u64) — fits in one cache line | 2517–2528 | M00169 | non-negotiable | false | 10 |
| R01731 | SIMD scan answers "same model?" | 2533 | M00170 | non-negotiable | false | 10 |
| R01732 | SIMD scan answers "same tokenizer?" | 2534 | M00170 | non-negotiable | false | 10 |
| R01733 | SIMD scan answers "same block hash?" | 2535 | M00170 | non-negotiable | false | 10 |
| R01734 | SIMD scan answers "allowed for this session?" | 2536 | M00170 | non-negotiable | false | 10 |
| R01735 | SIMD scan answers "hot enough to keep?" | 2537 | M00170 | non-negotiable | false | 10 |
| R01736 | SIMD scan answers "stale enough to evict?" | 2538 | M00170 | non-negotiable | false | 10 |
| R01737 | Do not ask the model — let the CPU govern memory | 2541 | M00168 | non-negotiable | false | 10 |
| R01738 | Tool schemas are repeated constantly and must be prefill-cached | 2545–2547 | M00171 | non-negotiable | false | 10 |
| R01739 | System prompts are repeated constantly and must be prefill-cached | 2545–2547 | M00171 | non-negotiable | false | 10 |
| R01740 | Repo instructions are repeated constantly and must be prefill-cached | 2545–2547 | M00171 | non-negotiable | false | 10 |
| R01741 | Coding policy is repeated constantly and must be prefill-cached | 2545–2547 | M00171 | non-negotiable | false | 10 |
| R01742 | JSON schemas are repeated constantly and must be prefill-cached | 2545–2547 | M00171 | non-negotiable | false | 10 |
| R01743 | Grammar descriptions are repeated constantly and must be prefill-cached | 2545–2547 | M00171 | non-negotiable | false | 10 |
| R01744 | System prompt KV prefill | 2550 | M00171 | non-negotiable | false | 10 |
| R01745 | Tool schema KV prefill | 2551 | M00171 | non-negotiable | false | 10 |
| R01746 | Project policy KV prefill | 2552 | M00171 | non-negotiable | false | 10 |
| R01747 | Repo summary KV prefill | 2553 | M00171 | non-negotiable | false | 10 |
| R01748 | User preference KV prefill | 2554 | M00171 | non-negotiable | false | 10 |
| R01749 | Grammar/task template KV prefill | 2555 | M00171 | non-negotiable | false | 10 |
| R01750 | Requests become "cached invariant prefix + small live delta" | 2561 | M00172 | non-negotiable | false | 10 |
| R01751 | This crushes TTFT because the big model does not repeatedly re-read boilerplate | 2564 | M00172 | non-negotiable | false | 10 |
| R01752 | Deterministic hashing matters for content-addressing | 2566 | M00173 | non-negotiable | false | 10 |
| R01753 | Hash key includes `model_id` | 2569 | M00173 | non-negotiable | false | 10 |
| R01754 | Hash key includes `tokenizer_id` | 2569 | M00173 | non-negotiable | false | 10 |
| R01755 | Hash key includes `prompt_bytes` | 2569 | M00173 | non-negotiable | false | 10 |
| R01756 | Hash key includes `schema_version` | 2569 | M00173 | non-negotiable | false | 10 |
| R01757 | If identical hash, reuse; if not, recompute | 2572 | M00173 | non-negotiable | false | 10 |
| R01758 | SpecInfer speculative token trees are verified in parallel by the large model | 2576 | M00174 | non-negotiable | false | 10 |
| R01759 | Medusa adds multiple decoding heads to predict future tokens in parallel | 2576 | M00174 | non-negotiable | false | 10 |
| R01760 | EAGLE speculative family claims lossless generation relative to vanilla decoding | 2576 | M00174 | non-negotiable | false | 10 |
| R01761 | Hardware version — 3090 creates speculative tree | 2581 | M00174 | non-negotiable | false | 10 |
| R01762 | Hardware version — CPU stores tree as bit-packed branch records | 2582 | M00174 | non-negotiable | false | 10 |
| R01763 | Hardware version — Blackwell verifies tree chunks | 2583 | M00174 | non-negotiable | false | 10 |
| R01764 | Hardware version — CPU commits accepted path | 2584 | M00174 | non-negotiable | false | 10 |
| R01765 | TokenNode row carries `token` (u32) | 2591 | M00175 | non-negotiable | false | 10 |
| R01766 | TokenNode row carries `parent` (u32) | 2592 | M00175 | non-negotiable | false | 10 |
| R01767 | TokenNode row carries `depth` (u16) | 2593 | M00175 | non-negotiable | false | 10 |
| R01768 | TokenNode row carries `child_mask` (u16) | 2594 | M00175 | non-negotiable | false | 10 |
| R01769 | TokenNode row carries `score` (u16) | 2595 | M00175 | non-negotiable | false | 10 |
| R01770 | TokenNode row carries `flags` (u16) | 2596 | M00175 | non-negotiable | false | 10 |
| R01771 | TokenNode is 16 bytes (compact tree node) | 2589–2598 | M00175 | non-negotiable | false | 10 |
| R01772 | AVX-512 filters invalid nodes | 2603 | M00176 | non-negotiable | false | 10 |
| R01773 | AVX-512 merges identical prefixes | 2604 | M00176 | non-negotiable | false | 10 |
| R01774 | AVX-512 deduplicates token paths | 2605 | M00176 | non-negotiable | false | 10 |
| R01775 | AVX-512 packs verification batches | 2606 | M00176 | non-negotiable | false | 10 |
| R01776 | AVX-512 tracks accepted subtree | 2607 | M00176 | non-negotiable | false | 10 |
| R01777 | Architecture realises branch-predicted cognition | 2610 | M00176 | non-negotiable | false | 10 |
| R01778 | Every branch knows which KV blocks it owns or shares | 2616 | M00177 | non-negotiable | false | 10 |
| R01779 | Branch row carries `branch_id` | 2619 | M00177 | non-negotiable | false | 10 |
| R01780 | Branch row carries `parent_branch_id` | 2620 | M00177 | non-negotiable | false | 10 |
| R01781 | Branch row carries `kv_prefix_ref` | 2621 | M00177 | non-negotiable | false | 10 |
| R01782 | Branch row carries `kv_delta_ref` | 2622 | M00177 | non-negotiable | false | 10 |
| R01783 | Branch row carries `control_word` | 2623 | M00177 | non-negotiable | false | 10 |
| R01784 | Branch row carries `budget` | 2624 | M00177 | non-negotiable | false | 10 |
| R01785 | Branch row carries `score` | 2625 | M00177 | non-negotiable | false | 10 |
| R01786 | Branch fork shares prefix KV | 2628 | M00178 | non-negotiable | false | 10 |
| R01787 | Only the delta changes on branch fork | 2628 | M00178 | non-negotiable | false | 10 |
| R01788 | Root KV = system + tools + project | 2631–2632 | M00178 | non-negotiable | false | 10 |
| R01789 | Branch A KV = root + plan A | 2634–2635 | M00178 | non-negotiable | false | 10 |
| R01790 | Branch B KV = root + plan B | 2637–2638 | M00178 | non-negotiable | false | 10 |
| R01791 | Branch C KV = root + retrieved docs + plan C | 2640–2641 | M00178 | non-negotiable | false | 10 |
| R01792 | CPU detects prefix sharing with hashes and bitsets before asking the GPU | 2644 | M00178 | non-negotiable | false | 10 |
| R01793 | Many branches, shared context, deterministic commit is a local AI workstation superpower | 2646 | E0091 | non-negotiable | false | 10 |
| R01794 | Not everything deserves KV | 2650 | M00179 | non-negotiable | false | 10 |
| R01795 | Cache if reused often | 2656 | M00179 | non-negotiable | false | 10 |
| R01796 | Cache if expensive to prefill | 2657 | M00179 | non-negotiable | false | 10 |
| R01797 | Cache if stable content | 2658 | M00179 | non-negotiable | false | 10 |
| R01798 | Cache if high trust | 2659 | M00179 | non-negotiable | false | 10 |
| R01799 | Cache if common across branches | 2660 | M00179 | non-negotiable | false | 10 |
| R01800 | Cache if part of tool/system/project base | 2661 | M00179 | non-negotiable | false | 10 |
| R01801 | Do not cache if one-off | 2664 | M00179 | non-negotiable | false | 10 |
| R01802 | Do not cache if low trust | 2665 | M00179 | non-negotiable | false | 10 |
| R01803 | Do not cache if user-private but cross-session forbidden | 2666 | M00179 | non-negotiable | false | 10 |
| R01804 | Do not cache if likely to mutate | 2667 | M00179 | non-negotiable | false | 10 |
| R01805 | Do not cache if branch-specific noise | 2668 | M00179 | non-negotiable | false | 10 |
| R01806 | Admission policy is a bitfield, not a prompt | 2671 | M00179 | non-negotiable | false | 10 |
| R01807 | Admission bitfield — bits 0..3 cache tier | 2674 | M00179 | non-negotiable | false | 10 |
| R01808 | Admission bitfield — bits 4..7 trust | 2675 | M00179 | non-negotiable | false | 10 |
| R01809 | Admission bitfield — bits 8..15 reuse count | 2676 | M00179 | non-negotiable | false | 10 |
| R01810 | Admission bitfield — bits 16..31 token cost | 2677 | M00179 | non-negotiable | false | 10 |
| R01811 | Admission bitfield — bits 32..47 owner/session | 2678 | M00179 | non-negotiable | false | 10 |
| R01812 | Admission bitfield — bits 48..63 flags | 2679 | M00179 | non-negotiable | false | 10 |
| R01813 | Strong runtime shape adds a KV plane | 2684 | E0093 | non-negotiable | false | 10 |
| R01814 | Deterministic Cortex Runtime — plane 1 Branch Engine | 2689 | M00180 | non-negotiable | false | 10 |
| R01815 | Deterministic Cortex Runtime — plane 2 Policy Engine | 2690 | M00180 | non-negotiable | false | 10 |
| R01816 | Deterministic Cortex Runtime — plane 3 Grammar Engine | 2691 | M00180 | non-negotiable | false | 10 |
| R01817 | Deterministic Cortex Runtime — plane 4 Memory Router | 2692 | M00180 | non-negotiable | false | 10 |
| R01818 | Deterministic Cortex Runtime — plane 5 Speculation Engine | 2693 | M00180 | non-negotiable | false | 10 |
| R01819 | Deterministic Cortex Runtime — plane 6 Tool Gate | 2694 | M00180 | non-negotiable | false | 10 |
| R01820 | Deterministic Cortex Runtime — plane 7 Replay Log | 2695 | M00180 | non-negotiable | false | 10 |
| R01821 | Deterministic Cortex Runtime — plane 8 KV Cache Controller | 2696 | M00180 | non-negotiable | false | 10 |
| R01822 | The KV controller turns 256 GB RAM + ZFS + two GPUs into an actual memory hierarchy | 2699 | M00180 | non-negotiable | false | 10 |
| R01823 | Golden Rule #1 — Never recompute stable context if it can be content-addressed | 2704 | E0094 | non-negotiable | false | 10 |
| R01824 | Golden Rule #2 — Never verify a branch that violates deterministic law | 2705 | E0094 | non-negotiable | false | 10 |
| R01825 | Golden Rule #3 — Never keep KV hot just because it exists | 2706 | E0094 | non-negotiable | false | 10 |
| R01826 | Golden Rule #4 — Never let the expensive GPU wait for context assembly | 2707 | E0094 | non-negotiable | false | 10 |
| R01827 | Workstation does not have NVLink — fine | 2712 | E0095 | non-negotiable | false | 10 |
| R01828 | Workstation does not have 8 GPUs — fine | 2714 | E0095 | non-negotiable | false | 10 |
| R01829 | Substitute — content addressing | 2719 | E0095 | non-negotiable | false | 10 |
| R01830 | Substitute — prefix sharing | 2720 | E0095 | non-negotiable | false | 10 |
| R01831 | Substitute — speculative trees | 2721 | E0095 | non-negotiable | false | 10 |
| R01832 | Substitute — AVX-512 branch compaction | 2722 | E0095 | non-negotiable | false | 10 |
| R01833 | Substitute — KV cache tiering | 2723 | E0095 | non-negotiable | false | 10 |
| R01834 | Substitute — deterministic commit | 2724 | E0095 | non-negotiable | false | 10 |
| R01835 | The workstation stops being "a PC with GPUs" and becomes a local AI operating system | 2727 | E0095 | non-negotiable | false | 10 |
| R01836 | KV-cache-controller backend operator-overrideable (native / vllm-apc / lmcache / dynamo / sglang-radix) | 2483–2486 | F00851 | non-negotiable | true | 10 |
| R01837 | Tool-schema-KV prefill set operator-configurable (csv subset of system,tool,project,repo,user,grammar) | 2549–2556 | F00878 | non-negotiable | true | 10 |
| R01838 | Speculative-tree draft organ operator-selectable (3090 / cpu_simulated / disabled) | 2580–2585 | F00891 | non-negotiable | true | 10 |
| R01839 | Memory-admission policy bitfield layout operator-tunable | 2673–2680 | F00928 | non-negotiable | true | 10 |
| R01840 | Dashboard — KV hierarchy tier occupancy (VRAM/RAM/NVMe) | 2491–2494 | F00855 | non-negotiable | true | 10 |
| R01841 | Dashboard — KV block hit-rate per tier | 2491–2494 | F00856 | non-negotiable | true | 10 |
| R01842 | Dashboard — TTFT reduction from tool-schema-KV prefill | 2560–2564 | F00881 | non-negotiable | true | 10 |
| R01843 | Dashboard — speculative-tree depth × width × acceptance-rate | 2580–2608 | F00894 | non-negotiable | true | 10 |
| R01844 | Dashboard — branch-tree KV-share heatmap | 2628–2646 | F00913 | non-negotiable | true | 10 |
| R01845 | Dashboard — admission decisions per minute (cache-yes / cache-no histogram) | 2648–2680 | F00927 | non-negotiable | true | 10 |
| R01846 | Dashboard — Deterministic Cortex Runtime 8-plane overview | 2687–2697 | F00931 | non-negotiable | true | 10 |
| R01847 | API `GET /v1/kv-cache/tiers` | 2491–2494 | F00857 | non-negotiable | true | 10 |
| R01848 | API `GET /v1/kv-cache/block/{hash}` | 2517–2528 | F00858 | non-negotiable | true | 10 |
| R01849 | API `POST /v1/kv-cache/scan` | 2530–2540 | F00859 | non-negotiable | true | 10 |
| R01850 | API `POST /v1/kv-cache/content-address` | 2568–2572 | F00884 | non-negotiable | true | 10 |
| R01851 | Metric `sovereign_kv_block_count{tier}` | 2491–2494 | F00860 | non-negotiable | true | 10 |
| R01852 | Metric `sovereign_kv_block_bytes{tier}` | 2491–2494 | F00861 | non-negotiable | true | 10 |
| R01853 | Metric `sovereign_kv_block_hit_total{tier}` | 2503–2511 | F00862 | non-negotiable | true | 10 |
| R01854 | Metric `sovereign_kv_block_evict_total{tier}` | 2503–2511 | F00863 | non-negotiable | true | 10 |
| R01855 | Metric `sovereign_kv_block_offload_total{from,to}` | 2503–2511 | F00864 | non-negotiable | true | 10 |
| R01856 | Metric `sovereign_kv_prefill_reuse_total{kind}` | 2549–2556 | F00882 | non-negotiable | true | 10 |
| R01857 | Metric `sovereign_branch_kv_prefix_share_ratio` | 2644 | F00914 | non-negotiable | true | 10 |
| R01858 | Env var `SOVEREIGN_KV_CACHE_CONTROLLER_BACKEND` | 2483–2486 | F00853 | non-negotiable | true | 10 |
| R01859 | Env var `SOVEREIGN_TOOL_SCHEMA_KV_PREFILL` | 2549–2556 | F00879 | non-negotiable | true | 10 |
| R01860 | Env var `SOVEREIGN_SPEC_TREE_DRAFT_ORGAN` | 2580–2585 | F00892 | non-negotiable | true | 10 |
| R01861 | Env var `SOVEREIGN_MEMORY_ADMISSION_POLICY_BITS` | 2673–2680 | F00929 | non-negotiable | true | 10 |
| R01862 | CLI `--kv-cache-controller <backend>` | 2483–2486 | F00854 | non-negotiable | true | 10 |
| R01863 | CLI `--tool-schema-kv-prefill <csv>` | 2549–2556 | F00880 | non-negotiable | true | 10 |
| R01864 | CLI `--spec-tree-draft-organ <name>` | 2580–2585 | F00893 | non-negotiable | true | 10 |
| R01865 | Test — content-addressing is deterministic across runs + boots | 2568–2572 | F00886 | non-negotiable | false | 10 |
| R01866 | Test — TokenNode 16-byte layout enforced | 2589–2598 | F00898 | non-negotiable | false | 10 |
| R01867 | Test — KvBlockMeta 64-byte cache-line layout enforced | 2517–2528 | F00865 | non-negotiable | false | 10 |
| R01868 | Composite F00932 — Golden Rule #1 runtime enforcement (never recompute stable context if content-addressed) | 2704 | F00932 | non-negotiable | false | 10 |
| R01869 | Composite F00933 — Golden Rule #2 runtime enforcement (never verify a branch that violates deterministic law) | 2705 | F00933 | non-negotiable | false | 10 |
| R01870 | Composite F00935 — Golden Rule #4 runtime enforcement (never let the expensive GPU wait for context assembly) | 2707 | F00935 | non-negotiable | false | 10 |

— End of M011 milestone file.
