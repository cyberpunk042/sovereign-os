# SDD-971 — consolidated deferred-work register

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-037** (deferred-work items promised in docs — consolidated register), at the consolidation core; ownership/sequencing left as an operator decision.
> Mandate module: **E11.M971** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

The docs already **promise** ~10 pieces of deferred work — scattered across `docs/decisions.md`, a dozen SDDs, and `context.md`. Because they're scattered, each audit pass **rediscovers** them instead of tracking them. F-2026-037's ask was precise: *"they need owners/ordering, not rediscovery"* — i.e. consolidate the promises into one register, not re-specify them.

## What this SDD builds

### 1. `docs/review/phase-1/deferred-work-register.md` — the pointer index

One table consolidating the 10 deferred items, each with: title · **source reference(s)** (the SDD / doc where it's authoritatively defined) · a one-line scope · a **proposed order** (grouped foundation → reproducibility/security → hardware/cross-repo → questions) · an **owner column set to `operator-to-assign`**. It is a pointer index, not a re-spec — each item's real definition stays in its cited source. Sequencing + ownership are explicitly an **operator decision-package**, not an agent call. Two items are flagged as the ledger notes them: item 7/8 (MS043 selfdef mirror surfaces) are cross-repo + need reconciling against the M060 completion claim; item 10 (Q-067-A..F) is partially overtaken by the July Brain/Code-Console arc.

### 2. `tests/lint/test_deferred_work_register.py` — the source-resolution contract

Every `SDD-NNN` and every doc path cited in the register must resolve to a file that exists — so the register can't rot into dangling references as SDDs are renumbered or docs move. It deliberately does **not** assert an item is still open (status reconciliation is per-item operator/authoring-session work against the source); the contract guards reference validity, which is the part that can silently break.

## Verification

- Every cited source resolves: `docs/decisions.md`, `context.md`, and SDD-015/016/019/020/022/029/046 (+ the SDD-003..025 range) all exist (checked before authoring); MS043 mirror-crates confirmed still `impl pending` in `context.md`.
- `python3 -m pytest tests/lint/test_deferred_work_register.py` — **3 passed** (register exists; every cited SDD resolves; every cited doc path resolves).
- `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Assigning owners / final sequence** — an operator decision-package; the register proposes an order and marks owners `operator-to-assign`.
- **Executing any of the 10 items** — this consolidates the promises; each item is its own future arc (several are large: Layer-4/5 suites, TPM2 PCR binding, reproducibility).
- **Reconciling each item's live status** — e.g. whether item 10's Q-067 questions survive the Brain/Code-Console work, or whether item 7's MS043 crates are done — that's per-item work against the cited source; the register flags the two the ledger already calls out.
- **Cross-repo closure** (items 7–8, selfdef) — only closable with the selfdef tree in scope.

## Safety invariants

Docs + read-only lint only — no crate code, no runtime behavior, no gateway touch. The register points at existing sources; it invents no new commitments (every item traces to a doc that already promised it). R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/review/phase-1/deferred-work-register.md` — the register
- `tests/lint/test_deferred_work_register.py` — the source-resolution contract
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-037 (source); F-2026-052 (Layer-4/5, register item 3)
- `docs/decisions.md` · `context.md` · SDD-015/016/019/020/022/029/046 — the cited sources
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
