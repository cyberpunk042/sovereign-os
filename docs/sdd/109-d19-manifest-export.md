# SDD-109 — D-19 super-model-manifest export (CSV+JSON of the filtered manifest)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-10
> Closes findings: D-19 renders the M001..M080 module manifest but can't export it
> Derived from: operator goal "god-tier dashboards"; a survey found this the single highest-value non-polish client-side increment left. Recover-projects band (SDD-109 / E11.M109).

## Mission

Let the operator **take the super-model manifest with them**. D-19 renders the M001..M080
module-version manifest (what capabilities shipped, per family + status) but has no export — so this
genuine hand-off / audit artifact can only be read on screen. Add a **CSV + JSON export of the
chip-filtered rows**, exactly the models-catalog pattern (SDD-106): a pure client-side recompute of
the already-fetched `milestones` (R10212 — no new fetch) that serializes only what's displayed
(SB-077).

## Problem

`webapp/d-19-super-model-manifest/index.html`: `load()` fetches `/api/d-19/snapshot` (once +
`setInterval(load, 60000)`) and builds `milestones = snap.milestones + snap.cross_refs.map(…)` (rows
`{ms, title, family, status, rrows, tag}`); `renderMs()` reads the on/off status + family chips
(`#ms-filters .filter.on[data-status]` + `[data-family]`), filters `milestones`, and paints
`#ms-tbody`. There is **no export button** and no serializer — the filtered manifest is a dead-end.
(A survey also confirmed a shared `_shared/table-tools.js` helper is **premature** — the rule of
three is unmet and the inline-lockstep machine only fits byte-identical blocks, so this stays a
clean per-panel inline copy of the SDD-106 idiom.)

## Grounded design — export the filtered set, reuse the in-repo CSV idiom

- **`filteredMs()` single source** — extract the `renderMs()` chip-filter body:
  `(milestones||[]).filter(m => okStatus.has(m.status) && okFamily.has(m.family))`. `renderMs()`
  becomes `for (const m of filteredMs())` (same rows, no behavior change). Both the table and the
  export read this one function → the export is byte-for-byte "what's on screen".
- **Export toolbar** by the filters / above the table: a muted "export the filtered set:" label +
  `#export-csv` + `#export-json`.
- **`exportCsv()`** — `cols = [ms, title, family, status, rrows, tag]` + the `cell()` escaper reused
  from `d-11-adapter-status` / `models-catalog`; `Blob` text/csv → `<a
  download="super-model-manifest-<YYYY-MM-DD>.csv">` → click → `revokeObjectURL`.
- **`exportJson()`** — `JSON.stringify(filteredMs(), null, 2)` → Blob application/json download.
- Wire both in the existing chip-wiring block; + a `SO_ASSIST` hover entry per button.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-109-A | Export scope. | **answered (operator, 2026-07-10): the chip-filtered set** (what's on screen) — SB-077-automatic; matches "narrow to shipped+runtime, export that". |
| Q-109-B | Formats. | **answered: CSV + JSON** (both client-side Blob downloads), mirroring models-catalog. |
| Q-109-C | Chip view-persistence (remember which chips are on). | **proposed: Stage-N** — chips are toggle buttons (a different persistence mechanism than models-catalog's select values); export is the high-value piece, persistence a later follow-up. |

## Non-goals (Stage N)

- New fetch / `/api/` call / server state (a recompute of the already-loaded `milestones`).
- Any change to `renderMs()` output / the chip filter semantics / the `/api/d-19/snapshot` fetch.
- Chip view-persistence (Q-109-C).
- A shared `_shared/table-tools.js` (premature — per-panel inline for now).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 109 + mandate E11.M109.
- **Stage 1:** `filteredMs()` + the export toolbar + `exportCsv()`/`exportJson()` + a new contract lint.
- **Stage 2:** full gate + Node round-trip e2e + ship.

## Safety invariants

Pure **client-side read-compute** — no new fetch, no `/api/` call, no server state; a recompute of the
already-loaded `milestones` (R10212). **SB-077** — exports only the real, on-screen chip-filtered rows
via the single-source `filteredMs()`; never fabricates or dumps unloaded data. No change to the
snapshot fetch, the chip semantics, or `renderMs()` output. MS003 `unsigned-pending-MS003`.

## Cross-references

- `webapp/d-19-super-model-manifest/index.html` — `milestones` + the chip-filter logic this extends.
- `webapp/models-catalog/index.html` (SDD-106) / `webapp/d-11-adapter-status/index.html:1032` — the
  CSV `cell()` escaper + Blob/`createObjectURL`/`<a download>` idiom reused here.
- `tests/lint/test_models_catalog_export_contract.py` — the template for the new d-19 export lint.
- SDD-106 (models-catalog export), R10212 (read-only web), SB-077.
