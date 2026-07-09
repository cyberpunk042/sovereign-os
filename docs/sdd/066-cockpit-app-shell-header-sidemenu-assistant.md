# SDD-066 — Cockpit app-shell: persistent header + collapsible sidemenu + Assistant mode

> Status: **draft** (planning — stop-for-review; no implementation this pass)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Derived from: operator directive 2026-07-09 (this session, verbatim below);
> inspiration operator-named — `devops-control-plane` `src/ui/web/templates/partials/_nav.html`;
> builds ON the existing per-panel canonical snippet stack (SDD-040 cockpit bridge,
> SDD-045 control-surface buildout, M060 keyboard-nav / a11y / responsive / personalization
> snippets); brain-of-record if depth needed = the wiki-hub (`devops-solutions-information-hub`).

---

## 0. The standing rule this plan answers

`<meta name="x-sovereign-standing-rule" content="We do not minimize anything.">`

## 0.1 Operator directive — verbatim, un-minimized (sacrosanct)

> "inspired from the devops-control-plane, lets start thinking of a header and
> sidemenu for the sovereign-os panels / dashboards.... something each of them
> can benefit and we can use to navigate and change settings like Assistant mode
> which will be a supplementatary panel that gives more info and assistant help
> with a good feeling when we hover element and theme toggle and such. it will
> weave together all the dashboard, even if two pages have cards or links to all
> the panels / dashboard, this will be the next level, lets think of this right,
> lets take the time. as always the brain is the wiki-hub if needed and like I
> said we can inspired ourself from the control-plane, for whatever is relevant
> that we can establish together. Take your time and do no minimize and start
> with a good research and questions and planning."

### Session decisions (operator, 2026-07-09 — via AskUserQuestion)

| # | Decision point | Chosen |
|---|---|---|
| 1 | **Distribution** across the ~52 self-contained panels | **Template + generator/sync** — a canonical source-of-truth block in `_shared/`, a generator that writes it into every panel, a contract test that enforces identity. Stays fully sovereignty-clean (no CDN, no shared runtime asset). |
| 2 | **Assistant mode** scope | **Client-side contextual help** — hover an element → explanation; a "what is this panel / what can I do here" help drawer + guided tour. No backend, no data leaves the box. |
| 3 | **Layout** | **Header + collapsible sidemenu**, applied to all ~52 panels. The full "next level." |
| 4 | **This session's deliverable** | **Plan/SDD, stop for review.** This document + a backlog note; no code. |

---

## 1. Mission

Give every cockpit surface a **shared app-shell** — a persistent top **header**
and a collapsible left **sidemenu** — so an operator landing on ANY of the ~52
panels can (a) *see where they are*, (b) *reach any other panel in one move*,
(c) *change global settings* (theme, and later more) from a fixed place, and
(d) *summon Assistant mode* — a supplementary drawer that explains the panel and
its elements on hover, with a good tactile feel. The shell **weaves the panels
into one product** without collapsing the multi-page, self-contained,
sovereignty-clean architecture that already ships.

Today navigation is already partly solved (⌘K palette + ⌘1..0 + the
master-dashboard hub) — but it is *invisible until invoked* and there is no fixed
chrome, no visible theme control on each page, and no in-context help. This plan
makes the weave **always-present and legible**.

---

## 2. Problem — what exists, and the gap

### 2.1 What already exists (this plan EXTENDS, never replaces)

The cockpit is **~52 self-contained panels** under `webapp/` — 25 numbered
dashboards (`d-01`…`d-25`) plus named panels (`master-dashboard`/D-00,
`surface-map`, `auditor`, `weaver`, `trinity`, `router`, `orchestration`,
`build-configurator`, `personalization`, …). Each is a single `index.html`
served statically (with live data via `scripts/operator/*-api.py`, e.g.
`/catalog`, `/control-systems`, `/api/control/registry`).

Every adopted panel already carries a **canonical `<head>` snippet stack** —
four blocks, in this order, each duplicated verbatim per panel and each guarded
by a lint contract test:

| Order | Snippet (source of truth in `_shared/`) | Purpose | Contract test |
|---|---|---|---|
| 1 | *personalization apply-snippet* (~20 lines, inline) | sets `data-theme` / `--accent` / `--font-scale` from `localStorage` **pre-paint** (no FOUC) | `tests/lint/test_personalization_contract.py` |
| 2 | `nav-snippet.html` (~110 lines) | ⌘K command palette + ⌘1..0 jump shortcuts (client-side `window.location`) | `tests/lint/test_keyboard_nav_contract.py` |
| 3 | `a11y-snippet.html` | WCAG 2.1 AA focus-visible ring, **skip-to-content link**, reduced-motion guard | `tests/lint/test_a11y_contract.py` |
| 4 | `responsive-snippet.html` | breakpoints ≤600 / ≤1024 / ≥2400 | `tests/lint/test_responsive_contract.py` |

