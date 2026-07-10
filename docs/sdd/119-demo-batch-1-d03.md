# SDD-119 — DEMO mode rollout (batch 1 start): D-03 Model Health

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: operator directive 2026-07-10 — *"broader demo support please, lets make a plan"* → the approved broad DEMO rollout plan. Batch 1 = the highest-value LM/compute panels; this increment ships **D-03 Model Health** (the flagship "see the models serving" panel) and establishes the recipe refinement (helper in `<head>`). The rest of batch 1 (d-23-models-catalog, models-catalog, d-11-adapter-status, d-10-eval-history) follow as the immediate next increments.
> Derived from / extends: SDD-116 (DEMO mode + shared helper), SDD-117/118 (D-21/D-22 DEMO). §1g operator-surface. Recover band (SDD-119 / E11.M119 per SDD-100).

## Mission

Apply the SDD-116 DEMO pattern to **D-03 Model Health**: opt-in, always-badged sample data so the panel
is explorable with no daemon. `refresh()` gains a `demoActive()` short-circuit that renders a badged
`DEMO_HEALTH` snapshot (obvious `demo/…` placeholder ids; sample summary + SRP roles + p50/p95/p99
latency + KV-cache + 24h heatmap) with **zero network calls** (no fetch, no EventSource). Same SB-077
reconciliation (opt-in + always-badged + no fabrication-as-real).

## Recipe refinement (applies to the whole rollout)

The shared `demo-mode.{js,css}` helper is inlined in **`<head>`** (not after `</footer>`), so
`window.soDemo` exists before the panel's main script runs its first `refresh()` — otherwise `demoActive()`
is `false` on the first paint and the panel fetches live. (The 3 done panels happened to place their
script after the footer, so their after-footer inline worked; head-injection is the robust universal rule
for the rollout — panels like D-03 have no `<footer>` and run `refresh()` inline.)

## Grounded design (no new data)

- `DEMO_HEALTH` is shaped to `refresh()`'s consumer (`s.summary{total,blackwell,rtx4090,cpu}`,
  `s.roles{conductor,logic,oracle}`, `s.models[]`, `s.kvcache[]`, `s.heatmap[]`).
- `refresh()`: `const s = demoActive() ? DEMO_HEALTH : await fetchHealth();` + set the DEMO banner +
  `soDemo.badge()` when demo; the rest of the existing render runs unchanged.
- The `new EventSource('/api/models/stream')` is skipped in demo (`if (demoActive()) throw` before it).
- A contract-lint guard pins the D-03 DEMO no-network path + the `<head>` inline.

## Way forward

- **Stage 0 (this doc)** — SDD-119 + INDEX + mandate E11.M119.
- **Stage 1** — D-03 DEMO (head-inlined helper + `demoActive()` branch + `DEMO_HEALTH`) + lint guard.
- **Stage 2** — full gate + Playwright (demo on: badge + sample summary/roles/latency/KV/heatmap, zero
  models API calls) + commit/push/draft PR.
- **Next increments** — batch-1 remainder (d-23, models-catalog, d-11, d-10), then batches 2–6 per plan.

## Cross-references

- SDD-116 (DEMO mode + shared helper), SDD-117/118 (D-21/D-22 DEMO). SDD-100 — band scheme.
