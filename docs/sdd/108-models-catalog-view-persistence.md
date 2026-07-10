# SDD-108 — models-catalog view-state persistence (remember filter + sort)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-10
> Closes findings: the cockpit data panels forget the operator's view on reload/navigation
> Derived from: operator goal "god-tier dashboards" — a genuinely-useful client-side ergonomic (not export-copy). Recover-projects band (SDD-108 / E11.M108).

## Mission

Make the models-catalog browser **remember how you were looking at it**. Today, when the operator
filters the 68-model catalog to "class=rlm, max VRAM 48, sorted by context window" and navigates away
or reloads, every facet + the sort reset to defaults. Add **per-panel view-state persistence** — the
6 facet filters + the sort column/direction are saved to `localStorage` and restored on load. Pure
client-side, reusing the established `loadPrefs`/`savePrefs` localStorage idiom; schema-guarded so a
stale/garbage entry never crashes or applies invalid state.

## Problem

`webapp/models-catalog/index.html`: `filtered()` reads 6 inputs (`f-tier / f-class / f-quant /
f-purpose / f-status` selects + `f-vram` number); `sortK`/`sortAsc` hold the sort; `buildFilters()`
fills the select options from the loaded `MODELS` and wires input→render + sort-header→render;
`load()` does `buildFilters(); renderStats(); render();`. None of this state survives a reload — the
panel already inlines the app-shell `loadPrefs`/`savePrefs` (keyed `sovereign-os.personalization`)
but uses it only for theme, never for the view.

## Grounded design — save on change, restore on load, schema-guarded

- **`VKEY = "sovereign-os.models-catalog.view"`, `VSCHEMA = 1`** — a **distinct** key so the view
  never collides with personalization prefs.
- **`saveView()`** — read the 6 filter inputs + `sortK`/`sortAsc` → `localStorage.setItem(VKEY,
  JSON.stringify({schema:VSCHEMA, f:{tier,class,quant,purpose,status,vram}, sortK, sortAsc}))`
  (try/catch, never throws).
- **`restoreView()`** — `JSON.parse(localStorage.getItem(VKEY))`; if `v.schema===VSCHEMA`: set each
  `el("f-…").value` from `v.f` **only when that value is still a real `<option>`** (a facet value no
  longer in the catalog is dropped, not applied) and `f-vram` only when numeric; set `sortK` **only
  if it matches a real `th[data-k]`** and `sortAsc` only if boolean. Whole thing in try/catch → a
  garbage/absent entry silently falls back to defaults.
- **Wire** `saveView()` into the existing filter-input listener + the sort-header handler (alongside
  `render()`); the export buttons don't touch the view.
- **`load()`** → `buildFilters(); restoreView(); renderStats(); render();` — restore AFTER the
  options exist (so `select.value=` sticks) and BEFORE the first render (programmatic `.value=`
  doesn't fire `input`, so no double-render).
- **`#clear-view` button** — reset the 6 filters + `sortK/sortAsc` to defaults,
  `localStorage.removeItem(VKEY)`, `render()`. The escape hatch so a remembered view is never a trap.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-108-A | Persistence scope. | **answered (operator, 2026-07-10): this panel only** (its own `VKEY`) — a bounded first instance; rolling the pattern out to the other facet/sort panels is Stage-N. |
| Q-108-B | Stale-value handling. | **answered: drop silently** — a saved facet no longer in the catalog (or an unknown sort column) is ignored; the view falls back to default for that field. |
| Q-108-C | A shared cross-panel view-state helper. | **proposed: Stage-N** — extract `saveView`/`restoreView` into a shared snippet once ≥2 panels adopt it (the inclusion mechanics need their own increment). |

## Non-goals (Stage N)

- Server state / any `/api/` call (pure `localStorage`; the export-contract R10212 guard still holds).
- Any change to `filtered()` / the sort comparator / `render()` output — only the inputs + `sortK/
  sortAsc` are pre-seeded.
- A localStorage key shared with personalization (distinct `VKEY`).
- Rollout to other panels (Q-108-A/C).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 108 + mandate E11.M108.
- **Stage 1:** `VKEY`/`VSCHEMA` + `saveView`/`restoreView` + wiring + `#clear-view` + a contract lint.
- **Stage 2:** full gate + Node round-trip e2e + ship.

## Safety invariants

Pure **client-side** — no fetch, no server state, no `/api/` mutation (the panel stays a read-only
browser; its export-contract R10212 guard is unchanged). **SB-077** — `restoreView` never crashes or
applies invalid state: schema-guarded, stale facet values + unknown sort columns dropped, try/catch
fallback to defaults. Distinct `VKEY` (no personalization-pref collision). No change to the served
catalog, the fetch, or the filter/sort/render logic. MS003 `unsigned-pending-MS003`.

## Cross-references

- `webapp/models-catalog/index.html` — `filtered()` inputs + `sortK`/`sortAsc` + `buildFilters()`
  wiring this extends; the `loadPrefs`/`savePrefs` localStorage idiom reused.
- `tests/lint/test_models_catalog_export_contract.py` — the SDD-106 export + R10212 contract
  (extended here / paralleled by the view-persistence lint).
- SDD-106 (models-catalog export), R10137 (personalization localStorage pattern), R10212, SB-077.
