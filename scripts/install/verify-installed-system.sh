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
  # WHICH one boots. A desktop install pulls in Debian's stock kernel
  # (6.12.96+deb13) alongside the custom znver5 build (6.12.0), and GRUB sorts
  # 6.12.96 ABOVE 6.12.0 -- so without a working pin the whole custom-kernel
  # build is unused. set-grub-default-kernel.sh writes saved_entry into grubenv;
  # listing the kernels present says nothing about which one is chosen.
  echo "  GRUB_DEFAULT : $(grep -m1 "^GRUB_DEFAULT=" /etc/default/grub 2>/dev/null || echo "unset")"
  if [ -f /boot/grub/grubenv ]; then
    echo "  saved_entry  : $(grep -m1 "^saved_entry=" /boot/grub/grubenv 2>/dev/null || echo "none -- GRUB boots the FIRST menu entry")"
  else
    echo "  saved_entry  : no grubenv"
  fi
  echo

  # Does sovereign-os itself exist on this machine, or is it just Debian+KDE?
  # The cockpit postinst runs install-gui-dashboards.sh behind `|| true`, so a
  # total failure there is invisible: the install still "succeeds" and the
  # operator gets a desktop with no sovereign-os in it (2026-07-26).
  echo "-- sovereign-os itself --"
  if [ -L /usr/local/lib/sovereign-os ]; then
    echo "  app tree: SYMLINK -> $(readlink /usr/local/lib/sovereign-os)"
    echo "    (the dashboards deploy did not run; units resolve via the fallback)"
  elif [ -d /usr/local/lib/sovereign-os ]; then
    echo "  app tree: deployed at /usr/local/lib/sovereign-os"
  else
    echo "  app tree: MISSING -- every unit ExecStarting from there will fail"
  fi
  # 68 units exec from that path and 67 carry Restart=; a missing path means
  # dozens of services failing and restarting forever.
  echo "  units present : $(ls /lib/systemd/system/sovereign-*.service 2>/dev/null | wc -l)"
  echo "  units enabled : $(ls /etc/systemd/system/*.wants/sovereign-*.service 2>/dev/null | wc -l)"
  echo "  dashboards hub:"
  for u in sovereign-dashboards.service sovereign-master-dashboard-api.service; do
    if [ -e "/etc/systemd/system/multi-user.target.wants/${u}" ]; then
      echo "    enabled  ${u}"
    else
      echo "    off      ${u}"
    fi
  done
} > "${OUT}" 2>&1

exit 0
