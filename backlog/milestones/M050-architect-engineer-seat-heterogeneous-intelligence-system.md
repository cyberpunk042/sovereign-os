# M050 — Architect and Engineer seat — heterogeneous intelligence system

> Parent: `backlog/milestones/INDEX.md` row M050 (dump 15120–15362).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 15120–15362. Operator directive 15120: "Now lets return to the archtecture. the AVX, the whole hardware and stack. return to the Architect and Engineer seet and software and devops specialist and fullstacka and AI expert" + closing 15362: "Continue".
> All entries below extract verbatim. No invention.

## Epics (E0478–E0487)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0478 | Operator directive + Architect seat — "Now lets return to the archtecture. the AVX, the whole hardware and stack. return to the Architect and Engineer seet and software and devops specialist and fullstacka and AI expert"; AI response "Yes. Architect seat back on" | 15120 + 15124 |
| E0479 | Workstation as heterogeneous intelligence system — "The workstation should be designed as a **heterogeneous intelligence system**, not a 'PC that runs models'"; 7-component hardware-mapping: Ryzen 9900X AVX-512 = deterministic control plane / RTX PRO 6000 96GB = oracle / resident high-value cognition / RTX 3090 24GB = scout / sandbox / SLM / perception / draft engine / 256GB RAM = active memory, context arena, ZFS ARC / NVMe + ZFS = replay, snapshots, model cache, rollback / Debian/Ubuntu base = sovereign OS substrate / Anthropic gateway = external/client compatibility layer | 15126–15144 |
| E0480 | Core Architecture 5-layer — Clients (Claude Code, OpenCode, Cline, local UI, CLI, APIs) / Gateway (Anthropic-first facade + OpenAI-compatible shim + cost ledger + provider routing + policy/redaction) / Cognitive Runtime (workflow compiler + branch scheduler + profile resolver + memory router + eval/value engine + tool gate) / Hardware Execution (Blackwell oracle + 3090 scout/sandbox + AVX-512 control engine + container/VM/REPL tools) / Persistence (ZFS snapshots + replay logs + memory graph + model registry + eval history) | 15148–15182 |
| E0481 | The AVX-512 Role — "The CPU is not 'backup compute.' It is the **logic accelerator**"; 9 use cases: branch filtering / policy masks / permission checks / memory bitset search / tool routing / schema/token mask fusion / candidate compression / reward-vector scoring / workflow state transitions | 15186–15208 |
| E0482 | Columnar hot data + bulk masks — 9 SoA arrays: branch_id[] / control_word[] / risk[] / budget[] / score[] / route[] / memory_ref[] / kv_ref[] / flags[]; 6 bulk-eval masks: alive_mask / tool_allowed_mask / oracle_needed_mask / sandbox_required_mask / memory_hit_mask / commit_allowed_mask; "This is where deterministic AI infrastructure becomes fast" | 15212–15240 |
| E0483 | GPU Roles — "Do not fuse the GPUs mentally"; Blackwell 7 roles (large oracle model / final synthesis / long-context verification / high-risk code review / deep RLM parent calls / FP8/FP4 model lab) + 3090 7 roles (SLM swarm / draft/speculative decoding / embeddings/reranking / perception/GUI / failure classification / sandboxed experiments / cheap branch expansion); compact artifacts to move: tokens / scores / branch refs / memory ids / tool intents / patch summaries; avoid moving: KV tensors / activations / layer-split traffic / huge intermediate states | 15244–15292 |
| E0484 | DevOps Stack — "Use Linux primitives as first-class architecture"; 7 primitives: systemd (service lifecycle + watchdogs + slices) / cgroup v2 (CPU/memory/IO/PID budgets) / AppArmor+seccomp (sandbox boundaries) / eBPF (truth sensor for file/network/process behavior) / ZFS (snapshots + rollback + replay + clone workspaces) / Podman/Quadlet (systemd-managed containers) / VFIO (hard isolate 3090 when needed); 8 profile bundles realize: fast / careful / private / offline / research / autonomous / production / experimental | 15296–15322 |
| E0485 | AI Runtime Loop — 7-step MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN: MAP (inspect environment, repo, tools, memory, risk) / SPEC (define intended behavior and constraints) / TEST (generate or select executable truth) / ACT (route work to scout/oracle/tools) / EVAL (judge outcome, trajectory, cost, risk) / COMMIT (gated write, snapshot, replay) / LEARN (update memory, routing, profiles, later LoRAs) | 15326–15346 |
| E0486 | Fullstack Surface — 5 entry points: local web dashboard (traces + costs + profiles + model health + approvals) / CLI (run task + inspect trace + resume session + switch profile) / API (Anthropic-compatible primary + OpenAI-compatible secondary) / MCP/tools (controlled capability layer) / Project integration (Claude Code / Cline / OpenCode point at local gateway) | 15350–15364 |
| E0487 | The Design Law + cloud-vs-station closing — 6-line Design Law: "Models propose. / Runtime routes. / CPU enforces. / Tools prove. / ZFS remembers. / User chooses."; "That is the architecture"; "The cloud has scale. This machine has locality, continuity, hardware control, private context, rollback, and user sovereignty. That is how it becomes better for real work" | 15368–15384 |

