# sovereign-os

> **Status:** foundation phase — no buildable artifact yet.
> This repo is the **OS-image generation + customization pipeline** for
> the SAIN-01 AI Workstation and other profiles. PRs 1–10 land the
> charter, substrate-survey, profile-schema, whitelabel mechanism, and
> hardware-free TDD harness. Build scripts begin in Stage 2 (post-Gate-5).

## What this repo is for

`sovereign-os` BUILDS the OS. It does not RUN on the OS (that's
[`selfdef`](https://github.com/cyberpunk042/selfdef)), and it does not
SYNTHESIZE knowledge about the OS (that's
[`devops-solutions-information-hub`](https://github.com/cyberpunk042/devops-solutions-information-hub)).

The pipeline's job, end-to-end:

1. **Pre-install** — substrate selection (live-build / mkosi / debootstrap
   / ostree / Nix / …), profile schema, whitelabel surface audit,
   compile-time customization (custom Zen-5-tuned kernel, identity
   injection, pre-baked drivers).
2. **During-install** — installer experience (debian-installer derivative
   / Calamares / custom TUI / image-only), profile selection, hardware
   probing, partitioning + ZFS layout, secure-boot enrollment.
3. **Post-install / first-boot** — service activation, GPU driver +
   VFIO binding, network split, Tetragon policy load, ZFS dataset
   stratification, first-login assistant flow.
4. **Ongoing management** — lifecycle tools to operate, observe, evolve
   the installed system (add services, swap profiles, rotate models,
   re-audit perimeter).

All four lifecycle stages are **specified before any script is written**
(SDD), and **tested before they execute on real hardware** (TDD via
chroot / systemd-nspawn / QEMU).

## Operator quality bar (sacrosanct, verbatim)

> "Do not rush anything and do not minimize anything nor should you
> compress or conflate or hallucinate anything"

> "We think before we act always. And we do things in order and we
> respect workflows and methodologies"

> "Everything being able to evolve, before and after"

> "I want things observable and operable and customizable, at all stages
> of lifecycle"

> "We do this clean and right and professional"

> "we always deliver IaC, high quality scripts and libs and configuration
> and easily tweakable and configurable and customisation and even via
> env vars when needed, or other pre-existing config or temporary file
> detected and restarting from there such as if there is has to be a
> local tracking of the progress of a build in multi-steps that can only
> ever re-happen locally"

> "we remember the SFIF, Skaffold, Fundation, Infrastructure, Features"

> "I think Debian is a bit like saying we have our Arc but we start from
> there, kind of thing ?"

Every PR in this repo is reviewed against these.

## The four-repo ecosystem

| Repo | Responsibility |
|---|---|
| **`cyberpunk042/sovereign-os`** (this) | BUILDS the OS — image generation + customization + lifecycle tools |
| [`cyberpunk042/selfdef`](https://github.com/cyberpunk042/selfdef) | RUNS on the OS — security daemon (Tetragon + agent-guard + 12 notifier channels + persistent escalations) |
| [`cyberpunk042/devops-solutions-information-hub`](https://github.com/cyberpunk042/devops-solutions-information-hub) | SYNTHESIZES knowledge — wiki second-brain; SAIN-01 milestone + 11 epics live here |
| `cyberpunk042/root-ghostproxy` | dormant |

## Architectural baseline (do NOT duplicate)

The architectural design is **already locked** in the info-hub and is
not re-derived here. `sovereign-os` references it by citation, not by
duplication.

| Artifact | Location |
|---|---|
| SAIN-01 milestone | info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md` |
| 11 epics (E100–E110) | info-hub `wiki/backlog/epics/milestone-sain01/e1??-*.md` |
| L1 source-synthesis (BitNet · DFlash · Zen 5 · SAIN-01 spec) | info-hub `wiki/sources/src-*.md` |
| L2 concepts (1-bit ternary · spec-dec block-diffusion · SRP Trinity · ZFS tiered · VFIO isolation · dual-CCD) | info-hub `wiki/domains/{ai-models,ai-agents,devops}/concept-*.md` |
| L3 comparisons (4 head-to-heads) | info-hub `wiki/comparisons/cmp-*.md` |
| Operator-directive verbatim (2026-05-16 sovereign-os arc opening) | info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md` |
| Plan-agent macro-arc output (authoritative scaffold for PRs 1–10) | info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` |
| Selfdef-side cross-repo bridge | selfdef `docs/sdd/011-sovereign-os-arc-opening.md` |
| Selfdef-side decision log entry | selfdef `docs/decisions.md` D-026 |
| Selfdef-side cold-start handoff | selfdef `docs/handoff/2026-05-16-sovereign-os-arc-opening.md` |

## Repo conventions (mirrors selfdef rhythm)

| Path | Purpose |
|---|---|
| `docs/sdd/NNN-*.md` | Software Design Documents — three-digit zero-padded, never recycled. `000-charter.md` is the project charter. |
| `docs/decisions.md` | Append-only chronological audit trail. Each `D-NNN` entry resolves a `Q-X` from an SDD or other source. |
| `docs/handoff/YYYY-MM-DD-*.md` | Dated session-handoff anchors. Each is a cold-start signpost for the next session. |
| `docs/review/phase-N/` | Audit phase ledgers. |
| `docs/sdd/INDEX.md`, `docs/handoff/INDEX.md`, `docs/review/INDEX.md` | Index tables for each doc series. |
| `profiles/<name>.yaml` | Schema-conformant OS profiles (default = `sain-01`; alternate = `old-workstation`; future: `minimal`, `developer`, `headless`). |
| `whitelabel/<name>.yaml` | Brand identity declarations. |
| `schemas/*.schema.yaml` | Formal schemas (profile, whitelabel, lifecycle hooks). |
| `scripts/` | Build / install / post-install / lifecycle scripts (IaC discipline; resumable; env-var-driven). |
| `tests/` | TDD harness: `schema/` · `lint/` · `chroot/` · `nspawn/` · `qemu/` · `hardware/`. |

## Default profile

The first-class profile is **`sain-01`** — the AMD Ryzen 9 9900X + RTX
PRO 6000 Blackwell + RTX 3090 + 256 GB DDR5 + dual PCIe 5 NVMe ZFS
RAID 0 AI workstation specified in the info-hub's SAIN-01 milestone.
An `old-workstation` profile (11 GB RAM + 8 GB GPU) is the second
profile from day 1, declared schema-conformant even before it has a
substantive body.

## SFIF lifecycle (applies to this arc)

Every PR in this repo is tagged against the operator's SFIF discipline:

| Tier | PR range | What lands |
|---|---|---|
| **Scaffold** | PRs 1–3 | Charter · ARCHITECTURE · mdbook + MCP template |
| **Foundation** | PRs 4–8 | Substrate survey · profile schema · profile stubs · whitelabel audit · whitelabel mechanism |
| **Infrastructure** | PRs 9–10 (start) + Stage 2+ | TDD harness scaffold; then actual build scripts |
| **Features** | Stage 2+ | Image generation · interactive build modes · lifecycle management · model catalog integration · first-login assistant |

Each tier has a stage gate (explicit operator review checkpoint) before
the next tier opens. No code-bearing PR opens past a gate without
operator sign-off.

## License

AGPL-3.0-or-later. See [`LICENSE`](LICENSE).

## Where to start reading

1. [`docs/sdd/000-charter.md`](docs/sdd/000-charter.md) — the project charter.
2. [`docs/decisions.md`](docs/decisions.md) — locked decisions + open
   questions Q-001..Q-019.
3. [`docs/sdd/INDEX.md`](docs/sdd/INDEX.md) — SDD numbering table.
4. info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` —
   the authoritative 10-PR foundation-phase scaffold.
