# M042 — Choice architecture — sovereignty as policy-composable

> Parent: `backlog/milestones/INDEX.md` row M042 (dump 12094–12614).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 12094–12614. Operator directive 12365: "Great. dont you worries selfdef and sovereign-os my two project are flexible and the user choses what he want. at every stage.. like you possibly can't even imagine... but yeah they will inherit this conversation later, lets continue".
> All entries below extract verbatim. No invention.

## Epics (E0398–E0407)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0398 | Architecture-grade value extracted — sources cluster into 6 major pillars: MAP / map-before-act + Spec + workflow orchestration + Agent harness engineering + Routing + cost-aware model selection + Sandboxes + secrets isolation + Model compression + hardware-aware model lab; "The breakthrough is not one model. The breakthrough is the harness, the runtime, the workflow, the router, the memory, the evals, and the hardware-aware execution substrate" | 12106–12126 |
| E0399 | Methodology — "MAP → SPEC → TEST → ACT → EVAL → COMMIT → LEARN" with 7-step definitions: MAP (understand environment before action) / SPEC (define intended behavior and constraints) / TEST (executable truth / TDD / regression checks) / ACT (model/tool/workflow execution) / EVAL (trajectory, cost, quality, risk, latency) / COMMIT (gated side effects, snapshots, review) / LEARN (update memory, model registry, profiles, skills) | 12137–12165 |
| E0400 | Source-by-source meaning — MAP "Do not let agents learn the environment only by failing through it. Build a map first" (7 maps: repo/test/tool/risk/memory/GUI-world/dependency) / Symphony "Workflow belongs in version-controlled repo artifacts" (6 contracts SPEC.md+WORKFLOW.md+PROFILES.yaml+EVALS.yaml+POLICY.yaml+MODEL_REGISTRY.yaml) / LiteLLM Vault-Proxy "agent sessions need real isolation, persistent sandboxes, and secret protection" (Claude Code/OpenCode/Cline get stub keys; Jean Gateway owns real keys + cost + policy + routing) / NadirClaw "many prompts do not deserve the expensive model" (7-axis routing: simple-complex / private-public / safe-risky / coding-research-gui / local-cloud / fast-careful / cheap-oracle) / Fast BLT "frontier inference is becoming memory-bandwidth-aware and speculation-aware" (4 architectural rules: reduce forward passes + speculate cheaply + verify carefully + avoid memory bandwidth waste) / LLM Compressor "build a model qualification lab" (BF16 baseline / FP8 / GPTQ / SmoothQuant / AWQ / NVFP4-MXFP4 when stable / KV quantization + profile-specific evals) | 12172–12230 |
| E0401 | 7-step deeper implementation TODO — Read MAP PDF deeper for concrete map schemas / Mine Symphony SPEC for WORKFLOW.md-compatible schema / Study LiteLLM Agent Platform sandbox-vault design in detail / Build Anthropic-first gateway compatibility tests / Prototype AVX-512 metadata core / Define first PROFILES.yaml + EVALS.yaml + MODEL_REGISTRY.yaml / Run hardware validation (PCIe + MIG + VFIO + ZFS + NICs + Blackwell FP4) | 12244–12259 |
| E0402 | North Star — Anthropic-first API gateway + deterministic AVX-512 control plane + Blackwell oracle + 4090 scout/sandbox + model portfolio lab + MAP/SPEC/TDD workflow compiler + sandboxed execution + trace-based evals + memory/replay/learning; key phrase "Evidence-driven autonomy" ("Not pure agent freedom. Not rigid workflow prison. A system that maps, specifies, tests, acts, evaluates, commits, and learns, using the right amount of intelligence for the task") | 12262–12286 |
| E0403 | Choice architecture — runtime should NOT be opinionated in the usual product sense; should be POLICY-COMPOSABLE; NOT "This system is local-only / cloud-hybrid / autonomous / safe / powerful" BUT "At each boundary, the user/system chooses: local or cloud / fast or careful / private or shared / automatic or gated / cheap or best / sandbox or host / scout or oracle / spec-first or exploratory / TDD strict or prototype"; "That is sovereignty" | 12368–12395 |
| E0404 | Choice primitive — every action exposes a choice envelope (3 examples): model_route (options: local_scout / local_oracle / cloud_anthropic / cloud_openai; default: local_oracle; requires.cloud_anthropic: user_approval + cost_budget + privacy_clearance) + execution (options: dry_run / sandbox / vm / host; default: sandbox) + development_mode (options: exploratory / spec_driven / tdd / spec_plus_tdd / production_verified); "the system becomes a choice compiler" | 12398–12442 |
| E0405 | Profiles are bundles NOT prisons — 4 example profile bundles (private: local models + no network + no cloud + sandbox tools / careful: map first + spec required + tests required + oracle review / fast: scout first + shallow map + minimal verification / sovereign: user-visible gates + local memory ownership + explicit external calls + replay always on); user can override any axis; distinction: "profile = starting posture / policy = enforced boundary / choice = user agency" | 12446–12491 |
| E0406 | Inheritance layer — selfdef + sovereign-os inherit this conversation; this discussion becomes seed material for 8 durable artifacts: VISION.md (philosophy and system thesis) / ARCHITECTURE.md (planes services hardware mapping) / METHODOLOGY.md (MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN) / PROFILES.yaml (user-selectable operating modes) / POLICY.yaml (hard constraints + capability gates) / MODEL_REGISTRY.yaml (local-cloud-model roles + eval scores) / HARDWARE_PROFILES.yaml (Blackwell/4090/AVX/ZFS/VFIO/MIG modes) / EVALS.yaml (trace tool task quality cost risk evals); "this is how the conversation becomes executable memory" | 12494–12515 |
| E0407 | Deep principle + final phrase — "`sovereign-os` should not merely protect the user. It should give the user **legible control** over intelligence" via 8 transparency questions (What is being asked? / Who is being asked? / What context is exposed? / What cost is incurred? / What can change? / What can be rolled back? / What was learned? / What becomes memory?); "That is self-defense at the intelligence layer"; final phrase "User-sovereign adaptive intelligence runtime" (adaptive=changes strategy per task / intelligent=routes-tests-remembers-evaluates / runtime=executes real workflows / user-sovereign=user owns choices+memory+policy+cost+exposure); "The whole machine becomes a living negotiation between" 8 axes: capability / control / cost / privacy / speed / quality / autonomy / reversibility | 12518–12614 |

