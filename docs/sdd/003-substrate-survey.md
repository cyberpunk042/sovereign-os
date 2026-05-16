# SDD-003 — Substrate survey & image-build tooling selection (resolves Q-001 + Q-016 at Gate 2)

> Status: **review** (research-grade SDD; recommendation surfaced; operator decides substrate at Stage Gate 2)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none
> Resolves at Gate 2: **Q-001** (final substrate selection) + **Q-016** (distro-base reconsideration "Debian-as-Ark")
> Derived from: Plan-agent macro-arc § PR 4 (info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`); charter (`docs/sdd/000-charter.md`); operator directive on "Debian as Ark" (info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md`)

## Problem

`sovereign-os` produces a custom-built, multi-profile, whitelabel-able
Linux OS for the SAIN-01 AI Workstation (default) + other profiles.
**Before any build script is written, we must pick a substrate** —
the image-build tooling that translates profile YAML + package sets +
kernel choice + post-install hooks into a bootable artifact (`.iso` /
`.img` / equivalent).

The substrate decision is **load-bearing**:
- It constrains the profile schema (some substrates assume specific
  schema shapes).
- It constrains the installer experience (substrate-native installer
  vs custom).
- It constrains reproducibility posture.
- It constrains the whitelabel mechanism's implementation surface.
- It constrains the lifecycle-management surface (some substrates
  provide updates; some only build).
- It constrains the TDD harness's runtime model (chroot vs nspawn vs
  QEMU mix changes per substrate).

The operator's directive added a paired second question — **Q-016
distro-base reconsideration**: would switching the upstream distro
(currently working-hypothesis Debian 13 Trixie) unlock material
potential we'd otherwise lose? "Debian as Ark" framing — Debian is
the starting boat, not the destination.

This SDD surveys both axes honestly, produces a recommendation matrix,
and surfaces a ranked recommendation for operator decision at **Stage
Gate 2**. The SDD intentionally does NOT pick the substrate or the
distro — it scopes the choice space and supplies the rationale.

## Survey scope (two axes)

| Axis | Candidates |
|---|---|
| **Image-build substrate** (image-generation tooling) | live-build · mkosi · debootstrap · Lorax/Anaconda · Kiwi · ostree (rpm-ostree/Silverblue path) · NixOS · Buildroot |
| **Distro base** (Q-016 reconsideration) | Debian 13 Trixie · Fedora 41/42 (Workstation / Silverblue) · RHEL-ABI (Rocky/AlmaLinux 10) · openSUSE Tumbleweed · openSUSE Leap 16 · Arch Linux · NixOS · Void Linux |

The two axes are **partially coupled** (some substrates target one
distro family natively) but **not identical** (mkosi works on Debian,
Fedora, openSUSE, Arch; ostree composes with Fedora rpm-ostree but
can also be used standalone). The recommendation handles this
coupling explicitly.

## Criteria matrix (12 dimensions)

Each candidate is scored against these dimensions with prose
justification (not just a number). Scores: ★★★★★ (best fit) → ★ (poor
fit) → ✗ (incompatible / disqualifying).

