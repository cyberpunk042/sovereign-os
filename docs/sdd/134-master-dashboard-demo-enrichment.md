# SDD-134 — Phase 3: enrich the master-dashboard DEMO front door (busy + healthy, zero-network)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the operator looked at the DEMO capture of the master-dashboard (D-00 front door) and asked *"the screenshot you showed is a bad Demo no?"* — the SDD-129 demo data was thin (3 routes, 2 manifests, 1 catalog dashboard, 0 control systems) and the four health banners + M060 mirror grid stayed "unreachable" in DEMO (their direct fetches were never demo-gated), so the front door read empty rather than busy. This enriches `DEMO_MASTER` and demo-gates the banner/grid fetchers so the DEMO view reads as a busy, healthy box. Presentation-only; zero-network; badged. Recover band (SDD-134 / E11.M134 per SDD-100).
> Derived from / extends: SDD-129 (master-dashboard rich demo), SDD-133 (front-door resilience), SDD-116 (DEMO contract). §1g.

## Mission

Make the opt-in DEMO front door demonstrate a healthy, populated box with no daemon — more routes, more discovered manifests, a full catalog with mixed live/snapshot/planned statuses, real coverage numbers, and all four health banners (M060 chain / MS022 SSE quota / four-watchdog IPS spine / AppArmor) + the M060 mirror grid showing green — all from client-side sample data, zero network, always badged.

## Grounded design (webapp/master-dashboard/index.html only)

- **`DEMO_MASTER` enriched** (the client-side sample constant read by `fetchJSON`'s demo short-circuit):
  - `/routes` 3 → **7** (all reachable); `/health` **7/7**; `/toggles` 6 on + 1 OFF (exercises the on/OFF pill + the disabled-row dimming).
  - `/discover` 2 → **4** selfdef manifests (mixed auth-tiers L1/L2).
  - `/catalog` 1 → **8** dashboards across **3** categories (compute/defense/operate) with mixed **live/snapshot/planned** status badges (the planned card carries a `demo/` CLI hint).
  - `/control-systems` 0 → **8** systems (drives the coverage `CONTROL SYSTEMS` stat); `/feature-coverage` bumped to **22 mapped / 5 waived / 27 families**.
  - `/api/m060/health` gains an **8-artifact** array (all present + parseable + fresh) so the M060 grid tiles classify **online**.
- **Banner + grid fetchers demo-gated** (each short-circuits to `DEMO_MASTER` sample data — **no `fetch` in the demo path**): `renderM060HealthBanner`, `renderMS022SseQuotaBanner`, `renderFourWatchdogBanner`, `fetchM060ArtifactHealthMap`, `fetchMirrorStatus` (new `DEMO_M060_MIRROR` = online). `renderApparmorBanner` (whose two probes were already `!demoActive()`-guarded) gets a synthetic enforcing-profile metrics blob in DEMO so it reads `enforce` / OK.
- All sample ids keep the obvious `demo/` placeholder prefix (SB-077 — never confusable with live telemetry).

## R10212 / SB-077 preserved

Presentation-only. No new endpoint, no write path, no `fetch` on the demo path (every gated fetcher returns a client-side constant). DEMO stays opt-in (off by default), always badged ("sample data — not real telemetry"), and every fabricated id is `demo/`-prefixed. R10212 (exec daemon is the only write path) untouched.

## Verification

- `make demo-capture PANELS=master-dashboard` (demo on): **badge=true · rows=7 · dataApiCalls=0 · pageErrors=0**.
- NEW `tests/lint/test_master_dashboard_demo_richness.py` pins the enrichment floor (≥6 routes, health parity, ≥3 catalog dashboards with mixed statuses, ≥6 control systems, the 4 banners demo-gated) so it can't silently regress to a thin front door.
- SDD-133 resilience lint still green (allSettled + honest scaffolds + initial paint untouched); full `make test`.

## On completion

The DEMO front door reads as a busy, healthy box end-to-end. Remaining Phase-3 items (non-security): cross-panel deep links (sibling `D-xx` refs → clickable `../<slug>/`) + Cmd-K palette coverage.

## Cross-references

- SDD-129 (master-dashboard rich demo); SDD-133 (front-door resilience); SDD-116 (DEMO contract); `scripts/webapp/demo-panels.json` (manifest); `scripts/webapp/demo-capture.mjs` (capture/verify). SDD-100 — band scheme.
