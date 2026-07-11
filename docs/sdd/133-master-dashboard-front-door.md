# SDD-133 — Phase 3: master-dashboard front-door resilience (no partial-blank)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the master-dashboard (the cockpit's front door / D-00) is a multi-fetch aggregator whose `refresh()` awaited `Promise.all` over 6 endpoints — so a SINGLE down probe rejected the gather and blanked the entire main view (stats/routes/collisions/discover stuck at `loading…`/`—`, and `renderM060Grid()` — the 4 status banners + mirror grid — never ran because it sat after the await). Recover band (SDD-133 / E11.M133 per SDD-100).
> Derived from / extends: SDD-113 (always-visible honest-offline pattern), SDD-129 (master-dashboard rich DEMO). §1g.

## Mission

Make every section of the front door always-visible with an honest "unreachable" scaffold — one dead
probe can never blank the rest. Presentation-only; no behaviour/data change; R10212 untouched.

## Grounded design (the SDD-113 always-visible pattern)

- **`refresh()`** — the 6-endpoint gather now uses **`Promise.allSettled`** (each section gets its value
  or `{}` — the gather never rejects), and **`renderM060Grid()` is moved ahead of the await** (it fires
  its own per-mirror fetches with internal honest-offline fallbacks, so it's independent of the gather).
- **Per-section honest scaffolds** — `renderStats` is null-safe (`—` per stat when its endpoint is down);
  `renderRoutes` / `renderCollisions` / `renderDiscover` each write an honest "unreachable" line instead
  of dereferencing a possibly-`{}` arg (which previously threw at `for (const p of health.probes)` etc).
- **Initial offline paint** at t=0 so no section shows `loading…` forever before the first fetch.
- The 4 status banners + mirror grid already carried their own honest-offline fallbacks; relocating the
  grid call ahead of the gather lets them actually render.

## Verification

- New `tests/lint/test_master_dashboard_resilience.py` (allSettled + honest scaffolds + initial paint).
- Playwright, all-probes-down (demo off, `file://`): routes/collisions/discover show honest "unreachable"
  scaffolds, stats show `—`, the M060 banner renders, **zero page errors** (previously the view blanked +
  could throw). `demo-capture` on master-dashboard still clean. Full `make test`.

## Cross-references

- SDD-113 (always-visible pattern, e.g. d-23 `renderTiers({offline:true})`); SDD-129 (rich DEMO). SDD-100 — band scheme.
