# OpenClaw sub-agent completion failure — 2026-10-02

## Incident and evidence

Parent dashboard `183a95a3-4769-4e25-af77-03621b706322`, session
`65f2d73a-43c9-489d-89c2-d27d96bf4fa1`; child dashboard
`398e9de4-732a-4ad5-a28a-7ac4df419641`, session
`6f39f53c-6f00-426c-9ec7-125fb7a2d134`.
Evidence: read-only OpenClaw SQLite transcripts and gateway/backend journals.
Times below are America/Toronto.

- 12:45:47: parent spawned the Science cockpit implementation child.
- Child performed one progress-card call, ten reads and twenty exec calls.
  The inspected commands were investigative; no implementation was observed.
- 13:07:37: parent yielded.
- 13:16:20: child produced **8192 output tokens, thinking only**, stop `length`.
  Input was approximately 73K including cached tokens, not a context overflow.
- OpenClaw attempted isolated finalization. At 13:20:25–26 that attempt also
  produced **8192 tokens, thinking only**, stop `length`.
- OpenClaw emitted its fallback: “The tool run finished, but no final summary
  was produced. I did not repeat any completed actions.”
- 13:22:26: parent settle wake exceeded the upstream 120-second deadline.
  The gateway logged `gateway request timeout for agent` and retried.
- Backend timings: first 8192-token decode 227.425s (36.02 tok/s), recovery
  decode 217.616s (37.64 tok/s), recovery prefill 26.583s.

This was an output-budget/recovery/delivery failure, not evidence of a GPU
crash. A successful tool invocation did not mean the requested UI was built.

## Bounded mitigation implemented

1. Profile synchronization fills missing Qwen3.8 local request budgets:
   Oracle `reasoning_budget_tokens=2048`; non-thinking Logic `=0`.
   Oracle still has its existing 8192-token total output cap. Explicit operator
   budget overrides are preserved. This trades unbounded internal deliberation
   for room to answer or call tools; it is not a larger context setting.
2. Only the restricted finalization attempt gets `thinkLevel=off`, template
   `enable_thinking=false`, and reasoning budget zero. Normal turns are not
   forced to non-thinking. Existing tool-disable, trajectory-disable and
   no-replay/persistence guards remain intact. Scope: sovereign Logic/Oracle
   with the managed reasoning-budget setting, not remote providers.
3. Supported OpenClaw configuration `agents.defaults.subagents.announceTimeoutMs`
   defaults to 600000ms for these local profiles when no operator value exists.
   This allows more time for local prefill/generation/queueing without adding
   retries or making the wait unbounded. It is a global subagent setting in
   OpenClaw, not a per-provider deadline.
4. Finalization compatibility patch is source-shape gated, backed up, idempotent,
   and reapplied on profile synchronization. Unknown upstream code fails closed.

No context, GPU placement, embedding/reranker allocation, workstation reboot,
or model-server restart. Only the OpenClaw gateway was reloaded.

## Verification

Targeted suite:

```text
python3 -m pytest -q tests/test_openclaw_completion_compat.py \
  tests/test_qwen38_sampling.py tests/test_openclaw_compaction_defaults.py \
  tests/test_openclaw_context_compat.py tests/test_qualify_openclaw.py \
  tests/test_request_diagnostics.py tests/lint/test_qwen_trial_profiles.py
23 passed in 0.99s
```

Tests cover preserved overrides, scope, idempotence, dry-run, backups, unknown
runtime rejection, and the actual installed restricted-attempt factory retaining
tool/no-replay guards while changing only the recovery request settings.

Real parent/child test (`python3 scripts/inference/qualify-openclaw-subagent.py`):

```json
{"passed":true,"elapsed_seconds":36.0,"parent_tools":["sessions_spawn","sessions_yield"],"child_tools":["read"],"errors":0,"length_stops":0,"child_returned_code":true,"parent_returned_code":true}
```

Parent `subagent-qualification-859aa4128c032992`; child
`agent:main:subagent:2aa66d70-158d-4833-ab81-e855df079d6b`.
Private evidence `/tmp/sovereign-subagent-qualification-pohv7_h7/report.json`.
The child read a generated random-code fixture; the parent received and reported
that exact code. No project edits, external delivery, or replay of the failed
Science task. Test sessions are retained for inspection.

Dual-route OpenClaw read-tool qualification (`--rounds 2`): **4/4 passed**,
12 successful reads, zero tool errors, no unexpected tools, no fallback,
zero compactions. Logic 18.68s / 18.28s; Oracle 35.74s / 24.51s.
Evidence `/tmp/sovereign-openclaw-qualification-6pusd3qe/summary.json`.

Profile-sync dry-run after application: `OpenClaw already in sync with profile
'qwen38-dual-agent-256k' — no change`. Oracle, Logic and OpenClaw services report
`ActiveState=active`, `NRestarts=0` after the tests.

Additional synthetic gateway request checks (explicit SSE parsing): a 32-token
reasoning budget produced 159 characters of reasoning followed by 1659 visible
characters. That request hit its deliberately small **512-token total cap**;
it verifies the thinking-to-answer transition, not successful task completion.
Recovery-mode request (`reasoning_budget_tokens=0`, template thinking disabled)
returned **425 visible characters, zero reasoning, `stop`, 2.47 seconds**.
The initial diagnostic assumed a JSON response; the live gateway returned SSE
even with `stream=false`, so the probe was corrected to parse SSE. This response
format discrepancy is separate from the sub-agent incident; OpenClaw uses SSE.
No claim is made that this synthetic request invokes OpenClaw's full recovery
state machine; that factory is covered by the installed-runtime test above.

## Remaining limits

These are bounded regression/smoke tests, not a long coding-task soak or proof
that every possible run completes. The exact incident's 8K thinking-only
failure was not replayed against the user's live task. The restricted recovery
factory is tested directly, while normal parent/child delivery is tested live.
Models can still fail, loop on tool choices, or exhaust a total runtime budget.
Long implementation tasks should be checked for actual artifacts and tests,
not just successful tools or a completion notification. Existing Science cockpit
edits were left untouched.
