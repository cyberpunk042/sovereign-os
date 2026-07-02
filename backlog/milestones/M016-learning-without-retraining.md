# M016 — Learning without retraining

> Parent: `backlog/milestones/INDEX.md` row M016 (dump 4004–4347).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 4004–4347.
> All entries below are extracted from the dump line range. No invention.

> **AVX++ canon update — 2026-05-19**: this milestone is affected by backward-sweep redefinition(s) — Profiles memory-lens-to-authority-gate (BREAKING) + Trust Rings 0..4 (ADDITIVE). See sovereign-os M061 for canonical pinning (commit 6f07dca). R-rows below are interpreted under the canonical later definitions per operator standing direction "layered: new direction ON TOP OF prior direction — never discarded".


## Epics (E0136–E0145)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0136 | Learning without retraining — local system improves before any fine-tune | 4019–4030 |
| E0137 | Research substrate — Reflexion / ReWOO / LATS / Voyager | 4023–4028 |
| E0138 | The Rule — do NOT start with fine-tuning | 4032–4048 |
| E0139 | Experience Records — bitfield hot + text cold | 4050–4078 |
| E0140 | Failure Codes Are Gold — structured 10-code taxonomy + AVX-512 episode scan | 4080–4109 |
| E0141 | Reflexion But Disciplined — 6-step typed reflection pipeline | 4111–4140 |
| E0142 | Skill Library — Voyager-style skills-as-code with YAML contract | 4142–4175 |
| E0143 | Skill Promotion Pipeline — candidate → sandbox → validation → oracle → user → draft → promote | 4177–4191 |
| E0144 | Learning As Policy Update — typed, auditable, reversible policy diff records | 4193–4226 |
| E0145 | Hardware-aware tree search + ReWOO + full learning loop + 8th plane "Learning Plane" | 4228–4346 |

## Modules (M00250–M00267)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00250 | Pre-fine-tune learning surface — experience memory / policy updates / prompt+program optimization / skill libraries / routing / cache / failure taxonomies | 4037–4046 | E0138 |
| M00251 | `Experience` record bitfield — task_type / branch_policy / model_route / tool_mask / outcome / failure_code / latency_bucket / artifact_ref | 4054–4064 | E0139 |
| M00252 | Cold natural-language reflection fields — What failed / What fixed it / Which tool was useful / Which memory mattered / Which branch was waste / What should be tried first next time | 4069–4076 | E0139 |
| M00253 | Failure-code taxonomy — 0x01 invalid_schema / 0x02 bad_tool_args / 0x03 test_failed / 0x04 missing_context / 0x05 hallucinated_api / 0x06 permission_denied / 0x07 timeout / 0x08 duplicate_branch / 0x09 low_oracle_agreement / 0x0A user_rejected | 4087–4097 | E0140 |
| M00254 | AVX-512 episode scan — same task type / same repo / same tool / same failure / same model route | 4101–4107 | E0140 |
| M00255 | Reflexion pipeline stage — collect objective outcome | 4120 | E0141 |
| M00256 | Reflexion pipeline stage — classify failure code | 4121 | E0141 |
| M00257 | Reflexion pipeline stage — generate short reflection | 4122 | E0141 |
| M00258 | Reflexion pipeline stage — validate reflection against trace | 4123 | E0141 |
| M00259 | Reflexion pipeline stage — store typed lesson + text | 4124 | E0141 |
| M00260 | Reflexion pipeline stage — retrieve only when matching conditions apply | 4125 | E0141 |
| M00261 | Skill registry — repo-specific build / test triage / document parsing / benchmark harness / safe package install / API usage / ZFS snapshot / model serving launch profile | 4148–4156 | E0142 |
| M00262 | Skill YAML contract — name / inputs / preconditions / commands / risk / side_effects / success_metric | 4161–4173 | E0142 |
| M00263 | Skill promotion 6-stage pipeline — candidate → sandbox → deterministic-validation → oracle review → user-approval-if-risky → store-as-draft → promote-after-repeated-success | 4181–4188 | E0143 |
| M00264 | Policy-update record — condition_mask / old_policy / new_policy / evidence_count / success_delta / approved_by / rollback_ref | 4217–4224 | E0144 |
| M00265 | Hardware-aware tree search — 4090 expands / CPU prunes / Blackwell evaluates / ZFS logs + 8-field tree node + 5 AVX-512 frontier operations | 4230–4262 | E0145 |
| M00266 | ReWOO-inspired plan-batch-collect-synthesize pipeline | 4267–4294 | E0145 |
| M00267 | Learning Plane (8th plane) — mutates branch policies / routing thresholds / retrieval filters / prompt+program templates / skill library / cache admission / tool schemas / human gate thresholds | 4316–4344 | E0145 |