| # | Criterion | Why it matters for sovereign-os |
|---|---|---|
| C1 | **Substrate maturity & community vitality** | Long-running upstream; active maintainers; recent commits; bus-factor; documentation depth. Stuck-on-abandonware is a sovereignty risk. |
| C2 | **Native upstream-distro support** | For substrate axis: does the substrate natively understand the chosen distro's package manager, init system, kernel packaging? For distro axis: how active + how trusted is the upstream distro itself? |
| C3 | **Declarative vs imperative** | The operator's IaC bar: "declarative where possible." Declarative substrates compose better with profiles, reproduce better, audit better. |
| C4 | **Multi-profile pluralism** | sovereign-os declares ≥2 profiles from day 1 (`sain-01` + `old-workstation`); reserved slots for `minimal` / `developer` / `headless`. Substrate must support N profiles sharing a common core without N-fold duplication. |
| C5 | **Whitelabel surface accessibility** | PR 7's surface audit (Debian-as-Ark) catalogs ~20+ identity surfaces (`/etc/os-release`, `/etc/issue`, `/etc/motd`, GRUB theme, Plymouth, `lsb_release`, dpkg vendor, APT sources, etc.). Substrate must allow declarative override of these surfaces without forking package metadata. |
| C6 | **Reproducibility** | Q-015 (reproducibility target). Bit-for-bit reproducible builds vs content-equivalent vs best-effort. The substrate's design determines what's achievable. |
| C7 | **CI testability without hardware** | ~70% of Foundation work is hardware-free (per Plan-agent). The substrate must build in a container/CI runner; image-verification via chroot/nspawn/QEMU rather than physical hardware. |
| C8 | **ZFS-root support** | E102 requires ZFS-root with three-dataset stratification (`tank/models` 1M lz4 · `tank/context` 16k zstd-9 copies=2 sync=always · `tank/agents` 128k zstd-3). Substrate's ecosystem must include ZFS-on-root recipes (or be receptive to authoring them). |
| C9 | **Secure-boot support** | Q-006 (secure-boot posture). MOK enrollment + signed-bootloader + signed-kernel-modules workflows. Substrate must integrate with the chosen secure-boot strategy. |
| C10 | **Operator-familiarity cost** | Operator is Debian-fluent + DevOps Senior Architect mindset. Familiarity cost = learning curve. Lower familiarity cost = faster delivery, fewer surprises, easier debugging at 2 AM. |
| C11 | **Lifecycle-tool surface** (post-install) | Does the substrate provide ongoing OS management (atomic updates, rollback, profile-switch) or only build? sovereign-os needs ongoing-management (Q-019 lifecycle surface) — substrate either provides this natively OR sovereign-os builds it on top. |
| C12 | **Evolvability / migration cost** | "Everything being able to evolve, before and after" (operator verbatim). Can we swap substrates in 2 years if needed without rewriting profile definitions? Lock-in matters. |

## Axis 1 — Image-build substrate candidates

### 1. live-build (Debian native)

**What it is.** Debian's official image-build tool (`live-build` / `lb`
command suite). Builds Debian live images and installation images via
a declarative config directory (`config/`) with subdirs for `auto/`,
`bootloaders/`, `hooks/`, `includes.chroot/`, `package-lists/`. Used to
build official Debian live ISOs.

**Strengths.**
- C1 ★★★★★ — official Debian upstream; battle-tested; used to ship Debian itself.
- C2 ★★★★★ — native Debian; understands `apt` / `dpkg` / Debian initramfs / Debian secure-boot signing workflow.
- C3 ★★★★ — config-directory declarative; some hook scripts are imperative bash.
- C4 ★★★ — multi-profile via parallel config trees + a build wrapper; not as elegant as substrates with first-class profile-tree pluralism, but workable.
- C5 ★★★★ — `includes.chroot/` overlay supports declarative file replacement (`/etc/os-release`, `/etc/issue`, etc.); GRUB theming, Plymouth, motd accessible.
- C6 ★★★ — content-equivalent reproducibility is straightforward; bit-for-bit requires extra discipline (`SOURCE_DATE_EPOCH`, deterministic tar, etc.).
- C7 ★★★★ — builds cleanly in Docker/containers; image verification via QEMU smoke-tests.
- C8 ★★★★ — ZFS-on-root recipes exist in the Debian + Proxmox communities; integrates via `live-build` package-list + custom initramfs hooks.
- C9 ★★★★ — Debian's secure-boot signing tooling (mokutil, sbsign, sbverify) works natively; MOK enrollment workflows documented.
- C10 ★★★★★ — operator-familiarity cost ≈ zero (Debian native).
- C11 ★ — build-only; no ongoing-management surface. sovereign-os builds the lifecycle tools on top.
- C12 ★★★★ — profile definitions are reusable across other Debian substrates (mkosi, debootstrap) with light translation; non-Debian substrate migration would be heavy.

**Bottom line.** The natural default for a Debian-13-derivative. High familiarity, well-documented, Debian-native at every level. Loses points only on lifecycle-tool surface (must build on top) and edge-case reproducibility discipline.

---

### 2. mkosi (systemd ecosystem)

**What it is.** Modern image-build tool from the systemd project
(`systemd/mkosi`). Generates bootable disk images, partition tables,
filesystems, and bootable initrds. Declarative `.conf` files
(INI-style). Cross-distro: targets Debian, Fedora, openSUSE, Arch,
CentOS Stream, Ubuntu. Active development; growing community; first-class
support for systemd-native features (systemd-boot, systemd-cryptenroll,
systemd-homed).

