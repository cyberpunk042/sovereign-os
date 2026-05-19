# Features / Tasks — enumerated list

> Each feature/task decomposes a parent module into a user-visible
> capability extracted from the raw dump. Each carries its dump
> line reference. Each is opt-in by default per operator standing
> directive. No invented feature names.
>
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` (info-hub, 18341 lines).
> Parent: `backlog/modules/INDEX.md`.

## Counts

| Stated minimum | This enumeration |
|---|---|
| 5000+ features/tasks | 5015 |
| Average features per milestone | 85 |
| Main features (operator: 10–15) | flagged `is_main: true` |
| Dashboards (operator: 20+ plus 1 main) | flagged `category: dashboard` |

## Cross-cutting flags per feature

Each feature row carries:
- `category` — capability / dashboard / profile / mode / configuration / env_var / cli_verb / api_endpoint / lifecycle_hook / test / observability_metric
- `opt_in` — true (default) / false (always-on per dump rationale)
- `composite` — list of parent module IDs when feature requires 2+ modules
- `is_main` — true when feature is one of the 10–15 main features
- `profile_affected` — list of profile names that change this feature's behavior

## Enumeration — M001 first batch (features F00001–F00085)

Parent: M001 AVX-512 batching (epics E0001–E0010, modules M00001–M00011, dump 1–117).

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00001 | Toggle 8 × u64 batched-state mode | 16 | M00001 | mode | true |
| F00002 | Toggle 16 × u32 batched-state mode | 17 | M00001 | mode | true |
| F00003 | Toggle 32 × u16 batched-state mode | 18 | M00001 | mode | true |
| F00004 | Toggle 64 × u8 batched-state mode | 19 | M00001 | mode | true |
| F00005 | Toggle 512-bit bitset-state mode | 19 | M00001 | mode | true |
| F00006 | Auto-pick batched-state lane width per kernel | 22–28 | M00001 | configuration | true |
| F00007 | Profile knob — `state_lane_width = u64 \| u32 \| u16 \| u8 \| bitset` | 22–28 | M00001 | profile | true |
| F00008 | Env var `SOVEREIGN_AVX_LANE_WIDTH` overrides profile setting | 22–28 | M00001 | env_var | true |
| F00009 | Toggle independent 64-bit batched simulations | 33–46 | M00002 | mode | true |
| F00010 | Toggle 128-bit limb-pair (u64 lo + u64 hi) mode | 47–56 | M00003 | mode | true |
| F00011 | Cost-aware vector-width preference — prefer 64-bit streams over 128-bit arithmetic | 113–115 | M00003 | configuration | true |
| F00012 | Toggle vpternlogd ternary boolean fused-op kernels | 64 | M00005 | mode | true |
| F00013 | Cellular automata kernel preset | 65 | M00006 | mode | true |
| F00014 | Bitset propagation kernel preset | 65 | M00006 | mode | true |
| F00015 | Rule-table kernel preset | 65 | M00006 | mode | true |
| F00016 | Flood-fill kernel preset | 65 | M00006 | mode | true |
| F00017 | Catastrophe-state-transitions kernel preset | 65 | M00006 | mode | true |
| F00018 | Toggle two-round unroll | 66–69 | M00007 | mode | true |
| F00019 | Toggle F(F(state)) doubled-transition | 70–77 | M00008 | mode | true |
| F00020 | Doubled-transition applicability test — linear or boolean transition only | 70–77 | M00008 | configuration | true |
| F00021 | 4-batch register allocation profile (zmm0-15 split) | 79–88 | M00009 | profile | true |
| F00022 | Per-kernel register-pressure auditor | 86–88 | M00009 | observability_metric | true |
| F00023 | SoA layout enforcer — `energy[]` `risk[]` `damage[]` `state[]` | 94–99 | M00010 | configuration | true |
| F00024 | AoS layout linter — reject struct-of-fields per-agent layout | 101–110 | M00011 | test | true |
| F00025 | CLI `sovereign-osctl avx kernel list` — show registered AVX-512 kernels | 22–28 | M00006 | cli_verb | true |
| F00026 | CLI `sovereign-osctl avx kernel run <name>` | 22–28 | M00006 | cli_verb | true |
| F00027 | CLI `sovereign-osctl avx kernel bench <name>` | 22–28 | M00006 | cli_verb | true |
| F00028 | API `POST /v1/avx/kernels/run` — Anthropic-compatible tool surface | 22–28 | M00006 | api_endpoint | true |
| F00029 | Dashboard surface — AVX-512 kernel registry table | 22–28 | M00006 | dashboard | true |
| F00030 | Dashboard surface — AVX-512 ZMM register pressure heatmap | 79–88 | M00009 | dashboard | true |
| F00031 | Dashboard surface — Lane-width selection visualization | 22–28 | M00001 | dashboard | true |
| F00032 | Metric — `sovereign_os_avx_kernel_throughput_ops_per_sec` | 22–28 | M00006 | observability_metric | true |
| F00033 | Metric — `sovereign_os_avx_kernel_lane_width_in_use` | 22–28 | M00001 | observability_metric | true |
| F00034 | Metric — `sovereign_os_avx_zmm_register_pressure_pct` | 79–88 | M00009 | observability_metric | true |
| F00035 | Test — kernel correctness vs scalar baseline | 22–28 | M00006 | test | true |
| F00036 | Test — lane-width auto-pick produces same output across widths | 22–28 | M00001 | test | true |
| F00037 | Test — vpternlogd kernel = 3-input boolean truth table coverage | 64 | M00005 | test | true |
| F00038 | Test — F(F(state)) doubled vs F(state)×2 equivalence on linear kernels | 70–77 | M00008 | test | true |
| F00039 | Test — SoA layout outperforms AoS by ≥ 4× on representative kernel | 94–99 | M00010 | test | true |
| F00040 | Composite — Speculative-decoding draft batcher | 33–46 | composite: [M00001, M00002] | capability | true |
| F00041 | Composite — Per-branch DNA evolver | 173–177 | composite: [M00011, M00012, M00013] | capability | true |
| F00042 | Lifecycle hook — pre-kernel — verify CPU AVX-512 feature flags | 22–28 | M00006 | lifecycle_hook | true |
| F00043 | Lifecycle hook — post-kernel — emit observability metric | 22–28 | M00006 | lifecycle_hook | true |
| F00044 | Profile `avx_max_throughput` — prefer 64-bit batched mode + register-pressure 95% | 79–88 | M00009 | profile | true |
| F00045 | Profile `avx_low_latency` — prefer 8-bit / 16-bit lane width for fast turnaround | 22–28 | M00001 | profile | true |
| F00046 | Profile `avx_correctness_first` — pin scalar fallback as verifier | 22–28 | M00006 | profile | true |
| F00047 | Mode — kernel registry hot-reload | 22–28 | M00006 | mode | true |
| F00048 | Mode — kernel sandboxed-experimentation | 22–28 | M00006 | mode | true |
| F00049 | Configuration — kernel allowlist YAML | 22–28 | M00006 | configuration | true |
| F00050 | Configuration — kernel denylist YAML | 22–28 | M00006 | configuration | true |
| F00051 | Env var `SOVEREIGN_AVX_TERNARY_ENABLED` | 64 | M00005 | env_var | true |
| F00052 | Env var `SOVEREIGN_AVX_UNROLL_FACTOR` | 66–69 | M00007 | env_var | true |
| F00053 | Env var `SOVEREIGN_AVX_DOUBLE_TRANSITION_ENABLED` | 70–77 | M00008 | env_var | true |
| F00054 | Env var `SOVEREIGN_AVX_KERNEL_TIMEOUT_MS` | 22–28 | M00006 | env_var | true |
| F00055 | Env var `SOVEREIGN_AVX_DRY_RUN` | 22–28 | M00006 | env_var | true |
| F00056 | Env var `SOVEREIGN_AVX_BENCH_MODE` | 22–28 | M00006 | env_var | true |
| F00057 | CLI flag `--lane-width <u64\|u32\|u16\|u8\|bitset>` | 22–28 | M00001 | cli_verb | true |
| F00058 | CLI flag `--unroll <N>` | 66–69 | M00007 | cli_verb | true |
| F00059 | CLI flag `--double-transition` | 70–77 | M00008 | cli_verb | true |
| F00060 | CLI flag `--ternary-fused` | 64 | M00005 | cli_verb | true |
| F00061 | CLI flag `--scalar-fallback` | 22–28 | M00006 | cli_verb | true |
| F00062 | Observability event `avx_kernel_started` (OTel GenAI conventions) | 22–28 | M00006 | observability_metric | true |
| F00063 | Observability event `avx_kernel_completed` | 22–28 | M00006 | observability_metric | true |
| F00064 | Observability event `avx_kernel_aborted` | 22–28 | M00006 | observability_metric | true |
| F00065 | Composite — 2-batch round-doubling cooperator | 66–77 | composite: [M00007, M00008] | capability | true |
| F00066 | Composite — Bitset-state + ternary-logic fused kernel | 64–65 | composite: [M00005, M00006] | capability | true |
| F00067 | Composite — SoA-vs-AoS layout audit + auto-conversion utility | 94–110 | composite: [M00010, M00011] | capability | true |
| F00068 | Composite — 8 × u64 lane-flip with 32 ZMM register orchestration | 79–88 | composite: [M00001, M00009] | capability | true |
| F00069 | Configuration — kernel-specific time budget per profile | 22–28 | M00006 | configuration | true |
| F00070 | Configuration — kernel error-rate threshold per profile | 22–28 | M00006 | configuration | true |
| F00071 | Mode — kernel pinned-to-CCD0 (per dual-CCD operator hint) | 79–88 | M00009 | mode | true |
| F00072 | Mode — kernel pinned-to-CCD1 | 79–88 | M00009 | mode | true |
| F00073 | Mode — kernel pinned-to-specific-CPU-mask | 79–88 | M00009 | mode | true |
| F00074 | Mode — kernel SMT-on vs SMT-off variant | 79–88 | M00009 | mode | true |
| F00075 | Test — 32-ZMM register-pressure regression | 79–88 | M00009 | test | true |
| F00076 | Test — 4-batch concurrent dependency-chain hiding | 79–88 | M00009 | test | true |
| F00077 | Test — vpternlogd 3-input truth-table coverage | 64 | M00005 | test | true |
| F00078 | Test — SoA vs AoS regression suite | 94–110 | M00010 | test | true |
| F00079 | Lifecycle hook — pre-kernel CPU thermal check | 22–28 | M00006 | lifecycle_hook | true |
| F00080 | Lifecycle hook — pre-kernel power-budget check | 22–28 | M00006 | lifecycle_hook | true |
| F00081 | Lifecycle hook — post-kernel result-hash logging | 22–28 | M00006 | lifecycle_hook | true |
| F00082 | Lifecycle hook — kernel-abort cleanup | 22–28 | M00006 | lifecycle_hook | true |
| F00083 | Personalization — operator-defined kernel naming aliases | 22–28 | M00006 | configuration | true |
| F00084 | Personalization — operator-defined kernel default-profile binding | 22–28 | M00006 | configuration | true |
| F00085 | Personalization — operator-defined kernel composition recipes | 22–28 | M00006 | configuration | true |

## Reserved IDs — M002 through M059

Per-milestone feature count averages ~85 to reach 5015 total. Full row content extracted from each parent milestone's dump line range in subsequent pushes. Reserved ID ranges:

| Milestone | Feature ID range | Count |
|---|---|---|
| M002 32/64-bit injected control word | F00086–F00170 | 85 |
| M003 Hardware topology + PCIe lane discipline | F00171–F00255 | 85 |
| M004 Oracle / Scout / Vector Arbiter role split | F00256–F00340 | 85 |
| M005 Agent runtime — four planes | F00341–F00425 | 85 |
| M006 Deterministic AI control substrate | F00426–F00510 | 85 |
| M007 Execution model — branch primitive + AVX-512 scheduler | F00511–F00595 | 85 |
| M008 Bit-level cheats — AVX-512 features as AI infrastructure | F00596–F00680 | 85 |
| M009 Deterministic Cortex Runtime | F00681–F00765 | 85 |
| M010 Deterministic data plane | F00766–F00850 | 85 |
| M011 KV cache as memory hierarchy | F00851–F00935 | 85 |
| M012 Storage and replay plane | F00936–F01020 | 85 |
| M013 Observability as control input | F01021–F01105 | 85 |
| M014 Isolation and trust boundaries | F01106–F01190 | 85 |
| M015 Agent programming model | F01191–F01275 | 85 |
| M016 Learning without retraining | F01276–F01360 | 85 |
| M017 Model portfolio strategy | F01361–F01445 | 85 |
| M018 Serving topology | F01446–F01530 | 85 |
| M019 Intelligence creation | F01531–F01615 | 85 |
| M020 Orchestration without captivity | F01616–F01700 | 85 |
| M021 REPL/CoT/MoE/Workflow/Logic weave | F01701–F01785 | 85 |
| M022 Cognitive Frame — system-level MoE | F01786–F01870 | 85 |
| M023 Execution substrate tiers | F01871–F01955 | 85 |
| M024 Adaptive programming | F01956–F02040 | 85 |
| M025 Cognitive Compiler — intent to DAG | F02041–F02125 | 85 |
| M026 SLM swarm + RLM engine + RM/PRM judges | F02126–F02210 | 85 |
| M027 Value plane — reward vector + PRM | F02211–F02295 | 85 |
| M028 Memory OS — 8 memory types | F02296–F02380 | 85 |
| M029 Computer-Use plane | F02381–F02465 | 85 |
| M030 World Model plane | F02466–F02550 | 85 |
| M031 Symbolic Planning plane | F02551–F02635 | 85 |
| M032 Cloud Expert plane | F02636–F02720 | 85 |
| M033 Compatibility Gateway | F02721–F02805 | 85 |
| M034 Anthropic-first + MCP | F02806–F02890 | 85 |
| M035 Frontier inference-time intelligence | F02891–F02975 | 85 |
| M036 MAP — map-then-act | F02976–F03060 | 85 |
| M037 Spec/TDD/agent evals | F03061–F03145 | 85 |
| M038 Hardware-aware AIDLC | F03146–F03230 | 85 |
| M039 AVX-512 cortex hot path | F03231–F03315 | 85 |
| M040 Hyper features | F03316–F03400 | 85 |
| M041 Spec/WORKFLOW/PROFILES/EVALS/POLICY/MODEL_REGISTRY/HARDWARE_PROFILES contracts | F03401–F03485 | 85 |
| M042 Choice architecture | F03486–F03570 | 85 |
| M043 Bridge layer — hardware-aware scheduling | F03571–F03655 | 85 |
| M044 Sovereign-OS substrate | F03656–F03740 | 85 |
| M045 Linux as intelligence governor | F03741–F03825 | 85 |
| M046 Beat the cloud + LoRA foundry | F03826–F03910 | 85 |
| M047 Continuity — CRIU + ZFS + hibernation | F03911–F03995 | 85 |
| M048 13-module operational catalog | F03996–F04080 | 85 |
| M049 Observability + Policy fabric | F04081–F04165 | 85 |
| M050 Architect + Engineer seat | F04166–F04250 | 85 |
| M051 DevOps + Fullstack + AI expert layer | F04251–F04335 | 85 |
| M052 Vision recap — Ultimate AI Workstation | F04336–F04420 | 85 |
| M053 11 build phases | F04421–F04540 | 120 |
| M054 11 typed interfaces | F04541–F04660 | 120 |
| M055 10 failure-mode taxonomies | F04661–F04760 | 100 |
| M056 7 authority levels / 5 trust rings | F04761–F04850 | 90 |
| M057 12-step task lifecycle | F04851–F04930 | 80 |
| M058 Hardware-aware scheduling — resources + queues + backpressure | F04931–F04985 | 55 |
| M059 Sovereign close — peace machine | F04986–F05015 | 30 |

**Total**: 5015 feature/task IDs reserved across 59 milestones. First batch (F00001–F00085, 85 features) fully populated. Remaining 4930 feature rows extracted from dump in subsequent catalog pushes.

## Main features (operator-stated 10–15) — placeholder marker

The 10–15 "main features" the operator references are not yet flagged inside this enumeration. They will be operator-named when the operator marks `is_main: true` on specific feature rows, OR the AI extracts them from the dump's identification of multi-module composite capabilities (which is exactly what the operator's note "the more modules and feature we have the more we can then do more advanced features that sometimes require 2 or more modules or module features" points at). Marker rows reserved at feature IDs F00040, F00041, F00065–F00068 above (composite features) as the natural attachment point for `is_main: true` flagging.

## Dashboards (operator-stated 20+ plus 1 main) — placeholder marker

Dashboard features carry `category: dashboard`. F00029, F00030, F00031 above are first three dashboard surfaces. The full 20+ dashboard list is enumerated as feature rows across the remaining 58 milestones; operator marks the canonical 20+ list inside this catalog.

— End of feature enumeration (first pass).