## Features (F01276–F01360)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01276 | Toggle learning-plane backend (rust-native / reflexion-bridge / voyager-bridge) | 4023–4028 | E0137 | mode | true |
| F01277 | Profile knob — `learning_plane_backend = rust_native \| reflexion \| voyager` | 4023–4028 | E0137 | profile | true |
| F01278 | Env var `SOVEREIGN_LEARNING_PLANE_BACKEND` | 4023–4028 | E0137 | env_var | true |
| F01279 | CLI `--learning-plane-backend <name>` | 4023–4028 | E0137 | cli_verb | true |
| F01280 | Fine-tuning guard — refuse to start fine-tune before pre-fine-tune surfaces explored | 4034 | E0138 | composite | true |
| F01281 | `Experience` row field — `task_type` | 4056 | M00251 | data_model | false |
| F01282 | `Experience` row field — `branch_policy` | 4057 | M00251 | data_model | false |
| F01283 | `Experience` row field — `model_route` | 4058 | M00251 | data_model | false |
| F01284 | `Experience` row field — `tool_mask` | 4059 | M00251 | data_model | false |
| F01285 | `Experience` row field — `outcome` | 4060 | M00251 | data_model | false |
| F01286 | `Experience` row field — `failure_code` | 4061 | M00251 | data_model | false |
| F01287 | `Experience` row field — `latency_bucket` | 4062 | M00251 | data_model | false |
| F01288 | `Experience` row field — `artifact_ref` | 4063 | M00251 | data_model | false |
| F01289 | Cold reflection field — What failed | 4070 | M00252 | data_model | true |
| F01290 | Cold reflection field — What fixed it | 4071 | M00252 | data_model | true |
| F01291 | Cold reflection field — Which tool was useful | 4072 | M00252 | data_model | true |
| F01292 | Cold reflection field — Which memory mattered | 4073 | M00252 | data_model | true |
| F01293 | Cold reflection field — Which branch was waste | 4074 | M00252 | data_model | true |
| F01294 | Cold reflection field — What should be tried first next time | 4075 | M00252 | data_model | true |
| F01295 | Failure code — `0x01 invalid_schema` | 4087 | M00253 | data_model | false |
| F01296 | Failure code — `0x02 bad_tool_args` | 4088 | M00253 | data_model | false |
| F01297 | Failure code — `0x03 test_failed` | 4089 | M00253 | data_model | false |
| F01298 | Failure code — `0x04 missing_context` | 4090 | M00253 | data_model | false |
| F01299 | Failure code — `0x05 hallucinated_api` | 4091 | M00253 | data_model | false |
| F01300 | Failure code — `0x06 permission_denied` | 4092 | M00253 | data_model | false |
| F01301 | Failure code — `0x07 timeout` | 4093 | M00253 | data_model | false |
| F01302 | Failure code — `0x08 duplicate_branch` | 4094 | M00253 | data_model | false |
| F01303 | Failure code — `0x09 low_oracle_agreement` | 4095 | M00253 | data_model | false |
| F01304 | Failure code — `0x0A user_rejected` | 4096 | M00253 | data_model | false |
| F01305 | AVX-512 episode-scan API — same task_type | 4102 | M00254 | composite | false |
| F01306 | AVX-512 episode-scan API — same repo | 4103 | M00254 | composite | false |
| F01307 | AVX-512 episode-scan API — same tool | 4104 | M00254 | composite | false |
| F01308 | AVX-512 episode-scan API — same failure | 4105 | M00254 | composite | false |
| F01309 | AVX-512 episode-scan API — same model route | 4106 | M00254 | composite | false |
| F01310 | Reflection-quality gate — runtime rejects low-information reflections | 4140 | E0141 | composite | false |
| F01311 | Reflection good-example reference — "npm test failed because jest config expected ESM" | 4131 | E0141 | composite | false |
| F01312 | Reflection bad-example reference — "I should be more careful" (rejected) | 4136 | E0141 | composite | false |
| F01313 | Skill catalog — repo-specific build procedure | 4149 | M00261 | composite | true |
| F01314 | Skill catalog — test triage script | 4150 | M00261 | composite | true |
| F01315 | Skill catalog — document parsing recipe | 4151 | M00261 | composite | true |
| F01316 | Skill catalog — benchmark harness | 4152 | M00261 | composite | true |
| F01317 | Skill catalog — safe package install workflow | 4153 | M00261 | composite | true |
| F01318 | Skill catalog — API usage pattern | 4154 | M00261 | composite | true |
| F01319 | Skill catalog — ZFS snapshot workflow | 4155 | M00261 | composite | true |
| F01320 | Skill catalog — model serving launch profile | 4156 | M00261 | composite | true |
| F01321 | Skill YAML field — `name` | 4162 | M00262 | data_model | false |
| F01322 | Skill YAML field — `inputs` | 4163 | M00262 | data_model | false |
| F01323 | Skill YAML field — `preconditions` | 4165 | M00262 | data_model | false |
| F01324 | Skill YAML field — `commands` | 4167 | M00262 | data_model | false |
| F01325 | Skill YAML field — `risk` | 4169 | M00262 | data_model | false |
| F01326 | Skill YAML field — `side_effects` | 4170 | M00262 | data_model | false |
| F01327 | Skill YAML field — `success_metric` | 4171 | M00262 | data_model | false |
| F01328 | Skill suggestion authority — models suggest, host commits after validation | 4175 | M00262 | composite | false |
| F01329 | Skill promotion stage 1 — sandbox execution | 4183 | M00263 | composite | false |
| F01330 | Skill promotion stage 2 — deterministic validation | 4184 | M00263 | composite | false |
| F01331 | Skill promotion stage 3 — oracle review | 4185 | M00263 | composite | false |
| F01332 | Skill promotion stage 4 — user approval if risky | 4186 | M00263 | composite | true |
| F01333 | Skill promotion stage 5 — store as draft | 4187 | M00263 | composite | false |
| F01334 | Skill promotion stage 6 — promote after repeated success | 4188 | M00263 | composite | false |
| F01335 | Policy-update record field — `condition_mask` | 4218 | M00264 | data_model | false |
| F01336 | Policy-update record field — `old_policy` | 4219 | M00264 | data_model | false |
| F01337 | Policy-update record field — `new_policy` | 4220 | M00264 | data_model | false |
| F01338 | Policy-update record field — `evidence_count` | 4221 | M00264 | data_model | false |
| F01339 | Policy-update record field — `success_delta` | 4222 | M00264 | data_model | false |
| F01340 | Policy-update record field — `approved_by` | 4223 | M00264 | data_model | false |
| F01341 | Policy-update record field — `rollback_ref` | 4224 | M00264 | data_model | false |
| F01342 | Tree-search node field — `state_hash` | 4244 | M00265 | data_model | false |
| F01343 | Tree-search node field — `parent` | 4245 | M00265 | data_model | false |
| F01344 | Tree-search node field — `score` | 4246 | M00265 | data_model | false |
| F01345 | Tree-search node field — `visit_count` | 4247 | M00265 | data_model | false |
| F01346 | Tree-search node field — `risk` | 4248 | M00265 | data_model | false |
| F01347 | Tree-search node field — `budget` | 4249 | M00265 | data_model | false |
| F01348 | Tree-search node field — `kv_ref` | 4250 | M00265 | data_model | false |
| F01349 | Tree-search node field — `tool_state` | 4251 | M00265 | data_model | false |
| F01350 | AVX-512 frontier operation — select top candidates | 4257 | M00265 | composite | false |
| F01351 | AVX-512 frontier operation — drop expired nodes | 4258 | M00265 | composite | false |
| F01352 | AVX-512 frontier operation — merge duplicate states | 4259 | M00265 | composite | false |
| F01353 | AVX-512 frontier operation — filter tool-forbidden paths | 4260 | M00265 | composite | false |
| F01354 | AVX-512 frontier operation — pack oracle eval batch | 4261 | M00265 | composite | false |
| F01355 | ReWOO pipeline — plan all needed observations | 4279 | M00266 | composite | true |
| F01356 | ReWOO pipeline — batch tool calls | 4280 | M00266 | composite | true |
| F01357 | ReWOO pipeline — collect observations | 4281 | M00266 | composite | true |
| F01358 | ReWOO pipeline — synthesize once | 4282 | M00266 | composite | true |
| F01359 | Dashboard — failure-code distribution heatmap (per repo / per task type) + Dashboard — skill library state (draft / promoted / deprecated) + Dashboard — policy-update history (chronological with rollback) | 4087–4226 | E0144 | dashboard | true |
| F01360 | Composite — Learning Plane is the 8th plane | 4318–4326 | M00267 | composite | false |

