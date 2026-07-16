# SDD-722 — the trace→dataset curator (E0444: success examples → training data) (IMPLEMENTATION)

> Status: **active — curator shipped** (runs in CI; the trace *source* wiring is the remaining runtime step)
> Owner: operator-directed 2026-07-16 (verbatim: *"go"*) — continue the M046 loop upstream after SDD-721
> landed the training producer. Addresses the E0444 "trace → success/failure examples → curated dataset"
> pipeline the foundry named as its own producer.
> Mandate module: **E11.M722**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## The gap this closes

SDD-721 added the training producer (`adapter-train.py`) but assumes a `--dataset` already exists. Where does
that dataset come from? E0444: *"trace → success/failure examples → curated dataset"*. Nothing produced it —
so the loop had a hole on the **input** side, symmetric to the training hole SDD-721 closed on the output side:

    traces → **DATASET (this)** → TRAIN (SDD-721) → register → MS041 gate → transport (SDD-716) → serve `--lora`

## What this delivers

- **NEW `scripts/inference/adapter-dataset.py`** — a **curator** (a real producer, not a planner: curation is
  pure I/O, so unlike GPU training it **runs in CI**). `curate <id> --traces <log.jsonl> [--out <path>]
  [--label success|all] [--min-turns N]` reads a JSONL **trace log** (one agentic interaction per line —
  `{"messages":[…], "outcome": …, "goal": …}`) and writes a curated JSONL **dataset** in chat format
  (`{"messages":[…]}`) that unsloth/TRL consume as `--dataset`. **DRY-RUN by default** (reports kept/dropped +
  reasons + previews the first example); `--apply` writes to `--out` (default
  `/var/lib/sovereign-os/adapters/<id>/dataset/train.jsonl`). Stdlib-only.
- **The success label is the goal loop's own completion token.** A trajectory is a positive example when
  `outcome == "success"` **OR** its final assistant message carries `DONE_SENTINEL` — imported from
  `goal-driver.py` (SDD-719). So "the `/goal` loop said it finished" *is* the training label; no separate oracle
  is invented. The sentinel is **stripped from the emitted target** so the model learns the behaviour, not the
  token.
- **Curation rails**: drop interactions shorter than `--min-turns` (default 2), drop ones with no assistant
  reply, **dedup** identical message sequences (SHA-256 over the cleaned messages). `--label all` keeps
  failures too, tagged `label: success|failure`, for contrastive/DPO-style datasets later.
- **NEW contract lint** `tests/lint/test_adapter_dataset_contract.py` (8): present/executable/stdlib; reuses
  the goal-driver sentinel; success-filter + dedup + too-short drop; sentinel stripped from the target; `all`
  includes failures; DRY-RUN default vs `--apply` writes.

## Why the goal loop's sentinel is the right label

The `/goal` self-loop (SDD-719) already ends a completed trajectory with `[[GOAL_DONE]]` — that is the system's
*own* signal that a goal was achieved. Reusing it as the success label means the training data is curated from
exactly the trajectories the agent itself judged complete, with zero new labelling machinery. It also keeps the
two halves coherent: the loop that *pursues* goals (SDD-719) feeds the curator that *learns* from the ones it
finished (this), which feeds the trainer (SDD-721) that produces the adapter that makes the next loop better.

## Verification

- `pytest tests/lint/test_adapter_dataset_contract.py` — 8 passed. Functional (real, in CI): 5 fixture traces →
  2 kept in `success` mode (dedup collapses the two identical successes + the explicit `outcome:success`; the
  failure and the too-short line dropped), sentinel stripped from the target; `--apply` writes the JSONL and
  `adapter-train.py plan … --dataset <that file>` consumes it unchanged.
- Full `tests/` + ruff green; `context.md` sdd count bumped.
- **Not runtime-verified**: the gateway/goal-loop does not yet *persist* traces to a defined log — the curator
  reads the shape they emit. Wiring the trace sink is the follow-up (below).

## Non-goals (follow-ups)

- **The trace sink** — persisting agentic interactions (gateway `/v1/chat/completions` + goal-loop passes) to
  a JSONL log the curator reads. This SDD fixes the *format contract*; writing the log is a runtime change.
- **Weighting / balancing / DPO pairs** — `--label all` emits the raw labelled set; turning failures into
  rejected-completion pairs is a later curation mode.
- **The GPU-side trainer** (`train/unsloth-lora.py`, SDD-721 non-goal) and **real gate-producers**
  (adapter-gate scores) remain SAIN-01-side / Stage-4.
- **`sovereign-osctl adapter-dataset` verb** (§1g ladder) — the standalone curator lands first, like
  `adapter-transport` / `adapter-train`.
