# SDD-724 — the adapter eval runner (the MS041 eval gate-producer) (IMPLEMENTATION)

> Status: **active — eval runner shipped** (the served-model query is the SAIN-01-side step; scoring/record are CI)
> Owner: operator-directed 2026-07-16 (verbatim: *"go"*) — after SDD-721/722/723 closed the loop's data spine,
> make the **MS041 eval gate reachable from real evidence**. Addresses the standing "real gate-producers"
> follow-up named across SDD-721/722/723.
> Mandate module: **E11.M724**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## The gap this closes

`adapter-gate.py`'s eval gate (`_eval_evidence`) filters `evals.jsonl` for a **passing** eval record for the
adapter and — per SB-077 (never fabricate) — **honest-defers** with *"run `sovereign-osctl models eval run <id>`
first"* when none exists. That runner didn't exist: the eval gate could never pass from real evidence, only from
an operator/stub record. This ships the producer:

    train (SDD-721) → register → **eval (this) → adapter-gate eval** → snapshot → human/oracle → promote

## What this delivers

- **NEW `scripts/inference/adapter-eval.py`** — runs a **benchmark suite** (JSONL: `{"prompt", "expect",
  "grader": contains|exact|regex}` per line) against a served adapter and writes the eval-run record the gate
  reads. Split like the rest of the foundry: **the only hardware-gated step is querying the served adapter**
  (`/v1/chat/completions`); grading, scoring, and record-assembly are pure and **CI-tested** via an injected
  `Responder` (real = HTTP to the daemon; tests = a scripted responder, no model). **DRY-RUN by default**
  (computes the score + previews the record); `--apply` appends the record.
- **The pass rule is the gate's own rule.** `passed = score ≥ threshold`, and the record carries
  `gate_agrees = (eval_tracker._passed(record) == passed)` — the runner reuses `eval-tracker._passed` itself, so
  the runner and the MS041 gate can **never disagree** on whether an eval passed. The record is written in
  `eval-tracker.py`'s exact shape (`task`/`suite`/`intervention_class`/`model`/`score`/`passed`/`adapter_id`/…),
  so it lands on the **D-10 dashboard** and is discoverable by the gate's `_eval_evidence` in one write.
- **Bounded + atomic** append to the eval store (`SOVEREIGN_OS_EVAL_STORE`, default
  `/var/log/sovereign-os/evals.jsonl`), trimmed to `eval-tracker.MAX_RUNS` so an always-on eval loop can't grow
  it unbounded.
- **NEW contract lint** `tests/lint/test_adapter_eval_contract.py` (7): present/executable/stdlib; reuses
  eval-tracker; the three graders (bad regex fails safe); score = fraction passed + `gate_agrees`; below-
  threshold fails; the written record is discoverable by `eval-tracker.load_runs` + `_passed` for the adapter
  (exactly the gate's evidence path); bounded + atomic append.

## Why a runner that reuses the gate's pass rule

The foundry's discipline is SB-077: a gate is never `passed` without proof. The risk in a *separate* eval runner
is that it computes "pass" one way and the gate reads "pass" another — a silent disagreement that either blocks a
good adapter or (worse) advances a bad one. Reusing `eval-tracker._passed` as the single criterion, and asserting
`gate_agrees` in the record itself, makes the producer and the consumer provably consistent. The runner produces
the evidence; the gate still independently reads and verifies it — but they share one definition of "passed".

## Verification

- `pytest tests/lint/test_adapter_eval_contract.py` — 7 passed. **End-to-end (real, in CI)**: a scripted 3-item
  suite (2 right, 1 wrong) → score 0.667 ≥ 0.5 → `passed`, `gate_agrees` true → `append_record` writes it →
  `eval-tracker.load_runs` + `_passed` find it as a passing run for the adapter (the gate's own `_eval_evidence`
  path). A 0/4 suite → `passed` false, still `gate_agrees`.
- Full `tests/` + ruff green; `context.md` sdd count bumped.
- **Not hardware-verified**: a real benchmark run against a *served* adapter (needs the model + GPUs). The
  scoring, grading, gate-agreement, record shape, and store discovery are proven with the scripted responder.

## Non-goals (follow-ups)

- **The GPU-served eval** — the actual `/v1/chat/completions` calls against a loaded `--lora` adapter on SAIN-01.
- **Richer graders** — LLM-as-judge / semantic / rubric scoring (the `oracle` gate is the judge path; this is
  the deterministic-grader path).
- **A curated benchmark suite** — this runs whatever suite it's given; assembling the ecosystem's standard
  suites is its own artifact.
- **`sovereign-osctl adapters eval run` wiring** (§1g ladder) — the gate's honest-defer already *names* that
  verb; the standalone runner lands first, the osctl verb + dashboard follow.
