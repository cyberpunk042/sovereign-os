# SDD-202 — Cockpit Assistant gold-standard rebuild (full-height, context-cascade, state-aware)

> Status: **complete** — every adopted panel rebuilt to the gold standard (see §4).
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-10
> Closes findings: E11.M202 (mandate decomposition — cockpit assistant gold-standard rebuild)
> Supersedes: **SDD-200** and **SDD-201** (the flat `{sel,title,msg,more}` gold-data model — its
> mechanism (SDD-200) and its per-element expansion to ~918 flat cards (SDD-201), both rejected by
> the operator as too thin; see §0). Builds ON SDD-067 (the app-shell header + sidemenu + Assistant)
> and reuses its 51-panel adoption surface. Third SDD in the header-sidemenu session's
> **200–299 band** (per SDD-100 parallel-session conflict avoidance).

## 0. Operator directive (verbatim)

> "the level of content is poor and the experience is crap… we restart from the beginning and
> this time we aim for a gold standard…. What you did makes no sense… hiding information behind a
> 'more' button that you need to absolutely click everytime since otherwise the content is too
> poor and even when you click it its still poor…. WHY DID YOU NOT LOOK AT the
> devops-control-plane to see how its done and what is high standard assistant feeling data ? the
> assistant panel is almost empty, it take 1/6 of the height and it breaks UX wise when you try
> to enable tour mode… RETURN look at devops-control-plane and fix all this crap…. RETURN TO IT..
> RETURN AND LEARN FROM IT. DO NOT STOP TILL YOU DID THE JOB… WHY ARE YOU STOPPING ? DONT STOP.
> LOOK AT devops-control-plane to do the sovereign-os panels properly…. we need a real assistant
> panel, high standards and assistant feeling. not a meek inconplete fart.."

## 1. Mission

Rebuild the Assistant from the ground up to the **gold standard set by
`devops-control-plane`**: a **full-height** side panel that renders a **hover/focus cascade** —
the panel context, the parent section, and the active element — with **rich content always
shown** (no click-to-reveal) and **state-aware variants**. No separate tour, no "more" button, no
1/6-height drawer. The content must have "assistant feeling": colleague-voice explanation of
*consequences and cross-references*, not a restatement of the label.