## Requirements (R02551–R02720)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R02551 | Local system should improve over time before you ever fine-tune a model | 4021 | E0136 | non-negotiable | false | 10 |
| R02552 | Reflexion improves agents by converting feedback into verbal memory rather than changing model weights | 4025 | E0137 | non-negotiable | false | 10 |
| R02553 | ReWOO separates reasoning/planning from observations to reduce repeated token consumption | 4026 | E0137 | non-negotiable | false | 10 |
| R02554 | ReWOO makes tool-augmented reasoning more efficient | 4026 | E0137 | non-negotiable | false | 10 |
| R02555 | LATS uses tree-search ideas to combine reasoning, acting, and planning | 4027 | E0137 | non-negotiable | false | 10 |
| R02556 | Voyager stores successful behaviors as executable code skills, not just text memories | 4028 | E0137 | non-negotiable | false | 10 |
| R02557 | Runtime synthesizes Reflexion + ReWOO + LATS + Voyager into a deterministic local learning system | 4030 | E0136 | non-negotiable | false | 10 |
| R02558 | Do NOT start with fine-tuning | 4034 | E0138 | non-negotiable | false | 10 |
| R02559 | Pre-fine-tune surface — experience memory | 4039 | M00250 | non-negotiable | false | 10 |
| R02560 | Pre-fine-tune surface — policy updates | 4040 | M00250 | non-negotiable | false | 10 |
| R02561 | Pre-fine-tune surface — prompt/program optimization | 4041 | M00250 | non-negotiable | false | 10 |
| R02562 | Pre-fine-tune surface — skill libraries | 4042 | M00250 | non-negotiable | false | 10 |
| R02563 | Pre-fine-tune surface — routing improvements | 4043 | M00250 | non-negotiable | false | 10 |
| R02564 | Pre-fine-tune surface — cache improvements | 4044 | M00250 | non-negotiable | false | 10 |
| R02565 | Pre-fine-tune surface — failure taxonomies | 4045 | M00250 | non-negotiable | false | 10 |
| R02566 | Pre-fine-tune is safer, inspectable, reversible | 4048 | E0138 | non-negotiable | false | 10 |
| R02567 | Every task attempt produces an experience record | 4052 | M00251 | non-negotiable | false | 10 |
| R02568 | Experience record carries `task_type` (u64) | 4056 | M00251 | non-negotiable | false | 10 |
| R02569 | Experience record carries `branch_policy` (u64) | 4057 | M00251 | non-negotiable | false | 10 |
| R02570 | Experience record carries `model_route` (u64) | 4058 | M00251 | non-negotiable | false | 10 |
| R02571 | Experience record carries `tool_mask` (u64) | 4059 | M00251 | non-negotiable | false | 10 |
| R02572 | Experience record carries `outcome` (u64) | 4060 | M00251 | non-negotiable | false | 10 |
| R02573 | Experience record carries `failure_code` (u64) | 4061 | M00251 | non-negotiable | false | 10 |
| R02574 | Experience record carries `latency_bucket` (u64) | 4062 | M00251 | non-negotiable | false | 10 |
| R02575 | Experience record carries `artifact_ref` (u64) | 4063 | M00251 | non-negotiable | false | 10 |
| R02576 | Bitfield version is hot | 4078 | E0139 | non-negotiable | false | 10 |
| R02577 | Text version is cold | 4078 | E0139 | non-negotiable | false | 10 |
| R02578 | Cold field — "What failed?" | 4070 | M00252 | non-negotiable | true | 10 |
| R02579 | Cold field — "What fixed it?" | 4071 | M00252 | non-negotiable | true | 10 |
| R02580 | Cold field — "Which tool was useful?" | 4072 | M00252 | non-negotiable | true | 10 |
| R02581 | Cold field — "Which memory mattered?" | 4073 | M00252 | non-negotiable | true | 10 |
| R02582 | Cold field — "Which branch was waste?" | 4074 | M00252 | non-negotiable | true | 10 |
| R02583 | Cold field — "What should be tried first next time?" | 4075 | M00252 | non-negotiable | true | 10 |
| R02584 | Most agent systems just save chat history — that is weak | 4082 | E0140 | non-negotiable | false | 10 |
| R02585 | Use structured failure codes | 4084 | M00253 | non-negotiable | false | 10 |
| R02586 | Failure code 0x01 invalid_schema | 4087 | M00253 | non-negotiable | false | 10 |
| R02587 | Failure code 0x02 bad_tool_args | 4088 | M00253 | non-negotiable | false | 10 |
| R02588 | Failure code 0x03 test_failed | 4089 | M00253 | non-negotiable | false | 10 |
| R02589 | Failure code 0x04 missing_context | 4090 | M00253 | non-negotiable | false | 10 |
| R02590 | Failure code 0x05 hallucinated_api | 4091 | M00253 | non-negotiable | false | 10 |
| R02591 | Failure code 0x06 permission_denied | 4092 | M00253 | non-negotiable | false | 10 |
| R02592 | Failure code 0x07 timeout | 4093 | M00253 | non-negotiable | false | 10 |
| R02593 | Failure code 0x08 duplicate_branch | 4094 | M00253 | non-negotiable | false | 10 |
| R02594 | Failure code 0x09 low_oracle_agreement | 4095 | M00253 | non-negotiable | false | 10 |
| R02595 | Failure code 0x0A user_rejected | 4096 | M00253 | non-negotiable | false | 10 |
| R02596 | AVX-512 scans thousands of prior episodes for "same task type" | 4102 | M00254 | non-negotiable | false | 10 |
| R02597 | AVX-512 scans thousands of prior episodes for "same repo" | 4103 | M00254 | non-negotiable | false | 10 |
| R02598 | AVX-512 scans thousands of prior episodes for "same tool" | 4104 | M00254 | non-negotiable | false | 10 |
| R02599 | AVX-512 scans thousands of prior episodes for "same failure" | 4105 | M00254 | non-negotiable | false | 10 |
| R02600 | AVX-512 scans thousands of prior episodes for "same model route" | 4106 | M00254 | non-negotiable | false | 10 |
| R02601 | This gives deterministic retrieval of lessons | 4109 | M00254 | non-negotiable | false | 10 |
| R02602 | Reflection should not become vague self-talk | 4115 | E0141 | non-negotiable | false | 10 |
| R02603 | Reflexion stage 1 — collect objective outcome | 4120 | M00255 | non-negotiable | false | 10 |
| R02604 | Reflexion stage 2 — classify failure code | 4121 | M00256 | non-negotiable | false | 10 |
| R02605 | Reflexion stage 3 — generate short reflection | 4122 | M00257 | non-negotiable | false | 10 |
| R02606 | Reflexion stage 4 — validate reflection against trace | 4123 | M00258 | non-negotiable | false | 10 |
| R02607 | Reflexion stage 5 — store typed lesson + text | 4124 | M00259 | non-negotiable | false | 10 |
| R02608 | Reflexion stage 6 — retrieve only when matching conditions apply | 4125 | M00260 | non-negotiable | false | 10 |
| R02609 | Reflection should be attached to facts (good — "npm test failed because jest config expected ESM") | 4128–4131 | E0141 | non-negotiable | false | 10 |
| R02610 | Reflection rejected if low-information ("I should be more careful") | 4136 | E0141 | non-negotiable | false | 10 |
| R02611 | CPU/runtime rejects low-information reflections | 4140 | E0141 | non-negotiable | false | 10 |
| R02612 | Voyager skills-as-code idea applies — skill catalog includes repo-specific build procedure | 4149 | M00261 | non-negotiable | true | 10 |
| R02613 | Skill — test triage script | 4150 | M00261 | non-negotiable | true | 10 |
| R02614 | Skill — document parsing recipe | 4151 | M00261 | non-negotiable | true | 10 |
| R02615 | Skill — benchmark harness | 4152 | M00261 | non-negotiable | true | 10 |
| R02616 | Skill — safe package install workflow | 4153 | M00261 | non-negotiable | true | 10 |
| R02617 | Skill — API usage pattern | 4154 | M00261 | non-negotiable | true | 10 |
| R02618 | Skill — ZFS snapshot workflow | 4155 | M00261 | non-negotiable | true | 10 |
| R02619 | Skill — model serving launch profile | 4156 | M00261 | non-negotiable | true | 10 |
| R02620 | A skill is not merely prose | 4159 | M00262 | non-negotiable | false | 10 |
| R02621 | Skill YAML — `name` field | 4162 | M00262 | non-negotiable | false | 10 |
| R02622 | Skill YAML — `inputs` field | 4163 | M00262 | non-negotiable | false | 10 |
| R02623 | Skill YAML — `preconditions` field | 4165 | M00262 | non-negotiable | false | 10 |
| R02624 | Skill YAML — `commands` field | 4167 | M00262 | non-negotiable | false | 10 |
| R02625 | Skill YAML — `risk` field | 4169 | M00262 | non-negotiable | false | 10 |
| R02626 | Skill YAML — `side_effects` field | 4170 | M00262 | non-negotiable | false | 10 |
| R02627 | Skill YAML — `success_metric` field | 4171 | M00262 | non-negotiable | false | 10 |
| R02628 | Skills suggested by models, committed by host after validation | 4175 | M00262 | non-negotiable | false | 10 |
| R02629 | Do not instantly trust a new skill | 4180 | M00263 | non-negotiable | false | 10 |
| R02630 | Skill promotion — candidate skill | 4183 | M00263 | non-negotiable | false | 10 |
| R02631 | Skill promotion — sandbox execution | 4183 | M00263 | non-negotiable | false | 10 |
| R02632 | Skill promotion — deterministic validation | 4184 | M00263 | non-negotiable | false | 10 |
| R02633 | Skill promotion — oracle review | 4185 | M00263 | non-negotiable | false | 10 |
| R02634 | Skill promotion — user approval if risky | 4186 | M00263 | non-negotiable | true | 10 |
| R02635 | Skill promotion — store as draft | 4187 | M00263 | non-negotiable | false | 10 |
| R02636 | Skill promotion — promote after repeated success | 4188 | M00263 | non-negotiable | false | 10 |
| R02637 | This is how the machine evolves without becoming chaotic | 4191 | E0143 | non-negotiable | false | 10 |
| R02638 | Routing learning — for repo X, scout A produces bad patches, scout B has higher oracle acceptance, use B first | 4198–4201 | M00264 | non-negotiable | true | 10 |
| R02639 | Routing learning — for "JSON extraction" task type, strict grammar improves validity but hurts semantic accuracy, use loose draft then strict final | 4203–4206 | M00264 | non-negotiable | true | 10 |
| R02640 | Routing learning — package manager calls fail in sandbox without network, ask for network scope before attempting | 4208–4210 | M00264 | non-negotiable | true | 10 |
| R02641 | These are policy updates, not model updates | 4212 | M00264 | non-negotiable | false | 10 |
| R02642 | Policy-update record carries `condition_mask` | 4218 | M00264 | non-negotiable | false | 10 |
| R02643 | Policy-update record carries `old_policy` | 4219 | M00264 | non-negotiable | false | 10 |
| R02644 | Policy-update record carries `new_policy` | 4220 | M00264 | non-negotiable | false | 10 |
| R02645 | Policy-update record carries `evidence_count` | 4221 | M00264 | non-negotiable | false | 10 |
| R02646 | Policy-update record carries `success_delta` | 4222 | M00264 | non-negotiable | false | 10 |
| R02647 | Policy-update record carries `approved_by` | 4223 | M00264 | non-negotiable | false | 10 |
| R02648 | Policy-update record carries `rollback_ref` | 4224 | M00264 | non-negotiable | false | 10 |
| R02649 | Policy updates are deterministic, auditable, reversible | 4226 | M00264 | non-negotiable | false | 10 |
| R02650 | LATS-style tree search is expensive | 4230 | M00265 | non-negotiable | false | 10 |
| R02651 | Hardware makes tree search practical if controlled | 4230 | M00265 | non-negotiable | false | 10 |
| R02652 | Tree search — 4090 expands candidate branches | 4235 | M00265 | non-negotiable | false | 10 |
| R02653 | Tree search — CPU prunes with bit policies | 4236 | M00265 | non-negotiable | false | 10 |
| R02654 | Tree search — Blackwell evaluates only frontier winners | 4237 | M00265 | non-negotiable | false | 10 |
| R02655 | Tree search — ZFS logs tree outcomes | 4238 | M00265 | non-negotiable | false | 10 |
| R02656 | Tree node carries `state_hash` | 4244 | M00265 | non-negotiable | false | 10 |
| R02657 | Tree node carries `parent` | 4245 | M00265 | non-negotiable | false | 10 |
| R02658 | Tree node carries `score` | 4246 | M00265 | non-negotiable | false | 10 |
| R02659 | Tree node carries `visit_count` | 4247 | M00265 | non-negotiable | false | 10 |
| R02660 | Tree node carries `risk` | 4248 | M00265 | non-negotiable | false | 10 |
| R02661 | Tree node carries `budget` | 4249 | M00265 | non-negotiable | false | 10 |
| R02662 | Tree node carries `kv_ref` | 4250 | M00265 | non-negotiable | false | 10 |
| R02663 | Tree node carries `tool_state` | 4251 | M00265 | non-negotiable | false | 10 |
| R02664 | AVX-512 frontier op — select top candidates | 4257 | M00265 | non-negotiable | false | 10 |
| R02665 | AVX-512 frontier op — drop expired nodes | 4258 | M00265 | non-negotiable | false | 10 |
| R02666 | AVX-512 frontier op — merge duplicate states | 4259 | M00265 | non-negotiable | false | 10 |
| R02667 | AVX-512 frontier op — filter tool-forbidden paths | 4260 | M00265 | non-negotiable | false | 10 |
| R02668 | AVX-512 frontier op — pack oracle eval batch | 4261 | M00265 | non-negotiable | false | 10 |
| R02669 | This is systems engineering, not abstract AI | 4264 | E0145 | non-negotiable | false | 10 |
| R02670 | ReWOO separates planning from observation (very useful for cost) | 4268 | M00266 | non-negotiable | false | 10 |
| R02671 | ReWOO pipeline — plan all needed observations | 4279 | M00266 | non-negotiable | false | 10 |
| R02672 | ReWOO pipeline — batch tool calls | 4280 | M00266 | non-negotiable | false | 10 |
| R02673 | ReWOO pipeline — collect observations | 4281 | M00266 | non-negotiable | false | 10 |
| R02674 | ReWOO pipeline — synthesize once | 4282 | M00266 | non-negotiable | false | 10 |
| R02675 | Research/retrieval task — 4090 drafts observation plan / CPU deduplicates / tools batch / Blackwell synthesizes | 4288–4292 | M00266 | non-negotiable | false | 10 |
| R02676 | Saves tokens and tool latency | 4295 | M00266 | non-negotiable | false | 10 |
| R02677 | Learning loop step 1 — Execute task with branch runtime | 4302 | E0145 | non-negotiable | false | 10 |
| R02678 | Learning loop step 2 — Record trace, metrics, outcome | 4303 | E0145 | non-negotiable | false | 10 |
| R02679 | Learning loop step 3 — Classify failure/success deterministically | 4304 | E0145 | non-negotiable | false | 10 |
| R02680 | Learning loop step 4 — Generate reflection only if useful | 4305 | E0145 | non-negotiable | false | 10 |
| R02681 | Learning loop step 5 — Extract possible skill/policy update | 4306 | E0145 | non-negotiable | false | 10 |
| R02682 | Learning loop step 6 — Validate against replay | 4307 | E0145 | non-negotiable | false | 10 |
| R02683 | Learning loop step 7 — Store in experience memory | 4308 | E0145 | non-negotiable | false | 10 |
| R02684 | Learning loop step 8 — Promote after evidence threshold | 4309 | E0145 | non-negotiable | false | 10 |
| R02685 | This is how the system gets better every week | 4312 | E0145 | non-negotiable | false | 10 |
| R02686 | 8th plane is Learning Plane | 4326 | M00267 | non-negotiable | false | 10 |
| R02687 | Learning Plane does NOT mutate weights first | 4329 | M00267 | non-negotiable | false | 10 |
| R02688 | Learning Plane mutates branch policies | 4334 | M00267 | non-negotiable | false | 10 |
| R02689 | Learning Plane mutates routing thresholds | 4335 | M00267 | non-negotiable | false | 10 |
| R02690 | Learning Plane mutates retrieval filters | 4336 | M00267 | non-negotiable | false | 10 |
| R02691 | Learning Plane mutates prompt/program templates | 4337 | M00267 | non-negotiable | false | 10 |
| R02692 | Learning Plane mutates skill library | 4338 | M00267 | non-negotiable | false | 10 |
| R02693 | Learning Plane mutates cache admission | 4339 | M00267 | non-negotiable | false | 10 |
| R02694 | Learning Plane mutates tool schemas | 4340 | M00267 | non-negotiable | false | 10 |
| R02695 | Learning Plane mutates human gate thresholds | 4341 | M00267 | non-negotiable | false | 10 |
| R02696 | The machine becomes not just fast, but experienced | 4346 | E0145 | non-negotiable | false | 10 |
| R02697 | Learning-plane backend operator-overrideable (rust_native / reflexion / voyager) | 4023–4028 | F01276 | non-negotiable | true | 10 |
| R02698 | Env var `SOVEREIGN_LEARNING_PLANE_BACKEND` | 4023–4028 | F01278 | non-negotiable | true | 10 |
| R02699 | CLI `--learning-plane-backend <name>` | 4023–4028 | F01279 | non-negotiable | true | 10 |
| R02700 | Fine-tuning guard refuses to start fine-tune before pre-fine-tune surfaces explored | 4034 | F01280 | non-negotiable | true | 10 |
| R02701 | Dashboard — failure-code distribution heatmap (per repo / per task type) | 4087–4097 | F01359 | non-negotiable | true | 10 |
| R02702 | Dashboard — skill library state (draft / promoted / deprecated) | 4181–4188 | F01359 | non-negotiable | true | 10 |
| R02703 | Dashboard — policy-update history (chronological with rollback) | 4217–4226 | F01359 | non-negotiable | true | 10 |
| R02704 | Test — `Experience` 8-field record round-trip | 4054–4064 | M00251 | non-negotiable | false | 10 |
| R02705 | Test — each failure code 0x01..0x0A maps to its operator-named meaning | 4087–4097 | M00253 | non-negotiable | false | 10 |
| R02706 | Test — AVX-512 episode scan matches scalar reference on 5 axes (task_type / repo / tool / failure / model_route) | 4101–4107 | M00254 | non-negotiable | false | 10 |
| R02707 | Test — reflexion 6-stage pipeline rejects low-information reflection at stage 4 | 4111–4140 | E0141 | non-negotiable | false | 10 |
| R02708 | Test — skill YAML 7-field round-trip | 4161–4173 | M00262 | non-negotiable | false | 10 |
| R02709 | Test — skill promotion 6-stage pipeline halts at oracle-review failure | 4181–4188 | M00263 | non-negotiable | false | 10 |
| R02710 | Test — policy-update record 7-field round-trip + rollback_ref dereferences | 4217–4224 | M00264 | non-negotiable | false | 10 |
| R02711 | Test — tree-search 8-field node round-trip | 4243–4251 | M00265 | non-negotiable | false | 10 |
| R02712 | Test — AVX-512 frontier 5-op set produces same result as scalar reference | 4256–4262 | M00265 | non-negotiable | false | 10 |
| R02713 | Test — ReWOO pipeline reduces total tool calls vs naive think-act loop | 4271–4283 | M00266 | non-negotiable | false | 10 |
| R02714 | Test — Learning Plane never writes weights | 4329 | M00267 | non-negotiable | false | 10 |
| R02715 | Test — Learning Plane mutation paths each respect declared 8-axis mutable surface | 4333–4341 | M00267 | non-negotiable | false | 10 |
| R02716 | Test — Learning loop 8-step end-to-end completes a recorded session | 4302–4309 | E0145 | non-negotiable | false | 10 |
| R02717 | Composite — Learning Plane integrates with M013 observability (metrics feed learning) | 4302–4309 | M00267 | non-negotiable | false | 10 |
| R02718 | Composite — Learning Plane integrates with M015 programming-plane (mutates skill library + prompt templates) | 4338, 4337 | M00267 | non-negotiable | false | 10 |
| R02719 | Composite — Learning Plane integrates with M014 capability tokens (mutates tool schemas + human-gate thresholds) | 4340, 4341 | M00267 | non-negotiable | false | 10 |
| R02720 | Composite — Learning Plane integrates with M012 storage (skill+policy diffs land in ZFS replay log) | 4226 | M00264 | non-negotiable | false | 10 |

— End of M016 milestone file.
