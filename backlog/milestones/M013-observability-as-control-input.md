# M013 — Observability as control input

> Parent: `backlog/milestones/INDEX.md` row M013 (dump 3022–3370).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 3022–3370.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0106–E0115)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0106 | Observability as control input — telemetry feeds the scheduler | 3037–3052 |
| E0107 | Observability raw substrate — DCGM / OpenTelemetry / eBPF / Dynamo-style Prom/DCGM | 3041–3046 |
| E0108 | Observability Plane — sixth plane added | 3071–3089 |
| E0109 | Metrics that matter — Oracle / Scout / CPU deterministic layer / KV+memory / tools | 3091–3155 |
| E0110 | The scheduler should react — feedback-loop rules | 3158–3188 |
| E0111 | Bit-level control with telemetry — worker status word + AVX-512 routing mask | 3190–3229 |
| E0112 | Tracing is crucial — trace_id / span_id / branch_id / commit_id | 3231–3269 |
| E0113 | eBPF layer — catch what the runtime did not explicitly report | 3271–3287 |
| E0114 | The new rule — No unobserved side effects | 3289–3295 |
| E0115 | Dashboard philosophy — answer operational questions, not vanity graphs | 3297–3367 |

## Modules (M00198–M00215)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00198 | NVIDIA DCGM telemetry — `dcgm-exporter` HTTP-to-Prometheus | 3043 | E0107 |
| M00199 | OpenTelemetry — traces / metrics / logs / context propagation | 3044 | E0107 |
| M00200 | eBPF layer — kernel/runtime observability for I/O / process / network / syscalls | 3045 | E0107 |
| M00201 | Observability Plane metric set — GPU telemetry / CPU counters / AVX-512 engine timing / KV cache hit/miss / branch acceptance / speculative success / tool failure / memory retrieval quality / ZFS+IO latency / replay log throughput | 3076–3087 | E0108 |
| M00202 | Blackwell oracle metric set — utilization / vram_used / memory_bandwidth / batch_tokens / prefill_time / decode_time / idle_ms / verification_accept_rate | 3095–3104 | E0109 |
| M00203 | 4090 scout metric set — utilization / draft_tokens_per_sec / draft_acceptance_rate / draft_rejection_reason / rerank_latency / embedding_batch_size | 3108–3115 | E0109 |
| M00204 | CPU deterministic-layer metric set — branches_active / branches_killed_{budget,policy,grammar} / branches_sent_{oracle,scout} / avx_scheduler_tick_us / mask_compute_us / json_validate_us / policy_scan_us | 3119–3130 | E0109 |
| M00205 | KV/memory metric set — kv_{hit,prefix_hit,nonprefix_hit}_rate / kv_evictions / kv_offload_bytes / context_prefill_saved_ms / memory_candidates_{before_filter, after_bitset, after_rerank} | 3134–3144 | E0109 |
| M00206 | Tool metric set — tool_intents_{generated, rejected, user_confirmed} / tool_failures / tool_side_effects_committed | 3148–3154 | E0109 |
| M00207 | Feedback-loop rule — oracle idle → increase branch packing / lower scout threshold / prefetch likely KV | 3163–3166 | E0110 |
| M00208 | Feedback-loop rule — oracle VRAM pressure → reduce active branches / evict low-heat KV / lower scout max-context | 3168–3171 | E0110 |
| M00209 | Feedback-loop rule — low draft acceptance → reduce speculation depth / switch draft model / n-gram or suffix speculation | 3173–3176 | E0110 |
| M00210 | Feedback-loop rule — grammar mask time high → cache by grammar state / fewer structured branches / relax structure until final output | 3178–3181 | E0110 |
| M00211 | Feedback-loop rule — high tool rejection → route planning to oracle / tighten prompt/tool schema | 3183–3186 | E0110 |
| M00212 | Worker 64-bit status word — load / memory / thermal / queue / error / health / policy_mode / flags | 3194–3205 | E0111 |
| M00213 | Branch-routing mask — `route_to_oracle = value_high & oracle_healthy & not_vram_pressure & branch_needs_verification` | 3211–3217 | E0111 |
| M00214 | Branch-routing mask — `route_to_scout = scout_healthy & low_risk & draft_expected_useful & branch_budget_ok` | 3221–3227 | E0111 |
| M00215 | Trace mapping — trace_id=user request, span_id=branch step / model call / tool call, branch_id=runtime object, commit_id=accepted transition | 3238–3242 | E0112 |

