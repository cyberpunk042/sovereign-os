# Handoff index

Dated session-handoff anchors. Each handoff is a cold-start signpost for
the next session — a fresh agent reading the latest handoff should know
exactly where the project sits and what to do next.

| Date | Title | Supersedes |
|---|---|---|
| 2026-05-16 | [001-architecture-baseline.md](001-architecture-baseline.md) | (none — first) |
| 2026-05-16 | [002-foundation-substantive-buildout.md](002-foundation-substantive-buildout.md) | 001 |
| 2026-05-16 | [003-operator-observability-arc.md](003-operator-observability-arc.md) | 002 |
| 2026-05-16 | [004-operator-friction-audit.md](004-operator-friction-audit.md) | (companion to 003 — honest critical review of operator-journey friction) |
| 2026-05-18 | [006-verbatim-preservation-arc.md](006-verbatim-preservation-arc.md) | 005 (R355-R380 verbatim-preservation contract mechanization — 26 rounds, 82 catalogued items, 67 L1 assertions across 8 lints, 20 real bugs caught, SDD-037 codified) |

Handoffs land at:

- **Stage gate transitions** (5 gates: PR 3 · PR 4 · PR 6 · PR 8 · PR 10).
- **End-of-session anchors** when significant work cycles close.
- **Cross-repo arc transitions** (when sovereign-os work crosses into
  selfdef or info-hub).

## Format

```markdown
# Handoff — <topic> — <YYYY-MM-DD>

> Read this first if you are starting a new session on sovereign-os.
> Supersedes: <prior handoff filename, if any>

## TL;DR — where things are
## What to do FIRST in the next session
## Session trajectory — N PRs (sovereign-os side)
## Cross-repo state map
## Standing rules (carried unchanged)
## Repo signposts (file:line pointers)
## Open items (deferred-by-design or scope-disciplined)
## What this session arc produced
```

The selfdef-side handoff template
(`cyberpunk042/selfdef/docs/handoff/2026-05-16-sovereign-os-arc-opening.md`)
is the reference pattern.
