# SDD-959 — MASTER-PLAN count reconciliation + a milestone-completeness contract

> Status: draft
> Owner: operator-directed ("continue … do this right, do not minimize" — Phase-1 audit); agent-authored
> Last updated: 2026-07-12
> Closes findings: **F-2026-032**. From `docs/review/phase-1/99-findings-ledger.md`.
> Mandate module: **E11.M959** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.
> Derived from / extends: the counts-as-contract discipline of SDD-952 / SDD-958.

## Mission

`docs/MASTER-PLAN.md` is the cross-repo milestone synthesis (selfdef Solution 2 + sovereign-os Solution 1). The audit found it self-contradictory on the most basic fact — the milestone count:

- it stated **both "128"** (intro line) **and "130"** (top-line table, `## The 130 milestones` header, the status-conventions line);
- its sovereign-os cell said **82** while the file tree had **84** — **M085 and M086 were missing from the enumeration** (the two newest, added after the list was last hand-updated);
- the D-16 audit-chain + D-12 networking rows read `catalog ✓ (not yet wired)` while `context.md` (M060 arc) and the file tree both show the dashboards shipped.

A cold-start reader of the master plan was misinformed on counts and wiring status. This SDD reconciles the numbers **and** installs a completeness contract so the enumeration can't silently fall behind the milestone files again.

## What this SDD builds

### 1. The reconciliation (docs/MASTER-PLAN.md)

- **Counts single-valued at 132** — intro line `128 → 132`; top-line table `48 | 82 | **130**` → `48 | 84 | **132**`; `## The 130 milestones` → `## The 132 milestones`; the status-conventions "All 130 milestones meet this bar" qualified (130 R-row-bearing + M085/M086 = 132).
- **M085 + M086 added to the enumeration** — the two missing sovereign-os milestones, annotated `operator-note (0 R-rows)` because they are operator-note-transcription milestones (2026-07-02 handwritten note) that carry design references rather than the R-row requirement structure — so the "meets the R-row bar" claim stays honest.
- **D-16 / D-12 rows reconciled** — `catalog ✓ (not yet wired)` → `at prod`, cited to `webapp/d-16-audit/` + `webapp/d-12-networking/` (both present, with `index.html`) and context.md's M060 arc.

R-rows are **unchanged** (M085/M086 carry 0 R-rows, so the 14,080 / 25,600 totals still hold).

### 2. `tests/lint/test_master_plan_counts.py` — the completeness contract

Pins the **in-repo-verifiable** invariants:
1. every `backlog/milestones/M*.md` is linked in the enumeration (no silently-missing milestone — the exact M085/M086 failure);
2. no enumeration entry points at a milestone file that no longer exists;
3. the table's sovereign-os cell equals the actual M*.md file count;
4. the combined total equals selfdef-cell + sovereign-os-cell;
5. the three stated totals (intro line, table, header) all agree — the 128-vs-130 contradiction guard.

Same self-maintaining discipline as `context.md`'s counts (SDD-952), the island register (SDD-955), and the mdbook catalog (SDD-958).

## Scope limit — the cross-repo half

MASTER-PLAN also counts **selfdef** milestones (`../../selfdef/backlog/milestones/MS*.md`), which are **not present in this checkout** (selfdef is a separate repo). So the lint verifies the selfdef cell only for **internal consistency** (combined = selfdef + sovereign-os), not against the selfdef tree. If selfdef's real milestone count drifts from the stated 48, that is a selfdef-side or cross-repo-CI concern this lint cannot catch — documented, not silently assumed away. The sovereign-os half (the half this repo owns) is fully enforced.

## Verification

- `python3 -m pytest tests/lint/test_master_plan_counts.py` — 6 passed: MASTER-PLAN exists; every milestone file enumerated; no stale entries; sovereign-os cell == 84 files; combined == 48+84; all three totals == 132.
- Post-edit checks: 84 sovereign-os M-links enumerated == 84 files; zero remaining `128` / `The 130` / `82` count references; `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Verifying the selfdef milestone count (48) or R-row totals against the selfdef tree** — cross-repo; out of this repo's reach (see scope limit).
- **Auto-generating the full enumeration prose** — the entries carry per-milestone R-row counts + titles that read as curated synthesis; the lint enforces completeness + count-consistency without dictating the prose. A generator could follow if the enumeration grows unwieldy.

## Safety invariants

Docs + read-only lint only — no crate code, no runtime behavior, no gateway touch. The reconciliation only corrects counts + two status cells to match verifiable reality (file tree + context.md + on-disk dashboards); it invents nothing. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/MASTER-PLAN.md` — the reconciled synthesis
- `tests/lint/test_master_plan_counts.py` — the completeness contract
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-032 (source); F-2026-033 (the sibling mdbook drift, closed by SDD-958)
- `context.md` — the M060 arc that shipped D-16/D-12 (the evidence for the row reconciliation)
- SDD-952 / SDD-958 — the same self-maintaining-contract pattern
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
