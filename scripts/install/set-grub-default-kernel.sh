#!/bin/sh
# scripts/install/set-grub-default-kernel.sh — make a specific kernel version the
# DEFAULT GRUB boot entry, keeping the others (e.g. the stock Debian kernel pulled
# in by the desktop task) available as fallbacks.
#
# Why: the sovereign-os desktop install ends up with BOTH the custom kernel
# (linux-image-6.12.0) and the stock Debian kernel (linux-image-amd64 →
# 6.12.96+deb13, dragged in by task-kde-desktop). GRUB orders kernels by version
# and 6.12.96 sorts NEWER than 6.12.0, so without this the box boots the stock
# kernel. This pins the custom kernel as the default; the stock one stays in the
# menu as a fallback.
#
# Run inside the target (the installer calls it via `in-target`), or on a running
# system as root.  Usage: set-grub-default-kernel.sh <version>   e.g. 6.12.0
set -e

KVER="${1:?usage: set-grub-default-kernel.sh <kernel-version, e.g. 6.12.0>}"
GRUBFILE=/etc/default/grub
GRUBCFG=/boot/grub/grub.cfg

[ -f "${GRUBFILE}" ] || { echo "set-grub-default-kernel: ${GRUBFILE} not found (grub not installed?)" >&2; exit 0; }

# GRUB_DEFAULT=saved so grub-set-default sticks across kernel updates.
if grep -q '^GRUB_DEFAULT=' "${GRUBFILE}"; then
  sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=saved/' "${GRUBFILE}"
else
  printf 'GRUB_DEFAULT=saved\n' >> "${GRUBFILE}"
fi
# Flatten the menu (no "Advanced options" submenu) so every kernel is a top-level
# entry that grub-set-default can target directly by its id.
if grep -q '^GRUB_DISABLE_SUBMENU=' "${GRUBFILE}"; then
  sed -i 's/^GRUB_DISABLE_SUBMENU=.*/GRUB_DISABLE_SUBMENU=y/' "${GRUBFILE}"
else
  printf 'GRUB_DISABLE_SUBMENU=y\n' >> "${GRUBFILE}"
fi

update-grub

# Find the menuentry id for our kernel (prefer the plain/advanced entry, not the
# recovery one) and pin it as the saved default.
id=$(awk -F"'" '/\$menuentry_id_option/ && /'"${KVER}"'/ && !/recovery/ {print $2; exit}' "${GRUBCFG}" 2>/dev/null || true)
if [ -n "${id}" ]; then
  grub-set-default "${id}"
  echo "set-grub-default-kernel: GRUB default → ${KVER}  (id=${id})"
else
  echo "set-grub-default-kernel: ‼ no GRUB entry found for ${KVER}; default left unchanged" >&2
fi
