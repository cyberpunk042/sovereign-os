# sovereign-os

> **Status:** Stage-2 onset, substantively built out.
> The **OS-image generation + customization pipeline** for the SAIN-01
> AI Workstation and 4 other profiles. Foundation phase complete
> (every PR-1 question closed/partial); Stage-2+ rounds have landed
> substantive build pipeline + lifecycle hooks + operator surfaces.
> Real builds are operator-driven on real hardware; CI gates all
> non-destructive paths at Layer 3.

## What ships today

- **23 SDDs** (`docs/sdd/000-022`) covering charter, substrate (mkosi
  primary; live-build ALT-A), profile schema (single-parent + mixins),
  whitelabel mechanism (7-strategy taxonomy + legal-floor preservation),
  secure-boot posture (none/shim/signed), ZFS root layout,
  reproducibility target, kernel-choice, disk encryption, CI
  infrastructure, distro-base lock-in.
- **5 profiles × 6 mixins**: `sain-01` (default AI workstation),
  `old-workstation` (constrained), `minimal` (VM baseline),
  `developer` (polyglot toolchain), `headless` (bare-metal server).
- **9-step build pipeline** (`scripts/build/orchestrate.sh`):
  bootstrap-forge → kernel-fetch → kernel-config → kernel-compile →
  substrate-prepare → whitelabel-render → image-build → image-sign →
  image-verify. Every step honors `--dry-run` + emits Layer B
  Prometheus metrics. `preflight`/`status`/`reset`/`rewind`/`skip`/
  `list`/`help` verbs operational.
- **5 lifecycle stages** with substantive hooks:
  pre-install (4 preflight) · during-install (4 setup) · post-install
  (8 first-boot) · recurrent (6 timer-driven) · decommission (3 gated).
- **Operator management CLI** (`sovereign-osctl`): 15 top-level
  command groups. `status`/`doctor`/`assistant` overview; `audit` (5
  subverbs incl. `provenance --deep` + `drift`); `inference` (7
  subverbs incl. `health` + `route`); `metrics`/`alerts`/`journal`/
  `history` (Layer-A/B observability surface); `maintenance` (8 on-
  demand subverbs incl. `alerts-check`); plus profiles/whitelabel/
  models/perimeter/decommission. SDD-025 codifies the observability
  CLI architecture.
- **5-layer test pyramid** in CI: ~25 schema + ~70 unit (incl. 2 L2
  JSON-schema contract gates for SDD-023 alerts + SDD-025 audit drift)
  + ~55 Layer-3 nspawn + 11 Layer-1 lint suites + shellcheck. L1/L2/L3
  combined catch real wiring bugs — running tally at **15 bugs
  caught** (see `docs/src/tdd/bugs-caught.md`).
- **Reproducibility chain end-to-end**:
  pin SOURCE_DATE_EPOCH + DEBIAN_SNAPSHOT + KERNEL_TAG → reproducible
  build → in-toto SLSA v1 build-provenance.json + sha256sums.txt →
  operator-side `sovereign-osctl audit provenance` verification.
- **Operator-owned signing chain**: SDD-015 3-level posture
  (`none`/`shim`/`signed`); Platform Key preferred for production;
  MOK fallback; preflight-tpm gates TPM2 readiness.
- **Disk encryption** (SDD-022): ZFS native for zfs-tiered profiles;
  LUKS2 for ext4; passphrase + TPM2 PCR-7+11 default for sain-01 +
  headless.
- **Observability (Layer A/B/C, SDD-016 + SDD-023 + SDD-025)**: 55
  metric names emitted across build pipeline + 24 lifecycle hooks +
  inference router; 3 Grafana JSON dashboard templates
  (`docs/observability/dashboards/`). In-tree 6-rule alerts engine
  + hourly meta-observability hook — operators get rule-derived
  alerts WITHOUT Alertmanager/Prometheus/SaaS. CI gates the three-way
  contract: code ↔ dashboard panels ↔ README inventory.
- **Hardening IaC (SDD-024)**: 5 server drop-ins + 4 workstation
  drop-ins (auditd ruleset · fail2ban jails · unattended-upgrades ·
  sshd · pwquality) with load-bearing invariants pinned at L1 lint
  (silent weakening fails CI); operator override via lexicographically-
  later drop-ins; `audit drift` verb detects deployed-vs-source drift.
- **Operator-side gates**: `scripts/onboard.sh` one-command fresh-machine
  onboarding (setup → init wizard → preflight; R138); `scripts/setup.sh`
  dev-env validation; `scripts/git-hooks/pre-commit` runs L1 lint +
  profile validation + L3 fast sample before every commit;
  `sovereign-osctl init` standalone wizard (R136); `sovereign-osctl env
  list` discovers 80+ env vars (R137); `sovereign-osctl install image
  --plan` 6-gate safety check for the disk dump (R134);
  `scripts/build/orchestrate.sh recover` diagnoses + suggests
  mid-pipeline failure recovery (R135).

## Quick start

```sh
# Discover all operator verbs (canonical entry point)
make help

# Fresh clone bootstrap (git hooks + deps + smoke test)
make setup

# Run the local equivalent of CI (lint + unit + L3 fast subset)
make test

# Validate the build plan without running anything
make dry-run                 # or: SOVEREIGN_OS_PROFILE=sain-01 scripts/build/orchestrate.sh run --dry-run

# Run pre-install gates against the active profile
scripts/build/orchestrate.sh preflight

# Real build (operator-only — needs root + build toolchain)
SOURCE_DATE_EPOCH=$(date +%s) \
DEBIAN_SNAPSHOT=20260515T000000Z \
SOVEREIGN_OS_PROFILE=sain-01 \
SOVEREIGN_OS_PK_KEY=/path/PK.priv SOVEREIGN_OS_PK_CERT=/path/PK.der \
  sudo scripts/build/orchestrate.sh run

# Verify the build is reproducible after it lands
sovereign-osctl audit provenance build/sain-01/output/build-provenance.json
```

## Documentation

- `docs/src/install-runbook.md` — end-to-end runbook (all 5 profiles)
- `docs/src/ops/manage.md` — `sovereign-osctl` operator handbook
- `docs/src/tdd/bugs-caught.md` — L3 catch ledger + 3 distilled
  cross-bug Learnings
- `docs/handoff/002-foundation-substantive-buildout.md` — chronological
  trajectory (cold-start signpost for next session)
- `docs/observability/dashboards/README.md` — Grafana template
  import + metric inventory

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
