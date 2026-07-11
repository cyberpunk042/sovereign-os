# SDD-136 — Phase 3: ⌘K palette + sidebar coverage guard (lock GROUPS == disk)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the last Phase-3 item was "Cmd-K palette coverage polish." Two recon passes proved the ⌘K palette is **already at full 52/52 coverage** — the palette (`CMDK`) and the sidebar (`buildSidemenu`) are both built from the same `GROUPS` catalog, a bijection with the on-disk panels; every panel is reachable by slug (`cmdkFilter` matches id/label/dir/grp). So there is no coverage gap to fill — the productive increment is a **coverage guard**: no existing lint asserts `GROUPS.dir set == disk panels`, so a future panel could ship invisible to both palette and sidebar and stay green. Recover band (SDD-136 / E11.M136 per SDD-100).
> Derived from / extends: SDD-114 (GROUPS catalog); SDD-135 (cross-panel links — the GROUPS→disk direction). §1g.

## Mission

Lock the ⌘K-palette + sidebar coverage invariant so it can never silently regress: the app-shell `GROUPS` catalog must remain a bijection with the on-disk `webapp/*/` panels, and the byte-identical embed list must equal disk too.

## Grounded design (test + docs only — no webapp/panel changes)

NEW `tests/lint/test_app_shell_palette_coverage.py`, mirroring the `_panel_dirs()` pattern of `tests/lint/test_dashboard_catalog_complete.py`:

1. **Bijection** — parse the `{id:'…', dir:'…'}` entries from the `GROUPS` block (between the `APP-SHELL:BEGIN/END M067` markers) of `webapp/_shared/app-shell-snippet.html`; assert `{dir} == _panel_dirs()` both directions. A disk panel missing from GROUPS is unreachable from the palette AND the sidebar; a GROUPS dir with no panel is a dead nav row.
2. **Typeable reachability** — every GROUPS entry has a non-empty `dir`, so `cmdkFilter` (which matches the slug) can reach it — including the 27 `id:'—'` panels that have no D-number to type.
3. **Embed lockstep** — `ADOPTED_APP_SHELL_PANELS` (imported from `tests/lint/test_app_shell_contract.py`) must equal the disk panel set, so the byte-identical embed contract can never silently skip a newly-added panel.

## Why the existing guards don't cover this

- `test_app_shell_contract.py::test_app_shell_catalog_covers_full_panel_set` — checks only the `D-00..D-25` **id strings**, not the 27 slug panels, not the dir set.
- `ADOPTED_APP_SHELL_PANELS` — a hand-maintained list, not derived from disk.
- `test_dashboard_catalog_complete.py` — locks disk ⊆ `config/dashboard-catalog.yaml` (a *different* catalog).
- `test_cross_panel_links_resolve.py` (SDD-135) — locks GROUPS→disk (real), not disk→GROUPS (complete).

## R10212 / SB-077 preserved

Test-only. No webapp/runtime/data change. Nothing fabricated. R10212 untouched.

## Verification

- `python3 -m pytest tests/lint/test_app_shell_palette_coverage.py -q` — passes on the current tree, proving the invariant holds today (GROUPS == disk == ADOPTED, **52/52**).
- Full `make test` green.

## On completion

Phase 3 (operability) is complete: actions execute from the cockpit where genuinely wireable (SDD-132), the front door is resilient + demo-rich (SDD-133/134), sibling references are navigable (SDD-135), and palette+sidebar coverage is now enforced (this SDD). Next stream: Phase 4 (beauty/UX consistency sweep). Noted follow-up (separate, operator-gated): the inert old head-snippet palette (`nav-snippet.html`) still rides on ~35 panels, superseded at runtime by the app-shell's capture-phase ⌘K handler — a dead-code cleanup gated by `test_keyboard_nav_contract.py`.

## Cross-references

- `webapp/_shared/app-shell-snippet.html` (GROUPS catalog + `CMDK` + `buildSidemenu` + `cmdkFilter`); `tests/lint/test_app_shell_contract.py` (`ADOPTED_APP_SHELL_PANELS`, BEGIN/END markers); `tests/lint/test_dashboard_catalog_complete.py` (`_panel_dirs` pattern). SDD-100 — band scheme.
