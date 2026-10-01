# Qwen 3.8 inference tuning — 2026-10-01

## Scope and baseline

Active profile remains qwen38-dual-agent-256k, Logic Q4_K_M / 131072,
Oracle Q8_0 / 262144; RTX 4090 allocations unchanged.
llama.cpp build 56381e4. No model service restart or weight replacement.
Only OpenClaw gateway restarted to load request sampling defaults.

Official references:
- https://huggingface.co/Qwen/Qwen3.8-27B#api-usage
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md

## Isolated Oracle batching experiment

Reproducer: `python3 scripts/inference/bench-qwen-tuning.py`.
Separate temporary server on localhost:18083; production model remains resident.
Select GPU by UUID, not CUDA ordinal. Initial ordinal-based attempt failed GPU
allocation; corrected launcher selected the RTX PRO 6000 by inventory UUID.
Logs: /tmp/sovereign-qwen-tuning-3ku2a6bn (failed initial placement),
/tmp/sovereign-qwen-tuning-h9apcj8s (successful comparison).

All six approximately 28035-token uncached retrieval requests passed exact-match.
Same logical batch 2048, context 262144, Q8 KV, greedy decoding, thinking off.

| Physical microbatch | Prefill tokens/sec, two repeats | End-to-end seconds |
|---|---|---|
| 512 | 2752.93 / 2723.74 | 10.399 / 10.791 |
| 1024 | 2855.08 / 2854.65 | 10.060 / 10.343 |
| 2048 | 2878.75 / 2854.62 | 9.982 / 10.343 |

1024 improves mean prefill about 4.3%; 2048 adds little. Not a randomized or
full-window benchmark; production residency and external traffic may influence
timings. Microbatch changes were NOT promoted to the active profile.

## MTP: incompatible artifact

`python3 scripts/inference/bench-qwen-tuning.py --mtp` failed startup:

```text
context type MTP requested but model doesn't contain MTP layers
failed to create MTP context
```

Log: /tmp/sovereign-qwen-tuning-f2pt4z5f/ubatch-512.log.
MTP remains disabled. A compatible artifact must be separately selected and
verified before further MTP testing; no speculative speedup is claimed.

## Sampling defaults applied and verified

The managed sync now fills missing Qwen3.8 sampler values while preserving
explicit operator values. Logic already requests enable_thinking=false; Oracle
already requests low reasoning effort. Installed OpenClaw extra-body wrapper
merges these fields into outgoing OpenAI-compatible payloads.

After sync, backend /slots confirmed Logic temperature=.7, top_p=.8,
top_k=20, min_p=0, presence_penalty=1.5; Oracle temperature=1, top_p=.95,
top_k=20, min_p=0, presence_penalty=0 (normal floating-point rounding).
Previous Oracle served request used min_p=.05.

OpenClaw real tool probes (SQLite transcript checked):
- tune-20261001-logic: 9699 ms, context131072, no fallback;
  one successful session_status tool call/result.
- tune-20261001-oracle: 11991 ms, context262144, no fallback;
  follow-up 11506 ms, second successful session_status call/result.

Oracle usage showed cacheRead24413 on the first tool continuation and24810 on
the second. However the next user turn had input24776/cacheRead0. Cache works
within a tool turn but was not retained for that next-turn request. Cause not
yet established; no cache configuration was changed on this evidence alone.

Verification:
```text
pytest -q tests/test_qwen38_sampling.py tests/test_openclaw_compaction_defaults.py tests/lint/test_qwen_trial_profiles.py
8 passed in 0.13s
systemctl show sovereign-logic-engine sovereign-oracle-core -p ActiveState -p NRestarts
ActiveState=active
NRestarts=0
ActiveState=active
NRestarts=0
```

Remaining: multi-turn cache-loss diagnosis, randomized/full-window batch trials,
broader sampling quality evaluation, long-running OpenClaw workload tests.
These bounded checks are not stability certification or proof of better quality.

## Follow-up: cache invalidation reproduced

Reproducer: `python3 scripts/inference/bench-qwen-tuning.py --cache-check`.
Artifacts: /tmp/sovereign-qwen-tuning-ow9zeezn. All four exact answers passed.
The temporary server was stopped by the harness; production was not restarted.

| Request | Prompt tokens | Cached tokens | Seconds |
|---|---:|---:|---:|
| Long system message, revision0 | 25529 | 0 | 9.365 |
| Same system with internal revision changed | 25529 | 0 | 9.461 |
| Stable system; revision moved into user message, first request | 25525 | 0 | 9.582 |
| Same stable system, changed user revision | 25525 | 25504 | 0.213 |

This is a synthetic datum relocation, NOT a change to real instruction roles.
Never demote system instructions to user content as a caching workaround.

Live Oracle journal at 09:01:02 reported f_sim_best=.622/f_keep=.622 before
reprocessing all24776 tokens. The preceding tool continuation matched .987 and
reused24413 tokens. Thus the observed next-turn failure involved a changed
prefix, not merely a missing cache_prompt flag. The exact differing field in
the real OpenClaw request is still unverified.

Upstream source at installed commit56381e4, tools/server/server-context.cpp
lines3590–3635, skips ordinary mid-prompt checkpoints unless at a user-message
start or near prompt end. This explains why changing an internal system-prefix
datum can force a hybrid model to replay from the beginning even when much of
the prefix matches. Decreasing checkpoint-min-step alone does not bypass that
condition.

Installed OpenClaw renderer defines a stable/dynamic system-prompt boundary.
Its openai-completions transport strips that marker unless cache-control handling
is enabled; cache-controlled text blocks are not automatically llama.cpp recurrent
state checkpoints. Changing cache RAM or sending a cache-control field therefore
is not a demonstrated fix. Next investigation must identify real prompt
differences with metadata-only instrumentation and preserve instruction authority
before proposing a transport or backend checkpoint change.

## Live prompt-hash trace: cache loss is not universal

Temporarily instrumented buildConfiguredAgentSystemPrompt for only session
cache-probe-20261001. Recorded per-line SHA256, lengths, and section categories
in /tmp/sovereign-prompt-trace-tBbmqF/hashes.jsonl (0600); no prompt text or
credentials were recorded. Instrumentation was removed after the experiment,
and the gateway restarted to unload it. Models were not restarted.

All three traced Oracle system prompts were byte-equivalent by line hashes.

| Oracle turn | End-to-end ms | First request uncached/cached tokens |
|---|---:|---|
| Fresh session | 11144 | 24302 / 0 |
| Same-session follow-up | 2024 | 53 / 24694 |
| Follow-up after a separate Logic session | 2860 | 53 / 25148 |

The intervening Logic tool probe completed in9317ms. Oracle tool continuations
also retained cache (24342,24782,25236 cached tokens). All probes returned ok.

This disproves a blanket claim that every new OpenClaw turn or card switch loses
cache. Earlier .622 prefix similarity and full replay remain real observations,
but the changing input was not reproduced in this trace. System hashes do not
cover transport-injected tool schemas or all historical message transformations.
No cache or prompt-structure fix was applied without identifying the actual
divergence. Next reproduction should compare transport-level metadata as well
as system hashes if the slowdown recurs.
