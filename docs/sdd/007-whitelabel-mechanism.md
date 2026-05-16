# SDD-007 — Whitelabel mechanism (Stage Gate 4: closes Q-004 legal scope)

> Status: **review** (mechanism specification; locks at Stage Gate 4)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none
> Resolves at Gate 4: **Q-004** (legal scope of whitelabel — public-distributable vs internal-only)
> Derived from: SDD-006 surface audit (the catalog this mechanism rebrands); SDD-004 profile schema (`whitelabel:` binding key); Plan-agent macro-arc § PR 8; charter (sovereignty + Debian-as-Ark)

## Problem

SDD-006 catalogs ~50 Debian identity surfaces. The schema (SDD-004)
reserves a `whitelabel:` binding key in every profile. **The
mechanism that translates whitelabel binding + surface catalog into
actual on-disk changes** is what this SDD specifies.

Mechanism requirements:
1. **Declarative** — whitelabel definitions live in
   `whitelabel/<name>.yaml`; build pipeline reads them; no
   imperative scripts authored per-whitelabel.
2. **Per-surface strategy** — each surface has a documented
   rebranding approach (template-substitution / file-overlay /
   package-replacement / build-time-flag). The strategy is chosen
   by surface-class, not per-whitelabel.
3. **Pre / during / post split** — surfaces get rebranded at
   different lifecycle stages depending on the strategy. Some are
   pre-build patches; some are install-time substitutions; some are
   first-boot scripts.
4. **Evolvability** — whitelabel can be swapped post-install without
   re-building the entire image (where possible — some surfaces
   like kernel `/proc/version` are compile-time and require rebuild).
5. **Legal-floor binding** — the must-not-touch list from SDD-006 is
   enforced **at validation time**. A whitelabel that attempts to
   override a must-not-touch surface fails the build.
6. **Substrate-agnostic** — mechanism doesn't bake in mkosi / live-
   build / rpm-ostree. Each substrate has an adapter that consumes
   the same whitelabel YAML.

## Mechanism shape (overview)

