# SDD-060 — M028 memory-entry list view + tombstone purge (the D-07 Stage-N follow-up to SDD-059)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: none (SDD-059 Stage N — the deferred memory-entry list view + retention purge)
> Derived from: operator directive 2026-07-09 (chose the M028 list-view + purge follow-up after SDD-059's forget/undo merged in PR #37); SDD-059 (the memory-entry store + soft-delete forget/undo — Q-059-C proposed the purge, the entry-list view was a named non-goal); M028 Memory OS; R10184 forget / R10185 undo.

## Mission

Make the SDD-059 forget/undo actually usable + close the retention loop:

1. **A memory-entry LIST view for D-07** — surface the addressable `mem-<id>` entries
   so the operator can SEE which memories exist and target `forget` from the panel
   (today `forget <mem-id>` works but nothing shows the ids).
2. **The tombstone PURGE** — a retention sweep that hard-removes `state:forgotten`
   entries past a window (SDD-059 Q-059-C), closing the loop `forget` (soft-delete)
   deliberately left open.

## Problem

- SDD-059 built the store + `forget`/`undo`, but the D-07 panel renders only the
  aggregate projection (counts / 11-stage lifecycle / diffs / pending queue) + wires
  the forget/undo controls. There is **no addressable `mem-<id>` list** — the operator
  has nothing to forget *from* unless they already know an id. `store_list()` exists
  (`scripts/intelligence/memory-store.py`) but is surfaced nowhere.
- `forget` only ever tombstones (`state:forgotten`) so `undo` can always restore —
  **nothing hard-removes**, so tombstones accumulate unbounded. SDD-059 Q-059-C
  proposed a 30-day purge; it does not exist.

## Required coverage

### The memory-entry list view (read surface)

- **`GET /api/d-07/entries`** on `scripts/operator/memory-changes-api.py` →
  `{schema_version, entries: store_list()}`. The API importlib-loads
  `memory-store.py` (read-only use of `store_list()`) as a SECOND read source
  alongside the `memory-changes.py` projection core. `memory-changes.py` stays a
  **pure projection reader** (untouched); the entries come from the *store*, honestly
  reflecting the SDD-059 store↔projection decoupling. The API stays read-only —
  mutations remain 405.
- **D-07 panel entry table** (`webapp/d-07-memory-changes/index.html`) — a new
  "M028 memory entries" table (mem-id · type · stage · state · summary · updated) fed
  by a new `loadEntries()` fetching `/api/d-07/entries` (offline-safe empty default).
  Each `active` row carries a **forget** button → `jumpToControl('memory-forget',
  row.id)`; `jumpToControl(cid, prefill)` best-effort populates the target control
  card's id input so the operator lands on the wired control with the id filled (the
  list works without prefill if the card shape differs — a guarded enhancement).

### The tombstone purge (CLI-only maintenance verb)

`purge(older_than_days=30, --confirm)` in `memory-store.py` — hard-removes
`state:forgotten` entries whose `updated` is older than the retention window (30d
default, `--older-than N` override), and marks each entry's non-reversed ledger
forget-change `purged: true` + `purged_ts` (the ledger is the audit record — never
deleted from). DRY-RUN unless `--confirm` AND `SOVEREIGN_OS_DRY_RUN` unset; the
DRY-RUN returns the would-purge list and removes nothing. It **only** touches
`state:forgotten` entries past the window — `active` entries and within-window
tombstones are never removed.

Purge is a **CLI-only maintenance verb, NOT a cockpit control** (Q-060-A): a purge is
IRREVERSIBLE — once an entry is hard-removed, `undo` can no longer restore it — so it
is strictly more dangerous than `forget` (which merely refuses from the web). By the
same destructive-op doctrine that keeps `sessions start` CLI-only (SDD-058), purge is
not web-triggerable at all: no `control-systems.yaml` entry, no cockpit sudoers grant,
registry stays 30. It runs as `sovereign-osctl memory-changes purge --older-than Nd
--confirm`.

### The undo purged-guard

`undo(change_id)` gains a guard after the `reversed` check: if the resolved ledger
change has `purged` truthy → reject (code 2) "change {id} was purged (retention);
cannot restore". This keeps `undo` honest once a forgotten entry has been purged.

### store ↔ projection decoupling (unchanged)