## Modules (M00697–M00713)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00697 | Pillar 1 — MAP / map-before-act | 12111 | E0398 |
| M00698 | Pillar 2 — Spec + workflow orchestration | 12112 | E0398 |
| M00699 | Pillar 3 — Agent harness engineering | 12113 | E0398 |
| M00700 | Pillar 4 — Routing + cost-aware model selection | 12114 | E0398 |
| M00701 | Pillar 5 — Sandboxes + secrets isolation | 12115 | E0398 |
| M00702 | Pillar 6 — Model compression + hardware-aware model lab | 12116 | E0398 |
| M00703 | Methodology chain — MAP → SPEC → TEST → ACT → EVAL → COMMIT → LEARN | 12139 | E0399 |
| M00704 | 7 maps inventory — repo / test / tool / risk / memory / GUI-world / dependency | 12182–12188 | E0400 |
| M00705 | 6 inheritance contracts (Symphony) — SPEC.md / WORKFLOW.md / PROFILES.yaml / EVALS.yaml / POLICY.yaml / MODEL_REGISTRY.yaml | 12196–12201 | E0400 |
| M00706 | Vault-proxy pattern — agent sees stub key + Jean Gateway owns real keys/cost/policy/routing | 12210–12215 | E0400 |
| M00707 | 7-axis routing — simple-complex / private-public / safe-risky / coding-research-gui / local-cloud / fast-careful / cheap-oracle | 12219–12225 | E0400 |
| M00708 | Model qualification lab — BF16 baseline / FP8 / GPTQ / SmoothQuant / AWQ / NVFP4-MXFP4 / KV quantization | 12233–12239 | E0400 + E0402 |
| M00709 | Choice envelope template — choice.domain / options[] / default / requires{} | 12400–12411 | E0404 |
| M00710 | 4 profile bundles — private / careful / fast / sovereign | 12448–12472 | E0405 |
| M00711 | Profile-vs-Policy-vs-Choice distinction — starting posture / enforced boundary / user agency | 12489–12491 | E0405 |
| M00712 | 8 inheritance artifacts — VISION.md / ARCHITECTURE.md / METHODOLOGY.md / PROFILES.yaml / POLICY.yaml / MODEL_REGISTRY.yaml / HARDWARE_PROFILES.yaml / EVALS.yaml | 12496–12513 | E0406 |
| M00713 | 8 transparency questions + 8 negotiation axes — what asked / who asked / context / cost / change / rollback / learned / memory + capability / control / cost / privacy / speed / quality / autonomy / reversibility | 12530–12613 | E0407 |

