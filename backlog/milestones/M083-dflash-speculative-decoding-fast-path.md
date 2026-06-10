# M083 — DFlash speculative decoding fast-path (task-type-gated 3× decode acceleration)

**Parent**: sovereign-os runtime — inference execution paradigm layer (sibling of M073 ternary / M074 VNNI; layered on top of Pulse/Logic per master spec)
**Source**: `~/infohub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md` lines 1115-1131 (DFlash addition — verbatim operator text + cross-references)
**Codified**: `docs/sdd/026-dflash-speculative-decoding.md` (Round 157; review) · router task-type signal closed in R161 · master spec rows `docs/src/sain-01-master-spec.md` 377 + 432
**Audit provenance**: closes the 2026-06 catalog audit gap #2 — "DFlash survives only as one incidental clause; no dedicated epic, unlike Ling-2.6 / Nemotron-3 which got full treatment."

## Doctrinal anchors

> "And there is also Dflash I recently learned about that somehow with code task on model that fit in memory like any functional model in general it can work 3 times faster, does not work on creative tasks in general but interesting topic and place of introspection and knowledge" (dump 1119 — verbatim operator text)
> Cross-ref: paper arXiv:2602.06036 "DFlash: Block Diffusion for Flash Speculative Decoding" (Z-Lab, Feb 2026); repo github.com/z-lab/dflash. "Operator framing '3× faster on code tasks, doesn't work on creative' matches the paper's reported pattern (highest gains on math/code, moderate on conversational)." (dump 1129)
> Master spec: "**DFlash** speculative decoder | 3× speedup on code/math (operator-added) | layered on top of Pulse/Logic | not integrated (R157)" (master spec 377)

## Epics (E0798-E0807)

| epic | name | source |
|---|---|---|
| E0798 | Operator addition — DFlash speculative decoding enters the catalog as a first-class topic | dump 1115-1119 |
| E0799 | Task-type-conditional gain — 3× on code (+math per paper); does NOT work on creative | dump 1119 + 1129 |
| E0800 | Introspection mandate — "interesting topic and place of introspection and knowledge"; the integration must surface its decision to the operator | dump 1119 + SDD-026 |
| E0801 | Gated wrapper architecture — `dflash-wrap.sh` argv-prefix wrapper, gating BEFORE the backend sees argv | SDD-026 |
| E0802 | Operator override knobs — `DFLASH_ENABLE_OVERRIDE` / `DFLASH_DISABLE_OVERRIDE`; DISABLE wins when both set | SDD-026 |
| E0803 | Per-backend integration — vllm / llama_cpp / transformers argv+env shaping | SDD-026 |
| E0804 | Graceful degradation — absent install → vanilla decoding + clearly-tagged downshift, never a hard failure | SDD-026 |
| E0805 | Layer A/B observability — decision counters + journald decision log, operator-readable | SDD-026 |
| E0806 | Router task-type signal — `classify_task_type` + `X-Sovereign-Task-Type` header feeds the gate | R161 closure (SDD-026 follow-up) |
| E0807 | Layer-5 empirical validation — benchmark the 3× claim on the operator's real code+math workload | SDD-026 out-of-scope, catalogued forward |

## Modules (M01395-M01411)

