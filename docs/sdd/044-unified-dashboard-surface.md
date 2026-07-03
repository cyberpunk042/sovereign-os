# SDD-044 — Unified dashboard surface

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-07-03
> Closes findings: operator-dashboard-gap-directive-2026-07-03
> Derived from: SDD-040 (cockpit dashboard implementation bridge), SDD-039
> (§1g 8-surface delivery), SDD-043 (flexible tiered feature+model
> exploitation — the un-paneled feature domains), the master-dashboard
> aggregator (`scripts/operator/master-dashboard.py`, R452/R500), and
> `config/dashboard-catalog.yaml`.

## Mission

Give the operator ONE coherent global view that surfaces **everything** —
all ~38 panels AND the feature domains that have no panel yet (Models,
CPU/AVX-512 choice, orchestration, runtime-profile generation, selfdef) —
each with a real description and a way to reach it, plus the net-new
dashboards those un-paneled domains deserve. The operator opened
`/master-dashboard/` + `/panels` and found "almost nothing" and an
undescribed list; this closes that gap end to end.

## Problem

Mapped 2026-07-03. Three distinct failures compounded into "there's
nothing here":

1. **No global view, no descriptions.** `/panels` was a flat list of 38
   slugs with no explanation, no grouping. `/master-dashboard/` is a
   route-registry aggregator, not a described global view. Nothing told
   the operator what each surface is or how the whole fits.
2. **Panels render empty.** There are 38 `sovereign-*-api` services (one
   per panel), but `make panel` started only 4 — so 34 panels had no data
   source and showed baked snapshots / blank tiles.
3. **Whole feature domains are invisible.** Everything built in SDD-043 —
   the model catalog + VRAM-aware selection, the tiered AVX-512
   exploitation, `tier_intent`, profile generation, the thinking router —
   plus selfdef management, is **CLI/API-only with no panel at all.** The
   operator's "where are all the Models, AVX-choice, orchestrations"
   points exactly here.

## Required coverage

- **C-1 · single source of truth + descriptions.** One catalog maps every
  surface → {category, description, status, how-to-reach}. Every webapp
  panel has an entry; nothing ships undescribed.
- **C-2 · global view.** A categorized, described index renders the
  catalog — panels AND un-paneled domains (with their CLI) — as the
  operator's front door.
- **C-3 · panels live.** The launcher starts the panel data APIs so
  panels show real data, honestly badged live/snapshot.
- **C-4 · the missing dashboards.** Build the net-new panels the catalog
  references as `planned`: a **Models** browser (catalog + tier_intent
  resolver + eval/fine-tune), a **CPU/AVX-512** capability matrix, an
  **Orchestration** view (routing decision + thinking_policy editor), a
  **Runtime-Profile** generator/preview, and a **selfdef** control panel.
- **C-5 · descriptions in lockstep.** Descriptions stay single-sourced and
  lint-locked so they never drift from the panels.

## Goals

- Honest surfacing — a panel says live vs snapshot; an un-paneled domain
  says "no panel yet" and shows its CLI. Never a dead reference.
- Reuse the existing 37 APIs + the catalog; don't rebuild working panels.
- The new dashboards follow the shipped webapp idiom (single-file, the
  `_shared/design-grammar.md` action hierarchy) + read live `/api/*`.

## Non-goals

- Not redesigning the 22 cockpit D-NN panels (SDD-040 owns their content).
- Not building a JS framework — the panels are stdlib-served single files.
- Not auto-starting the 38 APIs as hardened systemd services (the
  hardening lint forbids install-shaped services; `make panel` runs them
  as dev processes, the image ships them as their own units).

## Way forward (phased)

- **Phase 1 — catalog + global view + start-all APIs. SHIPPED
  (2026-07-03).** `config/dashboard-catalog.yaml` (42 entries: 37 panels +
  5 un-paneled domains, each described + categorized); the `/panels` index
  renders it as the categorized global view; `/catalog.json` exposes it;
  `make panel` starts every `scripts/operator/*-api.py`;
  `tests/lint/test_dashboard_catalog_complete.py` locks completeness +
  substantive descriptions + CLI-for-un-paneled.
- **Phase 2 — the Models dashboard (C-4).** Catalog browser over
  `models/catalog.yaml` (filter by class/quant/tier/vram), the
  `select-by-intent` resolver UI, eval history + fine-tune status. Backed
  by a new `models-api` reading the catalog + `scripts/models/*`.
- **Phase 3 — CPU/AVX-512 + Orchestration dashboards (C-4).** The AVX-512
  capability matrix (which instructions the profile exploits, per-tier
  fit, from `cpu-features.py` + `avx512-advisor.py`); the orchestration
  view (live routing decisions from `router plan` + a `thinking_policy`
  editor writing the profile block).
- **Phase 4 — Runtime-Profile + selfdef dashboards (C-4).** The generator
  wizard (hardware × strategy → resolved allocations preview) + the
  selfdef control panel unifying D-13..D-18 + on/off.
- **Phase 5 — descriptions in panel `<meta>` (C-5).** Move each
  description into the panel's own `index.html`
  (`<meta name="x-sovereign-description">`, extending the existing
  `x-sovereign-module` convention) so it's co-located; the catalog
  aggregates from there. Lint keeps them in lockstep.

## Open questions

| Q | Question | Status |
|---|---|---|
| Q-1 | Does the master-dashboard page ITSELF become the global view, or does `/panels` stay the index and master-dashboard stays the route/health aggregator? | open |
| Q-2 | New dashboards: one shared `panel-api` reading the catalog + delegating, or one `*-api` per new dashboard (matching the existing 37)? | open |
| Q-3 | Does the thinking_policy editor write the active `profiles/runtime/<id>.yaml` directly (mutating), or emit an overlay the operator applies? | open |
| Q-4 | Descriptions single-sourced in the catalog YAML, in panel `<meta>`, or both with the catalog aggregating (Phase 5)? | open |

## Cross-references

- `config/dashboard-catalog.yaml`, `tests/lint/test_dashboard_catalog_complete.py`
- `scripts/operator/build-configurator-api.py` (global-view index + /catalog.json)
- `scripts/operator/panel.sh` (start-all panel APIs)
- `scripts/operator/master-dashboard.py` (R452/R500 aggregator)
- `webapp/*` (37 panels), `webapp/_shared/design-grammar.md`
- SDD-040 (cockpit bridge), SDD-039 (8-surface), SDD-043 (the un-paneled
  feature domains: models / AVX / tier_intent / generation / router)
