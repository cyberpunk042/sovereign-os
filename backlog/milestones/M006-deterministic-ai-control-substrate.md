# M006 — Deterministic AI control substrate

> Parent: `backlog/milestones/INDEX.md` row M006 (dump 995–1228).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 995–1228.
> All entries below extracted from the dump line range. No invention.

> **AVX++ canon update — 2026-05-19**: this milestone is affected by backward-sweep redefinition(s) — Core Law (CLARIFYING) + Commit Authority deterministic-vs-earned (BREAKING-FOR-LAYERING). See sovereign-os M061 for canonical pinning (commit 6f07dca). R-rows below are interpreted under the canonical later definitions per operator standing direction "layered: new direction ON TOP OF prior direction — never discarded".


## Epics (E0047–E0050)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0047 | 64-bit control word per branch — route 0..3 / task 4..7 / budget 8..15 / risk 16..23 / tool 24..31 / grammar 32..39 / memory 40..47 / spec_depth 48..55 / lifecycle 56..63 | 1071–1081 |
| E0048 | Deterministic Cortex Runtime v0 — branch arena + queue + grammar + tool perm + memory admission + verifier + replay + metrics | 1112–1123 |
| E0049 | Main loop — user task / branch records / 3090 propose / CPU filter / Blackwell verify / commit / memory update | 1126–1138 |
| E0050 | CPU as deterministic law — masks invalid tokens / rejects forbidden tools / expires branches / enforces schema / admits memory / decides GPU routing | 1098–1104 |

## Modules (M00079–M00095) — 17 modules

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00079 | RTX PRO 6000 plane — deep probabilistic engine / target model / verifier / final synthesis | 1042–1046 | E0047 |
| M00080 | RTX 3090 plane — draft / scout / embeddings / reranker / vision-tool / sandbox cognition | 1048–1054 | E0047 |
| M00081 | Ryzen AVX-512 plane — deterministic executive / grammar engine / branch scheduler / memory policy / tool law / risk masks / replay state | 1056–1063 | E0047 |
| M00082 | AVX-512 population evaluation — 8 × u64 branches / 64 × u8 states / 512 boolean flags per ZMM | 1085–1090 | E0047 |
| M00083 | DCR Branch Arena — allocator for active branches | 1112 | E0048 |
| M00084 | DCR Token Candidate Queue — typed candidate transitions | 1113 | E0048 |
| M00085 | DCR Grammar/JSON Automata — FSMs per branch | 1114 | E0048 |
| M00086 | DCR Tool Permission Engine — per-branch tool capability mask evaluation | 1115 | E0048 |
| M00087 | DCR Memory Admission Policy — admit/evict gating | 1116 | E0048 |
| M00088 | DCR Speculation Verifier — verify accepted transitions | 1117 | E0048 |
| M00089 | DCR Replay Log Writer — append-only typed transition log | 1118 | E0048 |
| M00090 | DCR Metrics Emitter — Prometheus + OTel | 1119 | E0048 |
| M00091 | Main loop step 1 — user task enters control plane | 1130 | E0049 |
| M00092 | Main loop step 2 — CPU creates branch records with control words | 1131 | E0049 |
| M00093 | Main loop step 3 — 3090 proposes cheap continuations / summaries / embeddings / tool plans | 1132 | E0049 |
| M00094 | Main loop step 4 — CPU filters / ranks / masks candidates | 1133 | E0049 |
| M00095 | Main loop step 5 — RTX PRO verifies high-value steps; step 6 commit; step 7 memory update | 1134–1138 | E0049 |

