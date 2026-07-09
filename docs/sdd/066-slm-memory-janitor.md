# SDD-066 — M028 SLM memory janitor (M00473 — 7 cheap maintenance jobs, SLM via the SDD-062 loopback engine)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: SDD-064 Q-064-E (the SLM memory janitor half); F02379 / R04709-R04715 (the 7 SLM memory jobs)
> Derived from: operator directive 2026-07-09 (chose the M028 SLM memory janitor after SDD-065 merged in PR #43; picked "Full 7 jobs, SLM via SDD-062 engine"); M028 Memory OS (`config/agent/m028-memory-os.yaml`, milestone M028 M00473 / E0265); SDD-062 (`scripts/inference/prompt.py` loopback engine); SDD-064 (the admission engine + lifecycle); SB-077.

## Mission

Make the M028 memory lifecycle **do the janitorial work** it names. SDD-064 built the
admission engine + `advance(mem-id)`, but `advance()` is a **pure stage-label bump with
zero per-stage work** — it walks `observe → … → archive` without ever extracting a fact,
tagging, deduplicating, labelling a topic, proposing a graph edge, classifying a failure,
or summarising. Build the **M00473 SLM memory janitor** — the 7 cheap maintenance jobs
(R04709-R04715) — as a real engine that enriches memory entries with ground-truth-layer
fields, deterministic jobs always real, SLM jobs routed through the SDD-062 loopback
inference engine with **honest-defer** when no backend answers.

## Problem

- `memory-admit.advance()` relabels `stage` but performs no stage work; the 11-stage
  lifecycle is a label walk, not a maintenance pipeline.
- The M00473 janitor's 7 jobs (extract-facts R04709 / tag R04710 / dedup R04711 /
  topic-label R04712 / graph-edges R04713 / classify-failure R04714 / summarize R04715)
  are **all unbuilt** — nothing in the tree extracts, tags, dedups, or links memories.
- The E0261 ground-truth layer (raw-episode / derived-facts / summary / graph-edges /
  embeddings / bitset-metadata / trust-score / freshness) is **conceptual** — no store
  entry carries derived facts, a topic, edges, or a summary.

## Grounded reality (SB-077) — no SLM wired, but the loopback engine exists

There is **no SLM backend wired** for janitorial work today (the oracle/logic tiers are
hardware-gated; R04716 — "Oracle should not do janitorial memory work unless the stakes
are high"). But SDD-062 already shipped `scripts/inference/prompt.py` — the loopback
inference engine (`run(text)` streams token deltas from the local router, honest-defer
when unreachable, SB-077-clean). The janitor **reuses it as the "SLM"**: the SLM-routed
jobs (extract-facts / topic-label / summarize / classify-failure) route through
`prompt.run()`, and when the loopback router is unreachable they **honest-defer** — the
field is left unset and the job reports `{deferred:true, reason}`, never fabricating a
fact/topic/summary. The deterministic jobs (dedup / graph-edges / tag / stage-advance
effects) need no backend and are **always real**.

## Required coverage

### `scripts/intelligence/memory-janitor.py` — the SLM janitor engine (NEW)

Mirrors the `memory-admit.py` shape (`_load()`s the store `memory-store.py` owns; operates
on the store dict; atomic-writes + `_reconcile_safe()` after every mutation). Seven jobs,
split by determinism:

**Deterministic / always-real (no backend):**

- **dedup (R04711)** — collapse entries with an identical `(type, normalized-summary)`;
  keep the earliest by `created`, mark the rest `state:"duplicate"` + `dedup_of:<kept-id>`.
  NEVER hard-deletes (reversible bookkeeping — mirrors the SDD-065 reaper archive + the
  forget soft-delete).
- **graph-edges (R04713)** — link `active` entries sharing a topic or a token-overlap over
  a floor; write an additive `edges:[{to:<id>, kind:"related"}]` (bidirectional, deduped).
- **tag (R04710)** — deterministic keyword/token tagging → additive `tags:[...]` (the
  "obvious" tags; the SLM topic-label is the richer semantic pass).
- **advance-effects** — a janitor verb that *runs the stage's job then advances the label*:
  `classify`→ensure tags · `link`→ensure edges · `extract-facts`→derived_facts (SLM) ·
  `verify`→set `verified:true` · `promote`→set `promoted:true` · `decay`→bump a
  `freshness` counter · `archive`→terminal. Idempotent per stage. **One owner of the
  `stage` field** — the janitor performs the job, then delegates the label bump to
  `memory-admit.advance` (no duplicate lifecycle-mutation logic).

**SLM-routed (SDD-062 `prompt.run`, honest-defer per SB-077):**

- **extract-facts (R04709)** → additive `derived_facts:[...]` from the summary.
- **topic-label (R04712)** → additive `topic:"…"`.
- **summarize (R04715)** → additive `summary_short:"…"` (NEVER overwrites the raw `summary`).
- **classify-failure (R04714)** → additive `failure_class:"…"` (for `model-mistake` entries).

Each SLM job collects `prompt.run(text)`'s token events into a string; on the `error` event
(router unreachable) it honest-defers (`{deferred:true, reason}`) and leaves the field
unset. DRY-RUN default; `_SAFE_ID`; OCSF-5001 span.

### `scripts/intelligence/memory-store.py` — `reconcile()` `enriched` projection

Extend `reconcile()` to also project an additive `enriched` coverage block
(`{with_facts, with_topic, with_edges, with_summary, duplicates}`) so the D-07 reader
surfaces the janitor's effect. Preserve everything memory-decide owns (pending / history /
diffs / profile) and the existing `counts` / `lifecycle` — additive keys only.

