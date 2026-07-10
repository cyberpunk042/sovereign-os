# SDD-115 — d-24-cpu-features + d-25-selfdef-management stay fully visible when their daemon is offline

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the SDD-113 sequenced follow-ups — d-24-cpu-features and d-25-selfdef-management carry the identical banner-only-`catch` anti-pattern SDD-113 fixed on d-23. Closes the operator's D-21 bug class *"I dont see the grid... only an Apply button"* + the standing *"seeing all sections with all content too"* for the last two twins.
> Derived from / extends: SDD-113 (d-23 fix), SDD-111 (the always-visible / honest-deferred lesson). §1g operator-surface. Recover band (SDD-115 / E11.M115 per SDD-100).

## Mission

Apply the SDD-113 fix verbatim to the two remaining twins the recon flagged: **d-24-cpu-features** and
**d-25-selfdef-management**. Both call their `render()` only on the successful fetch; the `catch` sets
only `#data-source-banner` and there is no initial paint — so a daemon-down blanks the whole panel
(d-24's `#cpu-summary`/`#extensions`/`#workloads`/`#advisory`; d-25's tiles + `#mirror-panels`). Fix:
an initial paint + a `catch` fallback + an explicit honest offline branch in `render()`, so every
section stays visible with an honest "daemon unreachable" state, never blank (SB-077).

## Grounded fix (both — no new data)

- **d-24**: `render()` gains an `offline` branch (an honest "cpu-features daemon unreachable" card in all
  four sections); the `catch` calls `render({offline:true},{},{})`; an initial paint runs before the
  fetch.
- **d-25**: `render()` gains an `offline` branch (tiles → "unreachable", `#mirror-panels` → an honest
  card naming the M060 mirror-chain + D-13..D-18 panels that will populate when reachable); the `catch`
  calls `render({offline:true})`; an initial paint runs before the fetch.
- **Contract-lint guard** on each panel pinning the initial paint + the catch fallback.
- **No new fetch / EventSource / mutation** — pure render-path change (R10212 preserved by construction).

## Goals

- d-24 + d-25 render their full section scaffold when the daemon is offline (honest, never blank).
- A contract-lint guard per panel pins it.

## Non-goals

- master-dashboard's partial-blank (a different `Promise.all` + `el()` shape; a separate increment).
- No new producers, data-model change, or web mutation.

## Open questions

| Q | Question | Proposed |
|---|---|---|
| Q-115-A | Both panels in one increment? | **proposed: yes** — identical mechanical fix; one small reviewable PR closes the twin set (d-23 already shipped in SDD-113). |

## Way forward (stages)

- **Stage 0 (this doc)** — SDD-115 + INDEX + mandate E11.M115.
- **Stage 1** — d-24 + d-25 render-path fixes + contract-lint guards.
- **Stage 2** — full gate + Playwright (both daemon-down: full scaffold + honest offline cards, zero
  errors) + commit/push/draft PR.

## Cross-references

- SDD-113 — the d-23 fix this replicates; SDD-111 — the always-visible lesson.
- SDD-100 — parallel-session band scheme (recover band 100–199 / E11.M100–199).
