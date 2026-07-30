#!/usr/bin/env bash
# GRUB default kernel — pin the boot entry
# gate: IAC_ENABLE_BOOT
#
# WHY: this machine shipped booting a hand-built 6.12.0 while Ubuntu 26.04's
# stock kernel is 7.0.0-28-generic. Every symbol profiles.kernel.config.enable
# asks for (AQTION, VFIO_PCI, VFIO_IOMMU_TYPE1, INTEL_IOMMU, AMD_IOMMU, BPF_LSM,
# KVM_AMD, KVM_INTEL, SYSFB_SIMPLEFB, DRM_SIMPLEDRM) is ALREADY set in stock, so
# the custom build added nothing and subtracted:
#     - ZFS entirely (Ubuntu ships zfs per-ABI as linux-main-modules-zfs-*,
#       NOT via DKMS, so a custom kernel gets no module at all)
#     - 2,675 driver modules (4,233 vs 6,908)
#     - Secure Boot signing (the custom image is unsigned)
#     - CONFIG_INTEL_IOMMU_DEFAULT_ON, which stock sets
# The custom kernel was also seeded cross-distro: os-prober finds Debian 13 on
# /dev/nvme1n1p2, and scripts/build/03-kernel-config.sh seeds .config from the
# BUILD HOST's running kernel — its own comments warn that seeding an Ubuntu
# target from a Debian host "produces a kernel that matches NEITHER distro".
#
# This module only sets the DEFAULT. Every installed kernel stays in the menu,
# so a bad boot is one GRUB selection away from recovery.
#
# shellcheck shell=bash

_want="${IAC_BOOT_KERNEL:-}"
if [ -z "${_want}" ]; then
  # Default: the newest installed *packaged* kernel. Deliberately ignores
  # unpackaged/hand-built images — those are opt-in, never the auto-default.
  _want="$(dpkg-query -W -f='${Package}\n' 'linux-image-*-generic' 2>/dev/null \
           | sed 's/^linux-image-//; s/^unsigned-//' \
           | grep -E '^[0-9]' | sort -V | tail -1)"
fi

if [ -z "${_want}" ]; then
  skip "could not determine a packaged kernel to pin"
  return 0 2>/dev/null || exit 0
fi

iac_info "target default kernel: ${_want} (running: $(uname -r))"

for f in "/boot/vmlinuz-${_want}" "/boot/initrd.img-${_want}"; do
  if [ ! -e "${f}" ]; then
    fail "missing ${f} — refusing to pin a kernel that cannot boot"
    return 0 2>/dev/null || exit 0
  fi
done

# Out-of-tree modules must exist for the target or the GPUs go dark on reboot.
if command -v dkms >/dev/null 2>&1; then
  if dkms status 2>/dev/null | grep -q "${_want}.*installed"; then
    ok "dkms modules built for ${_want}"
  else
    fail "no DKMS module built for ${_want} — the NVIDIA driver would not load; refusing to pin"
    return 0 2>/dev/null || exit 0
  fi
fi

_uuid="$(findmnt -no UUID / 2>/dev/null)"
_entry="gnulinux-${_want}-advanced-${_uuid}"
_cur="$(grub-editenv list 2>/dev/null | sed -n 's/^saved_entry=//p')"

if [ "${_cur}" = "${_entry}" ]; then
  ok "grub default = ${_want}"
else
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "grub default: ${_cur:-none} → ${_entry}"
  else
    # grub.cfg must contain the entry id before saving it, or GRUB silently
    # falls through to the first menu entry on next boot.
    if ! grep -q "${_entry}" /boot/grub/grub.cfg 2>/dev/null; then
      update-grub >/dev/null 2>&1 || true
    fi
    if ! grep -q "${_entry}" /boot/grub/grub.cfg 2>/dev/null; then
      fail "entry id not in grub.cfg after update-grub: ${_entry}"
    elif run "grub-set-default" grub-set-default "${_entry}"; then
      changed "grub default: ${_cur:-none} → ${_want}"
      iac_info "reboot required to land on ${_want}"
    else
      fail "grub-set-default ${_entry}"
    fi
  fi
fi

# GRUB_DEFAULT must be 'saved' for saved_entry to be honoured at all.
_gd="$(sed -n 's/^GRUB_DEFAULT=//p' /etc/default/grub 2>/dev/null | tr -d '"')"
if [ "${_gd}" = "saved" ]; then
  ok "GRUB_DEFAULT=saved"
else
  fail "GRUB_DEFAULT is '${_gd}' not 'saved' — saved_entry will be ignored"
fi

if [ "$(uname -r)" != "${_want}" ]; then
  iac_info "note: running $(uname -r) — pinned ${_want} takes effect on next boot"
fi
