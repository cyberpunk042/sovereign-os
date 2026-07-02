# M005 — Agent runtime — four planes (Inference / Control / Memory / Tool)

> Parent: `backlog/milestones/INDEX.md` row M005 (dump 723–993).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 723–993.
> All entries below extracted from the dump line range. No invention.

> **AVX++ canon update — 2026-05-19**: this milestone is affected by backward-sweep redefinition(s) — Core Law (CLARIFYING) + Authority Levels 0..6 (ADDITIVE) + Scheduler-as-policy-layer (BREAKING). See sovereign-os M061 for canonical pinning (commit 6f07dca). R-rows below are interpreted under the canonical later definitions per operator standing direction "layered: new direction ON TOP OF prior direction — never discarded".


## Epics (E0041–E0046)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0041 | Branch struct — id / parent_id / control / score / budget / memory_ref / constraint_mask / rng | 752–760 |
| E0042 | Branch lifecycle states — drafted / verified / merged / killed / expanded / routed / summarized / tool-executed / committed | 1260–1271 |
| E0043 | AVX-512 scheduler tick — decrement / drop / boost / route / merge / admit / evict | 776–787 |
| E0044 | Constraint automata — JSON / grammar / tool / shell-command / patch FSMs | 911–913 |
| E0045 | Auditable replay log — input / chunks / drafts / oracle / tools / patches / tests / final | 898–907 |
| E0046 | Three big wins — oracle calls scarce / 4090 specialists / CPU constraint automata | 826–933 |

## Modules (M00062–M00078) — 17 modules

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00062 | Branch struct fields — id u64 / parent u64 / control u64 / score u64 / budget u64 / memory_ref u64 / constraint_mask u64 / rng u64 | 752–760 | E0041 |
| M00063 | Branch ops — drafted / verified / merged / killed / expanded / routed / summarized / tool-executed / committed | 1260–1271 | E0042 |
| M00064 | Scheduler tick — decrement budgets / drop dead / boost promising / route uncertain / route cheap / enforce constraints / merge dups / admit-evict memory | 776–787 | E0043 |
| M00065 | 8-bit control word fields — bits 0..3 model route / 4..7 task type / 8..15 max speculation / 16..23 risk / 24..31 tool perms / 32..39 memory policy / 40..47 grammar mode / 48..55 priority / 56..63 lifecycle flags | 793–805 | E0041 |
| M00066 | 4090 proposal format — N tokens + confidence + grammar state + tool intent | 810–812 | E0042 |
| M00067 | CPU decision format — no shell / keep N tokens / oracle for X / embedding around Y / kill branch Z | 815–820 | E0042 |
| M00068 | Oracle scarce + high-value invariant | 826 | E0046 |
| M00069 | Cheap cognition services on 4090 — draft / embedding / reranker / small code / vision / classifier / preference / summarizer / tool-risk | 829–839 | E0046 |
| M00070 | Specialist market on 4090 — CPU as exchange | 842–845 | E0046 |
| M00071 | Request lifecycle — user / root branch / context candidates / 4090 rerank-summarize-expand / CPU packs prompt / RTX PRO generates / 4090 drafts ahead / CPU validates / RTX PRO finalizes / memory logs | 850–860 | E0046 |
| M00072 | Coding workflow split — 4090 (grep / small-patch / speculation / test-classification) / CPU (dep-graph / risk-scoring / scheduling / grammar / merge) / RTX PRO (architectural / final-review / hard-bug / long-context) | 862–882 | E0046 |
| M00073 | Auditable trace — input / chunks / drafts / oracle / tool calls / patches / tests / final | 898–907 | E0045 |
| M00074 | Deterministic JSON FSM on CPU | 916 | E0044 |
| M00075 | Deterministic tool-call masking on CPU | 917 | E0044 |
| M00076 | Deterministic budget counter enforcement on CPU | 918 | E0044 |
| M00077 | Branch RNG advance — independent per-branch stream | 752–760 | E0041 |
| M00078 | Branch parent-child relationships — fork / merge / kill | 752–760 | E0041 |

