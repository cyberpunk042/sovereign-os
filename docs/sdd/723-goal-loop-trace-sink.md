# SDD-723 — the goal-loop trace sink (the M046 trace source) (IMPLEMENTATION)

> Status: **active — trace sink shipped**
> Owner: operator-directed 2026-07-16 (verbatim: *"go"*) — close the last software gap in the M046 loop after
> SDD-721 (train) + SDD-722 (dataset) landed the producers. Addresses SDD-722's named follow-up: *"the trace
> sink — persisting agentic interactions … to a JSONL log the curator reads."*
> Mandate module: **E11.M723**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## The gap this closes

SDD-722 (the curator) reads a JSONL **trace log** but nothing wrote one — the curator only had fixtures. The
loop's input was a *format contract* with no producer. This ships the producer, closing the loop's last
software gap:

    **traces (this) → dataset (SDD-722) → train (SDD-721) → register → gate → transport → serve `--lora`**

## Where the sink belongs — the goal loop, not the raw daemon

The natural trace source is **`goal-driver.py`'s loop** (SDD-719), for three reasons:

1. **Success/failure is already known there.** The loop terminates `done` (goal achieved) or `paused` (capped /
   stuck) — so the training label falls out of the terminal state (`done → success`, else `failure`) with no
   separate oracle. This is the same signal the curator keys on (the `[[GOAL_DONE]]` sentinel), now produced at
   the source.
2. **It's the trajectory that matters.** A whole goal pursuit — the alternating prompt/reply across iterations —
   is one coherent training example. The loop already holds it.
3. **No daemon rebuild.** Keeping the sink in the Python loop (not the Rust gatewayd `/v1/chat/completions`
   path) means it's stdlib-only and **fully CI-testable** with the scripted responder — no model, no daemon, no
   GPU. (The raw-API-call sink in gatewayd remains a possible future source; the goal loop is the high-value one
   because its traces are labelled by construction.)

## What this delivers

- **`goal-driver.py` `run_loop(..., trace_sink=None)`** — the loop now accumulates the trajectory (`messages`:
  user prompt + assistant reply per iteration) and, at termination, emits **one record** through an injected
  `trace_sink` (same injection pattern as `Responder`): `{"messages":[…], "outcome": "success"|"failure",
  "goal": <text>, "iterations": N, "stop_reason": …}` — exactly the shape `adapter-dataset.py` curates. A run
  that never took a step (no active goal) emits nothing.
- **`append_trace()` + `file_trace_sink()`** — the real sink appends to the trace log (`SOVEREIGN_OS_TRACE_LOG`,
  default `/var/lib/sovereign-os/traces/agentic.jsonl`), **bounded** (keeps the last `SOVEREIGN_OS_TRACE_MAX_LINES`,
  default 10 000 — an always-on loop can't grow it unbounded) and **atomic** (`os.replace`, like goal-ctl's state
  write — a crashed write never corrupts the log). CLI `run` wires it by default; `--no-trace` opts out.
- **NEW contract lint** `tests/lint/test_trace_sink_contract.py` (5): trajectory emitted with alternating roles;
  done→success / paused→failure; the record curates cleanly through `adapter-dataset.py` (sentinel stripped);
  `append_trace` bounded + atomic; `trace_sink=None` emits nothing; stdlib-only.

## Verification

- `pytest tests/lint/test_trace_sink_contract.py` — 5 passed; `tests/lint/test_goal_lock_contract.py` — 8
  passed (the `run_loop` signature change is backward-compatible: `trace_sink` defaults to `None`).
- **End-to-end (real, in CI)**: a scripted 2-step goal run → `file_trace_sink` writes the trajectory to the log
  → `adapter-dataset.py curate` reads that log and keeps it as one success example (sentinel stripped) →
  `adapter-train.py plan … --dataset <log>` consumes it. The M046 loop runs from a live goal pursuit all the way
  to a training-ready dataset without a single fixture.
- Full `tests/` + ruff green; `context.md` sdd count bumped.

## Non-goals (follow-ups)

- **The gatewayd raw-API sink** — persisting non-goal `/v1/chat/completions` turns. Lower value (unlabelled) and
  needs a daemon change; the goal loop's labelled traces are the training-worthy ones.
- **Trace redaction / PII scrubbing** before training — a curation concern (`adapter-dataset.py`), tracked there.
- **Log rotation to cold storage** beyond the in-file `max_lines` bound.
- **The GPU trainer** (SDD-721) and **real gate-producers** — SAIN-01-side / Stage-4, unchanged.
