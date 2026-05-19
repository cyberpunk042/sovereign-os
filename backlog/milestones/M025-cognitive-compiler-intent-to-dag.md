# M025 — Cognitive Compiler — intent to DAG

> Parent: `backlog/milestones/INDEX.md` row M025 (dump 7000–7378).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 7000–7378.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0228–E0237)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0228 | Compilation is the next layer — concrete realization of SMART/ADAPTIVE/OPTIONS/PROFILES/FLEXIBILITY/CHOICES/PROGRAMMING | 7015–7017 |
| E0229 | Research substrate — LLMCompiler (DAG + parallel + 3.7x latency / 6.7x cost saving) + BFCL V4 + SPIN + Future-based async function calling | 7019–7024 |
| E0230 | Compilation architecture — `AI intent → compiler → executable cognitive DAG → scheduler → experts/tools → observations → adaptive recompile` | 7026–7030 |
| E0231 | The Compiler Layer — 7-input / 5-output typed compile contract + YAML DAG example | 7032–7090 |
| E0232 | Options As Search Space — profiles constrain the compiler (Fast / Careful / Exploratory / Private / Autonomous) | 7094–7130 |
| E0233 | Futures Are Huge — symbolic futures + async function calling + placeholder reasoning | 7132–7166 |
| E0234 | AVX-512 Scheduler — DAG-aware vector scheduler with 8 ready-node axes + 6 dense queues | 7168–7198 |
| E0235 | Tool Calling Quality — BFCL V4 failure taxonomy + per-model tool-use profile (8-axis profile YAML) | 7200–7230 |
| E0236 | Programming The Station — user-facing `station.run()` API + adaptive recompile (5 named recompile triggers) | 7232–7282 |
| E0237 | The Compiler Pipeline — 10-stage compiler + intelligence-by-composition + Cognitive Compiler as new architecture component + closing rule | 7284–7376 |

## Modules (M00406–M00422)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00406 | LLMCompiler substrate — DAG of function calls + dispatch ready tasks + execute parallel | 7021 | E0229 |
| M00407 | BFCL V4 substrate — multi-turn + holistic agentic evaluation | 7022 | E0229 |
| M00408 | SPIN substrate — validated DAG planning + prefix-based execution control | 7023 | E0229 |
| M00409 | Async function calling substrate — reason over symbolic futures + tool calls run without blocking decoding | 7024 | E0229 |
| M00410 | Compiler 7-input contract — user goal / policies / available tools / model registry / memory state / hardware telemetry / risk profile | 7039–7046 | E0231 |
| M00411 | Compiler 5-output contract — typed workflow DAG / capability plan / model routing plan / cache plan / eval-verification plan | 7048–7053 | E0231 |
| M00412 | DAG node schema — id / type / depends_on / parallel / output (typed) / model_role / sandbox | 7061–7090 | E0231 |
| M00413 | 5-profile catalog — Fast / Careful / Exploratory / Private / Autonomous (each constrains compiler search space) | 7099–7126 | E0232 |
| M00414 | Symbolic futures — `f1 = read(package.json)`, `f2 = read(tsconfig.json)`, `f3 = grep("TODO")`, `f4 = list_tests()` | 7149–7156 | E0233 |
| M00415 | Placeholder reasoning — "When f1 resolves, if framework == vite, inspect vite config" | 7160–7163 | E0233 |
| M00416 | DAG-aware vector scheduler — 8 ready-node axes (dependency_satisfied / capability_allowed / budget_ok / risk_ok / sandbox_available / model_available / cache_affinity / priority) | 7174–7183 | E0234 |
| M00417 | Dense ready queues — ready_model_oracle / ready_model_scout / ready_tool_read / ready_tool_sandbox / ready_repl / ready_human_gate | 7189–7196 | E0234 |
| M00418 | BFCL V4 8-failure taxonomy — wrong function / wrong argument / wrong order / lost context / ignoring prior tool output / format drift / unnecessary tool call / missing tool call | 7205–7213 | E0235 |
| M00419 | Per-model tool-use profile YAML — single_call / multi_turn / parallel_call / json_strictness / argument_precision / needs_schema_examples | 7217–7226 | E0235 |
| M00420 | Adaptive recompile triggers — test failed / missing file / tool denied / oracle disagreement / memory conflict | 7271–7276 | E0236 |
| M00421 | 10-stage compiler pipeline — Intent Parse / Context Build / Plan Synthesis / Plan Validation / Plan Optimization / Execution / Observation / Recompile / Commit / Learn | 7287–7316 | E0237 |
| M00422 | Cognitive Compiler architecture component — sits above runtime; pipeline: `User intent → Cognitive Compiler → Frame/DAG Runtime → AVX-512 Scheduler → Experts/Tools → Replay/Evals → Compiler optimization` | 7349–7357 | E0237 |