## Features (F01021–F01105)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01021 | DCGM exporter integration — HTTP scrape endpoint | 3043 | M00198 | composite | false |
| F01022 | OpenTelemetry SDK integration — traces, metrics, logs | 3044 | M00199 | composite | false |
| F01023 | eBPF probes — I/O / process / network / syscall observers | 3045 | M00200 | composite | true |
| F01024 | Toggle telemetry backend (otel-collector / prom-direct / dual) | 3043–3046 | E0107 | mode | true |
| F01025 | Profile knob — `telemetry_backend = otel \| prom \| dual` | 3043–3046 | E0107 | profile | true |
| F01026 | Env var `SOVEREIGN_TELEMETRY_BACKEND` | 3043–3046 | E0107 | env_var | true |
| F01027 | CLI `--telemetry-backend <name>` | 3043–3046 | E0107 | cli_verb | true |
| F01028 | Metric — `sovereign_oracle_utilization` | 3096 | M00202 | observability_metric | false |
| F01029 | Metric — `sovereign_oracle_vram_used_bytes` | 3097 | M00202 | observability_metric | false |
| F01030 | Metric — `sovereign_oracle_memory_bandwidth_gbps` | 3098 | M00202 | observability_metric | false |
| F01031 | Metric — `sovereign_oracle_batch_tokens` | 3099 | M00202 | observability_metric | false |
| F01032 | Metric — `sovereign_oracle_prefill_time_ms` | 3100 | M00202 | observability_metric | false |
| F01033 | Metric — `sovereign_oracle_decode_time_ms` | 3101 | M00202 | observability_metric | false |
| F01034 | Metric — `sovereign_oracle_idle_ms` | 3102 | M00202 | observability_metric | false |
| F01035 | Metric — `sovereign_oracle_verification_accept_rate` | 3103 | M00202 | observability_metric | false |
| F01036 | Metric — `sovereign_scout_utilization` | 3109 | M00203 | observability_metric | false |
| F01037 | Metric — `sovereign_scout_draft_tokens_per_sec` | 3110 | M00203 | observability_metric | false |
| F01038 | Metric — `sovereign_scout_draft_acceptance_rate` | 3111 | M00203 | observability_metric | false |
| F01039 | Metric — `sovereign_scout_draft_rejection_reason_total{reason}` | 3112 | M00203 | observability_metric | false |
| F01040 | Metric — `sovereign_scout_rerank_latency_ms` | 3113 | M00203 | observability_metric | false |
| F01041 | Metric — `sovereign_scout_embedding_batch_size` | 3114 | M00203 | observability_metric | false |
| F01042 | Metric — `sovereign_cpu_branches_active` | 3120 | M00204 | observability_metric | false |
| F01043 | Metric — `sovereign_cpu_branches_killed_total{reason}` | 3121–3123 | M00204 | observability_metric | false |
| F01044 | Metric — `sovereign_cpu_branches_sent_total{organ}` | 3124–3125 | M00204 | observability_metric | false |
| F01045 | Metric — `sovereign_cpu_avx_scheduler_tick_us` | 3126 | M00204 | observability_metric | false |
| F01046 | Metric — `sovereign_cpu_mask_compute_us` | 3127 | M00204 | observability_metric | false |
| F01047 | Metric — `sovereign_cpu_json_validate_us` | 3128 | M00204 | observability_metric | false |
| F01048 | Metric — `sovereign_cpu_policy_scan_us` | 3129 | M00204 | observability_metric | false |
| F01049 | Metric — `sovereign_kv_hit_rate` | 3135 | M00205 | observability_metric | false |
| F01050 | Metric — `sovereign_kv_prefix_hit_rate` | 3136 | M00205 | observability_metric | false |
| F01051 | Metric — `sovereign_kv_nonprefix_hit_rate` | 3137 | M00205 | observability_metric | false |
| F01052 | Metric — `sovereign_kv_evictions_total` | 3138 | M00205 | observability_metric | false |
| F01053 | Metric — `sovereign_kv_offload_bytes_total{from,to}` | 3139 | M00205 | observability_metric | false |
| F01054 | Metric — `sovereign_context_prefill_saved_ms` | 3140 | M00205 | observability_metric | false |
| F01055 | Metric — `sovereign_memory_candidates_before_filter` | 3141 | M00205 | observability_metric | false |
| F01056 | Metric — `sovereign_memory_candidates_after_bitset` | 3142 | M00205 | observability_metric | false |
| F01057 | Metric — `sovereign_memory_candidates_after_rerank` | 3143 | M00205 | observability_metric | false |
| F01058 | Metric — `sovereign_tool_intents_generated_total` | 3149 | M00206 | observability_metric | false |
| F01059 | Metric — `sovereign_tool_intents_rejected_total` | 3150 | M00206 | observability_metric | false |
| F01060 | Metric — `sovereign_tool_intents_user_confirmed_total` | 3151 | M00206 | observability_metric | false |
| F01061 | Metric — `sovereign_tool_failures_total{tool}` | 3152 | M00206 | observability_metric | false |
| F01062 | Metric — `sovereign_tool_side_effects_committed_total` | 3153 | M00206 | observability_metric | false |
| F01063 | Feedback-loop policy — increase branch packing on oracle idle | 3163–3166 | M00207 | composite | true |
| F01064 | Feedback-loop policy — lower scout confidence threshold on oracle idle | 3163–3166 | M00207 | composite | true |
| F01065 | Feedback-loop policy — prefetch likely KV blocks on oracle idle | 3163–3166 | M00207 | composite | true |
| F01066 | Feedback-loop policy — reduce active branches on VRAM pressure | 3168–3171 | M00208 | composite | true |
| F01067 | Feedback-loop policy — evict low-heat KV on VRAM pressure | 3168–3171 | M00208 | composite | true |
| F01068 | Feedback-loop policy — lower scout max-context on VRAM pressure | 3168–3171 | M00208 | composite | true |
| F01069 | Feedback-loop policy — reduce speculation depth on low draft acceptance | 3173–3176 | M00209 | composite | true |
| F01070 | Feedback-loop policy — switch draft model on low draft acceptance | 3173–3176 | M00209 | composite | true |
| F01071 | Feedback-loop policy — fall back to n-gram/suffix speculation on low draft acceptance | 3173–3176 | M00209 | composite | true |
| F01072 | Feedback-loop policy — cache masks by grammar state on high mask time | 3178–3181 | M00210 | composite | true |
| F01073 | Feedback-loop policy — fewer structured branches per tick on high mask time | 3178–3181 | M00210 | composite | true |
| F01074 | Feedback-loop policy — relax structure until final output on high mask time | 3178–3181 | M00210 | composite | true |
| F01075 | Feedback-loop policy — route more planning to oracle on high tool rejection | 3183–3186 | M00211 | composite | true |
| F01076 | Feedback-loop policy — tighten prompt / tool schema on high tool rejection | 3183–3186 | M00211 | composite | true |
| F01077 | Profile knob — `feedback_loop_rules = oracle_idle,vram_pressure,draft_acceptance,mask_time,tool_rejection` | 3163–3186 | E0110 | profile | true |
| F01078 | Env var `SOVEREIGN_FEEDBACK_LOOP_RULES` | 3163–3186 | E0110 | env_var | true |
| F01079 | Worker status-word — `bits 0..7 load bucket` | 3197 | M00212 | data_model | false |
| F01080 | Worker status-word — `bits 8..15 memory pressure` | 3198 | M00212 | data_model | false |
| F01081 | Worker status-word — `bits 16..23 thermal pressure` | 3199 | M00212 | data_model | false |
| F01082 | Worker status-word — `bits 24..31 queue depth` | 3200 | M00212 | data_model | false |
| F01083 | Worker status-word — `bits 32..39 error state` | 3201 | M00212 | data_model | false |
| F01084 | Worker status-word — `bits 40..47 health` | 3202 | M00212 | data_model | false |
| F01085 | Worker status-word — `bits 48..55 policy mode` | 3203 | M00212 | data_model | false |
| F01086 | Worker status-word — `bits 56..63 flags` | 3204 | M00212 | data_model | false |
| F01087 | Branch routing — AVX-512 `route_to_oracle` mask composer | 3211–3217 | M00213 | composite | false |
| F01088 | Branch routing — AVX-512 `route_to_scout` mask composer | 3221–3227 | M00214 | composite | false |
| F01089 | Trace mapping — `trace_id` per user request | 3238 | M00215 | data_model | false |
| F01090 | Trace mapping — `span_id` per branch step / model call / tool call | 3239 | M00215 | data_model | false |
| F01091 | Trace mapping — `branch_id` deterministic runtime object | 3240 | M00215 | data_model | false |
| F01092 | Trace mapping — `commit_id` accepted transition | 3241 | M00215 | data_model | false |
| F01093 | eBPF probe — file-touch observer | 3276 | M00200 | composite | true |
| F01094 | eBPF probe — unexpected-network-attempt observer | 3277 | M00200 | composite | true |
| F01095 | eBPF probe — syscall-latency observer | 3278 | M00200 | composite | true |
| F01096 | eBPF probe — disk-I/O burst observer | 3279 | M00200 | composite | true |
| F01097 | eBPF probe — process-spawn observer | 3280 | M00200 | composite | true |
| F01098 | eBPF probe — container/VM boundary behavior observer | 3281 | M00200 | composite | true |
| F01099 | eBPF probe — GPU-process mapping (paired with NVML/DCGM) | 3282 | M00200 | composite | true |
| F01100 | Dashboard — "Is the Blackwell idle?" | 3304 | E0115 | dashboard | true |
| F01101 | Dashboard — "Is the 4090 helping?" + "Is speculation worth it?" + "Are token masks expensive?" + "Is KV reuse saving prefill?" + "Are tools being rejected too often?" + "Are branches dying for useful reasons?" + "Is storage latency hurting context?" + "Is the system becoming more efficient over time?" | 3305–3312 | E0115 | dashboard | true |
| F01102 | Runtime tuning — speculation profile by task type / best draft model by domain / best context retrieval policy by repo / tool failure patterns / grammar schemas that slow decoding / memory chunks repeatedly useful | 3319–3326 | E0115 | composite | true |
| F01103 | Composite — Six-plane architecture confirmed with Observability Plane as plane 6 | 3334–3352 | E0108 | composite | false |
| F01104 | Composite — Observability plane closes the loop | 3354 | E0108 | composite | false |
| F01105 | Composite — No unobserved side effects (rule enforcement) | 3292 | E0114 | composite | false |