```
┌─────────────────────┐    ┌──────────────────────┐
│ profiles/sain-01    │    │ whitelabel/default   │
│ .yaml               │───▶│ .yaml                │
│                     │    │                      │
│ whitelabel:         │    │ branding:            │
│   profile: default  │    │   name: "Sovereign…" │
│   surfaces: [all]   │    │   ...                │
│   legal_compliance: │    │ surfaces:            │
│     dfsg-only       │    │   /etc/os-release:   │
└─────────────────────┘    │     strategy: subst… │
                           │     content: ...     │
                           │   /etc/issue:        │
                           │     strategy: ...    │
                           │   ...                │
                           └──────────┬───────────┘
                                      │
                           ┌──────────▼───────────┐
                           │ whitelabel-render    │
                           │ engine               │
                           │ (lib + substrate-    │
                           │  adapter layer)      │
                           └──────────┬───────────┘
                                      │
                  ┌───────────────────┼──────────────────┐
                  ▼                   ▼                   ▼
        ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
        │ pre-build       │ │ during-install  │ │ post-install    │
        │ patches         │ │ substitutions   │ │ scripts         │
        │ (file overlays  │ │ (dpkg-divert    │ │ (first-boot     │
        │  in mkosi.skel/ │ │  + sed +        │ │  hooks; runtime │
        │  or includes/)  │ │  template render│ │  re-rebrand)    │
        └─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Per-surface strategy matrix

The 4 mechanism strategies, when each is used, and which surfaces
they apply to:

### Strategy 1 — **template-substitution** (build-time)

Variable expansion in a template file at build time. Best for simple
identity strings.

**Used for**:
- `/etc/os-release` (every field gets `${BRAND_*}` variable expansion)
- `/usr/lib/os-release`
- `/etc/issue`
- `/etc/issue.net`
- `/etc/lsb-release`
- `/etc/motd`
- `/etc/default/grub` `GRUB_DISTRIBUTOR=`
- `/etc/dpkg/origins/sovereign` (must-create)

**Mechanism**:
- Template files live in `whitelabel/<name>/templates/<path>.tmpl`.
- Build engine renders templates with the `branding:` block from the
  whitelabel YAML.
- Output placed at the destination path in the build chroot.

**Pre/during/post**: pre-build patch.

### Strategy 2 — **file-overlay** (build-time)

Bit-for-bit file replacement at build time. Best for non-text assets
(themes, splashes, wallpapers, logos).

**Used for**:
- Plymouth theme directory (`/usr/share/plymouth/themes/sovereign/`)
- GRUB theme directory (`/boot/grub/themes/sovereign/`)
- Desktop wallpapers (`/usr/share/backgrounds/sovereign-os/`)
- GNOME / KDE / SDDM / GDM theme assets (if DE is in profile)
- Kernel boot logo PPM (`drivers/video/logo/logo_sovereign_clut224.ppm`
  — special case; lives in the kernel source tree, not chroot)
- `/etc/dpkg/origins/sovereign` data file (overlay of the must-create
  entry; complement to strategy 1's template if dynamic data needed)

**Mechanism**:
- Assets live in `whitelabel/<name>/overlays/<path>`.
- Build engine copies overlay tree onto the chroot tree at the path
  semantics it expects (mkosi.extra, live-build includes.chroot,
  treefile.yaml overlay, etc. — substrate-adapted).

**Pre/during/post**: pre-build patch.

### Strategy 3 — **package-replacement** (build-time, alternatives)

When a Debian package owns the surface (e.g., `desktop-base` for
default wallpapers, `plymouth-themes-spinner-debian` for the spinner
theme), replace the package or use `update-alternatives` /
`dpkg-divert` to point at sovereign-os equivalents.

**Used for**:
- `desktop-base` package (Debian-branded SVG/PNG assets) → replace
  with `sovereign-os-desktop-base` package
- Plymouth theme alternative
  (`update-alternatives --set default.plymouth /usr/share/plymouth/themes/sovereign/sovereign.plymouth`)
- GRUB theme `GRUB_THEME=` variable pointing at sovereign-os theme
- Calamares branding (`calamares/branding/sovereign/` overrides default)

**Mechanism**:
- Whitelabel YAML's `surfaces:` block declares the surface as
  `strategy: package-replacement`.
- A sovereign-os-side debian package (e.g., `sovereign-os-desktop-base.deb`)
  is built once + installed via the profile's `packages.profile:` list.
- Where the upstream package isn't replaceable cleanly, use
  `dpkg-divert` to redirect specific files to the overlay.

**Pre/during/post**: build-time (package install).

### Strategy 4 — **build-time-flag** (compile-time)

Variables that flow into the kernel/initramfs/etc. compile process.

**Used for**:
- Kernel `CONFIG_LOCALVERSION` (already `-znver5` for sain-01;
  whitelabel-compatible)
- Kernel `KBUILD_BUILD_USER` (set to `sovereign-os` at compile time)
- Kernel `KBUILD_BUILD_HOST` (set to `sovereign-os` at compile time)
- Kernel boot logo (`CONFIG_LOGO_LINUX_CLUT224=y` + replacement PPM
  in source tree)

**Mechanism**:
- Whitelabel YAML's `compile_time:` block contains env-var-name → value
  pairs.
- Profile schema's `kernel.compile_flags:` block (already SDD-004)
  feeds into this.
- The kernel build step exports these env vars before invoking
  `make`.

**Pre/during/post**: pre-build (kernel compile happens earliest).

### Strategy 5 — **install-time-substitution** (during-install)

Substitutions that happen during the installer rather than at image
build. Used when the value isn't knowable until install time
(hostname pattern; user-chosen brand if a customisation step exists).

**Used for**:
- Default hostname pattern in debian-installer preseed
- Installer-displayed banners (`Welcome to <name>`)
- `/etc/sovereign-version` if it ships with install-time-generated
  data (Q7-C)

**Mechanism**:
- Whitelabel YAML's `install_time:` block declares the surface +
  the variable derivation.
- During-install hook reads the active whitelabel YAML and emits
  the surface.

**Pre/during/post**: during-install.

### Strategy 6 — **first-boot-script** (post-install)

Substitutions that happen on the live system at first boot. Used for
surfaces that need run-time data (e.g., MAC-based hostname, machine
serial, etc.).

**Used for**:
- Dynamic motd content reflecting system state at first boot
- /var/lib/sovereign-os/install-fingerprint
- Per-machine identity surfaces

**Mechanism**:
- Whitelabel YAML's `first_boot:` block lists scripts/templates to
  render at first boot.
- Profile's `hooks.post_install_first_boot:` already covers this;
  whitelabel-driven hooks merge into the profile's list.

**Pre/during/post**: post-install (first-boot).

### Strategy 7 — **must-not-touch** (legal floor — validation only)

Surfaces from SDD-006's legal-floor list that the mechanism MUST
refuse to override.

**Used for**:
- `/etc/debian_version`
- `/usr/share/doc/*/copyright` (any path matching)
- Upstream manpages
- Debian trademark assets (logo / swirl SVG / PNG)
- GPL/AGPL attribution chains

**Mechanism**:
- Whitelabel YAML cannot declare a `surfaces:` entry for any
  must-not-touch path. The schema validator rejects them.
- Hard-list of forbidden paths is in the validator (sourced from
  SDD-006 § "must-not-touch" section).

**Pre/during/post**: validation (build fails if violated).

## Whitelabel YAML structure (declarative spec)

```yaml
# yaml-language-server: $schema=../schemas/whitelabel.schema.yaml
schema_version: "1.0.0"

identity:
  id: sovereign-default
  name: "Sovereign OS Default Whitelabel"
  version: "0.1.0"
  status: draft
  maintainer: cyberpunk042
  description: |
    Placeholder default whitelabel pending Q-003 brand-identity
    commit. Provides a structurally-complete rebrand using neutral
    placeholder strings; operator commits actual brand identity
    (name, palette, logo) at a future PR.

# Branding variables — consumed by template-substitution strategy
branding:
  os_id: sovereign
  os_name: "Sovereign OS"
  os_pretty_name: "Sovereign OS v0.1 (Foundation Phase)"
  os_version: "0.1"
  os_codename: "trinity"             # placeholder; operator picks
  vendor: "cyberpunk042"
  home_url: "https://github.com/cyberpunk042/sovereign-os"
  bug_report_url: "https://github.com/cyberpunk042/sovereign-os/issues"
  support_url: "https://github.com/cyberpunk042/sovereign-os/blob/main/README.md"
  documentation_url: "https://cyberpunk042.github.io/sovereign-os/"
  privacy_policy_url: null
  motd: |
    We want quality over quantity and honesty over cheats and lies.
    We do not want hacks, quick fixes, and shortcuts.

# Per-surface declarations — strategy + content
surfaces:

  /etc/os-release:
    strategy: template-substitution
    template: templates/os-release.tmpl
    when: pre-build
    legal_floor: false

  /usr/lib/os-release:
    strategy: template-substitution
    template: templates/os-release.tmpl     # same template
    when: pre-build
    legal_floor: false

  /etc/issue:
    strategy: template-substitution
    content: |
      ${os_pretty_name}

      ${motd}

      \n \l
    when: pre-build
    legal_floor: false

  /etc/issue.net:
    strategy: template-substitution
    content: |
      ${os_pretty_name}
    when: pre-build
    legal_floor: false

  /etc/lsb-release:
    strategy: template-substitution
    content: |
      DISTRIB_ID=${os_id}
      DISTRIB_RELEASE=${os_version}
      DISTRIB_CODENAME=${os_codename}
      DISTRIB_DESCRIPTION="${os_pretty_name}"
    when: pre-build
    legal_floor: false

  /etc/motd:
    strategy: template-substitution
    content: |
      ${motd}
    when: pre-build
    legal_floor: false

  /etc/dpkg/origins/sovereign:
    strategy: template-substitution
    content: |
      Vendor: ${os_name}
      Vendor-URL: ${home_url}
      Bugs: ${bug_report_url}
      Parent: Debian
    when: pre-build
    legal_floor: false

  /etc/default/grub:
    strategy: template-substitution
    operation: line-replace
    pattern: '^GRUB_DISTRIBUTOR='
    replacement: 'GRUB_DISTRIBUTOR="${os_name}"'
    when: pre-build
    legal_floor: false

  /usr/share/plymouth/themes/sovereign:
    strategy: file-overlay
    overlay: overlays/plymouth-theme/
    when: pre-build
    legal_floor: false

  /boot/grub/themes/sovereign:
    strategy: file-overlay
    overlay: overlays/grub-theme/
    when: pre-build
    legal_floor: false

  desktop-base-replacement:
    strategy: package-replacement
    package: sovereign-os-desktop-base
    diverts:
      - /usr/share/backgrounds/desktop-base/
    when: pre-build
    legal_floor: false

  plymouth-alternative:
    strategy: package-replacement
    alternative: default.plymouth
    points_to: /usr/share/plymouth/themes/sovereign/sovereign.plymouth
    when: pre-build
    legal_floor: false

  kernel-buildflags:
    strategy: build-time-flag
    flags:
      KBUILD_BUILD_USER: ${os_id}
      KBUILD_BUILD_HOST: ${os_id}
      CONFIG_LOCALVERSION: "-znver5"      # profile-conditional; sain-01 only
    when: pre-build
    legal_floor: false

  hostname-default:
    strategy: install-time-substitution
    operation: preseed
    key: "d-i netcfg/get_hostname"
    value: "${os_id}"
    when: during-install
    legal_floor: false

  installer-banner:
    strategy: install-time-substitution
    operation: template-substitute
    target: installer/welcome.txt
    template: templates/installer-welcome.tmpl
    when: during-install
    legal_floor: false

  first-boot-greeting:
    strategy: first-boot-script
    script: scripts/whitelabel/first-boot-greeting.sh
    when: post-install
    legal_floor: false

# Legal-floor declarations (informational; enforced by validator)
legal_floor:
  preserved:
    - /etc/debian_version           # provenance
    - "/usr/share/doc/*/copyright"  # license attribution
    - "/usr/share/man/*"            # upstream manpages
    - "*/debian-logo*"              # trademark assets
  rationale: |
    Debian trademark policy + DFSG + GPL/AGPL attribution require
    these surfaces remain untouched. See SDD-006 § "Legal floor".