### Wiring

`sovereign-osctl memory-changes janitor <job> [mem-id|--all]` (and/or per-job verbs
`dedup / edges / tag / extract-facts / topic / summarize / classify`) → memory-janitor.py.
No D-07 webapp change — the panel renders from the snapshot; once the janitor writes fields
+ reconcile projects the `enriched` block, the coverage surfaces automatically.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-066-A | SLM source. | **answered (operator, 2026-07-09): the SDD-062 `scripts/inference/prompt.py` loopback engine; honest-defer when the router is unreachable — never fabricates (SB-077).** |
| Q-066-B | Deterministic vs SLM split. | **answered: dedup / graph-edges / tag / advance-effects deterministic (always real); extract-facts / topic-label / summarize / classify-failure SLM-routed.** |
| Q-066-C | Field representation. | **answered: additive optional entry keys (derived_facts / topic / summary_short / edges / tags / failure_class / verified / promoted / dedup_of); no existing field changes shape; reconcile projects an `enriched` block.** |
| Q-066-D | Dedup semantics. | **answered: mark `state:"duplicate"` + `dedup_of`, NEVER hard-delete — reversible, mirrors the reaper archive + forget soft-delete.** |
| Q-066-E | A recurrent janitor timer. | **proposed: Stage-N — the osctl verbs are the surface now; an optional `sovereign-memory-janitor.{service,timer}` pulls the full recurrent-hook registry lockstep when adopted.** |
| Q-066-F | Embeddings / bitset-metadata ground-truth layers. | **proposed: Stage-N — this increment covers derived-facts / summary / graph-edges / topic; embeddings need a real vector backend.** |

## Non-goals (Stage N)

- A recurrent `sovereign-memory-janitor.{service,timer}` (the osctl verbs are the surface
  this increment; a timer adds the EXPECTED_RECURRENT_HOOKS + HOOK_TO_TIMER_SLUG +
  ongoing.md + observability-coverage lockstep).
- The **embeddings** + **bitset-metadata** ground-truth layers (need a real vector / AVX
  candidate-packing backend — E0266 hardware mapping).
- The **RLM memory navigator** (M00472 — the query side; separate from the janitor).
- The real **observation event stream** (auto-feeding admit + janitor from agent history).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX + mandate E11.M33; flip SDD-064 Q-064-E
  (the SLM janitor half).
- **Stage 1:** `memory-janitor.py` engine (7 jobs) + `memory-store.py` `reconcile()`
  `enriched` projection + `tests/unit/test_memory_janitor.py` + `test_memory_store.py`
  reconcile-enriched tests.
- **Stage 2:** the osctl `memory-changes janitor …` routing + D-07 e2e.
- **Stage N:** the recurrent timer; embeddings/bitset layers; the RLM navigator; the
  observation event stream.

## Safety invariants

The janitor mutates the store → **CLI/timer-only, never a web control (R10212)** — the
`memory-changes-api` daemon stays read-only (405); the only web read-compute relaxation
(SDD-062 chat) is unrelated. SLM jobs **honest-defer when the loopback router is unreachable
— never fabricate a fact/topic/summary (SB-077)**. All new fields are **additive** (no
existing entry field — id/type/stage/summary/state/created/updated — changes shape → the
store / admit / decide / changes / reconcile all stay green). dedup **marks `duplicate` +
never hard-deletes** (reversible). **One owner of the `stage` field** (the janitor delegates
the label bump to `memory-admit.advance`). `reconcile()` preserves the memory-decide-owned
`memory.json` fields (no data loss). Ids `_SAFE_ID`-validated; atomic writes + OCSF-5001
span; DRY-RUN default; selfdef/perimeter untouched; MS003 `unsigned-pending-MS003`.

## Cross-references

- `config/agent/m028-memory-os.yaml` — the M028 contract (8 types, 11-stage lifecycle,
  ground-truth layer) the janitor enriches; locked by `tests/lint/test_m028_memory_os.py`
  (the contract names M00473's 7 jobs; no janitor block is locked — the engine matches the
  spec without a yaml change).
- `backlog/milestones/M028-memory-os-8-memory-types.md` — M00473 (SLM memory janitor) +
  R04709-R04716 (the 7 jobs + the "oracle not janitorial" rule) + E0265.
- `scripts/inference/prompt.py` (SDD-062) — the loopback inference engine reused as the SLM.
- `scripts/intelligence/memory-store.py` (SDD-059/060/064) — the store + `reconcile()`.
- `scripts/intelligence/memory-admit.py` (SDD-064) — the admission engine + `advance`
  (the sole `stage`-field owner the janitor delegates to).
- `scripts/intelligence/memory-changes.py` — the pure projection reader (405 API); unchanged.
- SDD-064 (admission engine), M028 milestone, R04709-R04716.
