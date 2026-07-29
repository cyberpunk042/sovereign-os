# Standing directive — Ubuntu 26.04 LTS is a SECOND distro option, not a replacement

**Status**: ACTIVE (operator directive, 2026-07-28, logged during the work)
**Audience**: every session touching `SOVEREIGN_OS_DISTRO`, the build panel's
distro control, `scripts/build/lib/distro.sh`, `scripts/build/ubuntu-autoinstall/*`,
the mkosi adapter, or SDD-013
**Extends**: [2026-07-25-installer-onto-nvme.md](2026-07-25-installer-onto-nvme.md)
and [2026-07-26-the-normal-debian-13-installer.md](2026-07-26-the-normal-debian-13-installer.md).
Neither is superseded — this generalises them to a second distribution.

## Verbatim operator statements (sacrosanct — do not paraphrase)

> "lets add a ubuntu 26 version, instead of debian 13.. it will be a new option
> in the panel"

> "new custom kernel... the whole deal...it was always the goal, and flexibility
> of hardware."

## What this directive establishes

1. **Distro is a FIRST-CLASS AXIS, orthogonal to substrate.**
   `SOVEREIGN_OS_DISTRO` ∈ {`debian`, `ubuntu`}, defaulting to `debian` so every
   existing build, profile and test keeps its behaviour. The suite is DERIVED
   (`debian`→`trixie`, `ubuntu`→`resolute`); `SOVEREIGN_OS_SUITE` remains an
   explicit override. The single source is `scripts/build/lib/distro.sh`.

2. **"The normal installer" is per-distro, and they are not interchangeable.**
   The 2026-07-26 requirement — the operator gets the STANDARD installer, never
   a bespoke launcher — now has two implementations, because Ubuntu dropped
   debian-installer at 20.04 and Subiquity does not read debconf preseeds:

   | ARTIFACT | DISTRO=debian | DISTRO=ubuntu |
   |---|---|---|
   | `image` | `mkosi` | `mkosi` |
   | `installer` | `installer-cdd` (d-i + preseed) | `ubuntu-autoinstall` (Subiquity + autoinstall YAML) |
   | `installer-live` | `live-build` | `live-build` *(untested on Ubuntu)* |

   Handing an Ubuntu operator the d-i path — or vice versa — is the same class
   of failure as handing them the whiptail TUI.

3. **Nothing about Debian changes.** `debian` is the default everywhere. A build
   that sets no distro must be byte-identical to what it was.

4. **The desktop stays KDE Plasma on both** (`task-kde-desktop` on Debian,
   `kubuntu-desktop` on Ubuntu), so `SOVEREIGN_OS_FRONTEND=kde-plasma` and the
   GUI dashboards deploy are identical across distros.

5. **The custom kernel is distro-agnostic and stays that way.** `kernel.source:
   kernel.org-stable` + `bindeb-pkg` builds the same znver5 kernel for either
   target; the `KCFLAGS` are derived from the CPU, not the OS. Adding a distro
   must never fork the kernel path.

## The two hazards this axis introduces (both now lint-enforced)

- **A distro switch must invalidate the build cache.** Debian and Ubuntu builds
  share a profile and a repo, so without `distro` in each step's `inputs_hash`
  the pipeline would report "already completed with matching inputs", skip, and
  hand the operator a Debian ISO labelled Ubuntu. That is the 2026-07-26
  stale-artifact failure one axis over. Enforced for steps 05/07/08/09 by
  `tests/lint/test_every_substrate_is_handled_end_to_end.py`.

- **The two installers must install the same system.** There is a
  `pkgsel/include` line and an autoinstall `packages:` list, and nothing
  structural stops them drifting — the exact shape that once put 37 packages in
  the mirror list and none in the install list. Enforced by
  `tests/lint/test_ubuntu_autoinstall_matches_the_debian_installer.py`, which
  compares them through the real mapping in `distro.sh`.

## Not yet proven (do not claim otherwise)

No Ubuntu ISO has been built. The `xorriso` remaster, the
`autoinstall ds=nocloud` boot argument and Subiquity's acceptance of the shipped
`user-data` are unverified until a real build runs. `live-build` on Ubuntu is
wired but untested (Ubuntu uses `livecd-rootfs`). Secure Boot needs review before
`secureboot=signed` is trusted on Ubuntu — step 08 assumes the Debian shim layout.

## Cross-references

- Axis + mapping: `scripts/build/lib/distro.sh`, `scripts/build/orchestrate.sh`
- Ubuntu installer: `scripts/build/ubuntu-autoinstall/{build.sh,autoinstall/user-data}`
- Shared cockpit package: `scripts/build/lib/cockpit-deb.sh` (both installers)
- Panel: `webapp/build-configurator/index.html` (`#distro`), `scripts/operator/build-configurator-api.py`
- SDD: `docs/sdd/013-installer-experience.md` (2026-07-28 amendment)
