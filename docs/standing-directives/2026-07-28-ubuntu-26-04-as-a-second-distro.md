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

**Debian 13 — BUILDS, as of attempt 8 on 2026-07-29.**
`sain-01-installer.iso` (1.4 GB) built end to end, and the image was verified to
carry all three components and every previously-missing package:

    /dists/trixie/{main,contrib,non-free-firmware}
    /pool/non-free-firmware/f/firmware-nonfree/firmware-{amd-graphics,misc-nonfree,nvidia-graphics}_20250410-2_all.deb
    /pool/non-free-firmware/a/amd64-microcode/…  /pool/non-free-firmware/i/intel-microcode/…

**Root cause — a simple-cdd bug, not our configuration.** debian-cd's
`tools/which_deb` gates the non-free components on `$ENV{NONFREE}`.
`/usr/bin/build-simple-cdd` gets that variable wrong twice:

  * line 119 `self.env.set("NONFREE", "")` — unconditionally CLOBBERS an
    inherited `NONFREE=1`, so exporting it from `build.sh` does nothing.
  * line 144 only flips it on for the LITERAL component `non-free`;
    `non-free-firmware` — a separate component since Debian 12 — never matches.

That produced the catch-22 recorded above: list `non-free` to flip the flag and
the component mirrors EMPTY, so dose3 dies on a missing `Packages.gz`; omit it
and the firmware is silently never placed, with all five packages sitting
correctly in the mirror.

**The fix** is `scripts/build/installer-cdd/profiles/sovereign.conf`. Profile
`.conf` files are read at line 121-124, AFTER the clobber, and nothing later
resets `NONFREE`. There is a second trap: `simple_cdd/env.py:365-367` adopts a
conf value only when it DIFFERS from the ambient environment, so setting it in
BOTH places is the same as setting it in neither — `build.sh` must leave both
variables unset. Verified against simple-cdd's own `Environment` class with a
negative control, and pinned by
`tests/lint/test_simple_cdd_actually_receives_our_component_config.py`.

`contrib` is populated for real by `zfsutils-linux` (the profile already ships
`sovereign-zfs-arc-clamp.service` and `sovereign-zfs-scrub.{service,timer}`), so
no component in the list is aspirational.

One more defect the build found: step 07's NON-ROOT branch invoked the builder
without `SOVEREIGN_OS_BUILD_OUT=${_out}`, which the root branch passes. The
builder inherited `build/<profile>` and wrote a perfectly good ISO one directory
above where the flash panel looks; the step then reported "exited 0 but produced
NO .iso" after an hour.

**Debian INSTALLS, verified 15/15 in a VM (2026-07-29).** The ISO was installed
to completion on a throwaway qcow2 and the resulting disk read back from
outside. Every fault behind the 2026-07-28 dark screen is confirmed fixed:

    PASS  nomodeset IS on the installed kernel command line
    PASS  a route to a graphical seat exists (udev can tag master-of-seat)
    PASS  custom znver5 kernel installed (vmlinuz-6.12.0)
    PASS  initramfs for 6.12.0 generated
    PASS  GRUB default pinned to the custom kernel
    PASS  display manager: sddm
    PASS  cockpit payload present at /opt/sovereign-os
    PASS  active-profile written (sain-01)
    PASS  installed: dkms / build-essential / xdg-utils / sddm
    PASS  install self-check ran, and found no problems
    PASS  dashboards deploy: ok

The installed system's own report confirms `firmware-amd-graphics ok` — the
NONFREE fix carries all the way through to the target, not merely onto the ISO.
`dashboards deploy: ok` closes the 2026-07-28 one-second bail.

The harness is `scripts/build/installer-cdd/verify-full-install-in-vm.sh`. It
extracts the SHIPPED preseed from the built ISO, appends VM-only answers (the
destructive confirmations and a per-run throwaway password) into scratch, and
proves by read-back that the remastered ISO carries them before spending an
hour. Nothing generated is written to the repo or to a shipped artifact.