## Features (F00341–F00425) — 85 features

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00341 | Toggle branch-struct standard layout | 752–760 | M00062 | mode | true |
| F00342 | Profile knob — `branch_struct_layout = standard \| extended` | 752–760 | M00062 | profile | true |
| F00343 | Env var `SOVEREIGN_BRANCH_STRUCT_LAYOUT` | 752–760 | M00062 | env_var | true |
| F00344 | CLI `sovereign-osctl branch list` | 752–760 | M00062 | cli_verb | true |
| F00345 | CLI `sovereign-osctl branch show <id>` | 752–760 | M00062 | cli_verb | true |
| F00346 | CLI `sovereign-osctl branch kill <id>` | 1260–1271 | M00063 | cli_verb | true |
| F00347 | CLI `sovereign-osctl branch merge <id1> <id2>` | 1260–1271 | M00063 | cli_verb | true |
| F00348 | CLI `sovereign-osctl branch fork <id>` | 752–760 | M00078 | cli_verb | true |
| F00349 | Dashboard surface — Branch table (live) | 752–760 | M00062 | dashboard | true |
| F00350 | Dashboard surface — Branch lifecycle Sankey diagram | 1260–1271 | M00063 | dashboard | true |
| F00351 | Dashboard surface — Branch fork tree (parent-child graph) | 752–760 | M00078 | dashboard | true |
| F00352 | API `GET /v1/branches` | 752–760 | M00062 | api_endpoint | true |
| F00353 | API `GET /v1/branches/<id>` | 752–760 | M00062 | api_endpoint | true |
| F00354 | API `POST /v1/branches/<id>/kill` | 1260–1271 | M00063 | api_endpoint | true |
| F00355 | API `POST /v1/branches/<id>/merge` | 1260–1271 | M00063 | api_endpoint | true |
| F00356 | API `POST /v1/branches/<id>/fork` | 752–760 | M00078 | api_endpoint | true |
| F00357 | Metric `sovereign_os_branches_total{state}` | 1260–1271 | M00063 | observability_metric | true |
| F00358 | Metric `sovereign_os_branches_by_lifecycle_state{state}` | 1260–1271 | M00063 | observability_metric | true |
| F00359 | Metric `sovereign_os_branch_struct_layout_in_use` (info gauge) | 752–760 | M00062 | observability_metric | true |
| F00360 | Test — branch struct serialize/deserialize round-trip | 752–760 | M00062 | test | true |
| F00361 | Test — branch parent-child relationships preserved across fork | 752–760 | M00078 | test | true |
| F00362 | Test — branch RNG independent per stream | 752–760 | M00077 | test | true |
| F00363 | Lifecycle hook — pre-branch-spawn emit OTel span | 752–760 | M00062 | lifecycle_hook | true |
| F00364 | Lifecycle hook — post-branch-kill emit OTel span | 1260–1271 | M00063 | lifecycle_hook | true |
| F00365 | Personalization — operator-defined branch-struct extended fields | 752–760 | M00062 | configuration | true |
| F00366 | Toggle scheduler-tick decrement-budgets pass | 776 | M00064 | mode | true |
| F00367 | Toggle scheduler-tick drop-dead pass | 777 | M00064 | mode | true |
| F00368 | Toggle scheduler-tick boost-promising pass | 778 | M00064 | mode | true |
| F00369 | Toggle scheduler-tick route-uncertain-to-oracle pass | 779 | M00064 | mode | true |
| F00370 | Toggle scheduler-tick route-cheap-to-scout pass | 780 | M00064 | mode | true |
| F00371 | Toggle scheduler-tick grammar-constraint pass | 781 | M00064 | mode | true |
| F00372 | Toggle scheduler-tick merge-duplicate pass | 782 | M00064 | mode | true |
| F00373 | Toggle scheduler-tick memory-admit-evict pass | 783 | M00064 | mode | true |
| F00374 | Profile knob — `scheduler_tick_passes = [list of pass names]` | 776–787 | M00064 | profile | true |
| F00375 | Env var `SOVEREIGN_SCHEDULER_TICK_PASSES` (comma-separated) | 776–787 | M00064 | env_var | true |
| F00376 | CLI `sovereign-osctl scheduler tick run` | 776–787 | M00064 | cli_verb | true |
| F00377 | Dashboard surface — Scheduler tick timeline | 776–787 | M00064 | dashboard | true |
| F00378 | Metric `sovereign_os_scheduler_tick_duration_us` (histogram) | 776–787 | M00064 | observability_metric | true |
| F00379 | Metric `sovereign_os_scheduler_tick_branches_dropped` (counter) | 777 | M00064 | observability_metric | true |
| F00380 | Metric `sovereign_os_scheduler_tick_branches_boosted` (counter) | 778 | M00064 | observability_metric | true |
| F00381 | Test — scheduler tick passes idempotent on no-change input | 776–787 | M00064 | test | true |
| F00382 | Composite — full scheduler tick chain (all 8 passes) | 776–787 | composite: [M00064] | capability | true |
| F00383 | Toggle 8-bit control word fields layout | 793–805 | M00065 | mode | true |
| F00384 | Profile knob — `control_word_v2_enabled` (8-field layout) | 793–805 | M00065 | profile | true |
| F00385 | Env var `SOVEREIGN_CONTROL_WORD_V2_ENABLED` | 793–805 | M00065 | env_var | true |
| F00386 | Dashboard surface — Control word bit-layout inspector | 793–805 | M00065 | dashboard | true |
| F00387 | Test — control word v2 decode covers all 9 fields | 793–805 | M00065 | test | true |
| F00388 | Personalization — operator-defined control-word field bit-widths | 793–805 | M00065 | configuration | true |
| F00389 | Toggle 4090 proposal-format mode | 810–812 | M00066 | mode | true |
| F00390 | Profile knob — `scout_proposal_format = v1 \| v2 \| operator_defined` | 810–812 | M00066 | profile | true |
| F00391 | Env var `SOVEREIGN_SCOUT_PROPOSAL_FORMAT` | 810–812 | M00066 | env_var | true |
| F00392 | API `POST /v1/scout/proposal` — accept N-token + confidence + grammar-state + tool-intent | 810–812 | M00066 | api_endpoint | true |
| F00393 | Test — scout proposal schema validates | 810–812 | M00066 | test | true |
| F00394 | Toggle CPU-decision-format mode | 815–820 | M00067 | mode | true |
| F00395 | Profile knob — `cpu_decision_format = v1 \| v2 \| operator_defined` | 815–820 | M00067 | profile | true |
| F00396 | Env var `SOVEREIGN_CPU_DECISION_FORMAT` | 815–820 | M00067 | env_var | true |
| F00397 | API `POST /v1/cortex/decision` — emit no-shell / keep-N-tokens / oracle-for-X / embedding-around-Y / kill-branch-Z | 815–820 | M00067 | api_endpoint | true |
| F00398 | Test — CPU decision schema covers all 5 named actions | 815–820 | M00067 | test | true |
| F00399 | Toggle oracle-scarce-invariant enforcement | 826 | M00068 | mode | true |
| F00400 | Profile knob — `oracle_scarcity_threshold` | 826 | M00068 | profile | true |
| F00401 | Env var `SOVEREIGN_ORACLE_SCARCITY_THRESHOLD` | 826 | M00068 | env_var | true |
| F00402 | Test — oracle calls scarce-by-default proven via load test | 826 | M00068 | test | true |
| F00403 | Toggle 4090-specialist-market mode | 842–845 | M00070 | mode | true |
| F00404 | Profile knob — `scout_specialist_registry_path` | 842–845 | M00070 | profile | true |
| F00405 | Env var `SOVEREIGN_SCOUT_SPECIALIST_REGISTRY_PATH` | 842–845 | M00070 | env_var | true |
| F00406 | CLI `sovereign-osctl scout specialists list` | 842–845 | M00070 | cli_verb | true |
| F00407 | Dashboard surface — Scout specialist registry table | 842–845 | M00070 | dashboard | true |
| F00408 | API `GET /v1/scout/specialists` | 842–845 | M00070 | api_endpoint | true |
| F00409 | Toggle request-lifecycle pipeline | 850–860 | M00071 | mode | true |
| F00410 | Profile knob — `request_lifecycle_pipeline = standard \| custom_<name>` | 850–860 | M00071 | profile | true |
| F00411 | Env var `SOVEREIGN_REQUEST_LIFECYCLE_PIPELINE` | 850–860 | M00071 | env_var | true |
| F00412 | Dashboard surface — Request lifecycle pipeline visualization | 850–860 | M00071 | dashboard | true |
| F00413 | Test — request lifecycle pipeline ordering deterministic | 850–860 | M00071 | test | true |
| F00414 | Toggle coding-workflow-split mode | 862–882 | M00072 | mode | true |
| F00415 | Profile knob — `coding_workflow_split = standard \| operator_defined` | 862–882 | M00072 | profile | true |
| F00416 | Dashboard surface — Coding workflow per-organ task assignment | 862–882 | M00072 | dashboard | true |
| F00417 | Test — 4090 receives grep / small-patch / speculation / test-classification only | 862–882 | M00072 | test | true |
| F00418 | Test — CPU receives dep-graph / risk-scoring / scheduling / grammar / merge only | 862–882 | M00072 | test | true |
| F00419 | Test — RTX PRO receives architectural / final-review / hard-bug / long-context only | 862–882 | M00072 | test | true |
| F00420 | Toggle auditable-trace replay mode | 898–907 | M00073 | mode | true |
| F00421 | Profile knob — `auditable_trace_replay_enabled` | 898–907 | M00073 | profile | true |
| F00422 | Env var `SOVEREIGN_AUDITABLE_TRACE_REPLAY_ENABLED` | 898–907 | M00073 | env_var | true |
| F00423 | CLI `sovereign-osctl trace replay <trace-id>` | 898–907 | M00073 | cli_verb | true |
| F00424 | Dashboard surface — Trace replay timeline | 898–907 | M00073 | dashboard | true |
| F00425 | Composite — request lifecycle → coding workflow split → auditable trace | 850–907 | composite: [M00071, M00072, M00073] | capability | true |

