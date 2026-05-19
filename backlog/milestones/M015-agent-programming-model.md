# M015 — Agent programming model

> Parent: `backlog/milestones/INDEX.md` row M015 (dump 3678–4003).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 3678–4003.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0126–E0135)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0126 | Agent programming model — the abstraction question after hardware/isolation/memory/replay/observability | 3694–3717 |
| E0127 | Research substrate — ReAct / Toolformer / LangGraph durable execution / DSPy optimizable programs | 3712–3715 |
| E0128 | Agent as state machine — graph + typed state + replay + gated side effects | 3719–3763 |
| E0129 | Typed state — explicit `AgentState` struct | 3765–3795 |
| E0130 | Five node classes — Deterministic / Scout / Oracle / Tool / Human Gate | 3797–3818 |
| E0131 | Human Gate node — rich operator view + 6-action affordance + durable pause-resume | 3820–3849 |
| E0132 | Program Optimization — DSPy-style optimize-against-metrics; runtime tuning first, fine-tuning later | 3851–3888 |
| E0133 | Agent DSL — YAML workflow definitions, e.g. `code_patch` | 3890–3918 |
| E0134 | AVX-512 in agent graphs — vectorized graph-transition scheduling | 3920–3944 |
| E0135 | Critical separation — thought ≠ action, observation ≠ trusted, commit is deterministic; updated 7-plane system; evolution Prompt chain → Agent loop → Durable graph → Deterministic AI OS | 3946–4002 |

## Modules (M00233–M00249)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00233 | Workflow graph — nodes = deterministic-or-model/tool actions / edges = policy-checked transitions / state = typed checkpointed replayable / side effects = gated commits | 3726–3731 | E0128 |
| M00234 | Canonical workflow — Intake → Classify → Retrieve → DraftPlan → PolicyCheck → OracleReview → ToolIntent → HumanGate? → ExecuteSandbox → ValidateResult → Commit → SummarizeMemory | 3735–3748 | E0128 |
| M00235 | Per-node contract — input schema / output schema / allowed tools / risk level / budget / model route / cache policy / checkpoint policy | 3752–3761 | E0128 |
| M00236 | `AgentState` Rust struct — task_id / branch_id / control / risk / budget / memory_refs / kv_refs / tool_intents / artifacts / trace_id | 3769–3781 | E0129 |
| M00237 | Model output typed envelopes — PlanProposal / ToolIntent / PatchProposal / MemoryWrite / VerificationResult / FinalAnswer | 3787–3793 | E0129 |
| M00238 | Node class 1 — Deterministic Node (pure CPU logic, parsers, masks, policy, validation) | 3802–3804 | E0130 |
| M00239 | Node class 2 — Scout Node (3090 model, cheap exploration/proposals) | 3805–3807 | E0130 |
| M00240 | Node class 3 — Oracle Node (Blackwell model, expensive synthesis/verification) | 3808–3810 | E0130 |
| M00241 | Node class 4 — Tool Node (shell/browser/file/API, always gated) | 3811–3813 | E0130 |
| M00242 | Node class 5 — Human Gate Node (explicit pause/resume with full context) | 3814–3816 | E0130 |
| M00243 | Human-gate display — what the agent wants / why / files-tools-network involved / risk bits / expected side effects / rollback plan / diff or command preview / model confidence / policy reason | 3826–3836 | E0131 |
| M00244 | Human-gate actions — approve / deny / edit / route to sandbox / ask oracle to review / lower-raise permission | 3840–3847 | E0131 |
| M00245 | Optimization metric set — task success / tool rejection rate / oracle calls per task / latency / user interventions / test pass rate / rollback rate / branch acceptance rate / KV reuse / memory usefulness | 3858–3868 | E0132 |
| M00246 | Tuning surface — scout model selection / speculation depth / retrieval thresholds / prompt templates / grammar strictness / oracle review thresholds / tool approval policies / cache admission | 3872–3881 | E0132 |
| M00247 | Agent DSL — `workflow:` + `nodes:` (per-node `type` / `gpu` / `policy` / `requires` / `output`) | 3894–3916 | E0133 |
| M00248 | Vectorized graph scheduler — SoA arrays `node_state[branch]` / `risk[branch]` / `budget[branch]` / `route[branch]` / `permission[branch]` | 3925–3942 | E0134 |
| M00249 | Updated 7-plane system — Inference / Control / Memory / Storage / Tool / Observability / Programming | 3970–3992 | E0135 |

