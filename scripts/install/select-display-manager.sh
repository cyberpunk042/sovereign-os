#!/bin/sh
# Make a specific display manager THE display manager.
#
# WHY. `systemctl enable sddm` does NOT make sddm the display manager on
# Debian/Ubuntu. The active DM is decided by two things the enable never touches:
#
#   /etc/X11/default-display-manager        (debconf's choice, read by the
#                                            DM packages' init integration)
#   /etc/systemd/system/display-manager.service   (an alias symlink; whichever
#                                            package claimed it first keeps it)
#
# WHAT THIS COST (2026-07-29). The first full Ubuntu install ran to completion
# and booted to a BLACK SCREEN WITH A BLINKING CURSOR — the operator's own
# words for the 2026-07-26 failure, reproduced exactly in a VM. Everything the
# earlier fixes targeted was correct on disk: nomodeset on the kernel line, a
# valid route to a graphical seat, sddm installed, kubuntu-desktop installed.
# But the image is built from the Ubuntu DESKTOP ISO, whose base install is
# GNOME, so display-manager.service still pointed at gdm3:
#
#     display-manager.service -> /lib/systemd/system/gdm3.service
#
# gdm3 wants a DRM device for its Wayland greeter, and nomodeset is precisely
# the flag that removes one. sddm on X11/fbdev is the configuration PROVEN on
# this hardware (the operator's working Debian runs exactly that). So the
# desktop package set is not enough — the DM must be selected explicitly.
#
# Idempotent. Safe to run on a system that already has the right DM.
#
# Usage:  select-display-manager.sh [sddm|gdm3|lightdm]     (default: sddm)
set -eu

DM="${1:-sddm}"
UNIT="/lib/systemd/system/${DM}.service"
[ -f "${UNIT}" ] || UNIT="/usr/lib/systemd/system/${DM}.service"

if [ ! -f "${UNIT}" ]; then
  echo "select-display-manager: ${DM}.service not installed — leaving the DM alone" >&2
  exit 0
fi

# 1. debconf's record of the choice. The DM packages read this file; without it
#    a later dpkg-reconfigure or upgrade silently reverts to the other DM.
_bin="/usr/bin/${DM}"
[ -x "${_bin}" ] || _bin="/usr/sbin/${DM}"
if [ -x "${_bin}" ]; then
  mkdir -p /etc/X11
  printf '%s\n' "${_bin}" > /etc/X11/default-display-manager
fi
if command -v debconf-set-selections >/dev/null 2>&1; then
  printf '%s shared/default-x-display-manager select %s\n' "${DM}" "${DM}" \
    | debconf-set-selections 2>/dev/null || true
fi

# 2. Disable every OTHER display manager, or two will race for the seat.
for _other in gdm3 gdm lightdm sddm lxdm xdm; do
  [ "${_other}" = "${DM}" ] && continue
  systemctl disable "${_other}.service" >/dev/null 2>&1 || true
done

# 3. Take the alias. `enable` will not steal it from an existing owner, so
#    replace the symlink directly — this is the step that was missing.
ln -sf "${UNIT}" /etc/systemd/system/display-manager.service
systemctl enable "${DM}.service" >/dev/null 2>&1 || true

echo "select-display-manager: ${DM} is now the display manager"
echo "  display-manager.service -> $(readlink -f /etc/systemd/system/display-manager.service 2>/dev/null)"
echo "  verify after boot:  loginctl show-seat seat0 -p CanGraphical   # must be yes"
exit 0
