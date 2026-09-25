# Dual-GPU model qualification — 2026-09-24

Status: qualification design and initial baseline; no candidate certified.

## Saved profile and heavier OpenClaw work — 2026-09-25

Renamed the profile file and ID to `qwen38-dual-agent`, retaining the display name
Qwen 3.8 Dual Agent — 96K / 128K. Updated control options, actual command enum,
OpenClaw profile-primary mapping and regression tests. Activated the new ID via
the existing authorized CLI (exit 0); runtime payload and marker migrated.
Readiness means downloadable artifacts are available, not soak certification.

Added `scripts/inference/qualify-openclaw.py`: bounded, concurrent actual OpenClaw
read-tool tasks on both routes, each reading three ~11KB generated ledgers and
extracting random codes and summed amounts. Transcript tool-call/result evidence,
answer checking, fallback detection and per-case timing are recorded. The harness
stops a route after a failed case rather than continuing a misleading success tally.
Run artifacts for the first five-round-per-card batch:
`/tmp/sovereign-openclaw-qualification-t7vg_8bd` (temporary, not archival storage).
This batch is heavier functional testing, not the planned four-hour soak.

## Context increase trial — 2026-09-25

Operator approved the next step: Logic 98304 tokens, Oracle 131072 tokens.
The qwen38-dual-trial profile retains the same quantizations, Q8 KV caches,
single slots, output reservations and worker allocations. Rollback settings:
restore both max_model_len and context_budget entries to 65536 and reapply.

The control API was inactive/dead, so activation used the already allowlisted
`sudo -n /usr/local/bin/sovereign-osctl trinity profile switch qwen38-dual-trial`.
It exited zero and synchronized OpenClaw. Backend /v1/models reported 98304 and
131072. OpenClaw confirmed the same limits and executed session_status on each
route (one toolCall + one toolResult each), no fallback: 10065 / 11613 ms.
Dedicated sessions: context-increase-20260925-logic and -oracle.

Concurrent synthetic long-input retrieval tests were launched with tokenizer-
measured contents of 80018 / 110026 tokens, excluding chat-template overhead.
These test backend retrieval beyond 64K, not complex OpenClaw long-session quality.
Observed VRAM during prefill: Logic 21975 MiB, Oracle 31852 MiB; worker unchanged.
Oracle reached 80 C during prefill; this is a snapshot, not a thermal soak result.
Both retrieval tests passed with the exact expected code: Logic 80030 actual
prompt tokens in 39.81 s; Oracle 110038 prompt tokens in 63.60 s. Ten output
tokens each. Both services remained active with NRestarts=0 at the post-Logic
check. Full-window OpenClaw and soak qualification remain pending.

## Live trial update — 2026-09-25

All three selected artifacts completed the download worker's SHA256 verification.
Coder-Next had failed during downloading with RuntimeError; retry resumed the
transfer and reached complete. Both Qwen3.8 quantizations completed initially.

Activated `qwen38-dual-trial` through POST :8130/api/control/execute:
`ok=true`, `dry_run=false`, `exit_code=0`. Fixed its missing change_cli enum
membership first; options alone did not authorize profile activation. A new
regression test checks both trial IDs through the actual argv resolver.

Both backends now serve Qwen3.8-27B: Q4_K_M on Logic, Q8_0 on Oracle, with
65536 context and one slot each. OpenClaw catalog synchronization completed.
Direct backend structured lookup_inventory tool fixtures passed on both:
Logic 1.05 s, Oracle 1.23 s (non-thinking fixture, 512 output limit).

The first OpenClaw session_status cycle passed on both, with actual toolCall,
toolResult and final answer events at transcript seq 5/6/7. Sessions:
`qualification-20260925-qwen38-logic` and
`qualification-20260925-qwen38-oracle`. Durations 10146 / 11244 ms respectively,
no fallback and no compaction reported. These differ from the previous DeepSeek
Oracle's fabricated tool response. Do not generalize one fixture to all tools.

