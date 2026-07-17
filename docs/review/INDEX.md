# Review (audit phases) index

Audit phases run after substantive work cycles converge, to systematically
review the codebase + docs + workflow for drift, gaps, and quality
regressions. Mirrors selfdef's `docs/review/phase-N/` pattern.

| Phase | Trigger | Status | Charter |
|---|---|---|---|
| [phase-1](phase-1/) | operator-authored (2026-07-12) — whole-repo improvement audit | open (ledger populated; 100+ findings `F-2026-NNN`) | [phase-1/00-charter.md](phase-1/00-charter.md) |

## When a phase opens

A phase opens when one of these conditions fires:

- **Stage-gate trigger** — at Gate 5 (PR 10, foundation-complete), a
  Phase-1 audit may open to review the entire foundation phase
  holistically.
- **Cycle-composition trigger** — when a cycle of N+ PRs closes on a
  cross-cutting concern (substrate, schema, whitelabel, harness, build
  scripts, lifecycle).
- **Operator-authored trigger** — operator directly opens a phase.

## Phase structure

Each `docs/review/phase-N/` directory contains:

- `00-charter.md` — what the phase covers, its scope, its non-goals.
- `01-explorer-<area>.md` — one or more area-specific exploration
  reports (codebase walk, docs walk, workflow walk, test walk, …).
- `phase-1/99-findings-ledger.md` — consolidated findings with IDs
  (`F-YYYY-NNN`), severity, status (open / shipped / deferred /
  rejected), and links to the closing PR or follow-up SDD.

## Findings ledger format

```markdown
## F-YYYY-NNN — <title>

**Severity**: blocker | important | minor | observation
**Area**: <SDD / script / config / doc / workflow / ...>
**Found in**: phase-N, <explorer file>
**Status**: open | shipped (PR #M) | deferred (to <slot>) | rejected (D-NNN)
**Summary**: <one paragraph>
**Recommendation**: <action>
```

Selfdef's `docs/review/99-findings-ledger.md` is the reference for the
F-NNN tracking pattern.
