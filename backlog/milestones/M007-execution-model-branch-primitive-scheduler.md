# M007 — Execution model — branch primitive + AVX-512 scheduler

> Parent: `backlog/milestones/INDEX.md` row M007 (dump 1228–1600).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 1228–1600.
> All entries below extracted from the dump line range. No invention.

## Epics (E0051–E0058)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0051 | Branch as live hypothesis with deterministic metadata | 1242 |
| E0052 | 8-step branch loop — Spawn / Retrieve / Draft / Filter / Verify / Act / Commit / Learn | 1280–1304 |
| E0053 | SoA branch state arrays — id / control / budget / score / flags / grammar / memory / route | 1314–1324 |
| E0054 | 64-bit control word composability — route / task / risk / permissions / grammar / priority / spec_depth / flags | 1355–1363 |
| E0055 | Epistemic role assignment per model — oracle / verifier / scout / specialist / law | 1390–1434 |
| E0056 | Memory typing — episodic / semantic / procedural / project / policy / trace | 1444–1451 |
| E0057 | MemoryRef struct — id / type / embedding_ref / trust / freshness / access_count / decay / flags | 1456–1465 |
| E0058 | Transactional tool call — intent → CPU permission check → execute/ask/rewrite/reject/sandbox | 1480–1517 |

## Modules (M00096–M00112) — 17 modules

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00096 | Branch primitive — live hypothesis with metadata | 1240–1255 | E0051 |
| M00097 | AI transaction engine framing | 1305 | E0052 |
| M00098 | 8-step lifecycle — Spawn / Retrieve / Draft / Filter / Verify / Act / Commit / Learn | 1280–1304 | E0052 |
| M00099 | SoA SIMD-friendly fields — 8 arrays | 1314–1324 | E0053 |
| M00100 | Per-tick AVX ops — budget decrement / dead_mask / risk_mask / oracle_mask / scout_mask / tool_mask / merge_mask | 1326–1336 | E0053 |
| M00101 | Branch operating system framing | 1337 | E0053 |
| M00102 | AVX pack via compress for dense GPU batches | 1338–1342 | E0053 |
| M00103 | Composable control word — 8 fields | 1355–1363 | E0054 |
| M00104 | Branch queries via AVX-512 — shell-allowed / file-write-allowed / JSON-required / verification-required / speculative-only / network-allowed | 1366–1375 | E0054 |
| M00105 | Psychological shift — instructions become data / policy becomes bits / reasoning becomes state transitions | 1378–1383 | E0054 |
| M00106 | Epistemic roles — Oracle (final reasoning, hard synthesis, verification, architecture, long context) | 1390–1404 | E0055 |
| M00107 | Epistemic role — Verifier (checks claims, code diffs, tool plans; may be oracle with different prompt) | 1399–1404 | E0055 |
| M00108 | Epistemic role — Scout (cheap exploration / draft continuations) | 1409–1414 | E0055 |
| M00109 | Epistemic role — Specialists (embeddings / rerank / code-local / vision / classification / safety-risk) | 1418–1424 | E0055 |
| M00110 | Epistemic role — Law (FSMs / grammar / token masks / permission masks / deterministic tests / scheduler / replay) | 1429–1434 | E0055 |
| M00111 | Memory MemoryRef metadata fields | 1455–1465 | E0057 |
| M00112 | Transactional tool gate — intent / permission / workspace / budget / risk / mode / confirmation | 1497–1517 | E0058 |

