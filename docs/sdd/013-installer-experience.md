# SDD-013 — Installer experience (Q-008 resolution)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-008 (installer experience decision)
> Derived from: SDD-003 (substrate survey — mkosi primary), SDD-005
> (initial profiles), `config/cloud-init/` + `config/preseed/` existing
> configs.

## Problem

Q-008 ("Installer experience: debian-installer · Calamares · custom
TUI · image-only") has been open since PR 1 and must resolve before
the operator can install onto SAIN-01 hardware.

Four candidates were enumerated. This SDD picks one + rationalizes the
choice + specifies what ships.

## Decision: **image-only with cloud-init/preseed pre-supplied answers**

`sovereign-os` ships **bootable disk images** built by `mkosi` (per
SDD-003) and reads pre-supplied answers from **cloud-init** (NoCloud
datasource) and/or **debian-installer preseed** (for variant install
paths that go through d-i instead of image-direct).

**No interactive installer UI** (no debian-installer Q&A, no Calamares,
no custom TUI). The first-boot assistant (`scripts/hooks/post-install/
first-login-assistant.sh`) covers post-install operator interaction.

## Rationale

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **image-only (CHOSEN)** | reproducible · no installer code surface · fast install (dd / write disk + boot) · operator can pre-configure via cloud-init · matches operator's IaC bar | requires good defaults · NoCloud media must be prepared | **picked** — aligns with sovereignty + reproducibility |
| debian-installer | familiar · supports complex partitioning · preseed-aware | wide attack surface · slow · ugly UI · adds a dependency on the installer's pace | not picked — too much surface for a sovereign image |
| Calamares | pretty · feature-complete | Qt5 GUI dep · pulls in too much for headless | not picked — wrong shape for sain-01 |
| custom TUI | minimal · operator-controlled | duplicates work · maintenance burden · we'd be inventing an installer | not picked — wrong investment |

The image-only choice locks in **sovereignty by reducing the installer
surface to "boot, run cloud-init, hand off to first-login-assistant"**.

## Shape of "image-only"

1. **Build**: `scripts/build/orchestrate.sh run --profile <id>` produces
   `mkosi.<id>.raw` (or `.iso` for the live-build alternate substrate).
2. **Write to target**: operator uses `dd` / Rufus / Etcher / gnome-disks
   to write the image to the target disk or USB stick.
3. **Pre-supplied answers**: operator drops `user-data` + `meta-data`
   on a NoCloud-labeled vfat USB stick (or partition) — cloud-init
   picks them up on first boot.
4. **First-boot**: kernel + initramfs from the image; cloud-init
   applies hostname / users / SSH keys / packages; the
   `sovereign-firstboot.target` runs post-install hooks
   (friction-audit, vfio-bind, tetragon, ZFS arc clamp, etc.).
5. **First-login**: `first-login-assistant.sh` handles the interactive
   bits cloud-init didn't pre-supply.

## What ships (already on main)

| Artifact | Path | Purpose |
|---|---|---|
| cloud-init for SAIN-01 | `config/cloud-init/sain-01.user-data.example.yaml` | full operator-customizable example |
| cloud-init for old-workstation | `config/cloud-init/old-workstation.user-data.example.yaml` | constrained variant |
| cloud-init for minimal | `config/cloud-init/minimal.user-data.example.yaml` | VM/headless variant (lands with this SDD) |
| preseed for SAIN-01 | `config/preseed/sain-01.preseed.example.cfg` | d-i fallback path (operator-optional) |
| cloud-init README | `config/cloud-init/README.md` | NoCloud datasource + how to attach |
| first-login assistant | `scripts/hooks/post-install/first-login-assistant.sh` | post-install operator interaction |
| install runbook | `docs/src/install-runbook.md` | end-to-end install walkthrough |

## What does NOT ship

- A debian-installer derivative (no d-i kernel + initrd customization).
- A Calamares Qt5 installer.
- A custom TUI installer.
- A network installer (operator must have local boot media).

## Layer-3 test gate

`tests/nspawn/test_install_configs.sh` (added with this SDD) validates:
1. Every `config/cloud-init/<profile>.user-data.example.yaml` parses
   as valid YAML.
2. Every cloud-init file begins with `#cloud-config` header (required
   by cloud-init to be recognized).
3. The hostname referenced in each cloud-init file matches the
   corresponding profile id (sain-01 cloud-init declares hostname:
   sain-01, etc.).
4. Each cloud-init file declares an `operator` user with SSH key path.
5. preseed files have valid `d-i ...` directives (syntactic, not
   semantic — we don't run d-i).
6. Every profile in `profiles/*.yaml` has a corresponding cloud-init
   example file (lockstep coverage).

## Goals

1. **No installer-UI maintenance burden** — image-only ships a smaller
   trusted base.
2. **Pre-configurable** — operator drops cloud-init/preseed on media,
   first boot reads + applies.
3. **Reproducible** — image bits + answer file = deterministic outcome.
4. **Sovereignty** — no install-time phone-home, no third-party UI
   surface, no network dep for first boot.
5. **Operator-overridable** — operator who DOES want d-i can boot a
   debian live ISO + use the preseed file instead.

## Non-goals (this SDD)

- Does NOT mandate cloud-init for every install — preseed is a
  parallel path for d-i users.
- Does NOT prescribe a UI for editing cloud-init pre-install — operator
  uses a text editor.
- Does NOT integrate with proprietary management consoles.

## Cross-references

- SDD-003 (substrate — mkosi primary)
- SDD-005 (initial profiles)
- `config/cloud-init/README.md`
- `docs/src/install-runbook.md`
- `tests/nspawn/test_install_configs.sh` (the gate)
