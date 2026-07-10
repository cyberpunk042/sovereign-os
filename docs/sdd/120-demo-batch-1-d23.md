# SDD-120 — DEMO mode rollout (batch 1 cont.): D-23 + models-catalog + D-11 + D-10

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the operator-approved broad DEMO rollout (roadmap Phase 1). Batch-1 continuation after SDD-119 (D-03). Ships the **batch-1 remainder in one PR** (operator: "you can do a bigger PR... not one thing at the time") — **D-23 Models Catalog**, **models-catalog**, **D-11 Adapter Status**, **D-10 Eval History** — completing the "see the models/adapters/evals with no daemon" batch.
> Derived from / extends: SDD-116 (DEMO + shared helper), SDD-119 (head-injection recipe). §1g. Recover band (SDD-120 / E11.M120 per SDD-100).

## Mission

Apply the SDD-116 DEMO pattern to the four remaining batch-1 (LM/compute "see the models") panels in a
single PR. Each: the shared `demo-mode.{js,css}` helper inlined in `<head>` (so `window.soDemo` exists
before the panel script's first paint — SDD-119 rule), a `demoActive()` gate, a badged `DEMO_<X>` sample
constant with obvious `demo/…` placeholder ids, and **zero network calls** in the demo path (any
`EventSource` skipped). Opt-in + always-badged SB-077 reconciliation; §1g — every section renders.

## Grounded design (no new data)

- **D-23 Models Catalog** — `DEMO_CATALOG` shaped to `renderTiers(data)` (`total`, `catalog_path`,
  `tiers[]{label, models[]}`); `refresh()` short-circuits to `renderTiers(DEMO_CATALOG)` (no fetch); the
  `/api/models-catalog/stream` EventSource guarded by `!demoActive()`.
- **models-catalog** — `DEMO_MODELS` (6 models: id/tier/class/quantization/size_class/purpose/vram/
  context/status); a demo branch at the top of `load()` sets `MODELS = DEMO_MODELS`, builds filters +
  renders + badges, then returns (no fetch). No EventSource in this panel.
- **D-11 Adapter Status** — `DEMO_ADAPTERS` (4 adapters: id/base_model/precision/training/size/
  eval_gain_pct/status/gates); `refresh()` selects `demoActive() ? DEMO_ADAPTERS : await fetchAdapters()`;
  the adapter-stream EventSource guarded (`throw` in demo before `new EventSource`).
- **D-10 Eval History** — `DEMO_EVALS` (summary/suites/tasks/models/candidates, spark helper);
  `refresh()` selects `demoActive() ? DEMO_EVALS : await fetchEvals()`; the eval-stream EventSource
  guarded in demo.
- Contract-lint guards pin each panel's demo no-network path + the `<head>` inline (`_assert_head_demo`).

## Way forward

- **Stage 0 (this doc)** — SDD-120 + INDEX + mandate E11.M120.
- **Stage 1** — the four panels' DEMO treatment (head-inlined helper + `demoActive()` branch +
  `DEMO_<X>`) + four lint guards.
- **Stage 2** — full gate + Playwright (demo on, per panel: badge + sample rows + demo ids, zero data
  API calls, no page errors) + PR.
- **Next** — batch 2 (hardware + compute posture: d-09-hardware-pressure, runtime-modes, orchestration,
  d-24-cpu-features, cpu-features, d-04-costs), then batches 3–6.

## Cross-references

- SDD-116/119 (DEMO + head recipe); SDD-113 (D-23 offline scaffold this builds on). SDD-100 — band scheme.
