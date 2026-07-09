# SDD-069 — M028 observation event stream (auto-feed admission from real spans)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: SB-077 (the recurring "no real agent-memory source" gap); SDD-064 Q-064-E (the observation event stream half); R04672 / F02354 (not every observation becomes memory — the source that feeds the gate)
> Derived from: operator directive 2026-07-09 (chose the M028 observation event stream after SDD-068 merged in PR #47; picked "CLI + a recurrent timer (self-populating)" and a "comprehensive" event→memory mapping); M028 Memory OS (`config/agent/m028-memory-os.yaml`, milestone M028 M00470/M00471); the M049 OCSF span log; the SDD-065 reaper recurrent-hook precedent; SB-077.

## Mission

Close the recurring **SB-077 "no real agent-memory source"** gap. SDD-064 (admission) +
SDD-066 (janitor) + SDD-068 (navigator) built the Memory-OS write/enrich/query triad, but
admission observations were always **CLI/fixture-fed** — nothing auto-fed the store from
real system activity. Build the **observation event stream**: an engine that tails the one
real, append-only, multi-producer event stream (the OCSF span log), maps each new event to
a memory admission, and feeds the existing admission value-gate — with a recurrent timer so
the Memory OS **self-populates** continuously.

## Problem

- Every prior increment's admission observations came from an operator typing
  `memory-changes admit …`. There was no real source (SB-077); the auto-feed was named a
  Stage-N non-goal in SDD-064 Q-064-E.
- R04672 / F02354 ("not every observation becomes memory") describes a value-gated
  admission — but there was **no observation stream** to gate at all.

## Grounded reality (SB-077) — the one real source is the span log

The single honest, real, populated-at-runtime, append-only, **multi-producer** event stream
in sovereign-os is **`/var/log/sovereign-os/spans.jsonl`** (`SOVEREIGN_OS_SPAN_STORE`) — the
M049 OCSF-5001 span log that 13 emitters already write (memory admit/janitor/store, the M057
reaper, session/approval/adapter/memory decisions, cockpit actions, dashboard toggles) and
that `scripts/observability/trace-store.py` already tails. Everything else is a **state
snapshot** (`sessions.json`, `memory.json`, `store.json`) or a strict **subset** already
flowing into spans.jsonl. The observe engine feeds the existing sink
`memory-admit.admit(mtype, summary, *, trigger, trust, confirm)` (8 store-if triggers, 8
types, DRY-RUN default, `_is_duplicate` content-dedup — the value gate that decides which
observations become memory, R04672). No fabrication: an absent/empty log → 0 admitted.

## Required coverage

### `scripts/intelligence/memory-observe.py` — the observation stream (NEW)

Tails `spans.jsonl` via a persisted cursor, maps each new span → an admission, and calls
`admit()`. Reuses the `_load` idiom (`_admit = _load("memory-admit.py")`, whose
`_admit._store` is the shared store — `_store = _admit._store` for `SPAN_STORE` /
`_read_json` / `_atomic_write` / `_now`).

**Comprehensive event→trigger→type mapping** (keyed on `operation` / `severity` /
`attributes`, only fields actually present; summaries built from real attribute values):

| Span | store-if trigger | memory type |
|---|---|---|
| `session_reap` (reason, session_id) | `task-outcome` | episodic (2) |
| `session_save_state` | `high-value-reuse` | procedural (4) |
| `cockpit_action` exit_code==0 | `tool-worked` | procedural (4) |
| `cockpit_action` exit_code!=0 OR severity∈{error,critical} | `model-mistake` | episodic (2) |
| `*_decision` (approval/adapter/session) | `preference` | value (6) |
| `adapter_gate_advance` | `task-outcome` | procedural (4) |
| `dashboard_toggle` (rationale) | `preference` | value (6) |
| any other span severity∈{error,critical} | `model-mistake` | episodic (2) |

**Feedback-loop exclusion (critical):** skip any span whose `operation` matches `^memory_`
— the engine's own `memory_admit`/`advance`/`forget`/`decision` spans must NEVER be
re-observed (else admit→span→observe→admit loops forever).

**Cursor / idempotency** (net-new — no cursor precedent in the repo): a persisted
`observe.cursor` (`SOVEREIGN_OS_MEMORY_OBSERVE_CURSOR`, default
`/var/lib/sovereign-os/memory/observe.cursor`) = `{"ts": <max start_ts processed>, "seen":
[<span_ids at that exact ts>]}`. A run processes spans with `start_ts > ts` OR (`== ts` AND
`span_id ∉ seen`), then advances the cursor to the new high-water-mark (atomic write).
`admit`'s `_is_duplicate(type,summary)` is the content backstop.

**DRY-RUN default** (inherited: `--confirm` AND unset `SOVEREIGN_OS_DRY_RUN` to mint).
Verbs: `run [--confirm] [--limit N]` + `status` (read-only: cursor position + would-observe
count). Honest-defer: empty/absent log → 0 admitted, never crashes.

### The recurrent self-populating feed

`systemd/system/sovereign-memory-observe.{service,timer}` (oneshot + ~5-min timer,
R171-hardened, mirroring the M057 reaper) + `scripts/hooks/recurrent/memory-observe.sh`
(sources `common.sh` + `observability.sh`; runs `memory-observe.py run --confirm`; emits
`sovereign_os_memory_observe_run_total{result}` + `sovereign_os_memory_observe_admitted_total{result}`
with fail-class symmetry). Lands in full lockstep with the 6 recurrent-hook registries.

### Wiring

`sovereign-osctl memory-changes observe {run,status}` → memory-observe.py.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-069-A | The source. | **answered: `spans.jsonl` — the one real append-only multi-producer stream; everything else is a state snapshot or a subset (SB-077).** |
| Q-069-B | Feed surface. | **answered (operator, 2026-07-09): CLI `observe` verb + a recurrent `sovereign-memory-observe.{service,timer}` — the Memory OS self-populates.** |
| Q-069-C | Mapping breadth. | **answered: comprehensive — every span type in the table maps (incl. routine successful cockpit-actions); admit's trust-floor + `_is_duplicate` + the janitor's dedup/decay keep it manageable.** |
| Q-069-D | Idempotency + feedback loop. | **answered: a persisted `{ts,seen}` cursor high-water-mark + `_is_duplicate` backstop; exclude `^memory_` spans (no self-observation loop).** |
| Q-069-E | A config-driven mapping + a per-event trust model + historical backfill. | **proposed: Stage-N.** |

## Non-goals (Stage N)

- A config-driven / operator-tunable event→trigger→type mapping (the table is
  engine-internal this increment).
- A per-event trust model (all admissions use admit's default trust; the value-gate +
  dedup filter).
- Historical backfill of the pre-existing span log beyond the cursor's first run.
- Consuming any source other than spans.jsonl (there is no other real one).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 069 + mandate E11.M36.
- **Stage 1:** `memory-observe.py` (tail + map + cursor + admit) + `tests/unit/test_memory_observe.py`.
- **Stage 2:** the `{service,timer}` + `memory-observe.sh` + osctl `observe` routing + the
  6-registry lockstep + e2e.
- **Stage N:** config-driven mapping; per-event trust; backfill.

## Safety invariants

The observe engine MUTATES the store (via `admit`) → **CLI/timer-only, never a web control
(R10212)** — no control-systems entry; the memory-changes-api daemon stays read-only (405),
exactly like admit/janitor. **SB-077:** the only source is the REAL spans.jsonl; an empty/
absent log → 0 admitted (honest-defer, never fabricated); summaries are built from real span
attributes only. **No feedback loop** — `^memory_` spans are excluded so the engine never
re-observes its own admissions. **Idempotent** — the persisted cursor + `_is_duplicate`
guarantee a re-run over the same log admits nothing new. DRY-RUN default (the timer runs
live). No contract yaml change (the admission_rules 8-trigger / 5-ignore lock is untouched).
MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/intelligence/memory-admit.py` (SDD-064) — the admission value-gate sink the
  stream feeds (R04672 — not every observation becomes memory).
- `scripts/observability/trace-store.py` — the span-log reader + the OCSF-5001 schema the
  stream tails (M049).
- `scripts/intelligence/memory-store.py` — `_emit_span` (the span schema), the shared store
  helpers, `_is_duplicate`.
- `systemd/system/sovereign-session-reaper.{service,timer}` + `scripts/hooks/recurrent/session-reap.sh`
  (SDD-065) — the recurrent oneshot+timer + layer-B metric precedent.
- `backlog/milestones/M028-memory-os-8-memory-types.md` — M00470 (admission), M00471
  (lifecycle), R04672 / F02354, E0264.
- SDD-064 (admission engine), SDD-066 (janitor), SDD-068 (navigator).
