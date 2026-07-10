# SDD-117 — Code Console assist-pane layout fix + DEMO mode rollout to D-21

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: operator directive 2026-07-10 — *"we can see the that UI for the code page is wrong a bit, especially with the assistant pane open but even when closed, lets fix that while we continue with the demoing"*. Two things in one increment: (1) fix the Code Console 3-pane layout so the conversation isn't crushed when the assistant pane is open; (2) continue the SDD-116 DEMO rollout — D-21 LM Orchestration (D-22 next).
> Derived from / extends: SDD-112 (Code Console), SDD-116 (DEMO mode + the shared `webapp/_shared/demo-mode.{js,css}` helper). §1g operator-surface. Recover band (SDD-117 / E11.M117 per SDD-100).

## Part 1 — Code Console layout fix

**Bug (grounded):** the 3-pane `.cc-grid` used a bare `1fr` center column. A bare `1fr` can't shrink
below its content's min-content width (the longest word), so when the app-shell assistant pane opens
(it steals ~360px via `#so-content { margin-right }`), the center column overflowed and `.cc-msg`'s
`word-break:break-word` broke text mid-word into a vertical sliver. It was cramped even closed.

**Fix:**
- Center column → **`minmax(0,1fr)`** (can now shrink below its longest word — the root fix).
- `.cc-msg` → `overflow-wrap:break-word; word-break:normal` (wrap at spaces; break only long tokens).
- **Reflow when the assistant pane is open** (`body.so-assist-open .cc-grid`) or the viewport ≤1180px:
  drop to **rail + thread** side-by-side and stack the **Plan** pane full-width below, so the
  conversation keeps a comfortable column. Single-column stack ≤820px (as before).

## Part 2 — DEMO mode for D-21 (reuses the SDD-116 shared helper)

Applies the SDD-116 pattern verbatim to **D-21 LM Orchestration** (an operator-named panel): inline the
shared `demo-mode.{js,css}` helper, add a `demoActive()` short-circuit in `refresh()` that renders
badged sample data (`DEMO_GRID` / `DEMO_PROFILES` / `DEMO_FEATURES`, obvious `demo/…` placeholder ids)
with **zero network calls** (no fetch, **no EventSource** in DEMO), behind the persistent DEMO badge.
Same SB-077 reconciliation (opt-in + always-badged), operator-confirmed in SDD-116.

## Goals

- Code Console conversation stays readable with the assistant pane open (and is cleaner when closed).
- D-21 is DEMO-capable via the shared helper (badged sample orchestration; zero network in DEMO).
- Contract-lint guards for both (the layout reflow + the D-21 DEMO no-network path).

## Non-goals

- D-22 LM Status & Operability (the immediate next DEMO increment — same pattern).
- No change to Code Console/D-21 live behaviour; no new data model; no web mutation.

## Open questions

| Q | Question | Proposed |
|---|---|---|
| Q-117-A | Assist-open reflow: 2-col (rail+thread, plan below) vs full stack. | **proposed: 2-col + plan-below** — keeps rail + conversation side-by-side (the important panes); the honest-deferred Plan drops below. |

## Way forward (stages)

- **Stage 0 (this doc)** — SDD-117 + INDEX + mandate E11.M117.
- **Stage 1** — Code Console CSS fix + D-21 DEMO (helper + `demoActive()` branch + sample data) +
  contract-lint guards.
- **Stage 2** — full gate + Playwright (Code Console assist-open reflow, no message overflow; D-21 DEMO
  badged sample grid/profiles/features, zero orchestration API calls) + commit/push/draft PR.

## Cross-references

- SDD-112 (Code Console), SDD-116 (DEMO mode + shared helper), M067 app-shell (`so-assist-open`).
- SDD-100 — parallel-session band scheme (recover band 100–199 / E11.M100–199).