## Features (F00511–F00595) — 85 features

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00511 | Toggle 8-step branch loop | 1280–1304 | M00098 | mode | true |
| F00512 | Profile knob — `branch_lifecycle_strict` (all 8 steps mandatory) | 1280–1304 | M00098 | profile | true |
| F00513 | Env var `SOVEREIGN_BRANCH_LIFECYCLE_STRICT` | 1280–1304 | M00098 | env_var | true |
| F00514 | CLI `sovereign-osctl branch lifecycle <id>` | 1280–1304 | M00098 | cli_verb | true |
| F00515 | CLI `sovereign-osctl branch spawn` | 1281 | M00098 | cli_verb | true |
| F00516 | CLI `sovereign-osctl branch retrieve <id>` | 1284 | M00098 | cli_verb | true |
| F00517 | CLI `sovereign-osctl branch draft <id>` | 1287 | M00098 | cli_verb | true |
| F00518 | CLI `sovereign-osctl branch filter <id>` | 1290 | M00098 | cli_verb | true |
| F00519 | CLI `sovereign-osctl branch verify <id>` | 1294 | M00098 | cli_verb | true |
| F00520 | CLI `sovereign-osctl branch act <id>` | 1297 | M00098 | cli_verb | true |
| F00521 | CLI `sovereign-osctl branch commit <id>` | 1300 | M00098 | cli_verb | true |
| F00522 | CLI `sovereign-osctl branch learn <id>` | 1303 | M00098 | cli_verb | true |
| F00523 | Dashboard surface — branch lifecycle timeline | 1280–1304 | M00098 | dashboard | true |
| F00524 | Dashboard surface — branch state SoA inspector | 1314–1324 | M00099 | dashboard | true |
| F00525 | Dashboard surface — AVX scheduler per-tick mask breakdown | 1326–1336 | M00100 | dashboard | true |
| F00526 | Dashboard surface — branch-OS framing visualization | 1337 | M00101 | dashboard | true |
| F00527 | Dashboard surface — AVX compress sparse-to-dense visualization | 1338–1342 | M00102 | dashboard | true |
| F00528 | Dashboard surface — control word composability inspector | 1355–1363 | M00103 | dashboard | true |
| F00529 | Dashboard surface — branch queries via AVX-512 audit | 1366–1375 | M00104 | dashboard | true |
| F00530 | Dashboard surface — epistemic role assignment matrix per model | 1390–1434 | M00106 | dashboard | true |
| F00531 | Dashboard surface — Oracle role utilization | 1390–1404 | M00106 | dashboard | true |
| F00532 | Dashboard surface — Verifier role accept rate | 1399–1404 | M00107 | dashboard | true |
| F00533 | Dashboard surface — Scout role draft acceptance | 1409–1414 | M00108 | dashboard | true |
| F00534 | Dashboard surface — Specialists role per-task class usage | 1418–1424 | M00109 | dashboard | true |
| F00535 | Dashboard surface — Law role enforcement audit | 1429–1434 | M00110 | dashboard | true |
| F00536 | Dashboard surface — Memory typing breakdown (6 types) | 1444–1451 | E0056 | dashboard | true |
| F00537 | Dashboard surface — MemoryRef metadata table | 1456–1465 | M00111 | dashboard | true |
| F00538 | Dashboard surface — Tool gate decision audit | 1497–1517 | M00112 | dashboard | true |
| F00539 | API `POST /v1/branches/spawn` | 1281 | M00098 | api_endpoint | true |
| F00540 | API `POST /v1/branches/<id>/retrieve` | 1284 | M00098 | api_endpoint | true |
| F00541 | API `POST /v1/branches/<id>/draft` | 1287 | M00098 | api_endpoint | true |
| F00542 | API `POST /v1/branches/<id>/filter` | 1290 | M00098 | api_endpoint | true |
| F00543 | API `POST /v1/branches/<id>/verify` | 1294 | M00098 | api_endpoint | true |
| F00544 | API `POST /v1/branches/<id>/act` | 1297 | M00098 | api_endpoint | true |
| F00545 | API `POST /v1/branches/<id>/commit` | 1300 | M00098 | api_endpoint | true |
| F00546 | API `POST /v1/branches/<id>/learn` | 1303 | M00098 | api_endpoint | true |
| F00547 | API `GET /v1/scheduler/tick` (next tick or current state) | 1326–1336 | M00100 | api_endpoint | true |
| F00548 | API `GET /v1/memory/types` | 1444–1451 | E0056 | api_endpoint | true |
| F00549 | API `GET /v1/memory/refs/<ref-id>` | 1456–1465 | M00111 | api_endpoint | true |
| F00550 | API `POST /v1/tools/<tool-id>/intent` | 1480–1494 | M00112 | api_endpoint | true |
| F00551 | Metric `sovereign_os_branch_lifecycle_steps_total{step}` | 1280–1304 | M00098 | observability_metric | true |
| F00552 | Metric `sovereign_os_avx_scheduler_compress_ratio` | 1338–1342 | M00102 | observability_metric | true |
| F00553 | Metric `sovereign_os_avx_scheduler_oracle_routed_total` | 1334 | M00100 | observability_metric | true |
| F00554 | Metric `sovereign_os_avx_scheduler_scout_routed_total` | 1335 | M00100 | observability_metric | true |
| F00555 | Metric `sovereign_os_avx_scheduler_tool_allowed_total` | 1336 | M00100 | observability_metric | true |
| F00556 | Metric `sovereign_os_branch_query_shell_allowed_total` | 1367 | M00104 | observability_metric | true |
| F00557 | Metric `sovereign_os_branch_query_file_write_allowed_total` | 1368 | M00104 | observability_metric | true |
| F00558 | Metric `sovereign_os_branch_query_json_required_total` | 1369 | M00104 | observability_metric | true |
| F00559 | Metric `sovereign_os_branch_query_verification_required_total` | 1370 | M00104 | observability_metric | true |
| F00560 | Metric `sovereign_os_branch_query_speculative_only_total` | 1371 | M00104 | observability_metric | true |
| F00561 | Metric `sovereign_os_branch_query_network_allowed_total` | 1372 | M00104 | observability_metric | true |
| F00562 | Metric `sovereign_os_epistemic_role_assignment{model,role}` (info gauge) | 1390–1434 | M00106 | observability_metric | true |
| F00563 | Metric `sovereign_os_memory_ref_count{type}` | 1444–1451 | E0056 | observability_metric | true |
| F00564 | Metric `sovereign_os_memory_ref_trust_distribution` (histogram) | 1456–1465 | M00111 | observability_metric | true |
| F00565 | Metric `sovereign_os_tool_intent_decisions_total{decision}` | 1497–1517 | M00112 | observability_metric | true |
| F00566 | Test — 8-step lifecycle deterministic across replays | 1280–1304 | M00098 | test | true |
| F00567 | Test — SoA fields aligned to 64-byte AVX-512 boundary | 1314–1324 | M00099 | test | true |
| F00568 | Test — AVX scheduler tick produces correct masks | 1326–1336 | M00100 | test | true |
| F00569 | Test — AVX compress preserves order of survivors | 1338–1342 | M00102 | test | true |
| F00570 | Test — control word composability — all 8 fields independently testable | 1355–1363 | M00103 | test | true |
| F00571 | Test — 6 branch queries return correct masks | 1366–1375 | M00104 | test | true |
| F00572 | Test — Oracle role enforces final-reasoning constraint | 1390–1404 | M00106 | test | true |
| F00573 | Test — Verifier role enforces accept/reject contract | 1399–1404 | M00107 | test | true |
| F00574 | Test — Scout role enforces draft-only contract | 1409–1414 | M00108 | test | true |
| F00575 | Test — Specialists role enforces per-task-class scope | 1418–1424 | M00109 | test | true |
| F00576 | Test — Law role enforces grammar/permission/budget/replay | 1429–1434 | M00110 | test | true |
| F00577 | Test — Memory 6 types correctly classified | 1444–1451 | E0056 | test | true |
| F00578 | Test — MemoryRef metadata round-trip | 1456–1465 | M00111 | test | true |
| F00579 | Test — Tool gate rejects forbidden combination | 1497–1517 | M00112 | test | true |
| F00580 | Lifecycle hook — pre-spawn enforce profile budget | 1281 | M00098 | lifecycle_hook | true |
| F00581 | Lifecycle hook — post-commit emit OTel completion span | 1300 | M00098 | lifecycle_hook | true |
| F00582 | Lifecycle hook — pre-tool-call enforce CPU permission check | 1497 | M00112 | lifecycle_hook | true |
| F00583 | Lifecycle hook — post-tool-call emit decision audit | 1500–1517 | M00112 | lifecycle_hook | true |
| F00584 | Lifecycle hook — pre-memory-write enforce admission policy | 1116 | M00111 | lifecycle_hook | true |
| F00585 | Lifecycle hook — post-memory-write emit OTel span | 1116 | M00111 | lifecycle_hook | true |
| F00586 | Composite — 8-step lifecycle end-to-end | 1280–1304 | composite: [M00098, M00099, M00100, M00102] | capability | true |
| F00587 | Composite — branch + control word + AVX scheduler | 1240–1342 | composite: [M00096, M00103, M00100] | capability | true |
| F00588 | Composite — epistemic role enforcement pipeline | 1390–1434 | composite: [M00106, M00107, M00108, M00109, M00110] | capability | true |
| F00589 | Composite — memory typed retrieval pipeline | 1444–1465 | composite: [M00111] | capability | true |
| F00590 | Composite — transactional tool gate pipeline | 1480–1517 | composite: [M00112] | capability | true |
| F00591 | Personalization — operator-defined lifecycle step ordering | 1280–1304 | M00098 | configuration | true |
| F00592 | Personalization — operator-defined branch SoA field layout | 1314–1324 | M00099 | configuration | true |
| F00593 | Personalization — operator-defined epistemic role per model | 1390–1434 | M00106 | configuration | true |
| F00594 | Personalization — operator-defined memory type extension | 1444–1451 | E0056 | configuration | true |
| F00595 | Personalization — operator-defined tool gate decision policy | 1497–1517 | M00112 | configuration | true |

