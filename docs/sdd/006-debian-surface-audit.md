# SDD-006 — Debian (or successor) surface audit + whitelabel target inventory

> Status: **review** (audit-grade inventory; locked at Stage Gate 4 alongside SDD-007 mechanism)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none
> Resolves at Gate 4: contributes to **Q-004** (legal scope of whitelabel) — paired with SDD-007 (mechanism)
> Derived from: Plan-agent macro-arc § PR 7 (info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`); operator "Debian as Ark" directive (info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md`); charter (`docs/sdd/000-charter.md`) § non-goals + sovereignty principles

## Problem

The sovereign-OS is — under the **Debian-as-Ark** working hypothesis
(Q-016 closure-path: probably stays on Debian 13 Trixie) — a custom
Debian derivative. A vanilla Debian system surfaces the identity
"Debian" in dozens of places: filesystem files, package metadata,
boot banners, installer branding, kernel strings, network defaults,
even the man pages.

Some of these MUST be rebranded (else the OS calls itself Debian when
it's the operator's sovereign distribution). Some MUST stay touched
in specific ways (Debian's trademark policy + DFSG + GPL attribution
have a legal floor). Some are convenience-only (`/etc/motd`).

Before the whitelabel mechanism (PR 8 / SDD-007) is specified, we
need a **catalog** of every surface. This SDD is that catalog.

If Q-016 closure-path picks a non-Debian distro (Fedora / openSUSE /
etc.), the inventory's categorisation translates surface-for-surface
to the chosen base (e.g., `redhat-release` instead of `debian_version`).
The methodology + legal framework stays identical.

## Required coverage

### A. Identity surfaces — filesystem

Files that name the upstream distro. Each row: path · default content
(Debian 13 Trixie) · category · reason · whitelabel approach.

| Path | Default content (sample) | Category | Why | Approach |
|---|---|---|---|---|
| `/etc/os-release` | `NAME="Debian GNU/Linux"; ID=debian; PRETTY_NAME="Debian GNU/Linux 13 (trixie)"; VERSION_ID="13"; HOME_URL=…` | **must-rebrand** | First file every systemd/userspace tool reads; defines `ID=` we want to set to `sovereign`. | template-substitution at build time (mkosi.skeleton or live-build includes.chroot) |
| `/usr/lib/os-release` | symlink/copy of `/etc/os-release` semantics; some distros maintain the canonical copy here | **must-rebrand** | Same as above. Modern systemd reads from `/usr/lib/os-release` if `/etc/os-release` is absent. | template-substitution; ensure both files coherent |
| `/etc/issue` | `Debian GNU/Linux 13 \\n \\l` | **must-rebrand** | Console login banner; operator-facing | template-substitution; substantive motd-style content per the operator's verbatim "We want quality over quantity..." motto |
| `/etc/issue.net` | `Debian GNU/Linux 13` | **must-rebrand** | Remote (telnet/SSH) login banner; same content as `/etc/issue` for consistency | template-substitution |
| `/etc/debian_version` | `13.0` | **must-not-touch** for trademark; **may-leave** otherwise | This file is provenance — *upstream* version. Deleting it would make the system claim to be non-Debian-derived (legally risky). Retain as-is. | leave untouched; whitelabel mechanism explicitly excludes |
| `/etc/lsb-release` | `DISTRIB_ID=Debian; DISTRIB_RELEASE=13; DISTRIB_CODENAME=trixie; DISTRIB_DESCRIPTION="Debian GNU/Linux 13 (trixie)"` | **must-rebrand** | Read by `lsb_release` and many scripts; tools may key on `DISTRIB_ID` | template-substitution; `DISTRIB_ID=Sovereign` (or operator-chosen brand) |
| `/etc/motd` | (often empty by default) | **must-rebrand** | First post-login surface; operator-facing | content from whitelabel profile; verbatim operator-stated motto |
| `/etc/update-motd.d/*` | dynamic motd scripts (e.g. `00-header` on Ubuntu-style, often absent on Debian unless `base-files` updates) | **should-rebrand** | If present, each generates a dynamic line | overlay scripts via includes.chroot or mkosi.extra |
| `/etc/hostname` | per-install (not Debian-named by default) | **n/a** | Not an identity surface; per-host | leave to during-install hook (Q-008 installer) |

### B. Package-manager surfaces

