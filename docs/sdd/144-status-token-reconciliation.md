# SDD-144 — Phase 4: status-color token reconciliation (canonise `--good/--bad`)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: Phase-4's real "beauty" foundation. The cockpit carried two rival status-color vocabularies: `--good/--bad/--warn` (the de-facto canonical — enforced by `test_dashboard_palette_consistency.py` + the d-21/23/24/25 contracts + the SDD-040 bridge, declared by ~49 panels, referenced 275× in rules) vs `--ok/--danger/--warn` (only in the **advisory** grammar doc `webapp/_shared/design-grammar.md` + the reference panel `build-configurator` + the parallel-added `course` panel + two shared-snippet fallbacks). The grammar doc even names build-configurator as "the reference — converge every other panel to this grammar", yet build-configurator used a *different palette* (and slightly different hex) than the 49 panels it's the reference for. This collision blocks a clean shared spacing/typography scale and misleads any agent that "converges to the grammar". Recover band (SDD-144 / E11.M144 per SDD-100).
> Derived from / extends: SDD-040 (palette contract). §1g.

## Mission

Collapse the two vocabularies into ONE — `--good/--bad/--warn` — aligned across the grammar doc + the enforcing lints + all panels + the reference impl, so a later `--space-*`/`--fs-*`/`--radius-*` scale has a clean palette to build on.

## Grounded design (Option C — canonise `--good/--bad`; 4 files + 2 re-syncs)

Evidence is lopsided (5 enforcing tests + ~49 panels + 275 refs + SDD-040 all use `--good/--bad`), so the tightest reconciliation is to make the *minority* match reality:

1. **`webapp/_shared/design-grammar.md`** — the token table reworded `--ok`→`--good`, `--danger`→`--bad`, hex corrected to canonical (`#7ad17a` / `#e6c062` / `#ff7676`); the console-card accent-bar note `--ok`→`--good`. (Advisory doc, no lint pins it.)
2. **`webapp/_shared/app-shell-snippet.html`** — the shared `.so-pill .dot` fallback `var(--ok,#7fd18a)` → `var(--good,#7ad17a)` (the universal status-dot mix-point in all panels).
3. **`webapp/_shared/course-snippet.html`** — the shared `.so-course-todo input` accent `var(--ok,#7fd18a)` → `var(--good,#7ad17a)` (the second synced fallback, added by the parallel guided-course #115).
4. **`webapp/build-configurator/index.html`** (the reference impl) + **`webapp/course/index.html`** — rename each `:root` `--ok/--danger` declaration → `--good/--bad` (drop the divergent `#7fd18a`/`#e6c07b`/`#e88`/`#e88888` for canonical hex) + all bare `var(--ok)`→`var(--good)`, `var(--danger)`→`var(--bad)` references.

Then `sync-app-shell.py --apply` + `sync-course.py --apply` re-propagate the two snippets byte-identically to every adopted panel. The ~49 `--good`-declaring panels needed **no** hand edit (their only `--ok` was the two shared fallbacks, fixed centrally). **0 lint changes, 0 per-panel-contract changes.**

## The one operator decision (ratified)

*Which vocabulary is canonical* → `--good/--bad` + its canonical hex (`--good:#7ad17a`, `--bad:#ff7676`, `--warn:#e6c062`). This converges build-configurator's chrome + the shared status-dot from the grammar's slightly-different `#7fd18a`/`#e6c07b`/`#e88` to the fleet hex — a real, sub-perceptual visual change on the status dot (all panels) + build-configurator/course chrome.

## R10212 / SB-077 preserved

CSS-token rename only. No behaviour/data/runtime change; nothing fabricated. R10212 untouched.

## Verification

- `grep -rn '--ok|--danger' webapp/` → **0** remaining (one vocabulary); both `sync-*.py --check` clean.
- The 5 `--good/--bad` contracts (`test_dashboard_palette_consistency.py` + d-21/23/24/25 `test_webapp_declares_canonical_palette_and_mono`) + the SDD-040 bridge + `test_app_shell_contract.py` + `test_course_snippet_contract.py` — all green (this increment converges *toward* them; 66 passed).
- NEW `tests/lint/test_status_token_vocabulary.py`: no panel/snippet declares or references `--ok`/`--danger`; build-configurator declares the canonical `--good/--bad/--warn`.
- Playwright: build-configurator + `d-20` + `course` render with `--good` resolving to `#7ad17a`, `--ok` undefined, **0 page errors**.
- Full `make test` green.

## On completion

The cockpit has ONE status-color vocabulary aligned across doc + lint + all panels + the reference impl. This unblocks the real scale SDD (`--space-*`/`--fs-*`/`--radius-*` in the synced app-shell `:root` — one edit reaches all panels — + a lint + gradual adoption). Also still open: the bashrc dry-run gate (ux-audit 4/6→5/6, behaviour change, operator-greenlit); `runtime-modes`' rogue `--warn:#7a701f` (non-`d`, no contract — a tiny separate cleanup).

## Cross-references

- SDD-040 (palette contract + bridge lint); `webapp/_shared/design-grammar.md`; the two sync scripts `scripts/webapp/{sync-app-shell,sync-course}.py` + their byte-identical contracts. SDD-100 — band scheme.
