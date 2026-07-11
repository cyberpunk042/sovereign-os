# SDD-141 — Phase 4: data-source banner wording convergence

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the SDD-140 follow-up. Panels show a data-source status line naming the endpoint they consume + how to recover when the daemon is down. Two phrasings coexisted: ~13 panels write the canonical Pattern-A form to `#ds-state-detail` (`consuming <code>/api/X</code> from the <name> API daemon` / `cannot reach <code>/api/X</code> — is the <name> API daemon running?`), while **5 panels** (code-console, d-21, d-23, d-24, d-25) wrote a terser form to `#data-source-banner` (`consuming <code>/api/X</code>` / `cannot reach the <name> API daemon (err)`) — the terse error dropped the endpoint AND the recover-prompt. Recover band (SDD-141 / E11.M141 per SDD-100).
> Derived from / extends: SDD-140 (honest-offline card wording — same visual-consistency stream). §1g.

## Mission

Converge the 5 terse `#data-source-banner` panels to the canonical Pattern-A phrasing so every panel names its endpoint and prompts the operator to check the daemon when it's unreachable, and pin it with a lint.

## Grounded design (visible-copy only, 5 panels + 1 lint)

Canonical shape: **`consuming <code>/api/X</code> from the <name> API daemon`** / **`cannot reach <code>/api/X</code> — is the <name> API daemon running? <span class="muted">(err)</span>`**.

- `d-23-models-catalog` → `/api/models-catalog/catalog`, name `models-catalog` (clean single-endpoint).
- `d-25-selfdef-management` → `/api/selfdef-management/state`, name `selfdef-management`; the `· selfdef is the producer, this panel only reads` disclaimer is preserved as a tail.
- `code-console` → `/api/code-console/sessions`, name `code-console`; the `(M057 task-sessions)` descriptor + the error's `— the three-pane console stays fully visible (honest empty/deferred)` honest-visibility tail are preserved.
- `d-21-lm-orchestration` → aggregator `/api/lm-orchestration/*` (the panel `Promise.all`s grid/profiles/features; the `/*` glob names the family without a literal `}`, which a brittle catch-block contract regex in a sibling lint can't span), name `lm-orchestration`.
- `d-24-cpu-features` → aggregator `/api/cpu-features/*` (probe/workloads/advisory), name `cpu-features`.

Each panel's banner element + set-logic is per-panel HTML/JS **below** the `APP-SHELL:END M067` marker — no shell-sync coupling. Panel-specific honest tails are preserved; only the phrasing skeleton is unified.

## R10212 / SB-077 preserved

Visible-copy only. No behaviour/data/runtime change; nothing fabricated. R10212 untouched.

## Verification

- NEW `tests/lint/test_data_source_banner_wording.py`: (1) no panel keeps the terse `cannot reach the <name> API daemon` form; (2) the 5 converted panels' `#data-source-banner` error branch is the canonical `cannot reach <code>…</code> — is the <name> API daemon running?` and positive branch is `consuming <code>…</code> from the <name> API daemon`.
- Playwright (file://, daemon unreachable → error banner renders): all 5 show the canonical `cannot reach /api/X — is the <name> API daemon running?` form, **no terse form, 0 page errors**.
- Full `make test` green (the per-panel d-21/d-23/d-24/d-25/code-console contract lints assert section-render behaviour, not banner text — unaffected; SDD-140's card lint targets a different element).

## On completion

The cockpit's data-source status lines now read consistently everywhere. Remaining Phase 4 (operator-selectable): align master-dashboard's section-scaffold cards (updating `test_master_dashboard_resilience.py` literals in lockstep); an SDD-040 evolution round to reconcile the `--good/--bad` vs `--ok/--danger` token vocabularies before any spacing/type-scale work; or the substantive ux-audit option B (raise 6 modules to 6/6 + bashrc dry-run gate).

## Cross-references

- SDD-140 (honest-offline card wording); the Pattern-A reference (`webapp/d-01-active-sessions/index.html` `renderDataSourceBanner`); `webapp/{code-console,d-21-lm-orchestration,d-23-models-catalog,d-24-cpu-features,d-25-selfdef-management}/index.html`. SDD-100 — band scheme.