| Surface | Default behavior | Category | Why | Approach |
|---|---|---|---|---|
| `dpkg-vendor --query Vendor` | returns `Debian` | **may-leave** | Trademark-compliance: dpkg is Debian's tool; `dpkg-vendor` identifying the *toolchain* origin as Debian is honest provenance. Some scripts key on this for behavior selection. | leave; OR document downstream that `dpkg-vendor` returns `Debian` (toolchain), distinct from `/etc/os-release ID=sovereign` (distribution) |
| `/etc/dpkg/origins/default` | symlink → `debian` | **may-leave** | Used by dpkg-vendor; same reasoning as above | leave |
| `/etc/dpkg/origins/sovereign` | does not exist | **must-create** | Allow downstream tools to query origin via `dpkg-vendor --vendor sovereign --query Origin` if they need brand identification | create alongside default; symlink toggleable |
| `/etc/apt/sources.list.d/debian.sources` (DEB822) | `URIs: http://deb.debian.org/debian; Suites: trixie trixie-updates trixie-security; …` | **may-leave** | Upstream Debian repos remain the truth source for security updates. Trademark policy doesn't prohibit this. | leave; sovereign-os may ADD its own `sovereign.sources` for sovereign-os-specific packages |
| `/etc/apt/sources.list.d/sovereign.sources` | does not exist | **must-create** (if sovereign-os ships its own apt repo) | sovereign-os packages (selfdef, custom kernel debs, agent tooling) need a deliverable channel | mkosi/live-build adds during build; signing key trust-anchored at build time |
| `apt-get install` output banners | `Reading package lists... Done`, etc. — Debian-string-free | **may-leave** | No identity claim | leave |
| `/etc/apt/apt.conf.d/*` | various — `99update-notifier`, `01autoremove`, etc. | **may-leave** | Operational; no identity surface | leave |
| `apt-key`, `apt-secure` documentation banners | "WARNING: apt does not have a stable CLI interface..." | **may-leave** | Tool warnings; no identity claim | leave |

### C. Boot surfaces

| Surface | Default | Category | Why | Approach |
|---|---|---|---|---|
| GRUB menu entries (`/boot/grub/grub.cfg`) | "Debian GNU/Linux" entries generated by `update-grub` | **must-rebrand** | Visible at every boot | hook into `/etc/default/grub` `GRUB_DISTRIBUTOR` variable + `/etc/grub.d/00_header` substitution |
| `/etc/default/grub` `GRUB_DISTRIBUTOR` | `lsb_release -i -s 2> /dev/null || echo Debian` | **must-rebrand** | This variable drives menu entry naming | set to `"Sovereign"` (or operator-chosen brand) via build-time substitution |
| GRUB theme | Debian's default theme (sometimes branded with Debian swirl) | **should-rebrand** | Visible at every boot if theme is set | replace `/boot/grub/themes/<theme>/` files or set `GRUB_THEME=` to sovereign-os theme |
| GRUB background image | optional, default may be Debian-branded | **should-rebrand** | Cosmetic | replace via `GRUB_BACKGROUND=/path/to/sovereign-bg.png` |
| Plymouth boot splash | Debian's default `joy` or `spinner-debian` theme | **must-rebrand** | Visible at every boot (if Plymouth enabled) | install sovereign-plymouth-theme package + `update-alternatives --set default.plymouth /usr/share/plymouth/themes/sovereign/sovereign.plymouth` |
| Kernel boot logo (Tux) | the default kernel logo | **may-leave** | Visible briefly during kernel init; subtle; replacing requires kernel rebuild (we already rebuild for znver5 — opportunity to swap) | optional: include a `drivers/video/logo/logo_sovereign_clut224.ppm` in kernel build; CONFIG_LOGO_LINUX_CLUT224 |
| systemd boot banner (early console) | `Welcome to Debian GNU/Linux 13 (trixie)!` | **must-rebrand** | Visible in console boot logs | `/etc/issue` content; some systemd versions read from `os-release` PRETTY_NAME so the os-release rebrand handles this automatically |
| systemd-boot loader (if used instead of GRUB) | `Debian Linux` entries | **must-rebrand** | systemd-boot reads from `/boot/loader/entries/*.conf` `title` field | template-substitution at build |

### D. Installer surfaces

These only apply if Q-008 picks an installer (debian-installer derivative
/ Calamares / image-only — image-only path skips this section entirely).