The first real install immediately exposed two inspector bugs that no synthetic
test had, both now regression-tested:

  * `grep -c` EXITS 1 when the count is zero while still printing "0", so the
    `|| echo 0` fallback appended a SECOND line and the arithmetic test died —
    reporting a FAIL on an install whose self-check was clean. Same trap as
    440f65b8.
  * `/etc/os-release` is a SYMLINK to `../usr/lib/os-release` and debugfs
    `dump` does not follow symlinks, so the distro read back "unknown" and
    silently defaulted to Debian. On an Ubuntu disk that reports the CORRECT
    configuration as a failure.

Still unproven for Debian: the ISO has not been installed on the REAL SAIN-01,
and a VM has no Blackwell GPU. What the VM cannot answer is whether the display
comes up on that hardware — only that everything the installer controls is now
correct.

## The Ubuntu APPLIANCE (mkosi .raw) — audited 2026-07-30, not yet built

`ARTIFACT=image DISTRO=ubuntu` has never been built. Audited statically first,
because the alternative is discovering each fault after a multi-GB buildroot
download.

**What was broken.** The mkosi adapter emitted a BYTE-IDENTICAL 45-package list
for both distros — it never called `distro_map_packages()` at all, though it had
existed since 2026-07-28 and both INSTALLERS used it. Four of those names do not
exist in the Ubuntu archive (checked against the live resolute index):

    firefox-esr              -> firefox
    nvidia-driver            -\
    nvidia-open-kernel-dkms  --> nvidia-driver-570-open   (ONE versioned
    nvidia-smi               -/    metapackage; not a 1:1 rename)

The build would have failed at package install. After the fix: Ubuntu 43/43
present in resolute, Debian 45/45 unchanged in trixie. The adapter now calls the
shared function rather than keeping a copy, and logs every substitution.

**What audited CLEAN.** The in-image postinst has no Debian-specific
apt/mirror/firmware assumptions (the appliance deliberately ships without apt).
`Repositories`/`Release`/`Distribution`/`Output` all render per distro. The
repart layout is distro-agnostic (vfat ESP + ext4 root). None of the 22
first-boot hooks names a Debian-only package.

**The two NVIDIA strategies do NOT collide.** Debian uses the `.run` installer
because trixie ships 550, which predates Blackwell; Ubuntu installs the packaged
`nvidia-driver-570-open`. `nvidia-driver-install.sh` queries
`nvidia-smi --query-gpu=driver_version` and no-ops at >= 570, so on Ubuntu the
packaged driver satisfies it, and `ConditionVirtualization=no` keeps it out of
VMs. Nothing to change.

**Operator decisions for the first build (2026-07-30).** Both blockers are
deliberate safety gates, not bugs:

  * `SOVEREIGN_OS_ROOT_PASSWORD` unset makes mkosi LOCK root, producing an image
    that boots to a prompt nobody can satisfy — it shipped once, looking "done +
    preflight-passed" (2026-07-03). The operator supplies a bootstrap password;
    `first-login-assistant.sh` rotates it on first boot.
  * `secure_boot: signed` needs an operator MOK. For the FIRST build on a
    never-executed path the operator chose **unsigned**, because that key is a
    long-lived identity — the firmware enrols it and the NVIDIA `.run` signs its
    modules against it (sain-01.yaml:460), so a throwaway would break every
    later signed kernel and rebuilt module.

`SOVEREIGN_OS_SECURE_BOOT` was added for this: a DOWNGRADE-ONLY override so a
build can run unsigned without editing the tracked profile. It refuses to
strengthen (claiming `signed` from the environment would let a build assert a
posture the profile never declared — that belongs in git), and it never
downgrades silently.

## WHY EVERY UBUNTU ATTEMPT REACHED A DEAD LOGIN — 2026-07-30

The operator: *"any of them there is a deadend… I can build and flash but I get
nowhere interesting after I boot."* Three Ubuntu artifacts, three dead logins,
while Debian on the same machine was fine.