## Requirements (R02041–R02210)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R02041 | A serious deterministic AI workstation adapts its scheduling based on telemetry | 3039 | E0106 | non-negotiable | false | 10 |
| R02042 | NVIDIA DCGM exposes GPU health + workload metrics | 3043 | M00198 | non-negotiable | false | 10 |
| R02043 | `dcgm-exporter` serves DCGM metrics over HTTP for Prometheus | 3043 | M00198 | non-negotiable | false | 10 |
| R02044 | OpenTelemetry is the vendor-neutral framework for traces, metrics, and logs | 3044 | M00199 | non-negotiable | false | 10 |
| R02045 | eBPF is the Linux-side superpower for low-overhead observability of kernel/runtime behavior | 3045 | M00200 | non-negotiable | false | 10 |
| R02046 | NVIDIA Dynamo docs use Prometheus/DCGM-style GPU observability for inference infrastructure | 3046 | M00198 | non-negotiable | true | 10 |
| R02047 | Telemetry feeds the scheduler — high-standard move | 3051 | E0106 | non-negotiable | false | 10 |
| R02048 | Not just "Grafana shows GPU hot" | 3057 | E0106 | non-negotiable | false | 10 |
| R02049 | GPU memory bandwidth saturated → reduce oracle batch shape | 3063 | M00208 | non-negotiable | true | 10 |
| R02050 | 4090 underused → increase speculative width | 3064 | M00207 | non-negotiable | true | 10 |
| R02051 | Blackwell waiting → prefetch context / pack larger batch | 3065 | M00207 | non-negotiable | true | 10 |
| R02052 | CPU hot → reduce grammar-mask concurrency | 3066 | M00210 | non-negotiable | true | 10 |
| R02053 | NVMe queue latency high → stop cold memory promotion | 3067 | M00205 | non-negotiable | true | 10 |
| R02054 | ZFS ARC hit rate low → adjust memory admission | 3068 | M00205 | non-negotiable | true | 10 |
| R02055 | Sixth plane is Observability Plane | 3073 | E0108 | non-negotiable | false | 10 |
| R02056 | Observability plane includes GPU telemetry | 3077 | M00201 | non-negotiable | false | 10 |
| R02057 | Observability plane includes CPU counters | 3078 | M00201 | non-negotiable | false | 10 |
| R02058 | Observability plane includes AVX-512 engine timing | 3079 | M00201 | non-negotiable | false | 10 |
| R02059 | Observability plane includes KV cache hit/miss | 3080 | M00201 | non-negotiable | false | 10 |
| R02060 | Observability plane includes branch acceptance rate | 3081 | M00201 | non-negotiable | false | 10 |
| R02061 | Observability plane includes speculative success rate | 3082 | M00201 | non-negotiable | false | 10 |
| R02062 | Observability plane includes tool failure rate | 3083 | M00201 | non-negotiable | false | 10 |
| R02063 | Observability plane includes memory retrieval quality | 3084 | M00201 | non-negotiable | false | 10 |
| R02064 | Observability plane includes ZFS/IO latency | 3085 | M00201 | non-negotiable | false | 10 |
| R02065 | Observability plane includes replay log throughput | 3086 | M00201 | non-negotiable | false | 10 |
| R02066 | Observability is the nervous system, not an afterthought | 3089 | E0108 | non-negotiable | false | 10 |
| R02067 | Oracle metric — `oracle_utilization` | 3096 | M00202 | non-negotiable | false | 10 |
| R02068 | Oracle metric — `oracle_vram_used` | 3097 | M00202 | non-negotiable | false | 10 |
| R02069 | Oracle metric — `oracle_memory_bandwidth` | 3098 | M00202 | non-negotiable | false | 10 |
| R02070 | Oracle metric — `oracle_batch_tokens` | 3099 | M00202 | non-negotiable | false | 10 |
| R02071 | Oracle metric — `oracle_prefill_time` | 3100 | M00202 | non-negotiable | false | 10 |
| R02072 | Oracle metric — `oracle_decode_time` | 3101 | M00202 | non-negotiable | false | 10 |
| R02073 | Oracle metric — `oracle_idle_ms` | 3102 | M00202 | non-negotiable | false | 10 |
| R02074 | Oracle metric — `oracle_verification_accept_rate` | 3103 | M00202 | non-negotiable | false | 10 |
| R02075 | Scout metric — `scout_utilization` | 3109 | M00203 | non-negotiable | false | 10 |
| R02076 | Scout metric — `draft_tokens_per_sec` | 3110 | M00203 | non-negotiable | false | 10 |
| R02077 | Scout metric — `draft_acceptance_rate` | 3111 | M00203 | non-negotiable | false | 10 |
| R02078 | Scout metric — `draft_rejection_reason` | 3112 | M00203 | non-negotiable | false | 10 |
| R02079 | Scout metric — `rerank_latency` | 3113 | M00203 | non-negotiable | false | 10 |
| R02080 | Scout metric — `embedding_batch_size` | 3114 | M00203 | non-negotiable | false | 10 |
| R02081 | CPU metric — `branches_active` | 3120 | M00204 | non-negotiable | false | 10 |
| R02082 | CPU metric — `branches_killed_budget` | 3121 | M00204 | non-negotiable | false | 10 |
| R02083 | CPU metric — `branches_killed_policy` | 3122 | M00204 | non-negotiable | false | 10 |
| R02084 | CPU metric — `branches_killed_grammar` | 3123 | M00204 | non-negotiable | false | 10 |
| R02085 | CPU metric — `branches_sent_oracle` | 3124 | M00204 | non-negotiable | false | 10 |
| R02086 | CPU metric — `branches_sent_scout` | 3125 | M00204 | non-negotiable | false | 10 |
| R02087 | CPU metric — `avx_scheduler_tick_us` | 3126 | M00204 | non-negotiable | false | 10 |
| R02088 | CPU metric — `mask_compute_us` | 3127 | M00204 | non-negotiable | false | 10 |
| R02089 | CPU metric — `json_validate_us` | 3128 | M00204 | non-negotiable | false | 10 |
| R02090 | CPU metric — `policy_scan_us` | 3129 | M00204 | non-negotiable | false | 10 |
| R02091 | KV/memory metric — `kv_hit_rate` | 3135 | M00205 | non-negotiable | false | 10 |
| R02092 | KV/memory metric — `kv_prefix_hit_rate` | 3136 | M00205 | non-negotiable | false | 10 |
| R02093 | KV/memory metric — `kv_nonprefix_hit_rate` | 3137 | M00205 | non-negotiable | false | 10 |
| R02094 | KV/memory metric — `kv_evictions` | 3138 | M00205 | non-negotiable | false | 10 |
| R02095 | KV/memory metric — `kv_offload_bytes` | 3139 | M00205 | non-negotiable | false | 10 |
| R02096 | KV/memory metric — `context_prefill_saved_ms` | 3140 | M00205 | non-negotiable | false | 10 |
| R02097 | KV/memory metric — `memory_candidates_before_filter` | 3141 | M00205 | non-negotiable | false | 10 |
| R02098 | KV/memory metric — `memory_candidates_after_bitset` | 3142 | M00205 | non-negotiable | false | 10 |
| R02099 | KV/memory metric — `memory_candidates_after_rerank` | 3143 | M00205 | non-negotiable | false | 10 |
| R02100 | Tool metric — `tool_intents_generated` | 3149 | M00206 | non-negotiable | false | 10 |
| R02101 | Tool metric — `tool_intents_rejected` | 3150 | M00206 | non-negotiable | false | 10 |
| R02102 | Tool metric — `tool_intents_user_confirmed` | 3151 | M00206 | non-negotiable | false | 10 |
| R02103 | Tool metric — `tool_failures` | 3152 | M00206 | non-negotiable | false | 10 |
| R02104 | Tool metric — `tool_side_effects_committed` | 3153 | M00206 | non-negotiable | false | 10 |
| R02105 | It becomes engineering, not mythology | 3156 | E0109 | non-negotiable | false | 10 |
| R02106 | Scheduler feedback loop — `oracle_idle_ms > threshold` triggers branch-packing increase | 3163–3164 | M00207 | non-negotiable | false | 10 |
| R02107 | Scheduler feedback loop — `oracle_idle_ms > threshold` triggers scout-confidence-threshold lowering | 3165 | M00207 | non-negotiable | false | 10 |
| R02108 | Scheduler feedback loop — `oracle_idle_ms > threshold` triggers KV-prefetch | 3166 | M00207 | non-negotiable | false | 10 |
| R02109 | Scheduler feedback loop — VRAM pressure triggers active-branch reduction | 3168–3169 | M00208 | non-negotiable | false | 10 |
| R02110 | Scheduler feedback loop — VRAM pressure triggers low-heat KV eviction | 3170 | M00208 | non-negotiable | false | 10 |
| R02111 | Scheduler feedback loop — VRAM pressure triggers scout max-context lowering | 3171 | M00208 | non-negotiable | false | 10 |
| R02112 | Scheduler feedback loop — low draft acceptance reduces speculation depth | 3173–3174 | M00209 | non-negotiable | false | 10 |
| R02113 | Scheduler feedback loop — low draft acceptance switches draft model | 3175 | M00209 | non-negotiable | false | 10 |
| R02114 | Scheduler feedback loop — low draft acceptance uses n-gram/suffix speculation | 3176 | M00209 | non-negotiable | false | 10 |
| R02115 | Scheduler feedback loop — high grammar-mask time caches by grammar state | 3178–3179 | M00210 | non-negotiable | false | 10 |
| R02116 | Scheduler feedback loop — high grammar-mask time reduces structured branches per tick | 3180 | M00210 | non-negotiable | false | 10 |
| R02117 | Scheduler feedback loop — high grammar-mask time relaxes structure until final output | 3181 | M00210 | non-negotiable | false | 10 |
| R02118 | Scheduler feedback loop — high tool-rejection routes more planning to oracle | 3183–3184 | M00211 | non-negotiable | false | 10 |
| R02119 | Scheduler feedback loop — high tool-rejection tightens prompt/tool schema | 3185 | M00211 | non-negotiable | false | 10 |
| R02120 | This is the real AI DevOps layer | 3188 | E0110 | non-negotiable | false | 10 |
| R02121 | Telemetry becomes bits — each worker gets a status word | 3192–3194 | M00212 | non-negotiable | false | 10 |
| R02122 | Worker status word — bits 0..7 load bucket | 3197 | M00212 | non-negotiable | false | 10 |
| R02123 | Worker status word — bits 8..15 memory pressure | 3198 | M00212 | non-negotiable | false | 10 |
| R02124 | Worker status word — bits 16..23 thermal pressure | 3199 | M00212 | non-negotiable | false | 10 |
| R02125 | Worker status word — bits 24..31 queue depth | 3200 | M00212 | non-negotiable | false | 10 |
| R02126 | Worker status word — bits 32..39 error state | 3201 | M00212 | non-negotiable | false | 10 |
| R02127 | Worker status word — bits 40..47 health | 3202 | M00212 | non-negotiable | false | 10 |
| R02128 | Worker status word — bits 48..55 policy mode | 3203 | M00212 | non-negotiable | false | 10 |
| R02129 | Worker status word — bits 56..63 flags | 3204 | M00212 | non-negotiable | false | 10 |
| R02130 | AVX-512 scheduler evaluates multiple workers/queues/branches with same mask logic | 3207 | M00212 | non-negotiable | false | 10 |
| R02131 | Branch routing mask — `route_to_oracle = value_high & oracle_healthy & not_vram_pressure & branch_needs_verification` | 3211–3217 | M00213 | non-negotiable | false | 10 |
| R02132 | Branch routing mask — `route_to_scout = scout_healthy & low_risk & draft_expected_useful & branch_budget_ok` | 3221–3227 | M00214 | non-negotiable | false | 10 |
| R02133 | Everything is law | 3229 | E0111 | non-negotiable | false | 10 |
| R02134 | Every request carries a trace id | 3233 | M00215 | non-negotiable | false | 10 |
| R02135 | OpenTelemetry gives the conceptual model: traces, metrics, logs, context propagation | 3235 | M00199 | non-negotiable | false | 10 |
| R02136 | Trace mapping — `trace_id` = user request | 3238 | M00215 | non-negotiable | false | 10 |
| R02137 | Trace mapping — `span_id` = branch step / model call / tool call | 3239 | M00215 | non-negotiable | false | 10 |
| R02138 | Trace mapping — `branch_id` = deterministic runtime object | 3240 | M00215 | non-negotiable | false | 10 |
| R02139 | Trace mapping — `commit_id` = accepted transition | 3241 | M00215 | non-negotiable | false | 10 |
| R02140 | Reconstructable per-trace — user request | 3247 | M00215 | non-negotiable | false | 10 |
| R02141 | Reconstructable per-trace — retrieved memory | 3248 | M00215 | non-negotiable | false | 10 |
| R02142 | Reconstructable per-trace — draft branches | 3249 | M00215 | non-negotiable | false | 10 |
| R02143 | Reconstructable per-trace — policy decisions | 3250 | M00215 | non-negotiable | false | 10 |
| R02144 | Reconstructable per-trace — oracle verification | 3251 | M00215 | non-negotiable | false | 10 |
| R02145 | Reconstructable per-trace — tool calls | 3252 | M00215 | non-negotiable | false | 10 |
| R02146 | Reconstructable per-trace — file edits | 3253 | M00215 | non-negotiable | false | 10 |
| R02147 | Reconstructable per-trace — final answer | 3254 | M00215 | non-negotiable | false | 10 |
| R02148 | Reconstructable per-trace — latency per stage | 3255 | M00215 | non-negotiable | false | 10 |
| R02149 | Tracing is how you debug agents | 3258 | E0112 | non-negotiable | false | 10 |
| R02150 | Without traces — "the AI did something weird" | 3260 | E0112 | non-negotiable | false | 10 |
| R02151 | With traces — concrete per-bit explanation of every decision | 3264–3267 | E0112 | non-negotiable | false | 10 |
| R02152 | eBPF observes which process touched which file | 3276 | M00200 | non-negotiable | true | 10 |
| R02153 | eBPF observes unexpected network attempts | 3277 | M00200 | non-negotiable | true | 10 |
| R02154 | eBPF observes syscall latency | 3278 | M00200 | non-negotiable | true | 10 |
| R02155 | eBPF observes disk I/O bursts | 3279 | M00200 | non-negotiable | true | 10 |
| R02156 | eBPF observes process spawning | 3280 | M00200 | non-negotiable | true | 10 |
| R02157 | eBPF observes container/VM boundary behavior | 3281 | M00200 | non-negotiable | true | 10 |
| R02158 | eBPF observes GPU process mapping when paired with NVML/DCGM | 3282 | M00200 | non-negotiable | true | 10 |
| R02159 | eBPF makes tool sandboxing measurable | 3287 | E0113 | non-negotiable | false | 10 |
| R02160 | The new rule — No unobserved side effects | 3292 | E0114 | non-negotiable | false | 10 |
| R02161 | Agent file edits are recorded by the runtime | 3294–3295 | E0114 | non-negotiable | false | 10 |
| R02162 | Agent shell calls are recorded by the runtime | 3294–3295 | E0114 | non-negotiable | false | 10 |
| R02163 | Agent network touches are recorded by the runtime | 3294–3295 | E0114 | non-negotiable | false | 10 |
| R02164 | Agent cache writes are recorded by the runtime | 3294–3295 | E0114 | non-negotiable | false | 10 |
| R02165 | Agent process spawns are recorded by the runtime | 3294–3295 | E0114 | non-negotiable | false | 10 |
| R02166 | Dashboard does NOT show vanity graphs | 3299 | E0115 | non-negotiable | false | 10 |
| R02167 | Dashboard answers — "Is the Blackwell idle?" | 3304 | E0115 | non-negotiable | false | 10 |
| R02168 | Dashboard answers — "Is the 4090 helping?" | 3305 | E0115 | non-negotiable | false | 10 |
| R02169 | Dashboard answers — "Is speculation worth it?" | 3306 | E0115 | non-negotiable | false | 10 |
| R02170 | Dashboard answers — "Are token masks expensive?" | 3307 | E0115 | non-negotiable | false | 10 |
| R02171 | Dashboard answers — "Is KV reuse saving prefill?" | 3308 | E0115 | non-negotiable | false | 10 |
| R02172 | Dashboard answers — "Are tools being rejected too often?" | 3309 | E0115 | non-negotiable | false | 10 |
| R02173 | Dashboard answers — "Are branches dying for useful reasons?" | 3310 | E0115 | non-negotiable | false | 10 |
| R02174 | Dashboard answers — "Is storage latency hurting context?" | 3311 | E0115 | non-negotiable | false | 10 |
| R02175 | Dashboard answers — "Is the system becoming more efficient over time?" | 3312 | E0115 | non-negotiable | false | 10 |
| R02176 | The system learns from itself, but deterministically | 3317 | E0115 | non-negotiable | false | 10 |
| R02177 | Runtime tuning — speculation profile by task type | 3320 | E0115 | non-negotiable | true | 10 |
| R02178 | Runtime tuning — best draft model by domain | 3321 | E0115 | non-negotiable | true | 10 |
| R02179 | Runtime tuning — best context retrieval policy by repo | 3322 | E0115 | non-negotiable | true | 10 |
| R02180 | Runtime tuning — tool failure patterns | 3323 | E0115 | non-negotiable | true | 10 |
| R02181 | Runtime tuning — grammar schemas that slow decoding | 3324 | E0115 | non-negotiable | true | 10 |
| R02182 | Runtime tuning — memory chunks repeatedly useful | 3325 | E0115 | non-negotiable | true | 10 |
| R02183 | Not model fine-tuning first; runtime tuning first | 3328 | E0115 | non-negotiable | false | 10 |
| R02184 | Plane 1 — Inference Plane (Blackwell oracle, 4090 scout) | 3335–3336 | E0108 | non-negotiable | false | 10 |
| R02185 | Plane 2 — Control Plane (AVX-512 branch/policy/grammar scheduler) | 3338–3339 | E0108 | non-negotiable | false | 10 |
| R02186 | Plane 3 — Memory Plane (semantic memory, KV refs, bitmaps, embeddings) | 3341–3342 | E0108 | non-negotiable | false | 10 |
| R02187 | Plane 4 — Storage Plane (ZFS replay, snapshots, caches, artifacts) | 3344–3345 | E0108 | non-negotiable | false | 10 |
| R02188 | Plane 5 — Tool Plane (sandboxed shell/browser/code/document actions) | 3347–3348 | E0108 | non-negotiable | false | 10 |
| R02189 | Plane 6 — Observability Plane (DCGM, OTel, eBPF, Prometheus/Grafana, custom runtime metrics) | 3350–3351 | E0108 | non-negotiable | false | 10 |
| R02190 | The observability plane closes the loop | 3354 | E0108 | non-negotiable | false | 10 |
| R02191 | Before — AI runtime executes | 3359 | E0106 | non-negotiable | false | 10 |
| R02192 | After — AI runtime senses itself, adapts, and remains replayable | 3365 | E0106 | non-negotiable | false | 10 |
| R02193 | Difference — between a powerful workstation and an evolving local AI system | 3368 | E0106 | non-negotiable | false | 10 |
| R02194 | Telemetry backend operator-overrideable (otel / prom / dual) | 3043–3046 | F01024 | non-negotiable | true | 10 |
| R02195 | Feedback-loop rule set operator-configurable (csv of rule keys) | 3163–3186 | F01077 | non-negotiable | true | 10 |
| R02196 | Each eBPF probe individually operator-toggleable | 3276–3282 | M00200 | non-negotiable | true | 10 |
| R02197 | Env var `SOVEREIGN_TELEMETRY_BACKEND` | 3043–3046 | F01026 | non-negotiable | true | 10 |
| R02198 | Env var `SOVEREIGN_FEEDBACK_LOOP_RULES` | 3163–3186 | F01078 | non-negotiable | true | 10 |
| R02199 | CLI `--telemetry-backend <name>` | 3043–3046 | F01027 | non-negotiable | true | 10 |
| R02200 | Test — every named oracle metric exposed via Prometheus | 3095–3104 | M00202 | non-negotiable | false | 10 |
| R02201 | Test — every named scout metric exposed via Prometheus | 3108–3115 | M00203 | non-negotiable | false | 10 |
| R02202 | Test — every named CPU metric exposed via Prometheus | 3119–3130 | M00204 | non-negotiable | false | 10 |
| R02203 | Test — every named KV/memory metric exposed via Prometheus | 3134–3144 | M00205 | non-negotiable | false | 10 |
| R02204 | Test — every named tool metric exposed via Prometheus | 3148–3154 | M00206 | non-negotiable | false | 10 |
| R02205 | Test — feedback loop rule fires on its trigger threshold | 3163–3186 | E0110 | non-negotiable | false | 10 |
| R02206 | Test — worker status-word bitfield encodes/decodes round-trip | 3194–3204 | M00212 | non-negotiable | false | 10 |
| R02207 | Test — trace context propagation (trace_id, span_id) across model+tool boundaries | 3233–3242 | M00215 | non-negotiable | false | 10 |
| R02208 | Test — eBPF probe captures the file-touch / network-attempt / process-spawn event the runtime did not report | 3273–3287 | M00200 | non-negotiable | false | 10 |
| R02209 | Test — No unobserved side effects rule fails when a runtime action is not recorded | 3289–3295 | E0114 | non-negotiable | false | 10 |
| R02210 | Test — dashboard answers each of the 9 operational questions with live data | 3304–3312 | E0115 | non-negotiable | false | 10 |

— End of M013 milestone file.
