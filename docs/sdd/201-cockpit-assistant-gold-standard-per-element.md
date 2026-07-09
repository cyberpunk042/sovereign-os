# SDD-201 — Cockpit Assistant gold-standard per-element coverage

> Status: **review** — gold data authored for every meaningful element on all 51 adopted panels (see §4).
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: E11.M201 (mandate decomposition — cockpit assistant per-element gold standard)
> Derived from: operator directive 2026-07-09 (verbatim below); builds ON SDD-200 (the
> `window.SO_ASSIST` gold-data model + app-shell reader) and SDD-067 (the app-shell itself).
> Second SDD in the **header-sidemenu session's 200–299 band** per SDD-100.

## 0. Operator directive (verbatim)

> "there is no way you are finished with the gold standard lol... it take days to do a proper
> Asssistant with proper data for evething in a page / panel...."

> "continue till everything is gold standard, no need for small PR. we do not minimize, we take
> our time and we do this right."

## 1. Mission

SDD-200 established the gold-data *mechanism* and seeded it thinly — ~2-3 `SO_ASSIST` cards per
panel, covering ~11% of each panel's meaningful elements. The operator correctly named that as
minimization: a "proper Assistant" explains **every** meaningful element on a page, not a
handful. SDD-201 is the discipline of carrying the gold data to that bar: **a grounded
`{sel, title, msg, more}` card for every meaningful element on every adopted panel** — each
stat, control, table, filter, banner, rule, and action.

The bar (operator-confirmed):

- **Depth** — every card is title + one-line `msg` + a 2-3 sentence `more` that explains what the
  element is, how to read it, and what it implies. (Reference exemplar: `d-09-hardware-pressure`,
  39 cards.)
- **Merge only pure echoes** — a gauge's fill bar folds into its value card; the same metric at
  1d/7d/30d windows folds into one card; a container `-panel` folds into its `-body`. Merging an
  echo is *de-duplication*, not minimization. Distinct concepts each get their own card.

## 2. Problem — where SDD-200 left the Assistant

SDD-200 shipped `window.SO_ASSIST` on all 51 panels, but at ~130 total cards against ~1,095
id-bearing elements. Hovering most elements surfaced nothing. The drawer *looked* covered but
wasn't — the exact "looks covered, isn't" failure the anti-minimization audit (D-anti-minimization)
exists to catch, applied to the Assistant itself.

## 3. Grounded design

No mechanism change from SDD-200 — the app-shell block, the `SO_ASSIST` reader, the `more▾`
card, and the tour are unchanged and stay **byte-identical** across panels. SDD-201 is purely
content: it replaces each panel's thin `SO_ASSIST` array with a full per-element one.

### 3.1 Accuracy (SB-077)

Every card is authored from the panel's **real** elements, not invented. The authoring pipeline
(`scripts/.../gold/sheet.py`) extracts, per panel, every `id`-bearing element together with its
visible label, section header, and the modules/rules cited inline. Cards are then written against
that grounding plus `config/dashboard-catalog.yaml` and the cited SDDs/modules — never a guessed
metric or control.

### 3.2 Verification gate (per panel, per batch)

Each panel is validated before commit:

- **every selector resolves** to a real `id=` element in that panel (0 unresolved across all 51),
- **no duplicate** selectors,
- **no thin fields** (`more` ≥ 80 chars, `msg` ≥ 20 chars),
- **valid JS** (`node`-parsed; `SO_ASSIST` is an array of complete objects),
- **app-shell contract green** (`tests/lint/test_app_shell_contract.py`) — the block stays
  byte-identical and non-mutating.

### 3.3 Non-mutating invariant (R10212) preserved

`SO_ASSIST` remains inline per-panel data (strings) — no fetch/XHR/POST is introduced. Every
card that describes an action reiterates that the web copies the signed `sovereign-osctl` /
`selfdefctl` verb; the cockpit never mutates privileged state.

## 4. Coverage (this SDD carried it to completion)

Gold data now covers **all 51 adopted panels** — **918 cards** authored against real elements
(83% of raw id-bearing elements; the remaining ~17% are the intentionally-merged echoes per §1:
gauge fills, same-metric-different-window cells, container/body pairs, pure section-header
fold-toggles). Representative depth:

- `build-configurator` 3 → **80** (the 12-section build wizard)
- `master-dashboard` 2 → **45** (the aggregator front door)
- `d-09-hardware-pressure` 3 → **39** (the exemplar)
- the five selfdef mirrors (D-13/14/15/17/18) → **95** combined
- every other panel expanded from its thin ~2-3 to full per-element depth

Delivered as one comprehensive change (operator directive: "no need for small PR"), committed
panel-by-panel on the branch and opened as a single PR.

## 5. Open questions

| Q | Question | Proposed |
|---|---|---|
| Q-201-A | Should the merged echoes (gauge fills, 7d/30d cells) ever get their own cards? | No — carding them restates their neighbour (a UX-audit `action-budget` failure). Merge is the confirmed bar. |
| Q-201-B | The optional live-LLM "discuss this element" layer (inherits SDD-200 Q-200-C). | **Flagged future decision** — unchanged from SDD-200; the hardcoded gold data stands alone. |

## 6. Non-goals

- **No mechanism change** — the app-shell block, reader, card, and tour are SDD-067/SDD-200; this
  is content only.
- **No LLM / chat backend** (Q-201-B is the future hook).
- **No change to any panel's data behavior** — gold data is read-only inline annotation.

## 7. Cross-references

- SDD-200 — the gold-data model + app-shell reader this completes.
- SDD-067 — the app-shell (header + sidemenu + Assistant drawer) itself.
- SDD-100 — the parallel-session number-band + `merge=union` scheme this SDD's registry rows follow.
- SB-077 — accuracy discipline (author from real behavior, never invent).
- R10212 / §1g — non-mutating web surface (copy the signed verb).