## Features (F01191–F01275)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01191 | Toggle programming-plane backend (rust-native / langgraph-bridge / dspy-bridge) | 3712–3715 | E0127 | mode | true |
| F01192 | Profile knob — `programming_plane_backend = rust_native \| langgraph \| dspy` | 3712–3715 | E0127 | profile | true |
| F01193 | Env var `SOVEREIGN_PROGRAMMING_PLANE_BACKEND` | 3712–3715 | E0127 | env_var | true |
| F01194 | CLI `--programming-plane-backend <name>` | 3712–3715 | E0127 | cli_verb | true |
| F01195 | Workflow loader — read DSL from `workflows/<name>.yaml` | 3892–3916 | M00247 | composite | false |
| F01196 | Workflow node — Intake | 3736 | M00234 | composite | false |
| F01197 | Workflow node — Classify | 3737 | M00234 | composite | false |
| F01198 | Workflow node — Retrieve | 3738 | M00234 | composite | false |
| F01199 | Workflow node — DraftPlan | 3739 | M00234 | composite | false |
| F01200 | Workflow node — PolicyCheck | 3740 | M00234 | composite | false |
| F01201 | Workflow node — OracleReview | 3741 | M00234 | composite | false |
| F01202 | Workflow node — ToolIntent | 3742 | M00234 | composite | false |
| F01203 | Workflow node — HumanGate? | 3743 | M00234 | composite | true |
| F01204 | Workflow node — ExecuteSandbox | 3744 | M00234 | composite | false |
| F01205 | Workflow node — ValidateResult | 3745 | M00234 | composite | false |
| F01206 | Workflow node — Commit | 3746 | M00234 | composite | false |
| F01207 | Workflow node — SummarizeMemory | 3747 | M00234 | composite | false |
| F01208 | Per-node contract field — input_schema | 3753 | M00235 | data_model | false |
| F01209 | Per-node contract field — output_schema | 3754 | M00235 | data_model | false |
| F01210 | Per-node contract field — allowed_tools | 3755 | M00235 | data_model | false |
| F01211 | Per-node contract field — risk_level | 3756 | M00235 | data_model | false |
| F01212 | Per-node contract field — budget | 3757 | M00235 | data_model | false |
| F01213 | Per-node contract field — model_route | 3758 | M00235 | data_model | false |
| F01214 | Per-node contract field — cache_policy | 3759 | M00235 | data_model | false |
| F01215 | Per-node contract field — checkpoint_policy | 3760 | M00235 | data_model | false |
| F01216 | `AgentState` field — task_id | 3771 | M00236 | data_model | false |
| F01217 | `AgentState` field — branch_id | 3772 | M00236 | data_model | false |
| F01218 | `AgentState` field — control (u64 control word) | 3773 | M00236 | data_model | false |
| F01219 | `AgentState` field — risk (u8) | 3774 | M00236 | data_model | false |
| F01220 | `AgentState` field — budget (u32) | 3775 | M00236 | data_model | false |
| F01221 | `AgentState` field — memory_refs (Vec<u64>) | 3776 | M00236 | data_model | false |
| F01222 | `AgentState` field — kv_refs (Vec<u64>) | 3777 | M00236 | data_model | false |
| F01223 | `AgentState` field — tool_intents (Vec<ToolIntent>) | 3778 | M00236 | data_model | false |
| F01224 | `AgentState` field — artifacts (Vec<ArtifactRef>) | 3779 | M00236 | data_model | false |
| F01225 | `AgentState` field — trace_id (TraceId) | 3780 | M00236 | data_model | false |
| F01226 | Typed envelope — PlanProposal | 3788 | M00237 | data_model | false |
| F01227 | Typed envelope — ToolIntent | 3789 | M00237 | data_model | false |
| F01228 | Typed envelope — PatchProposal | 3790 | M00237 | data_model | false |
| F01229 | Typed envelope — MemoryWrite | 3791 | M00237 | data_model | false |
| F01230 | Typed envelope — VerificationResult | 3792 | M00237 | data_model | false |
| F01231 | Typed envelope — FinalAnswer | 3793 | M00237 | data_model | false |
| F01232 | Node-class registry — Deterministic / Scout / Oracle / Tool / HumanGate (closed taxonomy) | 3800–3816 | E0130 | composite | false |
| F01233 | Every node returns typed result plus metrics | 3818 | E0130 | composite | false |
| F01234 | Human-gate display — what the agent wants to do | 3827 | M00243 | composite | true |
| F01235 | Human-gate display — why it wants to do it | 3828 | M00243 | composite | true |
| F01236 | Human-gate display — what files/tools/network are involved | 3829 | M00243 | composite | true |
| F01237 | Human-gate display — risk bits | 3830 | M00243 | composite | true |
| F01238 | Human-gate display — expected side effects | 3831 | M00243 | composite | true |
| F01239 | Human-gate display — rollback plan | 3832 | M00243 | composite | true |
| F01240 | Human-gate display — diff or command preview | 3833 | M00243 | composite | true |
| F01241 | Human-gate display — model confidence | 3834 | M00243 | composite | true |
| F01242 | Human-gate display — policy reason | 3835 | M00243 | composite | true |
| F01243 | Human-gate action — approve | 3841 | M00244 | composite | true |
| F01244 | Human-gate action — deny | 3842 | M00244 | composite | true |
| F01245 | Human-gate action — edit | 3843 | M00244 | composite | true |
| F01246 | Human-gate action — route to sandbox | 3844 | M00244 | composite | true |
| F01247 | Human-gate action — ask oracle to review | 3845 | M00244 | composite | true |
| F01248 | Human-gate action — lower/raise permission | 3846 | M00244 | composite | true |
| F01249 | Optimization metric — task_success | 3859 | M00245 | observability_metric | false |
| F01250 | Optimization metric — tool_rejection_rate | 3860 | M00245 | observability_metric | false |
| F01251 | Optimization metric — oracle_calls_per_task | 3861 | M00245 | observability_metric | false |
| F01252 | Optimization metric — latency | 3862 | M00245 | observability_metric | false |
| F01253 | Optimization metric — user_interventions | 3863 | M00245 | observability_metric | false |
| F01254 | Optimization metric — test_pass_rate | 3864 | M00245 | observability_metric | false |
| F01255 | Optimization metric — rollback_rate | 3865 | M00245 | observability_metric | false |
| F01256 | Optimization metric — branch_acceptance_rate | 3866 | M00245 | observability_metric | false |
| F01257 | Optimization metric — kv_reuse | 3867 | M00245 | observability_metric | false |
| F01258 | Optimization metric — memory_usefulness | 3868 | M00245 | observability_metric | false |
| F01259 | Tuning knob — scout model selection | 3873 | M00246 | profile | true |
| F01260 | Tuning knob — speculation depth | 3874 | M00246 | profile | true |
| F01261 | Tuning knob — retrieval thresholds | 3875 | M00246 | profile | true |
| F01262 | Tuning knob — prompt templates | 3876 | M00246 | profile | true |
| F01263 | Tuning knob — grammar strictness | 3877 | M00246 | profile | true |
| F01264 | Tuning knob — oracle review thresholds | 3878 | M00246 | profile | true |
| F01265 | Tuning knob — tool approval policies | 3879 | M00246 | profile | true |
| F01266 | Tuning knob — cache admission | 3880 | M00246 | profile | true |
| F01267 | DSL example — `workflow: code_patch` with 5 nodes (classify/retrieve/draft_patch/review_patch/apply_patch) | 3894–3916 | M00247 | composite | true |
| F01268 | API `POST /v1/workflows/{name}/start` | 3892–3918 | M00247 | api_endpoint | true |
| F01269 | API `POST /v1/workflows/{instance_id}/resume` (durable pause-resume) | 3849 | M00247 | api_endpoint | true |
| F01270 | API `GET /v1/workflows/{instance_id}/state` | 3729 | M00247 | api_endpoint | true |
| F01271 | API `GET /v1/workflows/{instance_id}/trace` | 3729 | M00247 | api_endpoint | true |
| F01272 | Dashboard — workflow DAG visualizer (live nodes with state) | 3725–3748 | M00233 | dashboard | true |
| F01273 | Dashboard — agent-state inspector (per-branch typed state with all 10 fields) | 3769–3781 | M00236 | dashboard | true |
| F01274 | Dashboard — human-gate queue (pending approvals with full context) | 3820–3849 | M00243 | dashboard | true |
| F01275 | Composite — Programming Plane is the 7th plane; evolution path Prompt chain → Agent loop → Durable graph → Deterministic AI OS | 3989–3998 | E0135 | composite | false |