## Requirements (R00681–R00850) — 170 requirements

| R ID | Phrase | Dump line | Parent F | Class | Opt-in | Sub-req min |
|---|---|---|---|---|---|---|
| R00681 | Branch struct field `id` = u64 unique non-zero | 752–760 | F00341 | non-negotiable | false | 10 |
| R00682 | Branch struct field `parent_id` = u64; root branch parent = 0 | 752–760 | F00341 | non-negotiable | false | 10 |
| R00683 | Branch struct field `control` = u64 (8 packed fields per M00065) | 752–760 | F00341 | non-negotiable | false | 10 |
| R00684 | Branch struct field `score` = u64 (Q16 fixed-point quality + Q16 fixed-point cost + 32-bit flags) | 752–760 | F00341 | non-negotiable | false | 10 |
| R00685 | Branch struct field `budget` = u64 (remaining-token + ttl + step-limit) | 752–760 | F00341 | non-negotiable | false | 10 |
| R00686 | Branch struct field `memory_ref` = u64 (arena-index + offset) | 752–760 | F00341 | non-negotiable | false | 10 |
| R00687 | Branch struct field `constraint_mask` = u64 (grammar + tool + safety + schema + route mask bits) | 752–760 | F00341 | non-negotiable | false | 10 |
| R00688 | Branch struct field `rng` = u64 (per-branch xoshiro256 seed state) | 752–760 | F00341 | non-negotiable | false | 10 |
| R00689 | Profile `branch_struct_layout` accepts `standard` / `extended` | 752–760 | F00342 | non-negotiable | true | 10 |
| R00690 | Env var `SOVEREIGN_BRANCH_STRUCT_LAYOUT` accepts same enum | 752–760 | F00343 | non-negotiable | true | 10 |
| R00691 | CLI `branch list` returns JSON | 752–760 | F00344 | non-negotiable | true | 10 |
| R00692 | CLI `branch show <id>` returns full branch detail | 752–760 | F00345 | non-negotiable | true | 10 |
| R00693 | CLI `branch kill <id>` transitions branch state → killed | 1260–1271 | F00346 | non-negotiable | true | 10 |
| R00694 | CLI `branch merge <id1> <id2>` requires both branches in mergeable state | 1260–1271 | F00347 | non-negotiable | false | 10 |
| R00695 | CLI `branch fork <id>` creates child branch with parent_id = <id> | 752–760 | F00348 | non-negotiable | true | 10 |
| R00696 | Dashboard branch table refreshes via SSE | 752–760 | F00349 | non-negotiable | true | 10 |
| R00697 | Dashboard branch lifecycle Sankey shows per-state transition counts | 1260–1271 | F00350 | non-negotiable | true | 10 |
| R00698 | Dashboard branch fork tree renders parent-child graph (D3 or Cytoscape) | 752–760 | F00351 | non-negotiable | true | 10 |
| R00699 | API `GET /v1/branches` returns JSON list | 752–760 | F00352 | non-negotiable | true | 10 |
| R00700 | API `GET /v1/branches/<id>` returns single branch JSON | 752–760 | F00353 | non-negotiable | true | 10 |
| R00701 | API `POST /v1/branches/<id>/kill` returns updated branch state | 1260–1271 | F00354 | non-negotiable | true | 10 |
| R00702 | API `POST /v1/branches/<id>/merge` requires target_id in body | 1260–1271 | F00355 | non-negotiable | true | 10 |
| R00703 | API `POST /v1/branches/<id>/fork` returns new branch id | 752–760 | F00356 | non-negotiable | true | 10 |
| R00704 | Metric `sovereign_os_branches_total` is Prometheus counter labeled by state | 1260–1271 | F00357 | non-negotiable | false | 10 |
| R00705 | Metric `sovereign_os_branches_by_lifecycle_state` is Prometheus gauge labeled by state | 1260–1271 | F00358 | non-negotiable | false | 10 |
| R00706 | Metric `sovereign_os_branch_struct_layout_in_use` is info gauge | 752–760 | F00359 | non-negotiable | false | 10 |
| R00707 | Test — branch struct serialize via bincode round-trip | 752–760 | F00360 | non-negotiable | false | 10 |
| R00708 | Test — fork preserves parent_id linkage | 752–760 | F00361 | non-negotiable | false | 10 |
| R00709 | Test — branch RNG produces independent streams (chi-square test 95% confidence) | 752–760 | F00362 | preferable | false | 10 |
| R00710 | Lifecycle hook `pre-branch-spawn` emits OTel span with parent_id + profile + budget | 752–760 | F00363 | non-negotiable | false | 10 |
| R00711 | Lifecycle hook `post-branch-kill` emits OTel span with reason enum | 1260–1271 | F00364 | non-negotiable | false | 10 |
| R00712 | Operator-defined branch-struct extended fields YAML — `name` `bit_offset` `bit_width` | 752–760 | F00365 | non-negotiable | true | 10 |
| R00713 | Scheduler tick `decrement-budgets` pass opt-in | 776 | F00366 | non-negotiable | true | 10 |
| R00714 | Scheduler tick `drop-dead` pass opt-in | 777 | F00367 | non-negotiable | true | 10 |
| R00715 | Scheduler tick `boost-promising` pass opt-in | 778 | F00368 | non-negotiable | true | 10 |
| R00716 | Scheduler tick `route-uncertain-to-oracle` pass opt-in | 779 | F00369 | non-negotiable | true | 10 |
| R00717 | Scheduler tick `route-cheap-to-scout` pass opt-in | 780 | F00370 | non-negotiable | true | 10 |
| R00718 | Scheduler tick `grammar-constraint` pass opt-in | 781 | F00371 | non-negotiable | true | 10 |
| R00719 | Scheduler tick `merge-duplicate` pass opt-in | 782 | F00372 | non-negotiable | true | 10 |
| R00720 | Scheduler tick `memory-admit-evict` pass opt-in | 783 | F00373 | non-negotiable | true | 10 |
| R00721 | Profile `scheduler_tick_passes` accepts ordered list of pass names | 776–787 | F00374 | non-negotiable | true | 10 |
| R00722 | Env var `SOVEREIGN_SCHEDULER_TICK_PASSES` accepts comma-separated pass names | 776–787 | F00375 | non-negotiable | true | 10 |
| R00723 | CLI `scheduler tick run` triggers single tick + returns JSON report | 776–787 | F00376 | non-negotiable | true | 10 |
| R00724 | Dashboard scheduler tick timeline shows per-pass latency | 776–787 | F00377 | non-negotiable | true | 10 |
| R00725 | Metric `sovereign_os_scheduler_tick_duration_us` is Prometheus histogram | 776–787 | F00378 | non-negotiable | false | 10 |
| R00726 | Metric `sovereign_os_scheduler_tick_branches_dropped` is Prometheus counter | 777 | F00379 | non-negotiable | false | 10 |
| R00727 | Metric `sovereign_os_scheduler_tick_branches_boosted` is Prometheus counter | 778 | F00380 | non-negotiable | false | 10 |
| R00728 | Test — scheduler tick idempotent on no-change input | 776–787 | F00381 | non-negotiable | false | 10 |
| R00729 | Composite F00382 full tick chain requires module M00064 | 776–787 | F00382 | non-negotiable | false | 10 |
| R00730 | Control word v2 layout bits 0..3 = model route (16 routes) | 793 | F00383 | non-negotiable | false | 10 |
| R00731 | Control word v2 layout bits 4..7 = task type (16 types) | 794 | F00383 | non-negotiable | false | 10 |
| R00732 | Control word v2 layout bits 8..15 = max speculation depth | 795 | F00383 | non-negotiable | false | 10 |
| R00733 | Control word v2 layout bits 16..23 = risk class | 796 | F00383 | non-negotiable | false | 10 |
| R00734 | Control word v2 layout bits 24..31 = tool permissions | 797 | F00383 | non-negotiable | false | 10 |
| R00735 | Control word v2 layout bits 32..39 = memory policy | 798 | F00383 | non-negotiable | false | 10 |
| R00736 | Control word v2 layout bits 40..47 = grammar mode | 799 | F00383 | non-negotiable | false | 10 |
| R00737 | Control word v2 layout bits 48..55 = priority | 800 | F00383 | non-negotiable | false | 10 |
| R00738 | Control word v2 layout bits 56..63 = lifecycle flags | 801 | F00383 | non-negotiable | false | 10 |
| R00739 | Profile `control_word_v2_enabled` accepts boolean | 793–805 | F00384 | non-negotiable | true | 10 |
| R00740 | Env var `SOVEREIGN_CONTROL_WORD_V2_ENABLED` accepts boolean | 793–805 | F00385 | non-negotiable | true | 10 |
| R00741 | Dashboard control word v2 inspector renders 9 fields | 793–805 | F00386 | non-negotiable | true | 10 |
| R00742 | Test — control word v2 decode covers all 9 fields | 793–805 | F00387 | non-negotiable | false | 10 |
| R00743 | Operator-defined field bit-widths must total 64 | 793–805 | F00388 | non-negotiable | true | 10 |
| R00744 | Scout proposal v1 schema — `tokens[]` + `confidence` + `grammar_state` + `tool_intent` | 810–812 | F00389 | non-negotiable | false | 10 |
| R00745 | Scout proposal v2 schema (forward-compat) — v1 fields + `model_id` + `precision` | 810–812 | F00389 | non-negotiable | true | 10 |
| R00746 | Profile `scout_proposal_format` accepts `v1` / `v2` / `operator_defined` | 810–812 | F00390 | non-negotiable | true | 10 |
| R00747 | Env var `SOVEREIGN_SCOUT_PROPOSAL_FORMAT` accepts same enum | 810–812 | F00391 | non-negotiable | true | 10 |
| R00748 | API `POST /v1/scout/proposal` validates against current schema | 810–812 | F00392 | non-negotiable | true | 10 |
| R00749 | Test — scout proposal schema validates via jsonschema | 810–812 | F00393 | non-negotiable | false | 10 |
| R00750 | CPU decision format covers all 5 named actions: `no_shell` / `keep_n_tokens` / `route_oracle` / `embedding_around` / `kill_branch` | 815–820 | F00394 | non-negotiable | false | 10 |
| R00751 | Profile `cpu_decision_format` accepts `v1` / `v2` / `operator_defined` | 815–820 | F00395 | non-negotiable | true | 10 |
| R00752 | Env var `SOVEREIGN_CPU_DECISION_FORMAT` accepts same enum | 815–820 | F00396 | non-negotiable | true | 10 |
| R00753 | API `POST /v1/cortex/decision` accepts decision JSON | 815–820 | F00397 | non-negotiable | true | 10 |
| R00754 | Test — CPU decision schema covers all 5 named actions | 815–820 | F00398 | non-negotiable | false | 10 |
| R00755 | Oracle-scarcity threshold default ≤ 10% of branches routed to oracle per tick | 826 | F00400 | non-negotiable | true | 10 |
| R00756 | Profile `oracle_scarcity_threshold` accepts integer 0–100 | 826 | F00400 | non-negotiable | true | 10 |
| R00757 | Env var `SOVEREIGN_ORACLE_SCARCITY_THRESHOLD` accepts integer 0–100 | 826 | F00401 | non-negotiable | true | 10 |
| R00758 | Test — load test verifies < 10% of branches routed to oracle under typical load | 826 | F00402 | preferable | false | 10 |
| R00759 | Scout specialist registry YAML — `name` `path` `model_role` `precision` `gpu_target` | 842–845 | F00404 | non-negotiable | true | 10 |
| R00760 | Env var `SOVEREIGN_SCOUT_SPECIALIST_REGISTRY_PATH` defaults `/etc/sovereign-os/scout-specialists.yaml` | 842–845 | F00405 | non-negotiable | true | 10 |
| R00761 | CLI `scout specialists list` returns JSON of registered specialists | 842–845 | F00406 | non-negotiable | true | 10 |
| R00762 | Dashboard scout specialist registry table shows specialist name + role + GPU + latency | 842–845 | F00407 | non-negotiable | true | 10 |
| R00763 | API `GET /v1/scout/specialists` returns JSON specialist list | 842–845 | F00408 | non-negotiable | true | 10 |
| R00764 | Request lifecycle pipeline order — user → root branch → context → 4090 rerank-summarize-expand → CPU pack → RTX PRO generate → 4090 draft ahead → CPU validate → RTX PRO finalize → memory log | 850–860 | F00409 | non-negotiable | false | 10 |
| R00765 | Profile `request_lifecycle_pipeline` accepts `standard` / `custom_<name>` | 850–860 | F00410 | non-negotiable | true | 10 |
| R00766 | Env var `SOVEREIGN_REQUEST_LIFECYCLE_PIPELINE` accepts same enum | 850–860 | F00411 | non-negotiable | true | 10 |
| R00767 | Dashboard request lifecycle pipeline shows live per-stage status | 850–860 | F00412 | non-negotiable | true | 10 |
| R00768 | Test — request lifecycle pipeline ordering deterministic across runs | 850–860 | F00413 | non-negotiable | false | 10 |
| R00769 | Coding workflow split 4090 = grep / small-patch / speculation / test-classification | 866–870 | F00414 | non-negotiable | false | 10 |
| R00770 | Coding workflow split CPU = dep-graph / risk-scoring / scheduling / grammar / merge | 871–876 | F00414 | non-negotiable | false | 10 |
| R00771 | Coding workflow split RTX PRO = architectural / final-review / hard-bug / long-context | 877–882 | F00414 | non-negotiable | false | 10 |
| R00772 | Profile `coding_workflow_split` accepts `standard` / `operator_defined` | 862–882 | F00415 | non-negotiable | true | 10 |
| R00773 | Dashboard coding workflow per-organ task assignment shows live load | 862–882 | F00416 | non-negotiable | true | 10 |
| R00774 | Test — 4090 task class allowlist enforced | 862–882 | F00417 | non-negotiable | false | 10 |
| R00775 | Test — CPU task class allowlist enforced | 862–882 | F00418 | non-negotiable | false | 10 |
| R00776 | Test — RTX PRO task class allowlist enforced | 862–882 | F00419 | non-negotiable | false | 10 |
| R00777 | Auditable trace covers — input / chunks / drafts / oracle / tool calls / patches / tests / final | 898–907 | F00420 | non-negotiable | false | 10 |
| R00778 | Profile `auditable_trace_replay_enabled` accepts boolean | 898–907 | F00421 | non-negotiable | true | 10 |
| R00779 | Env var `SOVEREIGN_AUDITABLE_TRACE_REPLAY_ENABLED` accepts boolean | 898–907 | F00422 | non-negotiable | true | 10 |
| R00780 | CLI `trace replay <trace-id>` replays trace from beginning | 898–907 | F00423 | non-negotiable | true | 10 |
| R00781 | CLI `trace replay <trace-id> --from <step>` replays from specific step | 898–907 | F00423 | non-negotiable | true | 10 |
| R00782 | Dashboard trace replay timeline scrub-bar across all steps | 898–907 | F00424 | non-negotiable | true | 10 |
| R00783 | Composite F00425 lifecycle → workflow split → auditable trace requires modules M00071 + M00072 + M00073 | 850–907 | F00425 | non-negotiable | false | 10 |
| R00784 | Branch lifecycle state `drafted` — produced by scout, awaiting filter | 1260 | M00063 | non-negotiable | false | 10 |
| R00785 | Branch lifecycle state `verified` — passed oracle verification | 1261 | M00063 | non-negotiable | false | 10 |
| R00786 | Branch lifecycle state `merged` — combined with sibling branch via merge_mask | 1262 | M00063 | non-negotiable | false | 10 |
| R00787 | Branch lifecycle state `killed` — terminated by scheduler tick (budget/policy/grammar) | 1263 | M00063 | non-negotiable | false | 10 |
| R00788 | Branch lifecycle state `expanded` — forked into N child branches | 1264 | M00063 | non-negotiable | false | 10 |
| R00789 | Branch lifecycle state `routed` — assigned to organ (oracle / scout / cortex / human) | 1265 | M00063 | non-negotiable | false | 10 |
| R00790 | Branch lifecycle state `summarized` — replaced with condensed representation | 1266 | M00063 | non-negotiable | false | 10 |
| R00791 | Branch lifecycle state `tool-executed` — tool action committed under policy | 1267 | M00063 | non-negotiable | false | 10 |
| R00792 | Branch lifecycle state `committed` — final state, persisted to replay log | 1268 | M00063 | non-negotiable | false | 10 |
| R00793 | Branch lifecycle transitions emit OTel events | 1260–1271 | M00063 | non-negotiable | false | 10 |
| R00794 | Branch lifecycle transitions immutable in replay log | 1260–1271 | M00063 | non-negotiable | false | 10 |
| R00795 | Branch lifecycle transitions content-addressed via blake3 in replay log | 1260–1271 | M00063 | non-negotiable | false | 10 |
| R00796 | Three big wins — oracle calls scarce + 4090 specialists + CPU constraint automata | 826–933 | M00068 | non-negotiable | false | 10 |
| R00797 | Three big wins measurable via Prometheus dashboards | 826–933 | M00068 | non-negotiable | false | 10 |
| R00798 | Three big wins measurable via OTel spans | 826–933 | M00068 | non-negotiable | false | 10 |
| R00799 | Three big wins surfaced on main cockpit | 826–933 | M00068 | non-negotiable | false | 10 |
| R00800 | Three big wins regression alerts emit via selfdef integration channels | 826–933 | M00068 | non-negotiable | true | 10 |
| R00801 | Constraint automata — JSON FSM tracks open/close brace + colon + comma + string | 916 | M00074 | non-negotiable | false | 10 |
| R00802 | Constraint automata — JSON FSM rejects invalid token transitions | 916 | M00074 | non-negotiable | false | 10 |
| R00803 | Constraint automata — tool-call FSM tracks function name → arg shape → close | 917 | M00075 | non-negotiable | false | 10 |
| R00804 | Constraint automata — tool-call FSM rejects forbidden tool names per branch | 917 | M00075 | non-negotiable | false | 10 |
| R00805 | Constraint automata — shell-command FSM rejects sudo / rm -rf / dd / chmod 777 etc. | 916–918 | M00074 | non-negotiable | true | 10 |
| R00806 | Constraint automata — patch FSM tracks file path + diff hunks + end-of-diff | 916–918 | M00074 | non-negotiable | false | 10 |
| R00807 | Constraint automata — budget counter decrements per-token / per-branch | 918 | M00076 | non-negotiable | false | 10 |
| R00808 | Constraint automata — budget counter expires branch at 0 | 918 | M00076 | non-negotiable | false | 10 |
| R00809 | Constraint automata FSMs implemented as SIMD (8 branches per AVX-512 vector) | 916–918 | M00074 | non-negotiable | false | 10 |
| R00810 | Constraint automata FSMs serialize/deserialize via bincode | 916–918 | M00074 | non-negotiable | false | 10 |
| R00811 | Auditable trace stored at `/var/lib/sovereign-os/replay/<trace-id>.jsonl` | 898–907 | M00073 | non-negotiable | false | 10 |
| R00812 | Auditable trace file mode 0640 | 898–907 | M00073 | non-negotiable | false | 10 |
| R00813 | Auditable trace file owner `sovereign-os:sovereign-os` | 898–907 | M00073 | non-negotiable | false | 10 |
| R00814 | Auditable trace rotated when ≥ 100 MiB | 898–907 | M00073 | non-negotiable | true | 10 |
| R00815 | Auditable trace ZFS snapshot before every commit transition | 898–907 | M00073 | non-negotiable | true | 10 |
| R00816 | Auditable trace replay supports `--step <N>` for fine-grained scrub | 898–907 | F00423 | non-negotiable | true | 10 |
| R00817 | Auditable trace replay supports `--diff <trace-id1> <trace-id2>` | 898–907 | F00423 | preferable | true | 10 |
| R00818 | Auditable trace replay emits OTel parent span on replay start | 898–907 | F00423 | non-negotiable | false | 10 |
| R00819 | Specialist market — scout discovers specialists at startup | 842–845 | M00070 | non-negotiable | false | 10 |
| R00820 | Specialist market — scout hot-reloads specialists on SIGHUP | 842–845 | M00070 | non-negotiable | true | 10 |
| R00821 | Specialist market — CPU routes per task class to specialist with best eval score | 842–845 | M00070 | non-negotiable | false | 10 |
| R00822 | Specialist market — operator can pin specialist to specific task class | 842–845 | M00070 | non-negotiable | true | 10 |
| R00823 | Specialist market — operator can blacklist specialist | 842–845 | M00070 | non-negotiable | true | 10 |
| R00824 | Specialist market metric `sovereign_os_specialist_usage_count{specialist}` | 842–845 | M00070 | non-negotiable | false | 10 |
| R00825 | Specialist market metric `sovereign_os_specialist_eval_score{specialist}` | 842–845 | M00070 | non-negotiable | false | 10 |
| R00826 | Specialist market metric `sovereign_os_specialist_latency_ms{specialist}` | 842–845 | M00070 | non-negotiable | false | 10 |
| R00827 | Request lifecycle observability — OTel parent span per request | 850–860 | M00071 | non-negotiable | false | 10 |
| R00828 | Request lifecycle observability — OTel child span per stage (10 stages) | 850–860 | M00071 | non-negotiable | false | 10 |
| R00829 | Request lifecycle observability — child spans carry stage name + organ + latency | 850–860 | M00071 | non-negotiable | false | 10 |
| R00830 | Request lifecycle replay supports operator-driven fast-forward / rewind | 850–860 | M00071 | non-negotiable | true | 10 |
| R00831 | Request lifecycle replay supports operator-driven step-into per organ | 850–860 | M00071 | non-negotiable | true | 10 |
| R00832 | Coding workflow split — 4090 grep tool runs ripgrep | 866 | M00072 | non-negotiable | false | 10 |
| R00833 | Coding workflow split — 4090 small-patch tool runs scout model on diff context | 867 | M00072 | non-negotiable | false | 10 |
| R00834 | Coding workflow split — 4090 speculation tool runs scout model on N-token continuation | 868 | M00072 | non-negotiable | false | 10 |
| R00835 | Coding workflow split — 4090 test-classification tool tags failures (assertion/import/timeout/permission) | 869 | M00072 | non-negotiable | false | 10 |
| R00836 | Coding workflow split — CPU dep-graph tool parses imports/requires/dependencies | 872 | M00072 | non-negotiable | false | 10 |
| R00837 | Coding workflow split — CPU risk-scoring tool emits per-path risk class | 873 | M00072 | non-negotiable | false | 10 |
| R00838 | Coding workflow split — CPU scheduling tool packs queue | 874 | M00072 | non-negotiable | false | 10 |
| R00839 | Coding workflow split — CPU grammar tool enforces JSON / language-specific grammar | 875 | M00072 | non-negotiable | false | 10 |
| R00840 | Coding workflow split — CPU merge tool deduplicates patches | 876 | M00072 | non-negotiable | false | 10 |
| R00841 | Coding workflow split — RTX PRO architectural review accepts long-context architectural questions | 878 | M00072 | non-negotiable | false | 10 |
| R00842 | Coding workflow split — RTX PRO final-review accepts diff + accepts/rejects with reason | 879 | M00072 | non-negotiable | false | 10 |
| R00843 | Coding workflow split — RTX PRO hard-bug accepts failing-test context + proposes investigation steps | 880 | M00072 | non-negotiable | false | 10 |
| R00844 | Coding workflow split — RTX PRO long-context accepts repo-summary + task description | 881 | M00072 | non-negotiable | false | 10 |
| R00845 | Coding workflow operator override — operator can manually route task to different organ | 862–882 | M00072 | non-negotiable | true | 10 |
| R00846 | Branch RNG uses xoshiro256++ algorithm | 752–760 | M00077 | non-negotiable | false | 10 |
| R00847 | Branch RNG seeded from blake3(branch_id ‖ parent_id ‖ daemon_secret) | 752–760 | M00077 | non-negotiable | false | 10 |
| R00848 | Branch RNG independent streams per branch (parent and child use distinct seeds) | 752–760 | M00077 | non-negotiable | false | 10 |
| R00849 | Branch RNG state persisted across checkpoint | 752–760 | M00077 | non-negotiable | false | 10 |
| R00850 | Branch RNG state restorable for deterministic replay | 752–760 | M00077 | non-negotiable | false | 10 |

— End of M005 milestone file.
