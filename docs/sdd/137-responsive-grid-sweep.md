# SDD-137 — Phase 4: responsive grid sweep (generalize the code-console minmax(0,1fr) + assist-open reflow)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: Phase-4 (beauty/UX) opener — the responsive audit. The assistant pane opens on the right and shrinks `#so-content` by ~360px via `margin-right` (app-shell, global) WITHOUT changing the viewport, so a panel whose grid keys its collapse to a viewport `@media` query never reflows when the assistant opens; a bare `1fr` flexible track (min-width auto) then can't shrink below its widest content and forces horizontal overflow. Recon proved this is a SMALL sweep: the app-shell reflow already covers 50/52 panels, only **2** carry the genuine code-console crush pattern (rigid fixed-sidebar grid + viewport-keyed collapse), and ~5 have moderate equal-split grids worth hardening. Recover band (SDD-137 / E11.M137 per SDD-100).
> Derived from / extends: SDD-112 (code-console `.cc-grid` responsive fix — the reference pattern). §1g.

## Mission

Generalize the code-console responsive fix (`minmax(0,1fr)` flexible track + `body.so-assist-open` reflow) to the panels that need it, and pin the standard with a contract lint so it can't regress.

## Grounded design (per-panel author CSS — the fix is not in the synced block)

**Two rigid-sidebar crush panels** (flexible main + fixed sidebar + viewport-keyed collapse → overflow on assist-open):
- **`build-configurator`** `.wrap`: `1fr 470px` → `minmax(0,1fr) 470px`; `.left { min-width:0 }`; `.kv`: `150px 1fr` → `150px minmax(0,1fr)`; NEW `body.so-assist-open .wrap { grid-template-columns:1fr }` + `body.so-assist-open .right { position:static; border-left:0; border-top:… }`.
- **`d-22-lm-status-operability`** `.devgrid`: `1fr minmax(230px,290px)` → `minmax(0,1fr) minmax(230px,290px)`; `.hs-cols`: `1fr 1fr` → `minmax(0,1fr) minmax(0,1fr)` + `min-width:0`; `.hs-col { min-width:0; overflow-x:auto }`; NEW `body.so-assist-open .devgrid { grid-template-columns:1fr }`.

**Three moderate equal-split grids** (table-bearing `1fr 1fr` → `minmax(0,1fr) minmax(0,1fr)` so a wide cell shrinks): `d-21-lm-orchestration` (`.grid`, `.features`), `d-24-cpu-features` (`.grid2`), `d-25-selfdef-management` (`.grid2`).

The global assist-open reflow (`body.so-assist-open #so-content{ margin-right:var(--so-assist-w) }`) already lives in the synced app-shell and covers every other panel — no per-panel change needed there.

## Scope note (honest)

`minmax(0,1fr)` bounds the *track* so wrappable/shrinkable wide content (long descriptions, tables that reflow) stays contained. Genuinely **unbreakable** tokens (long hashes) are a separate concern handled by `word-break` on the specific element — 4 panels use `word-break:break-all` on hash strings (`d-05-traces`, `d-16-audit`) or on `<pre>` that pairs it contradictorily with `overflow-x:auto` (`global-history`, `network-edge`). That word-break cleanup is a **noted follow-up**, not in this SDD.

## R10212 / SB-077 preserved

CSS-only presentation. No behaviour/data/runtime change; no fabricated data. R10212 untouched.

## Verification

- NEW `tests/lint/test_responsive_grid_contract.py`: (1) no panel-authored `grid-template-columns` pairs a bare `1fr` with a fixed `Npx` track (the crush pattern) — scans the pre-`APP-SHELL:BEGIN` region; (2) the 2 rigid-sidebar panels carry the `minmax(0,1fr)` main track + a `body.so-assist-open` reflow; (3) the 3 moderate grids are minmax-hardened.
- Playwright (viewport 1280, `body.so-assist-open` added, a long **wrappable** wide block injected into the main grid cell): all 5 edited panels show **page overflow 0px · main-grid overflow 0px · 0 page errors**.
- Full `make test` green.

## On completion

The responsive-audit first cut is done. Remaining Phase 4 (each a focused SDD/PR): the `ux-design-audit` six-dimension checklist sweep; the `word-break:break-all` cleanup (4 panels); spacing/typography/empty-state polish.

## Cross-references

- `webapp/code-console/index.html` (`.cc-grid` reference fix, SDD-112); `webapp/_shared/app-shell-snippet.html` (global `so-assist-open` reflow); `tests/lint/test_code_console_webapp_contract.py` (the code-console-specific analog). SDD-100 — band scheme.
