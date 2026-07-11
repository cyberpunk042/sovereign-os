# SDD-135 — Phase 3: cross-panel deep links (sibling D-xx references become clickable)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the cockpit's assistant is dense with sibling cross-references ("pairs with D-03…", "the six domain mirrors D-13…D-18") but they were plain text — an operator reading them had to go find the panel in the sidebar. Phase-3 operability item (operator: *"a panel's referenced siblings become clickable"*). Also folds in a real bug the recon surfaced: 10 panels linked `../d-00-master/`, a slug that does not exist (the master dashboard's real slug is `master-dashboard`), so the front-door footer link silently 404'd. Recover band (SDD-135 / E11.M135 per SDD-100).
> Derived from / extends: SDD-114 (app-shell GROUPS catalog); the shared app-shell sync (`scripts/webapp/sync-app-shell.py`). §1g.

## Mission

When the assistant surfaces a panel's cross-references to sibling panels (`D-01`…`D-25`, incl. the split `D-12a`/`D-12b`), turn each into a clickable deep link to `../<slug>/`, so the operator navigates the cockpit by following the references instead of hunting the sidebar. Presentation/navigation only; the web still never mutates (R10212).

## Grounded design

- **One edit, synced to all 52 panels.** The link map + linkify pass live in the shared app-shell (`webapp/_shared/app-shell-snippet.html`), then `sync-app-shell.py --apply` fans the byte-identical block into every adopted panel (the app-shell already owns the `GROUPS` catalog + the assistant render chokepoint + the sync mechanism — no 6th inlined asset needed).
- **`ID2DIR`** — built from the in-memory `GROUPS` catalog (`{id → dir}`, skipping the `id:'—'` panels that have no D-number), exactly as the ⌘K palette already keys off `GROUPS`.
- **`linkifyDxx(root)`** — a post-render DOM **text-node** pass (TreeWalker over `SHOW_TEXT`). For each text node containing a `\bD-\d{2}[ab]?\b` token that resolves in `ID2DIR`, it swaps the token for `<a class="so-dxx-link" href="../<dir>/">D-NN</a>`. It **never re-wraps a token already inside an `<a>`** (walks parents to the render root) and **never self-links** the current panel (`dir === curDir()` is left as text). Range shorthands (`D-13…D-18`) linkify their endpoints; the ellipsis stays text.
- Wired at the three assistant render points that set `abody.innerHTML`: `idle()`, `showPath()` (the hover cascade — where the `so-xref` cards in the trusted `expanded` HTML live), and the menu-hover panel-context render (the `menuHover` trusted HTML). Escaped `content` (plain-text D-xx) is linkified too, since the pass runs on the rendered DOM.
- **`.so-dxx-link`** — a subtle dotted-underline accent style (solid on hover), added beside the existing `.so-xref` rule.
- **Bug fold-in:** the 10 panels linking `../d-00-master/` (d-07, d-08, d-12, d-13, d-14, d-15, d-17, d-18, d-19, d-20) are corrected to `../master-dashboard/`.

## R10212 / SB-077 preserved

The linkify pass creates `<a href>` anchors only — no `fetch`, no XHR, no `sendBeacon`, no POST (the app-shell non-mutation contract, `test_app_shell_chrome_is_non_mutating`, still holds). No data is fabricated; anchors point only at real `webapp/<slug>/` panels. R10212 (exec-rail is the only write path) untouched.

## Verification

- NEW `tests/lint/test_cross_panel_links_resolve.py`: (a) every literal `href="../<slug>/"` in `webapp/*/index.html` resolves to a real panel dir; (b) no panel links the stale `d-00-master` slug (regression guard); (c) `linkifyDxx` is present in the synced app-shell, keyed off `ID2DIR`/`GROUPS`, and non-mutating.
- `test_app_shell_contract.py` (byte-identical block across all 52 panels + non-mutating chrome) still green after re-sync.
- Playwright: on `master-dashboard`, hovering the `d-25` menu item renders its menuHover with `D-12`→`../d-12-networking/` and `D-18`→`../d-18-trust-scores/` as `a.so-dxx-link`; **0 self-links**, **all targets resolve**, **0 page errors**.
- Full `make test` green (495 unit + lint + L3).

## On completion

Sibling references across the cockpit are navigable. Remaining Phase-3 item (non-security): Cmd-K palette coverage polish (the palette already covers the full catalog; audit for any gaps).

## Cross-references

- `webapp/_shared/app-shell-snippet.html` (GROUPS catalog + assistant render + linkify); `scripts/webapp/sync-app-shell.py` (sync); `tests/lint/test_app_shell_contract.py`. SDD-100 — band scheme.