Plus a shared **design grammar** (`_shared/design-grammar.md`): the token set
(`--bg --fg --muted --border --accent --ok --warn --danger`), the button
hierarchy (**one `.primary` per view**; executable actions are never ghost
buttons; `.heavy` confirms + states its cost), console cards, and status pills
(`live ✓` / `live ✗` / snapshot). Reference impl: `webapp/build-configurator/`.

Two panels already do **weaving**: `master-dashboard` (D-00) is the front door
(inlines the SDD-045 control-surface, fetches the full `/catalog`), and
`surface-map` maps everything. `personalization` already implements
dark/light/auto + accent + typography, persisted in `localStorage`.

### 2.2 The gap

- **No fixed chrome.** The weave is real but invisible until you press ⌘K or land
  on D-00. There is no persistent header telling you *which panel you are on* or
  giving you a one-glance jump to the rest.
- **No visible global-settings surface per page.** Theme lives only inside the
  `personalization` panel; there is no theme toggle on the page you are reading.
- **No in-context help.** Nothing explains a panel or its controls where the
  operator's attention already is. The "good feeling when we hover element" the
  operator asked for does not exist.
- **The inspiration is SPA; we are not.** `control-plane`'s `_nav.html` is a
  single-page app (`switchTab('dashboard')`). Sovereign-os is 52 separate static
  pages. The chrome therefore **cannot** be a client-router tab bar — it must be a
  block that lives *identically on every page*, which is exactly the problem the
  canonical-snippet doctrine already solves for nav/a11y/responsive/personalization.

---

## 3. Grounded design

### 3.1 Distribution — the **5th canonical snippet** + a generator + a contract test

The app-shell becomes the **fifth** member of the canonical `<head>`/`<body>`
stack, distributed by the *same* doctrine as the other four:

- **Source of truth:** `webapp/_shared/app-shell-snippet.html` — documentation
  header + the canonical block (CSS + a small bootstrap `<script>` + the shared
  `DASHBOARDS`/group catalog), mirroring `nav-snippet.html`.
- **Generator (new):** `scripts/webapp/sync-app-shell.py` — idempotently injects
  the canonical block into every *adopted* panel between marker comments
  (`<!-- APP-SHELL:BEGIN … -->` / `<!-- APP-SHELL:END -->`), **DRY-RUN by default**
  (`--apply` to write), honoring the repo's mutation discipline. It also
  single-sources the `DASHBOARDS`/group catalog so the palette and the sidemenu
  never drift from each other (today the palette's `DASHBOARDS` array is
  hand-duplicated in every panel — the generator ends that).
- **Contract test (new):** `tests/lint/test_app_shell_contract.py` — asserts every
  adopted panel carries the **identical** canonical block (byte-for-byte between
  markers), exactly like `test_keyboard_nav_contract.py`.

**Head vs body split (no per-panel body restructuring):**
- The shell **CSS** ships in `<head>` (pre-paint → no layout shift / FOUC), slotted
  as snippet #5 after the responsive snippet.
- The shell **DOM** (header bar, sidemenu, assistant drawer) is injected into
  `<body>` at `DOMContentLoaded` by the bootstrap script — the *same* technique the
  palette already uses to inject its backdrop. This keeps the generator's body
  footprint to a single marked `<script>` include, so no panel's existing markup
  is touched.
- The shell reserves layout space via CSS custom properties on `:root`
  (`--so-header-h`, `--so-sidemenu-w`) and offsets `body` padding, so injected
  chrome never overlaps panel content.

**Why not the alternatives (recorded):** a shared `_shared/app-shell.js` asset
would be one file but breaks the "no shared runtime asset" doctrine; server-side
injection only works when served (not `file://`) and adds a render path. The
operator chose template+generator — it preserves sovereignty-clean output and
reuses a doctrine that is already tested and trusted.

### 3.2 Header anatomy (persistent, top, full-width)

Inspired by `control-plane` `_nav.html` (brand + section group + right-cluster),
adapted to sovereign-clean and the design grammar:

```
┌───────────────────────────────────────────────────────────────────────────┐
│ ⚑ sovereign-os   ☰   D-04 · costs ▸                 [live ✓] ⟳  ⌘K  ☾  ✦   │
└───────────────────────────────────────────────────────────────────────────┘
   brand         menu  breadcrumb (where am I)     status  palette theme assist
```

- **Left:** brand mark + `☰` sidemenu toggle + **breadcrumb** (`D-NN · <panel name>`),
  the answer to *"where am I"* on every page.