| Surface | Default | Category | Approach |
|---|---|---|---|
| `debian-installer` UI strings | "Debian Installer", "Welcome to Debian GNU/Linux..." | **must-rebrand** | Build a sovereign-installer udeb fork OR theme via the `localechooser-data` package patterns; substantial work; documented in SDD-007 |
| `debian-installer` preseed banner | "Debian GNU/Linux 13 (trixie) - Welcome" | **must-rebrand** | Modify preseed templates |
| `debian-installer` boot splash | Debian-branded | **must-rebrand** | Replace the installer-side Plymouth theme |
| `Calamares` (alternative installer) | "Calamares" branding + per-distro skin | **must-rebrand** | Calamares supports per-distro skins via `calamares/branding/<id>/branding.desc`; ship our own |
| Live-system desktop wallpaper (during install) | Debian-default wallpaper | **must-rebrand** | Replace `/usr/share/backgrounds/desktop-base/*` or override via desktop profile |

### E. Desktop / display-manager surfaces

These apply only if a desktop environment is part of the profile. For
SAIN-01 default (which is primarily an AI workstation, may run with
or without DE), most of these are profile-conditional.

| Surface | Default | Category | Approach |
|---|---|---|---|
| GDM login screen branding | Debian's GDM theme | **should-rebrand** | Theme override; `/etc/gdm3/` and `/usr/share/gnome-shell/theme/` |
| SDDM login screen | Debian's SDDM theme | **should-rebrand** | Theme override |
| LightDM greeter | Debian default | **should-rebrand** | Theme override |
| Default desktop wallpaper | `/usr/share/backgrounds/desktop-base/*-symbolic.svg` (Debian) | **should-rebrand** | Replace files; the `desktop-base` package controls these |
| GNOME "About this system" dialog | reads `/etc/os-release` PRETTY_NAME | **must-rebrand** | Already covered by os-release rebrand |
| KDE "About System" dialog | reads `/etc/os-release` PRETTY_NAME | **must-rebrand** | Same |
| Lock screen branding | DE-specific | **should-rebrand** | DE theme override |
| `desktop-base` package files | Debian-branded SVG/PNG icons + wallpapers | **must-rebrand** if shipping `desktop-base` | Replace package or `dpkg-divert` the assets and overlay sovereign-os equivalents |

### F. Kernel surfaces

| Surface | Default | Category | Approach |
|---|---|---|---|
| `/proc/version` | `Linux version 6.x.y-amd64 (debian-kernel@lists.debian.org) (gcc-... Debian-...) #1 SMP Debian 6.x.y-...` | **may-leave** (provenance) OR **should-rebrand** (sovereignty) | This is compile-time-baked via `CONFIG_LOCALVERSION` + the `CONFIG_LOCALVERSION_AUTO` + the kernel's hostname-at-build-time substitution. Since we already custom-compile for znver5 (E101 + profile schema's `kernel.compile_flags`), the compile sets `LOCALVERSION="-znver5"` and the build-host appears in the string. Setting `KBUILD_BUILD_USER=sovereign-os` + `KBUILD_BUILD_HOST=sovereign-os` env vars at build time produces `Linux version 6.x.y-znver5 (sovereign-os@sovereign-os) ...` — sovereign-os-branded. |
| `uname -a` | derived from `/proc/version` | **may-leave / should-rebrand** | Same mechanism as `/proc/version` |
| `uname -r` (kernel release) | `6.x.y-amd64` | **may-leave / should-rebrand** | The `-amd64` suffix is set by Debian's `linux-image-amd64` packaging; our custom kernel uses `-znver5` per E101 → naturally sovereign-branded |
| Kernel package name | `linux-image-6.x.y-amd64` | **must-rebrand** | Custom build produces `linux-image-6.x.y-znver5_*.deb` (E101 already plans this) |
| kernel `CONFIG_LOCALVERSION` | empty in stock Debian; we set to `-znver5` | **must-rebrand** | Already part of E101 + profile schema; `-znver5` is the sovereign-os suffix marker |
| Initramfs banner (if any) | minimal | **may-leave** | Initramfs is rebuilt by `update-initramfs`; no identity surface inside |

### G. Documentation surfaces

