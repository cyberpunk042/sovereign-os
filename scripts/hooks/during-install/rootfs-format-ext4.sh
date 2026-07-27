#!/usr/bin/env bash
# scripts/hooks/during-install/rootfs-format-ext4.sh
#
# Format the rootfs device as ext4. Used for old-workstation profile
# (constrained hardware; ZFS overkill). Reads device from
# SOVEREIGN_OS_ROOTFS_DEV env var.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="rootfs-format-ext4"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_ROOTFS_DEV:=}"

log_step_header "${STEP_ID}" "format rootfs (ext4)"

emit_format_metric() {
  emit_metric sovereign_os_during_install_rootfs_format_total 1 \
    "device=\"${SOVEREIGN_OS_ROOTFS_DEV:-unset}\",result=\"$1\""
}

layout="$(profile_field hardware.storage.layout)"
if [ "${layout}" != "ext4" ]; then
  log_info "profile layout is '${layout}' (not ext4); skipping"
  emit_format_metric skip-layout
  exit 0
fi

if [ -z "${SOVEREIGN_OS_ROOTFS_DEV}" ]; then
  log_error "SOVEREIGN_OS_ROOTFS_DEV must be set (e.g. /dev/sda3)"
  emit_format_metric missing-device
  exit 1
fi

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would mkfs.ext4 -L sovereign-rootfs ${SOVEREIGN_OS_ROOTFS_DEV}"
  emit_format_metric skip-dry-run
  exit 0
fi

require_root
require_command mkfs.ext4

# Refuse if the device -- OR ANYTHING STACKED ON IT -- is in use.
#
# `mount | grep "^${dev} "` only catches a device mounted DIRECTLY. It misses:
#   * a whole disk whose PARTITIONS are mounted (mount never names the disk), and
#   * a PV partition beneath a mounted LVM root (mount shows
#     /dev/mapper/sovereign-root, never the partition underneath).
# Verified on this hardware: `mount | grep "^/dev/nvme1n1 "` returns nothing
# while that disk carries /, /boot/efi and swap -- so mkfs on the live disk
# passed the guard cleanly (2026-07-27).
#
# lsblk reports mountpoints for the device AND its descendants, which is the
# question actually being asked.
_in_use="$(lsblk -nro MOUNTPOINTS "${SOVEREIGN_OS_ROOTFS_DEV}" 2>/dev/null | grep -c . || true)"
if [ "${_in_use:-0}" -gt 0 ]; then
  log_error "device ${SOVEREIGN_OS_ROOTFS_DEV} (or something on it) is mounted; refusing to format"
  lsblk -nro NAME,MOUNTPOINTS "${SOVEREIGN_OS_ROOTFS_DEV}" 2>/dev/null | grep . | sed 's/^/  /' || true
  emit_format_metric refuse-mounted
  exit 1
fi

# ...and never the disk hosting the running root, even if nothing is mounted
# from it right now. Resolution walks the full chain: PKNAME is the IMMEDIATE
# parent, so a single hop stops at the PV partition on an LVM root.
_parent_disk_of() {
  _d="$1"
  while :; do
    _p="$(lsblk -no PKNAME "${_d}" 2>/dev/null | head -1 | tr -d ' ')"
    [ -n "${_p}" ] || break
    _d="/dev/${_p}"
  done
  printf '%s\n' "${_d}"
}
_run_root_disk="$(_parent_disk_of "$(findmnt -no SOURCE / 2>/dev/null)" 2>/dev/null || true)"
if [ -n "${_run_root_disk}" ] && \
   [ "$(_parent_disk_of "${SOVEREIGN_OS_ROOTFS_DEV}")" = "${_run_root_disk}" ]; then
  log_error "device ${SOVEREIGN_OS_ROOTFS_DEV} is on the RUNNING root disk (${_run_root_disk}); refusing"
  emit_format_metric refuse-running-root
  exit 1
fi

# Refuse without explicit confirmation (SOVEREIGN_OS_ASSUME_YES bypass
# for scripted installer flows)
if [ "${SOVEREIGN_OS_ASSUME_YES:-}" != "1" ]; then
  if ! confirm "Format ${SOVEREIGN_OS_ROOTFS_DEV} as ext4? THIS WIPES ALL DATA." default-no; then
    log_info "aborted by operator"
    emit_format_metric refuse-confirm
    exit 1
  fi
fi

log_info "formatting ${SOVEREIGN_OS_ROOTFS_DEV} as ext4"
if mkfs.ext4 -L sovereign-rootfs "${SOVEREIGN_OS_ROOTFS_DEV}" 2>&1 | sed 's/^/  /'; then
  emit_format_metric success
  log_info "${STEP_ID} complete"
else
  rc=${PIPESTATUS[0]}
  log_error "mkfs.ext4 failed (rc=${rc})"
  emit_format_metric fail
  exit 1
fi
