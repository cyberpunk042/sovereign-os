# SDD-106 — models-catalog export (complete the sort/filter/export triad)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-10
> Closes findings: the models-catalog browser's missing export (sort + filter present, export absent)
> Derived from: operator goal "beautiful god-tier functional dashboards"; chosen after a survey of the non-sensitive native data panels found this the best client-side ergonomics pick (the make-a-stub-functional / wire-a-producer threads stay hardware-gated-exhausted). Recover-projects band (SDD-106 / E11.M106).

## Mission

Complete the models-catalog browser's **sort / filter / export** triad. The panel already has
client-side column **sort** and 6-facet **filter**, but the operator who narrows the 68-model
catalog to "class=rlm, max VRAM 48, sort by context window" has **no way to take the shortlist
anywhere** — there is no export. Add a **CSV + JSON export of the derived (filtered + sorted)
rows**. It's a pure client-side recompute of the already-fetched catalog (R10212 — no new fetch)
and it serializes exactly the on-screen set (SB-077 — never a raw dump of unloaded data).

## Problem

`webapp/models-catalog/index.html` (the full 68-model browser, distinct from the D-23 live panel)
loads the catalog once (`fetch('/models-catalog.json')`, no SSE/interval) into `MODELS[]`, then:
`filtered()` applies the 6 facets, and `render()` does `const rows = filtered().sort(<cmp>)` and
paints a 9-column table (id, tier, class, quantization, size_class, purpose, vram_gib_min,
context_window_tokens, status). Sort headers + facet inputs are wired in `buildFilters()`. But
there is **no export button** and no serializer — the filtered/sorted view is a dead-end.

## Grounded design — export the derived set, reuse the in-repo CSV idiom

- **`sortedFiltered()` single source** — extract `filtered().sort(<the existing comparator>)` into a
  helper; `render()` becomes `const rows = sortedFiltered()` (no behavior change — same rows, same
  order). Both the table and the export read this one function, so the export is byte-for-byte
  "what's on screen".
- **Export toolbar** above the table: a muted "export the filtered + sorted set:" label +
  `#export-csv` + `#export-json` buttons.
- **`exportCsv()`** — the 9 rendered columns; the `cell()` escaper reused from
  `d-11-adapter-status/index.html:1032` (`/[",\n]/ → '"'+replace(/"/g,'""')+'"'`); `purpose` joined
  with `; `; `new Blob([csv],{type:'text/csv'})` → `<a download="models-catalog-<YYYY-MM-DD>.csv">` →
  click → `revokeObjectURL` (the exact d-11 Blob idiom).
- **`exportJson()`** — `JSON.stringify(sortedFiltered(), null, 2)` (the real model objects of the
  derived set) → `Blob({type:'application/json'})` → `.json` download.
- Wire both in `buildFilters()` (where the sort/facet listeners live); + a `SO_ASSIST` hover entry
  per button.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-106-A | Export scope. | **answered (operator, 2026-07-10): the filtered + sorted set** (what's on screen), not the raw 68 — SB-077-automatic + matches the filter→export-the-shortlist intent. |
| Q-106-B | Formats. | **answered: CSV (spreadsheets) + JSON (portable/programmatic)** — both pure client-side Blob downloads. |
| Q-106-C | A clipboard-copy variant (like personalization export). | **proposed: Stage-N** — a file download fits a 68-row table; clipboard is a later nicety. |

## Non-goals (Stage N)

- No new fetch / `/api/` call / server state (a recompute of the already-loaded `MODELS[]`).
- No change to `filtered()` / the sort comparator / the rendered table output.
- No export on the sensitive selfdef-mirror/audit panels (D-16 + D-12..D-18 keep their signed/CLI-only
  export doctrine — a client-side export there would muddy audit integrity).
- No FileReader/import (models-catalog is a read-only browser of the served catalog).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 106 + mandate E11.M106.
- **Stage 1:** `sortedFiltered()` + the export toolbar + `exportCsv()`/`exportJson()` + a new
  `tests/lint/test_models_catalog_export_contract.py`.
- **Stage 2:** full gate + static round-trip trace + ship.

## Safety invariants

Pure **client-side read-compute** — no new fetch, no `/api/` call, no server state; a recompute of the
already-loaded `MODELS[]` (R10212). **SB-077** — exports only the real, on-screen filtered+sorted rows
via the single-source `sortedFiltered()`; never fabricates or dumps unloaded data. No change to the
served catalog, the fetch, or the filter/sort logic. MS003 `unsigned-pending-MS003`.

## Cross-references

- `webapp/models-catalog/index.html` — `filtered()` + the sort comparator + `render()` this extends.
- `webapp/d-11-adapter-status/index.html:1032-1046` — the CSV `cell()` escaper + Blob/`createObjectURL`/
  `<a download>` idiom reused here.
- `tests/lint/test_models_catalog_export_contract.py` (NEW) — the export contract.
- R212/R214/R231/SDD-043 (the models catalog), R10212 (read-only web), SB-077.
