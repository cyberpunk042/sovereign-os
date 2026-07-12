# SDD-952 — context.md counts-as-contract: the re-orientation surface can't silently drift again

> Status: draft
> Owner: operator-directed ("continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-12
> Number band: **950–999 (general / audit session)** per SDD-100.
> Closes findings: **F-2026-030** (`context.md`, the mandated "read me first" surface, was ~6 weeks stale and self-contradictory — 29 vs 476 crates when the tree had 714; "17 of 21 dashboards"; "29 SDDs"). From `docs/review/phase-1/99-findings-ledger.md`.
> Derived from / extends: `context.md` (the operator-requested re-orientation surface) + `tests/lint/`.

## Mission

Make `context.md` — the operator's "read me first after every compaction" surface — **structurally unable to
silently drift**. Its own banner says *"if anything below is stale, fix it before continuing — never silently let
it drift."* It drifted anyway: the Phase-1 audit found it self-contradictory (it stated both "29 crates" and "476
crates" while the tree held **714**), claiming "17 of 21 dashboards" (reality: 25 `d-NN` + 55 total panels) and
"29 SDDs" (the tree already held well over a hundred), last-updated 2026-05-19. A one-time refresh would just rot again. The fix is a
**machine-verified contract**: `context.md` carries its key counts in a parseable block, and a lint asserts them
against the filesystem — so drift **fails CI** instead of accumulating.

## Problem

- The re-orientation surface trailed the code by ~6 weeks and contradicted itself on the most basic facts (crate
  count), so a cold-start agent reading it "first" was misinformed.
- Nothing enforced freshness — the "never let it drift" rule was prose, and prose drifts (the audit's recurring
  theme: generate + lint the counts, don't hand-maintain them).

## What this SDD builds

### 1. `context.md`: a current-state section with a COUNTS-CONTRACT block

A new **"Current state (2026-07-12 — counts machine-verified)"** section at the top (superseding the stale
"Current arc" header, which is retitled **"Historical arc"**), containing a fenced `COUNTS-CONTRACT` block:

| metric | count | source |
|---|---:|---|
| workspace crates | 714 | `crates/*/` |
| dashboards (d-nn) | 25 | `webapp/d-*/` |
| cockpit panels (total) | 55 | `webapp/*/index.html` |
| sdd files | 134 | `docs/sdd/<NNN>-*.md` |
| milestone files | 85 | `backlog/milestones/*.md` |

Plus a concise "recent arcs" summary (the July intelligence layer + the in-flight Phase-1 audit closures + the
SDD-100 band convention) so the surface actually reflects where the project is.

### 2. `tests/lint/test_context_md_counts.py`: the enforcing lint

Parses the `COUNTS-CONTRACT` block and asserts every declared count against the live tree
(`crates/`, `webapp/`, `docs/sdd/`, `backlog/milestones/`). Two tests: the block exists with all tracked
metrics; and every number matches reality. A drift now fails CI with a `stated -> actual` diff.

## Goals

- The re-orientation surface's headline counts are always true (or CI is red).
- Updating after a tree change is a one-line edit to the block; the lint tells you exactly which number drifted.
- The historical resume-cycle narrative below is left intact (it's a dated log, not a current claim) — only the
  misleading "Current arc" header is retitled and the current-state section added on top.

## Non-goals

- **Rewriting context.md's full historical log.** Those dated entries ("Workspace count now 118 … 476 …") are a
  point-in-time record; retitling the current-arc header + adding an authoritative current-state block on top is
  the honest fix, not deleting history.
- **A SessionStart hook that regenerates the block** — nice future automation, but the lint (fail-on-drift) is
  the load-bearing guarantee; auto-refresh can follow.
- Extending the contract to every count in every brain doc (mdbook SUMMARY, MASTER-PLAN — F-2026-032/033) — the
  same pattern applies there, tracked separately.

## Verification

- `cargo`/runtime: none (docs + lint only).
- `python3 -m pytest tests/lint/test_context_md_counts.py` — 2 passed (block present with all metrics; counts
  match the tree: 714 crates / 25 dashboards / 55 panels / 134 SDDs / 85 milestones).
- Full `tests/lint` + `tests/schema` — green.

## Way forward

The same counts-as-contract pattern is the fix for F-2026-032 (MASTER-PLAN vs context.md contradictions) and
F-2026-033 (mdbook SUMMARY frozen at SDD-067) — generate/lint those surfaces too. A SessionStart auto-refresh of
the block is a natural follow-up.

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — F-2026-030 (source), F-2026-032/033 (sibling doc-drift)
- `context.md` — the COUNTS-CONTRACT block + current-state section
- `tests/lint/test_context_md_counts.py` — the enforcing lint
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
- MS003 `unsigned-pending-MS003`
