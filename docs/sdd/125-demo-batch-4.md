# SDD-125 — DEMO mode rollout (batch 4): selfdef mirror family

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the operator-approved broad DEMO rollout (roadmap Phase 1). Batch 4 after SDD-119..122 (batches 1–3) + SDD-123 tooling + SDD-124 gear. Ships the **selfdef mirror family** — **d-12-networking**, **d-13-filesystem-grants**, **d-14-capability-tokens**, **d-15-sandboxes**, **d-16-audit**, **d-17-quarantine** — so an operator can explore the selfdef mirror surfaces with no daemon. First batch verified end-to-end with the SDD-123 `make demo-capture` tool (no throwaway script).
> Derived from / extends: SDD-116 (DEMO + shared helper), SDD-119 (head-injection recipe), SDD-123 (tooling + manifest). §1g. Recover band (SDD-125 / E11.M125 per SDD-100).

## Mission

Apply the SDD-116 DEMO pattern to the six selfdef-mirror panels. Each: the shared `demo-mode.{js,css}`
helper inlined in `<head>` (SDD-119 rule), a `demoActive()` gate, a badged `DEMO_D1X` sample constant with
obvious `demo/…`|`demo-…` placeholder ids, and **zero network calls** in the demo path. Opt-in +
always-badged SB-077 reconciliation; §1g — every section renders. Added to `scripts/webapp/demo-panels.json`
so the tool + lint cover them automatically.

## Grounded design (no new data)

- **Five uniform mirror panels** (d-13/14/15/16/17) share the `/api/d-XX/snapshot` envelope
  (`schema_version` / `mirror_status` / `captured_at` + `summaries[]` + a payload array, consumed via
  `if (r.ok) seed = Object.assign(seed, await r.json())`, arg-less `renderMirrorBanner()`, no EventSource).
  Demo branch: `if (demoActive()) { seed = Object.assign(seed, DEMO_D1X); } else { …fetch… }` — no fetch in
  demo — plus a `renderMirrorBanner()` DEMO-label override + badge. Payload shapes differ per domain
  (`grants` / `tokens` / `allocations` / `spans`+`integrity` / `entries`+`declaration_fields`).
- **d-12-networking** (outlier): leaner envelope (`mirror_status` only), full-replace
  `applySnapshot(await r.json())`, arg-less `renderBanner()` (`ds-*` ids), and a live
  `new EventSource('/api/d-12/stream')` inside `startSSE()`. Demo branch: `if (demoActive()) {
  applySnapshot(DEMO_D12); …DEMO ds-label + badge; return; }`; the SSE is skipped
  (`if (!demoActive()) startSSE();`).
- Contract-lint guards + the manifest generic contract pin each panel's demo no-network path + `<head>`
  inline. R10212/SB-077 untouched.

## Way forward

- **Stage 0 (this doc)** — SDD-125 + INDEX + mandate E11.M125.
- **Stage 1** — the six panels' DEMO treatment + manifest rows + lint guards.
- **Stage 2** — `make demo-preflight`; `make demo-capture --sdd SDD-125` (badge + sample rows + zero data
  API + no errors); `pytest tests/lint/test_demo_mode_contract.py`; full `make test` + PR + captures.
- **Next** — batch 5 (edge/mgmt/own-daemon dashboards: selfdef-management, edge-firewall, network-edge,
  ups, science, trinity, weaver, auditor, router, global-history), then batch 6 (hard + badge-only).

## Cross-references

- SDD-116/119/123 (DEMO + head recipe + tooling). SDD-100 — band scheme.
