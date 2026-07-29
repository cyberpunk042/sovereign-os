# Pre-flight — before you write an installer to SAIN-01

Everything here is cheap. The alternative to running it is an 18-minute boot
that ends in a black screen, which is how 2026-07-28 went three times, and the
fourth attempt left the other NVMe with a bootloader that had no entries.

Nothing on this page writes to a disk.

## 1. Confirm WHICH artifact you are about to flash

Both distros write into the same `build/<profile>/output/`, and both installer
ISOs end in `-installer.iso`. The name carries the distro:

| file | distro | installs |
|---|---|---|
| `sain-01-debian-installer.iso` | Debian 13 (trixie) | d-i + preseed, KDE on X11 |
| `sain-01-ubuntu-installer.iso` | Ubuntu 26.04 (resolute) | Subiquity + autoinstall, KDE on Wayland |
| `sain-01-<distro>.raw` | either | the mkosi appliance (dd whole-disk) |

```sh
sha256sum -c build/sain-01/output/sha256sums.txt
```

The flash panel names the distro on every row and warns when artifacts for more
than one are present. **Read the distro on the row before arming.** Flashing the
wrong one to an internal disk is not a recoverable mistake.

A legacy `sain-01-installer.iso` with no distro segment is a Debian ISO built
before 2026-07-29. If both it and `sain-01-debian-installer.iso` are present,
the older one is superseded — delete it so there is only one Debian row.

## 2. Check the ISO carries THIS tree

```sh
SOVEREIGN_OS_ARTIFACT=installer SOVEREIGN_OS_DISTRO=ubuntu \
  scripts/build/09-image-verify.sh
```

Confirms the ISO is bootable (two El Torito images: BIOS + UEFI) and that its
answer file still matches the repo — the driver, the DRM cmdline, the display
manager selection and the custom kernel. It refuses with **"do NOT flash this
ISO — rebuild first"** if any are missing.

This exists because a build that produced nothing once reported success and the
operator flashed a five-hour-old ISO twice, believing it was fresh.

## 3. Install it in a VM first

```sh
sovereign-osctl install verify-iso --distro ubuntu
```

40–60 minutes, unattended, on a throwaway qcow2. Nothing on the host is touched.
It installs to completion and then reads the resulting disk from outside,
asserting the things that decide whether the machine is usable:

- a route to a graphical seat exists (per-distro — see §4)
- the custom znver5 kernel landed and GRUB defaults to it
- `sddm` owns `display-manager.service`
- the cockpit payload and profile are present
- the dashboards deploy reported `ok`
- the install's own self-check found no problems

Current status: **Debian 15/15, Ubuntu 16/16.**

## 4. Know which display route your distro takes

They are opposite, and the wrong one is a silent total failure:

| | Debian 13 | Ubuntu 26.04 |
|---|---|---|
| Plasma session | X11 (`plasmax11.desktop`) | **Wayland only** (`/usr/share/xsessions` is EMPTY) |
| kernel cmdline | `nomodeset` | `nvidia-drm.modeset=1` |
| udev route | rules 23/28 tag `fb0` | rule 35 tags `card0` |
| needs | nothing | the NVIDIA driver actually installed |

`nomodeset` on Ubuntu guarantees there is no session the display manager can
start. Proven on a real disk: stripping it took the same install from a blinking
cursor to the Kubuntu greeter.

**Ubuntu's route depends on hardware this has never run on.** The VM has no
Blackwell GPU; `nvidia-driver-570-open` is verified *installed*, not verified
*working* on an RTX 5090. If Ubuntu boots to a blinking cursor on SAIN-01, that
is the open question — not a regression in the installer.

## 5. At the machine, first boot

```sh
loginctl show-seat seat0 -p CanGraphical     # must be yes
cat /var/log/sovereign-os/install-verify.log # the install's own verdict
cat /var/lib/sovereign-os/dashboards-install.status
```

`CanGraphical=no` with zero failed units is the 2026-07-28 signature: the
machine is healthy and blank, sddm waiting forever for a graphical seat with no
error, no failed unit and no `Xorg.0.log`.

If the screen is dark, read the log rather than power-cycling — it names the
cause and the fix command.

## 6. If it went wrong, read the disk from outside

```sh
sovereign-osctl install inspect-disk /dev/nvme0n1
```

Read-only and unprivileged. Understands both layouts (Ubuntu's plain ext4 and
Debian's `sovereign/root` LV) and reports the same assertions as §3 — so a
machine that will not boot can still be diagnosed without booting it.

## What this page does NOT cover

- **Secure Boot.** Step 08 skips MOK signing for an ISO and relies on the
  distro's signed shim chain. Review before trusting `secureboot=signed` on
  Ubuntu.
- **The appliance path.** `sain-01-<distro>.raw` is `dd`-ed whole-disk rather
  than installed; the Ubuntu appliance has not been built.
- **The ESP on a reused disk.** The preseed clears a stale sovereign UKI and
  systemd-boot and forces GRUB into the removable-media fallback, but it never
  touches another OS's bootloader. On a shared disk, check `EFI/` yourself.
