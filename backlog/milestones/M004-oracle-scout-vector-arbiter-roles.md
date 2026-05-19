# M004 — Oracle / Scout / Vector Arbiter role split

> Parent: `backlog/milestones/INDEX.md` row M004 (dump 566–722).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 566–722.
> All entries below extracted from the dump line range. No invention.

## Epics (E0032–E0040)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0032 | Oracle Core = RTX PRO 6000 — deep resident model / final verification / high-quality generation | 590 |
| E0033 | Scout = RTX 3090 — draft / sandbox / side models | 591 |
| E0034 | Vector Arbiter = Ryzen 9900X AVX-512 — control plane | 592 |
| E0035 | Memory Plane = 256GB DDR5 — working memory + queues + context arena | 593 |
| E0036 | Storage Plane = NVMe/ZFS — replay + datasets + checkpoints + cold memory | 594 |
| E0037 | Move decisions/tokens/summaries — not tensors/KV/activations | 526–545 |
| E0038 | Speculative decoding pipeline — 3090 drafts → CPU filters → Blackwell verifies | 470–488 |
| E0039 | Constraint automata — model = creative engine / CPU = deterministic law | 911–933 |
| E0040 | Bitset routing — 512 candidate memories per ZMM | 935–943 |

## Modules (M00045–M00061) — 17 modules

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00045 | Oracle Core resident-model warmth invariant | 415–423 | E0032 |
| M00046 | Oracle Core epistemic role — final synthesis / hard reasoning / high-risk verification / long-context | 1390–1404 | E0032 |
| M00047 | Oracle Core avoid-list — cheap classification / trivial rewrites / noisy branch expansion / repeated boilerplate prefill | 18055–18060 | E0032 |
| M00048 | Scout role — draft tokens / candidate branches / embeddings / rerank scores / tool decisions / vision captions / classification labels / summaries | 619–627 | E0033 |
| M00049 | Scout work-ahead invariant — 3090 dreams / RTX PRO judges | 985–989 | E0033 |
| M00050 | Scout backpressure — reduce branch width when 3090 busy | 18181–18186 | E0033 |
| M00051 | Vector Arbiter / Cortex — branch state + masks + budgets + routing + scoring | 731–739 | E0034 |
| M00052 | Cortex u64 lane field assignments — agent type / confidence / budget / risk / memory pointer / flags / grammar / mode | 456–465 | E0034 |
| M00053 | Cortex law — invalid token masks / forbidden tool rejection / branch expiry / schema enforcement / memory admission / GPU routing | 1098–1104 | E0034 |
| M00054 | Memory Plane — 256GB DDR5 working memory + queues + context arena | 519 | E0035 |
| M00055 | Memory Plane ARC tuning — ZFS ARC headroom | 219 | E0035 |
| M00056 | Storage Plane — NVMe + ZFS replay logs + datasets + checkpoints + cold memory | 522 | E0036 |
| M00057 | Storage Plane RAID-0 caveat — scratch / cache / datasets / artifacts only | 343–344 | E0036 |
| M00058 | Boundary transport policy — compact symbols only (tokens / scores / refs / summaries) | 526–536 | E0037 |
| M00059 | Boundary transport prohibition — KV tensors / activations / layer-split / constant sync | 540–547 | E0037 |
| M00060 | Speculative decode chunk loop — 3090 drafts N tokens × N branches / CPU filter / RTX PRO verify | 480–488 | E0038 |
| M00061 | Per-branch contract masks — citations / code-mode / no-tools / JSON-grammar / risky-alternative / compress / N-step terminate | 492–502 | E0039 |