## Requirements (R02381–R02550)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R02381 | The programming abstraction question follows hardware / isolation / memory / replay / observability | 3696–3700 | E0126 | non-negotiable | false | 10 |
| R02382 | The answer is NOT "prompt chains" | 3702 | E0126 | non-negotiable | false | 10 |
| R02383 | The answer is "deterministic workflow graph + probabilistic nodes + typed state + replay" | 3706–3707 | E0126 | non-negotiable | false | 10 |
| R02384 | ReAct interleaves reasoning and action so models can update plans by acting and observing | 3712 | E0127 | non-negotiable | false | 10 |
| R02385 | Toolformer shows models can learn when/how to call tools and incorporate results | 3713 | E0127 | non-negotiable | false | 10 |
| R02386 | LangGraph emphasizes durable execution, persistence, and human-in-the-loop workflows | 3714 | E0127 | non-negotiable | false | 10 |
| R02387 | LangGraph checkpointing lets state resume after interrupts/failures | 3714 | E0127 | non-negotiable | false | 10 |
| R02388 | DSPy treats language-model pipelines as optimizable programs rather than brittle prompt strings | 3715 | E0127 | non-negotiable | false | 10 |
| R02389 | DSPy compiles structured code into prompts/weights optimized against metrics | 3715 | E0127 | non-negotiable | false | 10 |
| R02390 | Runtime absorbs ReAct/Toolformer/LangGraph/DSPy ideas at lower level + hardware-aware | 3717 | E0126 | non-negotiable | false | 10 |
| R02391 | An agent is NOT a chat loop | 3721 | E0128 | non-negotiable | false | 10 |
| R02392 | Workflow graph — nodes = deterministic or model/tool actions | 3727 | M00233 | non-negotiable | false | 10 |
| R02393 | Workflow graph — edges = policy-checked transitions | 3728 | M00233 | non-negotiable | false | 10 |
| R02394 | Workflow graph — state = typed, checkpointed, replayable | 3729 | M00233 | non-negotiable | false | 10 |
| R02395 | Workflow graph — side effects = gated commits | 3730 | M00233 | non-negotiable | false | 10 |
| R02396 | Canonical workflow includes Intake | 3736 | M00234 | non-negotiable | false | 10 |
| R02397 | Canonical workflow includes Classify | 3737 | M00234 | non-negotiable | false | 10 |
| R02398 | Canonical workflow includes Retrieve | 3738 | M00234 | non-negotiable | false | 10 |
| R02399 | Canonical workflow includes DraftPlan | 3739 | M00234 | non-negotiable | false | 10 |
| R02400 | Canonical workflow includes PolicyCheck | 3740 | M00234 | non-negotiable | false | 10 |
| R02401 | Canonical workflow includes OracleReview | 3741 | M00234 | non-negotiable | false | 10 |
| R02402 | Canonical workflow includes ToolIntent | 3742 | M00234 | non-negotiable | false | 10 |
| R02403 | Canonical workflow includes HumanGate? | 3743 | M00234 | non-negotiable | true | 10 |
| R02404 | Canonical workflow includes ExecuteSandbox | 3744 | M00234 | non-negotiable | false | 10 |
| R02405 | Canonical workflow includes ValidateResult | 3745 | M00234 | non-negotiable | false | 10 |
| R02406 | Canonical workflow includes Commit | 3746 | M00234 | non-negotiable | false | 10 |
| R02407 | Canonical workflow includes SummarizeMemory | 3747 | M00234 | non-negotiable | false | 10 |
| R02408 | Each node has input schema | 3753 | M00235 | non-negotiable | false | 10 |
| R02409 | Each node has output schema | 3754 | M00235 | non-negotiable | false | 10 |
| R02410 | Each node has allowed tools | 3755 | M00235 | non-negotiable | false | 10 |
| R02411 | Each node has risk level | 3756 | M00235 | non-negotiable | false | 10 |
| R02412 | Each node has budget | 3757 | M00235 | non-negotiable | false | 10 |
| R02413 | Each node has model route | 3758 | M00235 | non-negotiable | false | 10 |
| R02414 | Each node has cache policy | 3759 | M00235 | non-negotiable | false | 10 |
| R02415 | Each node has checkpoint policy | 3760 | M00235 | non-negotiable | false | 10 |
| R02416 | Per-node contract becomes executable law | 3763 | M00235 | non-negotiable | false | 10 |
| R02417 | State is explicit (typed Rust struct) | 3767 | M00236 | non-negotiable | false | 10 |
| R02418 | `AgentState` carries task_id | 3771 | M00236 | non-negotiable | false | 10 |
| R02419 | `AgentState` carries branch_id | 3772 | M00236 | non-negotiable | false | 10 |
| R02420 | `AgentState` carries control u64 | 3773 | M00236 | non-negotiable | false | 10 |
| R02421 | `AgentState` carries risk u8 | 3774 | M00236 | non-negotiable | false | 10 |
| R02422 | `AgentState` carries budget u32 | 3775 | M00236 | non-negotiable | false | 10 |
| R02423 | `AgentState` carries memory_refs Vec<u64> | 3776 | M00236 | non-negotiable | false | 10 |
| R02424 | `AgentState` carries kv_refs Vec<u64> | 3777 | M00236 | non-negotiable | false | 10 |
| R02425 | `AgentState` carries tool_intents Vec<ToolIntent> | 3778 | M00236 | non-negotiable | false | 10 |
| R02426 | `AgentState` carries artifacts Vec<ArtifactRef> | 3779 | M00236 | non-negotiable | false | 10 |
| R02427 | `AgentState` carries trace_id TraceId | 3780 | M00236 | non-negotiable | false | 10 |
| R02428 | Model output enters the system only through typed structures | 3784 | M00237 | non-negotiable | false | 10 |
| R02429 | Typed envelope — PlanProposal | 3788 | M00237 | non-negotiable | false | 10 |
| R02430 | Typed envelope — ToolIntent | 3789 | M00237 | non-negotiable | false | 10 |
| R02431 | Typed envelope — PatchProposal | 3790 | M00237 | non-negotiable | false | 10 |
| R02432 | Typed envelope — MemoryWrite | 3791 | M00237 | non-negotiable | false | 10 |
| R02433 | Typed envelope — VerificationResult | 3792 | M00237 | non-negotiable | false | 10 |
| R02434 | Typed envelope — FinalAnswer | 3793 | M00237 | non-negotiable | false | 10 |
| R02435 | This is how you stop the model from smuggling authority through prose | 3795 | M00237 | non-negotiable | false | 10 |
| R02436 | Node class 1 — Deterministic Node (pure CPU logic, parsers, masks, policy, validation) | 3802–3804 | M00238 | non-negotiable | false | 10 |
| R02437 | Node class 2 — Scout Node (3090 model, cheap exploration/proposals) | 3805–3807 | M00239 | non-negotiable | false | 10 |
| R02438 | Node class 3 — Oracle Node (Blackwell model, expensive synthesis/verification) | 3808–3810 | M00240 | non-negotiable | false | 10 |
| R02439 | Node class 4 — Tool Node (shell/browser/file/API, always gated) | 3811–3813 | M00241 | non-negotiable | false | 10 |
| R02440 | Node class 5 — Human Gate Node (explicit pause/resume with full context) | 3814–3816 | M00242 | non-negotiable | false | 10 |
| R02441 | Every node returns a typed result plus metrics | 3818 | E0130 | non-negotiable | false | 10 |
| R02442 | Human-in-the-loop is NOT a dumb approve button | 3822 | E0131 | non-negotiable | false | 10 |
| R02443 | Human gate shows what the agent wants to do | 3827 | M00243 | non-negotiable | true | 10 |
| R02444 | Human gate shows why it wants to do it | 3828 | M00243 | non-negotiable | true | 10 |
| R02445 | Human gate shows what files/tools/network are involved | 3829 | M00243 | non-negotiable | true | 10 |
| R02446 | Human gate shows risk bits | 3830 | M00243 | non-negotiable | true | 10 |
| R02447 | Human gate shows expected side effects | 3831 | M00243 | non-negotiable | true | 10 |
| R02448 | Human gate shows rollback plan | 3832 | M00243 | non-negotiable | true | 10 |
| R02449 | Human gate shows diff or command preview | 3833 | M00243 | non-negotiable | true | 10 |
| R02450 | Human gate shows model confidence | 3834 | M00243 | non-negotiable | true | 10 |
| R02451 | Human gate shows policy reason | 3835 | M00243 | non-negotiable | true | 10 |
| R02452 | Human-gate action — approve | 3841 | M00244 | non-negotiable | true | 10 |
| R02453 | Human-gate action — deny | 3842 | M00244 | non-negotiable | true | 10 |
| R02454 | Human-gate action — edit | 3843 | M00244 | non-negotiable | true | 10 |
| R02455 | Human-gate action — route to sandbox | 3844 | M00244 | non-negotiable | true | 10 |
| R02456 | Human-gate action — ask oracle to review | 3845 | M00244 | non-negotiable | true | 10 |
| R02457 | Human-gate action — lower/raise permission | 3846 | M00244 | non-negotiable | true | 10 |
| R02458 | Human gate maps perfectly to durable execution — pause, persist, resume | 3849 | M00242 | non-negotiable | false | 10 |
| R02459 | Optimize the program against metrics, not vibes | 3853 | E0132 | non-negotiable | false | 10 |
| R02460 | Optimization metric — task success | 3859 | M00245 | non-negotiable | false | 10 |
| R02461 | Optimization metric — tool rejection rate | 3860 | M00245 | non-negotiable | false | 10 |
| R02462 | Optimization metric — oracle calls per task | 3861 | M00245 | non-negotiable | false | 10 |
| R02463 | Optimization metric — latency | 3862 | M00245 | non-negotiable | false | 10 |
| R02464 | Optimization metric — user interventions | 3863 | M00245 | non-negotiable | false | 10 |
| R02465 | Optimization metric — test pass rate | 3864 | M00245 | non-negotiable | false | 10 |
| R02466 | Optimization metric — rollback rate | 3865 | M00245 | non-negotiable | false | 10 |
| R02467 | Optimization metric — branch acceptance rate | 3866 | M00245 | non-negotiable | false | 10 |
| R02468 | Optimization metric — KV reuse | 3867 | M00245 | non-negotiable | false | 10 |
| R02469 | Optimization metric — memory usefulness | 3868 | M00245 | non-negotiable | false | 10 |
| R02470 | System tunes which scout model to use | 3873 | M00246 | non-negotiable | true | 10 |
| R02471 | System tunes speculation depth | 3874 | M00246 | non-negotiable | true | 10 |
| R02472 | System tunes retrieval thresholds | 3875 | M00246 | non-negotiable | true | 10 |
| R02473 | System tunes prompt templates | 3876 | M00246 | non-negotiable | true | 10 |
| R02474 | System tunes grammar strictness | 3877 | M00246 | non-negotiable | true | 10 |
| R02475 | System tunes oracle review thresholds | 3878 | M00246 | non-negotiable | true | 10 |
| R02476 | System tunes tool approval policies | 3879 | M00246 | non-negotiable | true | 10 |
| R02477 | System tunes cache admission | 3880 | M00246 | non-negotiable | true | 10 |
| R02478 | Clean version of self-improvement — runtime optimization first, fine-tuning later | 3886–3888 | E0132 | non-negotiable | false | 10 |
| R02479 | Agent DSL — `workflow:` keyword names the workflow | 3895 | M00247 | non-negotiable | false | 10 |
| R02480 | Agent DSL — `nodes:` block lists per-node configs | 3896 | M00247 | non-negotiable | false | 10 |
| R02481 | Agent DSL node carries `type` field (deterministic / memory / scout / oracle / tool) | 3898 | M00247 | non-negotiable | false | 10 |
| R02482 | Agent DSL node carries `policy` field | 3901 | M00247 | non-negotiable | true | 10 |
| R02483 | Agent DSL node carries `gpu` field (rtx3090 / blackwell) | 3904 | M00247 | non-negotiable | true | 10 |
| R02484 | Agent DSL node carries `output` field (typed envelope name) | 3905 | M00247 | non-negotiable | false | 10 |
| R02485 | Agent DSL node carries `requires` field (precondition list) | 3912 | M00247 | non-negotiable | true | 10 |
| R02486 | Agent DSL `requires` may include `workspace_write` | 3913 | M00247 | non-negotiable | true | 10 |
| R02487 | Agent DSL `requires` may include `policy_ok` | 3914 | M00247 | non-negotiable | true | 10 |
| R02488 | Agent DSL `requires` may include `diff_valid` | 3915 | M00247 | non-negotiable | true | 10 |
| R02489 | Agent DSL lets you define agent programs without burying everything in prompts | 3918 | M00247 | non-negotiable | false | 10 |
| R02490 | Graph runtime itself is vectorized | 3922 | M00248 | non-negotiable | false | 10 |
| R02491 | Many-branch SoA — `node_state[branch]` | 3927 | M00248 | non-negotiable | false | 10 |
| R02492 | Many-branch SoA — `risk[branch]` | 3928 | M00248 | non-negotiable | false | 10 |
| R02493 | Many-branch SoA — `budget[branch]` | 3929 | M00248 | non-negotiable | false | 10 |
| R02494 | Many-branch SoA — `route[branch]` | 3930 | M00248 | non-negotiable | false | 10 |
| R02495 | Many-branch SoA — `permission[branch]` | 3931 | M00248 | non-negotiable | false | 10 |
| R02496 | CPU batches graph transitions — which can enter tool node | 3937 | M00248 | non-negotiable | false | 10 |
| R02497 | CPU batches graph transitions — which need human gate | 3938 | M00248 | non-negotiable | false | 10 |
| R02498 | CPU batches graph transitions — which are ready for oracle | 3939 | M00248 | non-negotiable | false | 10 |
| R02499 | CPU batches graph transitions — which failed schema | 3940 | M00248 | non-negotiable | false | 10 |
| R02500 | CPU batches graph transitions — which share retrieval context | 3941 | M00248 | non-negotiable | false | 10 |
| R02501 | Do not let ReAct-style traces become authority | 3948 | E0135 | non-negotiable | false | 10 |
| R02502 | ReAct useful as model behavior pattern (reason → act → observe) | 3950–3953 | E0135 | non-negotiable | false | 10 |
| R02503 | Runtime invariant — thought is not action | 3959 | E0135 | non-negotiable | false | 10 |
| R02504 | Runtime invariant — action proposal is not execution | 3960 | E0135 | non-negotiable | false | 10 |
| R02505 | Runtime invariant — observation is not trusted until validated | 3961 | E0135 | non-negotiable | false | 10 |
| R02506 | Runtime invariant — commit is deterministic | 3962 | E0135 | non-negotiable | false | 10 |
| R02507 | Get benefits of agentic reasoning without surrendering control to the model | 3965 | E0135 | non-negotiable | false | 10 |
| R02508 | Plane 1 — Inference Plane (probabilistic workers) | 3972–3973 | M00249 | non-negotiable | false | 10 |
| R02509 | Plane 2 — Control Plane (deterministic branch graph scheduler) | 3975–3976 | M00249 | non-negotiable | false | 10 |
| R02510 | Plane 3 — Memory Plane (typed memories, KV refs, indexes) | 3978–3979 | M00249 | non-negotiable | false | 10 |
| R02511 | Plane 4 — Storage Plane (replayable checkpoints and artifacts) | 3981–3982 | M00249 | non-negotiable | false | 10 |
| R02512 | Plane 5 — Tool Plane (side-effect engines behind gates) | 3984–3985 | M00249 | non-negotiable | false | 10 |
| R02513 | Plane 6 — Observability Plane (metrics and traces feeding policy) | 3987–3988 | M00249 | non-negotiable | false | 10 |
| R02514 | Plane 7 — Programming Plane (typed durable workflow graphs) | 3990–3991 | M00249 | non-negotiable | false | 10 |
| R02515 | Evolution path — Prompt chain → Agent loop → Durable graph → Deterministic AI OS | 3996–3998 | E0135 | non-negotiable | false | 10 |
| R02516 | Workstation is strong enough to run the whole thing locally | 4000 | E0135 | non-negotiable | false | 10 |
| R02517 | Not just faster inference — a programmable, replayable, measurable, permissioned cognition runtime | 4002 | E0135 | non-negotiable | false | 10 |
| R02518 | Programming-plane backend operator-overrideable (rust_native / langgraph / dspy) | 3712–3715 | F01191 | non-negotiable | true | 10 |
| R02519 | Env var `SOVEREIGN_PROGRAMMING_PLANE_BACKEND` | 3712–3715 | F01193 | non-negotiable | true | 10 |
| R02520 | CLI `--programming-plane-backend <name>` | 3712–3715 | F01194 | non-negotiable | true | 10 |
| R02521 | Workflow loader reads DSL from `workflows/<name>.yaml` | 3892–3916 | F01195 | non-negotiable | false | 10 |
| R02522 | API `POST /v1/workflows/{name}/start` | 3892–3918 | F01268 | non-negotiable | true | 10 |
| R02523 | API `POST /v1/workflows/{instance_id}/resume` | 3849 | F01269 | non-negotiable | true | 10 |
| R02524 | API `GET /v1/workflows/{instance_id}/state` | 3729 | F01270 | non-negotiable | true | 10 |
| R02525 | API `GET /v1/workflows/{instance_id}/trace` | 3729 | F01271 | non-negotiable | true | 10 |
| R02526 | Dashboard — workflow DAG visualizer (live nodes with state) | 3725–3748 | F01272 | non-negotiable | true | 10 |
| R02527 | Dashboard — agent-state inspector (per-branch typed state with all 10 fields) | 3769–3781 | F01273 | non-negotiable | true | 10 |
| R02528 | Dashboard — human-gate queue (pending approvals with full context) | 3820–3849 | F01274 | non-negotiable | true | 10 |
| R02529 | Test — workflow loader rejects YAML missing `nodes:` block | 3894–3916 | M00247 | non-negotiable | false | 10 |
| R02530 | Test — workflow loader rejects unknown node type | 3898 | M00247 | non-negotiable | false | 10 |
| R02531 | Test — `AgentState` round-trip preserves all 10 fields | 3769–3781 | M00236 | non-negotiable | false | 10 |
| R02532 | Test — each typed envelope round-trip preserves declared fields | 3787–3793 | M00237 | non-negotiable | false | 10 |
| R02533 | Test — Deterministic Node refuses to call model | 3802–3804 | M00238 | non-negotiable | false | 10 |
| R02534 | Test — Scout Node refuses Blackwell route | 3805–3807 | M00239 | non-negotiable | false | 10 |
| R02535 | Test — Oracle Node refuses 3090 route | 3808–3810 | M00240 | non-negotiable | false | 10 |
| R02536 | Test — Tool Node refuses ungated tool call | 3811–3813 | M00241 | non-negotiable | false | 10 |
| R02537 | Test — Human Gate persists state on pause and resumes on action | 3814–3816, 3849 | M00242 | non-negotiable | false | 10 |
| R02538 | Test — each human-gate display field present when shown | 3826–3836 | M00243 | non-negotiable | false | 10 |
| R02539 | Test — each human-gate action returns expected state transition | 3840–3847 | M00244 | non-negotiable | false | 10 |
| R02540 | Test — optimization metric set exposed via Prometheus | 3858–3868 | M00245 | non-negotiable | false | 10 |
| R02541 | Test — tuning surface knobs operator-settable and respected by runtime | 3872–3881 | M00246 | non-negotiable | true | 10 |
| R02542 | Test — Agent DSL example `code_patch` workflow loads + dry-runs end-to-end | 3894–3916 | M00247 | non-negotiable | false | 10 |
| R02543 | Test — Vectorized graph scheduler batches transitions correctly across 8+ branches | 3925–3942 | M00248 | non-negotiable | false | 10 |
| R02544 | Test — runtime rejects model "action" that bypasses ToolIntent envelope | 3959–3963 | M00237 | non-negotiable | false | 10 |
| R02545 | Test — runtime rejects model "commit" that bypasses Commit node | 3962, 3746 | M00234 | non-negotiable | false | 10 |
| R02546 | Test — 7-plane system rollup enumerates all 7 planes by name | 3970–3992 | M00249 | non-negotiable | false | 10 |
| R02547 | Composite — Programming Plane integrates with Inference + Control + Memory + Storage + Tool + Observability planes | 3970–3992 | M00249 | non-negotiable | false | 10 |
| R02548 | Composite — Agent programming model integrates with M013 observability metrics (per-node + per-optimization-metric) | 3858–3868 | M00245 | non-negotiable | false | 10 |
| R02549 | Composite — Agent programming model integrates with M014 capability tokens (every Tool Node call carries a capability word) | 3811–3813 | M00241 | non-negotiable | false | 10 |
| R02550 | Composite — Workflow DAG visualizer is one of the operator-stated 20+ dashboards | 3725–3748 | F01272 | non-negotiable | true | 10 |

— End of M015 milestone file.