**The fact that explains all of it.** The operator's WORKING Debian desktop has
**no `/dev/dri` at all** — verified on the running system. It draws X11 straight
onto the EFI framebuffer (`CONFIG_FB_EFI=y`). X11 can do that. **Wayland cannot.**
Ubuntu 26.04's Plasma is Wayland-only, so it REQUIRES a DRM device — and the
custom kernel could produce one only if the NVIDIA driver bound to Blackwell,
because the config it is seeded from carries:

    # CONFIG_SYSFB_SIMPLEFB is not set
    # CONFIG_DRM_SIMPLEDRM is not set

`simpledrm` is the modern fallback that turns the firmware framebuffer into a
real DRM device with NO GPU driver. Stock Ubuntu ships it; Debian's config does
not, so the custom kernel inherited a hole invisible on Debian and fatal on
Ubuntu. "The driver did not bind" and "the machine is unusable" were the same
event. Both symbols are now in `profiles/sain-01.yaml` → `kernel.config.enable`;
step 03 already reports symbols that do not survive `olddefconfig`.

**Two further faults, each sufficient alone:**

  * `nomodeset` was baked into the appliance's UKI. `distro_kernel_cmdline()`
    had translated the ISO path since 2026-07-29 but `mkosi-emit` never called
    it — one path fixed, one forgotten, and the forgotten one reached hardware.

  * mkosi runs `systemctl preset-all`, which enables EVERY unit in
    /etc/systemd/system carrying `[Install]`. That re-enabled
    `sovereign-frontend-kiosk.service` — a fullscreen browser —
    *after* install-gui-dashboards.sh had deliberately disabled it for a desktop
    frontend, so the appliance booted with sddm AND a kiosk contending for the
    display. The ISO path never runs preset-all, which is why the ISO-installed
    system was clean and the two installers disagreed for an invisible reason.
    This repo had already hit the trap with the selfdef fleet. Now stated
    declaratively in a systemd preset, the mechanism preset-all obeys.

**Why nothing caught it: QEMU always provides a DRM device.** The ISO scored
16/16 in a VM on an image that cannot reach a desktop on the real box. That is a
structural blind spot, not bad luck — no VM run can falsify the display path.

**And the inspector was worse than useless on the one artifact that mattered.**
It scored the failing appliance 9/9 while asserting:

    "the kernel cmdline is embedded in the UKI, so the seat route is set at
     build time, not readable from grub.cfg here."

The cmdline is a PE section (`.cmdline`) inside the `.efi` and reads out in a few
lines. It declared a limitation instead of testing one — and was wrong. It now
reads the UKI cmdline, reads the kernel config off the ESP, prefers
`/etc/sovereign-os/base-distro` over the whitelabelled `os-release` (which says
`ID=sovereign` and made an Ubuntu appliance read as Debian, skipping every
Ubuntu check), and states plainly what it CANNOT establish: whether the driver
binds on real hardware.

Detection now matches reality: the failing appliance FAILS, the 16/16 ISO
install FAILS on the missing DRM fallback, and Debian is correctly unaffected.

**Still unproven, and only the hardware can answer it:** whether the NVIDIA
driver binds to Blackwell under 6.12.0. With `simpledrm` there is a desktop
either way; that question decides whether it is a desktop *with GPUs*.

## BOTH installers verified end to end in a VM, 2026-07-29

Run via `sovereign-osctl install verify-iso [--distro debian|ubuntu]`, against
the SHIPPED ISOs, after both were rebuilt under the distro-qualified naming rule
([2026-07-29-artifacts-must-name-their-distro.md](2026-07-29-artifacts-must-name-their-distro.md)):

| | Debian 13 | Ubuntu 26.04 |
|---|---|---|
| artifact | `sain-01-debian-installer.iso` (1.3 GB) | `sain-01-ubuntu-installer.iso` (6.2 GB) |
| seat route | `nomodeset` (udev 23/28) | `nvidia-drm.modeset=1` (udev rule 35) |
| result | **15 passed, 0 failed** | **16 passed, 0 failed** |