## Modules (M00833–M00849)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00833 | Architect seat re-entry — DevOps + Fullstack + AI-expert roles re-enabled | 15120 | E0478 |
| M00834 | Hardware mapping — Ryzen 9900X AVX-512 = deterministic control plane | 15130 | E0479 |
| M00835 | Hardware mapping — RTX PRO 6000 96GB = oracle/resident high-value cognition | 15132 | E0479 |
| M00836 | Hardware mapping — RTX 3090 24GB = scout/sandbox/SLM/perception/draft engine | 15134 | E0479 |
| M00837 | Hardware mapping — 256GB RAM = active memory + context arena + ZFS ARC | 15136 | E0479 |
| M00838 | Hardware mapping — NVMe + ZFS = replay + snapshots + model cache + rollback | 15138 | E0479 |
| M00839 | Hardware mapping — Debian/Ubuntu base = sovereign OS substrate | 15140 | E0479 |
| M00840 | Hardware mapping — Anthropic gateway = external/client compatibility layer | 15142 | E0479 |
| M00841 | Core Architecture 5-layer — Clients / Gateway / Cognitive Runtime / Hardware Execution / Persistence | 15150–15180 | E0480 |
| M00842 | AVX-512 9 use cases — branch filtering + policy masks + permission checks + memory bitset search + tool routing + schema/token mask fusion + candidate compression + reward-vector scoring + workflow state transitions | 15192–15208 | E0481 |
| M00843 | 9-SoA columnar hot-data layout — branch_id/control_word/risk/budget/score/route/memory_ref/kv_ref/flags | 15216–15232 | E0482 |
| M00844 | 6-bulk-eval masks — alive_mask / tool_allowed_mask / oracle_needed_mask / sandbox_required_mask / memory_hit_mask / commit_allowed_mask | 15236–15240 | E0482 |
| M00845 | Blackwell 7-role + 3090 7-role taxonomy + compact-move vs avoid-move artifact lists | 15248–15292 | E0483 |
| M00846 | DevOps 7-primitive stack — systemd + cgroup v2 + AppArmor/seccomp + eBPF + ZFS + Podman/Quadlet + VFIO | 15300–15318 | E0484 |
| M00847 | 7-step AI Runtime Loop with definitions — MAP/SPEC/TEST/ACT/EVAL/COMMIT/LEARN | 15330–15344 | E0485 |
| M00848 | Fullstack Surface — 5 entry points (web dashboard / CLI / API / MCP-tools / Project integration) | 15354–15364 | E0486 |
| M00849 | Design Law 6-line + cloud-vs-station 6-property advantage | 15370–15384 | E0487 |