During concurrent repeated-tool testing, both systemd services reported
ActiveState=active and NRestarts=0. Observed VRAM: Oracle 29356 MiB, Logic
20729 MiB, worker 4888 MiB. Snapshot temperatures 62 / 50 / 34 C respectively.
These snapshots are not peak measurements or a completed soak qualification.

The Qwen3.8 trial is left active for evaluation, not promoted as certified.
Completed five additional concurrent OpenClaw tool cycles per route: Logic
9765–10341 ms; Oracle 11258–12092 ms. All returned ok, no fallback or abort.
Still required: varied multi-tool tasks, large results, long-context/compaction,
stream cancellation, lifecycle recovery, Coder-Next comparison and sustained soak.

Operator request is preserved verbatim in the LM profile standing directive.
This plan authorizes neither automatic promotion nor claims of zero future crashes.
SG1–SG5 reported pending by `scripts/sovereign-osctl approvals gates`.

## Scope

- Oracle: RTX PRO 6000 Blackwell Max-Q, 97887 MiB reported VRAM.
- Logic: RTX 5090, 32607 MiB reported VRAM.
- Preserve RTX 4090 display, embedding and reranking allocations.
- Start with independent models, one per inference GPU. Do not pool VRAM by default.
- Preserve existing profiles as rollback targets. No workstation reboot required.
- Test candidates separately before jointly loading the winning pair.
- Never expose credentials in evidence; no external messaging or paid fallback.

## Research shortlist, not a ranking of measured local results

| Candidate | Intended test | Caveat |
|---|---|---|
| Existing DeepSeek R1 Distill Llama 70B Q4_K_M | Oracle control/baseline | Must prove tool serialization and long-session behavior, not just reasoning |
| Existing GGML Qwen3.6 27B Q4_K_M | Logic control/baseline | Current failures must be reproduced and classified |
| Qwen3.8-27B | General-purpose candidate on Oracle first, then Logic Q4 if qualified | Verify exact GGUF artifact, runtime support, parser and memory before download/load |
| Qwen3-Coder-Next Q5_K_M / Q6_K | Oracle coding/tool candidate | 80B total / 3B active; not a 5090-only candidate at these precisions |
| Qwen3.8-Flash-Next | Deferred experimental track | Linked Q8 weights ~151.5 GiB; requires separate offload/runtime study |

Primary sources accessed 2026-09-24:

- https://huggingface.co/Qwen/Qwen3.8-27B
- https://huggingface.co/Qwen/Qwen3-Coder-Next
- https://huggingface.co/Qwen/Qwen3-Coder-Next-GGUF/tree/main
- https://huggingface.co/ggml-org/Qwen3.8-Flash-Next-GGUF/tree/main

Vendor benchmarks are candidate-selection evidence, not OpenClaw qualification.
Download only an explicitly selected quantization, all its shards and required
metadata. Check free space and immutable revision/checksums first; never pull all
quantizations. Runtime upgrades require their own rollback and regression check.

## Qualification matrix

Every result records model revision/hash, quantization, runtime commit, GPU UUID,
profile, context, output reservation, KV types, concurrency, chat template,
tool parser, OpenClaw version and gateway configuration fingerprint.

1. Preflight: exact files, free disk/RAM/VRAM, model identity at backend/gateway/
   OpenClaw, consistent context/output limits, no fallback substitution.
2. Direct backend: plain answer, structured JSON, tool selection, argument types,
   tool-result continuation, no-tool task, invalid-argument recovery, streaming.
3. Gateway: repeat identical fixtures; verify tool-call IDs, finish reasons,
   reasoning separation, usage accounting, streaming termination and errors.
4. OpenClaw: dedicated test sessions and restricted scratch workspace; actual
   tools must execute and yield correct artifacts. No personal chat reuse.
   Include read/search, multi-file edits with deterministic unit tests, recovery
   from a deliberately failed tool, and grounded synthesis from fixture files.
   Pin the requested model; reject fallback as a passing result.