Both carry a cockpit byte-identical to the repo, so the on-box self-check is the
current one. Both report `install self-check ran, and found no problems` and
`dashboards deploy: ok` — the latter closes the 2026-07-28 one-second bail.

Ubuntu's run confirms the whole NVIDIA decision on a real install:
`nomodeset correctly ABSENT`, `nvidia-drm.modeset=1` on the installed cmdline,
and an `nvidia-driver-*` package actually installed — the option is inert
without the module, so all three had to be true together.

**Three checker bugs the real installs found that no synthetic test had**, all
now regression-tested:

  * GRUB's RECOVERY menuentry always carries `nomodeset` (Ubuntu) or `single`
    (Debian) — that is what recovery mode IS. Grepping every `linux` line
    therefore reported `nomodeset IS SET — FATAL` on a PERFECTLY CORRECT Ubuntu
    install. A checker that cries wolf on correct installs is how real signals
    get ignored.
  * `grep -c` exits 1 when the count is zero while still printing "0", so a
    `|| echo 0` fallback appended a second line and the arithmetic died —
    reporting a FAIL on a clean self-check. Same trap as 440f65b8.
  * `/etc/os-release` is a SYMLINK and debugfs `dump` does not follow it, so the
    distro read back "unknown" and silently defaulted to Debian — which on an
    Ubuntu disk reports the CORRECT configuration as a failure.

**What a VM still cannot answer.** There is no Blackwell GPU in qemu. Everything
the installer controls is verified on both distros; whether the RTX 5090 lights
up on SAIN-01 — Ubuntu's whole display strategy depends on it — is open until
the box is flashed and booted.

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

**RESOLVED 2026-07-29 — operator decision: the NVIDIA proprietary driver.**

Ubuntu takes udev rule 35 (a bound KMS driver), not rules 23/28 (fb0 under
nomodeset). `nvidia-driver-570-open` is installed by the autoinstall and
`nvidia-drm.modeset=1` replaces `nomodeset` on the installed cmdline. The
`-open` variant is REQUIRED, not preferred: NVIDIA's proprietary kernel
module does not support Blackwell (GB202). The version tracks the profile's
`driver: nvidia-570-open`, and 26.04 packages 570-595 in `restricted`, so
unlike Debian — whose trixie archive ships 550, predating Blackwell — no
`.run` installer is needed.

This also makes the RTX 5090 available for inference, which `nomodeset`
precludes. On an AI appliance that was always the better answer.

Single-sourced in two places, both exercised by lint rather than grepped:
`distro_kernel_cmdline()` (build side, `scripts/build/lib/distro.sh`) and
`target_seat_route()` / `target_seat_cmdline_option()` (runtime side,
`scripts/install/lib/target-distro.sh`). The Ubuntu builder REFUSES to build
if the rendered cmdline still contains `nomodeset`. Enforced by
`tests/lint/test_ubuntu_gets_a_drm_device.py` (11 tests, each proven to bite).

**Not yet proven:** the driver has never been installed on the real SAIN-01.
The autoinstall pulls it from the archive, so the install needs network; and
dkms must build the module against the custom znver5 kernel. Neither is
verified on hardware.

**The original framing, kept because it is what forced the decision.** Removing nomodeset works in a VM because
bochs-drm binds. On the SAIN-01 hardware (Blackwell RTX 5090) nouveau fails on
that chipset — which is why nomodeset exists. Without nomodeset AND without a
working KMS driver, Ubuntu lands in the same place. The likely answer for
Ubuntu + Blackwell is the proprietary NVIDIA driver providing DRM (the
`nvidia-drm.modeset=1` path the profile already contemplates and which
`persist-kernel-cmdline.sh` already refuses to clobber), NOT nomodeset.

That is a hardware-strategy decision for the operator, so nothing here changes
the profile's cmdline unilaterally. What IS changed: the installed-system checks
now treat nomodeset-on-Ubuntu as a PROBLEM rather than the desired state.