- **Right cluster** (each a ghost/chrome control per the grammar — chrome is never
  `.primary`):
  - **status pill** — reuses the existing `live ✓` / `live ✗` / snapshot grammar;
    reflects the panel's own data-source state (and, when `/catalog` is up, a
    system-wide attention roll-up — see Open Questions).
  - **pending-approvals badge** (optional, count) — a system-wide attention signal
    linking to D-06 (`d-06-pending-approvals`), analogous to control-plane's 🔔.
  - **⌘K palette launcher** — a visible button for the palette that already exists
    (discoverability for mouse users).
  - **theme toggle** `☾ / ☀ / auto` — writes the **same** `localStorage` keys the
    `personalization` panel uses, so the two stay in one source of truth; applies
    instantly via the existing pre-paint variables.
  - **Assistant toggle** `✦` — opens/closes the Assistant drawer (§3.4).
- A thin **refresh-bar** under the header (like control-plane's `.refresh-bar`) is
  optional polish, off by default.

### 3.3 Sidemenu anatomy (collapsible, left, grouped)

- **Three states**, persisted (a personalization-adjacent `localStorage` key):
  **expanded** (icon + label), **collapsed** (icon-only rail), **hidden**
  (off-canvas — the default on phone/tablet per the existing breakpoints).
- **Grouped, collapsible sections** over the ~52 panels. Proposed taxonomy
  (draft — final grouping should be **data-driven from the `/catalog` M060
  metadata** with this as the static fallback; see Open Questions):

  | Group | Panels (illustrative) |
  |---|---|
  | **Overview** | D-00 master-dashboard, surface-map, global-history |
  | **Sessions & Memory** | D-01 active-sessions, D-07 memory-changes, D-08 rollback-points |
  | **Models & Inference** | D-03 model-health, D-10 eval-history, D-11 adapter-status, D-19 super-model-manifest, D-21 lm-orchestration, D-22 lm-status-operability, D-23 models-catalog |
  | **Cost & Load** | D-04 costs, D-05 traces, D-09 hardware-pressure, D-24 cpu-features, ups |
  | **Security & Trust** | D-06 pending-approvals, D-13 filesystem-grants, D-14 capability-tokens, D-15 sandboxes, D-16 audit, D-17 quarantine, D-18 trust-scores, D-25 selfdef-management, auditor, auth-tier, compliance |
  | **Network** | D-12a network-edge, D-12b edge-firewall |
  | **System & Trinity** | D-20 peace-machine-health, trinity, weaver, router, orchestration, runtime-modes |
  | **Build & Configure** | build-configurator, flash, emulate, profile-generation, models-catalog, personalization |
  | **Meta / Audits** | doc-coverage, ux-design-audit, anti-minimization-audit, cpu-features, surface-map |

- **Active item** derived from `window.location.pathname` (matched to the panel
  `dir`), highlighted with `--accent`.
- **Filter box** at the top mirrors the palette filter (same catalog, same
  match logic) — type-to-narrow the list.
- **Navigation is client-side only** (`window.location.href`, no server mutation) —
  identical to the palette's existing contract. ⌘1..0 keep working unchanged.

### 3.4 Assistant mode (client-side contextual help — the "good feeling")

A right-side **drawer** toggled by `✦`, with three complementary faculties, all
pure client-side (no network, no LLM in this scope):

1. **Panel help** — *"what is this panel, what can I do here"*: the panel's M060
   description paragraph (already authored per SDD-045) + its Features / Options /
   Profiles rails + the trust contract line. Sourced from data already embedded /
   in `/catalog`, not re-authored.
2. **Element hover help** — interactive elements are annotated with a
   `data-assist="…"` attribute; on **hover or keyboard-focus** the drawer surfaces
   that element's explanation (and/or an enriched tooltip). This is the operator's
   *"good feeling when we hover element."* Focus-parity (not hover-only) keeps it
   WCAG-clean.
3. **Guided tour** — steps through the panel's key surfaces in order (the design
   grammar already reserves a ghost "tour" button concept). Escape / next / prev;
   remembers "seen" per panel.

**Feel spec:** subtle elevation + `--accent` border on hover, ~120ms transition,
a soft focus glow — all **gated by `prefers-reduced-motion`** (the a11y snippet's
guard). The drawer overlays, never reflows panel content; `Esc` closes it; it is
`role="complementary"` with an accessible label.

**Content authoring:** per-panel `data-assist` annotations + a tiny per-panel help
manifest, OR derived from existing M060 requirement text (Open Question). The
drawer degrades gracefully: a panel with no annotations still shows Panel help
from the catalog.

### 3.5 Integration with the existing four snippets (must not break any)

