# Sovereign OS Workstation — Backlog INDEX (catalog scaffold)

> **We are starting from scratch.** Previous SDDs (selfdef 000-026,
> sovereign-os 000-039) and previous milestone artifacts are NOT
> authoritative for this catalog. The catalog is being built from
> operator directives + the raw dump only.
>
> The operator sets the requirements. The AI extracts and enumerates
> from operator material; the AI does not invent milestone names,
> timeline phases, dashboard labels, feature names, or any structure
> the operator has not stated.

## Sources (in order of precedence)

1. **Operator standing directives** (verbatim, sacrosanct). Captured in `raw/notes/` on info-hub for the AVX++ arc; mirrored as-needed here.
2. **Raw dump**: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` (info-hub, 18341 lines).
3. Future operator-pushed directives + dumps.

That's it.

## Operator-stated counts (verbatim from /goal directive 2026-05-19)

| Level | Operator-stated count | Storage |
|---|---|---|
| Milestones | "multiple milestones" (no count stated) | `backlog/milestones/` |
| Epics | "400+ Epics" | `backlog/epics/` |
| Modules | "1000+ modules" (goal); "over 100 modules" (earlier) | `backlog/modules/` |
| Features | "5000+ features" | `backlog/features/` |
| Requirements | "10000+ requirements" (each with "at least 10 hard non-negotiable requirements") | `backlog/requirements/` |
| Main features | "10-15 main features" | inside `backlog/features/` flagged `is_main: true` |
| Dashboards | "over 20 dashboards and a main one" | flagged `category: dashboard` |
| Modes / profiles | "tons of modes and profiles" | flagged `category: profile` / `category: mode` |

## Storage convention

| Path | Holds |
|---|---|
| `backlog/INDEX.md` | this file — scaffold + source authorities + counts |
| `backlog/milestones/INDEX.md` | enumerated milestone list (operator-defined) |
| `backlog/milestones/MNN-<slug>.md` | one file per milestone, content operator-defined |
| `backlog/epics/INDEX.md` | enumerated epic list |
| `backlog/epics/E<NNNN>-<slug>.md` | one file per epic |
| `backlog/modules/INDEX.md` | enumerated module list |
| `backlog/modules/M<NNNN>-<slug>.md` | one file per module |
| `backlog/features/INDEX.md` | enumerated feature list (includes main features) |
| `backlog/features/F<NNNN>-<slug>.md` | one file per feature |
| `backlog/requirements/INDEX.md` | enumerated requirement list |
| `backlog/requirements/R<NNNNN>-<slug>.md` | one file per requirement |

## Status

| Path | State |
|---|---|
| `backlog/INDEX.md` | scaffold-only (this file) |
| `backlog/milestones/INDEX.md` | not yet authored (operator defines next) |
| All per-entry files | not yet authored |

## Rules the AI follows when populating this catalog

1. Every entry traces back to a verbatim operator quote or a verbatim dump line range. No invented names. No invented structure beyond directory paths.
2. The AI does not invent milestone names, timeline phases, dashboard labels, feature names, or main-feature numbering. The operator names them or they get extracted verbatim.
3. The AI does not reference prior SDDs (selfdef 000-026, sovereign-os 000-039) as authoritative. From scratch means from scratch.
4. The AI does not gate progress on operator clarification. When uncertain the AI either extracts more verbatim material or asks one terse question. The AI does not block on "to be confirmed" rows.
5. The AI never minimizes, compresses, conflates, or rephrases operator material.

— End of catalog scaffold.