| Surface | Default | Category | Approach |
|---|---|---|---|
| Manpages referencing Debian | many manpages reference "Debian" (e.g., apt(8), dpkg(1), debian-policy) | **must-not-touch** | Editing upstream Debian manpages would violate trademark + DFSG (these are Debian's documentation, copyrighted) | leave untouched; sovereign-os ships its own manpages (e.g., `sovereign-os(7)` overview manpage) |
| `/usr/share/doc/<package>/copyright` | per-package copyright files referencing Debian + upstream | **must-not-touch** | Legal: GPL/AGPL/MIT attribution; modifying these is a license violation | leave untouched; absolute floor |
| `/usr/share/doc/base-files/` | contains `motd.dpkg-dist` (skeleton motd) | **must-rebrand** | One of base-files' identity files | `dpkg-divert` the file or template-substitute |
| `/etc/dpkg/dpkg.cfg` | dpkg config | **may-leave** | Not an identity surface | leave |
| `/etc/os-release` `BUG_REPORT_URL=` | `https://bugs.debian.org/` | **must-rebrand** | Routes bug reports to Debian | redirect to sovereign-os issue tracker |
| `/etc/os-release` `HOME_URL=` | `https://www.debian.org/` | **must-rebrand** | Distribution homepage | sovereign-os GitHub Pages URL or operator-chosen |
| `/etc/os-release` `SUPPORT_URL=` | `https://www.debian.org/support` | **must-rebrand** | Same |

### H. Network surfaces

| Surface | Default | Category | Approach |
|---|---|---|---|
| Default hostname pattern (debian-installer) | `debian` if not configured during install | **must-rebrand** | preseed `d-i netcfg/get_hostname` to `sovereign` or operator-prompted |
| `/etc/timesyncd.conf` NTP servers | `NTP=` may include `pool.ntp.org` (generic) or Debian's NTP pool | **may-leave** | Generic NTP pool is fine; if Debian-specific pool, rebrand to generic | leave if generic; rebrand if Debian-specific |
| `/etc/resolv.conf` defaults | per-network | **n/a** | Not an identity surface | leave |
| Default APT mirror | `http://deb.debian.org/debian` | **may-leave** | Debian's CDN; trademark-permissible mirror identifier | leave |
| Default NetworkManager / systemd-networkd settings | Debian-default | **may-leave** | Operational defaults | leave |
| `apt-cacher-ng` config (if installed) | references Debian | **may-leave** | Caching proxy; operational | leave |

### I. Telemetry / phone-home surfaces (sovereignty-critical)

These deserve a dedicated section. The charter's sovereignty
principles forbid phone-home defaults.

| Package / surface | Default behavior | Category | Approach |
|---|---|---|---|
| `popularity-contest` | If enabled at install, sends weekly anonymous package-usage stats to Debian | **must-not-install** | Already on schema's `packages.deny` list; never installed | denied at package-selection time; build fails if accidentally added |
| `apport` | Crash reporting; can phone home if configured | **must-not-install** | Same; on `packages.deny` | denied |
| `whoopsie` (Ubuntu-derived) | Phones home; not default on Debian | **must-not-install** | Same | denied |
| `unattended-upgrades` default | Pulls from Debian security updates by default | **may-leave**, with config | Security updates are operator-aligned (we WANT security patches); `unattended-upgrades` doesn't phone home in a privacy-violating sense; it just downloads. | leave with config; operator-pulled philosophy via `Periodic::Update-Package-Lists` can be tuned |
| `motd-news` (Ubuntu motd-news package) | Pulls news from Canonical | **must-not-install** | Not Debian-default but worth blocking | denied |
| `ubuntu-advantage-tools` | Ubuntu-specific | **must-not-install** | Not Debian-default | denied |
| `snapd` | Snap package manager; phones home | **must-not-install** | On `packages.deny` per schema | denied |
| systemd `systemd-resolved` DNS-over-TLS to Cloudflare/Google | Not Debian-default; opt-in | **may-leave / configure** | If operator enables DoT, choose sovereignty-aligned DNS provider; not a Debian-identity surface | leave but document |

### J. Substrate-specific surfaces (substrate-dependent — see Q-001 Gate 2)

These vary by substrate decision; included for completeness:

**If substrate = mkosi:**
- `mkosi.conf` `Distribution=debian` field — internal; no run-time surface
- `mkosi.skeleton/etc/os-release` — operator-authored; controls the rebrand

**If substrate = live-build:**
- `config/binary` `LB_DISTRIBUTION` parameter — controls ISO metadata
- `config/auto/config` `--distribution trixie` — internal config
- `config/includes.chroot/etc/os-release` — operator-authored; controls the rebrand

**If substrate = rpm-ostree:**
- `treefile.yaml` `ref:` — image ref; sovereign-os-namespaced
- treefile `default-target:` — controls boot

**If substrate = NixOS:** does not apply (NixOS replaces Debian entirely; Q-016 picked NixOS).

## Legal floor (must-not-touch, sovereignty + trademark + DFSG)

**The operator's sovereignty principles require that nothing phones
home by default. The Debian trademark policy + DFSG + GPL/AGPL
attribution requirements set an opposite floor — certain things must
remain to honor upstream's terms.** This section documents the
intersection:

### Debian trademark policy (https://www.debian.org/trademark)

Debian's trademark policy permits derivative distributions but requires
honest provenance. Specifically:

1. **A derivative MUST NOT claim to be Debian itself.** Setting
   `/etc/os-release` `ID=sovereign` (not `debian`) satisfies this.
2. **A derivative MAY reference its Debian heritage factually.**
   "Based on Debian 13" is permitted; "Debian Sovereign Edition" is
   not (implies endorsement).
3. **A derivative MUST NOT modify the Debian logo / swirl.** Sovereign
   distribution ships its own logo; the Debian swirl is never
   modified, only optionally absent.
4. **A derivative MAY redistribute Debian packages unchanged.**
   Standard apt-mirror usage is permitted.
5. **A derivative MUST honor GPL/AGPL package attribution.** Every
   modified package's debian/copyright file accurately reflects the
   modification chain.

### DFSG (Debian Free Software Guidelines)

A Debian derivative may include non-DFSG-compliant software (it's no
longer Debian-pure), but each non-DFSG component must be honestly
labelled. Sovereign-OS's package list (per profile schema's `packages`
block) tracks each non-free addition explicitly.

