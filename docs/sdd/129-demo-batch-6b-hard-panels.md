# SDD-129 — DEMO batch 6b (FINAL): 5 hard panels + master-dashboard rich upgrade → 52/52

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the FINAL DEMO increment — the 5 data-rich *hard* panels (**d-25-selfdef-management** SSE, **d-05-traces** / **d-07-memory-changes** / **d-08-rollback-points** query-driven, **d-06-pending-approvals** execute-mid-render) PLUS the **master-dashboard rich upgrade** (operator caught it was mis-classified badge-only in 6a — it is a multi-fetch aggregator that deserves sample data). Completes the DEMO rollout at **52/52 panels**. Recover band (SDD-129 / E11.M129 per SDD-100).
> Derived from / extends: SDD-116/119/123..128 (DEMO + tooling + kind). §1g.

## Mission

Rich DEMO for the 5 hard panels, each with its bespoke interaction gated honestly, plus reclassify
master-dashboard from badge-only to rich. All verified with `make demo-capture`.

## Grounded design (SB-077 / R10212)

- **d-25-selfdef-management (SSE):** `refresh()` short-circuits to `render(DEMO_D25)` (no fetch); the
  `/api/selfdef-management/stream` EventSource is skipped (`if (!demoActive()) try …`). Read-only panel —
  no writes.
- **d-05-traces (query + SSE):** `fetchSpans()` returns `DEMO_D05` (no fetch); the `/api/traces/stream`
  EventSource is skipped; `openDetail()` **honest-defers** ("Trace detail is live-only in demo") instead
  of fetching `/api/traces/<id>`.
- **d-07-memory-changes (query + SSE):** `load()` renders `DEMO_D07` (no fetch); `startSSE()` skipped;
  `navigate()` **honest-defers** ("Navigator is live-only in demo").
- **d-08-rollback-points (query):** `load()` renders `DEMO_D08` (no fetch); `preview()` **honest-defers**
  ("Dry-run rollback plan is live-only in demo"). Demo snapshots use the real `rpool/*` dataset names so
  the static dataset-filter chips render them.
- **d-06-pending-approvals (execute-mid-render):** `refresh()` renders `DEMO_D06` (no fetch); the SSE is
  skipped; **the execute path is disabled** — `handleAction()` early-returns in demo BEFORE any
  `POST /api/control/execute`, so no fake approvals are actionable (R10212). `batch-approve-btn` disabled.
- **master-dashboard (aggregator, was badge-only):** `fetchJSON()` short-circuits to `DEMO_MASTER[path]`
  in demo (or `{}` for unknown paths) — **zero network** across all six-endpoint `Promise.all` sections +
  the m060/ms022/four-watchdog status banners; the apparmor `/metrics` text fetch is skipped too. Reuses
  every existing render fn (routes / catalog / coverage / stats / banners). `window.soDemoApply = refresh`
  for flash-free toggling. Reclassified rich in the manifest.
- Six manifest rows + bespoke lint guards (SSE skips, interaction defers, the d-06 execute-disable, the
  master-dashboard no-network short-circuit).

## Verification

- `make demo-capture --sdd SDD-129` → **6/6 pass** (badge + sample rows + zero data-API + no page errors).
- `make demo-preflight`; `pytest tests/lint/test_demo_mode_contract.py`; full `make test`.

## On completion — 52/52 panels demo-capable

Phase 1 (the DEMO rollout) is complete. Every cockpit panel is explorable with no daemon: opt-in +
always-badged sample data on the data panels, badge-only on the chrome/action/meta panels, nothing
fabricated (SB-077), no web mutation (R10212). Next: Phase 2 (guided tour), Phase 3 (operability), Phase 4
(beauty/UX), + wire `window.soDemoApply` into the remaining rich panels for flash-free toggling.

## Cross-references

- SDD-116/123/127/128 (DEMO + tooling + kind + badge-only). SDD-100 — band scheme.
