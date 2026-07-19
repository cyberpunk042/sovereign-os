# Architecture

> **The canonical architecture document is at the repo root**:
> [`ARCHITECTURE.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/ARCHITECTURE.md).
> This page is a navigation stub for the mdbook.

## At a glance

- **Four repos**: sovereign-os BUILDS, selfdef RUNS, info-hub
  SYNTHESIZES, root-modules GOVERNS AI agents (endpoint mode,
  proxy half disabled — SDD-046).
- **11 SAIN-01 epics** (E100–E110) — architectural baseline owned by
  info-hub; sovereign-os materializes them; never re-derived.
- **4 lifecycle stages**: pre-install · during-install · post-install ·
  ongoing-management.
- **4 cross-cutting concerns**: profiles · whitelabel · observability ·
  evolvability.
- **SFIF mapping for this arc**: Scaffold (PR 1–3) → Foundation (PR
  4–8) → Infrastructure (PR 9–10 start; Stage 2+ continues) →
  Features (Stage 2+).
- **5 stage gates**: after PR 3 · PR 4 (substrate) · PR 6 (schema) ·
  PR 8 (whitelabel + legal) · PR 10 (foundation-complete).

See [`ARCHITECTURE.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/ARCHITECTURE.md)
for the full architecture and the
[SAIN-01 milestone](https://github.com/cyberpunk042/devops-solutions-information-hub/blob/main/wiki/backlog/milestones/sain-01-sovereign-node.md)
for the architectural baseline (11 epics).