## Features (F02041–F02125)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F02041 | Toggle compiler backend (native / llmcompiler-bridge / spin-bridge) | 7019–7023 | E0229 | mode | true |
| F02042 | Profile knob — `compiler_backend = native \| llmcompiler \| spin` | 7019–7023 | E0229 | profile | true |
| F02043 | Env var `SOVEREIGN_COMPILER_BACKEND` | 7019–7023 | E0229 | env_var | true |
| F02044 | CLI `--compiler-backend <name>` | 7019–7023 | E0229 | cli_verb | true |
| F02045 | LLMCompiler — DAG of function calls + parallel dispatch (3.7x latency speedup target) | 7021 | M00406 | composite | true |
| F02046 | LLMCompiler — 6.7x cost savings target | 7021 | M00406 | composite | true |
| F02047 | LLMCompiler — accuracy gains vs ReAct-style sequential tool use | 7021 | M00406 | composite | true |
| F02048 | BFCL V4 multi-turn evaluation | 7022 | M00407 | composite | true |
| F02049 | BFCL V4 holistic agentic evaluation | 7022 | M00407 | composite | true |
| F02050 | SPIN validated-DAG planning | 7023 | M00408 | composite | true |
| F02051 | SPIN prefix-based execution control | 7023 | M00408 | composite | true |
| F02052 | Async function calling — symbolic futures | 7024 | M00409 | composite | false |
| F02053 | Async function calling — non-blocking decoding | 7024 | M00409 | composite | false |
| F02054 | Compiler input — user goal | 7040 | M00410 | data_model | false |
| F02055 | Compiler input — policies | 7041 | M00410 | data_model | false |
| F02056 | Compiler input — available tools | 7042 | M00410 | data_model | false |
| F02057 | Compiler input — model registry | 7043 | M00410 | data_model | false |
| F02058 | Compiler input — memory state | 7044 | M00410 | data_model | false |
| F02059 | Compiler input — hardware telemetry | 7045 | M00410 | data_model | false |
| F02060 | Compiler input — risk profile | 7046 | M00410 | data_model | false |
| F02061 | Compiler output — typed workflow DAG | 7049 | M00411 | data_model | false |
| F02062 | Compiler output — capability plan | 7050 | M00411 | data_model | false |
| F02063 | Compiler output — model routing plan | 7051 | M00411 | data_model | false |
| F02064 | Compiler output — cache plan | 7052 | M00411 | data_model | false |
| F02065 | Compiler output — eval/verification plan | 7053 | M00411 | data_model | false |
| F02066 | A plan is an executable object, not prose | 7058 | E0231 | composite | false |
| F02067 | DAG node field — `id` | 7062 | M00412 | data_model | false |
| F02068 | DAG node field — `type` (memory.retrieve / tool.read_files / model.generate / model.verify / tool.execute / ...) | 7063 | M00412 | data_model | false |
| F02069 | DAG node field — `depends_on` (list of node ids) | 7064 | M00412 | data_model | false |
| F02070 | DAG node field — `parallel` (bool, default false) | 7070 | M00412 | data_model | true |
| F02071 | DAG node field — `output` (typed; ContextSet / FileFacts / PatchProposal / VerificationResult / TestResult / ...) | 7065 | M00412 | data_model | false |
| F02072 | DAG node field — `model_role` (scout / oracle / perception / ...) | 7075 | M00412 | data_model | true |
| F02073 | DAG node field — `sandbox` (bool, default false) | 7087 | M00412 | data_model | true |
| F02074 | Compiler DAG validation — schema check before run | 7092 | E0231 | composite | false |
| F02075 | Compiler DAG validation — dependency cycle detection | 7092 | E0231 | composite | false |
| F02076 | Compiler DAG validation — capability check (declared capabilities subset-of granted) | 7092 | E0231 | composite | false |
| F02077 | Compiler DAG validation — policy check (per-profile constraints honored) | 7092 | E0231 | composite | false |
| F02078 | Profile — Fast (low branch width / scout-first / oracle only if needed / shallow verification) | 7099–7103 | M00413 | mode | true |
| F02079 | Profile — Careful (oracle-required for final / tests required / wider retrieval / stricter schemas) | 7105–7109 | M00413 | mode | true |
| F02080 | Profile — Exploratory (many branches / debate-tree search / sandbox-first tools / memory writes as draft) | 7111–7115 | M00413 | mode | true |
| F02081 | Profile — Private (no network / local models only / local memory only) | 7117–7120 | M00413 | mode | true |
| F02082 | Profile — Autonomous (durable workflow / tool loop allowed / human gate on high-risk commits) | 7122–7125 | M00413 | mode | true |
| F02083 | Compiler constrained-search — picks inside profile | 7128 | E0232 | composite | false |
| F02084 | Symbolic future — `f1 = read(package.json)` | 7149 | M00414 | data_model | false |
| F02085 | Symbolic future — `f2 = read(tsconfig.json)` | 7150 | M00414 | data_model | false |
| F02086 | Symbolic future — `f3 = grep("TODO")` | 7151 | M00414 | data_model | false |
| F02087 | Symbolic future — `f4 = list_tests()` | 7152 | M00414 | data_model | false |
| F02088 | Placeholder reasoning — `When f1 resolves, if framework == vite, inspect vite config` | 7161–7162 | M00415 | composite | true |
| F02089 | Placeholder reasoning — `When f4 resolves, choose test command` | 7163 | M00415 | composite | true |
| F02090 | DAG scheduler runs independent tools in parallel | 7157 | E0233 | composite | false |
| F02091 | Continue planning while futures resolve | 7154 | E0233 | composite | false |
| F02092 | Vector scheduler axis — `dependency_satisfied` | 7175 | M00416 | data_model | false |
| F02093 | Vector scheduler axis — `capability_allowed` | 7176 | M00416 | data_model | false |
| F02094 | Vector scheduler axis — `budget_ok` | 7177 | M00416 | data_model | false |
| F02095 | Vector scheduler axis — `risk_ok` | 7178 | M00416 | data_model | false |
| F02096 | Vector scheduler axis — `sandbox_available` | 7179 | M00416 | data_model | false |
| F02097 | Vector scheduler axis — `model_available` | 7180 | M00416 | data_model | false |
| F02098 | Vector scheduler axis — `cache_affinity` | 7181 | M00416 | data_model | false |
| F02099 | Vector scheduler axis — `priority` | 7182 | M00416 | data_model | false |
| F02100 | Dense ready queue — `ready_model_oracle` | 7190 | M00417 | data_model | false |
| F02101 | Dense ready queue — `ready_model_scout` | 7191 | M00417 | data_model | false |
| F02102 | Dense ready queue — `ready_tool_read` | 7192 | M00417 | data_model | false |
| F02103 | Dense ready queue — `ready_tool_sandbox` | 7193 | M00417 | data_model | false |
| F02104 | Dense ready queue — `ready_repl` | 7194 | M00417 | data_model | false |
| F02105 | Dense ready queue — `ready_human_gate` | 7195 | M00417 | data_model | false |
| F02106 | BFCL failure — wrong function | 7206 | M00418 | composite | false |
| F02107 | BFCL failure — wrong argument | 7207 | M00418 | composite | false |
| F02108 | BFCL failure — wrong order | 7208 | M00418 | composite | false |
| F02109 | BFCL failure — lost context over turns | 7209 | M00418 | composite | false |
| F02110 | BFCL failure — ignoring prior tool output | 7210 | M00418 | composite | false |
| F02111 | BFCL failure — format drift | 7211 | M00418 | composite | false |
| F02112 | BFCL failure — unnecessary tool call | 7212 | M00418 | composite | false |
| F02113 | BFCL failure — missing tool call | 7213 | M00418 | composite | false |
| F02114 | Per-model tool-use profile — `single_call` (level: high / medium / low / unknown) | 7220 | M00419 | data_model | false |
| F02115 | Per-model tool-use profile — `multi_turn` | 7221 | M00419 | data_model | false |
| F02116 | Per-model tool-use profile — `parallel_call` | 7222 | M00419 | data_model | false |
| F02117 | Per-model tool-use profile — `json_strictness` | 7223 | M00419 | data_model | false |
| F02118 | Per-model tool-use profile — `argument_precision` | 7224 | M00419 | data_model | false |
| F02119 | Per-model tool-use profile — `needs_schema_examples` (bool) | 7225 | M00419 | data_model | false |
| F02120 | Recompile trigger — test failed → recompile repair loop | 7272 | M00420 | composite | false |
| F02121 | Recompile trigger — missing file → recompile retrieval | 7273 | M00420 | composite | false |
| F02122 | Recompile trigger — tool denied → recompile offline path | 7274 | M00420 | composite | false |
| F02123 | Recompile trigger — oracle disagreement → recompile debate | 7275 | M00420 | composite | false |
| F02124 | Recompile trigger — memory conflict → recompile verification | 7276 | M00420 | composite | false |
| F02125 | Composite — `station.run(goal, profile, intelligence, constraints)` user-facing API + 10-stage compiler pipeline + Cognitive Compiler architecture component | 7232–7376 | M00422 | composite | false |