```

## Evolvability — swap-without-rebuild

Goal: a sovereign-os deployment can swap whitelabels (e.g., default →
ProductX-branded) on a running system without re-building the OS
image, **where the strategy permits**.

| Strategy | Swap-without-rebuild? | Mechanism |
|---|---|---|
| template-substitution | **Yes** (most cases) | Lifecycle tool re-renders templates; touches `/etc/*` files; no service restart unless surface is read by a daemon |
| file-overlay | **Yes** (asset replacement) | Lifecycle tool copies new overlay over old |
| package-replacement | **Partial** | New whitelabel package installs; `update-alternatives` switches |
| build-time-flag | **No** | Kernel/initramfs/etc. compiled-in; requires rebuild |
| install-time-substitution | **No** (already installed) | Same; install-time-only |
| first-boot-script | **No** (first-boot is once) | Re-runnable as a maintenance hook if needed |

The lifecycle-management surface (Q-019) integrates whitelabel
swapping as one of its operations: `sovereign-osctl whitelabel apply
<id>` (or analogue per Q-019 decision). Re-rendering happens via the
mechanism's runtime mode.

## Legal-compliance binding (Q-004 resolution)

The mechanism enforces Q-004 via a `legal_compliance:` declaration
on the **profile-side** (already in profile schema) AND a
`compliance_target:` on the **whitelabel-side**:

| Profile `legal_compliance:` | Whitelabel `compliance_target:` | Effect |
|---|---|---|
| `dfsg-only` | (any) | Legal floor enforced strictly; must-not-touch list inviolable |
| `trademark-cleared` | `trademark-cleared` | Operator asserts brand identity has trademark clearance; LICENSE-DEBIAN-HERITAGE.md ships |
| `internal-only` | `internal-only` | Personal sovereign workstation; lower bar; NOT redistributable |

The validator rejects mismatches (e.g., profile `dfsg-only` + whitelabel
`internal-only` → error; pick one path consistently).

## Mechanism implementation (lib + substrate adapter)

The mechanism has two layers:

### Layer 1 — Render engine (substrate-agnostic library)

`lib/whitelabel-render/` (Stage 2+; not in this PR's scope) — a
Python or Go library that:

1. Loads `whitelabel/<id>.yaml`.
2. Resolves `branding:` variable expansions in templates.
3. Validates `surfaces:` declarations against schema + legal-floor.
4. Emits a list of file-tree-changes (path → strategy → content)
   organized by lifecycle phase (pre-build / during-install /
   post-install).

This layer is substrate-agnostic — output is a generic file-tree-changeset.

### Layer 2 — Substrate adapter

Each substrate has an adapter that consumes the changeset:

- **mkosi adapter** — populates `mkosi.skeleton/` + `mkosi.extra/`
  with the changeset; runs `mkosi build`.
- **live-build adapter** — populates `config/includes.chroot/` with
  the changeset; runs `lb build`.
- **rpm-ostree adapter** — emits commits via `ostree commit`;
  composes with treefile.
- **NixOS adapter** — translates changeset into a `.nix` overlay.

Adapter selection happens via the Gate 2 substrate decision (Q-001).
Each adapter is < 500 LOC; Stage 2+.

## Goals

1. **Declarative whitelabel YAML** — one file fully specifies a
   whitelabel.
2. **Substrate-agnostic** — the YAML doesn't know which substrate
   consumes it.
3. **Per-surface strategy** — each surface picks the right strategy
   from the 7-strategy taxonomy.
4. **Legal-floor enforced** — must-not-touch list rejected at
   validation; cannot be overridden by mis-authored whitelabels.
5. **Swappable post-install** (where physical mechanism allows) —
   lifecycle tool can re-apply.
6. **Forward-compatible** — additional surfaces / strategies can be
   added without breaking existing whitelabels.
7. **Multi-whitelabel** — multiple whitelabel definitions can coexist
   (`whitelabel/default.yaml`, `whitelabel/internal.yaml`,
   `whitelabel/productX.yaml`); profile binds one.

## Non-goals (this SDD)

- Does NOT author the render engine library. Stage 2+.
- Does NOT author substrate adapters. Stage 2+ (per substrate
  decision).
- Does NOT pick a real brand identity. Q-003 deferred.
- Does NOT lock the schema for the substrate-specific YAML's they emit.
- Does NOT author template/overlay content (templates/, overlays/);
  the structure is reserved.
- Does NOT decide between Layer 1 implementation language (Python vs
  Go vs Rust); Stage 2+ picks.

## Open sub-questions

- **Q8-A** — Render engine implementation language (Python /
  Go / Rust)? Recommend Python for development velocity (small lib,
  no perf concern; selfdef is Rust, but this is build-time tooling
  not runtime).
- **Q8-B** — `dpkg-divert` everywhere vs only-where-needed? Recommend
  divert every must-rebrand file owned by a Debian package, so
  package updates don't silently restore Debian-branded content.
- **Q8-C** — Whitelabel CI gate: build sovereign-os image with the
  whitelabel applied + verify by booting in QEMU + greping
  `/etc/os-release` for sovereign-os strings? Strongly recommend at
  PR 10 TDD harness.
- **Q8-D** — When the lifecycle-management surface (Q-019) ships,
  should `whitelabel apply` be **atomic** (transaction-style — all
  surfaces or none) or **best-effort**? Recommend atomic; rollback
  on partial failure.
- **Q8-E** — Schema-validation timing: validate-on-author (every
  edit) vs validate-on-build (only at build time)? Recommend both;
  pre-commit hook + CI gate.

## Q-004 closure path (at Gate 4)

Operator picks one of:
- **A. Public-distribution whitelabel** (`compliance_target: trademark-cleared`):
  - All must-rebrand rebranded
  - Legal floor inviolable
  - `LICENSE-DEBIAN-HERITAGE.md` ships
  - Public distribution permitted
- **B. Internal-use whitelabel** (`compliance_target: internal-only`):
  - Identity surfaces rebranded for operator cosmetics
  - Less rigor on legal floor (operator-attestation)
  - Personal sovereign workstation only; NOT redistributable

Default profile path: `dfsg-only` (option B's compliance level + a
clear path to upgrade to option A by changing one field).

Closes as `D-NNN` in `docs/decisions.md` after Gate 4 review.

## Way forward

1. **PR 8 (this PR)** — mechanism specification + schema + default
   whitelabel placeholder + INDEX. **Stage Gate 4 fires after merge.**
2. **Gate 4** — operator picks Q-004 legal scope; Q-003 (brand
   identity) may stay open.
3. **PR 9-10** — TDD harness ships `tools/validate-whitelabel` + CI
   gate + image-boot-verification.
4. **Stage 2+** — render engine library + substrate adapters + actual
   templates + overlays + lifecycle-tool integration (Q-019
   `whitelabel apply`).

## Cross-references

- SDD-006 surface audit (the catalog this mechanism rebrands): [`006-debian-surface-audit.md`](006-debian-surface-audit.md)
- SDD-004 profile schema (`whitelabel:` binding key): [`004-profile-schema.md`](004-profile-schema.md)
- SDD-001 cross-repo boundaries: [`001-cross-repo-boundaries.md`](001-cross-repo-boundaries.md)
- Formal schema: [`../../schemas/whitelabel.schema.yaml`](../../schemas/whitelabel.schema.yaml)
- Default whitelabel: [`../../whitelabel/default.yaml`](../../whitelabel/default.yaml)
- Whitelabel index: [`../../whitelabel/INDEX.md`](../../whitelabel/INDEX.md)
- Decisions log: `docs/decisions.md` Q-003 + Q-004 (Q-004 resolves at Gate 4)
- Plan-agent macro-arc § PR 8: info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
- Debian trademark policy: https://www.debian.org/trademark
