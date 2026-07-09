# SDD-059 — M028 memory forget/undo (the memory-entry store + soft-delete + undo for D-07)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: none (SDD-052 Stage 3 — the deferred destructive/reversal memory ops)
> Derived from: operator directive 2026-07-08 (chose M028 memory forget/undo after SDD-058's M057 runtime merged in PR #36); SDD-052 (memory-change authority — the approve/reject sign-off; forget/undo were deferred); M028 Memory OS (8 types, 11-stage lifecycle); R10184 forget / R10185 undo.

## Mission

Implement the deferred D-07 destructive/reversal ops: `forget` (R10184 — delete a
memory) + `undo` (R10185 — reverse a change). SDD-052 refused `forget` and deferred
`undo` because the M028 projection has no addressable memory-entry store and no
change-ledger (SB-077 — no speculative store). This builds that minimal store +
ledger and the two ops on top.

## Problem

- M028 = 8 memory types + an 11-stage lifecycle, but `/run/sovereign-os/memory.json`
  is only the **aggregate projection** (counts / lifecycle / diffs / pending queue)
  — no per-entry store keyed by a `mem-id`, no change-ledger. So `forget <mem-id>`
  had nothing to delete and `undo` had nothing to reverse.
- The D-07 forget/undo buttons are honest-deferred toasts (SDD-052).

## Required coverage

### The M028 store + change-ledger (`scripts/intelligence/memory-store.py`)

- **store** `/var/lib/sovereign-os/memory/store.json` —
  `{entries:{<mem-id>:{id,type,stage,summary,state,created,updated}}}` — the
  addressable M028 entries. A minimal `register --type N` producer seeds them (the
  real M028 admission-lifecycle producer is Stage N).
- **change-ledger** `/var/lib/sovereign-os/memory/changes.json` —
  `{changes:[{id,op,mem_id,prev,ts,reversed}]}` — the reversible ledger `undo`
  reads/marks.

### forget — soft-delete, refuse-by-default (R10184)

`forget(mem_id, --force)` — **REFUSE-by-default**: `--force` is a CLI-only
escalation (SDD-052 Q-052-B); the cockpit `memory-forget` control (change_cli has
no `--force`) always refuses with a CLI remediation. With `--force` it
**SOFT-DELETES** (tombstone `state:forgotten` + ledger the prior state) — it NEVER
hard-removes (Q-059-A), so `undo` can always restore (the retention purge is Stage
N, Q-059-C).

### undo — reverse a change (R10185)

`undo(change_id)` — reverse a ledger change (for `forget`, restore the tombstoned
entry to `active`) + mark the change `reversed`. A normal (non-destructive)
operation.

### The controls

- `memory-forget` — `sovereign-osctl memory-changes forget <id> --confirm`,
  privileged, refuse-without-force (Q-059-B; the description documents the CLI
  `--force`). `applies_to: [d-07-memory-changes]`.
- `memory-undo` — `sovereign-osctl memory-changes undo <id> --confirm`, privileged.
  `applies_to: [d-07-memory-changes]`.
- Registry 28→30, local 26→28.

### store ↔ projection decoupling

The store is decoupled from the `memory.json` projection now — forgetting an entry
does not yet update the projection counts (the real M028 producer reconciles them,
Q-059-D/E — Stage N). Documented, not speculatively refactored. `memory-changes.py`
stays a pure reader; `memory-changes-api.py` stays 405.

## Goals

- A real, testable M028 memory-entry store + reversible change-ledger + forget/undo.
- Reuse the `memory-decide.py` writer pattern; keep `memory-changes.py` pure.
- R10212 + destructive-op safety: forget refuse-by-default + `--force` CLI-only +
  soft-delete (undo always restores).

## Non-goals (Stage N / follow-up)

- The real M028 **admission-lifecycle producer** (populates the store from the
  11-stage pipeline + reconciles the projection counts).
- The tombstone **purge** (retention window); a d-07 **memory-entry list** view
  (surface `mem-<id>`s to forget).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-059-A | forget delete model. | **answered (operator, 2026-07-08): soft-delete (tombstone) + retention — undo restores; a later purge hard-removes.** |
| Q-059-B | forget surface. | **answered (operator, 2026-07-08): a `memory-forget` control that refuses without `--force` (CLI-only override).** |
| Q-059-C | Retention / purge window. | **answered (SDD-060, 2026-07-09): a CLI-only `memory-changes purge --older-than Nd --confirm` maintenance verb hard-removes `state:forgotten` tombstones past the window (30d default) + marks the ledger change `purged`; `undo` gains a purged-guard. Not a cockpit control (irreversible).** |
| Q-059-D | store ↔ memory.json projection reconciliation. | **proposed: the real M028 producer — Stage N.** |
| Q-059-E | The real admission-lifecycle producer. | **answered (SDD-064, 2026-07-09): `scripts/intelligence/memory-admit.py` — the admission ENGINE (`admit` value-gates the 8 store-if/5 ignore-if triggers, mints at stage `observe`; `advance` walks the 11-stage lifecycle) + `memory-store.reconcile()` recomputes the memory.json projection FROM the store. GROUNDED (SB-077): observations are CLI/fixture-fed — no real memory source exists yet; the auto-observation event stream is a further Stage-N.** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `scripts/intelligence/memory-store.py` (store + ledger + forget/undo/
  register) + `tests/unit/test_memory_store.py`.
- **Stage 2:** the 2 controls + the `memory-changes)` osctl forget/undo/register
  sub-verbs + sudoers + lint bumps (28→30) + d-07 forget/undo button re-wire.
- **Stage N (follow-up):** the admission-lifecycle producer; purge; entry-list view.

## Safety invariants

`forget` refuse-by-default + `--force` CLI-only + soft-delete (tombstone, never
hard-remove — undo always restores); DRY-RUN-default + operator-key + type-to-
confirm; selfdef/perimeter untouched + store paths free of selfdef/tetragon;
`memory-changes-api.py` stays read-only (405); ids `_SAFE_ID`-validated; atomic
store write + reversible ledger + OCSF-5001 span; MS003 `unsigned-pending-MS003`.
The store write is the only host mutation, gated by the exec rail + sudoers.

## Cross-references

- `scripts/intelligence/memory-changes.py` — the reader (untouched; stays pure).
- `scripts/intelligence/memory-decide.py` (SDD-052) — the writer template.
- `scripts/operator/memory-changes-api.py` — read-only daemon (stays 405).
- `scripts/sovereign-osctl` — the `memory-changes)` arm (forget/undo/register dispatch).
- `scripts/operator/_action_exec.py` / `control-exec-api.py` — the exec rail.
- `config/control-systems.yaml` — the 28 controls (model the 2 new on memory-decide).
- SDD-052 (memory-change authority — the parent), M028 Memory OS, R10184/R10185.