5. Context: measured token counts at 8K, 16K, 32K, then 64K/128K only where
   budget permits. Include tool definitions, system prompt and output reservation.
   Test fresh and growing sessions, compaction, and near-limit tool results.
   Oversized input must yield a controlled error and leave the next request healthy.
6. Concurrency: each card alone, then both simultaneously; bounded queue tests,
   cancellation and retry. Keep 4090 services running throughout.
7. Lifecycle: service-only restart and profile reapply through the control rail;
   confirm route readiness and OpenClaw model-list persistence, no stale identities.
8. Soak: at least 4 hours and 500 completed turns for each finalist pair, including
   at least 100 tool cycles and 10 extended sessions. Both duration and counts
   must be met. Longer overnight testing is a separate explicitly scheduled run.

## Proposed promotion criteria

- Zero OOM, GPU Xid, backend crashes, unexpected service restarts, silent fallback,
  stuck streams, or false context-overflow errors on in-budget test requests.
- 100% passing deterministic protocol fixtures; >=95% passing scored tool tasks.
- Correctness measured independently of model self-reported success.
- Record p50/p95 time to first visible output, total latency, prompt processing,
  decode throughput, peak VRAM/RAM, temperature and restart counters.
- Provisional interactive short-task target: p95 first visible output <=10 s and
  p95 completion <=30 s at low concurrency. Report cold/long prompts separately;
  never improve latency by silently disabling required reasoning or shrinking tests.
- Maintain memory headroom under measured peak load; idle VRAM is not enough.
- Stop on hardware errors or repeated service failure; preserve evidence and
  restore only through the supported control path. No automatic destructive cleanup.

Any change to quantization, context, parser, runtime or profile invalidates the
affected qualification results and requires rerunning relevant stages.

## Initial observations

Read-only `/v1/models` probes on ports 8082 and 8083 report respectively 32768
and 131072 context, both Q4_K Medium. Idle VRAM usage: Logic 20023 MiB,
Oracle 63104 MiB, worker 4904 MiB. These are not peak measurements.

Initial OpenClaw no-tool baseline requests are tracked separately from tool and
soak qualification. A greeting or marker response cannot satisfy this plan.

### Completed baseline probes (not qualification)

Executed `openclaw agent --agent main --session-id <dedicated-id> --model
sovereign/<route> --timeout 90 --json`, without `--deliver`, for each route.
Model overrides were confirmed by effective-model receipts, no fallback used.

| Test | Logic | Oracle |
|---|---|---|
| Reply BASELINE_OK, no tools | Passed, 8761 ms | Passed, 31538 ms |
| Call session_status once, report actual model | Real tool call + toolResult + final answer, 27560 ms | FAILED: narrated a call and invented JSON; no toolCall/toolResult, 24927 ms |

Transcript evidence: dedicated sessions `reliability-baseline-20260924-logic`
and `reliability-baseline-20260924-oracle` in the main agent SQLite store.
Logic seq 10 is session_status toolCall, seq 11 toolResult, seq 13 final answer.
Oracle seq 7 contains only thinking/text, including a fabricated version 1.0.0.
The CLI returned status=ok for BOTH: transport success is not task success.

Logic's receipt successfulToolNames was empty despite the verified tool result:
cross-check transcripts, do not use that summary field as sole execution proof.
Logic also recorded compaction events at seq 8 and 12 in this tiny session;
the initial request reported 24398 input tokens and the tool continuation 25182.
Runtime-event turns appeared after replies. Their contribution and token accounting
need investigation; do not attribute these counts to old conversation pollution
without evidence. Oracle initial usage was 8981 input / 612 output tokens.

Research update: ggml-org/Qwen3.8-27B-GGUF currently provides a Q4_K_M artifact
of 18973870528 bytes and Q8_0 of 28595763648 bytes. Q4 is the initial Logic
candidate, not Q8 with inadequate long-context headroom. No download started.

Next: reproduce the Oracle tool fixture directly at port 8083 and via 8787
to distinguish model/template behavior from gateway serialization. Audit Logic
prompt/reserve/compaction accounting before attempting a larger context. Then
qualify replacement artifacts through the same fixtures before soak testing.
