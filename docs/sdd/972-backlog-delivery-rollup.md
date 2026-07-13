# SDD-972 — per-milestone backlog delivery roll-up

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-038** (backlog granularity gap — "how done is M0xx" was TBD).
> Mandate module: **E11.M972** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

The backlog catalogues **14,079 R-rows across 84 milestone files**, but delivery state was only readable by scrolling `backlog/SHIPPED.md`, which self-describes as a *SAMPLED snapshot* with a literal *"state TBD"* roll-up (the `%` column was `—`). So "how done is M0xx?" had no queryable answer. F-2026-038 asked for a **generated per-milestone shipped roll-up** so it becomes queryable.

## The honest-metric problem (and the fix)

A naive *"SHIPPED rows ÷ R-rows"* percentage **misleads**: `SHIPPED.md` records delivered **surfaces**, and a single R-row typically ships as several (an alert + a dashboard + an API + a doc + tests). M060 alone has 288 shipped-surface rows against 170 R-rows — a literal ratio of 169%. So this SDD reports the metrics that ARE meaningful and computable:

- **catalogued R-rows** per milestone — distinct `R#####` ids in its milestone file (each milestone owns a contiguous range; global-distinct total = 14,079, matching the catalogue);
- **delivered?** — whether `SHIPPED.md` carries a `## M###` production-delivery section for it;
- **shipped surfaces** — the delivery-record's data rows (a delivery-**depth** signal, explicitly *not* a completion %).

The grand roll-up then answers the finding directly: **7 of 84 milestones (8%) have production delivery recorded**; 77 are catalogued-only.

## What this SDD builds

### 1. `scripts/backlog/gen-shipped-rollup.py` — the generator

Stdlib-only. Parses the 84 milestone files (catalogued R-rows) + `SHIPPED.md` (delivery sections, crediting each id in a multi-milestone header like `## M045 + M013 — …`) and writes `backlog/SHIPPED-ROLLUP.md`: a grand roll-up + a per-milestone table (milestone · catalogued R-rows · delivered? · shipped surfaces). `--check` exits non-zero if the committed roll-up is stale.

### 2. `backlog/SHIPPED-ROLLUP.md` — the generated roll-up

The queryable answer to "how done is M0xx", with a header explaining the surfaces-≠-R-rows caveat so the depth column is never misread as a completion %.

### 3. `tests/lint/test_shipped_rollup.py` — the sync contract

Regen-and-compare (the committed roll-up must equal a fresh generation) + completeness (every milestone file appears). So the roll-up can't silently drift when a milestone or `SHIPPED.md` changes — the same self-maintaining discipline as the SDD-catalog (SDD-958) and context-counts (SDD-952) generators.

## Verification

- `python3 scripts/backlog/gen-shipped-rollup.py` → wrote `backlog/SHIPPED-ROLLUP.md`; `--check` idempotent.
- Grand roll-up: 84 milestones · 7 delivered (8%) · 14,079 distinct catalogued R-rows · 319 shipped surfaces recorded. Delivered milestones: M013, M045, M049, M060 (288 surfaces), M073, M077, M084.
- R-row ranges confirmed milestone-unique (M002 R00171–R00340, M060 R10031–R10200, …); global-distinct 14,079 matches the stated 14,080 catalogue.
- `python3 -m pytest tests/lint/test_shipped_rollup.py` — **3 passed**; `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **A completion `%` of the R-row catalogue** — not mechanically derivable from `SHIPPED.md`'s surface-oriented records (surfaces ≠ R-rows); the roll-up gives milestone delivery **coverage** (a real %) + per-milestone **depth**, and says so plainly.
- **Editing `SHIPPED.md`'s own SAMPLED narrative** — left as-is; the roll-up is the orthogonal computed view beside it.
- **Back-filling delivery records for the 77 catalogued-only milestones** — that's the actual shipping work, not this audit item.

## Safety invariants

Adds a stdlib generator + its output + a read-only lint. No crate code, no runtime behavior, no gateway touch. The roll-up is computed from files the repo already ships; it asserts nothing about R-rows beyond what the milestone files + SHIPPED.md state. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/backlog/gen-shipped-rollup.py` — the generator
- `backlog/SHIPPED-ROLLUP.md` — the generated roll-up
- `tests/lint/test_shipped_rollup.py` — the sync contract
- `backlog/SHIPPED.md` — the SAMPLED delivery narrative the roll-up computes over
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-038 (source)
- SDD-958 / SDD-952 — the same generator + regen-compare-contract pattern
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