## Features (F04166–F04250)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F04166 | Operator directive — "Now lets return to the archtecture" | 15120 | E0478 |
| F04167 | Operator directive — "the AVX, the whole hardware and stack" | 15120 | E0478 |
| F04168 | Operator directive — "return to the Architect and Engineer seet" | 15120 | E0478 |
| F04169 | Operator directive — "and software and devops specialist and fullstacka and AI expert" | 15120 | E0478 |
| F04170 | AI response — "Yes. Architect seat back on" | 15124 | E0478 |
| F04171 | Doctrine — "heterogeneous intelligence system" | 15126 | E0479 |
| F04172 | Doctrine — "not a PC that runs models" | 15126 | E0479 |
| F04173 | Hardware role — Ryzen 9900X AVX-512 = deterministic control plane | 15130 | M00834 |
| F04174 | Hardware role — RTX PRO 6000 96GB = oracle | 15132 | M00835 |
| F04175 | Hardware role — RTX PRO 6000 96GB = resident high-value cognition | 15132 | M00835 |
| F04176 | Hardware role — RTX 3090 24GB = scout | 15134 | M00836 |
| F04177 | Hardware role — RTX 3090 24GB = sandbox | 15134 | M00836 |
| F04178 | Hardware role — RTX 3090 24GB = SLM | 15134 | M00836 |
| F04179 | Hardware role — RTX 3090 24GB = perception | 15134 | M00836 |
| F04180 | Hardware role — RTX 3090 24GB = draft engine | 15134 | M00836 |
| F04181 | Hardware role — 256GB RAM = active memory | 15136 | M00837 |
| F04182 | Hardware role — 256GB RAM = context arena | 15136 | M00837 |
| F04183 | Hardware role — 256GB RAM = ZFS ARC | 15136 | M00837 |
| F04184 | Hardware role — NVMe + ZFS = replay | 15138 | M00838 |
| F04185 | Hardware role — NVMe + ZFS = snapshots | 15138 | M00838 |
| F04186 | Hardware role — NVMe + ZFS = model cache | 15138 | M00838 |
| F04187 | Hardware role — NVMe + ZFS = rollback | 15138 | M00838 |
| F04188 | Hardware role — Debian/Ubuntu base = sovereign OS substrate | 15140 | M00839 |
| F04189 | Hardware role — Anthropic gateway = external/client compatibility layer | 15142 | M00840 |
| F04190 | Layer — Clients (Claude Code + OpenCode + Cline + local UI + CLI + APIs) | 15150–15154 | M00841 |
| F04191 | Layer — Gateway (Anthropic-first facade + OpenAI-compatible shim + cost ledger + provider routing + policy/redaction) | 15156–15162 | M00841 |
| F04192 | Layer — Cognitive Runtime (workflow compiler + branch scheduler + profile resolver + memory router + eval/value engine + tool gate) | 15164–15172 | M00841 |
| F04193 | Layer — Hardware Execution (Blackwell oracle + 3090 scout/sandbox + AVX-512 control engine + container/VM/REPL tools) | 15174–15180 | M00841 |
| F04194 | Layer — Persistence (ZFS snapshots + replay logs + memory graph + model registry + eval history) | 15182–15186 | M00841 |
| F04195 | AVX-512 doctrine — "The CPU is not 'backup compute'" | 15188 | E0481 |
| F04196 | AVX-512 doctrine — "It is the logic accelerator" | 15190 | E0481 |
| F04197 | AVX-512 use — branch filtering | 15194 | M00842 |
| F04198 | AVX-512 use — policy masks | 15195 | M00842 |
| F04199 | AVX-512 use — permission checks | 15196 | M00842 |
| F04200 | AVX-512 use — memory bitset search | 15197 | M00842 |
| F04201 | AVX-512 use — tool routing | 15198 | M00842 |
| F04202 | AVX-512 use — schema/token mask fusion | 15199 | M00842 |
| F04203 | AVX-512 use — candidate compression | 15200 | M00842 |
| F04204 | AVX-512 use — reward-vector scoring | 15201 | M00842 |
| F04205 | AVX-512 use — workflow state transitions | 15202 | M00842 |
| F04206 | Hot data — columnar | 15212 | M00843 |
| F04207 | SoA — branch_id[] | 15216 | M00843 |
| F04208 | SoA — control_word[] | 15217 | M00843 |
| F04209 | SoA — risk[] | 15218 | M00843 |
| F04210 | SoA — budget[] | 15219 | M00843 |
| F04211 | SoA — score[] | 15220 | M00843 |
| F04212 | SoA — route[] | 15221 | M00843 |
| F04213 | SoA — memory_ref[] | 15222 | M00843 |
| F04214 | SoA — kv_ref[] | 15223 | M00843 |
| F04215 | SoA — flags[] | 15224 | M00843 |
| F04216 | Bulk-eval mask — alive_mask | 15232 | M00844 |
| F04217 | Bulk-eval mask — tool_allowed_mask | 15233 | M00844 |
| F04218 | Bulk-eval mask — oracle_needed_mask | 15234 | M00844 |
| F04219 | Bulk-eval mask — sandbox_required_mask | 15235 | M00844 |
| F04220 | Bulk-eval mask — memory_hit_mask | 15236 | M00844 |
| F04221 | Bulk-eval mask — commit_allowed_mask | 15237 | M00844 |
| F04222 | "This is where deterministic AI infrastructure becomes fast" | 15240 | E0482 |
| F04223 | GPU doctrine — "Do not fuse the GPUs mentally" | 15246 | E0483 |
| F04224 | Blackwell role — large oracle model + final synthesis + long-context verification + high-risk code review + deep RLM parent calls + FP8/FP4 model lab | 15250–15262 | M00845 |
| F04225 | 3090 role — SLM swarm + draft/speculative decoding + embeddings/reranking + perception/GUI + failure classification + sandboxed experiments + cheap branch expansion | 15266–15280 | M00845 |
| F04226 | Compact move — tokens + scores + branch refs + memory ids + tool intents + patch summaries | 15284–15290 | M00845 |
| F04227 | Avoid move — KV tensors + activations + layer-split traffic + huge intermediate states | 15294–15300 | M00845 |
| F04228 | DevOps doctrine — "Use Linux primitives as first-class architecture" | 15300 | E0484 |
| F04229 | Primitive — systemd (service lifecycle + watchdogs + slices) | 15304 | M00846 |
| F04230 | Primitive — cgroup v2 (CPU/memory/IO/PID budgets) | 15306 | M00846 |
| F04231 | Primitive — AppArmor/seccomp (sandbox boundaries) | 15308 | M00846 |
| F04232 | Primitive — eBPF (truth sensor for file/network/process behavior) | 15310 | M00846 |
| F04233 | Primitive — ZFS (snapshots + rollback + replay + clone workspaces) | 15312 | M00846 |
| F04234 | Primitive — Podman/Quadlet (systemd-managed containers) | 15314 | M00846 |
| F04235 | Primitive — VFIO (hard isolate 3090 when needed) | 15316 | M00846 |
| F04236 | Profile bundle — fast | 15320 | M00846 |
| F04237 | Profile bundle — careful | 15321 | M00846 |
| F04238 | Profile bundle — private | 15322 | M00846 |
| F04239 | Profile bundle — offline | 15323 | M00846 |
| F04240 | Profile bundle — research | 15324 | M00846 |
| F04241 | Profile bundle — autonomous | 15325 | M00846 |
| F04242 | Profile bundle — production | 15326 | M00846 |
| F04243 | Profile bundle — experimental | 15327 | M00846 |
| F04244 | Runtime loop step — MAP (inspect environment, repo, tools, memory, risk) + SPEC (define intended behavior and constraints) + TEST (generate or select executable truth) + ACT (route work to scout/oracle/tools) + EVAL (judge outcome, trajectory, cost, risk) + COMMIT (gated write, snapshot, replay) + LEARN (update memory, routing, profiles, later LoRAs) | 15330–15346 | M00847 |
| F04245 | Surface — local web dashboard (traces + costs + profiles + model health + approvals) | 15354–15356 | M00848 |
| F04246 | Surface — CLI (run task + inspect trace + resume session + switch profile) | 15356–15358 | M00848 |
| F04247 | Surface — API (Anthropic-compatible primary + OpenAI-compatible secondary) | 15358–15360 | M00848 |
| F04248 | Surface — MCP/tools (controlled capability layer) | 15360–15362 | M00848 |
| F04249 | Surface — Project integration (Claude Code / Cline / OpenCode point at local gateway) | 15362–15364 | M00848 |
| F04250 | Design Law 6-line + cloud-vs-station 6-property advantage closing | 15370–15384 | M00849 |