## Features (F00426–F00510) — 85 features

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00426 | Toggle DCR three-plane runtime | 1042–1063 | M00079 | mode | true |
| F00427 | Profile knob — `dcr_oracle_role_enabled` | 1042–1046 | M00079 | profile | true |
| F00428 | Profile knob — `dcr_scout_role_enabled` | 1048–1054 | M00080 | profile | true |
| F00429 | Profile knob — `dcr_cortex_role_enabled` | 1056–1063 | M00081 | profile | true |
| F00430 | Env var `SOVEREIGN_DCR_ORACLE_ENABLED` | 1042–1046 | M00079 | env_var | true |
| F00431 | Env var `SOVEREIGN_DCR_SCOUT_ENABLED` | 1048–1054 | M00080 | env_var | true |
| F00432 | Env var `SOVEREIGN_DCR_CORTEX_ENABLED` | 1056–1063 | M00081 | env_var | true |
| F00433 | CLI `sovereign-osctl dcr status` | 1112–1123 | M00083 | cli_verb | true |
| F00434 | CLI `sovereign-osctl dcr arena stats` | 1112 | M00083 | cli_verb | true |
| F00435 | CLI `sovereign-osctl dcr queue stats` | 1113 | M00084 | cli_verb | true |
| F00436 | CLI `sovereign-osctl dcr replay tail` | 1118 | M00089 | cli_verb | true |
| F00437 | Dashboard surface — DCR three-plane health | 1042–1063 | M00079 | dashboard | true |
| F00438 | Dashboard surface — DCR branch arena visualization | 1112 | M00083 | dashboard | true |
| F00439 | Dashboard surface — DCR token candidate queue | 1113 | M00084 | dashboard | true |
| F00440 | Dashboard surface — DCR grammar automata per-branch state | 1114 | M00085 | dashboard | true |
| F00441 | Dashboard surface — DCR tool permission mask matrix | 1115 | M00086 | dashboard | true |
| F00442 | Dashboard surface — DCR memory admission decision audit | 1116 | M00087 | dashboard | true |
| F00443 | Dashboard surface — DCR speculation verifier accept-rate | 1117 | M00088 | dashboard | true |
| F00444 | Dashboard surface — DCR replay log live tail | 1118 | M00089 | dashboard | true |
| F00445 | API `GET /v1/dcr/status` | 1112–1123 | M00083 | api_endpoint | true |
| F00446 | API `GET /v1/dcr/arena/stats` | 1112 | M00083 | api_endpoint | true |
| F00447 | API `GET /v1/dcr/queue/stats` | 1113 | M00084 | api_endpoint | true |
| F00448 | API `GET /v1/dcr/replay/tail` (SSE) | 1118 | M00089 | api_endpoint | true |
| F00449 | Metric `sovereign_os_dcr_branches_active` | 1112 | M00083 | observability_metric | true |
| F00450 | Metric `sovereign_os_dcr_branches_allocated_total` | 1112 | M00083 | observability_metric | true |
| F00451 | Metric `sovereign_os_dcr_token_queue_depth` | 1113 | M00084 | observability_metric | true |
| F00452 | Metric `sovereign_os_dcr_grammar_failures_total` | 1114 | M00085 | observability_metric | true |
| F00453 | Metric `sovereign_os_dcr_tool_permission_denials_total` | 1115 | M00086 | observability_metric | true |
| F00454 | Metric `sovereign_os_dcr_memory_admissions_total` | 1116 | M00087 | observability_metric | true |
| F00455 | Metric `sovereign_os_dcr_memory_evictions_total` | 1116 | M00087 | observability_metric | true |
| F00456 | Metric `sovereign_os_dcr_speculation_verifier_accept_rate` | 1117 | M00088 | observability_metric | true |
| F00457 | Metric `sovereign_os_dcr_replay_log_bytes_total` | 1118 | M00089 | observability_metric | true |
| F00458 | Test — DCR three-plane all enabled passes smoke test | 1042–1063 | M00079 | test | true |
| F00459 | Test — DCR Branch Arena handles 10K active branches | 1112 | M00083 | test | true |
| F00460 | Test — DCR Token Queue handles 1M candidates/sec | 1113 | M00084 | test | true |
| F00461 | Test — DCR Grammar Automata enforces JSON validity | 1114 | M00085 | test | true |
| F00462 | Test — DCR Tool Permission Engine rejects forbidden combo | 1115 | M00086 | test | true |
| F00463 | Test — DCR Memory Admission gates non-admissible memory | 1116 | M00087 | test | true |
| F00464 | Test — DCR Speculation Verifier accept rate ≥ 60% on typical workload | 1117 | M00088 | test | true |
| F00465 | Test — DCR Replay Log append-only invariant verified | 1118 | M00089 | test | true |
| F00466 | Lifecycle hook — DCR startup verifies all three planes available | 1042–1063 | M00079 | lifecycle_hook | true |
| F00467 | Lifecycle hook — DCR shutdown flushes arena + queue + replay | 1112–1123 | M00083 | lifecycle_hook | true |
| F00468 | Composite — DCR three-plane runtime end-to-end | 1042–1138 | composite: [M00079, M00080, M00081, M00083, M00084, M00085, M00086, M00087, M00088, M00089, M00090] | capability | true |
| F00469 | Personalization — operator-defined DCR plane priority order | 1042–1063 | M00079 | configuration | true |
| F00470 | Personalization — operator-defined DCR arena size | 1112 | M00083 | configuration | true |
| F00471 | Personalization — operator-defined DCR queue depth limit | 1113 | M00084 | configuration | true |
| F00472 | Toggle 64-bit control word route field | 1071 | M00082 | mode | true |
| F00473 | Toggle 64-bit control word task field | 1072 | M00082 | mode | true |
| F00474 | Toggle 64-bit control word budget field | 1073 | M00082 | mode | true |
| F00475 | Toggle 64-bit control word risk field | 1074 | M00082 | mode | true |
| F00476 | Toggle 64-bit control word tool permissions field | 1075 | M00082 | mode | true |
| F00477 | Toggle 64-bit control word grammar state field | 1076 | M00082 | mode | true |
| F00478 | Toggle 64-bit control word memory policy field | 1077 | M00082 | mode | true |
| F00479 | Toggle 64-bit control word speculation depth field | 1078 | M00082 | mode | true |
| F00480 | Toggle 64-bit control word lifecycle flags field | 1079 | M00082 | mode | true |
| F00481 | Profile knob — `control_word_field_enabled_<name>` per field | 1071–1081 | M00082 | profile | true |
| F00482 | Env var `SOVEREIGN_CTRL_WORD_FIELD_ENABLED_<NAME>` per field | 1071–1081 | M00082 | env_var | true |
| F00483 | CLI `sovereign-osctl dcr control-word inspect <branch-id>` | 1071–1081 | M00082 | cli_verb | true |
| F00484 | Dashboard surface — control word per-branch bit-layout heatmap | 1071–1081 | M00082 | dashboard | true |
| F00485 | API `GET /v1/dcr/control-word/<branch-id>` | 1071–1081 | M00082 | api_endpoint | true |
| F00486 | Metric `sovereign_os_dcr_control_word_field_usage{field}` | 1071–1081 | M00082 | observability_metric | true |
| F00487 | Toggle AVX-512 population eval mode (8 × u64 / 64 × u8 / 512-bit) | 1085–1090 | M00082 | mode | true |
| F00488 | Profile knob — `dcr_avx512_pop_eval_lane_width` | 1085–1090 | M00082 | profile | true |
| F00489 | Env var `SOVEREIGN_DCR_AVX512_POP_EVAL_LANE_WIDTH` | 1085–1090 | M00082 | env_var | true |
| F00490 | Toggle CPU mask invalid tokens enforcement | 1098 | M00081 | mode | true |
| F00491 | Toggle CPU reject forbidden tools enforcement | 1099 | M00081 | mode | true |
| F00492 | Toggle CPU expire branches enforcement | 1100 | M00081 | mode | true |
| F00493 | Toggle CPU enforce schema state enforcement | 1101 | M00081 | mode | true |
| F00494 | Toggle CPU memory admission enforcement | 1102 | M00081 | mode | true |
| F00495 | Toggle CPU GPU routing decision enforcement | 1103 | M00081 | mode | true |
| F00496 | Profile knob — `dcr_enforcement_strict` (all on) | 1098–1104 | M00081 | profile | true |
| F00497 | Env var `SOVEREIGN_DCR_ENFORCEMENT_STRICT` | 1098–1104 | M00081 | env_var | true |
| F00498 | CLI `sovereign-osctl dcr enforcement status` | 1098–1104 | M00081 | cli_verb | true |
| F00499 | Dashboard surface — DCR enforcement per-rule audit | 1098–1104 | M00081 | dashboard | true |
| F00500 | Metric `sovereign_os_dcr_enforcement_token_masks_total` | 1098 | M00081 | observability_metric | true |
| F00501 | Metric `sovereign_os_dcr_enforcement_tool_rejections_total` | 1099 | M00081 | observability_metric | true |
| F00502 | Metric `sovereign_os_dcr_enforcement_branch_expirations_total` | 1100 | M00081 | observability_metric | true |
| F00503 | Metric `sovereign_os_dcr_enforcement_schema_violations_total` | 1101 | M00081 | observability_metric | true |
| F00504 | Metric `sovereign_os_dcr_enforcement_memory_admissions_total` | 1102 | M00081 | observability_metric | true |
| F00505 | Metric `sovereign_os_dcr_enforcement_gpu_routes_total` | 1103 | M00081 | observability_metric | true |
| F00506 | Test — DCR enforcement strict mode rejects every violation | 1098–1104 | M00081 | test | true |
| F00507 | Lifecycle hook — DCR pre-enforcement emit pre-state snapshot | 1098–1104 | M00081 | lifecycle_hook | true |
| F00508 | Lifecycle hook — DCR post-enforcement emit decision audit | 1098–1104 | M00081 | lifecycle_hook | true |
| F00509 | Composite — DCR main loop step-1 through step-7 end-to-end | 1126–1138 | composite: [M00091, M00092, M00093, M00094, M00095] | capability | true |
| F00510 | Personalization — operator-defined enforcement bypass per branch class | 1098–1104 | M00081 | configuration | true |

