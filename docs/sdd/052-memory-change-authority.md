# SDD-052 — Memory-change authority (functional approve / reject sign-off for D-07)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-08
> Closes findings: none (write half atop the D-07 read model + SDD-047 control surface)
> Derived from: operator directive 2026-07-08 (chose the D-07 memory-changes engine after SDD-051's adapter promotion authority merged in PR #29); SDD-048 (approval authority) + SDD-051 (adapter promotion authority) — the structural twins (registry/queue-overlay read model + decision-writer + MS003-deferred signature); SDD-047 (cockpit functional execution / R10274); M028 Memory OS (8 types, 11-stage admission lifecycle M00471, R10093-R10096); R10184 forget / R10185 undo.

## Mission

Make the D-07 memory-changes panel's pending-change sign-off — **approve** /
**reject** — functional as a sanctioned cockpit control on the SDD-047 R10274
rail. Today the buttons are neutralized (`emit()` copies nothing); the D-07 read
path (`memory-changes.py` + `memory-changes-api.py`) is complete, but the write
half — the authority that transitions the pending-change queue — is greenfield.

## Problem

The D-07 pending-change buttons (approve/reject) + the direct
promote/pin/forget/undo/snapshot buttons emit a fake `sovereignctl memory …`
(sovereign-osctl has no memory write verb). Structurally the pre-SDD-048/051 gap:

- **Read side complete.** `sovereign-osctl memory-changes {snapshot,types,lifecycle}`
  → `scripts/intelligence/memory-changes.py` projects the M028 Memory OS state
  (`/run/sovereign-os/memory.json`: 8 type counts, 11-stage lifecycle, graph
  diffs, and the `pending` queue `[{id, op, mtype, scope, delta, requester}]`).
  `memory-changes-api.py` serves `/api/d-07/snapshot` + `/stream`; writes → 405.
- **`pending` is the ONLY id-addressable structure.** There is NO per-memory-entry
  store keyed by memory-id — so the direct `promote/pin/forget <memory-id>` buttons
  have no backing store; inventing one would be speculative.
- **The DESIGNED flow is the sign-off queue.** Per the core docstring: "the queue
  of pending **promote/pin/forget** operations awaiting operator sign-off." So
  promote/pin are realized by **approving a pending change** whose `op` is
  promote/pin — exactly the approvals/adapters pattern.

## Required coverage

### approve / reject (sign-off, sovereign-os-owned)

- **approve** — apply a pending change's op. Scope this engine (Q-052-A) to the
  non-destructive ops (`promote`, `pin`): remove from `pending` + record. A pending
  **`forget`** (R10184, destructive) is **REFUSED** (Stage 3; refuse-by-default,
  the override is a logged CLI `--force`, Q-052-B).
- **reject** — discard a pending change (any op — discarding is not deleting
  memory).
- Each decision removes the change from `pending`, appends a `history` entry, and
  records `signature: "unsigned-pending-MS003"`. **R10212 ownership**: the M028
  Memory OS is sovereign-os-owned (doctrine: "promote/pin/forget are … CLI
  verbs"); `memory-changes-api.py` stays read-only (405); write methods are
  CLI-dispatch-only.
- **No speculative store mutation.** approve/reject transition the `pending` queue
  + record the decision; the actual M028 memory-store effect (moving a memory to
  the `promote` stage, pinning it) is the producer's job (Stage 4) — exactly as
  approval-decide records a decision without performing the downstream transition.

### Decision-writer + producer

The writer lives in a NEW `scripts/intelligence/memory-decide.py` (keeps
`memory-changes.py` a pure reader — the API imports it and calls only
`snapshot()`), importing the reader's `MEMORY_STATE` / `_read_state` /
`_VALID_PENDING_OP` / `snapshot`. Atomic `os.replace` write; durable
`/var/log/sovereign-os/memory-decisions.jsonl` ledger; OCSF-5001 M049 span
(D-05/D-16). A minimal `request <op> --mtype` producer mints `mc-<hex>` pending
changes (the real M028 admission-lifecycle producers are Stage 4). (Web-exposed via the
R10274 exec-rail as the `memory-request` control as of **SDD-104** — the enqueue is an
unprivileged intent, distinct from the privileged `memory-decide` that signs it.)

### MS003 signing (deferred, per the SDD-048/051 precedent)

Signing delegated to selfdef; records `unsigned-pending-MS003` (no signing crypto
in sovereign-os — R10212). Presence-gated + type-to-confirm at the exec daemon.

### The control (mirrors approvals-decide / adapter-decide — one control, verb enum)

A single `memory-decide` control — `sovereign-osctl memory-changes
{approve|reject} <id> --confirm`, privileged, `applies_to: [d-07-memory-changes]`.
Registry 25→26, local 24→25 (`<id>` is a free `_SAFE_ID` change-id `mc-<hex>`).

## Goals

- Functional approve/reject via the sanctioned control-exec-api rail; one control
  auto-rendered on d-07.
- Reuse `memory-changes.py` (pure reader) + mirror `approval-decide.py`.
- R10212 preserved: selfdef/perimeter untouched; `state_path` free of
  selfdef/tetragon; `memory-changes-api.py` stays read-only (405).

## Non-goals (Stage 3 / follow-up)

- Direct `promote/pin/forget <memory-id>` ops (needs the M028 memory-entry store).
- **forget** (R10184 — refuse-by-default + `--force` CLI); **undo** (R10185 —
  needs a change-ledger); memory **snapshot**-before-edit.
- Real MS003 **signing** (selfdef) + real M028 gate/queue **producers**.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-052-A | Verb scope. | **answered (operator, 2026-07-08): approve/reject + queued promote/pin (applied via the sign-off queue); forget + undo deferred to Stage 3.** |
| Q-052-B | Destructive `forget` (R10184) gate. | **answered (operator, 2026-07-08): refuse-by-default + logged `--force` CLI-only (like the d-08 prune floor). Applied now: approving a pending `forget` is refused.** |
| Q-052-C | Direct `<memory-id>` promote/pin/forget ops. | **proposed: Stage 3 — needs the M028 memory-entry store (the projection is aggregate counts + the pending queue; no per-entry addressing).** |
| Q-052-D | promote-approve lifecycle-count reconciliation. | **proposed: record-only now (remove from pending + ledger); the M028 producer reconciles the 11-stage occupancy (Stage 4).** |
| Q-052-E | Real MS003 signing + real producers. | **proposed: Stage 4 — signature `unsigned-pending-MS003` until selfdef signs; the admission-lifecycle producer feeds the queue.** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `scripts/intelligence/memory-decide.py` (approve/reject + request) +
  `tests/unit/test_memory_decide.py`.
- **Stage 2:** the `memory-decide` control + the `memory-changes)` osctl read/write
  sub-case routing + sudoers + lint bumps (25→26) + honest d-07 button re-wire.
- **Stage 3 (follow-up):** direct memory-id ops, forget, undo, snapshot, real
  signing + producers.

## Safety invariants (every stage)

Privileged + operator-key + type-to-confirm + DRY-RUN-default; a pending `forget`
approve is refused (Stage 3); selfdef/perimeter untouched + `state_path` free of
selfdef/tetragon; `memory-changes-api.py` stays read-only (405); ids
`_SAFE_ID`-validated; atomic `memory.json` write + durable ledger + OCSF-5001
span; MS003 `unsigned-pending-MS003`. The pending-queue write is the only host
mutation, gated by the exec rail + sudoers; no speculative memory-store mutation.

## Cross-references

- `scripts/intelligence/memory-changes.py` — the D-07 reader (import its helpers;
  keep it a pure reader).
- `scripts/lifecycle/approval-decide.py` + `scripts/inference/adapter-decide.py` —
  the writer templates (this engine's twins).
- `scripts/operator/memory-changes-api.py` — read-only daemon (imported `_core`;
  stays 405).
- `scripts/sovereign-osctl` — the `memory-changes)` arm → read/write sub-case
  routing, mirroring `approvals)`.
- `scripts/operator/_action_exec.py` — the exec rail (`state_path` must avoid
  selfdef/tetragon; `_SAFE_VALUE` forbids `/`); `control-exec-api.py` — R10274 daemon.
- `config/control-systems.yaml` — the 25 controls (model the new one on
  approvals-decide / adapter-decide).
- SDD-048 (approval authority), SDD-051 (adapter promotion authority — the twins),
  SDD-047 (cockpit functional execution), SDD-050 (snapshot/rollback).
