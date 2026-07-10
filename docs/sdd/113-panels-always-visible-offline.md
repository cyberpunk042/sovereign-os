# SDD-113 — Cockpit panels stay fully visible when their daemon is offline (d-23 first; d-24/d-25 to follow)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the operator's verbatim D-21 bug — *"when i pull and launch the panels the D-21 I dont see the grid... only an Apply button"* — and the standing directive *"seeing all sections with all content too"* (2026-07-10). SDD-111 fixed D-21 + D-22; a recon then found the SAME "collapses to empty when the daemon is offline" anti-pattern in the three direct twins d-23 / d-24 / d-25.
> Derived from / extends: SDD-111 (the always-visible / honest-deferred lesson). §1g operator-surface. Recover band (SDD-113 / E11.M113 per SDD-100).

## Mission

Make the cockpit panels render their **full section scaffold** even when the backing daemon is
unreachable — an honest empty/`—`/offline state, never a blank content area. SDD-111 established the
pattern (a `FIXED_*` fallback + an initial paint + a fallback render in the fetch `catch`). This SDD
applies it to the three panels a recon flagged with the identical banner-only-`catch` anti-pattern:
**d-23-models-catalog**, **d-24-cpu-features**, **d-25-selfdef-management**. This increment ships
**d-23** (the highest-traffic of the three — the portfolio view); **d-24** and **d-25** follow as their
own increments (same pattern, verbatim).

## The anti-pattern (grounded)

`webapp/d-23-models-catalog/index.html`: `renderTiers(data)` sets `#summary` + `#tiers` innerHTML, but
is called **only** on the successful fetch path (`refresh()`); the `catch` sets only
`#data-source-banner`, leaving `#summary` + `#tiers` empty, and there is **no initial paint**. Result:
daemon-down → the whole catalog area is blank (only the banner shows). Identical shape to pre-fix
D-21/D-22.

## Grounded fix (d-23 — SB-077, no new data)

- **`renderTiers({})` initial paint** before the live fetch, so the section is visible immediately.
- **`renderTiers` handles the offline/empty case explicitly** — an honest "the models-catalog daemon
  is unreachable — the registry will list here when it's reachable" card (distinct from a real empty
  catalog), never a blank `#tiers`.
- **`catch` fallback render** — the `catch` calls `renderTiers({offline:true})` so an unreachable
  daemon keeps the scaffold visible (banner already reports the reason).
- **Contract-lint guard** — a test pins that the catch renders a fallback + an initial paint runs, so
  the panel can't regress to blank.
- **No new fetch / EventSource / mutation** — pure render-path change; the pre-existing catalog fetch +
  SSE are untouched (R10212 preserved by construction).

## Goals

- d-23 renders its full section scaffold when the daemon is offline (honest, never blank).
- A contract-lint guard pins the behaviour.
- Zero change to the live-data render output, the fetch, or the SSE.

## Non-goals (this increment)

- d-24-cpu-features + d-25-selfdef-management (same fix; sequenced as SDD-114 / SDD-115 or follow-up
  stages — named here, not minimized).
- master-dashboard's partial-blank (a different `Promise.all` + `el()` shape; a separate increment).
- No new producers, no data-model change, no web mutation.

## Open questions

| Q | Question | Proposed |
|---|---|---|
| Q-113-A | One SDD covering all three twins, or one-panel-per-increment? | **proposed: d-23 this increment; d-24/d-25 as follow-ups** — keeps each PR small + independently reviewable (the fix is identical, so the follow-ups are mechanical). |
| Q-113-B | Offline vs empty wording. | **proposed: distinguish** — an unreachable daemon says "daemon unreachable", a genuinely empty catalog says "catalog empty"; both honest, neither blank (SB-077). |

## Way forward (stages)

- **Stage 0 (this doc)** — SDD-113 + INDEX + mandate E11.M113.
- **Stage 1** — d-23 render-path fix + a contract-lint guard.
- **Stage 2** — full gate + Playwright (daemon-down: full catalog scaffold + honest offline card, zero
  errors) + commit/push/draft PR.

## Cross-references

- SDD-111 — the always-visible / honest-deferred lesson (the pattern this reuses).
- SDD-100 — parallel-session band scheme (recover band 100–199 / E11.M100–199).
