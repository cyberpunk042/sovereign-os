# Scaffold tier (PRs 1–3)

Established the repo's structural foundation:

- **PR 1** — Charter (`docs/sdd/000-charter.md`) + decisions log + INDEX + LICENSE + .gitignore + README
- **PR 2** — `ARCHITECTURE.md` + SDD-001 cross-repo boundaries + handoff 001
- **PR 3** — mdbook + MCP config template + SDD-002 documentation pipeline

**Stage Gate 1** fired after PR 3 merged.

## What landed

| File | Role |
|---|---|
| [`docs/sdd/000-charter.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/sdd/000-charter.md) | Project mission, SDD+TDD discipline, SFIF, IaC quality bar, "Debian as Ark", sovereignty principles, non-goals |
| [`docs/sdd/001-cross-repo-boundaries.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/sdd/001-cross-repo-boundaries.md) | Direction-of-dependency contract; reference shape per artifact-type; Q-011 partial resolution |
| [`docs/sdd/002-documentation-pipeline.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/sdd/002-documentation-pipeline.md) | docs-vs-internal-docs split; mdbook + CI |
| [`ARCHITECTURE.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/ARCHITECTURE.md) | Four-repo boundary diagram; 11 SAIN-01 epics cited |
| [`docs/decisions.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/decisions.md) | D-001..D-003 locked; Q-001..Q-019 seeded |

## Operator-verbatim quality bar (carried)

> "Do not rush anything and do not minimize anything nor should you compress or conflate or hallucinate anything"
>
> "we always deliver IaC, high quality scripts and libs and configuration and easily tweakable and configurable and customisation and even via env vars when needed, or other pre-existing config or temporary file detected and restarting from there"
