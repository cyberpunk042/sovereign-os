# Introduction

> **Status:** foundation phase — no buildable artifact yet.
> The mdbook scaffolding is operational; substantive content for many
> sections lands in their gated PRs (PR 4 substrate, PR 5 schema, PR 6
> profiles, PR 7 whitelabel inventory, PR 8 whitelabel mechanism, PR 9
> TDD harness spec, PR 10 TDD harness bootstrap, Stage 2+ build
> scripts).

## What this is

`sovereign-os` produces a **custom-built, multi-profile, whitelabel-able
Linux operating system** for the SAIN-01 AI Workstation (default) and
other deliberately-declared hardware profiles. The pipeline covers the
full lifecycle of an OS — pre-install image generation, during-install
experience, post-install / first-boot activation, and ongoing
post-install management — every stage **specified before built** (SDD)
and **tested before run on real hardware** (TDD).

The OS is **sovereign**: operator-owned, operator-evolvable, transparent,
free of phone-home defaults, and able to run without external
dependencies once installed.

## How this book is organized

This mdbook is the **operator-facing** documentation surface — getting
started, architecture overview, profile authoring, lifecycle handbook,
operations runbook. Internal agent-authoritative documents
(`docs/sdd/*`, `docs/decisions.md`, `docs/handoff/*`, `docs/review/*`)
are not rendered here; they live in the repo's `docs/` tree directly.

| You want… | Read |
|---|---|
| Why this repo exists + the four-repo split | [README](https://github.com/cyberpunk042/sovereign-os/blob/main/README.md) |
| Architectural overview (11 epics · lifecycle stages · cross-cutting concerns) | [Architecture](./architecture.md) |
| Mission · SDD+TDD · SFIF · IaC bar · Debian-as-Ark · sovereignty | [Charter & discipline](./charter.md) |
| Open questions Q-001..Q-019 + their resolution paths | [Open questions](./questions.md) |
| Audit trail of resolved decisions D-NNN | [Decisions log](./decisions.md) |
| The Plan-agent 10-PR foundation phase + 5 stage gates | [Foundation phase](./foundation/scaffold.md) |
| Cross-repo boundary contract (sovereign-os ↔ info-hub ↔ selfdef) | [Cross-repo boundaries](./xrepo/direction.md) |
| Build / install / manage runbooks (Stage 2+) | [Operator handbook](./ops/build.md) — landing in Stage 2+ |

## Where authoritative content lives

| Topic | Location |
|---|---|
| Architectural baseline (SAIN-01 milestone + 11 epics + L1–L3 syntheses) | `cyberpunk042/devops-solutions-information-hub` |
| OS-build pipeline + profile schema + whitelabel + TDD harness | `cyberpunk042/sovereign-os` (this repo) |
| Security daemon RUNNING on the OS (selfdef + agent-guard + notifier channels + escalations) | `cyberpunk042/selfdef` |

Full boundary contract: [Cross-repo boundaries → Direction of dependency](./xrepo/direction.md).
