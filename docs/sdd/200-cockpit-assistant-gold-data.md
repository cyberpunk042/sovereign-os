# SDD-200 — Cockpit Assistant gold-data content system (hardcoded hover intel, LLM optional)

> Status: **draft**
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: E11.M200 (mandate decomposition — cockpit assistant gold-data content)
> Derived from: operator directive 2026-07-09 (verbatim below); builds ON SDD-067 (the app-shell
> header + sidemenu + Assistant drawer, shipped across all 50 panels). First SDD in the
> **header-sidemenu session's 200–299 band** per SDD-100 (parallel-session conflict avoidance).

## 0. Operator directive (verbatim)

> "the Assistant panel does not need an LLM backend, it could be an option yes to get more or
> discuss about what is said in the panel but its mostly hardcoded gold data / message /
> information about what is hovered, it takes a long time and we will need to start at some
> point. we can also polish in general…"

## 1. Mission

Turn the Assistant drawer from a thin hover-echo into a body of **hardcoded "gold data"** — a
curated title + message + expandable detail for the meaningful elements of each cockpit panel,
plus the menu-link descriptions already shipped. **No LLM is required**: the intelligence is
authored, deterministic, offline, sovereignty-clean. A live-LLM "ask / discuss this" is an
*optional* future add-on layered on top of the same data, never a dependency.

This is explicitly a **long, ongoing** authoring effort (50 panels × their key elements). This
SDD establishes the model + mechanism and **starts** it; the content is filled in panel-by-panel
over subsequent increments.

## 2. Problem — where SDD-067 left the Assistant

The app-shell Assistant (SDD-067) ships with:
- **Menu-link descriptions** — every sidemenu link explains its panel (from
  `config/dashboard-catalog.yaml`). Good.
- **`data-assist` inline hover-help** — but authored on only ONE panel (D-04, 6 elements). The
  other 49 panels have no element-level intel.
- **A tour** that walks the `data-assist` elements.

The gap: there is no scalable, rich **per-panel content model**. `data-assist="…"` is a single
flat string on an element — no title, no expandable depth, and it edits the panel's markup
element-by-element. For "gold data" (a real explanation with a headline + body + more) authored
across a large surface, that is too thin and too invasive.

## 3. Grounded design

### 3.1 The gold-data model — a per-panel `SO_ASSIST` catalogue (selector-keyed)

Adapted from `devops-control-plane`'s `assistant-catalogue.json` (title / content / expanded,
keyed by a CSS `selector`), but **sovereignty-clean**: the data lives *in the panel*, not in a
shared fetched asset. Each panel optionally defines, in a small inline `<script>`:

```html
<script>
  window.SO_ASSIST = [
    { sel:'#per-req-max', title:'Most expensive request',
      msg:'The single priciest call in the window — your worst-case, not your average.',
      more:'A high value here with a low average means one outlier (a huge cloud-expert prompt). Trace it in D-05, and check whether the profile should have kept it local.' },
    // …
  ];
</script>
```

- `sel` — a CSS selector into the panel's own content (`#id`, `.class`, `[data-x]`).
- `title` — the headline (bold) shown in the drawer.
- `msg` — the primary gold message (1–2 sentences) — what the element means.
- `more` — optional expandable detail (the "get more" depth), revealed by a **more ▾** toggle.

The app-shell block (unchanged per panel, byte-identical) **reads `window.SO_ASSIST` at init**
and wires each `sel` element for hover/keyboard-focus + the tour — exactly like inline
`data-assist`, which stays supported as the lightweight one-liner fallback. Both feed one unified
target list (`SO_ASSIST` entries ∪ `[data-assist]` elements).

**Why this shape:** (a) rich (headline + body + depth) vs a flat string; (b) authored as *data*,
decoupled from markup — no per-element attribute surgery; (c) trivially extensible with the
optional LLM hook (§3.3); (d) still 100% client-side, no shared asset, no fetch — the
non-mutating contract holds.

### 3.2 Drawer rendering