## Features (F00256–F00340) — 85 features

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00256 | Toggle Oracle-Core warm-keep mode | 415–423 | M00045 | mode | true |
| F00257 | Profile knob — `oracle_core_warm_keep_enabled` | 415–423 | M00045 | profile | true |
| F00258 | Env var `SOVEREIGN_ORACLE_WARM_KEEP_ENABLED` | 415–423 | M00045 | env_var | true |
| F00259 | CLI `sovereign-osctl oracle status` | 415–423 | M00046 | cli_verb | true |
| F00260 | CLI `sovereign-osctl oracle route <task-id>` | 1390–1404 | M00046 | cli_verb | true |
| F00261 | Dashboard surface — Oracle utilization + queue depth + idle ms | 590 | M00046 | dashboard | true |
| F00262 | API `POST /v1/oracle/verify` — Anthropic-tool-compatible | 590 | M00046 | api_endpoint | true |
| F00263 | API `POST /v1/oracle/synthesize` — long-context final reasoning | 1390–1404 | M00046 | api_endpoint | true |
| F00264 | Metric `sovereign_os_oracle_utilization_pct` | 590 | M00046 | observability_metric | true |
| F00265 | Metric `sovereign_os_oracle_idle_ms` | 590 | M00046 | observability_metric | true |
| F00266 | Metric `sovereign_os_oracle_verification_accept_rate` | 590 | M00046 | observability_metric | true |
| F00267 | Test — Oracle protected from cheap-classification work | 18055–18060 | M00047 | test | true |
| F00268 | Test — Oracle protected from trivial-rewrites work | 18055–18060 | M00047 | test | true |
| F00269 | Test — Oracle protected from noisy-branch-expansion work | 18055–18060 | M00047 | test | true |
| F00270 | Test — Oracle protected from repeated-boilerplate-prefill | 18055–18060 | M00047 | test | true |
| F00271 | Lifecycle hook — pre-Oracle call verify task class is not in avoid-list | 18055–18060 | M00047 | lifecycle_hook | true |
| F00272 | Lifecycle hook — pre-Oracle call enforce branch budget | 590 | M00046 | lifecycle_hook | true |
| F00273 | Lifecycle hook — post-Oracle log verification accept/reject | 590 | M00046 | lifecycle_hook | true |
| F00274 | Composite — Oracle warm-keep + scout draft pipeline | 470–488 | composite: [M00045, M00060] | capability | true |
| F00275 | Personalization — operator-defined Oracle avoid-list | 18055–18060 | M00047 | configuration | true |
| F00276 | Personalization — operator-defined Oracle warm-keep model name | 415–423 | M00045 | configuration | true |
| F00277 | Toggle Scout draft-generation mode | 619–627 | M00048 | mode | true |
| F00278 | Profile knob — `scout_draft_width` (8 / 16 / 32 / 64) | 619 | M00048 | profile | true |
| F00279 | Env var `SOVEREIGN_SCOUT_DRAFT_WIDTH` | 619 | M00048 | env_var | true |
| F00280 | CLI `sovereign-osctl scout status` | 619–627 | M00048 | cli_verb | true |
| F00281 | CLI `sovereign-osctl scout draft <task-id> --width N` | 619–627 | M00048 | cli_verb | true |
| F00282 | Dashboard surface — Scout utilization + draft tokens/sec + acceptance rate | 619 | M00048 | dashboard | true |
| F00283 | API `POST /v1/scout/draft` — produce N candidate continuations | 619 | M00048 | api_endpoint | true |
| F00284 | API `POST /v1/scout/embed` | 619 | M00048 | api_endpoint | true |
| F00285 | API `POST /v1/scout/rerank` | 619 | M00048 | api_endpoint | true |
| F00286 | API `POST /v1/scout/perceive` | 619 | M00048 | api_endpoint | true |
| F00287 | API `POST /v1/scout/classify` | 619 | M00048 | api_endpoint | true |
| F00288 | Metric `sovereign_os_scout_utilization_pct` | 619 | M00048 | observability_metric | true |
| F00289 | Metric `sovereign_os_scout_draft_tokens_per_sec` | 619 | M00048 | observability_metric | true |
| F00290 | Metric `sovereign_os_scout_draft_acceptance_rate` | 619 | M00048 | observability_metric | true |
| F00291 | Metric `sovereign_os_scout_rejection_reason{reason}` | 619 | M00048 | observability_metric | true |
| F00292 | Test — Scout works ahead when 3090 idle | 985–989 | M00049 | test | true |
| F00293 | Test — Scout reduces branch width under backpressure | 18181–18186 | M00050 | test | true |
| F00294 | Lifecycle hook — pre-Scout draft enforce per-branch budget | 619 | M00048 | lifecycle_hook | true |
| F00295 | Lifecycle hook — post-Scout draft emit OTel span | 619 | M00048 | lifecycle_hook | true |
| F00296 | Composite — speculative-decode chunk loop (Scout drafts → Cortex filters → Oracle verifies) | 470–488 | composite: [M00060, M00048, M00046] | capability | true |
| F00297 | Personalization — operator-defined Scout model registry | 619 | M00048 | configuration | true |
| F00298 | Personalization — operator-defined Scout draft model per task class | 619 | M00048 | configuration | true |
| F00299 | Toggle Vector-Arbiter / Cortex enabled | 731–739 | M00051 | mode | true |
| F00300 | Profile knob — `cortex_avx512_enabled` | 731–739 | M00051 | profile | true |
| F00301 | Env var `SOVEREIGN_CORTEX_AVX512_ENABLED` | 731–739 | M00051 | env_var | true |
| F00302 | CLI `sovereign-osctl cortex status` | 731–739 | M00051 | cli_verb | true |
| F00303 | CLI `sovereign-osctl cortex branches list` | 731–739 | M00051 | cli_verb | true |
| F00304 | CLI `sovereign-osctl cortex branches show <id>` | 731–739 | M00051 | cli_verb | true |
| F00305 | Dashboard surface — Cortex branch table (live) | 731–739 | M00051 | dashboard | true |
| F00306 | Dashboard surface — Cortex routing decision audit | 1098–1104 | M00053 | dashboard | true |
| F00307 | API `GET /v1/cortex/branches` | 731–739 | M00051 | api_endpoint | true |
| F00308 | API `POST /v1/cortex/branches` | 731–739 | M00051 | api_endpoint | true |
| F00309 | API `DELETE /v1/cortex/branches/<id>` | 731–739 | M00051 | api_endpoint | true |
| F00310 | Metric `sovereign_os_cortex_branches_active` | 731–739 | M00051 | observability_metric | true |
| F00311 | Metric `sovereign_os_cortex_branches_killed_budget` | 1098–1104 | M00053 | observability_metric | true |
| F00312 | Metric `sovereign_os_cortex_branches_killed_policy` | 1098–1104 | M00053 | observability_metric | true |
| F00313 | Metric `sovereign_os_cortex_branches_killed_grammar` | 1098–1104 | M00053 | observability_metric | true |
| F00314 | Metric `sovereign_os_cortex_branches_sent_oracle` | 1098–1104 | M00053 | observability_metric | true |
| F00315 | Metric `sovereign_os_cortex_branches_sent_scout` | 1098–1104 | M00053 | observability_metric | true |
| F00316 | Metric `sovereign_os_cortex_avx_tick_us` | 731–739 | M00051 | observability_metric | true |
| F00317 | Test — Cortex tick processes 8 branches per AVX-512 vector | 731–739 | M00051 | test | true |
| F00318 | Test — Cortex masks invalid tokens before model inference | 1098–1104 | M00053 | test | true |
| F00319 | Test — Cortex rejects forbidden tool intents | 1098–1104 | M00053 | test | true |
| F00320 | Test — Cortex expires branches at budget = 0 | 1098–1104 | M00053 | test | true |
| F00321 | Lifecycle hook — pre-tick Cortex emit branch snapshot | 731–739 | M00051 | lifecycle_hook | true |
| F00322 | Lifecycle hook — post-tick Cortex emit branch state transitions | 731–739 | M00051 | lifecycle_hook | true |
| F00323 | Composite — Oracle + Scout + Cortex three-organ pipeline | 590–592 | composite: [M00046, M00048, M00051] | capability | true |
| F00324 | Personalization — operator-defined Cortex tick budget per profile | 731–739 | M00051 | configuration | true |
| F00325 | Toggle Memory Plane 256GB target mode | 519 | M00054 | mode | true |
| F00326 | Profile knob — `memory_plane_target_gib` | 519 | M00054 | profile | true |
| F00327 | Env var `SOVEREIGN_MEMORY_PLANE_TARGET_GIB` | 519 | M00054 | env_var | true |
| F00328 | Dashboard surface — Memory Plane utilization + ARC hit rate | 519 | M00055 | dashboard | true |
| F00329 | Metric `sovereign_os_memory_plane_working_used_bytes` | 519 | M00054 | observability_metric | true |
| F00330 | Metric `sovereign_os_memory_plane_arc_hit_rate` | 219 | M00055 | observability_metric | true |
| F00331 | Toggle Storage Plane ZFS replay mode | 522 | M00056 | mode | true |
| F00332 | Profile knob — `storage_plane_replay_retention_days` | 522 | M00056 | profile | true |
| F00333 | Env var `SOVEREIGN_STORAGE_REPLAY_RETENTION_DAYS` | 522 | M00056 | env_var | true |
| F00334 | Dashboard surface — Storage Plane usage by dataset | 343 | M00056 | dashboard | true |
| F00335 | Metric `sovereign_os_storage_plane_dataset_used_bytes{dataset}` | 343 | M00056 | observability_metric | true |
| F00336 | Boundary transport — only compact symbols mode | 526–536 | M00058 | mode | true |
| F00337 | Boundary transport — strict no-tensor mode | 540–547 | M00059 | mode | true |
| F00338 | Test — boundary transport rejects KV tensor payload | 540–547 | M00059 | test | true |
| F00339 | Test — boundary transport rejects activation tensor payload | 540–547 | M00059 | test | true |
| F00340 | Composite — speculative chunk pipeline with constraint automata enforcement | 470–502 | composite: [M00060, M00061, M00053] | capability | true |