- **Skip-to-content** (a11y snippet): the header is inserted *before* `<main>`, so
  the skip link must still jump *past* the header to main content — the shell
  gives `<main>` (or the first heading) the skip target id if absent, mirroring the
  palette's existing anchor-resolution helper.
- **Responsive** (responsive snippet): sidemenu is off-canvas ≤1024px; header
  condenses (labels → icons) ≤600px; the drawer goes full-width on phone. Reuses
  the existing breakpoints, adds no new ones.
- **Personalization** (apply-snippet): theme toggle writes the same keys; the shell
  reads the same `--accent`/`--font-scale` variables → zero divergence, zero FOUC.
- **Palette** (nav-snippet): the header's ⌘K button just opens the existing palette;
  the sidemenu shares the single-sourced catalog. No duplication of logic.
- **Design grammar**: all chrome controls are ghost/`.btn` (chrome is never
  `.primary`); the shell introduces **no** executable/server-mutating action.

---

## 4. Staged rollout (spec only — implementation is the NEXT session)

| Stage | Scope | Gate |
|---|---|---|
| **0 (this pass)** | SDD-066 + backlog note. **Stop for review.** | operator reviews this doc |
| **1** | Build `_shared/app-shell-snippet.html` + `scripts/webapp/sync-app-shell.py` + `tests/lint/test_app_shell_contract.py`; adopt on **2 reference panels** (D-00 master-dashboard + `build-configurator`, the grammar reference). | shell renders; palette/theme/a11y/responsive still green on both |
| **2** | Assistant drawer: Panel help + hover `data-assist` + tour, on the 2 reference panels. | hover/focus help works; reduced-motion respected |
| **3** | Sweep **all ~52 panels** via the generator; contract test green; a11y + responsive + reduced-motion regression across the sweep. | `test_app_shell_contract` + the other 4 contract tests all green |
| **4** | Catalog-driven sidemenu grouping (from `/catalog` M060 metadata, static fallback); status/approvals roll-up; polish. | grouping matches catalog; no CLI-only-invisible surface |

---

## 5. Open questions (resolve before Stage 1)

| Q | Question | Proposed |
|---|---|---|
| Q-066-A | Sidemenu **group taxonomy** source. | Data-driven from `/catalog` M060 domain/purpose metadata, with the §3.3 table as static fallback (works `file://` / server-down). |
| Q-066-B | Sidemenu **default state** + persistence key. | Default **collapsed** on desktop, **hidden** ≤1024px; persist under a personalization-adjacent key (fold into the existing personalization schema vs. a new key — operator's call). |
| Q-066-C | Header **status / approvals roll-up**. | Per-panel status is local + already-known; a *system-wide* attention count needs `/catalog` or an approvals-count endpoint (D-06 `approvals-api.py` exists). Confirm the source or ship per-panel-only first. |
| Q-066-D | Assistant **content authoring**. | Hand-authored `data-assist` for high-value controls + auto-derive Panel help from M060 text; do not block Stage 1 on full coverage. |
| Q-066-E | Which panels get the shell. | All operator-facing cockpit panels; confirm whether meta/audit panels (`ux-design-audit`, `anti-minimization-audit`, `doc-coverage`) are in or out. |
| Q-066-F | **Live-LLM Assistant** (Stage-N, out of scope now). | A real assistant chat wired to the ecosystem Per-Project AI Assistant / wiki-hub is a **future decision** — it introduces a network path (sovereignty-clean tension) + a trust/permission model. Flag, do not build. |

---

## 6. Non-goals (Stage N)

- **No live LLM / chat assistant** — Assistant mode here is client-side contextual
  help only (Q-066-F is the future hook).
- **No server-side rendering of chrome** and **no SPA conversion** — the multi-page,
  self-contained architecture stays; the shell is duplicated-by-generator, not a
  router.
- **No new executable/server-mutating action** in the chrome — the shell navigates
  and explains; it never runs anything (the console-card grammar owns execution).
- **No change to any panel's data behavior** or its `scripts/operator/*-api.py`.

---

## 7. Traceability

- Extends: SDD-040 (cockpit bridge), SDD-045 (control-surface buildout),
  M060 (nav / a11y / responsive / personalization snippets + design grammar).
- Inspiration: `devops-control-plane` `src/ui/web/templates/partials/_nav.html`
  (brand + section group + right-cluster; settings-gear & notif slide-outs =
  the pattern the Assistant drawer adapts).
- Backlog note: `backlog/notes/2026-07-09-app-shell-header-sidemenu-findings.md`.
- Brain-of-record for deeper UX/nav standards if needed: the wiki-hub
  (`devops-solutions-information-hub`).
