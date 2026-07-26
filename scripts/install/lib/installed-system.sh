#!/usr/bin/env bash
# scripts/install/lib/installed-system.sh — the ONE definition of what an
# installed sovereign-os system contains.
#
# WHY THIS EXISTS (2026-07-26). Two installer surfaces ship, per the
# 2026-07-25 directive:
#
#   (a) sovereign-osctl install system   → scripts/install/install-sovereign-root.sh
#   (b) the bootable installer USB       → scripts/build/build-target-rootfs.sh
#
# Both debootstrap a root and both installed the SAME hand-copied package list —
# the minimum needed to boot. Nothing in it opened a terminal, so the operator
# booted a KDE desktop with no way to get a shell: "there was not even a console
# tool installed and a lot was missing." Fixing surface (a) alone would have left
# (b) building exactly the same unusable machine, and the two would keep drifting
# apart every time either was touched.
#
# So: define it once, source it from both. A fix lands in both surfaces or
# neither. tests/lint/test_installed_system_is_a_workstation.py enforces that
# both really source this file rather than re-inlining a list.
#
# Every name here is verified to exist in the target suite by the lint —
# `dnsutils` was already wrong (transitional; trixie has bind9-dnsutils) and
# would have failed the whole apt-get install at install time.
#
# Tunables (set BEFORE sourcing):
#   SOVEREIGN_OS_INSTALL_GUI=0            headless — drops the GUI-only packages
#   SOVEREIGN_OS_WORKSTATION_PACKAGES=…   replace the workstation set wholesale
#                                         (set to "" for a truly minimal root)
#   SOVEREIGN_OS_KERNEL_CMDLINE=…         override the installed kernel cmdline

[ -n "${__SOVEREIGN_OS_INSTALLED_SYSTEM_SH:-}" ] && return 0
__SOVEREIGN_OS_INSTALLED_SYSTEM_SH=1

# ── BASE: what the system needs to boot and be managed at all ────────────────
# lvm2/grub/efibootmgr/initramfs — the boot chain onto the sovereign-root LV.
# systemd-resolved is NOT optional: networkd publishes DNS only through its
# stub resolver, and without it glibc has no resolver at all — that is what
# made every first-boot download fail with "Could not resolve host".
SOVEREIGN_OS_BASE_PACKAGES="${SOVEREIGN_OS_BASE_PACKAGES:-\
lvm2 grub-efi-amd64 efibootmgr initramfs-tools \
sudo locales console-setup keyboard-configuration \
systemd-resolved netbase iproute2 isc-dhcp-client \
python3 python3-yaml python3-jsonschema prometheus-node-exporter \
ca-certificates curl nano less}"

# ── WORKSTATION: what makes it usable by a person ────────────────────────────
#   console    a terminal you can open from the desktop, a multiplexer, a real
#              editor. xterm is the fallback that still works when the Plasma
#              session itself is broken.
#   hardware   what you reach for when a GPU/disk/USB misbehaves. This box has
#              three GPUs and two NVMe; diagnosing it on a framebuffer console
#              with no lspci is miserable.
#   fs/net     everyday moving-things-around and looking-at-the-network.
#   xfallback  `modesetting` needs a DRM device that `nomodeset` prevents, and
#              `nvidia` will not bind on Blackwell — without fbdev/vesa the X
#              server cannot start AT ALL and the desktop is a black screen on
#              a perfectly healthy system (the appliance's
#              "sddm: Failed to read display number from pipe").
#   firmware   The kernel is CONFIG_DRM_AMDGPU=m with CONFIG_EXTRA_FIRMWARE="",
#              so amdgpu loads at runtime and asks the FILESYSTEM for its blobs.
#              A Ryzen 9 9900X carries a Granite Ridge iGPU [1002:13c0]; with no
#              firmware-amd-graphics installed the module dies with "amdgpu:
#              Fatal error during GPU init" and the boot stops dead — on a
#              machine whose real GPUs are NVIDIA (2026-07-26). These are the
#              exact packages the operator's working Debian 13 carries on this
#              same hardware. non-free-firmware is already in the CD mirror.
_sovos_ws_console="konsole xterm tmux vim bash-completion man-db"
_sovos_ws_hardware="pciutils usbutils nvme-cli smartmontools lshw dmidecode lm-sensors htop"
_sovos_ws_fsnet="rsync wget git file tree lsof iputils-ping bind9-dnsutils ncdu"
_sovos_ws_xfallback="xserver-xorg-video-fbdev xserver-xorg-video-vesa"
_sovos_ws_firmware="amd64-microcode firmware-amd-graphics firmware-nvidia-graphics firmware-linux-free firmware-misc-nonfree"

if [ "${SOVEREIGN_OS_INSTALL_GUI:-1}" != 1 ]; then
  _sovos_ws_console="tmux vim bash-completion man-db"   # no X client on a headless root
  _sovos_ws_xfallback=""
fi

SOVEREIGN_OS_WORKSTATION_PACKAGES="${SOVEREIGN_OS_WORKSTATION_PACKAGES-${_sovos_ws_console} ${_sovos_ws_hardware} ${_sovos_ws_fsnet} ${_sovos_ws_xfallback} ${_sovos_ws_firmware}}"

# ── KERNEL CMDLINE for the installed system ──────────────────────────────────
# Both installers used to hardcode `root=… rw` and ignore the profile. On this
# hardware that is a dark screen: with KMS enabled nouveau binds the Blackwell
# cards and fails, and nvidia will not probe them either. The operator's own
# working Debian on this board boots with `nomodeset` and renders through the
# EFI framebuffer.
#
# No `console=` on purpose. The kernel gives /dev/console to the LAST console=
# listed, so `console=ttyS0` alone sent every message and every getty to an
# unplugged serial port and left the monitor on the bootloader's cursor — the
# "frozen underscore" that cost several build-and-flash cycles. With none set,
# /dev/console is tty0: the physical screen.
SOVEREIGN_OS_KERNEL_CMDLINE="${SOVEREIGN_OS_KERNEL_CMDLINE:-nomodeset}"

# All packages to install into an installed root, base first.
sovereign_os_installed_packages() {
  printf '%s %s\n' "${SOVEREIGN_OS_BASE_PACKAGES}" "${SOVEREIGN_OS_WORKSTATION_PACKAGES}"
}
