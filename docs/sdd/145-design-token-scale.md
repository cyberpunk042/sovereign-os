# SDD-145 — Phase 4: grounded design-token scale (`--fs-*` / `--space-*` / `--radius-*`)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the deepest "beautiful dashboard" foundation, unblocked by SDD-144 (single status-color vocabulary). The cockpit had **no** design-token scale — 751 `font-size` literals (29 distinct), 363 `border-radius` (16 distinct), thousands of spacing literals, hand-typed per panel — so consistency was aspirational and any polish edit meant touching 53 files. Recover band (SDD-145 / E11.M145 per SDD-100).
> Derived from / extends: SDD-137 (define fleet-wide + prove on the reference + soft-guard pattern); SDD-144 (unblocked the scale). §1g.

## Mission

Introduce ONE grounded, rem-based design-token scale so panels read as a consistent system and future polish edits a token, not 53 files — landed fleet-wide, proven on the reference panel, guarded, adopted gradually.

## Grounded design (zero-visual-change)

The scale values are chosen to land **on the fleet's dominant literals** (from a distribution recon: `--fs-sm:.78rem` ×144, `--radius-sm:3px` ×157, `--space-sm:.4rem` ×179, etc.), so adopting a token is a pure `var()` indirection, not a re-style.

- **`webapp/_shared/app-shell-snippet.html` `:root`** — the scale added additively (inside the byte-synced block), then `sync-app-shell.py --apply` propagates it to all panels. `--fs-*`/`--space-*` are **rem** so they auto-compose with the personalization `--font-scale` zoom (the html root is `calc(14px*--font-scale)`) — deliberately **not** `calc(*--font-scale)`-wrapped (that would double-apply the zoom and break the R10141 contract).
  - type: `--fs-2xs:.7 --fs-xs:.72 --fs-sm:.78 --fs-base:.85 --fs-md:1 --fs-lg:1.4` (rem)
  - radius: `--radius-xs:2 --radius-sm:3 --radius-md:4 --radius-lg:6` (px) · `--radius-pill:999px`
  - space: `--space-2xs:.2 --space-xs:.3 --space-sm:.4 --space-md:.6 --space-lg:.9 --space-xl:1 --space-2xl:1.2 --space-3xl:1.6` (rem)
- **`webapp/build-configurator/index.html`** (the grammar-doc reference impl) — its authored `<style>` block's **exact-match** screen literals converted to `var(--*)` (`.78rem`→`var(--fs-sm)`, `4px`→`var(--radius-md)`, `.4rem`→`var(--space-sm)`, …): 12 `--fs-*` + 11 `--radius-*` + 4 `--space-*` refs. Off-scale one-offs, multi-value paddings, `50%` circles, and the entire `@media print` `pt` sheet stay **literal**.
- **`webapp/_shared/design-grammar.md`** — the scale documented under `## Tokens`.

Fleet adoption is gradual (follow-up SDDs) — no fleet-wide literal ban, so unconverted panels stay green until they adopt.

## R10212 / SB-077 preserved

CSS-token indirection only. No behaviour/data/runtime change; the personalization `--font-scale` base rule untouched. R10212 untouched.

## Verification

- `sync-app-shell.py --check` clean; `test_app_shell_contract.py` (byte-identical re-sync) + `test_app_shell_palette_coverage.py` + `test_personalization_contract.py` (the `calc(14px*--font-scale)` base rule intact — `--fs-*` are rem) + `test_dashboard_palette_consistency.py` all green (29 passed).
- NEW `tests/lint/test_design_scale_contract.py`: (a) the app-shell `:root` declares every `--fs-*/--space-*/--radius-*` token; (b) build-configurator references each family (`var(--fs-`/`var(--radius-`/`var(--space-`) ≥ 3 — proving adoption.
- Playwright (build-configurator + d-20 + course): the scale resolves fleet-wide (`--fs-sm`=`.78rem`, `--radius-md`=`4px`, `--space-sm`=`.4rem`), **0 page errors**; build-configurator is pixel-identical (exact-match conversion).
- Full `make test` green.

## On completion

The cockpit has a real, grounded design-token scale declared fleet-wide + adopted on the reference. **Fleet adoption** (panel-family by panel-family, each Playwright-pixel-checked) is the follow-up stream. Also still open: the bashrc dry-run gate; `runtime-modes`' rogue `--warn:#7a701f`.

## Cross-references

- SDD-144 (status-color reconciliation); SDD-137 (define+prove+guard pattern); `webapp/_shared/design-grammar.md`; `scripts/webapp/sync-app-shell.py`; `test_personalization_contract.py` (--font-scale). SDD-100 — band scheme.