Still standing from SDD-059: the store is decoupled from the `memory.json`
projection — neither forget nor purge reconciles the projection counts (the real M028
admission-lifecycle producer does that — Q-059-E / Q-060-D, Stage N). Documented, not
speculatively refactored.

## Goals

- A read-only entry-list surface (endpoint + panel table + per-row forget prefill)
  that makes SDD-059's forget target-able from D-07.
- A tested, retention-bounded purge that closes the soft-delete loop without breaking
  undo's honesty (purged-guard) or the ledger's append-only audit trail.
- Reuse `store_list()` + the `_atomic_write`/`_emit_span`/`_SAFE_ID` helpers; keep
  `memory-changes.py` pure + `memory-changes-api.py` read-only.

## Non-goals (Stage N / follow-up)

- The real M028 **admission-lifecycle producer** (populates the store from the
  11-stage pipeline + reconciles the `memory.json` projection counts).
- A **purge scheduler / cron** (this ships the verb; wiring it to a timer is later).
- Richer entry filtering (by memory-type / MS039 trust dimension) in the list view.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-060-A | Purge surface — cockpit control vs CLI-only? | **answered (operator, 2026-07-09): CLI-only maintenance verb, NOT a control — a purge is irreversible (undo cannot restore a hard-removed entry), strictly more dangerous than forget, so it is not web-triggerable at all (matches the `sessions start` CLI-only doctrine).** |
| Q-060-B | Retention default / override. | **answered (operator, 2026-07-09): 30d default (SDD-059 Q-059-C), `--older-than N` override.** |
| Q-060-C | Entries source for the list. | **answered (operator, 2026-07-09): `store_list()` via a new `/api/d-07/entries` read endpoint; `memory-changes.py` stays a pure projection reader.** |
| Q-060-D | Reconcile the `memory.json` projection counts on forget/purge? | **answered (SDD-064, 2026-07-09): YES — `memory-store.reconcile()` recomputes memory.json counts+lifecycle FROM the store (preserving the memory-decide-owned pending/history), wired best-effort into forget/undo/purge/register + the admission engine. D-07's projection now reflects the real store.** |
| Q-060-E | A purge scheduler / cron timer. | **proposed: Stage N (this SDD ships the verb only).** |

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX + mandate E11.M27; flip SDD-059 Q-059-C.
- **Stage 1:** `memory-store.py` `purge()` + `undo` purged-guard + `purge` CLI
  subparser; extend `tests/unit/test_memory_store.py`.
- **Stage 2:** the `/api/d-07/entries` read endpoint + the `memory-changes)` osctl
  `purge` sub-verb + the d-07 entry-list table + `jumpToControl` prefill +
  `tests/lint/test_memory_changes_api_contract.py` entries test.
- **Stage N (follow-up):** the admission-lifecycle producer; a purge scheduler; entry
  filtering.

## Safety invariants

Purge is CLI-only + DRY-RUN default + `--confirm` + hard-remove restricted to
`state:forgotten` past the retention window (never `active`, never within-window);
the ledger stays append-only (purge marks `purged`, never deletes an audit row);
`undo` refuses purged changes; `memory-changes.py` stays a pure projection reader;
`memory-changes-api.py` stays read-only (a new GET only — mutations stay 405); ids
`_SAFE_ID`-validated; atomic store + ledger writes + OCSF-5001 span;
selfdef/perimeter untouched + store paths free of selfdef/tetragon; MS003
`unsigned-pending-MS003`; registry stays 30 (NO new control).

## Cross-references

- `scripts/intelligence/memory-store.py` (SDD-059) — the store + ledger + forget/undo;
  this SDD adds `purge()` + the `undo` purged-guard.
- `scripts/intelligence/memory-changes.py` — the projection reader (untouched; pure).
- `scripts/operator/memory-changes-api.py` — the read-only daemon (+ `/api/d-07/entries`).
- `scripts/sovereign-osctl` — the `memory-changes)` arm (+ `purge` dispatch).
- `webapp/d-07-memory-changes/index.html` — the D-07 panel (+ the entry-list table).
- SDD-059 (the parent — forget/undo + the store), SDD-052 (memory-change authority),
  M028 Memory OS, R10184 forget / R10185 undo (the purge is the retention sweep that
  bounds R10184's soft-delete tombstones — no separate requirement id).
