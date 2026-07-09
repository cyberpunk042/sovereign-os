# App-shell (header + sidemenu + Assistant mode) — planning findings — 2026-07-09

Source: operator directive 2026-07-09 (verbatim in [SDD-067](../../docs/sdd/067-cockpit-app-shell-header-sidemenu-assistant.md) §0.1). Inspiration operator-named: `devops-control-plane` `src/ui/web/templates/partials/_nav.html`. Deliverable this pass: **plan/SDD, stop for review** (no code).

## Research findings (grounded)

| # | Finding | Evidence |
|---|---|---|
| 1 | The cockpit is **~52 self-contained panels** (25 `d-01`…`d-25` + named: master-dashboard/D-00, surface-map, auditor, weaver, trinity, router, orchestration, build-configurator, personalization, …). Each is a single `index.html`. | `webapp/` (53 dirs incl. `_shared`) |
| 2 | **Sovereignty-clean doctrine**: no CDN, no shared runtime asset; cross-panel invariants are kept identical-by-duplication + a lint contract test. | `webapp/_shared/nav-snippet.html` header comment |
| 3 | Every adopted panel already carries a **4-snippet canonical `<head>` stack**, each contract-tested: personalization apply → keyboard-nav (⌘K palette + ⌘1..0) → a11y (focus-visible + skip-link + reduced-motion) → responsive (≤600/≤1024/≥2400). | `tests/lint/test_{personalization,keyboard_nav,a11y,responsive}_contract.py` |
| 4 | A **design grammar** exists: token set, one-`.primary`-per-view button hierarchy, console cards, status pills. Reference impl `build-configurator`. | `webapp/_shared/design-grammar.md` |
| 5 | **Weaving already partly exists**: master-dashboard (D-00) is the front door (inlines SDD-045 control-surface, fetches `/catalog`); surface-map maps everything; personalization ships theme/accent/typography. | `webapp/master-dashboard/index.html`, `webapp/personalization/index.html` |
| 6 | A **backing operator server** serves live data + `/catalog`, `/control-systems`, `/api/control/registry`. | `scripts/operator/*-api.py` (incl. `master-dashboard-api.py`) |
| 7 | Inspiration `control-plane/_nav.html` is a **single-page app** (`switchTab`); sovereign-os is **multi-page**. The chrome must live identically on every static page → the canonical-snippet doctrine is the fit. | `devops-control-plane/src/ui/web/templates/partials/_nav.html` |

## Decisions (operator, via AskUserQuestion)

1. **Distribution** = template + generator/sync (5th canonical snippet, contract-tested).
2. **Assistant mode** = client-side contextual help (hover explanations + help drawer + tour; no backend).
3. **Layout** = persistent header + collapsible sidemenu across all ~52 panels.
4. **Deliverable this pass** = SDD + this note, stop for review.

## The plan in one line

Elevate the invisible ⌘K/⌘1..0 weave into an **always-present app-shell** — a top header (brand · breadcrumb · status · ⌘K · theme · ✦Assist) + a grouped collapsible sidemenu + an Assistant drawer — distributed as the **5th canonical per-panel snippet** via a new generator (`scripts/webapp/sync-app-shell.py`) and a new contract test (`tests/lint/test_app_shell_contract.py`), reusing the personalization theme keys, the palette catalog, and the design grammar; nothing server-mutating, nothing that breaks the existing four snippets.

## Staged rollout (spec in SDD-067 §4)

Stage 0 (this pass, done): SDD + note → **review gate**. Stage 1: shell + generator + contract test on 2 reference panels. Stage 2: Assistant drawer on the 2. Stage 3: sweep all ~52. Stage 4: catalog-driven grouping + polish.

## Open questions for next session

Q-067-A group taxonomy source (catalog-driven vs static) · Q-067-B sidemenu default state + persistence key · Q-067-C system-wide status/approvals roll-up source · Q-067-D assistant content authoring · Q-067-E which panels (incl. meta/audit?) · Q-067-F live-LLM assistant = flagged future decision (network / trust tension). See SDD-067 §5.

Operator standing direction honored: *additive, never discarding* — this builds ON the four existing snippets + the design grammar; it replaces none of them.
