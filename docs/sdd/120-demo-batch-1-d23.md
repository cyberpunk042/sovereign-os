# SDD-120 — DEMO mode rollout (batch 1 cont.): D-23 Models Catalog

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the operator-approved broad DEMO rollout (roadmap Phase 1). Batch-1 continuation after SDD-119 (D-03). Ships **D-23 Models Catalog** — the canonical model registry browsed by SRP tier.
> Derived from / extends: SDD-116 (DEMO + shared helper), SDD-119 (head-injection recipe). §1g. Recover band (SDD-120 / E11.M120 per SDD-100).

## Mission

Apply the SDD-116 DEMO pattern to **D-23 Models Catalog**: the shared `demo-mode.{js,css}` helper inlined
in `<head>`, a `demoActive()` short-circuit in `refresh()` that renders a badged `DEMO_CATALOG` (obvious
`demo/…` ids; 3 SRP tiers × sample models with class/engine/precision/params/context/license/status) with
**zero network calls** (the `/api/models-catalog/stream` EventSource skipped in demo). Opt-in +
always-badged SB-077 reconciliation.

## Grounded design (no new data)

- `DEMO_CATALOG` is shaped to `renderTiers(data)` (`data.total`, `data.catalog_path`, `data.tiers[]`
  each `{label, models[{id,class,engine,precision,params_b,context_window_tokens,license,status,purpose}]}`).
- `refresh()`: `if (demoActive()) { banner=DEMO; renderTiers(DEMO_CATALOG); soDemo.badge(); return; }` — no fetch.
- The `new EventSource('/api/models-catalog/stream')` is guarded by `!demoActive()`.
- A contract-lint guard pins the D-23 demo no-network path + the `<head>` inline.

## Way forward

- **Stage 0 (this doc)** — SDD-120 + INDEX + mandate E11.M120.
- **Stage 1** — D-23 DEMO (head-inlined helper + `demoActive()` branch + `DEMO_CATALOG`) + lint guard.
- **Stage 2** — full gate + Playwright (demo on: badge + 3 sample tiers + demo ids, zero catalog API calls) + PR.
- **Next** — batch-1 remainder (models-catalog, d-11-adapter-status, d-10-eval-history), then batches 2–6.

## Cross-references

- SDD-116/119 (DEMO + head recipe); SDD-113 (D-23 offline scaffold this builds on). SDD-100 — band scheme.
