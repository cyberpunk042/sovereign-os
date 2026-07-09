# SDD-068 — M028 RLM memory navigator (M00472) + M00469 temporal query verbs

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: M00472 / R04699-R04708 (the RLM memory navigator) + M00469 / R04687-R04698 temporal query verbs (E0263); SDD-064 Q-064-E navigator half
> Derived from: operator directive 2026-07-09 (chose the M028 RLM navigator after SDD-066 merged in PR #45; picked "we do not minimize" → CLI + read-only D-07 web endpoint + webapp query box, and "Include temporal verbs (M00469)"); M028 Memory OS (`config/agent/m028-memory-os.yaml`, milestone M028); SDD-062 (`scripts/inference/prompt.py` loopback engine); SDD-064/066 (the store + admission + janitor); SB-077.

## Mission

Build the **query side** of the Memory OS. SDD-064 (admission) + SDD-066 (SLM janitor)
built the write/enrich side — the store is populated and enriched (topic / tags / edges /
derived_facts / summary_short) — but **nothing reads it back intelligently**: there is no
navigate / query / recall verb anywhere in `scripts/intelligence/`; the only reader is the
D-07 aggregate projection (counts + lifecycle). Build the **M00472 RLM memory navigator**
(get the memory environment → select slices → spawn child calls over slices → compose an
answer) + fold in the **M00469 temporal query verbs** (true-then / true-now / changed /
contradicted-by / last-verified).

> Numbering: renumbered 067 → **068** to resolve a collision — PR #46 claimed SDD-067 /
> E11.M34 for the cockpit app-shell while this increment was in planning. This is E11.M35.

## Problem

- The entire query side is unbuilt. `memory-changes.py` reads only the aggregate projection
  (`memory.json`), never the individual `entries`. No content query, no slice selection, no
  compose path, no temporal-verb query.
- The M028 contract yaml already carries an `rlm_memory_navigator` (M00472) block and a
  `temporal_query_verbs` (M00469) block, but the lint only locks the 5-verb list order
  (`test_temporal_query_five_verbs`) and never asserts the navigator's shape — so building
  both needs **no contract yaml change**.

## Grounded reality (SB-077) + design constraints

R04700-R04704 (non-negotiable) mandate an **agentic-over-slices** design — the RLM
**does NOT dump memory into the prompt** (R04700): it gets the memory *environment*
(R04701), selects/queries slices (R04702), spawns *child calls over slices* (R04703), and
returns a *composed answer* (R04704). The navigator is a **non-mutating read-compute**
(reads the store + composes via the SDD-062 loopback LM), so it sits on the SDD-062 chat
side of R10212 (web-exposable) — and a **GET** endpoint is inherently read-only-contract-
compliant (no `do_POST` change, unlike the SDD-062 chat POST).

The M00469 temporal verbs map to **real substrate** where it exists, and **honest-defer**
where it does not (per SB-077 — never invent):

| Verb | Substrate | Mapping |
|---|---|---|
| `changed` | `updated != created` | **fully real** |
| `true-then <T>` | `created`, forget/undo ledger | `created <= T` + active (partial — point-in-time via ledger where logged) |
| `true-now` | `state == "active"` | real (no invented decay threshold) |
| `last-verified` | `verified` bool + `updated` | partial — no `verified_at` timestamp exists; report the bool honestly, never invent a time |
| `contradicted-by` | **none** (edges are `kind:"related"` only) | **HONEST-DEFER / empty** — `{deferred:true, reason:"no contradiction edges in store"}` |

## Required coverage

### `scripts/intelligence/memory-navigate.py` — the RLM navigator (NEW)

A READ-COMPUTE (reads the store; **never mutates** — no `_atomic_write(STORE)`, no ledger,
no reconcile). Reuses `_load()` + shares the single store instance (`_store =
_load("memory-store.py")`, like memory-admit/janitor) + `_prompt = _load("inference/
prompt.py")` best-effort + the janitor's `_slm()` collect-token-stream + honest-defer
contract. The agentic pipeline:

1. **Environment** — `_entries()` filtered to `state=="active"`; slice axes (type / stage /
   topic / tags / edges / temporal).
2. **Select slices** (R04701, deterministic — NOT a dump): rank by token-overlap of the
   query against `summary` + `tags` + `topic` + `derived_facts`, plus optional structured
   filters (`--type N / --stage S / --topic T`); cap to top-K (bounded, K=5). Only the
   selected slices reach the LM, one per child call (R04700 honoured).
3. **Child calls over slices** (R04703): per selected slice, one bounded `_prompt.run`
   ("Relative to '<q>', what does this memory contribute?\n<slice>") → per-slice finding;
   honest-defer per hop.
4. **Compose** (R04704): a final `_prompt.run` ("Compose an answer to '<q>' from these
   findings:\n<findings>") → the composed answer.

**Honest-defer (SB-077):** LM unreachable at any hop → return the selected slices WITHOUT
the composed narrative (`answer:null, deferred:true, reason`); empty store / no match →
`{entries:[], answer:null, note:"no memory matched"}`. Never fabricates a memory or answer.

**M00469 temporal verbs** (`--verb <v>`) per the table above. CLI: `navigate <query>
[--type N] [--stage S] [--topic T] [--verb <temporal>] [--limit K] [--no-compose]`
(`--no-compose` = deterministic ranked slices only, no LM).

### `scripts/operator/memory-changes-api.py` — read-only GET endpoint

A third importlib block loading `memory-navigate.py` as `_navigator` (degrade-to-`None`,
like the defensive `_store` block) + a **`GET /api/d-07/navigate?q=...`** route in `do_GET`'s
`try:` (parse `parse_qs(urlsplit(self.path).query)` for `q` + optional filters →
`_navigator.navigate(...)` → `_send_json(200, ...)`; 503 when `_navigator is None`).
Non-streaming JSON. **`do_POST/PUT/DELETE` stay unconditional-405** — a GET adds no mutation
path (R10212); no `_reject`/contract relaxation needed.

### `webapp/d-07-memory-changes/index.html` — query box

A new "M028 memory query" section (input + button + results panel) near the entries table;
a `navigate()` fn `fetch('/api/d-07/navigate?q='+encodeURIComponent(q))` → render the
composed `answer` + ranked `slices` (mirrors `loadEntries()`/`renderEntries()`).
Offline-safe; honest banner when `deferred`.

### Wiring

`sovereign-osctl memory-changes navigate <query> …` → memory-navigate.py (a `navigate)`
branch alongside `janitor)`).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-068-A | Navigator design. | **answered (operator, 2026-07-09): agentic slice-select + child-calls + compose — NOT a memory dump (R04700-R04704).** |
| Q-068-B | Surface. | **answered ("we do not minimize"): CLI + a read-only GET `/api/d-07/navigate` + a D-07 webapp query box.** |
| Q-068-C | Temporal verbs. | **answered ("Include temporal verbs (M00469)"): fold the 5 verbs in, mapped to real substrate; `contradicted-by` + any timestamped `last-verified` honest-defer per SB-077.** |
| Q-068-D | Compose transport. | **answered: non-streaming JSON GET (compose server-side); SSE-over-GET is a Stage-N option.** |
| Q-068-E | Embeddings / rerank + the full M00475 8-step pipeline + a `contradicts` edge-kind + a `verified_at` timestamp. | **proposed: Stage-N (need a vector backend + new store substrate).** |

## Non-goals (Stage N)

- The full **M00475 8-step memory query pipeline** (intent → AVX bitset → sketch popcount →
  embed/rerank → graph expand → temporal validate → RLM recursive → oracle synthesis) —
  the navigator is the RLM-recursive step (R04743), not the whole pipeline. Embeddings /
  rerank / AVX bitset need a real vector + AVX backend.
- A `contradicts` edge-kind + a `verified_at` timestamp (the substrate `contradicted-by`
  and a timestamped `last-verified` would need) — this increment honest-defers them.
- SSE streaming of the composed answer (non-streaming JSON GET this increment).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 068 + mandate E11.M35.
- **Stage 1:** `memory-navigate.py` engine (navigator + temporal verbs) +
  `tests/unit/test_memory_navigate.py`.
- **Stage 2:** the daemon GET route + webapp query box + osctl `navigate` routing +
  `test_memory_changes_api_contract.py` extension + D-07 e2e.
- **Stage N:** the M00475 pipeline; embeddings/rerank; `contradicts`/`verified_at` substrate.

## Safety invariants

The navigator is a **READ-COMPUTE — it NEVER mutates the store** (no store write / ledger /
reconcile; the store file is byte-identical after a navigate). **Honest-defer (SB-077):** LM
unreachable → slices without a composed answer; empty store → empty result;
`contradicted-by` + timestamped `last-verified` → empty/deferred — never fabricated. R04700
honoured — only selected slices reach the LM, one per child call (no memory dump). R10212:
the web surface is a **GET** (read-only) — `do_POST/PUT/DELETE` stay unconditional-405; no
mutation path added. No contract yaml change (the 5-verb lock is untouched). MS003
`unsigned-pending-MS003`.

## Cross-references

- `config/agent/m028-memory-os.yaml` — the `rlm_memory_navigator` (M00472) +
  `temporal_query_verbs` (M00469) blocks; locked (5-verb order only) by
  `tests/lint/test_m028_memory_os.py`.
- `backlog/milestones/M028-memory-os-8-memory-types.md` — M00472 + R04699-R04708 (navigator)
  + M00469 (temporal verbs) + M00475 / R04737-R04744 (the full 8-step pipeline, Stage-N).
- `scripts/inference/prompt.py` (SDD-062) — the loopback LM the child calls + compose reuse.
- `scripts/intelligence/memory-store.py` / `memory-admit.py` / `memory-janitor.py` — the
  store + the `_load`/single-store + `_slm()` honest-defer idioms reused.
- `scripts/operator/memory-changes-api.py` (read-only 405 API) — gains one read-only GET.
- SDD-064 (admission), SDD-066 (janitor), SDD-062 (loopback chat / read-compute precedent).
