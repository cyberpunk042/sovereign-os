# SDD-064 — M028 memory admission-lifecycle engine + projection reconcile (make D-07 real end-to-end)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: SDD-059 Q-059-E + SDD-060 Q-060-D (the deferred real M028 producer + projection reconciliation)
> Derived from: operator directive 2026-07-09 (chose the M028 admission producer after SDD-063 merged in PR #41; confirmed the scope = the admission ENGINE + projection reconcile, observations CLI-fed); M028 Memory OS (`config/agent/m028-memory-os.yaml`, milestone M028); R10184/R10185; SB-077.

## Mission

Make the D-07 memory subsystem operate on **real memories** — build the M028
admission-lifecycle **ENGINE** (value-driven admission gating + the 11-stage lifecycle)
and **reconcile** the D-07 projection (`memory.json` counts + lifecycle) FROM the store,
closing the SDD-059/060 decoupling gap.

## Problem

- SDD-059/060 built the store + forget/undo/purge, but the producer was a minimal
  `register()` stand-in ("Stage-1 minimal producer — the real M028 admission-lifecycle
  producer is Stage N"): it mints one active entry, hard-codes `stage:"store-raw"`, and
  nothing advances the 11 stages.
- `memory.json`'s aggregate `counts`/`lifecycle` (the D-07 tiles + 11-stage occupancy)
  are **always 0** — nothing writes them (`memory-decide.py` only writes `pending`/
  `history`). The store (`store.json`) and the projection (`memory.json`) are decoupled
  (Q-059-D/Q-060-D — left for "the real producer, Stage N").

## Grounded reality (SB-077) — no real memory source

There is **no real agent-memory SOURCE** in sovereign-os today: no memory graph, no
event stream, no memory mirror (the AICP `memory_extract.py` lives in another repo,
unwired). So the producer **cannot "populate from a real graph"** — there is none.
Per SB-077 the engine must NOT fabricate a source. Operator decision (2026-07-09):
build the **admission ENGINE fed by an `admit` verb** — observations are CLI/fixture-
supplied now; the auto-observation event-stream feed is a further **Stage-N** (like the
selfdef rules-mirror publisher crate, and like how `session-runtime.py` built the real
M057 producer without a pre-existing source). The ENGINE (value gating + lifecycle +
projection reconcile) is real.

## Required coverage

### `scripts/intelligence/memory-admit.py` — the admission engine (NEW)

Reuses the store `memory-store.py` already owns. Two verbs:

- **`admit(type, summary, --trigger <store-if> | --ignore <reason> [, --trust 0-100])`**
  — the M028 value gate (`config/agent/m028-memory-os.yaml` `admission_rules`, milestone
  R04674-R04686): the 8 **store-if** value triggers (`user-corrected / task-outcome /
  repeated-pattern / new-fact / tool-worked / model-mistake / high-value-reuse /
  preference`) ADMIT; the 5 **ignore-if** (`transient / low-trust / duplicate / noisy /
  unverified`), a trust below the floor (30), or a duplicate (same type+summary active)
  → **NOT stored** (`admitted:False`, a legitimate value-gated decision). Admitted →
  mint an entry at stage **`observe`** with `admitted_via`/`trust`/`value_score`.
- **`advance(mem-id)`** — walk the entry to the next of the 11 stages
  (`observe → classify → quarantine → link → score → store-raw → extract-facts → verify
  → promote → decay → archive`, M00471 verbatim); idempotent at `archive`.

DRY-RUN default; `_SAFE_ID`; OCSF-5001 span. Every admit/advance calls `reconcile()`.

### `scripts/intelligence/memory-store.py` — `reconcile()` (the Q-059-D/Q-060-D closure)

`reconcile()` recomputes `memory.json` `counts` (per the 8 memory types, active entries)
+ `lifecycle` (per-stage occupancy) FROM the store, via read-modify-write that
**PRESERVES** the `memory-decide.py`-owned fields (`pending`/`history`/`diffs`/
`profile`). Lock-free (reads the store + atomic-writes a DIFFERENT file). Wired
**best-effort** into `register`/`forget`/`undo`/`purge` (a read-only projection must
never break a store write) + exposed as a `reconcile` CLI verb.

### Wiring

`sovereign-osctl memory-changes {admit,advance}` → memory-admit.py; `{reconcile}` →
memory-store.py. **No D-07 webapp change** — the panel already renders `counts`/
`lifecycle` from the `memory-changes-api` snapshot; once `reconcile()` writes real
values, the tiles + 11-stage occupancy become real automatically.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-064-A | Producer scope. | **answered (operator, 2026-07-09): the admission ENGINE (value gating + 11-stage lifecycle) + projection reconcile.** |
| Q-064-B | Observation source. | **answered: CLI/fixture-fed now; the auto-observation event-stream feed is Stage-N — the engine never fabricates a source (SB-077).** |
| Q-064-C | The store-if trigger set. | **answered: the 8 value triggers (R04674-R04681); 5 ignore-if per the spec yaml; trust floor 30.** |
| Q-064-D | Reconcile ownership. | **answered: `memory-store.py` (owns the store↔projection), best-effort, preserves the memory-decide-owned fields.** |
| Q-064-E | The RLM navigator (M00472) + SLM janitor (M00473) + the real observation event stream. | **the SLM janitor (M00473) half answered (SDD-066, 2026-07-09): built as `memory-janitor.py` — 7 jobs, deterministic (dedup/edges/tag/advance-effects) + SLM-routed via the SDD-062 loopback engine (extract-facts/topic/summarize/classify), honest-defer per SB-077.** The RLM navigator (M00472) + the observation event stream remain **proposed: Stage-N.** |

## Non-goals (Stage N)

- The real **observation event stream** (auto-feeding admit from agent task history) —
  needs a source built/wired first (cross-repo, like the AICP extractor).
- The **RLM memory navigator** (query) + the **SLM memory janitor** (extract/dedup/
  topic/edges) maintenance jobs.
- The **MemoryItem** full 10-uint64 struct (the store entry is a minimal projection).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX + mandate E11.M31; flip Q-059-E/Q-060-D.
- **Stage 1:** `memory-store.py` `reconcile()` + wiring + `memory-admit.py` engine +
  `tests/unit/test_memory_admit.py` + `test_memory_store.py` reconcile tests.
- **Stage 2:** the osctl `memory-changes {admit,advance,reconcile}` routing + D-07 e2e.
- **Stage N:** the observation event stream; the RLM navigator + SLM janitor.

## Safety invariants

SB-077: never fabricates a memory source (observations CLI/fixture-fed; auto-feed
deferred); admission is value-gated (ignore-if / low-trust / duplicate rejected, NOT
stored). `reconcile()` is best-effort + PRESERVES the memory-decide-owned `memory.json`
fields (no data loss); `memory-changes.py` stays a pure projection reader (405 API);
the store entry shape (id/type/stage/summary/state/created/updated) + ledger are
unchanged (admission fields are additive); ids `_SAFE_ID`-validated; atomic writes +
OCSF-5001 span; DRY-RUN default; selfdef/perimeter untouched; MS003
`unsigned-pending-MS003`.

## Cross-references

- `config/agent/m028-memory-os.yaml` — the M028 contract (8 types, admission_rules, the
  11-stage lifecycle) the engine implements; locked by `tests/lint/test_m028_memory_os.py`.
- `scripts/intelligence/memory-store.py` (SDD-059/060) — the store + `reconcile()`.
- `scripts/intelligence/memory-changes.py` — the pure projection reader (`MEMORY_TYPES`/
  `LIFECYCLE_STAGES` — the reconcile target shape); unchanged.
- `scripts/intelligence/memory-decide.py` (SDD-052) — the `memory.json` pending/history
  writer whose fields reconcile preserves.
- SDD-059 (forget/undo), SDD-060 (list/purge), M028 milestone, R04674-R04698.
