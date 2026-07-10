# SDD-110 — D-11 adapter-status view-state persistence (remember the 4 filters)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-10
> Closes findings: D-11 has export + filters but forgets the filters on reload
> Derived from: operator goal "god-tier dashboards" (§1g operator-surface) — applying the proven SDD-108 view-persistence pattern to the highest-traffic facet panel. Recover-projects band (SDD-110 / E11.M110).

## Mission

Make D-11 Adapter Status **remember the operator's filters**. D-11 is where operators live deciding
adapter placement; it already has CSV export + 4 filter selects (base / precision / training /
status), but reloading resets them — narrow to "base=Qwen3-Coder, precision=NVFP4, status=pending",
reload, and it's all-adapters again. Add **view-state persistence** (the SDD-108 pattern): the 4
filters are saved to `localStorage` and restored on load. Pure client-side, schema-guarded, distinct
key. Non-trivial vs models-catalog because D-11 is **SSE-refreshed** and `#base-filter`'s options are
**rebuilt dynamically each refresh** — so the restore seeds once, after the options first exist.

## Problem

`webapp/d-11-adapter-status/index.html`: `refresh()` fetches `/api/adapters/inventory`, rebuilds
`#base-filter` options from the live adapter set (preserving its current value), reads the 4 filter
values, filters + renders. It's driven by `#refresh-btn`/`#apply-btn`, the adapter SSE stream
(`EventSource('/api/adapters/stream')`), an error-interval, and the init call. None of the filter
state survives a reload — the panel inlines the app-shell `loadPrefs`/`savePrefs` localStorage idiom
(keyed `sovereign-os.personalization`) but uses it only for theme.

## Grounded design — save on change, seed once after options exist, schema-guarded

- **`VKEY = "sovereign-os.d-11-adapter-status.view"`, `VSCHEMA = 1`** — a distinct key.
- **`saveView()`** — `{schema:VSCHEMA, f:{base,precision,training,status}}` → `localStorage.setItem`
  (try/catch, never throws).
- **`restoreView()`** — parse + `schema===VSCHEMA` guard; set each select's `.value` **only when the
  value is still a real `<option>`** (a stale base-model / precision is dropped); try/catch → a
  garbage/absent entry silently falls back to defaults. Never crashes, never applies invalid state.
- **Seed once**: a module flag `let viewRestored = false;`; inside `refresh()`, right **after** the
  `#base-filter` options are (re)built and **before** the filter values are read,
  `if (!viewRestored) { restoreView(); viewRestored = true; }` — so the first render reflects the
  restored filters, and later SSE refreshes preserve them (base via the existing currentVal
  preservation; the 3 static selects retain their value).
- **Wire `saveView()`** to each of the 4 filters' `change` events (persist immediately on pick).
- **`#clear-view` button** — reset the 4 filters + `removeItem(VKEY)` + `refresh()`. The escape hatch.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-110-A | Seed timing under SSE. | **answered (operator, 2026-07-10): seed once via a `viewRestored` flag inside `refresh()`** (after base options are (re)built) — robust to the dynamic `#base-filter` + SSE re-renders. |
| Q-110-B | Stale-value handling. | **answered: drop silently** — a saved base-model/precision no longer offered is ignored; that field falls back to "all". |
| Q-110-C | A shared cross-panel view-state helper. | **proposed: Stage-N** — with models-catalog (SDD-108) + d-11 now persisting, extracting `_shared/table-view.js` (inline-lockstep) is a future increment once a 3rd consumer lands. |

## Non-goals (Stage N)

- New fetch / EventSource / `/api/` mutation (the view code is pure `localStorage`; the pre-existing
  inventory fetch + adapter SSE stream are untouched).
- Any change to `refresh()` filtering/render output, the export, or the adapter data flow.
- A distinct-key collision with personalization.
- Rollout to other panels (Q-110-C).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 110 + mandate E11.M110.
- **Stage 1:** `VKEY`/`VSCHEMA` + `viewRestored` + `saveView`/`restoreView` + the seed in `refresh()` +
  `#clear-view` + a contract lint.
- **Stage 2:** full gate + Node round-trip e2e + ship.

## Safety invariants

Pure **client-side** — no fetch, no server state, no `/api/` mutation; the pre-existing inventory fetch
+ adapter SSE stream are untouched (R10212). **SB-077** — `restoreView` never crashes or applies
invalid state: schema-guarded, stale options dropped, try/catch fallback. Distinct `VKEY` (no
personalization collision). No change to `refresh()` output, the export, or the adapter data flow.
MS003 `unsigned-pending-MS003`.

## Cross-references

- `webapp/d-11-adapter-status/index.html` — the 4 filters + `refresh()` this extends.
- `webapp/models-catalog/index.html` (SDD-108) — the `saveView`/`restoreView`/`clearView` pattern
  reused; the app-shell `loadPrefs`/`savePrefs` localStorage idiom.
- `tests/lint/test_models_catalog_export_contract.py` — the view-persistence lint template.
- SDD-108 (models-catalog view persistence), R10137 (localStorage pattern), R10212, SB-077.