This SDD replaces SDD-200's flat model wholesale and carries the rebuild to completion across
**all 51 adopted panels** (operator: *"DO NOT STOP TILL YOU DID THE JOB"* / *"no need for small
PR"*).

## 2. Problem — why SDD-200/201 was rejected

SDD-200 shipped a flat `window.SO_ASSIST = [{sel,title,msg,more}]` array (SDD-201 then expanded it to ~918 flat cards, but kept the same rejected shape) rendered as a small card
in a short bottom drawer, with the depth (`more`) hidden behind a toggle and a bolted-on guided
tour. The operator rejected it for concrete reasons:

1. **Poverty of content** — `msg` was a one-liner; even the `more` depth was thin.
2. **Click-to-reveal** — the useful part was hidden behind a "more" button that had to be clicked
   *every time*.
3. **Tiny panel** — the drawer took ~1/6 of the viewport height; it read as "almost empty".
4. **Broken tour UX** — enabling tour mode broke the layout.
5. **Wrong reference** — it never studied `devops-control-plane`, whose assistant is the operator's
   explicit quality bar.

## 3. Grounded design (learned from devops-control-plane)

### 3.1 The reference

`devops-control-plane`'s assistant is a **full-height sticky side panel** that, on hover/focus of
any element, renders a **cascade**: a context header (what panel am I on) → the parent chain
(dimmed, in-context) → the active element (accent-highlighted), each with `content` always shown
plus a rich `expanded` HTML card auto-shown for the active target. Its
`assistant-content-principles` demand **colleague voice**: never restate the label/value; explain
consequences; cross-reference sibling elements and other panels; teach; be state-aware; prefer
silence over filler.

### 3.2 The hierarchical, state-aware catalogue — `SO_ASSIST` as an object

The flat array is replaced by a **hierarchical object** authored inline per panel
(sovereignty-clean — in the panel, never fetched):

```js
window.SO_ASSIST = {
  context: { icon, title, content },            // what this whole panel is
  nodes: [                                       // the panel's sections
    { icon, title, content, children: [
      { selector:"#id", title, content,          // content: ALWAYS shown, ≥40 chars
        expanded:"<div>…rich authored HTML…</div>",
        variants:[ { when:{ textContains:"offline" }, content, expanded } ] }
    ]}
  ]
};
```

- **`context`** — the panel-level teaching header, always visible.
- **`nodes`** — sections; each section is itself a node with `content`.
- **`children[].selector`** — a CSS selector into the panel's own markup (`#id`).
- **`content`** — the primary teaching sentence(s), **always shown** (no toggle), authored ≥40
  chars so it carries real substance.
- **`expanded`** — a rich authored HTML card (grids / checklists / tips / cross-references),
  **auto-shown** for the active element — never behind a click.
- **`variants[]`** — **state-awareness**: when the live element text matches `when.textContains`
  (or `hasSelector`), the content/expanded swaps (e.g. `offline` → "the daemon is unreachable;
  treat the values as last-known"). This is the "assistant feeling" — the panel reacts to what
  the box is actually doing.

### 3.3 The cascade engine (in the byte-identical app-shell block)

The app-shell block (`webapp/_shared/app-shell-snippet.html`, propagated identically to every
panel by `scripts/webapp/sync-app-shell.py`) now:

1. Reads `window.SO_ASSIST` (object form; the legacy array is still tolerated as a graceful
   fallback so nothing breaks mid-migration).
2. Flattens the tree deepest-first, recording each node's **parent chain**.
3. On delegated `mouseover` / `focusin` over the panel content, matches the event target to the
   **deepest** node whose selector fits (`matches` / `closest` / `querySelector`).
4. Renders the **cascade**: context header → in-chain parent (dimmed) → active target
   (accent-highlighted, `content` + auto-`expanded`), resolving `variants` against the live
   element text, scroll-centering the active card, and highlighting the hovered DOM element.
5. Falls back to the panel context when nothing is hovered (`idle()`).

The panel is **full-height** (`#so-assist` fixed right, full viewport height), replacing the short
drawer. There is **no tour** and **no more-button** — depth is always on screen.

### 3.4 Authoring discipline (accuracy — SB-077)

Every card is grounded in a **real element id** in that panel (verified: all selectors resolve),
in `config/dashboard-catalog.yaml`, and in the panel's cited modules/SDDs. Colleague voice: the
`content`/`expanded` never merely restate the label — they explain what the value *means*, its
consequence, and where to look next (sibling element, another D-panel). When there was nothing
true to add, the text stays short rather than padded.

## 4. Way forward → done (the arc, and where it landed)

- **Stage 0:** the app-shell rebuild — new full-height `#so-assist`, the new
  `so-ctx`/`so-node`/`so-card`/`so-grid`/`so-li`/`so-tip` render classes, and the cascade engine
  replacing the old flat renderer + tour. Re-synced byte-identical into every adopted panel.
- **Stage 1..N (completed in this comprehensive PR):** the hierarchical `SO_ASSIST` catalogue
  authored **panel-by-panel across all 51 adopted panels**. Every `children[].selector` targets a
  **real element id** (verified: **866 selectors resolve, 0 unresolved**); every `content` is
  substantive (≥40 chars, no thin entries); state-aware `variants` added wherever the panel has a
  live/offline/armed/error posture worth reacting to.
- **Non-mutating invariant** preserved and re-verified by the contract test — the app-shell block
  is byte-identical across panels and contains no fetch/XHR/POST (R10212 / §17 sovereignty-clean).
  The catalogue is read-only annotation; no panel's data behavior changed.
- **Full regression:** the complete `tests/lint/` suite is green (5737 passed, 46 skipped, 0
  failures) on the rebuilt tree.

## 5. Open questions

| Q | Question | Proposed |
|---|---|---|
| Q-201-A | Catalogue location — inline `SO_ASSIST` object per panel vs a generated per-panel file. | Inline object (self-contained, sovereignty-clean, colocated with the panel). Carried from Q-200-A. |
| Q-201-B | Variant matching — `textContains`/`hasSelector` today; do we need value-range or regex predicates? | Sufficient for current panels; extend the resolver only when a panel needs it. |
| Q-201-C | The optional live-LLM "discuss" layer (inherits SDD-067 Q-067-F / SDD-200 Q-200-C). | **Flagged future decision** — a network path in tension with sovereignty-clean + a trust model; do NOT build until the operator decides. The authored cascade is complete standalone. |
| Q-201-D | Authoring order across the panels. | **Resolved** — all 51 panels rebuilt in one comprehensive PR (operator: *"no need for small PR"* / *"DO NOT STOP TILL YOU DID THE JOB"*). |

## 6. Non-goals

- **No LLM / chat backend** in this SDD (Q-201-C is the future hook).
- **No change to any panel's data behavior** — the cascade is read-only annotation.
- **No shared runtime asset** — `SO_ASSIST` is inline per panel; the app-shell block stays
  byte-identical + non-mutating.
- **No tour, no more-button, no bottom drawer** — explicitly removed per the operator directive.

## 7. Cross-references

- SDD-200 — the flat gold-data **mechanism** this supersedes.
- SDD-201 — the flat per-element **expansion** (~918 cards) this supersedes.
- SDD-067 — the app-shell (header + sidemenu + Assistant) this rebuilds within.
- SDD-100 — parallel-session bands (this is SDD-202, header-sidemenu 200–299 band).
- `config/dashboard-catalog.yaml` — the authoritative menu-link descriptions.
- `webapp/_shared/app-shell-snippet.html` — where the cascade engine + `SO_ASSIST` reader live.
- `scripts/webapp/sync-app-shell.py` — propagates the byte-identical block to every panel.
- `devops-control-plane` assistant (full-height cascade + `assistant-content-principles`) — the
  quality bar this rebuild learns from, adapted sovereignty-clean (inline, no fetch).
