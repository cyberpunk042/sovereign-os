# SDD-958 — unfreeze the mdbook: generated SDD catalog + standing-directives, enforced

> Status: draft
> Owner: operator-directed ("continue … do this right, do not minimize" — Phase-1 audit); agent-authored
> Last updated: 2026-07-12
> Number band: **950–999 (general / audit session)** per SDD-100.
> Closes findings: **F-2026-033**. From `docs/review/phase-1/99-findings-ledger.md`.
> Derived from / extends: the counts-as-contract discipline of SDD-952 / SDD-955 / SDD-956.

## Mission

The published mdbook (`docs/src/SUMMARY.md`) had **hand-curated** links to a handful of SDDs and stopped being updated at **SDD-067**. Consequences the audit found: the book trailed the repo by ~90 SDDs (the entire July intelligence layer — brain / CoAT / reasoning / jobs / plan-mode / tokenizer / console — plus this session's whole phase-1 audit arc), and had **no page** for the three July standing-directives. A reader of the published site saw a foundation-era snapshot, not the real project.

Hand-maintaining a 139-entry table of contents is exactly the living-doc drift (audit theme #2) the counts-as-contract pattern exists to kill. So this SDD **generates** the catalog from the file tree and **enforces** it, rather than adding 90 hand-written TOC rows that would re-freeze the moment the next SDD lands.

## What this SDD builds

### 1. `scripts/docs/gen-sdd-catalog.py` — the generator

Reads the file tree and renders two Markdown chapter pages deterministically:
- **`docs/src/sdd-catalog.md`** — every `docs/sdd/NNN-*.md`, by number, each linked with its verbatim H1 title (139 today).
- **`docs/src/standing-directives.md`** — every `docs/standing-directives/*.md` (the operator's verbatim mandate records, including the three July directives).

Run it after adding an SDD or directive: `python3 scripts/docs/gen-sdd-catalog.py` (or `--check` for CI). Stdlib only.

### 2. The two generated chapter pages + SUMMARY wiring

Both pages carry a "Generated — do not hand-edit" banner. `docs/src/SUMMARY.md` gains a **"Design record"** section linking them (additive — the pre-existing curated SDD links in the intro are left intact per adding≠discarding). mdbook renders them as ordinary chapters; a reader now reaches the full SDD record and the standing-directives from the book.

### 3. `tests/lint/test_mdbook_catalog_sync.py` — the enforced contract

Re-runs the generator and fails CI if either page is stale (regen-and-compare), plus: the catalog references the **newest** SDD (a direct anti-freeze guard), every relative link resolves (no dead chapters), and SUMMARY wires both pages. So the pages can only be **regenerated, never hand-edited**, and a new SDD/directive that isn't reflected in the book is caught — the mdbook can never freeze behind the design record again.

## Why generate, not hand-list

The finding says it explicitly: *"regenerate SUMMARY from `docs/sdd/INDEX.md` (script it — don't hand-maintain)."* A hand-curated list re-freezes on the next addition; a generated-and-linted list cannot. This is the same self-maintaining pattern as `context.md`'s counts (SDD-952), the island register (SDD-955), and the gateway route-parity contract (SDD-956) — the audit's structural answer to drift.

## Design choices

- **A catalog page, not 139 TOC entries.** Putting every SDD directly in `SUMMARY.md` would bloat the mdbook sidebar to unusability. One `sdd-catalog.md` chapter that lists them all keeps the sidebar sane while giving complete coverage.
- **Verbatim H1 as link text.** The catalog reads the same as the doc it points at (no separate hand-written summary to drift).
- **Additive to SUMMARY.** The intro's existing curated SDD links (037/039/043/044/045/067) stay; the new "Design record" section adds the complete catalog alongside them.

## Verification

- `python3 scripts/docs/gen-sdd-catalog.py` regenerates both pages; `--check` is clean.
- `python3 -m pytest tests/lint/test_mdbook_catalog_sync.py` — 6 passed: generator exists; both pages in sync; catalog references the newest SDD; all links resolve; SUMMARY wires both pages.
- `ruff check` clean on the generator + lint; full `tests/lint` + `tests/schema` green. (mdbook is not installed in this environment; the lint's link-resolution check stands in for `mdbook build`, which the existing `build mdbook` CI job runs.)

## Non-goals

- **Adding narrative pages for every intelligence-layer crate.** The finding's "add pages for the intelligence-layer crates/binaries" is a larger content-writing effort; this SDD makes the design record (SDDs + directives) reachable and un-freezable, which is the load-bearing fix. Per-crate chapters can follow.
- **The MASTER-PLAN count contradictions (F-2026-032)** — the sibling living-doc-drift finding, a separate chunk (it is cross-repo: sovereign-os + selfdef).

## Safety invariants

Docs + generator + lint only — no crate code, no runtime behavior, no gateway touch. The generator writes only its two catalog pages; the lint is read-only. Purely additive to SUMMARY. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/docs/gen-sdd-catalog.py` — the generator
- `docs/src/sdd-catalog.md` · `docs/src/standing-directives.md` — the generated chapters
- `docs/src/SUMMARY.md` — the "Design record" section
- `tests/lint/test_mdbook_catalog_sync.py` — the enforcing lint
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-033 (source); F-2026-032 (sibling MASTER-PLAN drift)
- SDD-952 / SDD-955 / SDD-956 — the same self-maintaining-contract pattern
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