## Requirements (R00851–R01020) — 170 requirements

| R ID | Phrase | Dump line | Parent F | Class | Opt-in | Sub-req min |
|---|---|---|---|---|---|---|
| R00851 | DCR three-plane runtime requires Oracle + Scout + Cortex enabled | 1042–1063 | F00426 | non-negotiable | true | 10 |
| R00852 | DCR fails closed when any plane disabled and strict mode active | 1042–1063 | F00426 | non-negotiable | true | 10 |
| R00853 | Profile `dcr_oracle_role_enabled` accepts boolean | 1042–1046 | F00427 | non-negotiable | true | 10 |
| R00854 | Profile `dcr_scout_role_enabled` accepts boolean | 1048–1054 | F00428 | non-negotiable | true | 10 |
| R00855 | Profile `dcr_cortex_role_enabled` accepts boolean | 1056–1063 | F00429 | non-negotiable | true | 10 |
| R00856 | Env var `SOVEREIGN_DCR_ORACLE_ENABLED` accepts boolean | 1042–1046 | F00430 | non-negotiable | true | 10 |
| R00857 | Env var `SOVEREIGN_DCR_SCOUT_ENABLED` accepts boolean | 1048–1054 | F00431 | non-negotiable | true | 10 |
| R00858 | Env var `SOVEREIGN_DCR_CORTEX_ENABLED` accepts boolean | 1056–1063 | F00432 | non-negotiable | true | 10 |
| R00859 | CLI `dcr status` returns JSON | 1112–1123 | F00433 | non-negotiable | true | 10 |
| R00860 | CLI `dcr arena stats` returns active/allocated/free count | 1112 | F00434 | non-negotiable | true | 10 |
| R00861 | CLI `dcr queue stats` returns depth/throughput/latency | 1113 | F00435 | non-negotiable | true | 10 |
| R00862 | CLI `dcr replay tail` follows append-only log | 1118 | F00436 | non-negotiable | true | 10 |
| R00863 | Dashboard DCR three-plane health card shows green/yellow/red per plane | 1042–1063 | F00437 | non-negotiable | true | 10 |
| R00864 | Dashboard arena visualization shows branch population | 1112 | F00438 | non-negotiable | true | 10 |
| R00865 | Dashboard queue shows top-50 candidate transitions | 1113 | F00439 | non-negotiable | true | 10 |
| R00866 | Dashboard grammar automata shows per-branch FSM state | 1114 | F00440 | non-negotiable | true | 10 |
| R00867 | Dashboard tool permission matrix shows per-branch × per-tool grid | 1115 | F00441 | non-negotiable | true | 10 |
| R00868 | Dashboard memory admission audit shows per-decision reason | 1116 | F00442 | non-negotiable | true | 10 |
| R00869 | Dashboard speculation verifier accept-rate shown as time-series | 1117 | F00443 | non-negotiable | true | 10 |
| R00870 | Dashboard replay log live tail shows last 100 entries | 1118 | F00444 | non-negotiable | true | 10 |
| R00871 | API `/v1/dcr/status` returns JSON | 1112–1123 | F00445 | non-negotiable | true | 10 |
| R00872 | API `/v1/dcr/arena/stats` returns JSON | 1112 | F00446 | non-negotiable | true | 10 |
| R00873 | API `/v1/dcr/queue/stats` returns JSON | 1113 | F00447 | non-negotiable | true | 10 |
| R00874 | API `/v1/dcr/replay/tail` streams server-sent events | 1118 | F00448 | non-negotiable | true | 10 |
| R00875 | Metric `sovereign_os_dcr_branches_active` is Prometheus gauge | 1112 | F00449 | non-negotiable | false | 10 |
| R00876 | Metric `sovereign_os_dcr_branches_allocated_total` is Prometheus counter | 1112 | F00450 | non-negotiable | false | 10 |
| R00877 | Metric `sovereign_os_dcr_token_queue_depth` is Prometheus gauge | 1113 | F00451 | non-negotiable | false | 10 |
| R00878 | Metric `sovereign_os_dcr_grammar_failures_total` is Prometheus counter | 1114 | F00452 | non-negotiable | false | 10 |
| R00879 | Metric `sovereign_os_dcr_tool_permission_denials_total` is Prometheus counter | 1115 | F00453 | non-negotiable | false | 10 |
| R00880 | Metric `sovereign_os_dcr_memory_admissions_total` is Prometheus counter | 1116 | F00454 | non-negotiable | false | 10 |
| R00881 | Metric `sovereign_os_dcr_memory_evictions_total` is Prometheus counter | 1116 | F00455 | non-negotiable | false | 10 |
| R00882 | Metric `sovereign_os_dcr_speculation_verifier_accept_rate` is Prometheus gauge 0–1 | 1117 | F00456 | non-negotiable | false | 10 |
| R00883 | Metric `sovereign_os_dcr_replay_log_bytes_total` is Prometheus counter | 1118 | F00457 | non-negotiable | false | 10 |
| R00884 | Test — all three DCR planes enabled passes smoke test | 1042–1063 | F00458 | non-negotiable | false | 10 |
| R00885 | Test — DCR Branch Arena handles 10K active branches without OOM | 1112 | F00459 | preferable | false | 10 |
| R00886 | Test — DCR Token Queue handles 1M candidates/sec | 1113 | F00460 | preferable | false | 10 |
| R00887 | Test — DCR Grammar Automata enforces JSON validity on adversarial inputs | 1114 | F00461 | non-negotiable | false | 10 |
| R00888 | Test — DCR Tool Permission rejects shell-write when permissions disallow | 1115 | F00462 | non-negotiable | false | 10 |
| R00889 | Test — DCR Memory Admission gates non-admissible memory writes | 1116 | F00463 | non-negotiable | false | 10 |
| R00890 | Test — DCR Speculation Verifier accept rate ≥ 60% on typical workload | 1117 | F00464 | preferable | false | 10 |
| R00891 | Test — DCR Replay Log append-only invariant verified via property test | 1118 | F00465 | non-negotiable | false | 10 |
| R00892 | Lifecycle hook DCR startup verifies oracle reachable | 1042–1046 | F00466 | non-negotiable | true | 10 |
| R00893 | Lifecycle hook DCR startup verifies scout reachable | 1048–1054 | F00466 | non-negotiable | true | 10 |
| R00894 | Lifecycle hook DCR startup verifies cortex AVX-512 features available | 1056–1063 | F00466 | non-negotiable | true | 10 |
| R00895 | Lifecycle hook DCR shutdown flushes arena | 1112 | F00467 | non-negotiable | false | 10 |
| R00896 | Lifecycle hook DCR shutdown flushes queue | 1113 | F00467 | non-negotiable | false | 10 |
| R00897 | Lifecycle hook DCR shutdown flushes replay log | 1118 | F00467 | non-negotiable | false | 10 |
| R00898 | Composite F00468 DCR three-plane runtime requires all 11 modules | 1042–1138 | F00468 | non-negotiable | false | 10 |
| R00899 | Personalization — operator-defined DCR plane priority order via YAML | 1042–1063 | F00469 | non-negotiable | true | 10 |
| R00900 | Personalization — DCR arena size (default 64K branches; operator-tunable) | 1112 | F00470 | non-negotiable | true | 10 |
| R00901 | Personalization — DCR queue depth limit (default 1M; operator-tunable) | 1113 | F00471 | non-negotiable | true | 10 |
| R00902 | Control word field `route` covers bits 0..3 (16 routes) | 1071 | F00472 | non-negotiable | false | 10 |
| R00903 | Control word field `task` covers bits 4..7 (16 task types) | 1072 | F00473 | non-negotiable | false | 10 |
| R00904 | Control word field `budget` covers bits 8..15 (256 budget values) | 1073 | F00474 | non-negotiable | false | 10 |
| R00905 | Control word field `risk` covers bits 16..23 (256 risk classes) | 1074 | F00475 | non-negotiable | false | 10 |
| R00906 | Control word field `tool_permissions` covers bits 24..31 (8 tool perm bits) | 1075 | F00476 | non-negotiable | false | 10 |
| R00907 | Control word field `grammar_state` covers bits 32..39 (256 grammar states) | 1076 | F00477 | non-negotiable | false | 10 |
| R00908 | Control word field `memory_policy` covers bits 40..47 (256 memory policies) | 1077 | F00478 | non-negotiable | false | 10 |
| R00909 | Control word field `speculation_depth` covers bits 48..55 (256 depth values) | 1078 | F00479 | non-negotiable | false | 10 |
| R00910 | Control word field `lifecycle_flags` covers bits 56..63 (8 lifecycle flag bits) | 1079 | F00480 | non-negotiable | false | 10 |
| R00911 | Profile knob `control_word_field_enabled_<name>` per field accepts boolean | 1071–1081 | F00481 | non-negotiable | true | 10 |
| R00912 | Env var `SOVEREIGN_CTRL_WORD_FIELD_ENABLED_<NAME>` per field accepts boolean | 1071–1081 | F00482 | non-negotiable | true | 10 |
| R00913 | CLI `dcr control-word inspect <branch-id>` returns 9-field decode | 1071–1081 | F00483 | non-negotiable | true | 10 |
| R00914 | Dashboard control-word heatmap shows per-field utilization across branches | 1071–1081 | F00484 | non-negotiable | true | 10 |
| R00915 | API `GET /v1/dcr/control-word/<branch-id>` returns 9-field JSON | 1071–1081 | F00485 | non-negotiable | true | 10 |
| R00916 | Metric `sovereign_os_dcr_control_word_field_usage` is Prometheus counter labeled by field | 1071–1081 | F00486 | non-negotiable | false | 10 |
| R00917 | AVX-512 pop eval lane width default = 8 × u64 | 1085–1090 | F00487 | non-negotiable | true | 10 |
| R00918 | AVX-512 pop eval supports lane width 64 × u8 | 1085–1090 | F00487 | non-negotiable | true | 10 |
| R00919 | AVX-512 pop eval supports 512-bit boolean flags | 1085–1090 | F00487 | non-negotiable | true | 10 |
| R00920 | Profile `dcr_avx512_pop_eval_lane_width` accepts `u64` / `u8` / `bitset` | 1085–1090 | F00488 | non-negotiable | true | 10 |
| R00921 | Env var `SOVEREIGN_DCR_AVX512_POP_EVAL_LANE_WIDTH` accepts same enum | 1085–1090 | F00489 | non-negotiable | true | 10 |
| R00922 | CPU mask invalid tokens enforcement applies grammar mask + schema mask + safety mask | 1098 | F00490 | non-negotiable | false | 10 |
| R00923 | CPU reject forbidden tools enforcement reads tool_permissions field | 1099 | F00491 | non-negotiable | false | 10 |
| R00924 | CPU expire branches enforcement decrements budget per tick | 1100 | F00492 | non-negotiable | false | 10 |
| R00925 | CPU enforce schema state enforcement reads grammar_state field | 1101 | F00493 | non-negotiable | false | 10 |
| R00926 | CPU memory admission enforcement reads memory_policy field | 1102 | F00494 | non-negotiable | false | 10 |
| R00927 | CPU GPU routing decision enforcement reads route field | 1103 | F00495 | non-negotiable | false | 10 |
| R00928 | Profile `dcr_enforcement_strict` enables all 6 enforcement passes | 1098–1104 | F00496 | non-negotiable | true | 10 |
| R00929 | Env var `SOVEREIGN_DCR_ENFORCEMENT_STRICT` accepts boolean | 1098–1104 | F00497 | non-negotiable | true | 10 |
| R00930 | CLI `dcr enforcement status` returns 6-pass enabled/disabled JSON | 1098–1104 | F00498 | non-negotiable | true | 10 |
| R00931 | Dashboard DCR enforcement audit shows per-rule fire count | 1098–1104 | F00499 | non-negotiable | true | 10 |
| R00932 | Metric `sovereign_os_dcr_enforcement_token_masks_total` is Prometheus counter | 1098 | F00500 | non-negotiable | false | 10 |
| R00933 | Metric `sovereign_os_dcr_enforcement_tool_rejections_total` is Prometheus counter | 1099 | F00501 | non-negotiable | false | 10 |
| R00934 | Metric `sovereign_os_dcr_enforcement_branch_expirations_total` is Prometheus counter | 1100 | F00502 | non-negotiable | false | 10 |
| R00935 | Metric `sovereign_os_dcr_enforcement_schema_violations_total` is Prometheus counter | 1101 | F00503 | non-negotiable | false | 10 |
| R00936 | Metric `sovereign_os_dcr_enforcement_memory_admissions_total` is Prometheus counter | 1102 | F00504 | non-negotiable | false | 10 |
| R00937 | Metric `sovereign_os_dcr_enforcement_gpu_routes_total` is Prometheus counter | 1103 | F00505 | non-negotiable | false | 10 |
| R00938 | Test — DCR enforcement strict mode rejects every adversarial violation | 1098–1104 | F00506 | non-negotiable | false | 10 |
| R00939 | Lifecycle hook DCR pre-enforcement emits pre-state OTel snapshot | 1098–1104 | F00507 | non-negotiable | false | 10 |
| R00940 | Lifecycle hook DCR post-enforcement emits decision audit | 1098–1104 | F00508 | non-negotiable | false | 10 |
| R00941 | Composite F00509 DCR main loop requires modules M00091 + M00092 + M00093 + M00094 + M00095 | 1126–1138 | F00509 | non-negotiable | false | 10 |
| R00942 | Composite F00509 main loop emits OTel parent span per request | 1126–1138 | F00509 | non-negotiable | false | 10 |
| R00943 | Composite F00509 main loop child spans — step1..step7 | 1126–1138 | F00509 | non-negotiable | false | 10 |
| R00944 | Personalization — operator-defined enforcement bypass per branch class via YAML | 1098–1104 | F00510 | non-negotiable | true | 10 |
| R00945 | DCR Branch Arena allocator = bump allocator with free list | 1112 | M00083 | non-negotiable | false | 10 |
| R00946 | DCR Branch Arena allocator capacity persisted across daemon restart | 1112 | M00083 | non-negotiable | false | 10 |
| R00947 | DCR Branch Arena allocator OOM emits OTel error span | 1112 | M00083 | non-negotiable | false | 10 |
| R00948 | DCR Branch Arena allocator OOM triggers backpressure event | 1112 | M00083 | non-negotiable | false | 10 |
| R00949 | DCR Token Candidate Queue ordered FIFO by default | 1113 | M00084 | non-negotiable | true | 10 |
| R00950 | DCR Token Candidate Queue priority-ordered when `priority_mode = reward` | 1113 | M00084 | non-negotiable | true | 10 |
| R00951 | DCR Token Candidate Queue lock-free MPMC channel | 1113 | M00084 | non-negotiable | false | 10 |
| R00952 | DCR Token Candidate Queue overflow policy = drop oldest by default | 1113 | M00084 | non-negotiable | true | 10 |
| R00953 | DCR Grammar Automata per-branch FSM state machine | 1114 | M00085 | non-negotiable | false | 10 |
| R00954 | DCR Grammar Automata supports JSON FSM | 1114 | M00085 | non-negotiable | false | 10 |
| R00955 | DCR Grammar Automata supports tool-call schema FSM | 1114 | M00085 | non-negotiable | false | 10 |
| R00956 | DCR Grammar Automata supports shell-command FSM | 1114 | M00085 | non-negotiable | true | 10 |
| R00957 | DCR Grammar Automata supports code-patch FSM | 1114 | M00085 | non-negotiable | true | 10 |
| R00958 | DCR Grammar Automata supports operator-defined custom FSM | 1114 | M00085 | non-negotiable | true | 10 |
| R00959 | DCR Tool Permission Engine evaluates per-branch tool_permissions bitmask | 1115 | M00086 | non-negotiable | false | 10 |
| R00960 | DCR Tool Permission Engine supports operator-defined permission profiles | 1115 | M00086 | non-negotiable | true | 10 |
| R00961 | DCR Memory Admission Policy default = trust ≥ 0.5 AND freshness ≤ 30d AND privacy ≤ profile.max_privacy | 1116 | M00087 | non-negotiable | true | 10 |
| R00962 | DCR Memory Admission Policy operator-tunable thresholds | 1116 | M00087 | non-negotiable | true | 10 |
| R00963 | DCR Memory Admission Policy emits audit OTel span per decision | 1116 | M00087 | non-negotiable | false | 10 |
| R00964 | DCR Speculation Verifier accepts transition iff oracle_ok & grammar_valid & tool_valid & budget_valid & memory_valid | 1117 | M00088 | non-negotiable | false | 10 |
| R00965 | DCR Speculation Verifier fail-closed on any predicate failure | 1117 | M00088 | non-negotiable | false | 10 |
| R00966 | DCR Speculation Verifier emits OTel span with predicate values per decision | 1117 | M00088 | non-negotiable | false | 10 |
| R00967 | DCR Replay Log append-only — no in-place mutation | 1118 | M00089 | non-negotiable | false | 10 |
| R00968 | DCR Replay Log content-addressed via blake3 hash per entry | 1118 | M00089 | non-negotiable | false | 10 |
| R00969 | DCR Replay Log rotated when ≥ 100 MiB | 1118 | M00089 | non-negotiable | true | 10 |
| R00970 | DCR Replay Log encoded as JSONL by default | 1118 | M00089 | non-negotiable | true | 10 |
| R00971 | DCR Replay Log encoded as bincode when `--binary-replay` set | 1118 | M00089 | preferable | true | 10 |
| R00972 | DCR Replay Log entry schema — branch_id / parent_id / state_before / candidate_ref / policy_mask / grammar_state / model / accepted / tool_intent / timestamp | 2840–2858 | M00089 | non-negotiable | false | 10 |
| R00973 | DCR Replay Log entry signed when `--require-signed-replay` set | 1118 | M00089 | non-negotiable | true | 10 |
| R00974 | DCR Metrics Emitter emits Prometheus textfile collector format | 1119 | M00090 | non-negotiable | false | 10 |
| R00975 | DCR Metrics Emitter emits OTel spans for high-cardinality events | 1119 | M00090 | non-negotiable | false | 10 |
| R00976 | DCR Metrics Emitter exposes `:9101/metrics` endpoint | 1119 | M00090 | non-negotiable | true | 10 |
| R00977 | Main loop step 1 — accept request via Anthropic-compatible `/v1/messages` | 1130 | M00091 | non-negotiable | false | 10 |
| R00978 | Main loop step 1 — also accept request via OpenAI-compatible `/v1/chat/completions` | 1130 | M00091 | non-negotiable | true | 10 |
| R00979 | Main loop step 1 — also accept request via MCP server endpoint | 1130 | M00091 | non-negotiable | true | 10 |
| R00980 | Main loop step 1 — also accept request via local CLI | 1130 | M00091 | non-negotiable | true | 10 |
| R00981 | Main loop step 2 — CPU creates branch records via DCR Branch Arena | 1131 | M00092 | non-negotiable | false | 10 |
| R00982 | Main loop step 2 — initial control word seeded from profile defaults | 1131 | M00092 | non-negotiable | false | 10 |
| R00983 | Main loop step 3 — 3090 produces cheap continuations | 1132 | M00093 | non-negotiable | false | 10 |
| R00984 | Main loop step 3 — 3090 produces summaries when context > budget | 1132 | M00093 | non-negotiable | false | 10 |
| R00985 | Main loop step 3 — 3090 produces embeddings on demand | 1132 | M00093 | non-negotiable | false | 10 |
| R00986 | Main loop step 3 — 3090 produces tool plans for routed branches | 1132 | M00093 | non-negotiable | false | 10 |
| R00987 | Main loop step 4 — CPU filters via constraint automata | 1133 | M00094 | non-negotiable | false | 10 |
| R00988 | Main loop step 4 — CPU ranks via reward vector | 1133 | M00094 | non-negotiable | false | 10 |
| R00989 | Main loop step 4 — CPU masks via grammar mask + tool policy mask + safety mask + schema mask + route mask | 1133 | M00094 | non-negotiable | false | 10 |
| R00990 | Main loop step 5 — RTX PRO verifies high-value transitions | 1134 | M00095 | non-negotiable | false | 10 |
| R00991 | Main loop step 5 — RTX PRO verification batched in one packed pass | 1134 | M00095 | non-negotiable | false | 10 |
| R00992 | Main loop step 6 — CPU commits accepted transitions to replay log | 1135 | M00095 | non-negotiable | false | 10 |
| R00993 | Main loop step 6 — Memory plane updates on commit | 1136 | M00095 | non-negotiable | false | 10 |
| R00994 | Main loop step 7 — Repeat loop | 1138 | M00095 | non-negotiable | false | 10 |
| R00995 | Main loop step 7 — Termination on commit reaching `final` lifecycle flag | 1138 | M00095 | non-negotiable | false | 10 |
| R00996 | DCR three-plane runtime law — no plane bypasses CPU enforcement | 1098–1104 | M00081 | non-negotiable | false | 10 |
| R00997 | DCR three-plane runtime law — replay log captures every accepted transition | 1118 | M00089 | non-negotiable | false | 10 |
| R00998 | DCR three-plane runtime law — large tensors never cross plane boundary | 540–547 | M00081 | non-negotiable | false | 10 |
| R00999 | DCR three-plane runtime law — boundaries move compact symbols only | 526–536 | M00081 | non-negotiable | false | 10 |
| R01000 | DCR three-plane runtime law — oracle never receives garbage work | 1180–1183 | M00079 | non-negotiable | true | 10 |
| R01001 | DCR three-plane runtime law — scout may be wrong cheaply | 1184 | M00080 | non-negotiable | false | 10 |
| R01002 | DCR three-plane runtime law — CPU owns truth/state | 1185 | M00081 | non-negotiable | false | 10 |
| R01003 | DCR three-plane runtime law — tool use never model-authorized alone | 1186 | M00081 | non-negotiable | false | 10 |
| R01004 | DCR three-plane runtime law — every branch has a budget | 1187 | M00081 | non-negotiable | false | 10 |
| R01005 | DCR three-plane runtime law — every output grammar/state constrained when possible | 1188 | M00085 | non-negotiable | false | 10 |
| R01006 | DCR three-plane runtime law — every transition replayable | 1189 | M00089 | non-negotiable | false | 10 |
| R01007 | DCR three-plane runtime law — large tensors stay on their GPU | 1190 | M00081 | non-negotiable | false | 10 |
| R01008 | DCR three-plane runtime law — boundaries move compact symbols not bulk activations | 1191 | M00081 | non-negotiable | false | 10 |
| R01009 | DCR three-plane runtime — operator's "AI proposes, runtime commits" framing surfaced on main cockpit | 1525–1530 | M00079 | non-negotiable | false | 10 |
| R01010 | DCR three-plane runtime — operator's quote logged verbatim in replay log header | 1525–1530 | M00079 | non-negotiable | false | 10 |
| R01011 | DCR persistence layer — branch arena snapshot under ZFS | 1112 | M00083 | non-negotiable | false | 10 |
| R01012 | DCR persistence layer — token queue snapshot under ZFS | 1113 | M00084 | non-negotiable | false | 10 |
| R01013 | DCR persistence layer — replay log snapshot under ZFS | 1118 | M00089 | non-negotiable | false | 10 |
| R01014 | DCR persistence layer — snapshot before every risky commit | 1118 | M00089 | non-negotiable | true | 10 |
| R01015 | DCR persistence layer — snapshot rollback via `sovereign-osctl rollback <snapshot-id>` | 1118 | M00089 | non-negotiable | true | 10 |
| R01016 | DCR observability — every step emits OTel span with branch_id + step_id + duration_ms | 1126–1138 | M00091 | non-negotiable | false | 10 |
| R01017 | DCR observability — every commit emits Prometheus counter | 1135 | M00095 | non-negotiable | false | 10 |
| R01018 | DCR observability — every reject emits Prometheus counter with reason label | 1133 | M00094 | non-negotiable | false | 10 |
| R01019 | DCR observability — every backpressure event emits OTel span | 1112 | M00083 | non-negotiable | false | 10 |
| R01020 | DCR observability — every operator override emits audit OTel span | 1098–1104 | F00510 | non-negotiable | false | 10 |

— End of M006 milestone file.