## Requirements (R08331–R08500)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R08331 | Operator directive — "Now lets return to the archtecture" | 15120 | F04166 | non-negotiable | false | 10 |
| R08332 | Operator directive — "the AVX, the whole hardware and stack" | 15120 | F04167 | non-negotiable | false | 10 |
| R08333 | Operator directive — "return to the Architect and Engineer seet" | 15120 | F04168 | non-negotiable | false | 10 |
| R08334 | Operator directive — "and software and devops specialist and fullstacka and AI expert" | 15120 | F04169 | non-negotiable | false | 10 |
| R08335 | AI response — "Yes. Architect seat back on" | 15124 | F04170 | non-negotiable | false | 10 |
| R08336 | Doctrine — workstation designed as "heterogeneous intelligence system" | 15126 | F04171 | non-negotiable | false | 10 |
| R08337 | Doctrine — "not a 'PC that runs models'" | 15126 | F04172 | non-negotiable | false | 10 |
| R08338 | Hardware — Ryzen 9900X AVX-512 = deterministic control plane | 15130 | F04173 | non-negotiable | false | 10 |
| R08339 | Hardware — RTX PRO 6000 96GB = oracle | 15132 | F04174 | non-negotiable | false | 10 |
| R08340 | Hardware — RTX PRO 6000 96GB = resident high-value cognition | 15132 | F04175 | non-negotiable | false | 10 |
| R08341 | Hardware — RTX 3090 24GB = scout | 15134 | F04176 | non-negotiable | false | 10 |
| R08342 | Hardware — RTX 3090 24GB = sandbox | 15134 | F04177 | non-negotiable | false | 10 |
| R08343 | Hardware — RTX 3090 24GB = SLM | 15134 | F04178 | non-negotiable | false | 10 |
| R08344 | Hardware — RTX 3090 24GB = perception | 15134 | F04179 | non-negotiable | false | 10 |
| R08345 | Hardware — RTX 3090 24GB = draft engine | 15134 | F04180 | non-negotiable | false | 10 |
| R08346 | Hardware — 256GB RAM = active memory | 15136 | F04181 | non-negotiable | false | 10 |
| R08347 | Hardware — 256GB RAM = context arena | 15136 | F04182 | non-negotiable | false | 10 |
| R08348 | Hardware — 256GB RAM = ZFS ARC | 15136 | F04183 | non-negotiable | false | 10 |
| R08349 | Hardware — NVMe + ZFS = replay | 15138 | F04184 | non-negotiable | false | 10 |
| R08350 | Hardware — NVMe + ZFS = snapshots | 15138 | F04185 | non-negotiable | false | 10 |
| R08351 | Hardware — NVMe + ZFS = model cache | 15138 | F04186 | non-negotiable | false | 10 |
| R08352 | Hardware — NVMe + ZFS = rollback | 15138 | F04187 | non-negotiable | false | 10 |
| R08353 | Hardware — Debian/Ubuntu base = sovereign OS substrate | 15140 | F04188 | non-negotiable | false | 10 |
| R08354 | Hardware — Anthropic gateway = external/client compatibility layer | 15142 | F04189 | non-negotiable | false | 10 |
| R08355 | Layer 1 Clients — Claude Code | 15152 | F04190 | non-negotiable | false | 10 |
| R08356 | Layer 1 Clients — OpenCode | 15152 | F04190 | non-negotiable | false | 10 |
| R08357 | Layer 1 Clients — Cline | 15152 | F04190 | non-negotiable | false | 10 |
| R08358 | Layer 1 Clients — local UI | 15152 | F04190 | non-negotiable | false | 10 |
| R08359 | Layer 1 Clients — CLI | 15152 | F04190 | non-negotiable | false | 10 |
| R08360 | Layer 1 Clients — APIs | 15152 | F04190 | non-negotiable | false | 10 |
| R08361 | Layer 2 Gateway — Anthropic-first facade | 15158 | F04191 | non-negotiable | false | 10 |
| R08362 | Layer 2 Gateway — OpenAI-compatible shim | 15158 | F04191 | non-negotiable | false | 10 |
| R08363 | Layer 2 Gateway — cost ledger | 15160 | F04191 | non-negotiable | false | 10 |
| R08364 | Layer 2 Gateway — provider routing | 15160 | F04191 | non-negotiable | false | 10 |
| R08365 | Layer 2 Gateway — policy/redaction | 15162 | F04191 | non-negotiable | false | 10 |
| R08366 | Layer 3 Cognitive Runtime — workflow compiler | 15166 | F04192 | non-negotiable | false | 10 |
| R08367 | Layer 3 Cognitive Runtime — branch scheduler | 15167 | F04192 | non-negotiable | false | 10 |
| R08368 | Layer 3 Cognitive Runtime — profile resolver | 15168 | F04192 | non-negotiable | false | 10 |
| R08369 | Layer 3 Cognitive Runtime — memory router | 15169 | F04192 | non-negotiable | false | 10 |
| R08370 | Layer 3 Cognitive Runtime — eval/value engine | 15170 | F04192 | non-negotiable | false | 10 |
| R08371 | Layer 3 Cognitive Runtime — tool gate | 15171 | F04192 | non-negotiable | false | 10 |
| R08372 | Layer 4 Hardware Execution — Blackwell oracle | 15176 | F04193 | non-negotiable | false | 10 |
| R08373 | Layer 4 Hardware Execution — 3090 scout/sandbox | 15177 | F04193 | non-negotiable | false | 10 |
| R08374 | Layer 4 Hardware Execution — AVX-512 control engine | 15178 | F04193 | non-negotiable | false | 10 |
| R08375 | Layer 4 Hardware Execution — container/VM/REPL tools | 15179 | F04193 | non-negotiable | false | 10 |
| R08376 | Layer 5 Persistence — ZFS snapshots | 15184 | F04194 | non-negotiable | false | 10 |
| R08377 | Layer 5 Persistence — replay logs | 15184 | F04194 | non-negotiable | false | 10 |
| R08378 | Layer 5 Persistence — memory graph | 15185 | F04194 | non-negotiable | false | 10 |
| R08379 | Layer 5 Persistence — model registry | 15185 | F04194 | non-negotiable | false | 10 |
| R08380 | Layer 5 Persistence — eval history | 15186 | F04194 | non-negotiable | false | 10 |
| R08381 | AVX-512 doctrine — "The CPU is not 'backup compute'" | 15188 | F04195 | non-negotiable | false | 10 |
| R08382 | AVX-512 doctrine — "It is the logic accelerator" | 15190 | F04196 | non-negotiable | false | 10 |
| R08383 | AVX-512 use — branch filtering | 15194 | F04197 | non-negotiable | false | 10 |
| R08384 | AVX-512 use — policy masks | 15195 | F04198 | non-negotiable | false | 10 |
| R08385 | AVX-512 use — permission checks | 15196 | F04199 | non-negotiable | false | 10 |
| R08386 | AVX-512 use — memory bitset search | 15197 | F04200 | non-negotiable | false | 10 |
| R08387 | AVX-512 use — tool routing | 15198 | F04201 | non-negotiable | false | 10 |
| R08388 | AVX-512 use — schema/token mask fusion | 15199 | F04202 | non-negotiable | false | 10 |
| R08389 | AVX-512 use — candidate compression | 15200 | F04203 | non-negotiable | false | 10 |
| R08390 | AVX-512 use — reward-vector scoring | 15201 | F04204 | non-negotiable | false | 10 |
| R08391 | AVX-512 use — workflow state transitions | 15202 | F04205 | non-negotiable | false | 10 |
| R08392 | Hot data — columnar layout | 15212 | F04206 | non-negotiable | false | 10 |
| R08393 | SoA array — branch_id[] | 15216 | F04207 | non-negotiable | false | 10 |
| R08394 | SoA array — control_word[] | 15217 | F04208 | non-negotiable | false | 10 |
| R08395 | SoA array — risk[] | 15218 | F04209 | non-negotiable | false | 10 |
| R08396 | SoA array — budget[] | 15219 | F04210 | non-negotiable | false | 10 |
| R08397 | SoA array — score[] | 15220 | F04211 | non-negotiable | false | 10 |
| R08398 | SoA array — route[] | 15221 | F04212 | non-negotiable | false | 10 |
| R08399 | SoA array — memory_ref[] | 15222 | F04213 | non-negotiable | false | 10 |
| R08400 | SoA array — kv_ref[] | 15223 | F04214 | non-negotiable | false | 10 |
| R08401 | SoA array — flags[] | 15224 | F04215 | non-negotiable | false | 10 |
| R08402 | Bulk mask — alive_mask | 15232 | F04216 | non-negotiable | false | 10 |
| R08403 | Bulk mask — tool_allowed_mask | 15233 | F04217 | non-negotiable | false | 10 |
| R08404 | Bulk mask — oracle_needed_mask | 15234 | F04218 | non-negotiable | false | 10 |
| R08405 | Bulk mask — sandbox_required_mask | 15235 | F04219 | non-negotiable | false | 10 |
| R08406 | Bulk mask — memory_hit_mask | 15236 | F04220 | non-negotiable | false | 10 |
| R08407 | Bulk mask — commit_allowed_mask | 15237 | F04221 | non-negotiable | false | 10 |
| R08408 | "This is where deterministic AI infrastructure becomes fast" | 15240 | F04222 | non-negotiable | false | 10 |
| R08409 | GPU doctrine — "Do not fuse the GPUs mentally" | 15246 | F04223 | non-negotiable | false | 10 |
| R08410 | Blackwell role — large oracle model | 15250 | F04224 | non-negotiable | false | 10 |
| R08411 | Blackwell role — final synthesis | 15252 | F04224 | non-negotiable | false | 10 |
| R08412 | Blackwell role — long-context verification | 15254 | F04224 | non-negotiable | false | 10 |
| R08413 | Blackwell role — high-risk code review | 15256 | F04224 | non-negotiable | false | 10 |
| R08414 | Blackwell role — deep RLM parent calls | 15258 | F04224 | non-negotiable | false | 10 |
| R08415 | Blackwell role — FP8/FP4 model lab | 15260 | F04224 | non-negotiable | false | 10 |
| R08416 | 3090 role — SLM swarm | 15266 | F04225 | non-negotiable | false | 10 |
| R08417 | 3090 role — draft/speculative decoding | 15268 | F04225 | non-negotiable | false | 10 |
| R08418 | 3090 role — embeddings/reranking | 15270 | F04225 | non-negotiable | false | 10 |
| R08419 | 3090 role — perception/GUI | 15272 | F04225 | non-negotiable | false | 10 |
| R08420 | 3090 role — failure classification | 15274 | F04225 | non-negotiable | false | 10 |
| R08421 | 3090 role — sandboxed experiments | 15276 | F04225 | non-negotiable | false | 10 |
| R08422 | 3090 role — cheap branch expansion | 15278 | F04225 | non-negotiable | false | 10 |
| R08423 | Compact move — tokens | 15284 | F04226 | non-negotiable | false | 10 |
| R08424 | Compact move — scores | 15285 | F04226 | non-negotiable | false | 10 |
| R08425 | Compact move — branch refs | 15286 | F04226 | non-negotiable | false | 10 |
| R08426 | Compact move — memory ids | 15287 | F04226 | non-negotiable | false | 10 |
| R08427 | Compact move — tool intents | 15288 | F04226 | non-negotiable | false | 10 |
| R08428 | Compact move — patch summaries | 15289 | F04226 | non-negotiable | false | 10 |
| R08429 | Avoid move — KV tensors | 15294 | F04227 | non-negotiable | false | 10 |
| R08430 | Avoid move — activations | 15296 | F04227 | non-negotiable | false | 10 |
| R08431 | Avoid move — layer-split traffic | 15298 | F04227 | non-negotiable | false | 10 |
| R08432 | Avoid move — huge intermediate states | 15300 | F04227 | non-negotiable | false | 10 |
| R08433 | DevOps doctrine — "Use Linux primitives as first-class architecture" | 15300 | F04228 | non-negotiable | false | 10 |
| R08434 | Primitive — systemd: service lifecycle | 15304 | F04229 | non-negotiable | false | 10 |
| R08435 | Primitive — systemd: watchdogs | 15304 | F04229 | non-negotiable | false | 10 |
| R08436 | Primitive — systemd: slices | 15304 | F04229 | non-negotiable | false | 10 |
| R08437 | Primitive — cgroup v2: CPU/memory/IO/PID budgets | 15306 | F04230 | non-negotiable | false | 10 |
| R08438 | Primitive — AppArmor/seccomp: sandbox boundaries | 15308 | F04231 | non-negotiable | false | 10 |
| R08439 | Primitive — eBPF: truth sensor for file/network/process behavior | 15310 | F04232 | non-negotiable | false | 10 |
| R08440 | Primitive — ZFS: snapshots + rollback + replay + clone workspaces | 15312 | F04233 | non-negotiable | false | 10 |
| R08441 | Primitive — Podman/Quadlet: systemd-managed containers | 15314 | F04234 | non-negotiable | false | 10 |
| R08442 | Primitive — VFIO: hard isolate 3090 when needed | 15316 | F04235 | non-negotiable | false | 10 |
| R08443 | "This lets profiles become real" | 15318 | E0484 | non-negotiable | false | 10 |
| R08444 | Profile bundle — fast | 15320 | F04236 | non-negotiable | false | 10 |
| R08445 | Profile bundle — careful | 15321 | F04237 | non-negotiable | false | 10 |
| R08446 | Profile bundle — private | 15322 | F04238 | non-negotiable | false | 10 |
| R08447 | Profile bundle — offline | 15323 | F04239 | non-negotiable | false | 10 |
| R08448 | Profile bundle — research | 15324 | F04240 | non-negotiable | false | 10 |
| R08449 | Profile bundle — autonomous | 15325 | F04241 | non-negotiable | false | 10 |
| R08450 | Profile bundle — production | 15326 | F04242 | non-negotiable | false | 10 |
| R08451 | Profile bundle — experimental | 15327 | F04243 | non-negotiable | false | 10 |
| R08452 | AI Runtime Loop — MAP step | 15330 | M00847 | non-negotiable | false | 10 |
| R08453 | MAP definition — inspect environment, repo, tools, memory, risk | 15332 | M00847 | non-negotiable | false | 10 |
| R08454 | AI Runtime Loop — SPEC step | 15334 | M00847 | non-negotiable | false | 10 |
| R08455 | SPEC definition — define intended behavior and constraints | 15336 | M00847 | non-negotiable | false | 10 |
| R08456 | AI Runtime Loop — TEST step | 15338 | M00847 | non-negotiable | false | 10 |
| R08457 | TEST definition — generate or select executable truth | 15340 | M00847 | non-negotiable | false | 10 |
| R08458 | AI Runtime Loop — ACT step | 15342 | M00847 | non-negotiable | false | 10 |
| R08459 | ACT definition — route work to scout/oracle/tools | 15344 | M00847 | non-negotiable | false | 10 |
| R08460 | AI Runtime Loop — EVAL step | 15346 | M00847 | non-negotiable | false | 10 |
| R08461 | EVAL definition — judge outcome, trajectory, cost, risk | 15348 | M00847 | non-negotiable | false | 10 |
| R08462 | AI Runtime Loop — COMMIT step | 15350 | M00847 | non-negotiable | false | 10 |
| R08463 | COMMIT definition — gated write, snapshot, replay | 15352 | M00847 | non-negotiable | false | 10 |
| R08464 | AI Runtime Loop — LEARN step | 15354 | M00847 | non-negotiable | false | 10 |
| R08465 | LEARN definition — update memory, routing, profiles, later LoRAs | 15356 | M00847 | non-negotiable | false | 10 |
| R08466 | Surface — local web dashboard: traces + costs + profiles + model health + approvals | 15356 | F04245 | non-negotiable | false | 10 |
| R08467 | Surface — CLI: run task | 15358 | F04246 | non-negotiable | false | 10 |
| R08468 | Surface — CLI: inspect trace | 15358 | F04246 | non-negotiable | false | 10 |
| R08469 | Surface — CLI: resume session | 15358 | F04246 | non-negotiable | false | 10 |
| R08470 | Surface — CLI: switch profile | 15358 | F04246 | non-negotiable | false | 10 |
| R08471 | Surface — API: Anthropic-compatible primary | 15360 | F04247 | non-negotiable | false | 10 |
| R08472 | Surface — API: OpenAI-compatible secondary | 15360 | F04247 | non-negotiable | false | 10 |
| R08473 | Surface — MCP/tools: controlled capability layer | 15362 | F04248 | non-negotiable | false | 10 |
| R08474 | Surface — Project integration: Claude Code / Cline / OpenCode point at local gateway | 15362–15364 | F04249 | non-negotiable | false | 10 |
| R08475 | Design Law — "Models propose." | 15372 | M00849 | non-negotiable | false | 10 |
| R08476 | Design Law — "Runtime routes." | 15374 | M00849 | non-negotiable | false | 10 |
| R08477 | Design Law — "CPU enforces." | 15376 | M00849 | non-negotiable | false | 10 |
| R08478 | Design Law — "Tools prove." | 15378 | M00849 | non-negotiable | false | 10 |
| R08479 | Design Law — "ZFS remembers." | 15380 | M00849 | non-negotiable | false | 10 |
| R08480 | Design Law — "User chooses." | 15382 | M00849 | non-negotiable | false | 10 |
| R08481 | "That is the architecture" | 15384 | M00849 | non-negotiable | false | 10 |
| R08482 | Closing — "The cloud has scale" | 15386 | M00849 | non-negotiable | false | 10 |
| R08483 | Closing — "This machine has locality" | 15388 | M00849 | non-negotiable | false | 10 |
| R08484 | Closing — continuity | 15388 | M00849 | non-negotiable | false | 10 |
| R08485 | Closing — hardware control | 15388 | M00849 | non-negotiable | false | 10 |
| R08486 | Closing — private context | 15388 | M00849 | non-negotiable | false | 10 |
| R08487 | Closing — rollback | 15388 | M00849 | non-negotiable | false | 10 |
| R08488 | Closing — user sovereignty | 15388 | M00849 | non-negotiable | false | 10 |
| R08489 | Closing — "That is how it becomes better for real work" | 15390 | M00849 | non-negotiable | false | 10 |
| R08490 | Architect-seat scope — DevOps + Fullstack + AI-expert roles re-enabled | 15120 | M00833 | non-negotiable | false | 10 |
| R08491 | Architect-seat doctrine — return to architecture means hardware + stack + AVX-512 perspective | 15120 | M00833 | non-negotiable | false | 10 |
| R08492 | Layer mapping — Clients → Gateway: REST/gRPC/HTTP semantics | architecture + 15152 | M00841 | non-negotiable | false | 10 |
| R08493 | Layer mapping — Gateway → Cognitive Runtime: in-process tokio channel | architecture + 15164 | M00841 | non-negotiable | false | 10 |
| R08494 | Layer mapping — Cognitive Runtime → Hardware Execution: AVX-512 hot tables + CUDA streams | architecture + 15174 | M00841 | non-negotiable | false | 10 |
| R08495 | Layer mapping — Hardware Execution → Persistence: ZFS write-ahead + replay log + memory writes | architecture + 15182 | M00841 | non-negotiable | false | 10 |
| R08496 | Layer mapping — Persistence → memory router (closes loop) | architecture + 15169 | M00841 | non-negotiable | false | 10 |
| R08497 | Cross-repo — selfdef MS010 hardware-tune-cache + MS028 bitnet + MS029 slm-cpu-loop + MS030 tensor-parallel + MS031 wasm-aot-cache realize the AVX-512 + Blackwell + 3090 + RAM + ZFS hardware mapping | cross-ref MS010 + MS028 + MS029 + MS030 + MS031 | E0479 | non-negotiable | false | 10 |
| R08498 | Cross-repo — selfdef MS017 agent-guard + MS019 threat-model + MS020 L1-L5 test harness + MS027 observability realize the DevOps 7-primitive stack | cross-ref MS017 + MS019 + MS020 + MS027 | E0484 | non-negotiable | false | 10 |
| R08499 | Cross-repo — selfdef MS022 SSE quota + MS023 polarproxy + MS024 bridge-l2 + MS025 detect-host realize Gateway + Hardware Execution surfaces | cross-ref MS022 + MS023 + MS024 + MS025 | E0480 | non-negotiable | false | 10 |
| R08500 | Composite — M050 (10 epics / 17 modules / 85 features / 170 reqs) catalogs Architect+Engineer+DevOps+Fullstack+AI-expert seat: workstation as heterogeneous intelligence system NOT "PC that runs models" + 7-component hardware mapping (Ryzen-AVX-512=control plane / RTX-PRO-6000=oracle / RTX-3090=scout-sandbox / 256GB-RAM=arena / NVMe-ZFS=replay / Debian-Ubuntu=sovereign substrate / Anthropic-gateway=external compatibility) + 5-layer Core Architecture (Clients / Gateway / Cognitive Runtime / Hardware Execution / Persistence) + AVX-512 9-use-case logic accelerator + 9-SoA columnar hot data + 6-bulk-eval-mask + Blackwell 7-role + 3090 7-role + compact-move-vs-avoid-move artifact list + DevOps 7-primitive Linux stack (systemd + cgroup v2 + AppArmor-seccomp + eBPF + ZFS + Podman-Quadlet + VFIO) + 8 profile bundles + 7-step MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN runtime loop + 5-entry-point Fullstack Surface (dashboard + CLI + API + MCP-tools + project integration) + Design Law 6-line ("Models propose. Runtime routes. CPU enforces. Tools prove. ZFS remembers. User chooses.") + cloud-vs-station 6-property advantage ("locality + continuity + hardware control + private context + rollback + user sovereignty") + KEY LINE "That is how it becomes better for real work" | 15120–15390 | E0478-E0487 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: operator directive (R08331–R08335) + heterogeneous-intelligence-system doctrine (R08336–R08337) + 7-component hardware mapping (R08338–R08354) + 5-layer Core Architecture (R08355–R08380) + AVX-512 doctrine + 9 use cases (R08381–R08391) + 9-SoA columnar + 6 bulk masks + "deterministic AI infrastructure becomes fast" (R08392–R08408) + GPU doctrine + Blackwell 6 roles + 3090 7 roles + compact-move 6 + avoid-move 4 (R08409–R08432) + DevOps 7-primitive stack + "profiles become real" + 8 profile bundles (R08433–R08451) + 7-step AI Runtime Loop with definitions (R08452–R08465) + 5-entry-point Fullstack Surface (R08466–R08474) + Design Law 6 lines + "That is the architecture" + cloud-vs-station 6-property advantage + "better for real work" (R08475–R08489) + architect-seat scope + layer mapping invariants (R08490–R08496) + cross-repo binding (R08497–R08499) + composite (R08500)
- Source range 15120–15390 yields 270 lines; 170 R-rows represent ~63% line-coverage at the verbatim-citation level
- Project boundary — M050 is sovereign-os architect/engineer/DevOps/fullstack/AI-expert seat consolidation; selfdef IPS-side substrate (MS001–MS031) realizes the hardware-execution + DevOps + observability + policy planes; cross-repo binding via MS007 typed-mirror crates