### GPL / AGPL / MIT attribution

`/usr/share/doc/<package>/copyright` files MUST stay untouched. These
are legally-required attribution surfaces. The whitelabel mechanism
explicitly skips `/usr/share/doc/`.

### `/etc/debian_version` retention

Although it surfaces "Debian", this file is **provenance evidence**.
Removing it would imply the system has no Debian heritage, which is
factually wrong. Retain unchanged. The legal floor preserves this.

## Q-004 — legal scope of whitelabel (resolves at Gate 4)

The audit above informs Q-004 resolution. Two scoping options:

### Option A — Public-distribution whitelabel (high legal bar)
- All must-rebrand items rebranded
- All must-not-touch items preserved (legal floor)
- A `LICENSE-DEBIAN-HERITAGE.md` ships with the OS image documenting the upstream chain
- Trademark policy honored: ID is sovereign-os, references to Debian are factual ("based on Debian 13"), no Debian logo modification
- Suitable for public distribution + operator licensing posture

### Option B — Internal-use whitelabel (lower bar)
- Identity surfaces rebranded for operator-facing cosmetics
- Less rigor on the legal-floor preservation
- Suitable for personal sovereign workstation use only; NOT redistributable

Operator picks at Gate 4 based on intent (public distribution vs
personal sovereign workstation only). Per the charter and the
"sovereignty" framing, the operator's intent appears to lean
**personal sovereign workstation** initially with the option to
publicly distribute later — both scopes worth supporting.

## Surface categorization summary

