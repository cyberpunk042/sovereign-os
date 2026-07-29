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

*(Superseded in part — see "Build status, recorded 2026-07-29" below. The
`xorriso` remaster, the `autoinstall ds=nocloud` boot argument and Subiquity's
acceptance of the answer file are now PROVEN by a real build and an A/B boot.)*

Still unproven: the install has never been allowed to RUN to completion, so
nothing downstream of the disk pick is verified — the `late-commands`, the custom
kernel landing via `dpkg -i`, `nomodeset` reaching the installed `grub.cfg`, or
`loginctl show-seat seat0 -p CanGraphical` returning `yes` on the installed
system. `live-build` on Ubuntu is wired but untested (Ubuntu uses
`livecd-rootfs`). Secure Boot needs review before `secureboot=signed` is trusted
on Ubuntu — step 08 skips MOK signing for an ISO and relies on the distro's
signed shim chain.

## Cross-references

- Axis + mapping: `scripts/build/lib/distro.sh`, `scripts/build/orchestrate.sh`
- Ubuntu installer: `scripts/build/ubuntu-autoinstall/{build.sh,autoinstall/user-data}`
- Shared cockpit package: `scripts/build/lib/cockpit-deb.sh` (both installers)
- Panel: `webapp/build-configurator/index.html` (`#distro`), `scripts/operator/build-configurator-api.py`
- SDD: `docs/sdd/013-installer-experience.md` (2026-07-28 amendment)

## Build status, recorded 2026-07-29 (first real builds)

**Ubuntu 26.04 — BUILDS AND BOOTS, autoinstall proven.**
`sain-01-ubuntu-installer.iso` (6.2 GB) built end to end, and an A/B boot under
OVMF proved the seed is consumed: the stock 26.04 ISO waits at "Choose your
language" (step 1 of 17) while ours auto-advances to "Disk setup" (step 11) and
stops there — exactly the `interactive-sections: [storage, identity]` contract.
That satisfies the 2026-07-26 "must be the normal installer" requirement: it IS
Ubuntu's own installer, and it still stops for the disk pick.

Three bugs the real build found that no lint had:
  1. step 01 hard-failed a non-root run on a tmpfs mount — a PERFORMANCE
     optimisation blocking an otherwise-ready build. Now warns and builds on disk.
  2. `WORK="${HERE}/tmp"` put scratch inside the checkout, so packaging the repo
     copied a directory into itself and cp refused.
  3. a bare `WARNING: word` in an unquoted YAML scalar made a whole
     `late-commands` entry parse as a MAPPING. Valid YAML, silently wrong.

**Debian 13 — DOES NOT BUILD YET.** `installer-cdd` fails inside
simple-cdd/debian-cd, and the two observed failure modes pull against each other:

  * with `mirror_components="main contrib non-free non-free-firmware"` (the
    committed state) CD1 gets main=1205 and non-free-firmware=5 — the firmware
    IS placed — but contrib and non-free mirror EMPTY, so CD1 has no
    `Packages.gz` for them and simple-cdd's dose3 pass dies:
        Input file …/CD1/dists/trixie/contrib/binary-amd64/Packages.gz does not exist
    (`build-simple-cdd` line ~613 skips a missing FOREGROUND Packages.gz but
    appends background ones unconditionally.)

  * narrowing to `"main non-free-firmware"` clears distcheck but then the
    firmware is never placed on CD1 at all:
        ERROR: missing required packages from profile sovereign:
          amd64-microcode firmware-amd-graphics firmware-nvidia-graphics
          firmware-misc-nonfree intel-microcode
    — with all five sitting correctly in the mirror. Setting `NONFREE=1`
    (which_deb line 22 only reads `NONFREE_COMPONENTS` when it is truthy) did
    not change this.

Both narrowing attempts were REVERTED; the tree is back to the committed
4-component config. The next session should start here rather than re-deriving
it. Do NOT reuse the scratch tree across a component change —
`SOVEREIGN_OS_CDD_KEEP_TMP=1` leaves a reprepro db built for the old component
set and yields a misleading `undefinedtarget` error.

## nomodeset is a DEBIAN-ONLY workaround — it is fatal on Ubuntu 26.04

Established 2026-07-29 by a controlled experiment on one installed disk.

**The evidence.** A complete Ubuntu 26.04 install, verified 14/15 on disk
(nomodeset present, sddm selected, custom kernel installed, cockpit deployed),
booted to a blinking cursor on black. The same disk, with `nomodeset` stripped
from `/boot/grub/grub.cfg` and nothing else changed, boots to the Kubuntu Plasma
greeter. Screen luminance went from 1e-05 to 0.076.

**Why.** Ubuntu 26.04's Plasma is WAYLAND-ONLY:

    /usr/share/wayland-sessions/  ->  plasma.desktop, ubuntu.desktop
    /usr/share/xsessions/         ->  EMPTY

`plasma-workspace` and `kwin-x11` ship no session `.desktop` at all on Ubuntu
(checked by downloading both .debs). Debian's `plasma-workspace` DOES ship
`/usr/share/xsessions/plasmax11.desktop` — which is why the operator's Debian
box runs X11-on-fbdev happily with nomodeset, and why that workaround was
adopted in the first place.

Wayland needs a DRM device. `nomodeset` is precisely what prevents one. So on
Ubuntu the flag guarantees there is NO session the display manager can start —
the failure is total and silent, exactly like the Debian one it was meant to fix.

**What this does NOT settle.** Removing nomodeset works in a VM because
bochs-drm binds. On the SAIN-01 hardware (Blackwell RTX 5090) nouveau fails on
that chipset — which is why nomodeset exists. Without nomodeset AND without a
working KMS driver, Ubuntu lands in the same place. The likely answer for
Ubuntu + Blackwell is the proprietary NVIDIA driver providing DRM (the
`nvidia-drm.modeset=1` path the profile already contemplates and which
`persist-kernel-cmdline.sh` already refuses to clobber), NOT nomodeset.

That is a hardware-strategy decision for the operator, so nothing here changes
the profile's cmdline unilaterally. What IS changed: the installed-system checks
now treat nomodeset-on-Ubuntu as a PROBLEM rather than the desired state.