## Features (F03486–F03570)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F03486 | Sources cluster into 6 major pillars | 12110 | E0398 |
| F03487 | Together pillars confirm same thesis "breakthrough is not one model" | 12120 | E0398 |
| F03488 | "Breakthrough is the harness, the runtime, the workflow, the router, the memory, the evals, and the hardware-aware execution substrate" | 12126 | E0398 |
| F03489 | Most important extra confirmation came from Agent Harness Engineering survey | 12128 | E0398 |
| F03490 | Survey argues "real-world reliability depends heavily on the execution harness around the model" | 12131 | E0398 |
| F03491 | Survey organizes space into 7: execution / tools / context / lifecycle / observability / verification / governance | 12131 | E0398 |
| F03492 | "Almost exactly our station architecture" | 12133 | E0398 |
| F03493 | Methodology — MAP definition "understand environment before action" | 12141 | M00703 |
| F03494 | Methodology — SPEC definition "define intended behavior and constraints" | 12146 | M00703 |
| F03495 | Methodology — TEST definition "executable truth / TDD / regression checks" | 12150 | M00703 |
| F03496 | Methodology — ACT definition "model/tool/workflow execution" | 12153 | M00703 |
| F03497 | Methodology — EVAL definition "trajectory, cost, quality, risk, latency" | 12157 | M00703 |
| F03498 | Methodology — COMMIT definition "gated side effects, snapshots, review" | 12160 | M00703 |
| F03499 | Methodology — LEARN definition "update memory, model registry, profiles, skills" | 12164 | M00703 |
| F03500 | Methodology — "cleanest extraction from MAP, Symphony, agent eval work, Goldilocks profile idea" | 12168 | E0399 |
| F03501 | MAP doctrine — "Do not let agents learn the environment only by failing through it. Build a map first" | 12175–12179 | M00697 |
| F03502 | Map type — repo map | 12183 | M00704 |
| F03503 | Map type — test map | 12184 | M00704 |
| F03504 | Map type — tool map | 12185 | M00704 |
| F03505 | Map type — risk map | 12186 | M00704 |
| F03506 | Map type — memory map | 12187 | M00704 |
| F03507 | Map type — GUI/world map | 12188 | M00704 |
| F03508 | Map type — dependency map | 12189 | M00704 |
| F03509 | Symphony — "Workflow belongs in version-controlled repo artifacts" | 12194 | M00698 |
| F03510 | Contract — SPEC.md | 12196 | M00705 |
| F03511 | Contract — WORKFLOW.md | 12197 | M00705 |
| F03512 | Contract — PROFILES.yaml | 12198 | M00705 |
| F03513 | Contract — EVALS.yaml | 12199 | M00705 |
| F03514 | Contract — POLICY.yaml | 12200 | M00705 |
| F03515 | Contract — MODEL_REGISTRY.yaml | 12201 | M00705 |
| F03516 | LiteLLM doctrine — "agent sessions need real isolation, persistent sandboxes, and secret protection" | 12206 | M00701 |
| F03517 | Vault-proxy step — agent sees stub credentials | 12211 | M00706 |
| F03518 | Vault-proxy step — sidecar swaps real credentials at wire boundary | 12211 | M00706 |
| F03519 | Station translation — Claude Code gets stub keys | 12213 | M00706 |
| F03520 | Station translation — OpenCode gets stub keys | 12213 | M00706 |
| F03521 | Station translation — Cline gets stub keys | 12213 | M00706 |
| F03522 | Station translation — Jean Gateway owns real keys | 12215 | M00706 |
| F03523 | Station translation — Jean Gateway owns cost | 12215 | M00706 |
| F03524 | Station translation — Jean Gateway owns policy | 12215 | M00706 |
| F03525 | Station translation — Jean Gateway owns routing | 12215 | M00706 |
| F03526 | NadirClaw doctrine — "many prompts do not deserve the expensive model" | 12218 | M00700 |
| F03527 | Routing axis — simple/complex | 12220 | M00707 |
| F03528 | Routing axis — private/public | 12221 | M00707 |
| F03529 | Routing axis — safe/risky | 12222 | M00707 |
| F03530 | Routing axis — coding/research/gui | 12223 | M00707 |
| F03531 | Routing axis — local/cloud | 12224 | M00707 |
| F03532 | Routing axis — fast/careful | 12225 | M00707 |
| F03533 | Routing axis — cheap/oracle | 12226 | M00707 |
| F03534 | Fast BLT doctrine — "frontier inference is becoming memory-bandwidth-aware and speculation-aware" | 12228 | E0400 |
| F03535 | LLM Compressor doctrine — "build a model qualification lab" | 12232 | M00708 |
| F03536 | "Not 'download model, hope'" | 12233 | M00708 |
| F03537 | Implementation TODO 1 — Read MAP PDF deeper for concrete map schemas | 12246 | E0401 |
| F03538 | Implementation TODO 2 — Mine Symphony SPEC for WORKFLOW.md-compatible schema | 12248 | E0401 |
| F03539 | Implementation TODO 3 — Study LiteLLM Agent Platform sandbox/vault design in detail | 12250 | E0401 |
| F03540 | Implementation TODO 4 — Build Anthropic-first gateway compatibility tests | 12252 | E0401 |
| F03541 | Implementation TODO 5 — Prototype AVX-512 metadata core | 12254 | E0401 |
| F03542 | Implementation TODO 6 — Define first PROFILES.yaml / EVALS.yaml / MODEL_REGISTRY.yaml | 12256 | E0401 |
| F03543 | Implementation TODO 7 — Run hardware validation: PCIe, MIG, VFIO, ZFS, NICs, Blackwell FP4 | 12258 | E0401 |
| F03544 | North-Star component — Anthropic-first API gateway | 12264 | E0402 |
| F03545 | North-Star component — deterministic AVX-512 control plane | 12265 | E0402 |
| F03546 | North-Star component — Blackwell oracle | 12266 | E0402 |
| F03547 | North-Star component — 4090 scout/sandbox | 12267 | E0402 |
| F03548 | North-Star component — model portfolio lab | 12268 | E0402 |
| F03549 | North-Star component — MAP/SPEC/TDD workflow compiler | 12269 | E0402 |
| F03550 | North-Star component — sandboxed execution | 12270 | E0402 |
| F03551 | North-Star component — trace-based evals | 12271 | E0402 |
| F03552 | North-Star component — memory/replay/learning | 12272 | E0402 |
| F03553 | Phrase — "Evidence-driven autonomy" | 12277 | E0402 |
| F03554 | "Not pure agent freedom. Not rigid workflow prison. A system that maps, specifies, tests, acts, evaluates, commits, and learns, using the right amount of intelligence for the task" | 12281–12286 | E0402 |
| F03555 | Choice architecture — "runtime should not be opinionated in the usual product sense. It should be policy-composable" | 12372–12376 | E0403 |
| F03556 | Choice boundary axis — local or cloud | 12384 | E0403 |
| F03557 | Choice boundary axis — fast or careful | 12385 | E0403 |
| F03558 | Choice boundary axis — private or shared | 12386 | E0403 |
| F03559 | Choice boundary axis — automatic or gated | 12387 | E0403 |
| F03560 | Choice boundary axis — cheap or best | 12388 | E0403 |
| F03561 | Choice boundary axis — sandbox or host | 12389 | E0403 |
| F03562 | Choice boundary axis — scout or oracle | 12390 | E0403 |
| F03563 | Choice boundary axis — spec-first or exploratory | 12391 | E0403 |
| F03564 | Choice boundary axis — TDD strict or prototype | 12392 | E0403 |
| F03565 | "That is sovereignty" | 12395 | E0403 |
| F03566 | Choice envelope — model_route + execution + development_mode examples + "system becomes a choice compiler" | 12400–12444 | M00709 + E0404 |
| F03567 | Profiles bundles — private / careful / fast / sovereign (4 examples) + user can override any axis + 3-way distinction profile/policy/choice | 12448–12491 | M00710 + M00711 + E0405 |
| F03568 | Inheritance — 8 durable artifacts (VISION/ARCHITECTURE/METHODOLOGY/PROFILES/POLICY/MODEL_REGISTRY/HARDWARE_PROFILES/EVALS) + "this is how the conversation becomes executable memory" | 12494–12515 | M00712 + E0406 |
| F03569 | Deep principle — "legible control over intelligence" via 8 transparency questions + "self-defense at the intelligence layer" | 12525–12544 | M00713 + E0407 |
| F03570 | Final phrase — "User-sovereign adaptive intelligence runtime" (4-component def) + "the whole machine becomes a living negotiation between" 8 axes (capability / control / cost / privacy / speed / quality / autonomy / reversibility) | 12548–12613 | M00713 + E0407 |

