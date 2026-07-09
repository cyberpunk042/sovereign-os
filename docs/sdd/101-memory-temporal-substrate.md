# SDD-101 — Memory-OS temporal substrate (`contradicts` edge-kind + `verified_at`)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: SDD-068 Q-068-E (the `contradicts` edge-kind + `verified_at` timestamp half) — turns the RLM navigator's `contradicted-by` + timestamped `last-verified` verbs from honest-defer into real answers
> Derived from: operator directive 2026-07-09 (chose the Memory-OS temporal substrate after SDD-100 merged in PR #54); picked deterministic candidate-pairing + SLM confirmation (honest-defer) for contradiction detection; M028 Memory OS (M00469 temporal verbs); SDD-066 janitor + SDD-068 navigator + SDD-071 sweep; SB-077. First entry in the recover-projects band (SDD-101 / E11.M101, per SDD-100).

## Mission

Close the last honest-defer in the Memory OS. SDD-068 (RLM navigator) folded in the M00469
temporal query verbs, but two of them still return **honest-defer** because the store lacks
their substrate: `last-verified` reports only the `verified` bool (no `verified_at` timestamp),
and `contradicted-by` defers/empty (edges are `kind:"related"` only — no `contradicts` edge).
Build both substrates so those verbs return **real** answers — the tight completion of the
Memory-OS query side.

## Problem

- `memory-navigate.py` `_temporal()` `last-verified` branch: filters `verified is True` but
  reports "no verified_at timestamp exists in the store … reports verified-ness, not a
  verification time (honest partial substrate, SB-077)".
- `_temporal()` `contradicted-by` branch: `{deferred:True, entries:[], reason:"no contradiction
  edges in store (edges are kind:'related' only); a `contradicts` edge-kind is Stage-N"}`.

## Grounded design

The M028 contract locks only the temporal-verb *list* (5 verbs, order) + the MemoryItem *field
names* (`time_range` is spec-only) — neither locks a `contradicts` edge-kind or a `verified_at`
field, so **no contract yaml change**. The janitor sets `verified:true` in the `verify` stage
effect (`_STAGE_EFFECT["verify"]`) + the SDD-071 sweep's at-stop verify effect; edges are
written by `_add_edge` as `{"to":dst,"kind":"related"}`.

- **`verified_at` (deterministic).** Where the janitor writes `verified:true`, also write
  `verified_at: <_now()>` (additive; no existing shape changes).

- **`contradicts` edge-kind — a NEW `contradict` janitor job** (the substrate producer for the
  contract's M00469 `contradicted-by` verb; NOT a fabricated 8th M00473 job):
  1. **Deterministic candidate-pairing** — active pairs sharing a `topic` (or a tag/token
     overlap) are contradiction candidates (same subject, possibly opposing).
  2. **SLM confirmation (honest-defer per SB-077)** — one bounded `_slm` call per candidate
     ("Do these two memories contradict each other? Answer yes or no.\n<A>\n<B>") → on "yes",
     write a bidirectional `edges:[{to,kind:"contradicts"}]`; an unreachable router → honest-
     defer (no edge, never fabricated). Mirrors the janitor's deterministic-candidate +
     SLM-judge pattern. Idempotent (existing `contradicts` edge not re-added). Folded into
     `sweep` (after `edges`; deterministic pairing always runs, the SLM confirm honest-defers).

- **Navigator temporal verbs consume the real substrate** (`_temporal`):
  - `last-verified` → filter `verified is True`, **sort by `verified_at` desc**, report the
    real timestamp (drop the caveat).
  - `contradicted-by` → return active entries carrying a `contradicts` edge (optionally to a
    target via `--at <mem-id>`); a **real** result (empty when there genuinely are none, honest
    — not "substrate absent").

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-101-A | Contradiction detection method. | **answered (operator, 2026-07-09): deterministic candidate-pairing (shared topic/tags) + SLM confirmation, honest-defer when the router is unreachable — matches the janitor's deterministic+SLM pattern + the operator's prior "deterministic + SLM" sweep pick.** |
| Q-101-B | `verified_at` source. | **answered: `_now()` at the janitor's verify effect — the only place `verified` is set.** |
| Q-101-C | `contradicted-by` with no substrate yet. | **answered: return the real (possibly empty) contradicts-edge set; the store is honestly empty of contradictions until a router-backed sweep runs.** |
| Q-101-D | An embeddings-backed contradiction judge + a `time_range` materialization (the MemoryItem spec field). | **proposed: Stage-N (needs a vector backend).** |

## Non-goals (Stage N)

- An embeddings/vector-backed contradiction judge (the deterministic-pair + SLM-confirm is this
  increment).
- Materialising the MemoryItem `time_range` uint64 field (spec-only; needs the bitset substrate).
- Auto-resolving contradictions (flagging one side stale) — the edge is informational.

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 101 + mandate E11.M101; flip SDD-068 Q-068-E.
- **Stage 1:** `verified_at` + the `contradict` job + the navigator verb upgrades + tests.
- **Stage 2:** the osctl `janitor contradict` routing (arm comment) + e2e.

## Safety invariants

Additive fields only (`verified_at`, `contradicts` edge-kind) — no existing entry shape
changes; **no contract yaml change** (the verb list + MemoryItem field names are locked-
unchanged). The `contradict` job mutates the store → **CLI/timer-only** (via the sweep/janitor
arm), never a web control (R10212). **SB-077 honest-defer** — the SLM contradiction-confirm
writes no edge when the loopback router is unreachable; never fabricates a contradiction.
Idempotent (existing edges not re-added). The navigator stays a read-compute (byte-identical
store after a navigate). MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/intelligence/memory-janitor.py` (SDD-066/071) — `_STAGE_EFFECT["verify"]`,
  `_add_edge`/`_related_pairs`, `_slm`, `sweep`.
- `scripts/intelligence/memory-navigate.py` (SDD-068) — `_temporal()` (the two verb branches).
- `config/agent/m028-memory-os.yaml` / `tests/lint/test_m028_memory_os.py` — the M00469
  `temporal_query_verbs` list + MemoryItem fields (locked, unchanged).
- SDD-068 (navigator + temporal verbs), SDD-071 (sweep), M028 milestone (M00469).