| module | name | source |
|---|---|---|
| M01395 | sovereign-dflash-wrap (argv-prefix wrapper `scripts/inference/dflash-wrap.sh`) | SDD-026 |
| M01396 | sovereign-dflash-gating-policy (task_type → enabled/disabled decision table) | SDD-026 + dump 1119 |
| M01397 | sovereign-dflash-override-knobs (env-var precedence resolver; DISABLE wins) | SDD-026 |
| M01398 | sovereign-dflash-vllm-binding (`--speculative-config '{"method":"dflash",...}'`) | SDD-026 |
| M01399 | sovereign-dflash-llamacpp-binding (`--draft-model ${DFLASH_PATH}/draft.gguf`) | SDD-026 |
| M01400 | sovereign-dflash-transformers-binding (`PYTHONPATH=${DFLASH_PATH}` generation strategy) | SDD-026 |
| M01401 | sovereign-dflash-install-detector (`${DFLASH_PATH}` probe + `disabled-no-install` fallback) | SDD-026 |
| M01402 | sovereign-dflash-decision-metrics (Layer B counters, `sovereign_os_dflash_*`) | SDD-026 |
| M01403 | sovereign-dflash-journal-binding (Layer A decision+reason via journald → SDD-016 pipeline) | SDD-026 |
| M01404 | sovereign-dflash-router-tasktype-consumer (R161 `X-Sovereign-Task-Type` signal) | R161 |
| M01405 | sovereign-dflash-benchmark-harness (Layer 5 hardware-required speedup validation; pending) | SDD-026 out-of-scope |
| M01406 | sovereign-dflash-draft-model-tuner (draft size / acceptance-rate target; pending) | SDD-026 out-of-scope |
| M01407 | sovereign-dflash-cli-surface (`sovereign-osctl metrics show dflash` + journal lens) | SDD-026 |
| M01408 | sovereign-dflash-dashboard-binding (D-03 model health + D-10 eval history) | cross-ref M060 |
| M01409 | sovereign-dflash-typed-mirror (decision-policy mirror under MS007 scheme) | cross-ref selfdef MS007 |
| M01410 | sovereign-dflash-event-emitter (M049 trace + OCSF via MS026) | cross-ref M049 + selfdef MS026 |
| M01411 | sovereign-dflash-doctrine-preserver (operator's exact phrasing in runtime decision reasons) | SDD-026 citation discipline |

## Features (F06956-F07040)

| feature | name | source |
|---|---|---|
| F06956 | Doctrinal — DFlash operator-added topic, dump-tail addition alongside two HF model candidates | dump 19 + 1115 |
| F06957 | Doctrinal — "with code task ... it can work 3 times faster" verbatim | dump 1119 |
| F06958 | Doctrinal — "on model that fit in memory like any functional model in general" verbatim | dump 1119 |
| F06959 | Doctrinal — "does not work on creative tasks in general" verbatim | dump 1119 |
| F06960 | Doctrinal — "interesting topic and place of introspection and knowledge" verbatim | dump 1119 |
| F06961 | Cross-ref — arXiv:2602.06036 "DFlash: Block Diffusion for Flash Speculative Decoding" (Z-Lab) | dump 1129 |
| F06962 | Cross-ref — github.com/z-lab/dflash reference implementation | dump 1129 |
| F06963 | Cross-ref — operator framing matches paper pattern (highest gains math/code, moderate conversational) | dump 1129 |
| F06964 | Master-spec anchor — "3× speedup on code/math (operator-added) · layered on top of Pulse/Logic · not integrated (R157)" | master spec 377 |
| F06965 | Master-spec anchor — open-question row "DFlash integration — speculative-decoder fast-path for code/math" | master spec 432 |
| F06966 | Gating — task_type=code → enabled ("3 times faster" on code tasks) | SDD-026 |
| F06967 | Gating — task_type=math → enabled (paper's code+math acceleration pattern) | SDD-026 |
| F06968 | Gating — task_type=conversational → disabled (moderate gains; not worth quantization noise) | SDD-026 |
| F06969 | Gating — task_type=creative → disabled ("does not work on creative tasks in general") | SDD-026 + dump 1119 |
| F06970 | Gating — default decision computed BEFORE backend argv assembled (wrapper owns the gate) | SDD-026 |
| F06971 | Gating — decision-reason strings preserve operator's exact phrasing | SDD-026 citation discipline |
| F06972 | Override — `DFLASH_ENABLE_OVERRIDE=1` force-enables any task_type (e.g. benchmark creative to confirm the caveat) | SDD-026 |
| F06973 | Override — `DFLASH_DISABLE_OVERRIDE=1` force-disables globally (broken install fallback without redeploy) | SDD-026 |
| F06974 | Override — DISABLE wins when both env knobs set | SDD-026 |
| F06975 | Wrapper — `dflash-wrap.sh --task-type {code|math|conversational|creative} --backend {vllm|llama_cpp|transformers} -- <argv>` | SDD-026 |
| F06976 | Wrapper — argv-prefix pattern: backend command passes through unmodified when gate says disabled | SDD-026 |
| F06977 | Backend vllm — appends `--speculative-config '{"method":"dflash","path":...}'` | SDD-026 |
| F06978 | Backend llama_cpp — appends `--draft-model ${DFLASH_PATH}/draft.gguf` | SDD-026 |
| F06979 | Backend transformers — exports `PYTHONPATH=${DFLASH_PATH}` so dflash generation strategy is importable | SDD-026 |
| F06980 | Install — operator-facing path: `git clone github.com/z-lab/dflash /opt/dflash && pip install -e .` | SDD-026 |
| F06981 | Fallback — absent `${DFLASH_PATH}` → vanilla decoding + WARN log | SDD-026 |
| F06982 | Fallback — `decision="disabled-no-install"` metric label tags the downshift | SDD-026 |
| F06983 | Fallback — operator never gets a hard failure due to install state | SDD-026 |
| F06984 | Observability — `sovereign_os_dflash_decision_total{task_type,decision}` counter | SDD-026 |
| F06985 | Observability — `sovereign_os_dflash_last_invocation_timestamp{task_type}` gauge | SDD-026 |
| F06986 | Observability — `sovereign-osctl metrics show dflash` consumes Layer B | SDD-026 |
| F06987 | Observability — Layer A: decision + reason per run via log_info → journald → SDD-016 pipeline | SDD-026 |
| F06988 | Observability — `sovereign-osctl journal show inference` surfaces the decision log | SDD-026 |
| F06989 | Router — `classify_task_type` classifies requests into the 4-class R161 taxonomy | R161 |
| F06990 | Router — `X-Sovereign-Task-Type` response header carries the classification | R161 |
| F06991 | Router — task-type signal feeds the DFlash gate (closes SDD-026's R157 follow-up) | R161 + SDD-026 |
| F06992 | Introspection — was DFlash used for this request? why? — answerable without reading backend internals | SDD-026 + dump 1119 |
| F06993 | Benchmark (pending) — empirical Layer 5 speedup measurement on operator's real code+math workload | SDD-026 out-of-scope |
| F06994 | Benchmark (pending) — verify the 3× claim against measured tokens/sec ratio | SDD-026 out-of-scope + dump 1119 |
| F06995 | Benchmark (pending) — confirm the creative-tasks caveat empirically (ENABLE_OVERRIDE path) | SDD-026 |
| F06996 | Tuning (pending) — per-model draft-model size selection | SDD-026 out-of-scope |
| F06997 | Tuning (pending) — acceptance-rate target operator-tunable | SDD-026 out-of-scope |
| F06998 | Dashboard — D-03 model health surfaces DFlash decision distribution | cross-ref M060 |
| F06999 | Dashboard — D-10 eval history surfaces speculative vs vanilla eval scores | cross-ref M060 |
| F07000 | Dashboard — D-04 costs surfaces decode-time savings projection | cross-ref M060 |
| F07001 | Typed mirror — dflash decision-policy mirror under MS007 8/8 SATURATED scheme | cross-ref selfdef MS007 |
| F07002 | Typed mirror — TaskType enum {Code, Math, Conversational, Creative} | cross-ref selfdef MS007 + R161 |
| F07003 | Typed mirror — DflashDecision enum {Enabled, Disabled, DisabledNoInstall, ForcedOn, ForcedOff} | SDD-026 labels |
| F07004 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F07005 | Event — every wrapper run emits M049 trace with task_type + decision + reason | cross-ref M049 |
| F07006 | Event — OCSF System Activity 1001 per gated inference launch | cross-ref selfdef MS026 |
| F07007 | Event — override use (either knob) emits OCSF Configuration Change 5001 | cross-ref selfdef MS026 |
| F07008 | CLI — `sovereign-osctl metrics show dflash` returns decision counters | SDD-026 |
| F07009 | CLI — `sovereign-osctl journal show inference` returns decision log lines | SDD-026 |
| F07010 | CLI — wrapper `--help` documents task-types, backends, knobs, fallback | architecture |
| F07011 | Composition — layered on top of Pulse/Logic (Trinity placement per master spec) | master spec 377 + cross-ref M066 |
| F07012 | Composition — composes with M017 model portfolio (models that "fit in memory") | dump 1119 + cross-ref M017 |
| F07013 | Composition — composes with M035 inference-time intelligence (budget tiers pick decode strategy) | cross-ref M035 |
| F07014 | Composition — composes with M048 modules map (Compute Fabric serving role) | cross-ref M048 |
| F07015 | Composition — composes with M058 Goldilocks scheduler (decode-speed axis in routing objective) | cross-ref M058 |
| F07016 | Composition — composes with M060 cockpit (decision visibility surfaces) | cross-ref M060 |
| F07017 | Composition — composes with M073 ternary core (CPU-side models also speculative-eligible) | cross-ref M073 |
| F07018 | Composition — composes with selfdef MS036 tool sandboxes (backend processes sandboxed) | cross-ref selfdef MS036 |
| F07019 | Composition — composes with selfdef MS043 IPS operator surface (CLI integration) | cross-ref selfdef MS043 |
| F07020 | Boundary — DFlash gating + decode run in sovereign-os runtime | operator standing direction |
| F07021 | Boundary — selfdef IPS enforces sandbox/network boundaries for backend processes | cross-ref selfdef MS036 + MS038 |
| F07022 | Boundary — info-hub indexes the DFlash paper/repo as read-only second-brain entries | operator standing direction "second-brain" |
| F07023 | Doctrinal preservation — "3 times faster" never paraphrased in decision reasons | SDD-026 citation discipline + dump 1119 |
| F07024 | Doctrinal preservation — "does not work on creative tasks in general" never paraphrased | SDD-026 + dump 1119 |
| F07025 | Doctrinal preservation — wrapper script header cites the Block 7 verbatim addition | SDD-026 |
| F07026 | Doctrinal preservation — arXiv id + Z-Lab attribution preserved | dump 1129 |
| F07027 | Operational — wrapper is a pure argv shim: no daemon, no persistent state | SDD-026 |
| F07028 | Operational — gating decision deterministic for a given (task_type, env, install-state) triple | SDD-026 + architecture |
| F07029 | Operational — wrapper exit code mirrors the wrapped backend's exit code | architecture |
| F07030 | Operational — WARN-level decision logs rate-limited to one per launch (no log spam) | architecture |
| F07031 | Operator UX — operator can ask "was DFlash on for that request?" and get one-line answer | SDD-026 + dump 1119 |
| F07032 | Operator UX — operator can flip one env var to benchmark or kill the feature, no redeploy | SDD-026 |
| F07033 | Operator UX — decision distribution visible per task_type on the cockpit | cross-ref M060 |
| F07034 | Reproducibility — decision + reason recorded per run (Layer A) for replay audit | SDD-026 + cross-ref selfdef MS009 |
| F07035 | Reproducibility — draft-model file digest recorded at launch when llama_cpp path used | architecture + cross-ref selfdef MS003 |
| F07036 | Audit lineage — catalog audit 2026-06 gap #2 ("under-catalogued") closed by this milestone | audit verbatim |
| F07037 | Audit lineage — Ling-2.6 / Nemotron-3 "full treatment" parity reached (dedicated catalog presence) | audit verbatim + cross-ref M017 |
| F07038 | Closing — covers dump 1115-1131 verbatim DFlash scope | dump 1115-1131 |
| F07039 | Closing — SDD-026 design fully decomposed into catalog rows | SDD-026 |
| F07040 | Closing — Layer-5 benchmarking + draft-model tuning remain explicitly pending (no false "done") | SDD-026 out-of-scope + operator standing constraint |

## Requirements (R13911-R14080)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R13911 | Doctrinal — DFlash catalogued as first-class operator-added topic | dump 1115-1119 | F06956 | non-negotiable | false | 10 |
| R13912 | Doctrinal — "with code task ... it can work 3 times faster" preserved verbatim | dump 1119 | F06957 | non-negotiable | false | 10 |
| R13913 | Doctrinal — applies to "model that fit in memory like any functional model in general" | dump 1119 | F06958 | non-negotiable | false | 10 |
| R13914 | Doctrinal — "does not work on creative tasks in general" preserved verbatim | dump 1119 | F06959 | non-negotiable | false | 10 |
| R13915 | Doctrinal — "interesting topic and place of introspection and knowledge" preserved verbatim | dump 1119 | F06960 | non-negotiable | false | 10 |
| R13916 | Cross-ref — arXiv:2602.06036 cited wherever DFlash is documented | dump 1129 | F06961 | non-negotiable | false | 10 |
| R13917 | Cross-ref — github.com/z-lab/dflash cited as reference implementation | dump 1129 | F06962 | non-negotiable | false | 10 |
| R13918 | Cross-ref — operator-framing/paper-pattern match documented (math/code high, conversational moderate) | dump 1129 | F06963 | non-negotiable | false | 10 |
| R13919 | Master-spec — "layered on top of Pulse/Logic" placement honored | master spec 377 | F06964 | non-negotiable | false | 10 |
| R13920 | Master-spec — R157 "not integrated" status superseded only by real integration evidence | master spec 377 + SHIPPED discipline | F06964 | non-negotiable | false | 10 |
| R13921 | Master-spec — open-question row 432 tracked to closure via this milestone | master spec 432 | F06965 | non-negotiable | false | 10 |
| R13922 | Gating — task_type=code defaults to enabled | SDD-026 | F06966 | non-negotiable | false | 10 |
| R13923 | Gating — code-enable rationale recorded as operator verbatim "3 times faster" | SDD-026 + dump 1119 | F06966 | non-negotiable | false | 10 |
| R13924 | Gating — task_type=math defaults to enabled | SDD-026 | F06967 | non-negotiable | false | 10 |
| R13925 | Gating — math-enable rationale cites paper's code+math acceleration pattern | SDD-026 + dump 1129 | F06967 | non-negotiable | false | 10 |
| R13926 | Gating — task_type=conversational defaults to disabled | SDD-026 | F06968 | non-negotiable | false | 10 |
| R13927 | Gating — conversational-disable rationale: moderate gains, not worth quantization noise | SDD-026 | F06968 | non-negotiable | false | 10 |
| R13928 | Gating — task_type=creative defaults to disabled | SDD-026 | F06969 | non-negotiable | false | 10 |
| R13929 | Gating — creative-disable rationale recorded as operator verbatim | SDD-026 + dump 1119 | F06969 | non-negotiable | false | 10 |
| R13930 | Gating — naive always-on enablement is forbidden (quality on creative requests protected) | SDD-026 | F06969 | non-negotiable | false | 10 |
| R13931 | Gating — decision computed before backend argv assembled | SDD-026 | F06970 | non-negotiable | false | 10 |
| R13932 | Gating — decision-reason strings preserve exact operator phrasing | SDD-026 | F06971 | non-negotiable | false | 10 |
| R13933 | Gating — unknown task_type → disabled + WARN (fail-safe default) | architecture | F06970 | non-negotiable | false | 10 |
| R13934 | Override — DFLASH_ENABLE_OVERRIDE=1 force-enables any task_type | SDD-026 | F06972 | non-negotiable | false | 10 |
| R13935 | Override — ENABLE path exists to empirically benchmark the creative caveat | SDD-026 | F06972 | non-negotiable | false | 10 |
| R13936 | Override — DFLASH_DISABLE_OVERRIDE=1 force-disables globally | SDD-026 | F06973 | non-negotiable | false | 10 |
| R13937 | Override — DISABLE path exists for broken-install fallback without redeploy | SDD-026 | F06973 | non-negotiable | false | 10 |
| R13938 | Override — DISABLE wins when both knobs set | SDD-026 | F06974 | non-negotiable | false | 10 |
| R13939 | Override — override use visible in decision metric labels (ForcedOn/ForcedOff) | SDD-026 labels + architecture | F07003 | non-negotiable | false | 10 |
| R13940 | Wrapper — invocation schema `--task-type {code|math|conversational|creative}` | SDD-026 | F06975 | non-negotiable | false | 10 |
| R13941 | Wrapper — invocation schema `--backend {vllm|llama_cpp|transformers}` | SDD-026 | F06975 | non-negotiable | false | 10 |
| R13942 | Wrapper — `--` separator delimits wrapped backend argv | SDD-026 | F06975 | non-negotiable | false | 10 |
| R13943 | Wrapper — disabled decision passes backend argv through unmodified | SDD-026 | F06976 | non-negotiable | false | 10 |
| R13944 | Wrapper — wrapper lives at scripts/inference/dflash-wrap.sh | SDD-026 | F06975 | non-negotiable | false | 10 |
| R13945 | Wrapper — wrapper header cites Block 7 verbatim addition | SDD-026 | F07025 | non-negotiable | false | 10 |
| R13946 | Backend — vllm: append --speculative-config '{"method":"dflash","path":...}' | SDD-026 | F06977 | non-negotiable | false | 10 |
| R13947 | Backend — llama_cpp: append --draft-model ${DFLASH_PATH}/draft.gguf | SDD-026 | F06978 | non-negotiable | false | 10 |
| R13948 | Backend — transformers: export PYTHONPATH=${DFLASH_PATH} | SDD-026 | F06979 | non-negotiable | false | 10 |
| R13949 | Backend — per-backend shaping isolated so adding a 4th backend touches one case | architecture | F06977 | non-negotiable | false | 10 |
| R13950 | Install — documented operator path: clone to /opt/dflash + pip install -e . | SDD-026 | F06980 | non-negotiable | false | 10 |
| R13951 | Fallback — absent ${DFLASH_PATH} → vanilla decoding | SDD-026 | F06981 | non-negotiable | false | 10 |
| R13952 | Fallback — fallback logs WARN with decision reason | SDD-026 | F06981 | non-negotiable | false | 10 |
| R13953 | Fallback — fallback tagged decision="disabled-no-install" in metrics | SDD-026 | F06982 | non-negotiable | false | 10 |
| R13954 | Fallback — install state never produces a hard failure | SDD-026 | F06983 | non-negotiable | false | 10 |
| R13955 | Observability — sovereign_os_dflash_decision_total{task_type,decision} counter emitted | SDD-026 | F06984 | non-negotiable | false | 10 |
| R13956 | Observability — sovereign_os_dflash_last_invocation_timestamp{task_type} gauge emitted | SDD-026 | F06985 | non-negotiable | false | 10 |
| R13957 | Observability — metrics inventoried per the metric-inventory lockstep gate | repo gate discipline | F06984 | non-negotiable | false | 10 |
| R13958 | Observability — sovereign-osctl metrics show dflash renders Layer B counters | SDD-026 | F06986 | non-negotiable | false | 10 |
| R13959 | Observability — Layer A decision+reason printed via log_info per run | SDD-026 | F06987 | non-negotiable | false | 10 |
| R13960 | Observability — journald capture flows into SDD-016 Layer A pipeline | SDD-026 | F06987 | non-negotiable | false | 10 |
| R13961 | Observability — sovereign-osctl journal show inference surfaces decision lines | SDD-026 | F06988 | non-negotiable | false | 10 |
| R13962 | Router — classify_task_type implements the 4-class R161 taxonomy | R161 | F06989 | non-negotiable | false | 10 |
| R13963 | Router — X-Sovereign-Task-Type header carries the classification | R161 | F06990 | non-negotiable | false | 10 |
| R13964 | Router — task-type signal feeds the DFlash gate (R157 follow-up CLOSED) | R161 + SDD-026 | F06991 | non-negotiable | false | 10 |
| R13965 | Router — misclassification recoverable via the override knobs | SDD-026 + architecture | F06972 | non-negotiable | false | 10 |
| R13966 | Introspection — "was DFlash used for this request? why?" answerable from operator surfaces | SDD-026 + dump 1119 | F06992 | non-negotiable | false | 10 |
| R13967 | Introspection — answer requires no reading of backend internals | SDD-026 | F06992 | non-negotiable | false | 10 |
| R13968 | Benchmark (pending) — Layer 5 speedup measured on operator's real code+math workload | SDD-026 out-of-scope | F06993 | non-negotiable | false | 10 |
| R13969 | Benchmark (pending) — measured tokens/sec ratio compared against the 3× claim | SDD-026 + dump 1119 | F06994 | non-negotiable | false | 10 |
| R13970 | Benchmark (pending) — creative-task caveat empirically confirmed via ENABLE_OVERRIDE | SDD-026 | F06995 | non-negotiable | false | 10 |
| R13971 | Benchmark (pending) — results recorded in D-10 eval history | cross-ref M060 | F06999 | non-negotiable | false | 10 |
| R13972 | Tuning (pending) — draft-model size operator-tunable per model | SDD-026 out-of-scope | F06996 | non-negotiable | false | 10 |
| R13973 | Tuning (pending) — acceptance-rate target operator-tunable | SDD-026 out-of-scope | F06997 | non-negotiable | false | 10 |
| R13974 | Dashboard — D-03 model health shows decision distribution per task_type | cross-ref M060 | F06998 | non-negotiable | false | 10 |
| R13975 | Dashboard — D-10 eval history shows speculative vs vanilla eval scores | cross-ref M060 | F06999 | non-negotiable | false | 10 |
| R13976 | Dashboard — D-04 costs shows decode-time savings projection | cross-ref M060 | F07000 | non-negotiable | false | 10 |
| R13977 | Typed mirror — dflash decision-policy mirror under MS007 scheme | cross-ref selfdef MS007 | F07001 | non-negotiable | false | 10 |
| R13978 | Typed mirror — TaskType enum {Code, Math, Conversational, Creative} | cross-ref selfdef MS007 + R161 | F07002 | non-negotiable | false | 10 |
| R13979 | Typed mirror — DflashDecision enum {Enabled, Disabled, DisabledNoInstall, ForcedOn, ForcedOff} | SDD-026 labels | F07003 | non-negotiable | false | 10 |
| R13980 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F07004 | non-negotiable | false | 10 |
| R13981 | Typed mirror — schema-breaking changes require schema_version bump | cross-ref selfdef MS007 | F07004 | non-negotiable | false | 10 |
| R13982 | Event — every wrapper run emits M049 trace (task_type + decision + reason) | cross-ref M049 | F07005 | non-negotiable | false | 10 |
| R13983 | Event — OCSF System Activity 1001 per gated inference launch | cross-ref selfdef MS026 | F07006 | non-negotiable | false | 10 |
| R13984 | Event — override use emits OCSF Configuration Change 5001 | cross-ref selfdef MS026 | F07007 | non-negotiable | false | 10 |
| R13985 | Event — trace spans deterministic for MS009 replay | cross-ref selfdef MS009 | F07034 | non-negotiable | false | 10 |
| R13986 | CLI — sovereign-osctl metrics show dflash returns decision counters | SDD-026 | F07008 | non-negotiable | false | 10 |
| R13987 | CLI — sovereign-osctl journal show inference returns decision log | SDD-026 | F07009 | non-negotiable | false | 10 |
| R13988 | CLI — wrapper --help documents task-types, backends, knobs, fallback | architecture | F07010 | non-negotiable | false | 10 |
| R13989 | CLI — help text quotes the operator gating rationale verbatim | SDD-026 citation discipline | F07023 | non-negotiable | false | 10 |
| R13990 | Composition — Trinity placement: layered on top of Pulse/Logic | master spec 377 + cross-ref M066 | F07011 | non-negotiable | false | 10 |
| R13991 | Composition — composes with M017 model portfolio (memory-fitting models eligible) | dump 1119 + cross-ref M017 | F07012 | non-negotiable | false | 10 |
| R13992 | Composition — composes with M035 budget tiers (decode strategy is an intelligence-budget lever) | cross-ref M035 | F07013 | non-negotiable | false | 10 |
| R13993 | Composition — composes with M048 Compute Fabric serving role | cross-ref M048 | F07014 | non-negotiable | false | 10 |
| R13994 | Composition — composes with M058 Goldilocks objective (decode-speed axis) | cross-ref M058 | F07015 | non-negotiable | false | 10 |
| R13995 | Composition — composes with M060 cockpit decision visibility | cross-ref M060 | F07016 | non-negotiable | false | 10 |
| R13996 | Composition — composes with M073 ternary core (CPU models speculative-eligible) | cross-ref M073 | F07017 | non-negotiable | false | 10 |
| R13997 | Composition — composes with selfdef MS036 sandboxed backend processes | cross-ref selfdef MS036 | F07018 | non-negotiable | false | 10 |
| R13998 | Composition — composes with selfdef MS043 IPS operator surface | cross-ref selfdef MS043 | F07019 | non-negotiable | false | 10 |
| R13999 | Boundary — gating + decode run in sovereign-os runtime | operator standing direction | F07020 | non-negotiable | false | 10 |
| R14000 | Boundary — selfdef IPS enforces sandbox per MS036 | cross-ref selfdef MS036 | F07021 | non-negotiable | false | 10 |
| R14001 | Boundary — selfdef IPS enforces network per MS038 | cross-ref selfdef MS038 | F07021 | non-negotiable | false | 10 |
| R14002 | Boundary — info-hub indexes paper/repo read-only | operator standing direction "second-brain" | F07022 | non-negotiable | false | 10 |
| R14003 | Boundary — info-hub never mutated by the decode runtime | operator standing direction | F07022 | non-negotiable | false | 10 |
| R14004 | Doctrinal preservation — "3 times faster" never paraphrased | SDD-026 + dump 1119 | F07023 | non-negotiable | false | 10 |
| R14005 | Doctrinal preservation — "does not work on creative tasks in general" never paraphrased | SDD-026 + dump 1119 | F07024 | non-negotiable | false | 10 |
| R14006 | Doctrinal preservation — wrapper header citation maintained across edits | SDD-026 | F07025 | non-negotiable | false | 10 |
| R14007 | Doctrinal preservation — arXiv id + Z-Lab attribution preserved | dump 1129 | F07026 | non-negotiable | false | 10 |
| R14008 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F07023 | non-negotiable | false | 10 |
| R14009 | Operational — wrapper is a pure argv shim (no daemon, no persistent state) | SDD-026 | F07027 | non-negotiable | false | 10 |
| R14010 | Operational — decision deterministic for (task_type, env, install-state) | SDD-026 + architecture | F07028 | non-negotiable | false | 10 |
| R14011 | Operational — wrapper exit code mirrors wrapped backend exit code | architecture | F07029 | non-negotiable | false | 10 |
| R14012 | Operational — WARN decision logs limited to one per launch | architecture | F07030 | non-negotiable | false | 10 |
| R14013 | Operational — wrapper passes shellcheck (repo CI gate) | repo gate discipline | F06975 | non-negotiable | false | 10 |
| R14014 | Operational — wrapper covered by an L3 nspawn-style execution test | repo test discipline | F06975 | non-negotiable | false | 10 |
| R14015 | Operator UX — one-line answer to "was DFlash on for that request?" | SDD-026 + dump 1119 | F07031 | non-negotiable | false | 10 |
| R14016 | Operator UX — one env var flips benchmark/kill behavior, no redeploy | SDD-026 | F07032 | non-negotiable | false | 10 |
| R14017 | Operator UX — decision distribution per task_type visible on cockpit | cross-ref M060 | F07033 | non-negotiable | false | 10 |
| R14018 | Operator UX — operator may toggle the feature per profile | operator standing direction "everything can be turned on and off" | F07032 | non-negotiable | false | 10 |
| R14019 | Reproducibility — decision + reason recorded per run for replay audit | SDD-026 + cross-ref selfdef MS009 | F07034 | non-negotiable | false | 10 |
| R14020 | Reproducibility — draft-model digest recorded at launch (llama_cpp path) | architecture + cross-ref selfdef MS003 | F07035 | non-negotiable | false | 10 |
| R14021 | Reproducibility — digest mismatch emits OCSF Detection 2004 | cross-ref selfdef MS026 | F07035 | non-negotiable | false | 10 |
| R14022 | Audit lineage — 2026-06 catalog audit gap #2 closed by this milestone | audit verbatim | F07036 | non-negotiable | false | 10 |
| R14023 | Audit lineage — parity with Ling-2.6 / Nemotron-3 catalog treatment reached | audit verbatim + cross-ref M017 | F07037 | non-negotiable | false | 10 |
| R14024 | Performance — wrapper gating overhead < 50ms per launch | architecture | F06970 | non-negotiable | false | 10 |
| R14025 | Performance — metrics emission adds no blocking I/O to the launch path | architecture | F06984 | non-negotiable | false | 10 |
| R14026 | Performance — code-task decode throughput target: ≥ 2× vanilla until Layer-5 confirms 3× | dump 1119 + SDD-026 out-of-scope | F06994 | non-negotiable | false | 10 |
| R14027 | Performance — speculative path never slower than vanilla on enabled task-types (else auto-disable candidate) | architecture + dump 1129 | F06994 | non-negotiable | false | 10 |
| R14028 | Telemetry — decision counts per task_type emitted via Layer B | SDD-026 | F06984 | non-negotiable | false | 10 |
| R14029 | Telemetry — last-invocation freshness per task_type emitted | SDD-026 | F06985 | non-negotiable | false | 10 |
| R14030 | Telemetry — fallback (no-install) occurrences trackable over time | SDD-026 | F06982 | non-negotiable | false | 10 |
| R14031 | Telemetry — override usage trackable over time | SDD-026 + architecture | F07003 | non-negotiable | false | 10 |
| R14032 | Gating matrix — code × {no-override, enable, disable, both} → {enabled, ForcedOn, ForcedOff, ForcedOff} | SDD-026 | F06966 | non-negotiable | false | 10 |
| R14033 | Gating matrix — math × {no-override, enable, disable, both} → {enabled, ForcedOn, ForcedOff, ForcedOff} | SDD-026 | F06967 | non-negotiable | false | 10 |
| R14034 | Gating matrix — conversational × {no-override, enable, disable, both} → {disabled, ForcedOn, ForcedOff, ForcedOff} | SDD-026 | F06968 | non-negotiable | false | 10 |
| R14035 | Gating matrix — creative × {no-override, enable, disable, both} → {disabled, ForcedOn, ForcedOff, ForcedOff} | SDD-026 | F06969 | non-negotiable | false | 10 |
| R14036 | Gating matrix — full 4×4 matrix covered by lint/unit tests | repo test discipline | F06966 | non-negotiable | false | 10 |
| R14037 | Backend matrix — vllm × enabled → speculative-config appended exactly once | SDD-026 | F06977 | non-negotiable | false | 10 |
| R14038 | Backend matrix — vllm × disabled → argv untouched | SDD-026 | F06976 | non-negotiable | false | 10 |
| R14039 | Backend matrix — llama_cpp × enabled → draft-model flag appended exactly once | SDD-026 | F06978 | non-negotiable | false | 10 |
| R14040 | Backend matrix — llama_cpp × disabled → argv untouched | SDD-026 | F06976 | non-negotiable | false | 10 |
| R14041 | Backend matrix — transformers × enabled → PYTHONPATH exported | SDD-026 | F06979 | non-negotiable | false | 10 |
| R14042 | Backend matrix — transformers × disabled → environment untouched | SDD-026 | F06976 | non-negotiable | false | 10 |
| R14043 | Backend matrix — unknown backend → exit 2 + usage (dispatch-surface discipline) | architecture + repo CLI discipline | F06975 | non-negotiable | false | 10 |
| R14044 | Install detector — DFLASH_PATH unset → disabled-no-install | SDD-026 | F06981 | non-negotiable | false | 10 |
| R14045 | Install detector — DFLASH_PATH set but missing → disabled-no-install + WARN names the path | SDD-026 + architecture | F06981 | non-negotiable | false | 10 |
| R14046 | Install detector — DFLASH_PATH present → install considered live | SDD-026 | F06980 | non-negotiable | false | 10 |
| R14047 | Install detector — detection result included in the decision reason string | SDD-026 | F06987 | non-negotiable | false | 10 |
| R14048 | Decision vocabulary — enabled | SDD-026 | F07003 | non-negotiable | false | 10 |
| R14049 | Decision vocabulary — disabled (task-type gate) | SDD-026 | F07003 | non-negotiable | false | 10 |
| R14050 | Decision vocabulary — disabled-no-install (install gate) | SDD-026 | F06982 | non-negotiable | false | 10 |
| R14051 | Decision vocabulary — forced-on / forced-off (override gates) | SDD-026 + architecture | F07003 | non-negotiable | false | 10 |
| R14052 | Decision vocabulary — vocabulary closed: any new decision label requires catalog + mirror schema update | architecture + cross-ref selfdef MS007 | F07003 | non-negotiable | false | 10 |
| R14053 | Quality protection — creative output quality never degraded by silent speculation | dump 1119 + SDD-026 | F06969 | non-negotiable | false | 10 |
| R14054 | Quality protection — identity-aligned responses excluded from speculation by default | SDD-026 (problem statement) | F06969 | non-negotiable | false | 10 |
| R14055 | Quality protection — quantization-noise tradeoff documented per task-type | SDD-026 | F06968 | non-negotiable | false | 10 |
| R14056 | Scheduler — M058 may consult the decision policy when placing decode jobs | cross-ref M058 | F07015 | non-negotiable | false | 10 |
| R14057 | Scheduler — speculative-enabled jobs schedulable on either GPU tier (fit-in-memory rule) | dump 1119 + cross-ref M058 | F07012 | non-negotiable | false | 10 |
| R14058 | Portfolio — Ling-2.6-flash a named candidate for speculative serving | dump 1129 + cross-ref M017 | F07012 | non-negotiable | false | 10 |
| R14059 | Portfolio — Nemotron-3-Nano-Omni a named candidate for speculative serving | dump 1129 + cross-ref M017 | F07012 | non-negotiable | false | 10 |
| R14060 | Portfolio — per-model speculative eligibility recorded in the model registry | architecture + cross-ref M048 | F07012 | non-negotiable | false | 10 |
| R14061 | Docs — SDD-026 stays the canonical design doc; this milestone is its catalog decomposition | SDD-026 | F07039 | non-negotiable | false | 10 |
| R14062 | Docs — INDEX.md SDD row kept in lockstep with milestone status | repo gate discipline | F07039 | non-negotiable | false | 10 |
| R14063 | Docs — operator install path documented in deployment guide when integration ships | SDD-026 + repo doc discipline | F06980 | non-negotiable | false | 10 |
| R14064 | Docs — master-spec rows 377/432 updated when "not integrated (R157)" flips | master spec 377+432 + SHIPPED discipline | F06964 | non-negotiable | false | 10 |
| R14065 | Tests — gating-policy unit tests cover all 4 task-types | repo test discipline | F06966 | non-negotiable | false | 10 |
| R14066 | Tests — override-precedence tests cover both-set DISABLE-wins | SDD-026 | F06974 | non-negotiable | false | 10 |
| R14067 | Tests — per-backend argv-shaping tests for all 3 backends | SDD-026 | F06977 | non-negotiable | false | 10 |
| R14068 | Tests — no-install fallback test (absent DFLASH_PATH) | SDD-026 | F06981 | non-negotiable | false | 10 |
| R14069 | Tests — metric-emission contract test for both Layer-B series | SDD-026 | F06984 | non-negotiable | false | 10 |
| R14070 | Closing — covers dump 1115-1131 verbatim DFlash scope | dump 1115-1131 | F07038 | non-negotiable | false | 10 |
| R14071 | Closing — SDD-026 design fully decomposed (gating, overrides, backends, install, observability) | SDD-026 | F07039 | non-negotiable | false | 10 |
| R14072 | Closing — R161 router closure linked (classify_task_type + header) | R161 | F06991 | non-negotiable | false | 10 |
| R14073 | Closing — Layer-5 benchmarking remains pending; never claimed done without measurement | SDD-026 + operator standing constraint | F07040 | non-negotiable | false | 10 |
| R14074 | Closing — draft-model tuning remains pending; never claimed done | SDD-026 | F07040 | non-negotiable | false | 10 |
| R14075 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F06956 | non-negotiable | false | 10 |
| R14076 | Closing — sovereignty preserved (local decode acceleration; no cloud dependency) | operator standing direction | F07020 | non-negotiable | false | 10 |
| R14077 | Closing — boundary respected (sovereign-os decodes; selfdef IPS enforces) | operator standing direction | F07021 | non-negotiable | false | 10 |
| R14078 | Closing — cross-repo binding only through MS007 typed mirrors | cross-ref selfdef MS007 | F07001 | non-negotiable | false | 10 |
| R14079 | Closing — "Do not minimize" upheld (full DFlash catalog with 170 R-rows) | operator standing direction | F06956 | non-negotiable | false | 10 |
| R14080 | Closing — M083 closes audit gap #2; sovereign-os catalog at 81 milestones | audit verbatim + architecture | F07036 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M083.

## Cross-references

- **M017** — model portfolio strategy (Ling-2.6-flash / Nemotron-3 candidates; fit-in-memory rule)
- **M035** — frontier inference-time intelligence (decode strategy as an intelligence-budget lever)
- **M048** — modules map (Compute Fabric serving role; model registry)
- **M049** — observability + trace pipeline
- **M058** — Goldilocks hardware-aware scheduler (decode-speed axis)
- **M060** — cockpit + dashboards (D-03 / D-04 / D-10)
- **M066** — Trinity Framework (Pulse/Logic placement per master spec 377)
- **M073** — 1-bit ternary core (CPU-side models also speculative-eligible)
- **selfdef MS003** — signing (draft-model digest)
- **selfdef MS007** — typed-mirror crate scheme (dflash decision-policy mirror)
- **selfdef MS009** — replay validator (decision log replay audit)
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS036** — tool sandboxes (backend processes)
- **selfdef MS038** — network boundary
- **selfdef MS043** — IPS operator surface (CLI integration)
- **SDD-026** — `docs/sdd/026-dflash-speculative-decoding.md` (canonical design; review)
- **R157 / R161** — codification round + router task-type closure

## Schema

```
schema_version: "1.0.0"
milestone_id: M083
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump: 2026-05-15-sain-01-master-spec-other-conversation-transposition.md
source_dump_lines: 1115-1131 (DFlash addition — verbatim operator text)
codified_design: docs/sdd/026-dflash-speculative-decoding.md
gating_policy:
  code: enabled        # "3 times faster" (operator verbatim)
  math: enabled        # paper's code+math acceleration pattern
  conversational: disabled
  creative: disabled   # "does not work on creative tasks in general" (operator verbatim)
override_knobs: [DFLASH_ENABLE_OVERRIDE, DFLASH_DISABLE_OVERRIDE]  # DISABLE wins
backends: [vllm, llama_cpp, transformers]
wrapper: scripts/inference/dflash-wrap.sh
metrics: [sovereign_os_dflash_decision_total, sovereign_os_dflash_last_invocation_timestamp]
paper: arXiv:2602.06036
reference_repo: github.com/z-lab/dflash
catalog_status:
  sovereign_os: 81 milestones
  selfdef: 48 milestones
  combined: 129 milestones
```
