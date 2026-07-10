# SDD-128 — DEMO batch 6a: badge-only for the 10 chrome/action/meta panels

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: DEMO rollout batch 6a (final phase). Badge-only DEMO for the chrome/action/meta panels that have no daemon telemetry to sample: **build-configurator, emulate, flash** (action panels — run real host actions), **master-dashboard, compliance, auth-tier, anti-minimization-audit, surface-map, doc-coverage, ux-design-audit** (meta/audit views). Recover band (SDD-128 / E11.M128 per SDD-100).
> Derived from / extends: SDD-127 (badge-only `kind` machinery). §1g.

## Mission

Apply the SDD-127 badge-only treatment to the 10 remaining chrome/action/meta panels: inline the shared
`demo-mode.{js,css}` helper in `<head>` (auto-renders the DEMO badge when demo is on) and register each in
`scripts/webapp/demo-panels.json` as `"kind": "badge-only"`. No `demoActive()` branch, no `DEMO_<X>`
data — these panels either run real host actions (nothing honest to sample) or are meta/audit views of the
cockpit itself, so per SB-077 nothing is fabricated; the badge just marks DEMO consistently.

## Grounded design (no fabricated data)

- One atomic Python script inlines the head-block into all 10 panels.
- 10 `badge-only` rows added to the manifest → the drift guard + generic contract lint cover them; the
  capture tool asserts badge present + zero page errors (rows + data-API skipped for badge-only).
- Presentation-only; no fetch, no web mutation. R10212/SB-077 untouched.
- After 6a: **47/52** panels demo-capable. Batch 6b (the 5 data-rich hard panels: d-25 SSE, d-05/07/08
  query-driven, d-06 execute-mid-render) completes the rollout at 52/52.

## Way forward

- **Verify** — `make demo-preflight`; `make demo-capture --sdd SDD-128` (10/10: badge + no errors);
  `pytest tests/lint/test_demo_mode_contract.py`; full `make test` + PR + captures.
- **Next** — batch 6b (SDD-129), then Phases 2–4.

## Cross-references

- SDD-127 (badge-only `kind`); SDD-123 (tooling + manifest). SDD-100 — band scheme.