## Requirements (R06971–R07140)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R06971 | Sources cluster into 6 major pillars | 12110 | F03486 | non-negotiable | false | 10 |
| R06972 | Pillar 1 — MAP / map-before-act | 12111 | M00697 | non-negotiable | false | 10 |
| R06973 | Pillar 2 — Spec + workflow orchestration | 12112 | M00698 | non-negotiable | false | 10 |
| R06974 | Pillar 3 — Agent harness engineering | 12113 | M00699 | non-negotiable | false | 10 |
| R06975 | Pillar 4 — Routing + cost-aware model selection | 12114 | M00700 | non-negotiable | false | 10 |
| R06976 | Pillar 5 — Sandboxes + secrets isolation | 12115 | M00701 | non-negotiable | false | 10 |
| R06977 | Pillar 6 — Model compression + hardware-aware model lab | 12116 | M00702 | non-negotiable | false | 10 |
| R06978 | Pillars confirm same thesis | 12120 | F03487 | non-negotiable | false | 10 |
| R06979 | "Breakthrough is not one model" | 12121 | F03487 | non-negotiable | false | 10 |
| R06980 | "Breakthrough is the harness" | 12126 | F03488 | non-negotiable | false | 10 |
| R06981 | "Breakthrough is the runtime" | 12126 | F03488 | non-negotiable | false | 10 |
| R06982 | "Breakthrough is the workflow" | 12126 | F03488 | non-negotiable | false | 10 |
| R06983 | "Breakthrough is the router" | 12126 | F03488 | non-negotiable | false | 10 |
| R06984 | "Breakthrough is the memory" | 12126 | F03488 | non-negotiable | false | 10 |
| R06985 | "Breakthrough is the evals" | 12126 | F03488 | non-negotiable | false | 10 |
| R06986 | "Breakthrough is the hardware-aware execution substrate" | 12126 | F03488 | non-negotiable | false | 10 |
| R06987 | Most important confirmation came from Agent Harness Engineering survey | 12128 | F03489 | non-negotiable | false | 10 |
| R06988 | Survey thesis — real-world reliability depends heavily on execution harness around the model | 12131 | F03490 | non-negotiable | false | 10 |
| R06989 | Survey organizes space into execution | 12131 | F03491 | non-negotiable | false | 10 |
| R06990 | Survey organizes space into tools | 12131 | F03491 | non-negotiable | false | 10 |
| R06991 | Survey organizes space into context | 12131 | F03491 | non-negotiable | false | 10 |
| R06992 | Survey organizes space into lifecycle | 12131 | F03491 | non-negotiable | false | 10 |
| R06993 | Survey organizes space into observability | 12131 | F03491 | non-negotiable | false | 10 |
| R06994 | Survey organizes space into verification | 12131 | F03491 | non-negotiable | false | 10 |
| R06995 | Survey organizes space into governance | 12131 | F03491 | non-negotiable | false | 10 |
| R06996 | "Almost exactly our station architecture" | 12133 | F03492 | non-negotiable | false | 10 |
| R06997 | Methodology — MAP step | 12139 | M00703 | non-negotiable | false | 10 |
| R06998 | Methodology — SPEC step | 12139 | M00703 | non-negotiable | false | 10 |
| R06999 | Methodology — TEST step | 12139 | M00703 | non-negotiable | false | 10 |
| R07000 | Methodology — ACT step | 12139 | M00703 | non-negotiable | false | 10 |
| R07001 | Methodology — EVAL step | 12139 | M00703 | non-negotiable | false | 10 |
| R07002 | Methodology — COMMIT step | 12139 | M00703 | non-negotiable | false | 10 |
| R07003 | Methodology — LEARN step | 12139 | M00703 | non-negotiable | false | 10 |
| R07004 | MAP definition — "understand environment before action" | 12141 | F03493 | non-negotiable | false | 10 |
| R07005 | SPEC definition — "define intended behavior and constraints" | 12146 | F03494 | non-negotiable | false | 10 |
| R07006 | TEST definition — "executable truth / TDD / regression checks" | 12150 | F03495 | non-negotiable | false | 10 |
| R07007 | ACT definition — "model/tool/workflow execution" | 12153 | F03496 | non-negotiable | false | 10 |
| R07008 | EVAL definition — "trajectory, cost, quality, risk, latency" | 12157 | F03497 | non-negotiable | false | 10 |
| R07009 | COMMIT definition — "gated side effects, snapshots, review" | 12160 | F03498 | non-negotiable | false | 10 |
| R07010 | LEARN definition — "update memory, model registry, profiles, skills" | 12164 | F03499 | non-negotiable | false | 10 |
| R07011 | Methodology — "cleanest extraction from MAP, Symphony, agent eval work, and your own Goldilocks profile idea" | 12168 | F03500 | non-negotiable | false | 10 |
| R07012 | MAP — "Do not let agents learn the environment only by failing through it" | 12175 | F03501 | non-negotiable | false | 10 |
| R07013 | MAP — "Build a map first" | 12179 | F03501 | non-negotiable | false | 10 |
| R07014 | Map type — repo map | 12183 | F03502 | non-negotiable | false | 10 |
| R07015 | Map type — test map | 12184 | F03503 | non-negotiable | false | 10 |
| R07016 | Map type — tool map | 12185 | F03504 | non-negotiable | false | 10 |
| R07017 | Map type — risk map | 12186 | F03505 | non-negotiable | false | 10 |
| R07018 | Map type — memory map | 12187 | F03506 | non-negotiable | false | 10 |
| R07019 | Map type — GUI/world map | 12188 | F03507 | non-negotiable | false | 10 |
| R07020 | Map type — dependency map | 12189 | F03508 | non-negotiable | false | 10 |
| R07021 | Symphony — "Workflow belongs in version-controlled repo artifacts" | 12194 | F03509 | non-negotiable | false | 10 |
| R07022 | Inheritance contract — SPEC.md | 12196 | F03510 | non-negotiable | false | 10 |
| R07023 | Inheritance contract — WORKFLOW.md | 12197 | F03511 | non-negotiable | false | 10 |
| R07024 | Inheritance contract — PROFILES.yaml | 12198 | F03512 | non-negotiable | false | 10 |
| R07025 | Inheritance contract — EVALS.yaml | 12199 | F03513 | non-negotiable | false | 10 |
| R07026 | Inheritance contract — POLICY.yaml | 12200 | F03514 | non-negotiable | false | 10 |
| R07027 | Inheritance contract — MODEL_REGISTRY.yaml | 12201 | F03515 | non-negotiable | false | 10 |
| R07028 | LiteLLM — "agent sessions need real isolation, persistent sandboxes, and secret protection" | 12206 | F03516 | non-negotiable | false | 10 |
| R07029 | Vault-proxy pattern — agent sees stub credentials | 12211 | F03517 | non-negotiable | false | 10 |
| R07030 | Vault-proxy pattern — sidecar swaps real credentials at wire boundary | 12211 | F03518 | non-negotiable | false | 10 |
| R07031 | Station — Claude Code gets stub keys | 12213 | F03519 | non-negotiable | false | 10 |
| R07032 | Station — OpenCode gets stub keys | 12213 | F03520 | non-negotiable | false | 10 |
| R07033 | Station — Cline gets stub keys | 12213 | F03521 | non-negotiable | false | 10 |
| R07034 | Station — Jean Gateway owns real keys | 12215 | F03522 | non-negotiable | false | 10 |
| R07035 | Station — Jean Gateway owns cost | 12215 | F03523 | non-negotiable | false | 10 |
| R07036 | Station — Jean Gateway owns policy | 12215 | F03524 | non-negotiable | false | 10 |
| R07037 | Station — Jean Gateway owns routing | 12215 | F03525 | non-negotiable | false | 10 |
| R07038 | NadirClaw — "many prompts do not deserve the expensive model" | 12218 | F03526 | non-negotiable | false | 10 |
| R07039 | Routing axis — simple/complex | 12220 | F03527 | non-negotiable | false | 10 |
| R07040 | Routing axis — private/public | 12221 | F03528 | non-negotiable | false | 10 |
| R07041 | Routing axis — safe/risky | 12222 | F03529 | non-negotiable | false | 10 |
| R07042 | Routing axis — coding/research/gui | 12223 | F03530 | non-negotiable | false | 10 |
| R07043 | Routing axis — local/cloud | 12224 | F03531 | non-negotiable | false | 10 |
| R07044 | Routing axis — fast/careful | 12225 | F03532 | non-negotiable | false | 10 |
| R07045 | Routing axis — cheap/oracle | 12226 | F03533 | non-negotiable | false | 10 |
| R07046 | Fast BLT — "frontier inference is becoming memory-bandwidth-aware and speculation-aware" | 12228 | F03534 | non-negotiable | false | 10 |
| R07047 | Fast BLT architectural rule — reduce forward passes | 12230 | M00708 | non-negotiable | false | 10 |
| R07048 | Fast BLT architectural rule — speculate cheaply | 12230 | M00708 | non-negotiable | false | 10 |
| R07049 | Fast BLT architectural rule — verify carefully | 12230 | M00708 | non-negotiable | false | 10 |
| R07050 | Fast BLT architectural rule — avoid memory bandwidth waste | 12230 | M00708 | non-negotiable | false | 10 |
| R07051 | LLM Compressor — "build a model qualification lab" | 12232 | F03535 | non-negotiable | false | 10 |
| R07052 | "Not 'download model, hope'" | 12233 | F03536 | non-negotiable | false | 10 |
| R07053 | Model-lab slot — BF16 baseline | 12234 | M00708 | non-negotiable | false | 10 |
| R07054 | Model-lab slot — FP8 | 12235 | M00708 | non-negotiable | false | 10 |
| R07055 | Model-lab slot — GPTQ | 12236 | M00708 | non-negotiable | false | 10 |
| R07056 | Model-lab slot — SmoothQuant | 12237 | M00708 | non-negotiable | false | 10 |
| R07057 | Model-lab slot — AWQ | 12238 | M00708 | non-negotiable | false | 10 |
| R07058 | Model-lab slot — NVFP4/MXFP4 when stable | 12239 | M00708 | non-negotiable | false | 10 |
| R07059 | Model-lab slot — KV quantization | 12240 | M00708 | non-negotiable | false | 10 |
| R07060 | Model-lab slot — profile-specific evals | 12241 | M00708 | non-negotiable | false | 10 |
| R07061 | TODO 1 — Read MAP PDF deeper for concrete map schemas | 12246 | F03537 | non-negotiable | false | 10 |
| R07062 | TODO 2 — Mine Symphony SPEC for WORKFLOW.md-compatible schema | 12248 | F03538 | non-negotiable | false | 10 |
| R07063 | TODO 3 — Study LiteLLM Agent Platform sandbox/vault design in detail | 12250 | F03539 | non-negotiable | false | 10 |
| R07064 | TODO 4 — Build Anthropic-first gateway compatibility tests | 12252 | F03540 | non-negotiable | false | 10 |
| R07065 | TODO 5 — Prototype AVX-512 metadata core | 12254 | F03541 | non-negotiable | false | 10 |
| R07066 | TODO 6 — Define first PROFILES.yaml | 12256 | F03542 | non-negotiable | false | 10 |
| R07067 | TODO 6 — Define first EVALS.yaml | 12256 | F03542 | non-negotiable | false | 10 |
| R07068 | TODO 6 — Define first MODEL_REGISTRY.yaml | 12256 | F03542 | non-negotiable | false | 10 |
| R07069 | TODO 7 — Hardware validation: PCIe | 12258 | F03543 | non-negotiable | false | 10 |
| R07070 | TODO 7 — Hardware validation: MIG | 12258 | F03543 | non-negotiable | false | 10 |
| R07071 | TODO 7 — Hardware validation: VFIO | 12258 | F03543 | non-negotiable | false | 10 |
| R07072 | TODO 7 — Hardware validation: ZFS | 12258 | F03543 | non-negotiable | false | 10 |
| R07073 | TODO 7 — Hardware validation: NICs | 12258 | F03543 | non-negotiable | false | 10 |
| R07074 | TODO 7 — Hardware validation: Blackwell FP4 | 12258 | F03543 | non-negotiable | false | 10 |
| R07075 | North-Star — Anthropic-first API gateway | 12264 | F03544 | non-negotiable | false | 10 |
| R07076 | North-Star — deterministic AVX-512 control plane | 12265 | F03545 | non-negotiable | false | 10 |
| R07077 | North-Star — Blackwell oracle | 12266 | F03546 | non-negotiable | false | 10 |
| R07078 | North-Star — 4090 scout/sandbox | 12267 | F03547 | non-negotiable | false | 10 |
| R07079 | North-Star — model portfolio lab | 12268 | F03548 | non-negotiable | false | 10 |
| R07080 | North-Star — MAP/SPEC/TDD workflow compiler | 12269 | F03549 | non-negotiable | false | 10 |
| R07081 | North-Star — sandboxed execution | 12270 | F03550 | non-negotiable | false | 10 |
| R07082 | North-Star — trace-based evals | 12271 | F03551 | non-negotiable | false | 10 |
| R07083 | North-Star — memory/replay/learning | 12272 | F03552 | non-negotiable | false | 10 |
| R07084 | Phrase to keep — "Evidence-driven autonomy" | 12277 | F03553 | non-negotiable | false | 10 |
| R07085 | "Not pure agent freedom" | 12281 | F03554 | non-negotiable | false | 10 |
| R07086 | "Not rigid workflow prison" | 12282 | F03554 | non-negotiable | false | 10 |
| R07087 | "A system that maps, specifies, tests, acts, evaluates, commits, and learns" | 12284 | F03554 | non-negotiable | false | 10 |
| R07088 | "Using the right amount of intelligence for the task" | 12286 | F03554 | non-negotiable | false | 10 |
| R07089 | Choice architecture — "runtime should not be opinionated in the usual product sense" | 12372 | F03555 | non-negotiable | false | 10 |
| R07090 | Choice architecture — "should be policy-composable" | 12376 | F03555 | non-negotiable | false | 10 |
| R07091 | NOT "This system is local-only" | 12379 | E0403 | non-negotiable | false | 10 |
| R07092 | NOT "This system is cloud-hybrid" | 12380 | E0403 | non-negotiable | false | 10 |
| R07093 | NOT "This system is autonomous" | 12381 | E0403 | non-negotiable | false | 10 |
| R07094 | NOT "This system is safe" | 12382 | E0403 | non-negotiable | false | 10 |
| R07095 | NOT "This system is powerful" | 12383 | E0403 | non-negotiable | false | 10 |
| R07096 | Boundary choice — local or cloud | 12384 | F03556 | non-negotiable | false | 10 |
| R07097 | Boundary choice — fast or careful | 12385 | F03557 | non-negotiable | false | 10 |
| R07098 | Boundary choice — private or shared | 12386 | F03558 | non-negotiable | false | 10 |
| R07099 | Boundary choice — automatic or gated | 12387 | F03559 | non-negotiable | false | 10 |
| R07100 | Boundary choice — cheap or best | 12388 | F03560 | non-negotiable | false | 10 |
| R07101 | Boundary choice — sandbox or host | 12389 | F03561 | non-negotiable | false | 10 |
| R07102 | Boundary choice — scout or oracle | 12390 | F03562 | non-negotiable | false | 10 |
| R07103 | Boundary choice — spec-first or exploratory | 12391 | F03563 | non-negotiable | false | 10 |
| R07104 | Boundary choice — TDD strict or prototype | 12392 | F03564 | non-negotiable | false | 10 |
| R07105 | "That is sovereignty" | 12395 | F03565 | non-negotiable | false | 10 |
| R07106 | Choice envelope — every action exposes choice envelope | 12398 | M00709 | non-negotiable | false | 10 |
| R07107 | Choice envelope schema — domain | 12402 | M00709 | non-negotiable | false | 10 |
| R07108 | Choice envelope schema — options[] | 12403 | M00709 | non-negotiable | false | 10 |
| R07109 | Choice envelope schema — default | 12408 | M00709 | non-negotiable | false | 10 |
| R07110 | Choice envelope schema — requires{} | 12409 | M00709 | non-negotiable | false | 10 |
| R07111 | Choice example model_route options — local_scout / local_oracle / cloud_anthropic / cloud_openai | 12404–12407 | M00709 | non-negotiable | false | 10 |
| R07112 | Choice example model_route default — local_oracle | 12408 | M00709 | non-negotiable | false | 10 |
| R07113 | Choice example model_route requires cloud_anthropic — user_approval + cost_budget + privacy_clearance | 12410–12413 | M00709 | non-negotiable | false | 10 |
| R07114 | Choice example execution options — dry_run / sandbox / vm / host | 12421–12424 | M00709 | non-negotiable | false | 10 |
| R07115 | Choice example execution default — sandbox | 12425 | M00709 | non-negotiable | false | 10 |
| R07116 | Choice example development_mode options — exploratory / spec_driven / tdd / spec_plus_tdd / production_verified | 12432–12436 | M00709 | non-negotiable | false | 10 |
| R07117 | "System becomes a choice compiler" | 12442 | F03566 | non-negotiable | false | 10 |
| R07118 | Profile bundle private — local models | 12453 | M00710 | non-negotiable | false | 10 |
| R07119 | Profile bundle private — no network | 12454 | M00710 | non-negotiable | false | 10 |
| R07120 | Profile bundle private — no cloud | 12455 | M00710 | non-negotiable | false | 10 |
| R07121 | Profile bundle private — sandbox tools | 12456 | M00710 | non-negotiable | false | 10 |
| R07122 | Profile bundle careful — map first | 12459 | M00710 | non-negotiable | false | 10 |
| R07123 | Profile bundle careful — spec required | 12460 | M00710 | non-negotiable | false | 10 |
| R07124 | Profile bundle careful — tests required | 12461 | M00710 | non-negotiable | false | 10 |
| R07125 | Profile bundle careful — oracle review | 12462 | M00710 | non-negotiable | false | 10 |
| R07126 | Profile bundle fast — scout first | 12465 | M00710 | non-negotiable | false | 10 |
| R07127 | Profile bundle fast — shallow map | 12466 | M00710 | non-negotiable | false | 10 |
| R07128 | Profile bundle fast — minimal verification | 12467 | M00710 | non-negotiable | false | 10 |
| R07129 | Profile bundle sovereign — user-visible gates | 12470 | M00710 | non-negotiable | false | 10 |
| R07130 | Profile bundle sovereign — local memory ownership | 12471 | M00710 | non-negotiable | false | 10 |
| R07131 | Profile bundle sovereign — explicit external calls | 12472 | M00710 | non-negotiable | false | 10 |
| R07132 | Profile bundle sovereign — replay always on | 12473 | M00710 | non-negotiable | false | 10 |
| R07133 | "But the user can override any axis" | 12487 | F03567 | non-negotiable | false | 10 |
| R07134 | Distinction — profile = starting posture | 12489 | M00711 | non-negotiable | false | 10 |
| R07135 | Distinction — policy = enforced boundary | 12490 | M00711 | non-negotiable | false | 10 |
| R07136 | Distinction — choice = user agency | 12491 | M00711 | non-negotiable | false | 10 |
| R07137 | Inheritance artifact — VISION.md (philosophy and system thesis) | 12500 | M00712 | non-negotiable | false | 10 |
| R07138 | Inheritance artifact — ARCHITECTURE.md (planes services hardware mapping) | 12503 | M00712 | non-negotiable | false | 10 |
| R07139 | Inheritance artifact — METHODOLOGY.md (MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN) | 12506 | M00712 | non-negotiable | false | 10 |
| R07140 | Composite — M042 (10 epics / 17 modules / 85 features / 170 reqs) catalogs choice architecture / policy-composable sovereignty: 6 pillars + 7-step methodology + 7 map types + 6 inheritance contracts + vault-proxy pattern + 7-axis routing + 8-slot model-lab + 9-component North Star + "Evidence-driven autonomy" + 9-boundary-axis choice + 3-domain choice envelope + 4 profile bundles + profile/policy/choice 3-way distinction + 8 inheritance artifacts (VISION/ARCHITECTURE/METHODOLOGY/PROFILES/POLICY/MODEL_REGISTRY/HARDWARE_PROFILES/EVALS) + 8 transparency questions + 8-axis negotiation; final phrase "User-sovereign adaptive intelligence runtime" | 12094–12614 | E0398-E0407 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: 6 pillars (R06971–R06986) + 7-layer survey (R06987–R06996) + 7-step methodology + 7 definitions + cleanest-extraction note (R06997–R07011) + MAP doctrine + 7 map types (R07012–R07020) + Symphony doctrine + 6 inheritance contracts (R07021–R07027) + LiteLLM + vault-proxy + Jean-Gateway translation (R07028–R07037) + NadirClaw + 7-axis routing (R07038–R07045) + Fast BLT + 4 architectural rules (R07046–R07050) + LLM-Compressor + 8-slot model-lab (R07051–R07060) + 7-step implementation TODO (R07061–R07074) + 9-component North Star + "Evidence-driven autonomy" 4-clause definition (R07075–R07088) + choice-architecture policy-composable + 5 NOTs + 9 boundary choices + sovereignty phrase (R07089–R07105) + choice-envelope schema + 3-domain examples (R07106–R07117) + 4 profile bundles (R07118–R07132) + override-any-axis rule + 3-way distinction (R07133–R07136) + 3 inheritance artifacts (R07137–R07139) + composite (R07140)
- Source range 12094–12614 yields 520 lines; 170 R-rows represent ~33% line-coverage at the verbatim-citation level (web-search trace lines + redundant restatements of methodology + closing operator-question echo excluded; remaining 5 inheritance artifacts PROFILES/POLICY/MODEL_REGISTRY/HARDWARE_PROFILES/EVALS already cited in R07024–R07027 + R07067–R07068 + M00712)
- Project boundary — M042 is sovereign-os runtime/choice-architecture/sovereignty scope; selfdef MS017 agent-guard enforces the POLICY.yaml subset for IPS-side; MS013 27-SDD charter is the SPEC.md-equivalent doctrine for IPS-side

