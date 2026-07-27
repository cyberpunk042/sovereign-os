#!/bin/sh
# Self-check for a freshly installed sovereign-os, run in-target by the d-i
# late_command and readable afterwards via `sovereign-osctl install logs --from`.
#
# WHY THIS EXISTS. The direct-install path fails loudly (sovereign_verify_install).
# The debian-installer path had no verification at all: it installed every
# package, registered sddm as display-manager, finished with zero failed units
# -- and produced a dark screen, because the kernel booted without nomodeset and
# so had no framebuffer for X to open (2026-07-26). A silent success is what
# cost the operator a day.
#
# This NEVER fails the install. d-i has already partitioned and unpacked by the
# time it runs; aborting here would leave a half-installed disk and tell the
# operator nothing. It writes evidence instead.
set -u
OUT=/var/log/sovereign-os/install-verify.log
mkdir -p /var/log/sovereign-os

{
  echo "== sovereign-os install self-check =="
  echo

  echo "-- kernel cmdline that GRUB will use --"
  grep -m2 -E "^[[:space:]]*linux[[:space:]]" /boot/grub/grub.cfg 2>/dev/null \
    || echo "  NO grub.cfg -- nothing will boot"
  # nomodeset is the difference between a desktop and a dark screen on hardware
  # where no GPU driver binds. Call it out by name.
  if grep -qE "^[[:space:]]*linux.*[[:space:]]nomodeset([[:space:]]|$)" \
       /boot/grub/grub.cfg 2>/dev/null; then
    echo "  OK: nomodeset present"
  else
    echo "  PROBLEM: nomodeset ABSENT -- no EFI framebuffer, X cannot start"
  fi
  echo

  echo "-- display manager --"
  dm=$(readlink /etc/systemd/system/display-manager.service 2>/dev/null || true)
  [ -n "${dm}" ] && echo "  ${dm}" || echo "  PROBLEM: none registered -- nothing starts a session"
  echo

  echo "-- module blacklists --"
  ls /etc/modprobe.d/sovereign-blacklist-* 2>/dev/null || echo "  none"
  echo

  echo "-- packages --"
  for p in sddm plasma-desktop xserver-xorg-core xserver-xorg-video-fbdev \
           xserver-xorg-video-vesa firmware-amd-graphics sovereign-os-cockpit; do
    if dpkg -s "${p}" >/dev/null 2>&1; then
      echo "  ok      ${p}"
    else
      echo "  MISSING ${p}"
    fi
  done
  echo

  echo "-- kernels --"
  ls /boot/vmlinuz-* 2>/dev/null || echo "  none"
} > "${OUT}" 2>&1

exit 0
