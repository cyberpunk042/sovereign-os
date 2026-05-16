# Charter & discipline

> **The canonical charter is at**:
> [`docs/sdd/000-charter.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/sdd/000-charter.md).
> This page summarises for the mdbook.

## Mission (one paragraph)

Produce a custom-built, multi-profile, whitelabel-able Linux OS for the
SAIN-01 AI Workstation (default) + other declared hardware profiles.
Every lifecycle stage specified before built (SDD) and tested before
run (TDD). Sovereign: operator-owned, operator-evolvable, transparent,
no phone-home defaults, offline-first core, operator-pulled updates,
documented provenance for every binary.

## Operator quality bar (verbatim, sacrosanct)

> *"Do not rush anything and do not minimize anything nor should you compress or conflate or hallucinate anything"*
>
> *"We think before we act always. And we do things in order and we respect workflows and methodologies"*
>
> *"Everything being able to evolve, before and after"*
>
> *"I want things observable and operable and customizable, at all stages of lifecycle"*
>
> *"We do this clean and right and professional"*
>
> *"we always deliver IaC, high quality scripts and libs and configuration and easily tweakable and configurable and customisation and even via env vars when needed, or other pre-existing config or temporary file detected and restarting from there"*
>
> *"we remember the SFIF, Skaffold, Fundation, Infrastructure, Features"*
>
> *"I think Debian is a bit like saying we have our Arc but we start from there, kind of thing ?"*
>
> *"reach our ultimate sovereignty"*

## SFIF lifecycle (this arc)

| Tier | PRs | Deliverables |
|---|---|---|
| **Scaffold** | 1–3 | Repo skeleton · charter · ARCHITECTURE.md · cross-repo refs · mdbook · MCP template (this PR closes Scaffold tier; Gate 1 follows) |
| **Foundation** | 4–8 | Substrate survey (Q-001 + Q-016) · profile schema · profile stubs · whitelabel surface audit · whitelabel mechanism. Decisions land here. |
| **Infrastructure** | 9–10 start; Stage 2+ continues | TDD harness (chroot · nspawn · QEMU) · then actual build scripts |
| **Features** | Stage 2+ | Image generation · interactive build · lifecycle management · first-login assistant · model-catalog integration · post-install evolution |

## IaC quality bar (load-bearing)

Every script / lib / config:

- **IaC** — every operational pattern as reproducible tooling.
- **High quality** — shellcheck / ruff / yamllint / sealed deps / drift-guard.
- **Tweakable** — config-file + env-var + CLI-flag, three layers, documented precedence.
- **Restart-from-state** — multi-step builds persist per-step state and resume.
- **Pre-existing config detection** — probe before clobber.
- **Observable** — structured progress logs; exit codes meaningful.
- **Operable** — pause / inspect / resume / rewind / skip-step.

## Debian as Ark

Debian 13 is the **starting boat**, not the destination. Q-016
(distro-base reconsideration) keeps the question honest through PR 4's
substrate survey. Working hypothesis: stay + customize heavily.
