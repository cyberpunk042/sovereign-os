# SDD-105 — personalization import (complete the export→import round-trip)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: the personalization panel's dead-ended export (export-with-no-import)
> Derived from: operator goal "the beautiful dashboard … god tier"; chosen after a deferred-gap survey found the make-a-stub-functional / wire-a-producer threads hardware-gated-exhausted and the honest remaining vein is client-side ergonomics on already-live panels. Recover-projects band (SDD-105 / E11.M105).

## Mission

Complete the personalization panel's **export → import round-trip**. Today the operator can
**export** their theme / accent / typography prefs (a button copies the prefs JSON to the
clipboard), but there is **no import** — so the export dead-ends: prefs can be copied out of one
browser but cannot be loaded into another. Add a **validated paste-JSON import** that reuses the
existing apply helpers. Pure client-side, localStorage-only — the personalization read-only
doctrine (R10212) and honest-reject (SB-077) both hold by construction.

## Problem

`webapp/personalization/index.html` is the canonical personalization control surface (the other
30+ dashboards only embed the apply-snippet — they have no control UI). It already has:
`loadPrefs()` / `savePrefs(p)` / `applyPrefs(p)` / `renderAll()` / `toast(msg)`, `DEFAULTS`
`{schema,theme,accent,font_scale}`, `SCHEMA_V=1`, the `KEY='sovereign-os.personalization'`, and
an `#export-btn` that does `navigator.clipboard.writeText(JSON.stringify(prefs,null,2))`. But
there is **no import / restore / paste** path (no `JSON.parse` of operator input, no import
button). The export button has nowhere to land.

## Grounded design — a validated paste-JSON import (symmetric to the clipboard export)

- **`#import-btn`** beside `#export-btn` reveals an inline `<textarea id="import-json">` +
  `#import-apply` button (the reveal-inline idiom, matching this codebase's button+toast style —
  no modal, no new dependency).
- **`#import-apply` handler** — validate-then-apply, honest-reject (never apply garbage):
  1. `JSON.parse(textarea.value)` in try/catch → invalid → `toast('invalid JSON')`.
  2. `p.schema !== SCHEMA_V` → `toast('unknown schema — expected v1')`.
  3. Field-validate: `theme ∈ {auto,dark,light}`; `accent` matches `/^#[0-9a-fA-F]{6}$/`;
     `font_scale ∈ {0.85,1,1.15}` — any invalid field → a specific `toast`; `prefs` is NOT
     mutated on any reject.
  4. On success: `prefs = {...DEFAULTS, ...validated}` (mirrors `loadPrefs`); `savePrefs(prefs)`;
     `applyPrefs(prefs)`; `renderAll()`; `toast('imported')` — reusing the exact existing helpers,
     no new apply logic.
- Update the actions note so the round-trip is discoverable (export ⇄ import). **No change** to
  the localStorage KEY / SCHEMA_V / apply-snippet — the cross-panel coherence contract and every
  adopted-dashboard apply-snippet stay untouched.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-105-A | Import transport. | **answered (operator, 2026-07-09): a paste-JSON textarea** — symmetric to the existing clipboard-JSON export; no fetch, no file API. |
| Q-105-B | Invalid-input posture. | **answered: honest-reject with a specific toast; never partially-apply** (SB-077 spirit). Merge onto DEFAULTS so a *missing* field falls back, a *wrong* field is rejected. |
| Q-105-C | File-based export/import (Blob download + FileReader upload). | **proposed: Stage-N** — this increment matches the current clipboard export with a paste import; a file round-trip is a later polish. |

## Non-goals (Stage N)

- Server state / any `/api/` POST (personalization is client-side-only — its lint enforces it).
- localStorage KEY / SCHEMA_V change (would ripple across all 30+ adopted apply-snippets).
- Import UI on the non-control panels (they only *apply* prefs; the control surface owns import).
- File upload/download (Q-105-C).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 105 + mandate E11.M105.
- **Stage 1:** the `#import-btn` + inline textarea + validated `#import-apply` handler +
  `tests/lint/test_personalization_contract.py` import assertions.
- **Stage 2:** full gate + static round-trip e2e string-trace + ship.

## Safety invariants

Pure **client-side** — no fetch, no server state, no `/api/` mutation (the personalization
read-only doctrine + the `test_personalization_page_is_client_side_only` lint hold by
construction). **SB-077** — an invalid import is honest-rejected with a specific toast, never
partially-applied, never fabricated. No localStorage KEY / SCHEMA_V change (cross-panel coherence
untouched). No apply-snippet change on adopted dashboards. MS003 `unsigned-pending-MS003`.

## Cross-references

- `webapp/personalization/index.html` — `loadPrefs`/`savePrefs`/`applyPrefs`/`renderAll`/`toast`,
  `DEFAULTS`/`SCHEMA_V`/`PALETTE`, the `#export-btn` this completes.
- `tests/lint/test_personalization_contract.py` — the R10137/R10140/R10141 + client-side-only
  contract (extended here with the import round-trip).
- M060 R10137/R10140/R10141 (personalization catalog), R10212 (read-only web), SB-077.
