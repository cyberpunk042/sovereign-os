# Whitelabel surface inventory (PR 7 / SDD-006)

Audit-grade catalog of ~50 Debian identity surfaces, categorized into 6 buckets. Full content: [`docs/sdd/006-debian-surface-audit.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/sdd/006-debian-surface-audit.md).

## Categorization summary

| Category | Count | Examples |
|---|---|---|
| **must-rebrand** | 16 | `/etc/os-release`, `/etc/issue`, `/etc/lsb-release`, `/etc/motd`, GRUB menu, Plymouth, GDM/SDDM, installer banners, kernel package name, BUG_REPORT_URL |
| **should-rebrand** | 8 | `/etc/update-motd.d/`, GRUB theme/background, desktop wallpapers, login-manager themes, lock screens, desktop-base, hostname pattern |
| **may-leave** | 12 | `dpkg-vendor`, `/etc/dpkg/origins/default`, APT sources, APT config, manpage doc paths, NTP defaults |
| **must-not-touch (legal floor)** | 7 | `/etc/debian_version` (provenance), `/usr/share/doc/*/copyright` (attribution), upstream manpages, Debian-trademark assets, GPL/AGPL attribution chains |
| **must-create** | 2 | `/etc/dpkg/origins/sovereign`, `/etc/apt/sources.list.d/sovereign.sources` |
| **must-not-install** | 5 | `popularity-contest`, `apport`, `whoopsie`, `motd-news`, `snapd`, `ubuntu-advantage-tools` |

## 10 surface sections (SDD-006)

- A — Identity surfaces (filesystem)
- B — Package-manager surfaces
- C — Boot surfaces (GRUB, Plymouth, systemd-boot)
- D — Installer surfaces (debian-installer / Calamares; Q-008-conditional)
- E — Desktop / display-manager surfaces
- F — Kernel surfaces (`/proc/version`, `uname -a`, `CONFIG_LOCALVERSION`, `KBUILD_BUILD_USER`)
- G — Documentation surfaces (legal floor heaviest)
- H — Network surfaces
- I — Telemetry / phone-home surfaces (sovereignty-critical)
- J — Substrate-specific surfaces

## Legal floor (enforced at validation time)

The render engine (`scripts/whitelabel/render.py`) refuses to write to any path matching:

- `/etc/debian_version`
- `/usr/share/doc/*/copyright`
- `/usr/share/man/*`
- `*/debian-logo*`
- `*/debian-swirl*`

A whitelabel YAML that declares a `surfaces:` entry matching these patterns fails with exit code 4.