## Requirements (R01021–R01190) — 170 requirements

| R ID | Phrase | Dump line | Parent F | Class | Opt-in | Sub-req min |
|---|---|---|---|---|---|---|
| R01021 | Branch is the smallest unit of cognition | 1240 | M00096 | non-negotiable | false | 10 |
| R01022 | Branch carries deterministic metadata only (no opaque pointers) | 1242 | M00096 | non-negotiable | false | 10 |
| R01023 | 8-step lifecycle order = Spawn → Retrieve → Draft → Filter → Verify → Act → Commit → Learn | 1280–1304 | F00511 | non-negotiable | false | 10 |
| R01024 | Profile `branch_lifecycle_strict` enforces all 8 steps mandatory | 1280–1304 | F00512 | non-negotiable | true | 10 |
| R01025 | Env var `SOVEREIGN_BRANCH_LIFECYCLE_STRICT` accepts boolean | 1280–1304 | F00513 | non-negotiable | true | 10 |
| R01026 | CLI `branch lifecycle <id>` returns JSON | 1280–1304 | F00514 | non-negotiable | true | 10 |
| R01027 | CLI `branch spawn` creates root branch with profile-default control word | 1281 | F00515 | non-negotiable | true | 10 |
| R01028 | CLI `branch retrieve` pulls context candidates into branch | 1284 | F00516 | non-negotiable | true | 10 |
| R01029 | CLI `branch draft` requests scout-side N continuations | 1287 | F00517 | non-negotiable | true | 10 |
| R01030 | CLI `branch filter` runs deterministic mask cascade | 1290 | F00518 | non-negotiable | true | 10 |
| R01031 | CLI `branch verify` routes to oracle for verification | 1294 | F00519 | non-negotiable | true | 10 |
| R01032 | CLI `branch act` executes tool intent under policy | 1297 | F00520 | non-negotiable | true | 10 |
| R01033 | CLI `branch commit` writes accepted state to replay log | 1300 | F00521 | non-negotiable | true | 10 |
| R01034 | CLI `branch learn` updates memory + routing stats + skills | 1303 | F00522 | non-negotiable | true | 10 |
| R01035 | Dashboard lifecycle timeline shows per-step latency | 1280–1304 | F00523 | non-negotiable | true | 10 |
| R01036 | Dashboard SoA inspector shows 8 arrays | 1314–1324 | F00524 | non-negotiable | true | 10 |
| R01037 | Dashboard AVX scheduler mask breakdown shows per-mask survivors per tick | 1326–1336 | F00525 | non-negotiable | true | 10 |
| R01038 | Dashboard branch-OS framing shows branch population analogy to process table | 1337 | F00526 | non-negotiable | true | 10 |
| R01039 | Dashboard AVX compress visualization shows sparse-to-dense transformation | 1338–1342 | F00527 | non-negotiable | true | 10 |
| R01040 | Dashboard control word composability inspector renders 8-field decomposition | 1355–1363 | F00528 | non-negotiable | true | 10 |
| R01041 | Dashboard branch queries audit shows per-query mask fire count | 1366–1375 | F00529 | non-negotiable | true | 10 |
| R01042 | Dashboard epistemic role assignment matrix shows model × role grid | 1390–1434 | F00530 | non-negotiable | true | 10 |
| R01043 | Dashboard Oracle role utilization shows oracle-only metric | 1390–1404 | F00531 | non-negotiable | true | 10 |
| R01044 | Dashboard Verifier role accept rate shows verifier-only metric | 1399–1404 | F00532 | non-negotiable | true | 10 |
| R01045 | Dashboard Scout role draft acceptance shows scout-only metric | 1409–1414 | F00533 | non-negotiable | true | 10 |
| R01046 | Dashboard Specialists per-task usage shows specialist breakdown | 1418–1424 | F00534 | non-negotiable | true | 10 |
| R01047 | Dashboard Law role enforcement audit shows per-rule fire count | 1429–1434 | F00535 | non-negotiable | true | 10 |
| R01048 | Dashboard Memory typing breakdown shows 6 types pie chart | 1444–1451 | F00536 | non-negotiable | true | 10 |
| R01049 | Dashboard MemoryRef metadata table shows trust × freshness × type × access × decay × flags | 1456–1465 | F00537 | non-negotiable | true | 10 |
| R01050 | Dashboard Tool gate decision audit shows per-tool intent × decision matrix | 1497–1517 | F00538 | non-negotiable | true | 10 |
| R01051 | API `POST /v1/branches/spawn` accepts profile_hint + initial_control | 1281 | F00539 | non-negotiable | true | 10 |
| R01052 | API `POST /v1/branches/<id>/retrieve` accepts query + memory_filter | 1284 | F00540 | non-negotiable | true | 10 |
| R01053 | API `POST /v1/branches/<id>/draft` accepts N + scout_model_id | 1287 | F00541 | non-negotiable | true | 10 |
| R01054 | API `POST /v1/branches/<id>/filter` accepts mask_set | 1290 | F00542 | non-negotiable | true | 10 |
| R01055 | API `POST /v1/branches/<id>/verify` accepts oracle_model_id | 1294 | F00543 | non-negotiable | true | 10 |
| R01056 | API `POST /v1/branches/<id>/act` accepts tool_intent | 1297 | F00544 | non-negotiable | true | 10 |
| R01057 | API `POST /v1/branches/<id>/commit` accepts accepted_state_hash | 1300 | F00545 | non-negotiable | true | 10 |
| R01058 | API `POST /v1/branches/<id>/learn` accepts experience_record | 1303 | F00546 | non-negotiable | true | 10 |
| R01059 | API `GET /v1/scheduler/tick` returns current tick or next-tick prediction | 1326–1336 | F00547 | non-negotiable | true | 10 |
| R01060 | API `GET /v1/memory/types` returns 6 named types | 1444–1451 | F00548 | non-negotiable | true | 10 |
| R01061 | API `GET /v1/memory/refs/<ref-id>` returns MemoryRef metadata | 1456–1465 | F00549 | non-negotiable | true | 10 |
| R01062 | API `POST /v1/tools/<tool-id>/intent` returns decision JSON | 1480–1494 | F00550 | non-negotiable | true | 10 |
| R01063 | Metric `sovereign_os_branch_lifecycle_steps_total` is Prometheus counter labeled by step | 1280–1304 | F00551 | non-negotiable | false | 10 |
| R01064 | Metric `sovereign_os_avx_scheduler_compress_ratio` is Prometheus gauge 0–1 | 1338–1342 | F00552 | non-negotiable | false | 10 |
| R01065 | Metric `sovereign_os_avx_scheduler_oracle_routed_total` is Prometheus counter | 1334 | F00553 | non-negotiable | false | 10 |
| R01066 | Metric `sovereign_os_avx_scheduler_scout_routed_total` is Prometheus counter | 1335 | F00554 | non-negotiable | false | 10 |
| R01067 | Metric `sovereign_os_avx_scheduler_tool_allowed_total` is Prometheus counter | 1336 | F00555 | non-negotiable | false | 10 |
| R01068 | Metric `sovereign_os_branch_query_shell_allowed_total` is Prometheus counter | 1367 | F00556 | non-negotiable | false | 10 |
| R01069 | Metric `sovereign_os_branch_query_file_write_allowed_total` is Prometheus counter | 1368 | F00557 | non-negotiable | false | 10 |
| R01070 | Metric `sovereign_os_branch_query_json_required_total` is Prometheus counter | 1369 | F00558 | non-negotiable | false | 10 |
| R01071 | Metric `sovereign_os_branch_query_verification_required_total` is Prometheus counter | 1370 | F00559 | non-negotiable | false | 10 |
| R01072 | Metric `sovereign_os_branch_query_speculative_only_total` is Prometheus counter | 1371 | F00560 | non-negotiable | false | 10 |
| R01073 | Metric `sovereign_os_branch_query_network_allowed_total` is Prometheus counter | 1372 | F00561 | non-negotiable | false | 10 |
| R01074 | Metric `sovereign_os_epistemic_role_assignment` is info gauge labeled by model + role | 1390–1434 | F00562 | non-negotiable | false | 10 |
| R01075 | Metric `sovereign_os_memory_ref_count` is Prometheus gauge labeled by type | 1444–1451 | F00563 | non-negotiable | false | 10 |
| R01076 | Metric `sovereign_os_memory_ref_trust_distribution` is Prometheus histogram | 1456–1465 | F00564 | non-negotiable | false | 10 |
| R01077 | Metric `sovereign_os_tool_intent_decisions_total` is Prometheus counter labeled by decision | 1497–1517 | F00565 | non-negotiable | false | 10 |
| R01078 | Test — 8-step lifecycle deterministic across replays under seeded RNG | 1280–1304 | F00566 | non-negotiable | false | 10 |
| R01079 | Test — SoA fields 64-byte aligned (AVX-512 alignment) | 1314–1324 | F00567 | non-negotiable | false | 10 |
| R01080 | Test — AVX scheduler tick produces alive_mask / risk_mask / oracle_mask / scout_mask / tool_mask / merge_mask correctly | 1326–1336 | F00568 | non-negotiable | false | 10 |
| R01081 | Test — AVX compress preserves order of survivors (first-fit) | 1338–1342 | F00569 | non-negotiable | false | 10 |
| R01082 | Test — control word 8 fields independently extractable and updatable | 1355–1363 | F00570 | non-negotiable | false | 10 |
| R01083 | Test — branch queries shell-allowed / file-write-allowed / JSON-required / verification-required / speculative-only / network-allowed return correct boolean | 1366–1375 | F00571 | non-negotiable | false | 10 |
| R01084 | Test — Oracle role rejects non-final-reasoning task | 1390–1404 | F00572 | non-negotiable | false | 10 |
| R01085 | Test — Verifier role returns accept/reject with reason | 1399–1404 | F00573 | non-negotiable | false | 10 |
| R01086 | Test — Scout role never commits state | 1409–1414 | F00574 | non-negotiable | false | 10 |
| R01087 | Test — Specialists role refuses out-of-scope task class | 1418–1424 | F00575 | non-negotiable | false | 10 |
| R01088 | Test — Law role enforces grammar + permission + budget + replay deterministically | 1429–1434 | F00576 | non-negotiable | false | 10 |
| R01089 | Test — Memory typing correctly classifies all 6 types via classifier | 1444–1451 | F00577 | non-negotiable | false | 10 |
| R01090 | Test — MemoryRef metadata bincode round-trip | 1456–1465 | F00578 | non-negotiable | false | 10 |
| R01091 | Test — Tool gate rejects forbidden combination (e.g., shell + write + network) | 1497–1517 | F00579 | non-negotiable | false | 10 |
| R01092 | Lifecycle hook `pre-spawn` enforces profile budget cap | 1281 | F00580 | non-negotiable | true | 10 |
| R01093 | Lifecycle hook `post-commit` emits OTel completion span with branch_id + final_state_hash | 1300 | F00581 | non-negotiable | false | 10 |
| R01094 | Lifecycle hook `pre-tool-call` enforces CPU permission mask | 1497 | F00582 | non-negotiable | false | 10 |
| R01095 | Lifecycle hook `post-tool-call` emits decision audit | 1500–1517 | F00583 | non-negotiable | false | 10 |
| R01096 | Lifecycle hook `pre-memory-write` enforces admission policy | 1116 | F00584 | non-negotiable | false | 10 |
| R01097 | Lifecycle hook `post-memory-write` emits OTel span | 1116 | F00585 | non-negotiable | false | 10 |
| R01098 | Composite F00586 8-step lifecycle requires modules M00098 + M00099 + M00100 + M00102 | 1280–1304 | F00586 | non-negotiable | false | 10 |
| R01099 | Composite F00587 branch + control word + AVX scheduler requires modules M00096 + M00103 + M00100 | 1240–1342 | F00587 | non-negotiable | false | 10 |
| R01100 | Composite F00588 epistemic role enforcement requires modules M00106 + M00107 + M00108 + M00109 + M00110 | 1390–1434 | F00588 | non-negotiable | false | 10 |
| R01101 | Composite F00589 memory typed retrieval requires module M00111 | 1444–1465 | F00589 | non-negotiable | false | 10 |
| R01102 | Composite F00590 transactional tool gate requires module M00112 | 1480–1517 | F00590 | non-negotiable | false | 10 |
| R01103 | Personalization — operator-defined lifecycle step ordering via YAML | 1280–1304 | F00591 | non-negotiable | true | 10 |
| R01104 | Personalization — operator-defined branch SoA field layout via YAML | 1314–1324 | F00592 | non-negotiable | true | 10 |
| R01105 | Personalization — operator-defined epistemic role per model via YAML | 1390–1434 | F00593 | non-negotiable | true | 10 |
| R01106 | Personalization — operator-defined memory type extension via YAML | 1444–1451 | F00594 | non-negotiable | true | 10 |
| R01107 | Personalization — operator-defined tool gate decision policy via YAML | 1497–1517 | F00595 | non-negotiable | true | 10 |
| R01108 | Branch lifecycle step 1 Spawn — create branch from user task | 1281 | M00098 | non-negotiable | false | 10 |
| R01109 | Branch lifecycle step 2 Retrieve — pull relevant memory/code/context | 1284 | M00098 | non-negotiable | false | 10 |
| R01110 | Branch lifecycle step 3 Draft — 3090 proposes several continuations or plans | 1287 | M00098 | non-negotiable | false | 10 |
| R01111 | Branch lifecycle step 4 Filter — CPU applies grammar / budget / risk / permissions / duplication masks | 1290 | M00098 | non-negotiable | false | 10 |
| R01112 | Branch lifecycle step 5 Verify — RTX PRO validates or improves high-value branches | 1294 | M00098 | non-negotiable | false | 10 |
| R01113 | Branch lifecycle step 6 Act — tool calls happen only if CPU policy allows | 1297 | M00098 | non-negotiable | false | 10 |
| R01114 | Branch lifecycle step 7 Commit — accepted branch state written to replay log | 1300 | M00098 | non-negotiable | false | 10 |
| R01115 | Branch lifecycle step 8 Learn — update memory, scores, branch priors, failure records | 1303 | M00098 | non-negotiable | false | 10 |
| R01116 | SoA field array `id[N]` u64 | 1316 | M00099 | non-negotiable | false | 10 |
| R01117 | SoA field array `control[N]` u64 | 1317 | M00099 | non-negotiable | false | 10 |
| R01118 | SoA field array `budget[N]` u64 | 1318 | M00099 | non-negotiable | false | 10 |
| R01119 | SoA field array `score[N]` u64 | 1319 | M00099 | non-negotiable | false | 10 |
| R01120 | SoA field array `flags[N]` u64 | 1320 | M00099 | non-negotiable | false | 10 |
| R01121 | SoA field array `grammar[N]` u64 | 1321 | M00099 | non-negotiable | false | 10 |
| R01122 | SoA field array `memory[N]` u64 | 1322 | M00099 | non-negotiable | false | 10 |
| R01123 | SoA field array `route[N]` u64 | 1323 | M00099 | non-negotiable | false | 10 |
| R01124 | AVX tick op `budget -= cost` | 1328 | M00100 | non-negotiable | false | 10 |
| R01125 | AVX tick op `dead_mask = budget == 0` | 1329 | M00100 | non-negotiable | false | 10 |
| R01126 | AVX tick op `risk_mask = risk > threshold` | 1330 | M00100 | non-negotiable | false | 10 |
| R01127 | AVX tick op `oracle_mask = confidence_low & value_high` | 1331 | M00100 | non-negotiable | false | 10 |
| R01128 | AVX tick op `scout_mask = confidence_medium & cost_low` | 1332 | M00100 | non-negotiable | false | 10 |
| R01129 | AVX tick op `tool_mask = tool_requested & tool_allowed` | 1333 | M00100 | non-negotiable | false | 10 |
| R01130 | AVX tick op `merge_mask = similarity_high` | 1334 | M00100 | non-negotiable | false | 10 |
| R01131 | AVX pack compress survivors into dense GPU batches | 1338–1342 | M00102 | non-negotiable | false | 10 |
| R01132 | AVX pack target — GPU likes batches; CPU turns chaotic thought into dense GPU work | 1338–1347 | M00102 | non-negotiable | false | 10 |
| R01133 | Composable control word field `route` = control & 0xF | 1356 | M00103 | non-negotiable | false | 10 |
| R01134 | Composable control word field `task` = (control >> 4) & 0xF | 1357 | M00103 | non-negotiable | false | 10 |
| R01135 | Composable control word field `risk` = (control >> 8) & 0xFF | 1358 | M00103 | non-negotiable | false | 10 |
| R01136 | Composable control word field `permissions` = (control >> 16) & 0xFFFF | 1359 | M00103 | non-negotiable | false | 10 |
| R01137 | Composable control word field `grammar` = (control >> 32) & 0xFF | 1360 | M00103 | non-negotiable | false | 10 |
| R01138 | Composable control word field `priority` = (control >> 40) & 0xFF | 1361 | M00103 | non-negotiable | false | 10 |
| R01139 | Composable control word field `spec_depth` = (control >> 48) & 0xFF | 1362 | M00103 | non-negotiable | false | 10 |
| R01140 | Composable control word field `flags` = (control >> 56) & 0xFF | 1363 | M00103 | non-negotiable | false | 10 |
| R01141 | Branch query `which branches may use shell?` AVX-512 single-pass | 1367 | M00104 | non-negotiable | false | 10 |
| R01142 | Branch query `which branches may write files?` AVX-512 single-pass | 1368 | M00104 | non-negotiable | false | 10 |
| R01143 | Branch query `which branches require JSON?` AVX-512 single-pass | 1369 | M00104 | non-negotiable | false | 10 |
| R01144 | Branch query `which branches must be verified?` AVX-512 single-pass | 1370 | M00104 | non-negotiable | false | 10 |
| R01145 | Branch query `which branches are speculative only?` AVX-512 single-pass | 1371 | M00104 | non-negotiable | false | 10 |
| R01146 | Branch query `which branches are allowed to call network?` AVX-512 single-pass | 1372 | M00104 | non-negotiable | false | 10 |
| R01147 | Epistemic role Oracle — final reasoning / hard synthesis / verification / architecture decisions / long context | 1390–1404 | M00106 | non-negotiable | false | 10 |
| R01148 | Epistemic role Verifier — checks claims / code diffs / tool plans / may be oracle with different prompt | 1399–1404 | M00107 | non-negotiable | false | 10 |
| R01149 | Epistemic role Scout — cheap exploration / generate options / draft continuations | 1409–1414 | M00108 | non-negotiable | false | 10 |
| R01150 | Epistemic role Specialists — embeddings / reranking / code-local edits / vision / classification / safety-risk tagging | 1418–1424 | M00109 | non-negotiable | false | 10 |
| R01151 | Epistemic role Law — finite-state machines / grammar / token masks / permission masks / deterministic tests / scheduler / replay | 1429–1434 | M00110 | non-negotiable | false | 10 |
| R01152 | Memory typing 6 types — episodic / semantic / procedural / project / policy / trace | 1444–1451 | E0056 | non-negotiable | false | 10 |
| R01153 | Memory type `episodic` — what happened | 1445 | E0056 | non-negotiable | false | 10 |
| R01154 | Memory type `semantic` — facts and summaries | 1446 | E0056 | non-negotiable | false | 10 |
| R01155 | Memory type `procedural` — how to do things | 1447 | E0056 | non-negotiable | false | 10 |
| R01156 | Memory type `project` — repo-specific knowledge | 1448 | E0056 | non-negotiable | false | 10 |
| R01157 | Memory type `policy` — user preferences and hard rules | 1449 | E0056 | non-negotiable | false | 10 |
| R01158 | Memory type `trace` — branch/replay history | 1450 | E0056 | non-negotiable | false | 10 |
| R01159 | MemoryRef struct field `id` u64 | 1457 | M00111 | non-negotiable | false | 10 |
| R01160 | MemoryRef struct field `type` u64 | 1458 | M00111 | non-negotiable | false | 10 |
| R01161 | MemoryRef struct field `embedding_ref` u64 | 1459 | M00111 | non-negotiable | false | 10 |
| R01162 | MemoryRef struct field `trust` u64 | 1460 | M00111 | non-negotiable | false | 10 |
| R01163 | MemoryRef struct field `freshness` u64 | 1461 | M00111 | non-negotiable | false | 10 |
| R01164 | MemoryRef struct field `access_count` u64 | 1462 | M00111 | non-negotiable | false | 10 |
| R01165 | MemoryRef struct field `decay` u64 | 1463 | M00111 | non-negotiable | false | 10 |
| R01166 | MemoryRef struct field `flags` u64 | 1464 | M00111 | non-negotiable | false | 10 |
| R01167 | CPU memory op `admit this memory` | 1473 | M00111 | non-negotiable | false | 10 |
| R01168 | CPU memory op `evict this one` | 1474 | M00111 | non-negotiable | false | 10 |
| R01169 | CPU memory op `summarize this cluster` | 1475 | M00111 | non-negotiable | false | 10 |
| R01170 | CPU memory op `ask 3090 to rerank` | 1476 | M00111 | non-negotiable | false | 10 |
| R01171 | CPU memory op `ask oracle to resolve conflict` | 1477 | M00111 | non-negotiable | false | 10 |
| R01172 | Tool intent JSON schema — tool / intent / command / writes / network | 1486–1494 | M00112 | non-negotiable | false | 10 |
| R01173 | Tool gate check — permission bits | 1498 | M00112 | non-negotiable | false | 10 |
| R01174 | Tool gate check — workspace policy | 1499 | M00112 | non-negotiable | false | 10 |
| R01175 | Tool gate check — branch budget | 1500 | M00112 | non-negotiable | false | 10 |
| R01176 | Tool gate check — risk class | 1501 | M00112 | non-negotiable | false | 10 |
| R01177 | Tool gate check — current mode | 1502 | M00112 | non-negotiable | false | 10 |
| R01178 | Tool gate check — required confirmation | 1503 | M00112 | non-negotiable | false | 10 |
| R01179 | Tool gate decision — executes | 1509 | M00112 | non-negotiable | false | 10 |
| R01180 | Tool gate decision — asks user | 1510 | M00112 | non-negotiable | false | 10 |
| R01181 | Tool gate decision — rewrites into safe plan | 1511 | M00112 | non-negotiable | false | 10 |
| R01182 | Tool gate decision — rejects | 1512 | M00112 | non-negotiable | false | 10 |
| R01183 | Tool gate decision — routes to sandbox | 1513 | M00112 | non-negotiable | false | 10 |
| R01184 | Big pattern — model proposes state transitions / CPU commits state transitions | 1525–1530 | M00081 | non-negotiable | false | 10 |
| R01185 | Always-on control work — thousands of branch states / millions of memory flags / 512-bit token masks / packed permission checks / branch compaction / priority filtering / grammar-state batches / duplicate detection sketches | 1552–1562 | M00100 | non-negotiable | false | 10 |
| R01186 | Spec artifact DCR v0 objects — Branch / Candidate / MemoryRef / ToolIntent / Verification / Commit | 1576–1581 | M00111 | non-negotiable | false | 10 |
| R01187 | Spec artifact DCR v0 services — Scheduler / Grammar Engine / Policy Engine / Memory Router / GPU Router / Replay Log | 1583–1588 | M00100 | non-negotiable | false | 10 |
| R01188 | Spec artifact DCR v0 guarantees — bounded budgets / replayable decisions / schema-valid tool calls / deterministic permissioning / no uncommitted side effects / oracle used only for high-value work | 1591–1597 | M00081 | non-negotiable | false | 10 |
| R01189 | Spec artifact DCR v0 is the foundation; once it exists, hardware finally has something worthy to do | 1599 | M00081 | non-negotiable | false | 10 |
| R01190 | Branch state transitions immutable in replay log; content-addressed via blake3 | 1260–1304 | M00098 | non-negotiable | false | 10 |

— End of M007 milestone file.