## Cross-references

- Adjacent dump-range milestones: M049 Continuity through observability and policy (14812–15120) / M051 DevOps + Fullstack + AI expert layer (next; dump 15362–15705)
- Hardware mapping — 7 components align with M043 Bridge Layer hardware-aware intelligence scheduling + M044 Sovereign-OS substrate + M045 Linux as intelligence governor
- Core Architecture 5-layer — generalizes M048 13-module map into Clients/Gateway/Cognitive Runtime/Hardware Execution/Persistence layering
- AVX-512 9 use cases — directly maps to M039 AVX-512 cortex hot path + M043 AVX-512 Routing Brain (10 hot-metadata fields + 8 bulk-eval decisions)
- 9-SoA columnar + 6 bulk masks — extends M043 AVX-512 Routing Brain with explicit SoA naming + mask semantics
- GPU 7+7 role split — extends M043 Blackwell-as-Context-Sovereign (5 roles) + 3090-as-Cognitive-Scratchpad (8 uses) with the "do not fuse the GPUs mentally" doctrine
- DevOps 7-primitive stack — codifies M045 Linux as intelligence governor's 8 OS primitives + M048 Module 3 Container/Sandbox Fabric's Podman-Quadlet pattern
- 8 profile bundles — extends M042 Choice Architecture's 4 profile bundles + M045's 5 sovereign profiles + M044's 4 security profiles into the canonical 8 (fast/careful/private/offline/research/autonomous/production/experimental)
- 7-step AI Runtime Loop — finalizes M036 MAP+M041 6-contract+M042 8-axis-choice into MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN
- 5-entry-point Fullstack Surface — realizes M033 Compatibility Gateway + M034 Anthropic-first Gateway + M048 Module 4 Gateway via dashboard + CLI + API + MCP + project-integration entries
- Design Law 6-line — unifying frame: "Models propose. Runtime routes. CPU enforces. Tools prove. ZFS remembers. User chooses." — synthesizes all prior milestones
- Selfdef integration — selfdef MS010 hardware-tune-cache + MS028 bitnet + MS029 slm-cpu-loop + MS030 tensor-parallel + MS031 wasm-aot-cache realize the AVX-512 + Blackwell + 3090 + RAM + ZFS hardware mapping; selfdef MS017 + MS019 + MS020 + MS027 realize the DevOps 7-primitive stack; selfdef MS022 + MS023 + MS024 + MS025 realize Gateway + Hardware Execution surfaces; cross-repo binding via MS007 typed-mirror crates (8/8 SATURATED)
- Operator references: AMD Zen 5 9900X spec + NVIDIA RTX PRO 6000 Blackwell 96GB spec + NVIDIA RTX 3090 24GB spec + ProArt X870E-Creator motherboard + OpenZFS docs + Anthropic API spec + OpenAI Chat Completions API spec
