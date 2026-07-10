# SDD-127 — DEMO batch 5b: badge-only support + 5 static dashboards

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the operator-approved broad DEMO rollout (roadmap Phase 1). Batch 5b — **trinity, weaver, auditor, router, global-history**. Recon found these are NOT multi-fetch aggregators (the plan's assumption): they are static informational/navigational dashboards whose only fetch is the shared control-surface. The honest treatment per SB-077 is **badge-only** — there is no telemetry to sample, so nothing is fabricated. Recover band (SDD-127 / E11.M127 per SDD-100).
> Derived from / extends: SDD-116/119/123..126 (DEMO + tooling). §1g.

## Mission

Add **badge-only** DEMO support to the tooling and apply it to the 5 static dashboards. A badge-only panel
inlines the shared `demo-mode.{js,css}` helper in `<head>`; the helper auto-renders the DEMO badge when
demo is on (`readyState`-gated `badge()` call) — no `DEMO_<X>` sample data, no `demoActive()` branch,
nothing fabricated. This is the honest treatment for panels with no daemon dependency: they are already
fully explorable with no daemon, so DEMO just marks them consistently with the badge.

## Grounded design (no fabricated data)

- **Manifest** — `scripts/webapp/demo-panels.json` gains a `kind` field: `rich` (default; has a
  `DEMO_<X>` const) or `badge-only` (`demoConst`/`apiPrefix`/`rowSelector` all null). The 5 panels are
  added as `badge-only`.
- **Capture tool** — `demo-capture.mjs` skips the rows + data-API assertions when `apiPrefix`/`rowSelector`
  are null; a badge-only panel passes on **badge present + zero page errors**.
- **Lint** — `test_manifest_panels_satisfy_the_generic_demo_contract` branches on `kind`: badge-only panels
  assert only helper-in-`<head>` + badge text + `demoConst is null` (nothing fabricated). The drift guard
  (`test_manifest_covers_exactly_the_demo_capable_panels`) already covers them (they carry `so-demo-badge`).
- Presentation-only; no fetch added, no web mutation. R10212/SB-077 untouched.

## Way forward

- **Verify** — `make demo-preflight`; `make demo-capture --sdd SDD-127` (5/5: badge + no errors);
  `pytest tests/lint/test_demo_mode_contract.py`; full `make test` + PR + captures.
- **Next** — batch 6: the remaining data-rich hard panels (d-25 SSE, d-05/07/08 query-driven, d-06
  execute-mid-render) get rich DEMO; the remaining chrome/action/meta panels (build-configurator, emulate,
  flash, master-dashboard, compliance, auth-tier, anti-minimization-audit, surface-map, doc-coverage,
  ux-design-audit) get the same badge-only treatment via this new manifest `kind`.

## Cross-references

- SDD-116/119/123/126 (DEMO + head recipe + tooling + manifest). SDD-100 — band scheme.