| Category | Count (in this audit) | Examples |
|---|---|---|
| **must-rebrand** | 16 | os-release, issue, lsb-release, motd, GRUB menu, Plymouth, GDM/SDDM, installer banners, kernel package name, BUG_REPORT_URL, HOME_URL, base-files motd, etc. |
| **should-rebrand** | 8 | update-motd.d, GRUB theme, GRUB background, desktop wallpaper, login-manager themes, lock screens, desktop-base assets, hostname pattern |
| **may-leave** | 12 | dpkg-vendor, /etc/dpkg/origins/default, apt sources, apt config, manpage doc paths, NTP defaults, /proc/version (depending on operator preference), uname-a, etc. |
| **must-not-touch** | 7 (legal floor) | /etc/debian_version (provenance), /usr/share/doc/*/copyright (attribution), Debian-trademark-modifying assets (logo/swirl), upstream manpages, GPL attribution chains |
| **must-create** | 2 | /etc/dpkg/origins/sovereign, /etc/apt/sources.list.d/sovereign.sources (if sovereign-os apt repo ships) |
| **must-not-install** | 5 | popularity-contest, apport, whoopsie, motd-news, snapd, ubuntu-advantage-tools |

Total surfaces cataloged: **~50** (across A-I; some grouped).

## Goals

1. **Exhaustive surface inventory** — every place "Debian" surfaces
   in a vanilla Debian 13 system is cataloged.
2. **Legal-floor honest** — trademark + DFSG + GPL/AGPL preserve
   list is explicit; the whitelabel mechanism (PR 8) will respect
   it.
3. **Substrate-agnostic** — surfaces are the same regardless of
   substrate; the mechanism for rebranding varies but the audit
   targets stay constant.
4. **Distro-axis flexible** — if Q-016 picks a non-Debian base,
   the methodology + legal framework translates surface-for-surface
   (e.g., `/etc/redhat-release` analogue).
5. **Telemetry sovereignty** — phone-home defaults are systematically
   blocked via the schema's `packages.deny` list.
6. **PR 8 ready** — the categorization + approach hints in this audit
   feed directly into SDD-007's mechanism specification.

## Non-goals (this SDD)

- Does NOT specify the rebrand mechanism. That's SDD-007 / PR 8.
- Does NOT commit a brand identity (name, palette, logo). Q-003 stays
  open.
- Does NOT decide between public-distribution vs internal-use scope.
  Q-004 resolves at Gate 4.
- Does NOT author the rebranding scripts. Stage 2+ ships scripts; this
  PR ships the surface catalog only.
- Does NOT audit non-Debian distros surface-for-surface. If Q-016
  picks a different distro at Gate 2, a successor SDD (or this one
  revised) catalogs the chosen distro's surfaces.

## Open sub-questions

- **Q7-A** — Should sovereign-os define its own logo asset (SVG +
  PNG + Plymouth) NOW (PR 8 ready) or DEFER until Q-003 brand
  identity resolves? Recommendation: defer asset commit; PR 8
  ships a placeholder logo. <!-- anti-min-waiver: R480 placeholder-logo-anchored-to-Q-003-brand-identity-commit-per-SDD-012-deferred-with-criteria -->
- **Q7-B** — Bug-report URL: should it point to the sovereign-os
  GitHub issues page, or a separate sovereignty-distinct issue
  tracker? Recommendation: GitHub issues for now (operator-owned). <!-- anti-min-waiver: R480 GitHub-issues-recommendation-is-architectural-choice-anchored-to-Stage-4-fleet-mode-issue-tracker-decision -->
- **Q7-C** — Should `/etc/sovereign-version` ship as a sovereign
  analogue to `/etc/debian_version`? If yes, what semantics
  (date-versioned / semver / git-sha)?
- **Q7-D** — Should the whitelabel mechanism (PR 8) ship `dpkg-divert`
  rules for `/etc/issue` etc. so that package updates don't
  silently restore Debian-branded content? Strongly recommended;
  PR 8 will lock this.
- **Q7-E** — Documentation surfaces: does the operator want a
  `sovereign-os(7)` overview manpage to ship in PR 8 or defer to a
  Stage-2+ docs PR?

## Way forward

1. **PR 7 (this PR)** — surface audit + categorization + legal floor.
2. **PR 8** — whitelabel mechanism (SDD-007). Each surface gets a
   per-surface strategy (template-substitution / file-overlay /
   package-replacement / build-time-flag). Stage Gate 4 fires after.
3. **Q-004 closure** at Gate 4 — operator picks scope
   (public-distribution vs internal-use).
4. **Stage 2+** — the actual rebranding scripts execute these
   strategies during build / install / first-boot.

## Cross-references

- Charter: `docs/sdd/000-charter.md` (sovereignty principles + "Debian as Ark" framing)
- SDD-001 cross-repo boundaries: `docs/sdd/001-cross-repo-boundaries.md`
- SDD-003 substrate survey (Q-016 distro-base; this audit assumes Debian per working hypothesis): `docs/sdd/003-substrate-survey.md`
- SDD-004 profile schema (`whitelabel` binding key consumes this audit): `docs/sdd/004-profile-schema.md`
- Future SDD-007 whitelabel mechanism (PR 8) — consumes this audit
- Decisions log: `docs/decisions.md` Q-003 + Q-004 (Q-004 resolves at Gate 4)
- Plan-agent macro-arc § PR 7: info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
- Operator "Debian as Ark" directive: info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md`
- L1 source-synthesis (Debian system context for whitelabel): info-hub `wiki/sources/src-sain-01-sovereign-node-spec.md`
- Debian trademark policy: https://www.debian.org/trademark
- DFSG: https://www.debian.org/social_contract#guidelines
