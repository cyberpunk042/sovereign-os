# SDD-122 — DEMO mode rollout (batch 3): punchy verdicts + compute meta

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the operator-approved broad DEMO rollout (roadmap Phase 1). Batch 3 after SDD-119/120/121 (batches 1–2). Ships the **verdicts + compute-meta** panels in one PR (operator: "you can do a bigger PR... not one thing at the time") — **d-01-active-sessions**, **d-20-peace-machine-health**, **d-18-trust-scores**, **d-19-super-model-manifest**, **d-02-profile-choices**, **profile-generation** — so an operator can explore active sessions, machine health verdict, trust scores, the super-model manifest, profile choices, and profile generation with no daemon.
> Derived from / extends: SDD-116 (DEMO + shared helper), SDD-119 (head-injection recipe), SDD-120/121 (batch pattern). §1g. Recover band (SDD-122 / E11.M122 per SDD-100).

## Mission

Apply the SDD-116 DEMO pattern to the six batch-3 panels in a single PR. Each: the shared
`demo-mode.{js,css}` helper inlined in `<head>` (SDD-119 rule), a `demoActive()` gate, and a badged
`DEMO_<X>` sample constant shaped to the panel's render fn with obvious `demo/…` placeholder ids, and
**zero network calls** in the demo path (d-01's `/api/sessions/stream` EventSource skipped; the
`/api/d-XX/snapshot` + `/api/profile/show` + static `/profile-generation.json` fetches never evaluated
in demo). Opt-in + always-badged SB-077 reconciliation; §1g — every section renders.

## Grounded design (no new data)

- **d-01-active-sessions** — `DEMO_SESSIONS` shaped to `renderSessions()`/`renderStepBar()`; `refresh()`
  short-circuit (no `fetchSessions`); `/api/sessions/stream` EventSource guarded by `!demoActive()`.
- **d-20-peace-machine-health** — `DEMO_D20` shaped to `load()`'s `/api/d-20/snapshot` render; demo
  branch renders the sample health verdict with no fetch.
- **d-18-trust-scores** — `DEMO_D18` shaped to `render()`/`renderTiles()`/`renderTools()`; demo branch
  renders sample trust tiles with no fetch to `/api/d-18/snapshot`.
- **d-19-super-model-manifest** — `DEMO_D19` shaped to `render()`/`renderMs()`/`renderPhases()`; demo
  branch renders the sample manifest with no fetch to `/api/d-19/snapshot`.
- **d-02-profile-choices** — `DEMO_PROFILE` shaped to `renderCards()`/`renderGates()`/`renderLadder()`;
  `refresh()` short-circuit with no fetch to `/api/profile/show`.
- **profile-generation** — `DEMO_PROFGEN` shaped to `load()`'s `/profile-generation.json` render; demo
  branch renders sample generation with no fetch.
- Contract-lint guards (`_assert_head_demo`) pin each panel's demo no-network path + the `<head>` inline.

## Way forward

- **Stage 0 (this doc)** — SDD-122 + INDEX + mandate E11.M122.
- **Stage 1** — the six panels' DEMO treatment + six lint guards.
- **Stage 2** — full gate + Playwright (demo on, per panel: badge + sample data + demo ids, zero data
  API calls, no page errors) + PR + captures.
- **Next** — batch 4 (selfdef mirror family: d-12-networking, d-13-filesystem-grants, d-14-capability-tokens,
  d-15-sandboxes, d-16-audit, d-17-quarantine — uniform `/api/d-XX/snapshot` shape), then 5–6.

## Cross-references

- SDD-116/119/120/121 (DEMO + head recipe + batch pattern). SDD-100 — band scheme.