## Cross-references

- Adjacent dump-range milestones: M041 7-contract architecture (11790–12094) / M043 Bridge layer hardware-aware intelligence scheduling (next; dump 12614–12944)
- Inheritance — M042 8 inheritance artifacts (VISION/ARCHITECTURE/METHODOLOGY/PROFILES/POLICY/MODEL_REGISTRY/HARDWARE_PROFILES/EVALS) seed the entire downstream catalog; ALL prior planes (M025-M041) consume these contracts
- Choice-architecture — M042 choice envelopes drive M025 Cognitive Compiler (compiles choice-envelope into DAG) + M026 SLM swarm + M027 Value Plane (cost/risk/quality choice axes are reward weights) + M029 Computer-Use Plane (sandbox-vs-vm-vs-host execution choice) + M030 World Model (rollback as choice gate) + M031 Symbolic Planning Plane (POLICY.yaml + SPEC.md consumers) + M032 Cloud Expert Plane (cloud_anthropic + cloud_openai options) + M033/M034 Gateways (Tool-interface choices)
- Methodology MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN — supersedes M036 MAP-then-act 7-truth-anchor + 9-layer-architecture (M042 extends with COMMIT + LEARN as explicit steps)
- 4 profile bundles (private / careful / fast / sovereign) — extend M040 4-example-YAML-profiles (max_oracle / secure_agent_lab / fast_code / research_deep) into the user-agency dimension
- Selfdef integration — M042 8 inheritance artifacts pair with selfdef MS013 27-SDD ledger (SPEC.md-equiv) + MS017 agent-guard (POLICY.yaml subset) + MS020 L1-L5 harness (EVALS.yaml + TEST step) + MS022 per-token quota (POLICY.yaml capability gate)
- Cross-repo binding — VISION/ARCHITECTURE/METHODOLOGY artifacts may surface via MS007 doc-manifest typed-mirror crate (SATURATED 8/8)
- Operator references: openreview.net Agent Harness Engineering survey / arxiv.org/abs/2605.13037 MAP / github.com/openai/symphony/blob/main/SPEC.md / docs.litellm-agent-platform.ai vault proxy / github.com/NadirRouter/NadirClaw / arxiv.org/abs/2605.08044 Fast BLT / docs.vllm.ai/projects/llm-compressor compression_schemes
