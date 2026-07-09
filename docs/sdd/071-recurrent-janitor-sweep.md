# SDD-071 — recurrent SLM-janitor sweep (auto-enrich + bounded lifecycle advance)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: SDD-066 Q-066-E (the recurrent janitor timer); completes the SDD-069 self-populating loop (observe admits → janitor enriches, both on cadence)
> Derived from: operator directive 2026-07-09 (chose the recurrent janitor timer after SDD-069 merged in PR #50; picked "advance to a safe stop-stage" + "deterministic + SLM (honest-defer)"); M028 Memory OS (M00471 lifecycle, M00473 janitor); the SDD-065 reaper + SDD-069 observe recurrent-hook precedent; SB-077.

## Mission

Close the Memory-OS self-populating loop. SDD-069 made the store self-populate — real span
events auto-admit at stage `observe` — but those raw entries **sit at `observe` forever**:
the SDD-066 SLM janitor (dedup/tag/edges/SLM-enrich/advance) only runs on manual invocation.
Build a **recurrent janitor sweep**: a timer that auto-enriches admitted memories and walks
them through the lifecycle, the mirror of the observe timer (observe admits → janitor
enriches, both on cadence).

## Problem

- The observe stream (SDD-069) fills the store with raw `observe`-stage entries. Nothing
  auto-enriches or advances them; they never gain tags/edges/facts or progress.
- The janitor (`memory-janitor.py`) is **per-job** (`dedup`/`edges`/`tag`/`extract-facts`/
  `topic`/`summarize`/`classify`/`advance`) — there is no full-pass "sweep" verb — and there
  is **no recurrent janitor hook**.

## Grounded design

`advance(mem_id)` runs the CURRENT stage's effect then delegates the label bump to
`memory-admit.advance` (one owner of `stage`). The 11-stage lifecycle
`observe→classify→quarantine→link→score→store-raw→extract-facts→verify→promote→decay→archive`
has per-stage effects: classify→tag, link→edges, extract-facts→SLM facts, verify→`verified`,
promote→`promoted`, decay→`freshness`.

### `sweep` verb (NEW in `memory-janitor.py`)

One bounded maintenance pass over active, non-`duplicate` entries:

1. **Global deterministic enrichment** (idempotent): `dedup()` → `tag(all)` → `edges()`.
2. **SLM enrichment** (honest-defer per entry when the loopback router is unreachable):
   `topic` + `summarize` on entries missing those fields (not lifecycle-stage effects, run
   explicitly); `extract-facts` is applied via the `extract-facts` stage effect during
   advance; `classify` (failure_class) on `model-mistake`-admitted entries missing it.
3. **Bounded lifecycle advance** toward **STOP_STAGE = `verify`**
   (`SOVEREIGN_OS_MEMORY_JANITOR_STOP_STAGE`, `--stop`) — ONE step per tick (gradual):
   - `stage_index < stop_index` → `advance(mem_id)` (current stage effect + one label bump).
   - `stage_index == stop_index` (at `verify`) → apply the stop-stage effect DIRECTLY
     (`verified:true`) WITHOUT advancing — the entry gets verified but is NEVER
     auto-`promote`d. (Subtlety: `advance()` runs the *current* stage's effect then bumps,
     so "stop at verify" by never advancing-from-verify would leave the verify effect
     unapplied — hence apply it directly at the stop.)
   - `stage_index > stop_index` (operator-advanced past the auto zone) → left untouched.

The auto-sweep NEVER crosses into `promote`/`decay`/`archive` — those value/retention
judgments stay operator-gated. DRY-RUN default (each underlying job gates on `--confirm` +
`SOVEREIGN_OS_DRY_RUN`); honest-defer inherited from the SLM jobs. Returns a per-pass summary.

### The recurrent auto-enrich feed

`systemd/system/sovereign-memory-janitor.{service,timer}` (oneshot + ~10-min timer — heavier
than observe's 5-min since it makes SLM calls, R171-hardened) +
`scripts/hooks/recurrent/memory-janitor.sh` (sources `common.sh` + `observability.sh`; runs
`janitor sweep --confirm`; emits `sovereign_os_memory_janitor_run_total{result}` +
`sovereign_os_memory_janitor_swept_total{result}` with layer-B fail-class symmetry). In full
lockstep with the 6 recurrent-hook registries.

### Wiring

The osctl `janitor)` arm already routes `janitor <job> "$@"` → memory-janitor.py, so
`janitor sweep --confirm` routes with no osctl change (the `sweep` subparser is added in the
engine; the arm comment + job-list are updated).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-071-A | Trigger. | **answered: a recurrent `sovereign-memory-janitor.{service,timer}` + a `sweep` verb, mirroring the SDD-069 observe timer.** |
| Q-071-B | Advance policy. | **answered (operator, 2026-07-09): enrich + advance to STOP_STAGE=`verify`, one step per tick, NEVER auto-promote/decay/archive.** |
| Q-071-C | SLM scope. | **answered: deterministic (dedup/tag/edges) + SLM (topic/summarize/extract-facts) each tick, honest-defer when the router is unreachable.** |
| Q-071-D | Cadence. | **answered: ~10 min (heavier than observe's 5 min — the sweep makes SLM calls).** |
| Q-071-E | A per-memory-type stop-stage + a value-gated auto-promote. | **proposed: Stage-N.** |

## Non-goals (Stage N)

- Auto-`promote`/`decay`/`archive` (value + retention decisions stay operator-gated).
- A per-memory-type or per-trust configurable stop-stage.
- A value-gated auto-promote (promotion from a score threshold).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 071 + mandate E11.M38.
- **Stage 1:** the `sweep` verb + `tests/unit/test_memory_janitor.py` sweep tests.
- **Stage 2:** the `{service,timer}` + `memory-janitor.sh` + the 6-registry lockstep + e2e.
- **Stage N:** per-type stop-stage; value-gated auto-promote.

## Safety invariants

The sweep MUTATES the store (enrich + advance) → **CLI/timer-only, never a web control
(R10212)** — the memory-changes-api daemon stays read-only (405), exactly like
admit/janitor/observe. **Bounded advance:** the auto-sweep NEVER crosses into
`promote`/`decay`/`archive` (STOP_STAGE=`verify`). **SB-077 honest-defer:** the SLM jobs skip
(field unset) when the loopback router is unreachable — never fabricated; the deterministic
jobs always run. **One owner of `stage`** — the sweep delegates every label bump to
`memory-admit.advance` (via the existing `advance()`). dedup marks `duplicate` + never
hard-deletes. DRY-RUN default (the timer runs live). Idempotent (deterministic jobs + the
stop-stage guard). No contract yaml change (the 11-stage lifecycle + admission_rules locks
are untouched). MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/intelligence/memory-janitor.py` (SDD-066) — the 7 jobs + `advance` + `_STAGE_EFFECT`.
- `scripts/intelligence/memory-observe.py` (SDD-069) — the source that admits at `observe`.
- `scripts/intelligence/memory-admit.py` — `advance` (the sole `stage` owner) + `_LIFECYCLE`.
- `systemd/system/sovereign-memory-observe.{service,timer}` + `scripts/hooks/recurrent/memory-observe.sh`
  (SDD-069) + `sovereign-session-reaper.*` (SDD-065) — the recurrent-hook + lockstep precedent.
- `backlog/milestones/M028-memory-os-8-memory-types.md` — M00471 lifecycle, M00473 janitor.
- SDD-066 (janitor), SDD-069 (observe stream).
