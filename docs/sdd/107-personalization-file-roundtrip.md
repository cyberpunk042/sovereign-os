# SDD-107 — personalization file round-trip (Blob download + FileReader upload)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-10
> Closes findings: SDD-105 Q-105-C (file-based export/import)
> Derived from: operator goal "god-tier dashboards"; the explicitly-deferred SDD-105 Stage-N — the personalization panel had a clipboard/paste round-trip but no file portability. Recover-projects band (SDD-107 / E11.M107).

## Mission

Give the personalization panel a **file round-trip**. Today it exports prefs to the **clipboard**
and imports from a **pasted textarea** (SDD-105) — but you can't hand someone a
`personalization.json` or load one you saved to disk. Add a **Blob-download export** + a
**FileReader-upload import** that reuse the SDD-105 validator wholesale. Pure client-side; the file
import runs the identical validate-then-apply/honest-reject path as paste, so both are equally safe.

## Problem

`webapp/personalization/index.html` has `#export-btn` (clipboard copy of `JSON.stringify(prefs)`) and
`#import-btn`/`#import-apply` (paste a profile into `#import-json`, validate, apply — SDD-105). There
is **no file export** (no `Blob`/`download`) and **no file import** (no `FileReader`; grep confirms
`FileReader` exists nowhere in `webapp/`). So an operator's exported profile can only travel via the
clipboard — not as a saved/shared file.

## Grounded design — extract the validator, add a file round-trip

- **`applyImportedText(text)`** — extract the `#import-apply` validate-then-apply body (SDD-105): parse
  in try/catch → object / `schema===SCHEMA_V` / `theme∈VALID_THEMES` / `accent /^#[0-9a-fA-F]{6}$/` /
  `font_scale∈VALID_SCALES` checks, each honest-rejecting with a `toast`; on success
  `prefs={...DEFAULTS,...p, font_scale:Number(..)}` + `savePrefs`/`applyPrefs`/`renderAll`/`toast` +
  close `#import-box`. **One validator, both import paths** (paste + file). `#import-apply` becomes a
  one-liner calling it — no behavior change to the paste path.
- **File export** — `#export-file` beside `#export-btn`: `download('personalization-<YYYY-MM-DD>.json',
  JSON.stringify(prefs,null,2), 'application/json')` using the SDD-106 `download(name,text,mime)` (Blob +
  `createObjectURL` + `<a download>` + `revokeObjectURL`) + `stamp()` idiom, copied in. The clipboard
  export stays.
- **File import** — `#import-file-btn` + a hidden `<input type="file" id="import-file"
  accept="application/json,.json">`; the button triggers `import-file.click()`; on `change`, a
  `FileReader` reads the file as text → `applyImportedText(reader.result)` (same validator).
- Update the actions note + `SO_ASSIST` entries so the file round-trip is discoverable.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-107-A | Keep clipboard + paste too? | **answered (operator, 2026-07-10): yes — additive.** File download/upload sit beside the existing clipboard/paste; the validator is shared, so both import paths are identically safe. |
| Q-107-B | Validation for file import. | **answered: identical to paste** — the SAME `applyImportedText`; a bad file toasts a reason and changes nothing (SB-077). |
| Q-107-C | Multi-profile / named slots. | **proposed: Stage-N** — one active profile in localStorage as today; named slots are a later feature. |

## Non-goals (Stage N)

- Server state / any `/api/` POST (client-side-only doctrine + lint).
- localStorage KEY / SCHEMA_V change (cross-panel apply-snippet coherence untouched).
- Behavior change to the paste-import (only extracted into a shared function).
- File round-trip on other panels (this is the personalization control surface).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 107 + mandate E11.M107.
- **Stage 1:** extract `applyImportedText`; add `download`/`stamp`, `#export-file`, `#import-file-btn` +
  hidden `#import-file` + FileReader handler; contract-test assertions.
- **Stage 2:** full gate + static/Node e2e + ship.

## Safety invariants

Pure **client-side** — no fetch, no server state, no `/api/` mutation (personalization read-only
doctrine + the `test_personalization_page_is_client_side_only` lint; `Blob`/`FileReader` are browser
built-ins with no network). **SB-077** — file import runs the SAME validator as paste; invalid input
honest-rejected with a toast, never partially-applied, never fabricated. No localStorage KEY/SCHEMA_V
change. MS003 `unsigned-pending-MS003`.

## Cross-references

- `webapp/personalization/index.html` — `#export-btn`/`#import-apply` (SDD-105) this extends;
  `savePrefs`/`applyPrefs`/`renderAll`/`toast`, `DEFAULTS`/`SCHEMA_V`/`VALID_THEMES`/`VALID_SCALES`.
- `webapp/models-catalog/index.html` — the `download`/`stamp` Blob idiom (SDD-106) reused here.
- `tests/lint/test_personalization_contract.py` — the client-side-only + import contract (extended).
- SDD-105 (the clipboard/paste round-trip), M060 R10137/R10140/R10141, R10212, SB-077.