## Requirements (R00511–R00680) — 170 requirements

| R ID | Phrase | Dump line | Parent F | Class | Opt-in | Sub-req min |
|---|---|---|---|---|---|---|
| R00511 | Oracle Core warm-keep keeps resident model loaded across requests | 415–423 | F00256 | non-negotiable | true | 10 |
| R00512 | Oracle Core warm-keep disabled by default; opt-in per profile | 415–423 | F00256 | non-negotiable | true | 10 |
| R00513 | Profile `oracle_core_warm_keep_enabled` accepts boolean | 415–423 | F00257 | non-negotiable | true | 10 |
| R00514 | Env var `SOVEREIGN_ORACLE_WARM_KEEP_ENABLED` accepts boolean | 415–423 | F00258 | non-negotiable | true | 10 |
| R00515 | CLI `oracle status` returns JSON when `--json` set | 415–423 | F00259 | non-negotiable | true | 10 |
| R00516 | CLI `oracle route <task-id>` enqueues task for Oracle execution | 1390–1404 | F00260 | non-negotiable | true | 10 |
| R00517 | Dashboard Oracle card shows utilization / queue depth / idle ms | 590 | F00261 | non-negotiable | true | 10 |
| R00518 | API `POST /v1/oracle/verify` accepts model_call schema | 590 | F00262 | non-negotiable | true | 10 |
| R00519 | API `POST /v1/oracle/synthesize` accepts long-context final reasoning request | 1390–1404 | F00263 | non-negotiable | true | 10 |
| R00520 | Metric `sovereign_os_oracle_utilization_pct` is Prometheus gauge 0–100 | 590 | F00264 | non-negotiable | false | 10 |
| R00521 | Metric `sovereign_os_oracle_idle_ms` is Prometheus gauge | 590 | F00265 | non-negotiable | false | 10 |
| R00522 | Metric `sovereign_os_oracle_verification_accept_rate` is Prometheus gauge 0–1 | 590 | F00266 | non-negotiable | false | 10 |
| R00523 | Test — Oracle rejects cheap-classification tasks when avoid-list active | 18055–18060 | F00267 | non-negotiable | true | 10 |
| R00524 | Test — Oracle rejects trivial-rewrite tasks when avoid-list active | 18055–18060 | F00268 | non-negotiable | true | 10 |
| R00525 | Test — Oracle rejects noisy-branch-expansion when avoid-list active | 18055–18060 | F00269 | non-negotiable | true | 10 |
| R00526 | Test — Oracle rejects repeated-boilerplate-prefill when avoid-list active | 18055–18060 | F00270 | non-negotiable | true | 10 |
| R00527 | Lifecycle hook `pre-Oracle` aborts on task class match against avoid-list | 18055–18060 | F00271 | non-negotiable | true | 10 |
| R00528 | Lifecycle hook `pre-Oracle` enforces per-branch budget | 590 | F00272 | non-negotiable | true | 10 |
| R00529 | Lifecycle hook `post-Oracle` logs accept/reject + reason | 590 | F00273 | non-negotiable | false | 10 |
| R00530 | Composite F00274 Oracle warm-keep + scout draft requires modules M00045 + M00060 | 470–488 | F00274 | non-negotiable | false | 10 |
| R00531 | Personalization — operator can extend Oracle avoid-list via YAML | 18055–18060 | F00275 | non-negotiable | true | 10 |
| R00532 | Personalization — operator selects Oracle warm-keep model | 415–423 | F00276 | non-negotiable | true | 10 |
| R00533 | Scout draft generation produces N candidate continuations | 619 | F00277 | non-negotiable | false | 10 |
| R00534 | Profile `scout_draft_width` accepts 8 / 16 / 32 / 64 | 619 | F00278 | non-negotiable | true | 10 |
| R00535 | Env var `SOVEREIGN_SCOUT_DRAFT_WIDTH` accepts 8 / 16 / 32 / 64 | 619 | F00279 | non-negotiable | true | 10 |
| R00536 | CLI `scout status` returns JSON | 619 | F00280 | non-negotiable | true | 10 |
| R00537 | CLI `scout draft <task-id> --width N` enqueues N drafts | 619 | F00281 | non-negotiable | true | 10 |
| R00538 | Dashboard Scout card shows draft tokens/sec + acceptance rate | 619 | F00282 | non-negotiable | true | 10 |
| R00539 | API `POST /v1/scout/draft` returns N candidate continuations | 619 | F00283 | non-negotiable | true | 10 |
| R00540 | API `POST /v1/scout/embed` returns embedding vector | 619 | F00284 | non-negotiable | true | 10 |
| R00541 | API `POST /v1/scout/rerank` returns ranked scores | 619 | F00285 | non-negotiable | true | 10 |
| R00542 | API `POST /v1/scout/perceive` returns parsed UI state | 619 | F00286 | non-negotiable | true | 10 |
| R00543 | API `POST /v1/scout/classify` returns label + confidence | 619 | F00287 | non-negotiable | true | 10 |
| R00544 | Metric `sovereign_os_scout_utilization_pct` is Prometheus gauge 0–100 | 619 | F00288 | non-negotiable | false | 10 |
| R00545 | Metric `sovereign_os_scout_draft_tokens_per_sec` is Prometheus counter | 619 | F00289 | non-negotiable | false | 10 |
| R00546 | Metric `sovereign_os_scout_draft_acceptance_rate` is Prometheus gauge | 619 | F00290 | non-negotiable | false | 10 |
| R00547 | Metric `sovereign_os_scout_rejection_reason` is Prometheus counter labeled by reason | 619 | F00291 | non-negotiable | false | 10 |
| R00548 | Test — Scout produces drafts when 3090 idle and oracle busy | 985–989 | F00292 | non-negotiable | false | 10 |
| R00549 | Test — Scout draft width reduces under backpressure | 18181–18186 | F00293 | non-negotiable | false | 10 |
| R00550 | Lifecycle hook `pre-Scout draft` enforces per-branch budget | 619 | F00294 | non-negotiable | true | 10 |
| R00551 | Lifecycle hook `post-Scout draft` emits OTel span with token count + latency | 619 | F00295 | non-negotiable | false | 10 |
| R00552 | Composite F00296 speculative chunk loop requires modules M00060 + M00048 + M00046 | 470–488 | F00296 | non-negotiable | false | 10 |
| R00553 | Personalization — operator can register Scout models via YAML | 619 | F00297 | non-negotiable | true | 10 |
| R00554 | Personalization — operator binds Scout draft model per task class | 619 | F00298 | non-negotiable | true | 10 |
| R00555 | Cortex enabled controls AVX-512 branch table processing | 731–739 | F00299 | non-negotiable | true | 10 |
| R00556 | Profile `cortex_avx512_enabled` accepts boolean | 731–739 | F00300 | non-negotiable | true | 10 |
| R00557 | Env var `SOVEREIGN_CORTEX_AVX512_ENABLED` accepts boolean | 731–739 | F00301 | non-negotiable | true | 10 |
| R00558 | CLI `cortex status` returns JSON | 731–739 | F00302 | non-negotiable | true | 10 |
| R00559 | CLI `cortex branches list` returns active branch table | 731–739 | F00303 | non-negotiable | true | 10 |
| R00560 | CLI `cortex branches show <id>` returns single-branch detail | 731–739 | F00304 | non-negotiable | true | 10 |
| R00561 | Dashboard Cortex branch table refreshes via SSE | 731–739 | F00305 | non-negotiable | true | 10 |
| R00562 | Dashboard Cortex routing decision audit shows per-branch route + reason | 1098–1104 | F00306 | non-negotiable | true | 10 |
| R00563 | API `GET /v1/cortex/branches` returns JSON branch list | 731–739 | F00307 | non-negotiable | true | 10 |
| R00564 | API `POST /v1/cortex/branches` creates a new branch | 731–739 | F00308 | non-negotiable | true | 10 |
| R00565 | API `DELETE /v1/cortex/branches/<id>` kills a branch | 731–739 | F00309 | non-negotiable | true | 10 |
| R00566 | Metric `sovereign_os_cortex_branches_active` is Prometheus gauge | 731–739 | F00310 | non-negotiable | false | 10 |
| R00567 | Metric `sovereign_os_cortex_branches_killed_budget` is Prometheus counter | 1098–1104 | F00311 | non-negotiable | false | 10 |
| R00568 | Metric `sovereign_os_cortex_branches_killed_policy` is Prometheus counter | 1098–1104 | F00312 | non-negotiable | false | 10 |
| R00569 | Metric `sovereign_os_cortex_branches_killed_grammar` is Prometheus counter | 1098–1104 | F00313 | non-negotiable | false | 10 |
| R00570 | Metric `sovereign_os_cortex_branches_sent_oracle` is Prometheus counter | 1098–1104 | F00314 | non-negotiable | false | 10 |
| R00571 | Metric `sovereign_os_cortex_branches_sent_scout` is Prometheus counter | 1098–1104 | F00315 | non-negotiable | false | 10 |
| R00572 | Metric `sovereign_os_cortex_avx_tick_us` is Prometheus histogram | 731–739 | F00316 | non-negotiable | false | 10 |
| R00573 | Test — Cortex tick processes 8 branches per AVX-512 vector | 731–739 | F00317 | non-negotiable | false | 10 |
| R00574 | Test — Cortex masks invalid tokens before model inference | 1098–1104 | F00318 | non-negotiable | false | 10 |
| R00575 | Test — Cortex rejects forbidden tool intents | 1098–1104 | F00319 | non-negotiable | false | 10 |
| R00576 | Test — Cortex expires branches at budget = 0 | 1098–1104 | F00320 | non-negotiable | false | 10 |
| R00577 | Lifecycle hook `pre-tick` emits branch snapshot for replay | 731–739 | F00321 | non-negotiable | false | 10 |
| R00578 | Lifecycle hook `post-tick` emits branch state transitions for replay | 731–739 | F00322 | non-negotiable | false | 10 |
| R00579 | Composite F00323 three-organ pipeline requires modules M00046 + M00048 + M00051 | 590–592 | F00323 | non-negotiable | false | 10 |
| R00580 | Personalization — operator-defined Cortex tick budget per profile (cycles or ms) | 731–739 | F00324 | non-negotiable | true | 10 |
| R00581 | Cortex u64 lane field — bits 0..7 agent type | 458–465 | M00052 | non-negotiable | false | 10 |
| R00582 | Cortex u64 lane field — bits 8..15 confidence | 458–465 | M00052 | non-negotiable | false | 10 |
| R00583 | Cortex u64 lane field — bits 16..23 budget | 458–465 | M00052 | non-negotiable | false | 10 |
| R00584 | Cortex u64 lane field — bits 24..31 risk / toxicity / constraint class | 458–465 | M00052 | non-negotiable | false | 10 |
| R00585 | Cortex u64 lane field — bits 32..47 memory pointer / arena index | 458–465 | M00052 | non-negotiable | false | 10 |
| R00586 | Cortex u64 lane field — bits 48..63 flags / grammar / mode | 458–465 | M00052 | non-negotiable | false | 10 |
| R00587 | Memory Plane target 256 GiB | 519 | F00325 | non-negotiable | true | 10 |
| R00588 | Memory Plane intermediate target 128 GiB acceptable | 219 | F00325 | non-negotiable | true | 10 |
| R00589 | Profile `memory_plane_target_gib` accepts 128 / 256 | 519 | F00326 | non-negotiable | true | 10 |
| R00590 | Env var `SOVEREIGN_MEMORY_PLANE_TARGET_GIB` accepts 128 / 256 | 519 | F00327 | non-negotiable | true | 10 |
| R00591 | Dashboard Memory Plane card shows utilization + ARC hit rate | 519 | F00328 | non-negotiable | true | 10 |
| R00592 | Metric `sovereign_os_memory_plane_working_used_bytes` is Prometheus gauge | 519 | F00329 | non-negotiable | false | 10 |
| R00593 | Metric `sovereign_os_memory_plane_arc_hit_rate` is Prometheus gauge 0–1 | 219 | F00330 | non-negotiable | false | 10 |
| R00594 | Storage Plane ZFS replay retention default 30 days | 522 | F00331 | non-negotiable | true | 10 |
| R00595 | Profile `storage_plane_replay_retention_days` accepts integer ≥ 1 | 522 | F00332 | non-negotiable | true | 10 |
| R00596 | Env var `SOVEREIGN_STORAGE_REPLAY_RETENTION_DAYS` accepts integer ≥ 1 | 522 | F00333 | non-negotiable | true | 10 |
| R00597 | Dashboard Storage Plane card shows per-dataset usage | 343 | F00334 | non-negotiable | true | 10 |
| R00598 | Metric `sovereign_os_storage_plane_dataset_used_bytes` labeled by dataset | 343 | F00335 | non-negotiable | false | 10 |
| R00599 | Boundary transport `only-compact-symbols` mode allows tokens/scores/refs/summaries | 526–536 | F00336 | non-negotiable | true | 10 |
| R00600 | Boundary transport `strict-no-tensor` mode rejects KV tensors, activations, layer-split fragments | 540–547 | F00337 | non-negotiable | true | 10 |
| R00601 | Test — boundary transport rejects KV tensor payload (sized > 10 MiB binary) | 540–547 | F00338 | non-negotiable | false | 10 |
| R00602 | Test — boundary transport rejects activation tensor payload (sized > 10 MiB binary) | 540–547 | F00339 | non-negotiable | false | 10 |
| R00603 | Composite F00340 speculative chunk pipeline with constraint automata requires modules M00060 + M00061 + M00053 | 470–502 | F00340 | non-negotiable | false | 10 |
| R00604 | Composite F00296 speculative chunk loop emits OTel parent span per chunk | 470–488 | F00296 | non-negotiable | false | 10 |
| R00605 | Composite F00296 chunk loop child spans — scout_draft / cortex_filter / oracle_verify / cortex_update | 470–488 | F00296 | non-negotiable | false | 10 |
| R00606 | Composite F00323 three-organ pipeline gated by all three opt-in flags | 590–592 | F00323 | non-negotiable | true | 10 |
| R00607 | Composite F00323 fails closed if any organ unavailable | 590–592 | F00323 | non-negotiable | true | 10 |
| R00608 | Composite F00323 surfaces operator-actionable error message on partial unavailability | 590–592 | F00323 | non-negotiable | true | 10 |
| R00609 | Oracle Core enforces verification-only role — no draft generation | 1390–1404 | M00046 | non-negotiable | false | 10 |
| R00610 | Oracle Core enforces final-synthesis role — no intermediate reasoning | 1390–1404 | M00046 | non-negotiable | false | 10 |
| R00611 | Oracle Core enforces long-context role — context ≥ 64K tokens recommended | 1390–1404 | M00046 | non-negotiable | true | 10 |
| R00612 | Scout enforces draft-only role — no commit authority | 619 | M00048 | non-negotiable | false | 10 |
| R00613 | Scout enforces embedding-only role — never produces side effects | 619 | M00048 | non-negotiable | false | 10 |
| R00614 | Scout enforces rerank-only role — accepts candidate set, returns scored list | 619 | M00048 | non-negotiable | false | 10 |
| R00615 | Scout enforces perceive-only role — produces parsed UI state, no UI actions | 619 | M00048 | non-negotiable | false | 10 |
| R00616 | Scout enforces classify-only role — produces label + confidence, no commit | 619 | M00048 | non-negotiable | false | 10 |
| R00617 | Cortex enforces filter-only role — never produces text or tokens | 731–739 | M00051 | non-negotiable | false | 10 |
| R00618 | Cortex enforces routing-only role — selects expert, never executes | 731–739 | M00051 | non-negotiable | false | 10 |
| R00619 | Cortex enforces commit-only role — never proposes state transition | 731–739 | M00051 | non-negotiable | false | 10 |
| R00620 | Cortex tick budget per profile — `cortex_low_latency` ≤ 100µs | 731–739 | F00324 | non-negotiable | true | 10 |
| R00621 | Cortex tick budget per profile — `cortex_max_throughput` ≤ 1ms | 731–739 | F00324 | non-negotiable | true | 10 |
| R00622 | Cortex tick budget per profile — `cortex_strict_correctness` ≤ 10ms | 731–739 | F00324 | non-negotiable | true | 10 |
| R00623 | Cortex tick budget profile selectable at runtime via daemon SIGUSR2 | 731–739 | F00324 | non-negotiable | true | 10 |
| R00624 | Cortex branch table persisted at `/var/lib/sovereign-os/cortex/branches.json` | 731–739 | M00051 | non-negotiable | false | 10 |
| R00625 | Cortex branch table mode 0640 | 731–739 | M00051 | non-negotiable | false | 10 |
| R00626 | Cortex branch table written atomically | 731–739 | M00051 | non-negotiable | false | 10 |
| R00627 | Cortex branch table content-addressed via blake3 in replay log | 731–739 | M00051 | non-negotiable | false | 10 |
| R00628 | Oracle Core enqueue policy — FIFO by default | 590 | M00046 | non-negotiable | true | 10 |
| R00629 | Oracle Core enqueue policy — priority by branch reward when `priority_mode = reward` | 590 | M00046 | non-negotiable | true | 10 |
| R00630 | Oracle Core enqueue policy — fair share when `priority_mode = fair` | 590 | M00046 | non-negotiable | true | 10 |
| R00631 | Oracle Core max concurrent verifications = 4 by default | 590 | M00046 | non-negotiable | true | 10 |
| R00632 | Oracle Core max concurrent verifications operator-tunable | 590 | M00046 | non-negotiable | true | 10 |
| R00633 | Scout max concurrent drafts = 8 by default | 619 | M00048 | non-negotiable | true | 10 |
| R00634 | Scout max concurrent drafts operator-tunable | 619 | M00048 | non-negotiable | true | 10 |
| R00635 | Cortex max concurrent ticks = 1 (single AVX-512 thread per tick) by default | 731–739 | M00051 | non-negotiable | true | 10 |
| R00636 | Cortex max concurrent ticks operator-tunable (multi-CCD pinning) | 731–739 | M00051 | non-negotiable | true | 10 |
| R00637 | Memory Plane queue depth limit = 1024 by default | 519 | M00054 | non-negotiable | true | 10 |
| R00638 | Memory Plane queue depth limit operator-tunable | 519 | M00054 | non-negotiable | true | 10 |
| R00639 | Memory Plane queue overflow policy = drop oldest by default | 519 | M00054 | non-negotiable | true | 10 |
| R00640 | Memory Plane queue overflow policy = drop lowest priority when `overflow_mode = drop_lowest_priority` | 519 | M00054 | non-negotiable | true | 10 |
| R00641 | Memory Plane queue overflow policy = block when `overflow_mode = block` | 519 | M00054 | non-negotiable | true | 10 |
| R00642 | Memory Plane ARC tuning — clamp ARC to 128 GB max by default | 219 | M00055 | non-negotiable | true | 10 |
| R00643 | Memory Plane ARC clamp operator-tunable | 219 | M00055 | non-negotiable | true | 10 |
| R00644 | Storage Plane RAID-0 layout — operator must acknowledge "RAID-0 ≠ durability" at first apply | 343–344 | M00057 | non-negotiable | false | 10 |
| R00645 | Storage Plane datasets — `tank/models` recordsize 1M lz4 | 343 | M00056 | non-negotiable | true | 10 |
| R00646 | Storage Plane datasets — `tank/context` recordsize 16K zstd-9 copies=2 sync=always | 343 | M00056 | non-negotiable | true | 10 |
| R00647 | Storage Plane datasets — `tank/agents` recordsize 128K zstd-3 | 343 | M00056 | non-negotiable | true | 10 |
| R00648 | Boundary transport — Unix socket between Cortex daemon and Oracle server | 1156 | M00058 | non-negotiable | true | 10 |
| R00649 | Boundary transport — Unix socket between Cortex daemon and Scout server | 1156 | M00058 | non-negotiable | true | 10 |
| R00650 | Boundary transport — virtio-vsock when Scout is VFIO-isolated | 3453–3461 | M00058 | non-negotiable | true | 10 |
| R00651 | Boundary transport — gRPC over vsock when Scout is VFIO-isolated | 3453–3461 | M00058 | non-negotiable | true | 10 |
| R00652 | Boundary transport — shared memory when same-host bare-metal | 3453–3461 | M00058 | non-negotiable | true | 10 |
| R00653 | Boundary transport message schema — `RuntimeRequest` typed Rust struct | 16519–16533 | M00058 | non-negotiable | false | 10 |
| R00654 | Boundary transport message schema — `DraftRequest` typed Rust struct | 3464–3473 | M00058 | non-negotiable | false | 10 |
| R00655 | Boundary transport message schema — `DraftResult` typed Rust struct | 3464–3473 | M00058 | non-negotiable | false | 10 |
| R00656 | Boundary transport message schema — `EmbeddingRequest` typed Rust struct | 3464–3473 | M00058 | non-negotiable | false | 10 |
| R00657 | Boundary transport message schema — `RerankResult` typed Rust struct | 3464–3473 | M00058 | non-negotiable | false | 10 |
| R00658 | Boundary transport message schema — `VisionResult` typed Rust struct | 3464–3473 | M00058 | non-negotiable | false | 10 |
| R00659 | Boundary transport message schema — `ToolPlan` typed Rust struct | 3464–3473 | M00058 | non-negotiable | false | 10 |
| R00660 | Boundary transport message schema — `RiskAssessment` typed Rust struct | 3464–3473 | M00058 | non-negotiable | false | 10 |
| R00661 | Boundary transport message schema — `PatchProposal` typed Rust struct | 3464–3473 | M00058 | non-negotiable | false | 10 |
| R00662 | Boundary transport messages serialized via bincode or postcard | 1156 | M00058 | preferable | true | 10 |
| R00663 | Boundary transport messages opt-in JSON encoding for debugging | 1156 | M00058 | non-negotiable | true | 10 |
| R00664 | Boundary transport messages signed when `--require-signed-messages` set | 1156 | M00058 | non-negotiable | true | 10 |
| R00665 | Boundary transport message size cap = 10 MiB default | 540–547 | M00059 | non-negotiable | true | 10 |
| R00666 | Boundary transport message size cap operator-tunable | 540–547 | M00059 | non-negotiable | true | 10 |
| R00667 | Boundary transport message timeout = 5 seconds default | 1156 | M00058 | non-negotiable | true | 10 |
| R00668 | Boundary transport message timeout operator-tunable | 1156 | M00058 | non-negotiable | true | 10 |
| R00669 | Speculative decode chunk size = 16 tokens default | 480 | M00060 | non-negotiable | true | 10 |
| R00670 | Speculative decode chunk size operator-tunable (8 / 16 / 32 / 64) | 480 | M00060 | non-negotiable | true | 10 |
| R00671 | Speculative decode branch count = 4 default | 480 | M00060 | non-negotiable | true | 10 |
| R00672 | Speculative decode branch count operator-tunable | 480 | M00060 | non-negotiable | true | 10 |
| R00673 | Per-branch contract mask — "must cite sources" toggleable | 492–502 | M00061 | non-negotiable | true | 10 |
| R00674 | Per-branch contract mask — "must stay in code mode" toggleable | 492–502 | M00061 | non-negotiable | true | 10 |
| R00675 | Per-branch contract mask — "must avoid tool calls" toggleable | 492–502 | M00061 | non-negotiable | true | 10 |
| R00676 | Per-branch contract mask — "must preserve JSON grammar" toggleable | 492–502 | M00061 | non-negotiable | true | 10 |
| R00677 | Per-branch contract mask — "must explore risky alternative" toggleable | 492–502 | M00061 | non-negotiable | true | 10 |
| R00678 | Per-branch contract mask — "must compress memory" toggleable | 492–502 | M00061 | non-negotiable | true | 10 |
| R00679 | Per-branch contract mask — "must terminate after N steps" toggleable with operator-defined N | 492–502 | M00061 | non-negotiable | true | 10 |
| R00680 | Per-branch contract masks composable — multiple masks OR-combined per branch | 492–502 | M00061 | non-negotiable | true | 10 |

— End of M004 milestone file.
