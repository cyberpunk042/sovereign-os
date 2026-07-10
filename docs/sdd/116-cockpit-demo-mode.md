# SDD-116 — Cockpit DEMO mode (opt-in, always-badged sample data so panels are explorable with no daemon)

> Status: draft — **design for operator review (doctrine-touching: reconciles with SB-077)**
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: operator directive 2026-07-10 — *"it would be nice if when there is the services unreachable / not installed or configured or whatever that we can enable a demo mode to see and 'test' things, like for the code page or lm orchestration or lm status & operation and so many other"*.
> Derived from / extends: SDD-111/113/115 (the `offline`/`FIXED_*` render hooks this plugs into), the personalization localStorage idiom (`sovereign-os.personalization`). §1g operator-surface. Recover band (SDD-116 / E11.M116 per SDD-100).

## Mission

Let the operator flip a **DEMO mode** so panels whose daemon is unreachable / not installed / not
configured render **clearly-labelled sample data** — enough to see the full UX and "test" the
interactions (Code Console, D-21 LM Orchestration, D-22 LM Status & Operability, and more) without any
backend running. DEMO mode is the natural next layer on top of the "always-visible when offline" work:
where the panel currently shows an honest *empty/offline* scaffold, DEMO mode fills that same scaffold
with sample data behind an unmistakable badge.

## The SB-077 reconciliation (the load-bearing design decision — operator, please confirm)

SB-077 is sacrosanct: **never fabricate data presented as real.** DEMO data is fabricated. The design
reconciles this by making DEMO data impossible to mistake for real:

1. **Opt-in only** — DEMO mode is OFF by default; the operator explicitly enables it (a personalization
   toggle). It never turns itself on.
2. **Always badged** — while DEMO is on, every affected panel shows a **persistent, unmistakable DEMO
   badge** (a fixed corner ribbon "DEMO · sample data — not real telemetry") + the `data-source-banner`
   reads "DEMO mode — sample data, not a live daemon". The badge cannot be dismissed while DEMO is on.
3. **No real mutations** — in DEMO mode the composer / Apply / Actions do NOT hit any endpoint; they
   show a canned, DEMO-labelled response (e.g. the Code Console composer streams a scripted sample
   reply prefixed "[DEMO]"). R10212 is strengthened, not weakened (DEMO makes *zero* network calls).
4. **Sample data is authored + labelled as sample** — the DEMO datasets live in the panel, are obvious
   placeholders (e.g. model ids like `demo/qwen3-coder`, sessions like `demo-session-01`), and every
   DEMO render path is behind the badge.

Under these four constraints DEMO data is not "fabrication presented as real" — it is operator-requested,
always-labelled sample data for exploring the UI. **If the operator prefers a different reconciliation
(or wants DEMO gated behind an even louder confirm), that steers this SDD before any build.**

## Grounded design — a shared mechanism + per-panel sample data

- **The toggle** — a `demo` boolean on the personalization pref (`sovereign-os.personalization`, schema
  bumped or a sibling `sovereign-os.demo` key). A control in the **personalization** panel ("DEMO mode —
  sample data for exploring panels with no daemon"). Also: when a panel detects its daemon is
  unreachable, its offline card offers "▸ Enable DEMO mode to explore this panel" (a link to the toggle).
- **A shared inlined helper** (like the personalization pre-paint snippet, lockstep-linted): reads the
  `demo` flag + renders/removes the DEMO badge. Kept in `webapp/_shared/` and distributed.
- **Per-panel DEMO data + render branch** — each demo-capable panel gets a `DEMO_<X>` sample dataset and,
  at the top of its render/refresh, `if (demoOn()) return renderDemo();`. renderDemo reuses the existing
  render functions with the sample data + sets the badge; the composer/actions use canned DEMO responses.
- **A contract-lint guard** per demo-capable panel: DEMO is opt-in (off by default), the badge string is
  present, and DEMO mode adds NO network call (R10212).

## Scope (this increment vs rollout)

- **This increment (Stage 1)**: the shared mechanism + the toggle in personalization + **Code Console**
  as the first demo-capable panel (the operator named it first; it's the freshest). A working,
  reviewable proof of the pattern.
- **Follow-ups (sequenced, named — not minimized)**: D-21 LM Orchestration, D-22 LM Status &
  Operability, then the broader set ("so many other") — each a small increment applying the same helper
  + a `DEMO_<X>` dataset.

## Goals

- One operator toggle enables explorable, clearly-labelled sample data across demo-capable panels.
- Unmistakable DEMO badge on every affected panel; impossible to confuse with live telemetry (SB-077).
- Zero network calls in DEMO mode (R10212 strengthened).
- A shared mechanism so rollout to more panels is mechanical.

## Non-goals

- Not a fake backend / not a mock server — DEMO is a client-side render mode only.
- Not on by default, ever. Not auto-enabled.
- No change to live-data behaviour when DEMO is off.

## Open questions

| Q | Question | Proposed |
|---|---|---|
| Q-116-A | The SB-077 reconciliation (opt-in + always-badged + no-mutations + labelled sample). | **proposed: as above** — operator confirms this is honest enough, or names a stricter gate. |
| Q-116-B | Toggle home: a `demo` field on `sovereign-os.personalization` vs a sibling `sovereign-os.demo` key. | **proposed: sibling `sovereign-os.demo` key** (schema-guarded) — keeps DEMO orthogonal to theme/accent, easy to clear. |
| Q-116-C | First-panel scope. | **proposed: Code Console first** (operator named it first), then D-21 + D-22, then the rest. |
| Q-116-D | Auto-offer DEMO from the offline card when a daemon is unreachable? | **proposed: yes** — a non-intrusive "▸ Enable DEMO to explore" link in the offline card (still operator-click). |

## Way forward (stages)

- **Stage 0 (this doc)** — SDD-116 + INDEX + mandate E11.M116. **Operator reviews the SB-077
  reconciliation (Q-116-A) before Stage 1.**
- **Stage 1** — shared `webapp/_shared/demo-mode` helper + personalization toggle + Code Console DEMO
  (dataset + render branch + canned composer + badge) + contract lint.
- **Stage 2** — full gate + Playwright (DEMO on: Code Console shows badged sample sessions + a scripted
  composer reply, zero network calls; DEMO off: unchanged) + commit/push/draft PR.

## Cross-references

- SDD-111/113/115 — the `offline`/`FIXED_*` render hooks DEMO plugs into.
- The personalization localStorage idiom (`sovereign-os.personalization`) + panel (the toggle home).
- SB-077 (never fabricate) — the doctrine this SDD reconciles via opt-in + always-badged sample data.
- SDD-100 — parallel-session band scheme (recover band 100–199 / E11.M100–199).