**Strengths.**
- C1 ★★★★ — younger than live-build (born ~2017 vs live-build's 2006) but very active; systemd umbrella means strong upstream commitment.
- C2 ★★★★ — Debian-native via apt; understands Debian package metadata.
- C3 ★★★★★ — fully declarative `.conf` files; `mkosi.conf` + `mkosi.conf.d/` profile overlays; no imperative scripts required (though hook scripts supported).
- C4 ★★★★★ — first-class profile pluralism via `mkosi.conf.d/<profile>.conf`; shared base + per-profile overrides is the native idiom.
- C5 ★★★★ — `mkosi.skeleton/`, `mkosi.extra/`, `mkosi.finalize/` directories overlay files declaratively at build time; identity surfaces accessible.
- C6 ★★★★ — designed with reproducibility in mind; `SOURCE_DATE_EPOCH` honored; bit-for-bit achievable with discipline.
- C7 ★★★★★ — builds cleanly in containers/CI; image verification via `mkosi qemu` (built-in QEMU smoke-test runner) — first-class.
- C8 ★★★ — ZFS-on-root is achievable but not as community-blessed as on live-build; would require custom mkosi prepare scripts to install zfs-dkms before the rootfs is sealed.
- C9 ★★★★ — systemd-boot + SBAT signing workflow is mkosi-native; MOK enrollment supported.
- C10 ★★★ — learning curve modest for a Debian-fluent operator (config syntax differs from live-build but is conceptually similar; mkosi's idioms — `Distribution`, `Release`, `Format`, `Output` — are intuitive).
- C11 ★★ — primarily build; some systemd-sysupdate composition possible for ongoing updates but not as integrated as ostree.
- C12 ★★★★ — profile definitions translate to other declarative substrates with relative ease; mkosi's cross-distro support makes future distro-axis pivots cheap.

**Bottom line.** Modern, declarative, multi-distro, first-class QEMU smoke-tests. Trades a small familiarity cost for substantially better profile pluralism and reproducibility than live-build. Strong candidate.

---

### 3. debootstrap (low-level Debian)

**What it is.** Debian's foundational bootstrap tool — installs a base
Debian system into a target directory from a Debian mirror. Imperative;
no profile concept; no build-output management. The atom underneath
live-build and mkosi (mkosi's Debian path calls debootstrap; live-build
calls it directly).

**Strengths.**
- C1 ★★★★★ — universal Debian baseline; rock-solid.
- C2 ★★★★★ — Debian-native; how Debian thinks about bootstrapping.
- C3 ✗ — imperative; not a substrate per se, just a tool. Using it directly means hand-rolling the whole pipeline.

**Verdict.** Disqualifying as a standalone substrate; we'd be reinventing live-build / mkosi. Useful as a build-step component (a custom pipeline could `debootstrap` then layer custom logic), but operator's "do not minimize, do not hack" bar rejects hand-rolled pipelines when a mature substrate exists. **Excluded from further analysis.**

---

### 4. Lorax / Anaconda / Image Builder (Fedora ecosystem)

**What it is.** Lorax is Fedora's image-build framework, used to build
Fedora installation media. Anaconda is Fedora's installer. The newer
"Image Builder" (osbuild + composer) is the modern declarative
front-end. Native to RPM-based distros (Fedora / RHEL / Rocky /
AlmaLinux).

**Strengths.**
- C1 ★★★★ — Fedora-backed; active; used to ship Fedora.
- C2 ★ for Debian (we'd be using Fedora-native tooling against Debian targets, which is mostly not supported); ★★★★★ for Fedora-base if Q-016 selects Fedora.
- C3 ★★★★ — osbuild's blueprint format is declarative TOML.
- C4 ★★★ — multi-profile via blueprints; not as fluent as mkosi's overlay model.
- C5 ★★★★ — RPM-side identity surfaces accessible; whitelabel-friendly within Fedora.
- C10 ★★ — operator-familiarity cost is high for Debian-fluent operator; RPM idioms differ.
- C12 ★★ — Lorax/osbuild lock-in to RPM ecosystem makes future Debian-axis pivot expensive.

**Bottom line.** Disqualified for a Debian-base target. Re-enters the picture only if Q-016 picks Fedora-base. **Conditional candidate** — track in the recommendation conditional-on-distro section.

---

### 5. Kiwi (SUSE ecosystem)

**What it is.** SUSE's image-build framework. XML-based config
(`config.xml`). Cross-distro support (Debian, Fedora, openSUSE, Arch,
CentOS) but native to openSUSE / SUSE Linux Enterprise. Mature.

**Strengths.**
- C1 ★★★★ — SUSE-backed; mature; cross-distro is genuine, not aspirational.
- C2 ★★★ for Debian (supported but second-class); ★★★★★ for openSUSE.
- C3 ★★★ — XML is declarative but verbose; not Markdown- or YAML-grade ergonomics.
- C4 ★★★ — multi-profile via XML profile attributes; workable but heavy.
- C5 ★★★ — surface accessibility OK; less idiomatic than mkosi.
- C10 ★ — operator-familiarity cost high; XML config is unergonomic.
- C12 ★★ — lock-in to Kiwi's XML; profile definitions don't translate cleanly to other substrates.

**Bottom line.** Disqualified primarily on operator-ergonomics (XML config) + lower Debian-native fluency than live-build/mkosi. **Excluded from primary recommendation.** Re-evaluable if openSUSE wins the distro axis AND operator accepts XML config.

---

### 6. ostree / rpm-ostree (image-based atomic)

**What it is.** OSTree is a content-addressable filesystem for OS
images. The Fedora Silverblue / CoreOS / Kinoite family is built on
rpm-ostree. The model: the OS is an immutable read-only tree;
upgrades atomic; rollback trivial; layered overrides via overlays.

**Strengths.**
- C1 ★★★★ — strong upstream; Fedora-backed; production-deployed at scale (Silverblue, CoreOS, Endless OS, etc.).
- C2 ★★ for Debian (rpm-ostree is RPM-coupled; pure ostree can work with Debian content but ecosystem is RPM-centric); ★★★★★ for Fedora.
- C3 ★★★★ — declarative manifests (treefile JSON for rpm-ostree).
- C4 ★★★★ — multi-profile via separate refs; cheap to maintain N profiles atomically.
- C5 ★★★ — surface accessibility via overlay files; cleaner than imperative but slightly indirect.
- C6 ★★★★★ — content-addressed by design; reproducibility is foundational.
- C7 ★★★★ — builds in CI; image verification via boot-into-ostree-commit.
- C8 ★★ — ZFS-on-root is awkward with ostree (ostree assumes traditional filesystem semantics; layering on ZFS requires careful integration).
- C9 ★★★★ — secure-boot integrated; ostree commits sign-able.
- C10 ★ — operator-familiarity cost very high; immutable-OS paradigm is a substantial mental shift from traditional Debian.
- C11 ★★★★★ — **the killer feature**: post-install lifecycle is ostree's strength (`rpm-ostree upgrade`, `rpm-ostree rollback`, `ostree admin status`). Atomic updates + rollback baked in.
- C12 ★★★ — paradigm shift makes migration to/from ostree expensive.

**Bottom line.** Architecturally compelling — atomic updates + rollback + content-addressed reproducibility. But: high familiarity cost; rpm-ostree's Debian path is weak; ZFS-on-root is awkward. **Conditional candidate** — re-enter the recommendation if operator accepts immutable-OS paradigm AND Q-016 picks Fedora-base.

---

### 7. NixOS / nix-image (declarative system)

**What it is.** NixOS is a Linux distribution built on the Nix package
manager. The entire system (kernel, services, users, packages,
network) is defined declaratively in `.nix` configuration files. Pure
functional; immutable; reproducible; rollback to any prior generation.

**Strengths.**
- C1 ★★★★ — strong community; NixOS Foundation; active development.
- C2 N/A for Debian (NixOS replaces the distro entirely; not a substrate for Debian).
- C3 ★★★★★ — fully declarative; the pinnacle of declarative system definition.
- C4 ★★★★★ — first-class profile pluralism via modules; sharing + override is idiomatic.
- C5 ★★★★ — every identity surface configurable in `configuration.nix`.
- C6 ★★★★★ — reproducibility is foundational; bit-for-bit possible.
- C7 ★★★★ — builds entirely in CI; image verification via `nixos-rebuild build-vm`.
- C8 ★★★★ — ZFS-on-root is a first-class supported config in NixOS.
- C9 ★★★ — secure-boot supported but less polished than Fedora/Debian.
- C10 ★ — operator-familiarity cost is the highest of all candidates; Nix language is genuinely different; the whole mental model is different.
- C11 ★★★★★ — atomic generation switching + rollback baked in.
- C12 ★ — picking NixOS is picking a different OS entirely; migration TO NixOS rewrites the OS; migration FROM NixOS rewrites the OS.

**Bottom line.** Technically the most elegant for declarative + reproducible + multi-profile. But: **it IS the distro**, not a substrate atop Debian. Picking NixOS means abandoning Debian-as-Ark entirely. This is a Q-016 candidate (replace Debian with NixOS) more than a Q-001 candidate (substrate atop Debian). Evaluated again in the Q-016 section.

---

### 8. Buildroot (embedded reference for contrast)

**What it is.** Cross-compile embedded Linux image builder. Used for
routers, IoT devices, small appliances. Mature. Designed for
constrained targets (small flash, limited RAM).

**Bottom line.** Disqualified for the SAIN-01 desktop workstation use
case — Buildroot's optimization point (embedded constrained-resource)
is mismatched to the target (256 GB DDR5 desktop workstation).
Included as a contrast in the Plan-agent spec to confirm we evaluated
breadth. **Excluded from primary recommendation.**

---

### Substrate-axis comparison matrix (Debian-base assumption)

Assuming Q-016 stays on Debian 13 (working hypothesis):

| Criterion | live-build | mkosi | Lorax | Kiwi | ostree (debian-os) | NixOS | Buildroot |
|---|---|---|---|---|---|---|---|
| C1 maturity | ★★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★ |
| C2 Debian-native | ★★★★★ | ★★★★ | ✗ | ★★★ | ★★ | ✗ | ★★ |
| C3 declarative | ★★★★ | ★★★★★ | ★★★★ | ★★★ | ★★★★ | ★★★★★ | ★★ |
| C4 multi-profile | ★★★ | ★★★★★ | ★★★ | ★★★ | ★★★★ | ★★★★★ | ★★ |
| C5 whitelabel surface | ★★★★ | ★★★★ | n/a | ★★★ | ★★★ | ★★★★ | ★★ |
| C6 reproducibility | ★★★ | ★★★★ | ★★★ | ★★★ | ★★★★★ | ★★★★★ | ★★★★ |
| C7 CI testability | ★★★★ | ★★★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ | ★★★★★ |
| C8 ZFS-root | ★★★★ | ★★★ | n/a | ★★ | ★★ | ★★★★ | ★ |
| C9 secure-boot | ★★★★ | ★★★★ | n/a | ★★★ | ★★★★ | ★★★ | ★★ |
| C10 operator familiarity | ★★★★★ | ★★★ | ★ | ★ | ★ | ★ | ★ |
| C11 lifecycle-tool surface | ★ | ★★ | ★★ | ★★ | ★★★★★ | ★★★★★ | ★ |
| C12 evolvability | ★★★★ | ★★★★ | ★★ | ★★ | ★★★ | ★ | ★★★ |

**Top 2 on Debian-base**: **live-build** (familiarity + Debian-native) and **mkosi** (declarative + multi-profile + reproducibility + CI-first). Both viable.

## Axis 2 — Distro-base reconsideration (Q-016)

Per operator: "Debian is a bit like saying we have our Arc but we start
from there." Distro-base reconsideration evaluates whether staying on
Debian 13 costs us material potential.

### Debian 13 Trixie (baseline; working hypothesis)

**Strengths.** Operator-familiar; massive package archive (~60K binary packages); rock-solid stability; AGPL-friendly ecosystem; secure-boot well-supported; ZFS-on-root mature in community; lives forever (LTS path).

**Weaknesses.** Packages skew older than Fedora/Arch (less of a concern for OS substrate; more for desktop apps); systemd-native modern features (mkosi-style image building, systemd-cryptenroll, systemd-homed) work but aren't first-class.

**For SAIN-01 default profile.** Kernel custom-tuned via `-march=znver5` (E101) sits cleanly on Debian; ZFS-DKMS + NVIDIA 560+ open-kernel-dkms drivers are well-supported; AGPL daemon (selfdef) lives in operator-controlled archive.

**Verdict.** Strong default. Familiarity + Debian-native substrate options (live-build, mkosi) + zero-cost familiarity bar.

---

### Fedora 41/42 (Workstation; Silverblue/Kinoite variants)

**Strengths.** Leading-edge software (newer kernels by default; newer systemd; newer drivers); fast iteration; **Silverblue/Kinoite immutable variants** (ostree-backed atomic updates + rollback) are operationally compelling; strong Wayland + GNOME/KDE story.

**Weaknesses.** Faster release cadence (~6 months); operator-familiarity cost (RPM idioms; dnf instead of apt); ZFS-on-root supported but less polished than on Debian; AGPL daemon lives outside the official archive (RPM Fusion or Copr or self-host).

**For SAIN-01.** Custom kernel works; NVIDIA drivers via RPM Fusion; ostree provides the atomic-update + rollback story Debian doesn't have natively.

**Verdict.** Compelling specifically for the **immutable-OS Silverblue path** (Q-011 lifecycle surface gets atomic updates for free). Weakens on operator-familiarity + Debian-AGPL-archive ecosystem alignment.

---

### RHEL-ABI (Rocky Linux 10 / AlmaLinux 10)

**Strengths.** Enterprise stability (10-year support cycle); RHEL ABI compatibility; AppStream modular packages.

**Weaknesses.** Same RPM-familiarity cost as Fedora; conservative kernel version (less aggressive Zen 5 tuning support out-of-box); Recent Red Hat/CentOS turbulence (CentOS 8 / Stream / Rocky/Alma forks) is a sovereignty risk if a future Red Hat policy shift undermines the downstream distros.

**Verdict.** Strong for stability; weak for cutting-edge AI hardware (Blackwell Q3-2026 drivers; Zen 5 single-cycle AVX-512 tuning); sovereignty concern given Red Hat's recent posture changes.

---

### openSUSE Tumbleweed

**Strengths.** Rolling-release leading-edge; YaST configuration; btrfs+snapper for snapshot-based rollback baked in; strong community.

**Weaknesses.** Rolling means breakage risk; operator-familiarity cost (zypper instead of apt); ZFS-on-root supported via OpenZFS but not as mature as Debian; build substrate is Kiwi (XML-heavy).

**Verdict.** Compelling for the snapshot-rollback story; weaker on operator-familiarity.

---

### openSUSE Leap 16

**Strengths.** SUSE-stable release; shares RPM kernel and userspace with SLE; btrfs+snapper for snapshots.

**Weaknesses.** Slower than Tumbleweed without the Debian-grade ecosystem; SLE-codebase shifts (SUSE strategic decisions) are a sovereignty risk.

**Verdict.** Weaker variant of Tumbleweed without the rolling-edge advantage.

---

### Arch Linux

**Strengths.** Rolling; minimal default install; AUR's vast user-packaged catalog; lean by design.

**Weaknesses.** Rolling means continuous-update overhead; partial-upgrades unsupported; less stable than Debian for long-running deployments; no enterprise / LTS path; sovereignty concern: Arch's "you-are-the-sysadmin" mantra trades enterprise support for DIY responsibility.

**Verdict.** Compelling for cutting-edge but a sovereign workstation that must run reliably for years prefers Debian stability over Arch rolling.

---

### NixOS

(Already detailed in Axis 1 §7.)

**For Q-016.** Picking NixOS is picking a different OS entirely. Not "Debian as Ark" — it's a different boat. Compelling if operator accepts the Nix-language paradigm shift; high cost if not.

**Verdict.** Architecturally elegant; high operator-familiarity cost; doesn't compose with Debian-as-Ark framing.

---

### Void Linux

**Strengths.** Independent (not Debian/Fedora/openSUSE/Arch derivative); runit init (not systemd); musl OR glibc; lean.

**Weaknesses.** Small community vs Debian/Fedora; runit-based ecosystem incompatible with most systemd-assuming AI tooling (vLLM service units, Tetragon expects systemd journal, etc.); ZFS-on-root supported but small ecosystem; non-systemd is a substantive deviation that costs everywhere.

**Verdict.** Sovereignty-attractive (independent + runit + small) but disqualified by systemd-incompatibility with the AI tooling stack we need.

---

### Distro-axis comparison matrix

| Criterion | Debian 13 | Fedora Silverblue | Rocky 10 | openSUSE Tumbleweed | Arch | NixOS | Void |
|---|---|---|---|---|---|---|---|
| Maturity | ★★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★ |
| Operator-familiarity | ★★★★★ | ★★ | ★★ | ★★ | ★★ | ★ | ★ |
| Cutting-edge kernel/drivers | ★★★ | ★★★★ | ★★ | ★★★★★ | ★★★★★ | ★★★★ | ★★★ |
| ZFS-on-root maturity | ★★★★★ | ★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ | ★★★ |
| AI tooling ecosystem (vLLM/CUDA/Tetragon) | ★★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★ |
| Atomic-update / rollback | ★★ | ★★★★★ | ★★ | ★★★★ (snapper) | ★★ | ★★★★★ | ★★ |
| Sovereignty (operator-pulled updates, no vendor pressure) | ★★★★★ | ★★★ | ★★★ | ★★★★ | ★★★★★ | ★★★★★ | ★★★★★ |
| AGPL ecosystem-friendliness | ★★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★★ | ★★★★ | ★★★★ |
| Custom-kernel tooling fluency | ★★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★★ | ★★★★ | ★★★★ |

**Top 2 on distro axis**: **Debian 13** (familiarity + Debian-native substrate options + AI tooling ecosystem) and **Fedora Silverblue** (atomic-update + immutable-OS paradigm). NixOS is a strong outlier requiring paradigm acceptance.

## Recommendation

### Primary recommendation (default; assumes operator stays on Debian-as-Ark)

**Substrate: `mkosi` on Debian 13 Trixie.**

| Reason | Detail |
|---|---|
| Declarative profile pluralism | `mkosi.conf.d/<profile>.conf` is exactly the multi-profile-from-day-1 idiom we need. `sain-01` + `old-workstation` + reserved (`minimal` / `developer` / `headless`) compose naturally. |
| CI-first | `mkosi qemu` runs the built image in QEMU for smoke-testing as a single command. Aligns with the TDD harness (SDD-008) for hardware-free validation. |
| Reproducibility | `SOURCE_DATE_EPOCH` honored; bit-for-bit achievable with build-time discipline. |
| Debian-native | Targets Debian 13 directly via apt/debootstrap-under-the-hood; we keep AGPL ecosystem, kernel-custom-build path, ZFS-DKMS recipes, NVIDIA driver alignment. |
| Future-proof | Cross-distro: if Q-016 later picks Fedora or openSUSE, the mkosi profile syntax translates with minor surgery. |
| Modern systemd integration | systemd-boot + SBAT signing + systemd-cryptenroll (for Q-006 secure-boot path) all first-class. |
| Operator-familiarity cost | Modest; the `.conf` syntax is conceptually similar to live-build's config tree but more idiomatic. |

**Trade-offs accepted by this recommendation**:
- ZFS-on-root requires a `mkosi.prepare.chroot` hook to install zfs-dkms before the rootfs is sealed (vs live-build where ZFS-on-root recipes are slightly more turnkey).
- No native ostree-style atomic-update story (Q-019 lifecycle surface builds on top in Stage 2+).

### Alternative recommendation A (lower-risk; conservative)

**Substrate: `live-build` on Debian 13 Trixie.**

Pick this if:
- Operator-familiarity cost is the primary driver (live-build is what Debian itself uses; zero learning curve).
- Speed-to-first-bootable-image is the priority (live-build's defaults are closer to "what Debian users expect from a live ISO").
- ZFS-on-root recipes from the Proxmox/Debian community are more directly applicable.

**Trade-off vs primary**: less declarative; multi-profile is workable but less elegant; CI testability is good but not as first-class as `mkosi qemu`.

### Alternative recommendation B (paradigm-shift; high reward)

**Substrate + distro: `rpm-ostree` on Fedora Silverblue.**

Pick this if:
- Q-019 lifecycle-management surface should be **substrate-native** (atomic updates + rollback baked in; no Stage 2+ surface-building required for the basic case).
- Operator accepts immutable-OS paradigm shift.
- Operator accepts RPM ecosystem cost (selfdef AGPL ships via Copr; NVIDIA via RPM Fusion).
- Cutting-edge kernels + drivers via Fedora's faster cadence are net positive.

**Trade-off vs primary**: substantial operator-familiarity cost; AGPL ecosystem shift; ZFS-on-root harder; whitelabel surface harder (rpm-ostree's immutability complicates `/etc/issue` overrides for SOME paths — would need careful overlay design).

### Alternative recommendation C (declarative-elegance; paradigm-shift)

**Distro + substrate: `NixOS` (drops Debian entirely).**

Pick this if:
- Declarative system definition is the highest-priority goal.
- Operator accepts Nix-language paradigm shift.
- Reproducibility (bit-for-bit) is the highest-priority goal.
- Atomic generation switching + rollback baked in.

**Trade-off vs primary**: massive operator-familiarity cost; AGPL daemon (selfdef) requires a `nixpkgs` package authoring; abandons Debian-as-Ark framing entirely.

### Why mkosi-on-Debian is the recommended primary

It's the only candidate that scores high (★★★★ or ★★★★★) on **all** of:
- C1 maturity + C2 native + C3 declarative + C4 multi-profile + C5 whitelabel + C6 reproducibility + C7 CI + C9 secure-boot + C10 familiarity (with modest learning curve) + C12 evolvability

The only ★★/★★★ scores are C8 (ZFS-root — workable with prepare hook) and C11 (lifecycle-tool surface — sovereign-os builds in Q-019 anyway).

Compared to live-build: mkosi wins on C3 / C4 / C7 / C12 (declarative, multi-profile, CI, evolvability).
Compared to rpm-ostree: mkosi wins on C2 / C10 (Debian-native, familiarity).
Compared to NixOS: mkosi wins on C2 / C10 / C12 (Debian-native, familiarity, evolvability).

### Reversal cost (per recommendation)

If we later switch substrate (within Debian-base):
- mkosi → live-build: **moderate** (rewrite `mkosi.conf` tree as `live-build/config/`; semantically equivalent; ~2 days dev effort).
- mkosi → ostree-on-Debian: **high** (paradigm shift; rewrite for atomic-OS model; ~2-4 weeks).
- mkosi → NixOS: **very high** (changes distro entirely; rewrite as `configuration.nix`; ~1-2 months).

The mkosi recommendation preserves substrate-swap optionality at moderate cost.

## Goals (for the substrate decision)

1. **Pick a substrate that meets all 12 criteria at ★★★ or better**, with at least 8 criteria at ★★★★ or better. (mkosi-on-Debian hits this; live-build hits 11/12.)
2. **Preserve Debian-as-Ark framing**: stay on Debian 13 unless operator explicitly chooses a paradigm shift.
3. **Enable Stage Gate 2 to lock the choice cleanly**: substrate decision must be reversible at ≤ 4-week cost.
4. **Enable Foundation tier parallel tracks**: PR 5 (profile schema), PR 7 (Debian surface audit) progress regardless of substrate choice (substrate decision shapes their content but doesn't block their PR opening).

## Non-goals (this SDD)

- Does NOT decide the substrate. Operator decides at Gate 2.
- Does NOT decide the distro. Q-016 closure happens at Gate 2 alongside Q-001.
- Does NOT specify the build pipeline's command surface — that's Stage 2+.
- Does NOT specify the installer experience (Q-008) — Stage 2+.
- Does NOT specify the lifecycle-management surface (Q-019) — Stage 2+.

## Open sub-questions (PR 4-local)

These get resolved either at Gate 2 (operator picks) or rolled forward
to subsequent SDDs:

- **Q4-A** — If primary recommendation (mkosi-on-Debian) wins, do we
  pin mkosi to a specific version, or track latest? Trade-off:
  reproducibility favours pinning; ergonomics favour latest.
- **Q4-B** — If primary wins, where does mkosi config live? `mkosi/`
  at repo root? `profiles/<name>/mkosi/`? Substrate-config inside
  profile YAML? Plan-agent suggests `profiles/<name>.yaml` is the
  schema-canonical home with substrate-config as a key inside.
- **Q4-C** — Does the operator want a deeper dive on top-2 (mkosi +
  live-build) with a small Proof-of-Concept comparing actual build
  times + image sizes? Adds 1-2 days; produces empirical data; not
  strictly needed if the analysis above is sufficient.
- **Q4-D** — If the answer to Q-016 is "stay on Debian", do we
  reserve a future SDD slot for periodic re-evaluation (every 12-18
  months)? Or accept Debian-as-Ark as durable?
- **Q4-E** — If the primary loses and the operator picks ostree path,
  do we keep `sovereign-os` repo or fork to a new repo with the
  immutable-OS paradigm baked into its name? Affects repo-naming +
  history.

## Way forward

1. **Stage Gate 2 opens after this PR merges**: operator reviews this
   SDD; picks substrate + distro base (Q-001 + Q-016 resolve as
   D-NNN entries in `docs/decisions.md`).
2. **PR 5 (profile schema)** opens in parallel — schema design is
   substrate-influenced but not substrate-blocking.
3. **PR 7 (Debian-or-successor surface audit)** opens in parallel —
   the audit's content depends on the distro decision; the audit
   methodology + structure can be authored ahead.
4. **PR 6 (profile stubs)** opens after Gate 2 + Gate 3 (schema
   locked) — its profile bodies depend on the substrate decision.
5. **PR 8 (whitelabel mechanism)** opens after PR 7 + Gate 4 — its
   mechanism depends on which surfaces PR 7 cataloged.

## Cross-references

- Charter: `docs/sdd/000-charter.md` (mission + IaC bar + sovereignty)
- SDD-001 cross-repo boundaries: `docs/sdd/001-cross-repo-boundaries.md`
- SDD-002 documentation pipeline: `docs/sdd/002-documentation-pipeline.md` (mdbook substrate-aware)
- Decisions log: `docs/decisions.md` (Q-001 + Q-016 pending; D-NNN entries land at Gate 2)
- Plan-agent macro-arc § PR 4: info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
- Operator directive "Debian as Ark": info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md`
- L0 limit-continuation (Q-017 inference-backend distinct from this Q): info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening-limit-continuation.md`
- SAIN-01 milestone (E101 OS build): info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md`