## Requirements (R04081–R04250)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R04081 | Compilation is the next layer — SMART/ADAPTIVE/OPTIONS/PROFILES/FLEXIBILITY/CHOICES/PROGRAMMING become concrete | 7015–7017 | E0228 | non-negotiable | false | 10 |
| R04082 | LLMCompiler creates a DAG of function calls, dispatches ready tasks, and executes in parallel | 7021 | M00406 | non-negotiable | false | 10 |
| R04083 | LLMCompiler reports latency speedups up to 3.7x vs ReAct-sequential | 7021 | M00406 | non-negotiable | false | 10 |
| R04084 | LLMCompiler reports cost savings up to 6.7x vs ReAct-sequential | 7021 | M00406 | non-negotiable | false | 10 |
| R04085 | LLMCompiler reports accuracy gains vs ReAct-sequential | 7021 | M00406 | non-negotiable | false | 10 |
| R04086 | BFCL V4 evaluates tool calling as agentic behavior, not just one-shot function selection | 7022 | M00407 | non-negotiable | false | 10 |
| R04087 | BFCL V4 explicitly covers multi-turn evaluation | 7022 | M00407 | non-negotiable | false | 10 |
| R04088 | BFCL V4 explicitly covers holistic agentic evaluation | 7022 | M00407 | non-negotiable | false | 10 |
| R04089 | SPIN focuses on validated DAG planning | 7023 | M00408 | non-negotiable | false | 10 |
| R04090 | SPIN focuses on prefix-based execution control | 7023 | M00408 | non-negotiable | false | 10 |
| R04091 | SPIN avoids invalid or overlong workflows | 7023 | M00408 | non-negotiable | false | 10 |
| R04092 | Async function calling — models reason over symbolic futures | 7024 | M00409 | non-negotiable | false | 10 |
| R04093 | Async function calling — tool calls run without blocking decoding | 7024 | M00409 | non-negotiable | false | 10 |
| R04094 | Architecture flow — AI intent → compiler → executable cognitive DAG → scheduler → experts/tools → observations → adaptive recompile | 7028–7030 | E0230 | non-negotiable | false | 10 |
| R04095 | Do NOT let the model "just agent loop" — compile its intent | 7034–7036 | E0231 | non-negotiable | false | 10 |
| R04096 | Compiler input — user goal | 7040 | F02054 | non-negotiable | false | 10 |
| R04097 | Compiler input — policies | 7041 | F02055 | non-negotiable | false | 10 |
| R04098 | Compiler input — available tools | 7042 | F02056 | non-negotiable | false | 10 |
| R04099 | Compiler input — model registry | 7043 | F02057 | non-negotiable | false | 10 |
| R04100 | Compiler input — memory state | 7044 | F02058 | non-negotiable | false | 10 |
| R04101 | Compiler input — hardware telemetry | 7045 | F02059 | non-negotiable | false | 10 |
| R04102 | Compiler input — risk profile | 7046 | F02060 | non-negotiable | false | 10 |
| R04103 | Compiler output — typed workflow DAG | 7049 | F02061 | non-negotiable | false | 10 |
| R04104 | Compiler output — capability plan | 7050 | F02062 | non-negotiable | false | 10 |
| R04105 | Compiler output — model routing plan | 7051 | F02063 | non-negotiable | false | 10 |
| R04106 | Compiler output — cache plan | 7052 | F02064 | non-negotiable | false | 10 |
| R04107 | Compiler output — eval/verification plan | 7053 | F02065 | non-negotiable | false | 10 |
| R04108 | This is programming | 7056 | E0231 | non-negotiable | false | 10 |
| R04109 | A plan is not prose — it is an executable object | 7058 | E0231 | non-negotiable | false | 10 |
| R04110 | DAG node carries `id` | 7062 | F02067 | non-negotiable | false | 10 |
| R04111 | DAG node carries `type` (memory.retrieve / tool.read_files / model.generate / model.verify / tool.execute / ...) | 7063 | F02068 | non-negotiable | false | 10 |
| R04112 | DAG node carries `depends_on` (list of node ids) | 7064 | F02069 | non-negotiable | false | 10 |
| R04113 | DAG node carries `parallel` (bool, default false) | 7070 | F02070 | non-negotiable | true | 10 |
| R04114 | DAG node carries `output` (typed; ContextSet / FileFacts / PatchProposal / VerificationResult / TestResult) | 7065 | F02071 | non-negotiable | false | 10 |
| R04115 | DAG node carries `model_role` (scout / oracle / perception / ...) | 7075 | F02072 | non-negotiable | true | 10 |
| R04116 | DAG node carries `sandbox` (bool, default false) | 7087 | F02073 | non-negotiable | true | 10 |
| R04117 | DAG schema validation runs before execution | 7092 | F02074 | non-negotiable | false | 10 |
| R04118 | DAG dependency cycle detection runs before execution | 7092 | F02075 | non-negotiable | false | 10 |
| R04119 | DAG capability check (declared subset-of granted) runs before execution | 7092 | F02076 | non-negotiable | false | 10 |
| R04120 | DAG policy check (per-profile constraints honored) runs before execution | 7092 | F02077 | non-negotiable | false | 10 |
| R04121 | Profiles are NOT fixed commands — they constrain the compiler | 7096 | E0232 | non-negotiable | false | 10 |
| R04122 | Profile — Fast (low branch width / scout-first / oracle-only-if-needed / shallow verification) | 7099–7103 | F02078 | non-negotiable | true | 10 |
| R04123 | Profile — Careful (oracle-required for final / tests required / wider retrieval / stricter schemas) | 7105–7109 | F02079 | non-negotiable | true | 10 |
| R04124 | Profile — Exploratory (many branches / debate-tree search / sandbox-first tools / memory writes as draft) | 7111–7115 | F02080 | non-negotiable | true | 10 |
| R04125 | Profile — Private (no network / local models only / local memory only) | 7117–7120 | F02081 | non-negotiable | true | 10 |
| R04126 | Profile — Autonomous (durable workflow / tool loop allowed / human gate on high-risk commits) | 7122–7125 | F02082 | non-negotiable | true | 10 |
| R04127 | Compiler chooses inside the profile | 7128 | F02083 | non-negotiable | false | 10 |
| R04128 | User choice stays simple, but system behavior remains adaptive | 7130 | E0232 | non-negotiable | false | 10 |
| R04129 | Async function calling is an important idea | 7134 | E0233 | non-negotiable | false | 10 |
| R04130 | Symbolic futures replace serial call/wait/think/call/wait | 7138–7143 | M00414 | non-negotiable | false | 10 |
| R04131 | Symbolic future — `f1 = read(package.json)` | 7149 | F02084 | non-negotiable | false | 10 |
| R04132 | Symbolic future — `f2 = read(tsconfig.json)` | 7150 | F02085 | non-negotiable | false | 10 |
| R04133 | Symbolic future — `f3 = grep("TODO")` | 7151 | F02086 | non-negotiable | false | 10 |
| R04134 | Symbolic future — `f4 = list_tests()` | 7152 | F02087 | non-negotiable | false | 10 |
| R04135 | Continue planning while f1..f4 resolve | 7154 | E0233 | non-negotiable | false | 10 |
| R04136 | DAG scheduler runs independent tools in parallel | 7157 | E0233 | non-negotiable | false | 10 |
| R04137 | Model reasons over placeholders | 7159 | M00415 | non-negotiable | false | 10 |
| R04138 | Placeholder example — "When f1 resolves, if framework == vite, inspect vite config" | 7161–7162 | F02088 | non-negotiable | true | 10 |
| R04139 | Placeholder example — "When f4 resolves, choose test command" | 7163 | F02089 | non-negotiable | true | 10 |
| R04140 | CPU/runtime should outperform naive agents massively at futures+placeholder reasoning | 7166 | E0233 | non-negotiable | false | 10 |
| R04141 | DAG gives many ready nodes | 7170 | M00416 | non-negotiable | false | 10 |
| R04142 | CPU vector scheduler axis — `dependency_satisfied` | 7175 | F02092 | non-negotiable | false | 10 |
| R04143 | CPU vector scheduler axis — `capability_allowed` | 7176 | F02093 | non-negotiable | false | 10 |
| R04144 | CPU vector scheduler axis — `budget_ok` | 7177 | F02094 | non-negotiable | false | 10 |
| R04145 | CPU vector scheduler axis — `risk_ok` | 7178 | F02095 | non-negotiable | false | 10 |
| R04146 | CPU vector scheduler axis — `sandbox_available` | 7179 | F02096 | non-negotiable | false | 10 |
| R04147 | CPU vector scheduler axis — `model_available` | 7180 | F02097 | non-negotiable | false | 10 |
| R04148 | CPU vector scheduler axis — `cache_affinity` | 7181 | F02098 | non-negotiable | false | 10 |
| R04149 | CPU vector scheduler axis — `priority` | 7182 | F02099 | non-negotiable | false | 10 |
| R04150 | CPU vector scheduler evaluates many nodes at once | 7185 | M00416 | non-negotiable | false | 10 |
| R04151 | Ready queue — `ready_model_oracle` | 7190 | F02100 | non-negotiable | false | 10 |
| R04152 | Ready queue — `ready_model_scout` | 7191 | F02101 | non-negotiable | false | 10 |
| R04153 | Ready queue — `ready_tool_read` | 7192 | F02102 | non-negotiable | false | 10 |
| R04154 | Ready queue — `ready_tool_sandbox` | 7193 | F02103 | non-negotiable | false | 10 |
| R04155 | Ready queue — `ready_repl` | 7194 | F02104 | non-negotiable | false | 10 |
| R04156 | Ready queue — `ready_human_gate` | 7195 | F02105 | non-negotiable | false | 10 |
| R04157 | This is system-level MoE plus workflow compilation | 7198 | E0234 | non-negotiable | false | 10 |
| R04158 | BFCL V4 matters because tool calling fails in ways ordinary benchmarks miss | 7202 | M00418 | non-negotiable | false | 10 |
| R04159 | BFCL failure — wrong function | 7206 | F02106 | non-negotiable | false | 10 |
| R04160 | BFCL failure — wrong argument | 7207 | F02107 | non-negotiable | false | 10 |
| R04161 | BFCL failure — wrong order | 7208 | F02108 | non-negotiable | false | 10 |
| R04162 | BFCL failure — lost context over turns | 7209 | F02109 | non-negotiable | false | 10 |
| R04163 | BFCL failure — ignoring prior tool output | 7210 | F02110 | non-negotiable | false | 10 |
| R04164 | BFCL failure — format drift | 7211 | F02111 | non-negotiable | false | 10 |
| R04165 | BFCL failure — unnecessary tool call | 7212 | F02112 | non-negotiable | false | 10 |
| R04166 | BFCL failure — missing tool call | 7213 | F02113 | non-negotiable | false | 10 |
| R04167 | Every model in the registry needs a tool-use profile | 7215 | M00419 | non-negotiable | false | 10 |
| R04168 | Per-model tool-use profile field — `single_call` | 7220 | F02114 | non-negotiable | false | 10 |
| R04169 | Per-model tool-use profile field — `multi_turn` | 7221 | F02115 | non-negotiable | false | 10 |
| R04170 | Per-model tool-use profile field — `parallel_call` | 7222 | F02116 | non-negotiable | false | 10 |
| R04171 | Per-model tool-use profile field — `json_strictness` | 7223 | F02117 | non-negotiable | false | 10 |
| R04172 | Per-model tool-use profile field — `argument_precision` | 7224 | F02118 | non-negotiable | false | 10 |
| R04173 | Per-model tool-use profile field — `needs_schema_examples` (bool) | 7225 | F02119 | non-negotiable | false | 10 |
| R04174 | Runtime measures tool-use profile locally (not via generic leaderboard) | 7228–7230 | M00419 | non-negotiable | false | 10 |
| R04175 | Do not trust generic leaderboard scores | 7230 | M00419 | non-negotiable | false | 10 |
| R04176 | User-facing API — `station.run(goal, profile, intelligence, constraints)` | 7236–7246 | F02125 | non-negotiable | true | 10 |
| R04177 | User-facing API constraint — `network: deny` | 7242 | F02125 | non-negotiable | true | 10 |
| R04178 | User-facing API constraint — `writes: ask` | 7243 | F02125 | non-negotiable | true | 10 |
| R04179 | User-facing API constraint — `oracle_final: True` | 7244 | F02125 | non-negotiable | true | 10 |
| R04180 | Under-the-hood pipeline — compile DAG | 7252 | E0236 | non-negotiable | false | 10 |
| R04181 | Under-the-hood pipeline — route experts | 7253 | E0236 | non-negotiable | false | 10 |
| R04182 | Under-the-hood pipeline — execute parallel futures | 7254 | E0236 | non-negotiable | false | 10 |
| R04183 | Under-the-hood pipeline — validate schemas | 7255 | E0236 | non-negotiable | false | 10 |
| R04184 | Under-the-hood pipeline — observe results | 7256 | E0236 | non-negotiable | false | 10 |
| R04185 | Under-the-hood pipeline — recompile if needed | 7257 | E0236 | non-negotiable | false | 10 |
| R04186 | Under-the-hood pipeline — commit trace | 7258 | E0236 | non-negotiable | false | 10 |
| R04187 | Under-the-hood pipeline — update evals | 7259 | E0236 | non-negotiable | false | 10 |
| R04188 | That is the difference between an assistant and an intelligence machine | 7262 | E0236 | non-negotiable | false | 10 |
| R04189 | Smart runtime does NOT blindly finish the original plan | 7266 | M00420 | non-negotiable | false | 10 |
| R04190 | Smart runtime recompiles when observations arrive | 7268 | M00420 | non-negotiable | false | 10 |
| R04191 | Recompile trigger — test failed → recompile repair loop | 7272 | F02120 | non-negotiable | false | 10 |
| R04192 | Recompile trigger — missing file → recompile retrieval | 7273 | F02121 | non-negotiable | false | 10 |
| R04193 | Recompile trigger — tool denied → recompile offline path | 7274 | F02122 | non-negotiable | false | 10 |
| R04194 | Recompile trigger — oracle disagreement → recompile debate | 7275 | F02123 | non-negotiable | false | 10 |
| R04195 | Recompile trigger — memory conflict → recompile verification | 7276 | F02124 | non-negotiable | false | 10 |
| R04196 | Static workflow is brittle | 7280 | M00420 | non-negotiable | false | 10 |
| R04197 | Fully free agent loop is chaotic | 7281 | M00420 | non-negotiable | false | 10 |
| R04198 | Adaptive compilation is the middle path | 7282 | M00420 | non-negotiable | false | 10 |
| R04199 | Compiler pipeline stage 1 — Intent Parse (classify task, risk, modality, desired outcome) | 7287–7288 | M00421 | non-negotiable | false | 10 |
| R04200 | Compiler pipeline stage 2 — Context Build (memory, files, KV refs, tool catalog) | 7290–7291 | M00421 | non-negotiable | false | 10 |
| R04201 | Compiler pipeline stage 3 — Plan Synthesis (generate candidate DAGs) | 7293–7294 | M00421 | non-negotiable | false | 10 |
| R04202 | Compiler pipeline stage 4 — Plan Validation (schema, dependency, capability, policy) | 7296–7297 | M00421 | non-negotiable | false | 10 |
| R04203 | Compiler pipeline stage 5 — Plan Optimization (parallelize, batch, cache, choose models/tools) | 7299–7300 | M00421 | non-negotiable | false | 10 |
| R04204 | Compiler pipeline stage 6 — Execution (run DAG with futures and checkpoints) | 7302–7303 | M00421 | non-negotiable | false | 10 |
| R04205 | Compiler pipeline stage 7 — Observation (collect typed outputs and telemetry) | 7305–7306 | M00421 | non-negotiable | false | 10 |
| R04206 | Compiler pipeline stage 8 — Recompile (adjust DAG if reality differs) | 7308–7309 | M00421 | non-negotiable | false | 10 |
| R04207 | Compiler pipeline stage 9 — Commit (deterministic final state update) | 7311–7312 | M00421 | non-negotiable | false | 10 |
| R04208 | Compiler pipeline stage 10 — Learn (eval cases, routing stats, recipe tuning) | 7314–7315 | M00421 | non-negotiable | false | 10 |
| R04209 | Intelligence creation — Generate possible programs | 7323 | E0237 | non-negotiable | false | 10 |
| R04210 | Intelligence creation — Run them against reality | 7324 | E0237 | non-negotiable | false | 10 |
| R04211 | Intelligence creation — Measure outcomes | 7325 | E0237 | non-negotiable | false | 10 |
| R04212 | Intelligence creation — Retain the useful patterns | 7326 | E0237 | non-negotiable | false | 10 |
| R04213 | Intelligence creation — Improve the compiler | 7327 | E0237 | non-negotiable | false | 10 |
| R04214 | Models generate | 7330 | E0237 | non-negotiable | false | 10 |
| R04215 | The compiler structures | 7331 | E0237 | non-negotiable | false | 10 |
| R04216 | The runtime tests | 7332 | E0237 | non-negotiable | false | 10 |
| R04217 | Memory accumulates | 7333 | E0237 | non-negotiable | false | 10 |
| R04218 | Policy constrains | 7334 | E0237 | non-negotiable | false | 10 |
| R04219 | Evals select | 7335 | E0237 | non-negotiable | false | 10 |
| R04220 | That is adaptation | 7337 | E0237 | non-negotiable | false | 10 |
| R04221 | Add Cognitive Compiler as new architecture component | 7344 | M00422 | non-negotiable | false | 10 |
| R04222 | Cognitive Compiler sits above the runtime | 7347 | M00422 | non-negotiable | false | 10 |
| R04223 | Architecture flow — User intent → Cognitive Compiler → Frame/DAG Runtime → AVX-512 Scheduler → Experts/Tools → Replay/Evals → Compiler optimization | 7350–7356 | M00422 | non-negotiable | false | 10 |
| R04224 | The Rule — Do not merely prompt the model. Compile the task | 7362–7364 | E0237 | non-negotiable | false | 10 |
| R04225 | High-standard move — compile the task | 7366 | E0237 | non-negotiable | false | 10 |
| R04226 | Profiles give choice | 7368 | E0237 | non-negotiable | false | 10 |
| R04227 | Recipes give programmability | 7369 | E0237 | non-negotiable | false | 10 |
| R04228 | DAGs give parallelism | 7370 | E0237 | non-negotiable | false | 10 |
| R04229 | Futures give latency hiding | 7371 | E0237 | non-negotiable | false | 10 |
| R04230 | Evals give adaptation | 7372 | E0237 | non-negotiable | false | 10 |
| R04231 | AVX-512 gives deterministic scheduling | 7373 | E0237 | non-negotiable | false | 10 |
| R04232 | The model portfolio gives options | 7374 | E0237 | non-negotiable | false | 10 |
| R04233 | That is SMART — flexible — intelligence you can actually operate | 7376 | E0237 | non-negotiable | false | 10 |
| R04234 | Compiler backend operator-overrideable (native / llmcompiler / spin) | 7019–7023 | F02041 | non-negotiable | true | 10 |
| R04235 | Env var `SOVEREIGN_COMPILER_BACKEND` | 7019–7023 | F02043 | non-negotiable | true | 10 |
| R04236 | CLI `--compiler-backend <name>` | 7019–7023 | F02044 | non-negotiable | true | 10 |
| R04237 | API `POST /v1/compile` — submit intent + receive typed DAG + capability plan + routing plan + cache plan + eval plan | 7038–7053 | E0231 | non-negotiable | true | 10 |
| R04238 | API `POST /v1/compile/dry-run` — preview DAG without execution | 7038–7053 | E0231 | non-negotiable | true | 10 |
| R04239 | API `POST /v1/compile/run` — compile + execute end-to-end | 7236–7259 | E0236 | non-negotiable | true | 10 |
| R04240 | Dashboard — Cognitive Compiler DAG visualizer (live nodes + state + dependency arrows + futures) | 7060–7090 | M00412 | non-negotiable | true | 10 |
| R04241 | Dashboard — Compiler pipeline 10-stage progress bar | 7287–7316 | M00421 | non-negotiable | true | 10 |
| R04242 | Dashboard — Symbolic futures resolution timeline | 7149–7163 | M00414 | non-negotiable | true | 10 |
| R04243 | Dashboard — Per-model tool-use profile inspector (6-axis YAML preview) | 7217–7226 | M00419 | non-negotiable | true | 10 |
| R04244 | Dashboard — Recompile-trigger event log (per trigger: original DAG → recompiled DAG diff) | 7271–7276 | M00420 | non-negotiable | true | 10 |
| R04245 | Test — 5-profile DAG-constraint compatibility (Fast/Careful/Exploratory/Private/Autonomous each produces compliant DAG) | 7099–7126 | M00413 | non-negotiable | false | 10 |
| R04246 | Test — DAG validation rejects cycle / unsatisfied dependency / unauthorized capability / policy violation | 7092 | F02074-F02077 | non-negotiable | false | 10 |
| R04247 | Test — 8-axis vector scheduler matches scalar reference on synthetic 1000-node DAG | 7174–7183 | M00416 | non-negotiable | false | 10 |
| R04248 | Test — symbolic futures resolve out-of-order without deadlock | 7149–7166 | M00414 | non-negotiable | false | 10 |
| R04249 | Test — 5 recompile triggers each produce expected recompiled DAG on synthetic input | 7271–7276 | M00420 | non-negotiable | false | 10 |
| R04250 | Composite — Cognitive Compiler is THE intelligence-creation mechanism: Models generate / Compiler structures / Runtime tests / Memory accumulates / Policy constrains / Evals select → Adaptation; integrates with M015 programming plane, M016 learning, M017 model registry, M019 cognitive operators, M020 semantic ISA, M021 6-layer weave, M022 Cognitive Frame, M023 execution substrate, M024 adaptive programming | 7320–7376 | E0237 | non-negotiable | false | 10 |

— End of M025 milestone file.