The "Focus / hover" section renders: **title** (bold) · **msg** · a **more ▾** toggle when `more`
is present (reveals/collapses the detail). The tour steps through the same unified list, showing
title + msg + more per step. Menu-link hover keeps showing the panel's catalog description
(a `SO_ASSIST`-shaped entry synthesized from the catalog).

### 3.3 The optional LLM layer (NOT built here — the "option to discuss")

The operator's *"it could be an option yes to get more or discuss"* is a **future, opt-in** layer:
a small **"✦ discuss"** affordance on the current gold-data card that would send *the already-shown
hardcoded context* (panel + element + msg) to a local assistant for follow-up. It is:
- **off by default**, **not** in this SDD's scope, and gated behind an explicit operator opt-in;
- a **network path** → in tension with sovereignty-clean → requires a trust/permission decision
  (this is the SDD-067 Q-067-F question, inherited here as **Q-200-C**);
- purely additive — the hardcoded gold data is complete and useful without it.

### 3.4 Authoring discipline (accuracy — SB-077)

Gold data must be **true**. Author from the panel's real behavior + `config/dashboard-catalog.yaml`
+ the relevant SDD/spec — never invent a metric or a control. When unsure, write less, not
fiction. Menu descriptions already come from the authoritative yaml; element gold-data is authored
against the panel's actual elements.

## 4. Way forward (this SDD starts it; the tail is ongoing)

- **Stage 0 (this commit):** SDD-200 + INDEX row 200 + mandate E11.M200.
- **Stage 1:** app-shell mechanism — read `window.SO_ASSIST`, unify with `[data-assist]`, render
  title/msg/more + the more-toggle; re-sync into all 50 panels (the block stays byte-identical).
  Seed the **reference panel (D-04 costs)** with a real `SO_ASSIST` gold-data catalogue.
- **Stage 2..N (ongoing, efficient loop — no per-panel preview):** author `SO_ASSIST` gold data
  panel-by-panel, prioritising high-traffic panels (D-00 hub, D-01 sessions, D-03/D-21/D-22
  models, D-06 approvals, D-09 hardware, the selfdef mirrors). Each panel is a small additive
  edit; the shell needs no change.
- **General polish** (operator-invited): spacing/typography, collapsed-rail affordances, the
  status pill wiring, keyboard niceties — folded in opportunistically.

## 5. Open questions

| Q | Question | Proposed |
|---|---|---|
| Q-200-A | Gold-data location — inline `SO_ASSIST` per panel vs a generated per-panel file. | Inline `SO_ASSIST` (self-contained, sovereignty-clean, colocated with the panel). |
| Q-200-B | Menu-link `more` depth — should sidemenu links also gain an expandable `more`? | Add later by extending the catalog (from the yaml) — not blocking Stage 1. |
| Q-200-C | The optional LLM "discuss" layer (inherits SDD-067 Q-067-F). | **Flagged future decision** — network path vs sovereignty-clean + a trust model; do NOT build until the operator decides. |
| Q-200-D | Authoring order / prioritisation across 50 panels. | High-traffic first (see Stage 2..N); the tail fills in over time. |

## 6. Non-goals (Stage N)

- **No LLM / chat backend** in this SDD (Q-200-C is the future hook).
- **No change to any panel's data behavior** — gold data is read-only annotation.
- **No shared runtime asset** — `SO_ASSIST` is inline per panel; the app-shell block stays
  byte-identical + non-mutating.

## 7. Cross-references

- SDD-067 — the app-shell (header + sidemenu + Assistant) this builds on.
- SDD-100 — parallel-session bands (this is SDD-200, first in the header-sidemenu band).
- `config/dashboard-catalog.yaml` — the authoritative menu-link descriptions.
- `webapp/_shared/app-shell-snippet.html` — where the `SO_ASSIST` reader lands.
- `devops-control-plane` `src/ui/web/static/data/assistant-catalogue.json` — the title/content/
  expanded-by-selector pattern this adapts (sovereignty-clean, inlined).
