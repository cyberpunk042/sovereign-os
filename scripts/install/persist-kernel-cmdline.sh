#!/bin/sh
# Make the sovereign-os kernel cmdline PERMANENT on a running installed system.
#
# WHY. A one-time `e` at the GRUB menu proved the diagnosis: with nomodeset the
# machine boots to a functional KDE Plasma desktop; without it nouveau attempts
# KMS on the Blackwell cards, fails ("unknown chipset (1b2000a1)"), no EFI
# framebuffer is established, /dev/fb0 never appears, and X has no device to
# open -- a clean install, zero failed units, dark screen (2026-07-27).
#
# That edit does not survive reboot. New installs get this via the preseed
# (debian-installer/add-kernel-opts); this repairs an EXISTING install without
# reinstalling it.
#
# Run it ON the installed system, as root. Idempotent: run it as many times as
# you like. Reads the option set from the ONE definition, so it cannot drift
# from what a fresh install would receive.
set -eu

DEFAULT=/etc/default/grub
[ "$(id -u)" -eq 0 ] || { echo "must run as root: sudo $0" >&2; exit 1; }
[ -f "${DEFAULT}" ] || { echo "no ${DEFAULT} — is GRUB installed?" >&2; exit 1; }

# Prefer the shared definition when the payload is present, so this stays in
# lockstep with installed-system.sh instead of hardcoding a second copy.
WANT="${SOVEREIGN_OS_KERNEL_CMDLINE:-}"
if [ -z "${WANT}" ] && [ -r /opt/sovereign-os/scripts/install/lib/installed-system.sh ]; then
  WANT="$(. /opt/sovereign-os/scripts/install/lib/installed-system.sh 2>/dev/null \
          && printf '%s' "${SOVEREIGN_OS_KERNEL_CMDLINE}")" || WANT=""
fi
[ -n "${WANT}" ] || WANT="nomodeset"

# nomodeset and the NVIDIA DRM driver are MUTUALLY EXCLUSIVE.
# nvidia-blackwell-driver-install.sh deliberately strips nomodeset and adds
# nvidia-drm.modeset=1; re-adding nomodeset here would silently undo that and
# put the machine back on the framebuffer — the exact repair this script exists
# to perform, applied at the one moment it is wrong (2026-07-27).
if grep -q 'nvidia-drm\.modeset=1' "${DEFAULT}" 2>/dev/null \
   || grep -q 'nvidia-drm\.modeset=1' /proc/cmdline 2>/dev/null; then
  case " ${SOVEREIGN_OS_KERNEL_CMDLINE:-nomodeset} " in
    *" nomodeset "*)
      echo "REFUSING: this system runs the NVIDIA DRM driver (nvidia-drm.modeset=1)." >&2
      echo "  Adding 'nomodeset' would disable it and return the box to the" >&2
      echo "  framebuffer. If that is really what you want, re-run with:" >&2
      echo "    SOVEREIGN_OS_KERNEL_CMDLINE='' $0" >&2
      exit 1 ;;
  esac
fi

cur="$(sed -n 's/^GRUB_CMDLINE_LINUX_DEFAULT="\(.*\)"$/\1/p' "${DEFAULT}" | head -1)"
new="${cur}"
changed=0
for opt in ${WANT}; do
  case " ${new} " in
    *" ${opt} "*) echo "already present: ${opt}" ;;
    *) new="${new:+${new} }${opt}"; changed=1; echo "adding: ${opt}" ;;
  esac
done

if [ "${changed}" -eq 0 ]; then
  echo "kernel cmdline already carries: ${WANT}"
  exit 0
fi

cp -a "${DEFAULT}" "${DEFAULT}.sovereign-bak"
if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' "${DEFAULT}"; then
  sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT=\"${new}\"|" "${DEFAULT}"
else
  printf 'GRUB_CMDLINE_LINUX_DEFAULT="%s"\n' "${new}" >> "${DEFAULT}"
fi
echo "GRUB_CMDLINE_LINUX_DEFAULT=\"${new}\"  (backup: ${DEFAULT}.sovereign-bak)"

update-grub
echo "done — reboot and the option persists without touching the GRUB menu"
