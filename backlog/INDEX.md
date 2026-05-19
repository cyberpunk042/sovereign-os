# Sovereign OS Workstation — Backlog INDEX (master timeline)

> The single workstation has two repos. This catalog is the **shared backlog**.
> Each entry names a milestone, epic, module, feature, or requirement.
> Each entry traces back to a source. **No invention.**
>
> Source authorities (in order of precedence):
> 1. Operator directive (verbatim, sacrosanct)
> 2. Raw dump `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` (info-hub, 18341 lines)
> 3. Existing selfdef SDDs 000-026 + existing sovereign-os SDDs 000-039
> 4. Existing SAIN-01 milestone (info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md`)
> 5. Existing selfdef README.md (14 modules + 12 notifier channels + 50+ crates + 9 cross-repo binding crates)
> 6. Existing sovereign-os README.md + ARCHITECTURE.md (11 SAIN-01 epics E100–E110)

## What this catalog covers

Per operator directive 2026-05-19:

> "THE FIRST THING IS IDENTIFYING THOSE 10000+ requirements in a clear timeline, multiple milestones and 400+ Epics and 1000+ modules and 5000+ features before starting working on them in order in SDD."

Target counts:

| Level | Target | Status |
|---|---|---|
| Milestones | ~31 | enumerated below (M00–M30); each gets a `milestones/MNN-*.md` file |
| Epics | 400+ | catalog in `epics/INDEX.md`; per-epic files in `epics/E*-*.md` |
| Modules | 1000+ | catalog in `modules/INDEX.md`; per-module files in `modules/M*-*.md` |
| Features | 5000+ | catalog in `features/INDEX.md`; per-feature files in `features/F*-*.md` |
| Requirements | 10000+ | catalog in `requirements/INDEX.md`; per-requirement files in `requirements/R*-*.md` |

Each level decomposes the previous by 2.5×–5× on average. Math:
- 31 milestones × ~13 epics = ~400 epics
- 400 epics × ~3 modules = ~1200 modules
- 1200 modules × ~4 features = ~4800 features
- 4800 features × ~2 requirements = ~10000 requirements
- 10000 requirements × ≥10 hard sub-requirements each = ≥100000 requirement-atoms (operator's stated decomposition)

## Master timeline — 31 milestones

Numbered M00–M30. Order = dependency-and-criticality order. Each milestone has its own `backlog/milestones/MNN-<slug>.md` file with its epic list, scope boundaries, and entry/exit criteria. Items in **bold** are the dump's named operational planes; items in *italic* are existing-shipped baselines that the AVX++ arc augments.

| # | Milestone | Source anchors | Status |
|---|---|---|---|
| **M00** | *Sovereign Foundation* — base OS image pipeline + profile schema + whitelabel + cross-repo boundaries | sovereign-os SDDs 000–039 | shipped baseline |
| **M01** | *SAIN-01 Hardware Substrate* — 9900X Zen 5 / Blackwell 96GB / 3090 24GB / ZFS / dual-NIC / VFIO | info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md` (E100–E110); selfdef SDD-017 hardware inventory | partially shipped (selfdef-side rollups + hardware-tune surface) |
| **M02** | *Detect+Defend Perimeter* — selfdef daemon + 6 collectors + 14 modules + 12 integrations + Phase 1-8 audit + 6 audit-shipped opt-ins | selfdef README.md + selfdef SDDs 000–008 + Phase 1-8 audit | shipped baseline |
| **M03** | **Hardware Exploitation Foundation** — AVX-512 Cortex (branch table + policy mask + bitset compose + compress/expand + ternary logic + bitset token-law + inline LUT) | dump §§ 1-2000 + 2000-3000 + 3300-4600 + 11185-11409; selfdef SDD-022 hardware-exploit doctrine | new |
| **M04** | **Anthropic-First Gateway** — `/v1/messages` + `/v1/models` + streaming + model aliases (jean/*) + OpenAI-compatible shim + MCP bridge + cost ledger + redaction | dump §§ 9486-10107 + 15915-16175 | new |
| **M05** | **Inference Fabric (multi-backend adapter)** — vLLM + SGLang + TRT-LLM + llama.cpp + bitnet.cpp + LM Studio + Ollama; unified `generate/embed/rerank/verify/perceive` interface | dump §§ 4631-4990 + 11790-11892; sovereign-os SDD-011 inference-backend-stack; sovereign-os SDD-036 inference-service-hardening | new (extends SDD-011) |
| **M06** | **Model Fabric + Registry** — Blackwell oracle server + 3090 scout server + embedding/rerank service + per-role registry (role · hardware_target · precision · context · latency · VRAM · eval_scores · adapter_support · trust · privacy_class) | dump §§ 4348-4624 + 16176-16210; selfdef SD-R71 ModelSpec + R212 catalog | new (extends R212 catalog) |
| **M07** | **Speculative Decoding Engine** — 3090 drafts 8-64 continuations × N branches → AVX-512 CPU filters → Blackwell verifies in packed pass; SpecInfer + Medusa + EAGLE + DFlash patterns | dump §§ 2459-2728 + 4631-4831; sovereign-os SDD-026 dflash-speculative-decoding | new (extends SDD-026) |
| **M08** | **MTP Integration** — Multi-Token Prediction wiring: llama.cpp PR #22673 (beta, ~1.7× speedup) + vLLM first-class `spec_decode_config` + SGLang + DeepSeek V3/V4 native + Qwen 3.6 native + Gemma 4 native | external research + dump §§ 7378-7728 | new |
| **M09** | **KV Cache Controller** — VRAM as L1/L2 + RAM as L3 + NVMe ZFS as cold cache; KvBlockMeta (hash_hi/hash_lo/model_id/token_range/trust_flags/heat/last_used/owner_policy); content-addressed `hash(model_id, tokenizer_id, prompt_bytes, schema_version)`; tool-schema KV; KV-aware routing | dump §§ 2459-3020 + 12705-12943 | new |
| **M10** | **Memory OS** — 8 memory types (Working + Episodic + Semantic + Procedural + Temporal Graph + Value + KV/prefix + Artifact); memory-as-tools (search/read/write/promote/forget); trust + freshness + privacy + value lifecycle; MemMachine/Letta/Zep/A-MEM/D-Mem/PlugMem patterns | dump §§ 4019-4346 + 8127-8474 + 13099-13205 | new |
| **M11** | **MAP / Environment Mapper** — repo map · test map · tool map · risk map · memory map · GUI/world map · dependency map; pre-act phase before any commit | dump § 10378-10711 ("MAP" paper extraction); operator-named (line 10422) | new |
| **M12** | **Eval / Value Plane** — 12-dim reward vector (correctness/evidence/schema_validity/tool_success/test_success/risk/latency/cost/novelty/user_preference/cache_reuse/confidence_calibration); PRM + RRM + ORM + RM judges; Best-of-N + tree search + MCTS-for-agents; anti-delusion law | dump §§ 7744-8120 + 5000-5366 | new |
| **M13** | **Goldilocks Profile System** — 8+ named profiles (private/fast/careful/offline/research/autonomous/experimental/production) + composite (careful_code, claude-jean-private, jean/oracle, etc.) + operator extensions; profile → reward weights → hardware effects pipeline | dump §§ 5009-5367 + 7613-7644 + 11722-11784; selfdef SDD-026 flex-profile Z-3 | new (extends 026 Z-3) |
| **M14** | **Sandbox Fabric** — tiered execution (read-only → workspace-write → Podman → network-denied → network-allowed → VFIO 3090 VM → browser/GUI → CRIU checkpoints → ZFS clone workspaces); 64-bit capability words per request | dump §§ 3385-3676 + 16252-16277 | new |
| **M15** | **Trust Boundary Enforcement** — 5 Trust Rings (R0-R4) + 4 Trust Zones (Host/Oracle/Sandbox/Disposable); VFIO + IOMMU + MIG + CRIU + AppArmor + cgroup v2 + seccomp + eBPF + LUKS2 + TPM2/FIDO2 wired | dump §§ 17217-17529 + 13325-13544 | new |
| **M16** | **Cognitive Compiler / Workflow Compiler** — Intent Parse → Context Build → Plan Synthesis → Plan Validation → Plan Optimization → Execution → Observation → Recompile → Commit → Learn; adaptive recompile triggers; symbolic-future / async function calling | dump §§ 7015-7376 + 16493-16894 | new |
| **M17** | **Workflow Engine (durable execution)** — Temporal-style durable execution; WorkflowRun (nodes · edges · frames · checkpoints · evals · pending_gates); pause/resume/cancel/fork/merge/rollback/recompile; LlamaIndex Workflows + Symphony patterns | dump §§ 3679-4002 + 6046-6364 + 10708-10963 | new |
| **M18** | **World Model Plane** — 5 tiers (Deterministic · Learned Local · Language · Simulated · Human); State/Action/Transition primitive; predicted transition records; rollback planner; success/failure detectors | dump §§ 8804-9150 | new |
| **M19** | **Symbolic Planning Plane** — PDDL planners + SAT/SMT solvers + Prolog/Datalog + LTL temporal logic monitors + FSMs + type/schema checkers; predicate bitsets + precondition/add/delete/forbidden masks | dump §§ 9151-9485 | new |
| **M20** | **Computer-Use Plane** — 3 layers (Perception → Planning → Execution); 6 profiles (observe_only · assistive · supervised · sandbox · autonomous_low_risk · high_risk); GUI state JSON + action JSON; trajectory replay + CUAVerifierBench scoring; Fara-7B + OmniParser V2 + ActionEngine patterns | dump §§ 8475-8802 | new |
| **M21** | **RLM Engine** — Recursive Language Model — long-context-as-environment; self-call orchestration; subcall state (parent_id · depth · context_slice_ref · question_ref · budget · uncertainty · reward_score · visited_hash); AVX-512 schedules dedup/depth/oracle/SLM-routing/slice-overlap | dump §§ 7378-7727 (RLM section + Alex Zhang paper extraction) | new |
| **M22** | **SLM Swarm** — 14+ named small specialists: intent classifier · tool-call planner · JSON fixer · schema selector · risk tagger · memory router · branch summarizer · patch scout · GUI perception helper · query reformulator · test failure classifier · uncertainty assessor · difficulty estimator · PDDL syntax repair; SLM-survey patterns (Fara-7B, TinyLLM) | dump §§ 7445-7470 + 8014-8027 | new |
| **M23** | **Model Lab + LoRA Foundry** — per-precision qualification (BF16 baseline + FP8 + GPTQ W4A16 + SmoothQuant W8A8 + AWQ + NVFP4/MXFP4 + KV-cache quantization); per-role qualification (oracle/scout/router-classifier/perception); LoRA pipeline (trace → curated dataset → adapter training → eval gate → profile assignment → monitored deployment); multi-LoRA serving (vLLM dynamic + S-LoRA/Punica + Ray Serve); 9 named LoRA examples | dump §§ 10554-10599 + 13825-14106 | new |
| **M24** | **Cloud Expert Plane** — Anthropic + OpenAI as optional remote experts behind capability gates; vault proxy / stub-credential pattern; cost ledger toggles; per-request audit; redaction layer; LiteLLM Agent Platform patterns | dump §§ 9504-9956 | new |
| **M25** | **Continuity Manager** — workflow hibernation + ZFS snapshot per risky action + CRIU sandbox checkpoints + warm model sessions + resume tokens; 8 context lifecycle states (hot/warm/indexed/cold/hibernated/quarantined/forgotten/active); zombie-reap rules | dump §§ 14107-14400 | new |
| **M26** | **Configuration Resolver** — 7-layer layered config (hardware · OS · runtime · policy · workflow · user · project); conflict resolution rules (hard policy beats profile · project beats generic · user approval elevates within hard limits · offline beats cloud · sandbox beats host) | dump §§ 14817-15119 | new |
| **M27** | **Cost Ledger + Resource Governance** — tokens + GPU seconds + cloud dollars + energy + latency + cache hits + branch acceptance + tool retries + oracle calls + per-client budget + per-project budget; AgentRM-style resource manager (scheduling, rate-limit admission, zombie reaping, context lifecycle); human attention as resource | dump §§ 13036-13305 + 9728-9956 | new |
| **M28** | **Observability Fabric** — OpenTelemetry GenAI semantic conventions (model_call/tool_call/memory_read/memory_write/route_decision/policy_decision/sandbox_start/sandbox_stop/test_run/eval_score/checkpoint/rollback/human_gate/cloud_call/cost_event) + DCGM + eBPF + PSI + journald + Phoenix/Langfuse trace UI; feedback loop into scheduler | dump §§ 3022-3369 + 14827-14924; sovereign-os SDD-016 observability-bindings + SDD-025 observability-cli-architecture | new (extends SDD-016 + SDD-025) |
| **M29** | **Policy Fabric** — PolicyDecision (allow/deny/ask_user/sandbox/escalate_to_oracle/require_snapshot/require_test); intent-based policy input (subject · action · resource · intent · profile · risk · model/provider · context_sensitivity · side_effect_class · user_approval_state); OPA/Cedar/OpenFGA as replaceable backends | dump §§ 14924-14997 + 17217-17530 | new |
| **M30** | **Tool ABI / Tool Gate** — typed tool ABI (tool_id · version · input_schema · output_schema · capabilities_required · side_effect_class · determinism · sandbox_required · timeout_ms · rollback_strategy); 4 tool tiers (A/B/C/D); 6 execution tiers (Pure Logic / WASM / Deno / Python REPL / Containers-microVMs / VFIO 3090 VM); 8 REPL types (math/Python/Deno-TS/SQL/shell/browser/simulation/WASM) | dump §§ 6380-6671 + 16689-16710 | new |

## Cross-cutting concerns (every milestone owns its share)

1. **Profiles** — every module exposes profile knobs; every milestone names which profiles affect its behavior
2. **Whitelabel** — every UI surface routes through whitelabel mechanism (sovereign-os SDD-007 + SDD-012)
3. **Observability** — every action emits an OTel span (`trace_id · span_id · parent_span_id · event_type · module · timestamp · profile · cost · risk · status`)
4. **Evolvability** — every contract is versioned; every module is replaceable
5. **Opt-in everywhere** — every feature has an `enabled: true/false` toggle in profile YAML; runtime starts with all opt-in features OFF
6. **Continuity** — every long-running workflow has a hibernation contract
7. **Reversibility** — every commit names its rollback path (ZFS snapshot · CRIU restore · reverse-diff · policy revert)
8. **Real UX (Hat 4)** — every dashboard names its IA, user flow, interaction states (loading/error/empty/success), visual hierarchy, accessibility posture

## Cockpit dashboards (cross-cutting against M28 + every plane milestone)

1 main cockpit + 22 specialized surfaces, each opt-in:

| # | Dashboard | Plane milestone it surfaces |
|---|---|---|
| **D-00** | Main Cockpit | composes every other dashboard |
| D-01 | Sessions | M16 + M17 |
| D-02 | Profile Picker | M13 |
| D-03 | Model Health | M05 + M06 |
| D-04 | Cost & Budget | M27 |
| D-05 | Trace Explorer | M28 |
| D-06 | Approval Queue | M29 |
| D-07 | Memory Inspector | M10 |
| D-08 | Rollback / Snapshot | M25 |
| D-09 | Hardware Pressure | M03 + M01 |
| D-10 | Eval History | M12 + M23 |
| D-11 | Adapter / LoRA | M23 |
| D-12 | Policy Editor | M29 |
| D-13 | Workflow / DAG Visualizer | M16 + M17 |
| D-14 | Tool Catalog | M30 |
| D-15 | Memory Graph Explorer | M10 |
| D-16 | Sandbox Monitor | M14 + M15 |
| D-17 | KV Cache Heatmap | M09 |
| D-18 | World Model / Transition Predictor | M18 |
| D-19 | Computer-Use Trajectory Replay | M20 |
| D-20 | Symbolic Plan Visualizer | M19 |
| D-21 | RLM Tree Explorer | M21 |
| D-22 | Provider Routing | M04 + M24 |

## 10–15 main features (cross-cutting, composed from milestones)

Per operator directive "10–15 main features and many more sub-features and endless configurations and options and personalizations":

| # | Main Feature | Composed from |
|---|---|---|
| **F-MAIN-01** | Sovereign Anthropic-compatible Gateway (Claude Code talks to your station) | M04 + M24 + M27 |
| **F-MAIN-02** | Three-Organ Cognition (Blackwell Oracle + 3090 Scout + AVX-512 Cortex) | M03 + M05 + M06 |
| **F-MAIN-03** | Speculative Cognition with Deterministic Commit | M07 + M08 + M12 |
| **F-MAIN-04** | Situated Intelligence (Memory OS + MAP + RLM) | M10 + M11 + M21 |
| **F-MAIN-05** | Programmable Profiles + Adaptive Routing (Goldilocks) | M13 + M16 + M22 |
| **F-MAIN-06** | Safe Autonomy (Sandbox Fabric + Trust Boundary + World Model + Symbolic Planning) | M14 + M15 + M18 + M19 |
| **F-MAIN-07** | Computer-Use Agent (Perception → Planning → Execution under policy) | M20 + M29 + M30 |
| **F-MAIN-08** | Durable Workflows (Cognitive Compiler + Workflow Engine + Continuity Manager) | M16 + M17 + M25 |
| **F-MAIN-09** | Model Lab + LoRA Foundry (per-precision qualification + adapter pipeline) | M23 + M06 |
| **F-MAIN-10** | Cost & Energy Sovereignty (Cost Ledger + Resource Governance) | M27 + M28 |
| **F-MAIN-11** | Cockpit UX (1 main + 22 specialized dashboards, all opt-in) | M28 + every plane milestone |
| **F-MAIN-12** | Cross-Repo Bridges (selfdef perimeter ↔ runtime; info-hub knowledge ↔ memory OS) | M02 + M10 + cross-repo binding crates |
| **F-MAIN-13** | Reproducible OS Image (build pipeline + profile schema + whitelabel + decommission) | M00 + M01 |
| **F-MAIN-14** | Deterministic Cortex Runtime (the dump's `Models propose; the runtime commits` law applied across every plane) | every plane milestone |

## Multi-year delivery timeline (operator-stated horizon)

Operator-stated: *"See this a year project"* + *"I have enough work for years"*.

Phased delivery:

| Phase | Span | Milestones delivered | Gate criterion |
|---|---|---|---|
| **Phase A: Substrate Complete** | shipped + first 3 months | M00 + M01 + M02 + M03 + M04 baseline | Anthropic-compatible gateway serves Claude Code with at least 2 profile aliases backed by 2 model adapters; SAIN-01 hardware passes friction-audit; AVX-512 cortex prototype runs branch-table filter on real workload |
| **Phase B: Inference Spine** | months 4–9 | M05 + M06 + M07 + M08 + M09 | Multi-backend adapter contract stable; 3090 drafts → AVX filters → Blackwell verifies pipeline measured; MTP active on at least one model; KV cache controller measured cache hit ≥ 60% |
| **Phase C: Cognitive Layer** | months 10–18 | M10 + M11 + M12 + M13 + M16 + M17 | MAP-before-act discipline shipped; reward vector live; profiles drive hardware behavior; cognitive compiler emits DAGs; durable workflows survive reboot |
| **Phase D: Safe Autonomy** | months 19–24 | M14 + M15 + M18 + M19 + M20 | Sandbox tiers operational; trust boundaries enforced; world model predicts transitions; symbolic planning gates high-risk commits; computer-use agent ships under autonomous_low_risk profile |
| **Phase E: Specialist Cognition** | months 25–30 | M21 + M22 + M23 + M24 | RLM tree explorer ships; SLM swarm of 14+ specialists deployed; LoRA foundry promotes adapters via eval gate; cloud expert plane behind vault proxy |
| **Phase F: Continuity + Governance** | months 31–36 | M25 + M26 + M27 + M28 + M29 + M30 | Sessions survive reboot via CRIU + ZFS; 7-layer config resolver active; cost ledger live on main cockpit; policy fabric replaceable backends |
| **Phase G: Cockpit Complete** | months 37–48+ | D-00 through D-22 fully implemented | All 23 dashboards ship with real UX (IA + flows + interaction states + accessibility); operator can drive every plane from cockpit, CLI, or MCP |

Each phase's exit criterion is measurable; no clarification gates. Operator overrides phase ordering at any time.

## Cross-repo placement

Where each milestone primarily lives (some span both repos):

| Repo | Owns |
|---|---|
| `sovereign-os` | M00, M01 (hardware spec), M03 (AVX-512 cortex), M04 (gateway), M05 (inference fabric), M06 (model fabric), M07 (speculative), M08 (MTP), M09 (KV cache), M10 (memory OS), M11 (MAP), M12 (eval), M13 (profiles), M14 (sandbox), M16 (compiler), M17 (workflow), M18 (world model), M19 (symbolic planning), M20 (computer-use), M21 (RLM), M22 (SLM swarm), M23 (model lab), M24 (cloud expert), M25 (continuity), M26 (config), M27 (cost ledger), M28 (observability spine), M29 (policy), M30 (tool ABI), D-00 through D-22 (cockpit dashboards) |
| `selfdef` | M02 (security daemon baseline), M03 selfdef-side rollups (hardware-tune), M15 (trust boundary enforcement — wires VFIO/AppArmor/eBPF into both), security extensions to every runtime plane (eventstream consumer of runtime traces; agent-guard policing runtime sandboxes); new cross-repo binding crates `selfdef-runtime-manifest`, `selfdef-route-manifest`, `selfdef-cortex-manifest` |
| `info-hub` | architectural baseline + raw dumps + decisions log + L1/L2/L3 syntheses — **read-only for project work** per operator standing directive |

## How operators ratify this catalog

Same pattern as the cycle-N-vectors SDDs (selfdef 019/020/021/024/025/026):

1. Operator reads `backlog/INDEX.md` (this file) + `backlog/milestones/INDEX.md` + per-milestone files
2. Operator edits ENTRIES IN PLACE — renames, reorders, splits, merges
3. Each milestone's entry/exit criterion is measurable so the AI doesn't ask "is this done?"
4. Catalog evolves continuously; no freeze gates

## Status

- **Master timeline** (this file): authored
- `backlog/milestones/INDEX.md`: next commit
- `backlog/milestones/M03-hardware-exploitation-foundation.md`: first full milestone decomposition (next commit) — extracts every AVX-512 / cortex / branch-table primitive from the dump as epic/module/feature/requirement
- Subsequent milestones decomposed iteratively over the multi-year horizon

— End of master timeline.
