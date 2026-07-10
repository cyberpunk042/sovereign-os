# SDD-121 — DEMO mode rollout (batch 2): hardware + compute posture

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the operator-approved broad DEMO rollout (roadmap Phase 1). Batch 2 after SDD-119/120 (batch 1). Ships the **hardware + compute posture** panels in one PR (operator: "you can do a bigger PR... not one thing at the time") — **d-09-hardware-pressure**, **runtime-modes**, **orchestration**, **d-24-cpu-features**, **cpu-features**, **d-04-costs** — so an operator can explore the box's hardware pressure, runtime modes, orchestration rules, CPU features, and cost posture with no daemon.
> Derived from / extends: SDD-116 (DEMO + shared helper), SDD-119 (head-injection recipe), SDD-120 (batch-1 four-panel pattern). §1g. Recover band (SDD-121 / E11.M121 per SDD-100).

## Mission

Apply the SDD-116 DEMO pattern to the six batch-2 panels in a single PR. Each: the shared
`demo-mode.{js,css}` helper inlined in `<head>` (SDD-119 rule — `window.soDemo` exists before the panel
script's first paint), a `demoActive()` gate, and a badged `DEMO_<X>` sample constant shaped to the
panel's render fn with obvious `demo/…` placeholder ids, and **zero network calls** in the demo path
(each panel's `EventSource` skipped where present). Opt-in + always-badged SB-077 reconciliation; §1g —
every section renders.

## Grounded design (no new data)

- **d-09-hardware-pressure** — `DEMO_PRESSURE` shaped to `render()`/`renderResults()`; `refresh()`
  short-circuits to render sample pressure (no `fetchPressure`); `/api/hardware/stream` EventSource
  guarded by `!demoActive()`.
- **runtime-modes** — `DEMO_MODES` shaped to `renderActiveModeBanner()` + `renderModesGrid()`; the demo
  branch renders the sample active mode + modes grid with no fetch to `/api/runtime-modes/{active,list}`.
- **orchestration** — `DEMO_ORCH` shaped to `load()`'s `d.rules.rules` + `d.metrics`; the demo branch
  renders sample rules/metrics with no fetch to `/orchestration.json`. (No EventSource.)
- **d-24-cpu-features** — `DEMO_CPU` shaped to `refresh()`/`render()`; the demo branch renders sample
  CPU features with no `fetchJson`; `/api/cpu-features/stream` EventSource guarded.
- **cpu-features** — `DEMO_AVX` shaped to `load()`'s `d.probe`/`d.workloads`/`d.advisory`; the demo
  branch renders sample AVX posture with no fetch to `/cpu-avx.json`. (No EventSource.)
- **d-04-costs** — `DEMO_COSTS` shaped to `render()`/`renderResults()`; `refresh()` short-circuits with
  no `fetchCosts`; `/api/costs/stream` EventSource guarded.
- Contract-lint guards (`_assert_head_demo`) pin each panel's demo no-network path + the `<head>` inline.

## Way forward

- **Stage 0 (this doc)** — SDD-121 + INDEX + mandate E11.M121.
- **Stage 1** — the six panels' DEMO treatment + six lint guards.
- **Stage 2** — full gate + Playwright (demo on, per panel: badge + sample data + demo ids, zero data
  API calls, no page errors) + PR + captures.
- **Next** — batch 3 (punchy verdicts + compute meta: d-01-active-sessions, d-20-peace-machine-health,
  d-18-trust-scores, d-19-super-model-manifest, d-02-profile-choices, profile-generation), then 4–6.

## Cross-references

- SDD-116/119/120 (DEMO + head recipe + batch pattern). SDD-100 — band scheme.
